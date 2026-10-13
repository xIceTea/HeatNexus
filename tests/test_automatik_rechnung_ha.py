"""Rechnungen der Automatik mit Home Assistant: Lernstunden, Lesefehler, Ziel der Stunde.

Die Lernstunden werden gegen die lineare Rechnung geprüft, die Aufzeichnung ist eine Attrappe.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import random
import time

import pytest

from . import test_automatik_ha as ha
from .conftest import requires_ha
from .test_automatik_rechnung import zufallsreihe

pytestmark = requires_ha()

# Die Anlage mit Automatik aus den übrigen Automatiktests.
anlage = ha.anlage

ANFANG = datetime(2026, 10, 1, tzinfo=UTC)


def _jetzt() -> datetime:
    from homeassistant.util import dt as dt_util

    return dt_util.now()


def _linear(reihen, art, raum_art, zeiten, boegen):
    """Die Lernstunden wie vor der Bisektion: jede Abfrage durchläuft die ganze Reihe."""
    from custom_components.heatnexus.automatik import eingaben, hausmodell, tagesansicht

    raum = [
        eingaben.raumwert([eingaben.mittel_der_stunde(r, z) for r in reihen.raeume], raum_art)
        for z in zeiten
    ]
    ganz = []
    for z, r in zip(zeiten, raum, strict=True):
        at = eingaben.mittel_der_stunde(reihen.at, z)
        quelle = eingaben.mittel_der_stunde(reihen.heizen, z)
        if r is None or at is None or quelle is None:
            ganz.append(None)
            continue
        wolken = eingaben.wert_zur_stunde(reihen.wolken, z)
        bogen = boegen.get(z.date())
        sonne = 0.0 if bogen is None else tagesansicht.sonnenanteil(z.hour, *bogen, wolken)
        heizen = quelle if art == "pumpe" else max(0.0, quelle - r)
        wind = eingaben.wert_zur_stunde(reihen.wind, z)
        ganz.append(hausmodell.Stunde(r, None, at, sonne, wind, heizen))
    ergebnis = {}
    for i, stunde in enumerate(ganz[:-1]):
        if stunde is not None:
            danach = raum[i + 1] if ganz[i + 1] is not None else None
            ergebnis.setdefault(zeiten[i].date(), []).append(replace(stunde, raum_danach=danach))
    return ergebnis


def _zufallsreihen(saat: int, stunden: int):
    from custom_components.heatnexus.automatik.vorausschau import Reihen

    zufall = random.Random(saat)
    return Reihen(
        [zufallsreihe(zufall, ANFANG, stunden) for _ in range(3)],
        *(zufallsreihe(zufall, ANFANG, stunden) for _ in range(4)),
    )


@pytest.mark.parametrize(("saat", "art"), [(1, "vorlauf"), (2, "pumpe"), (3, "vorlauf")])
@pytest.mark.parametrize("raum_art", ["mittel", "minimum"])
def test_lernstunden_gleichen_der_linearen_rechnung(saat, art, raum_art):
    from custom_components.heatnexus.automatik.vorausschau import lernstunden

    reihen = _zufallsreihen(saat, 96)
    zeiten = [ANFANG + timedelta(hours=h) for h in range(97)]
    boegen = {(ANFANG + timedelta(days=t)).date(): (7.5, 18.25) for t in range(4)}

    assert lernstunden(reihen, art, raum_art, zeiten, boegen) == _linear(
        reihen, art, raum_art, zeiten, boegen
    )


def test_lernstunden_aus_minutenwerten_blockieren_nicht():
    from custom_components.heatnexus.automatik.vorausschau import Reihen, lernstunden

    # Ein Fühler mit Minutentakt über vierzehn Tage, je Raum, Außentemperatur und Vorlauf.
    minuten = [(ANFANG + timedelta(minutes=i), 20.0 + i % 7 / 10) for i in range(14 * 24 * 60)]
    reihen = Reihen([minuten, minuten, minuten], minuten, minuten, [], [])
    zeiten = [ANFANG + timedelta(hours=h) for h in range(14 * 24 + 1)]

    beginn = time.perf_counter()
    stunden = lernstunden(reihen, "vorlauf", "mittel", zeiten, {})
    dauer = time.perf_counter() - beginn

    assert sum(len(s) for s in stunden.values()) == 14 * 24
    assert dauer < 1.0


class _Executor:
    """Wie der Executor der Aufzeichnung: Die Abfrage kehrt erst nach einem Wechsel zurück."""

    async def async_add_executor_job(self, aufgabe):
        await asyncio.sleep(0)
        return aufgabe()


async def test_ein_lesefehler_warnt_einmal(hass, anlage, freezer, monkeypatch, caplog):
    import logging

    from homeassistant.components.recorder import history

    verwaltung, _ = anlage
    freezer.move_to(ha.MORGEN)
    laufzeit = await ha._eingerichtet(hass, verwaltung)
    await hass.async_block_till_done(wait_background_tasks=True)
    ha._verlauf_bereit(hass, monkeypatch, {})

    def scheitern(*_argumente, **_benannt):
        raise RuntimeError("Datenbank gesperrt")

    monkeypatch.setattr(history, "get_significant_states", scheitern)
    caplog.set_level(logging.DEBUG)

    for _ in range(2):
        assert await laufzeit._verlauf_lesen([], ["sensor.wohnzimmer"], _jetzt()) is None

    meldungen = [r for r in caplog.records if "Verlauf nicht lesbar" in r.getMessage()]
    assert [r.levelno for r in meldungen] == [logging.WARNING, logging.DEBUG]


PROGRAMM = [
    {
        "weekdays": ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"],
        "switchPoints": [{"time": "00:00", "value": "21"}, {"time": "18:00", "value": "20.5"}],
    }
]


@pytest.mark.parametrize(("behaglichkeit", "erwartet"), [(None, 20.5), ("1.0", 21.5)])
async def test_kuenftiges_ziel_behaelt_die_behaglichkeit(
    hass, anlage, freezer, behaglichkeit, erwartet
):
    # `1/1` enthält die Behaglichkeit `3/58`, die Schaltpunkte des Programms nicht.
    verwaltung, coordinator = anlage
    freezer.move_to(ha.MORGEN)
    laufzeit = await ha._eingerichtet(hass, verwaltung)
    zuschlag = float(behaglichkeit or 0)
    coordinator.data["oids"][f"{ha.PREFIX}/1/1/0"] = str(21.0 + zuschlag)
    if behaglichkeit is not None:
        coordinator.data["oids"][f"{ha.PREFIX}/3/58/0"] = behaglichkeit
    hass.states.async_set("sensor.wohnzimmer", "21.8")
    await laufzeit.auswerten()
    lage = laufzeit.lage
    abends = lage.jetzt.replace(hour=19, minute=0)

    assert laufzeit._ziel(lage, PROGRAMM, lage.jetzt.replace(hour=12)) == 21.0 + zuschlag
    assert laufzeit._ziel(lage, PROGRAMM, abends) == pytest.approx(erwartet)


async def test_system_geraet_traegt_den_namen_der_anlage(hass, anlage):
    hass.config.language = "de"
    from homeassistant.helpers import device_registry as dr

    from custom_components.heatnexus.automatik import system
    from custom_components.heatnexus.registrierung import geraet_suchen

    verwaltung, _ = anlage
    entry = hass.config_entries.async_entries("heatnexus")[0]
    hass.config_entries.async_update_entry(entry, title="Hebebühne")
    await ha._eingerichtet(hass, verwaltung)
    register = dr.async_get(hass)
    geraet = geraet_suchen(register, system.system_kennung(entry.entry_id), entry.entry_id)
    register.async_update_device(geraet.id, name_by_user="Mein System")

    status = system.KLASSEN["status"](verwaltung, entry.entry_id)
    info = status.device_info
    # So legt die Plattform das Gerät an: Ein vorhandenes behält den Namen des Nutzers.
    neu = register.async_get_or_create(config_entry_id=entry.entry_id, **info)

    assert info["name"] == "Automatik Hebebühne"
    assert (neu.id, neu.name, neu.name_by_user) == (geraet.id, "Automatik Hebebühne", "Mein System")
    assert status.unique_id == system.system_unique_id(entry.entry_id, "status")


