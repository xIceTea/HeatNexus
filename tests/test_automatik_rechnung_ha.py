"""Rechnungen der Automatik mit Home Assistant: Lernstunden, gemeinsamer Verlauf, Ziel der Stunde.

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
from . import test_automatik_optimierung as opt
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


async def test_hausmodell_und_nachrechnen_teilen_eine_abfrage(hass, anlage, freezer, monkeypatch):
    from homeassistant.components import recorder
    from homeassistant.components.recorder import history

    verwaltung, coordinator = anlage
    laufzeit = await opt._laufzeit(hass, verwaltung, freezer)
    opt._aufzeichnung(hass, monkeypatch, opt._historie(hass, coordinator))
    gelesen = history.get_significant_states
    lerntage = []

    def gezaehlt(_hass, anfang, *argumente, **benannt):
        # Das Nachtragen von heute liest nur den laufenden Tag; gezählt werden die Lerntage.
        if anfang < _jetzt() - timedelta(days=2):
            lerntage.append(benannt.get("no_attributes"))
        return gelesen(_hass, anfang, *argumente, **benannt)

    monkeypatch.setattr(history, "get_significant_states", gezaehlt)
    monkeypatch.setattr(recorder, "get_instance", lambda _hass: _Executor(), raising=False)

    await laufzeit.neu_starten(laufzeit.konfig)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert sorted(lerntage) == [False, True]
    assert len(laufzeit.archivierte_tage()) == opt.HEIZTAGE
    assert laufzeit.archiv_nachgerechnet == opt.FASSUNG


async def test_ein_lesefehler_warnt_einmal(hass, anlage, freezer, monkeypatch, caplog):
    import logging

    from homeassistant.components.recorder import history

    verwaltung, coordinator = anlage
    laufzeit = await opt._laufzeit(hass, verwaltung, freezer)
    opt._aufzeichnung(hass, monkeypatch, opt._historie(hass, coordinator))

    def scheitern(*_argumente, **_benannt):
        raise RuntimeError("Datenbank gesperrt")

    monkeypatch.setattr(history, "get_significant_states", scheitern)
    caplog.set_level(logging.DEBUG)

    for _ in range(2):
        assert await laufzeit._verlauf_lesen([], ["sensor.wohnzimmer"], _jetzt()) is None

    meldungen = [r for r in caplog.records if "Verlauf nicht lesbar" in r.getMessage()]
    assert [r.levelno for r in meldungen] == [logging.WARNING, logging.DEBUG]
