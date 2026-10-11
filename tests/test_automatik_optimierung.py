"""Optimierungshinweise in Home Assistant: das Archiv aus der Aufzeichnung nachrechnen.

Die Aufzeichnung ist eine Attrappe; sie liefert je Entität die Zustände, die der Test vorgibt.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from . import test_automatik_ha as ha
from .conftest import requires_ha

pytestmark = requires_ha()

# Die Anlage mit Automatik aus den übrigen Automatiktests.
anlage = ha.anlage
ERSTER = date(2026, 9, 17)
HEIZTAGE = 10
# Heute ist der 27.09. (`ha.MORGEN`); die Aufzeichnung reicht bis zum Vortag.
TAGE = [(ERSTER + timedelta(days=i)).isoformat() for i in range(HEIZTAGE)]
HEUTE = "2026-09-27"


def _zeit(tag: int, stunde: int = 0, minute: int = 0):
    from homeassistant.util import dt as dt_util

    beginn = dt_util.start_of_local_day(ERSTER + timedelta(days=tag))
    return beginn + timedelta(hours=stunde, minutes=minute)


def _zustaende(kennung: str, *werte, attribute: dict | None = None) -> list:
    """Zustände einer Entität aus `(tag, stunde, minute, wert)`."""
    from homeassistant.core import State

    return [
        State(kennung, str(wert), attribute or {}, last_updated=_zeit(tag, stunde, minute))
        for tag, stunde, minute, wert in werte
    ]


def _historie(hass, coordinator) -> dict[str, list]:
    """Zehn Tage im Heizbetrieb: AT 10 °C, Raum 21,2 °C bei Raumsoll 21 °C.

    Am dritten Tag läuft eine halbe Stunde lang eine Vorgabe am Gerät.
    """
    aussen, soll, vl, ba, restzeit = ha._entitaeten(
        hass,
        [
            ("sensor", "0-0-0"),
            ("sensor", "1-1-0"),
            ("sensor", "1-2-0"),
            ("sensor", "2-9-0"),
            ("number", "2-10-0"),
        ],
    )
    coordinator.data["devices"].append(
        {
            "type": "enum_sensor",
            "id": f"{ha.HEIZKREIS}-2-9-0",
            "device_id": ha.HEIZKREIS,
            "oid": f"{ha.PREFIX}/2/9/0",
            "enum": "2/9",
        }
    )
    return {
        aussen: _zustaende(aussen, (0, 0, 0, 10.0)),
        soll: _zustaende(soll, (0, 0, 0, 21.0)),
        vl: _zustaende(vl, (0, 0, 0, 40.0)),
        ba: _zustaende(ba, (0, 0, 0, "Heizbetrieb")),
        restzeit: _zustaende(restzeit, (0, 0, 0, 0), (2, 10, 0, 60), (2, 10, 30, 0)),
        "sensor.wohnzimmer": _zustaende("sensor.wohnzimmer", (0, 0, 0, 21.2)),
    }


async def _laufzeit(hass, verwaltung, freezer):
    """Eine eingerichtete Automatik; der erste Start lief ohne Aufzeichnung."""
    freezer.move_to(ha.MORGEN)
    laufzeit = await ha._eingerichtet(hass, verwaltung)
    await hass.async_block_till_done(wait_background_tasks=True)
    laufzeit.tage_archiv = []
    return laufzeit


async def test_leeres_archiv_wird_beim_start_nachgerechnet(hass, anlage, freezer, monkeypatch):
    verwaltung, coordinator = anlage
    laufzeit = await _laufzeit(hass, verwaltung, freezer)
    assert laufzeit.archiv_nachgerechnet is False
    ha._verlauf_bereit(hass, monkeypatch, _historie(hass, coordinator))

    await laufzeit.neu_starten(laufzeit.konfig)
    await hass.async_block_till_done(wait_background_tasks=True)

    tage = laufzeit.archivierte_tage()
    assert [t.datum for t in tage] == TAGE
    assert all(t.nachgerechnet for t in tage)
    assert (tage[0].at, tage[0].soll, tage[0].stunden) == (10.0, 21.0, 24)
    assert tage[0].abweichung == pytest.approx(0.2)
    assert [t.datum for t in tage if not t.ungestoert] == [TAGE[2]]
    assert laufzeit.archiv_nachgerechnet is True
    assert laufzeit.als_dict()["archiv_nachgerechnet"] is True


async def test_nachrechnen_liefert_die_zahl_neuer_tage(hass, anlage, freezer, monkeypatch):
    verwaltung, coordinator = anlage
    laufzeit = await _laufzeit(hass, verwaltung, freezer)
    ha._verlauf_bereit(hass, monkeypatch, _historie(hass, coordinator))

    assert await laufzeit.archiv_nachrechnen() == HEIZTAGE


async def test_nach_dem_nachrechnen_laeuft_kein_zweiter_lauf(hass, anlage, freezer, monkeypatch):
    verwaltung, coordinator = anlage
    laufzeit = await _laufzeit(hass, verwaltung, freezer)
    ha._verlauf_bereit(hass, monkeypatch, _historie(hass, coordinator))
    await laufzeit.archiv_nachrechnen()
    aufrufe = []

    async def gezaehlt() -> int:
        aufrufe.append(True)
        return 0

    monkeypatch.setattr(laufzeit, "archiv_nachrechnen", gezaehlt)
    await laufzeit.neu_starten(laufzeit.konfig)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert aufrufe == []


async def test_die_marke_wird_gespeichert_und_geladen(hass, anlage, freezer, monkeypatch):
    verwaltung, coordinator = anlage
    laufzeit = await _laufzeit(hass, verwaltung, freezer)
    ha._verlauf_bereit(hass, monkeypatch, _historie(hass, coordinator))
    await laufzeit.archiv_nachrechnen()
    zustand = laufzeit.als_dict()

    verwaltung.laufzeiten.pop(ha.HEIZKREIS).stoppen()
    verwaltung._daten["heizkreise"][ha.HEIZKREIS]["zustand"] = zustand
    await verwaltung._nachholen(hass.config_entries.async_entries("heatnexus")[0])

    assert verwaltung.laufzeiten[ha.HEIZKREIS].archiv_nachgerechnet is True


async def test_ohne_aufzeichnung_bleibt_alles_offen(hass, anlage, freezer):
    verwaltung, coordinator = anlage
    laufzeit = await _laufzeit(hass, verwaltung, freezer)
    _historie(hass, coordinator)

    assert await laufzeit.archiv_nachrechnen() == 0

    assert laufzeit.tage_archiv == []
    assert laufzeit.archiv_nachgerechnet is False


async def test_ein_lesefehler_setzt_keine_marke(hass, anlage, freezer, monkeypatch):
    from homeassistant.components.recorder import history

    verwaltung, coordinator = anlage
    laufzeit = await _laufzeit(hass, verwaltung, freezer)
    ha._verlauf_bereit(hass, monkeypatch, _historie(hass, coordinator))

    def scheitern(*_argumente, **_benannt):
        raise RuntimeError("Datenbank gesperrt")

    monkeypatch.setattr(history, "get_significant_states", scheitern)

    assert await laufzeit.archiv_nachrechnen() == 0
    assert laufzeit.tage_archiv == []
    assert laufzeit.archiv_nachgerechnet is False


async def test_ein_archivierter_tag_bleibt_unveraendert(hass, anlage, freezer, monkeypatch):
    verwaltung, coordinator = anlage
    laufzeit = await _laufzeit(hass, verwaltung, freezer)
    vorhanden = {
        "datum": TAGE[4],
        "at": -2.0,
        "abweichung": -0.7,
        "soll": 20.0,
        "morgen_min": 90,
        "ungestoert": True,
        "stunden": 20,
    }
    laufzeit.tage_archiv = [vorhanden]
    ha._verlauf_bereit(hass, monkeypatch, _historie(hass, coordinator))

    assert await laufzeit.archiv_nachrechnen() == HEIZTAGE - 1

    assert [t["datum"] for t in laufzeit.tage_archiv] == TAGE
    assert laufzeit.tage_archiv[4] == vorhanden


async def test_ein_parameterwechsel_beginnt_die_grundlage_neu(hass, anlage, freezer, monkeypatch):
    from custom_components.heatnexus.automatik import optimierer

    verwaltung, coordinator = anlage
    laufzeit = await _laufzeit(hass, verwaltung, freezer)
    zustaende = _historie(hass, coordinator)
    (fusspunkt,) = ha._entitaeten(hass, [("number", "3-1-0")])
    zustaende[fusspunkt] = _zustaende(fusspunkt, (0, 0, 0, 45.0), (4, 10, 0, 47.0))
    laufzeit.parameter_verlauf = {"3/1": [[HEUTE, 47.0]], "3/13": [[HEUTE, 80.0]]}
    ha._verlauf_bereit(hass, monkeypatch, zustaende)

    await laufzeit.archiv_nachrechnen()

    assert laufzeit.parameter_verlauf == {
        "3/1": [[TAGE[0], 45.0], [TAGE[4], 47.0]],
        "3/13": [[HEUTE, 80.0]],
    }
    fortschritt = optimierer.fortschritt(
        laufzeit.archivierte_tage(), laufzeit.parameter_verlauf, HEUTE
    )
    assert fortschritt["kurve_uebergang"] == HEIZTAGE - 5


async def test_ein_spaeterer_wechsel_der_lesung_bleibt(hass, anlage, freezer, monkeypatch):
    verwaltung, coordinator = anlage
    laufzeit = await _laufzeit(hass, verwaltung, freezer)
    zustaende = _historie(hass, coordinator)
    (fusspunkt,) = ha._entitaeten(hass, [("number", "3-1-0")])
    zustaende[fusspunkt] = _zustaende(fusspunkt, (0, 0, 0, 45.0))
    laufzeit.parameter_verlauf = {"3/1": [[HEUTE, 47.0]]}
    ha._verlauf_bereit(hass, monkeypatch, zustaende)

    await laufzeit.archiv_nachrechnen()

    assert laufzeit.parameter_verlauf == {"3/1": [[TAGE[0], 45.0], [HEUTE, 47.0]]}


async def test_ein_ausgeschalteter_thermostat_verhindert_keine_abweichung(
    hass, anlage, freezer, monkeypatch
):
    verwaltung, coordinator = anlage
    laufzeit = await _laufzeit(hass, verwaltung, freezer)
    zustaende = _historie(hass, coordinator)
    zustaende["climate.bad"] = _zustaende(
        "climate.bad", (0, 0, 0, "off"), attribute={"current_temperature": 17.0}
    )
    laufzeit.konfig = {**laufzeit.konfig, "raeume": ["sensor.wohnzimmer", "climate.bad"]}
    ha._verlauf_bereit(hass, monkeypatch, zustaende)

    await laufzeit.archiv_nachrechnen()

    tage = laufzeit.archivierte_tage()
    assert len(tage) == HEIZTAGE
    assert all(t.abweichung == pytest.approx(0.2) for t in tage)


async def test_raeume_zaehlen_gegen_ihr_eigenes_ziel(hass, anlage, freezer, monkeypatch):
    verwaltung, coordinator = anlage
    laufzeit = await _laufzeit(hass, verwaltung, freezer)
    zustaende = _historie(hass, coordinator)
    zustaende["climate.bad"] = _zustaende(
        "climate.bad",
        (0, 0, 0, "heat"),
        attribute={"current_temperature": 20.5, "temperature": 20.0},
    )
    raeume = ["sensor.wohnzimmer", "climate.bad"]
    laufzeit.konfig = {**laufzeit.konfig, "raeume": raeume, "raum_ziel": 21.5}
    ha._verlauf_bereit(hass, monkeypatch, zustaende)

    await laufzeit.archiv_nachrechnen()

    # Wohnzimmer gegen die Wunschtemperatur der Einrichtung, das Bad gegen sein Thermostat.
    assert laufzeit.archivierte_tage()[0].abweichung == pytest.approx((-0.3 + 0.5) / 2)


async def test_diagnose_zaehlt_nachgerechnete_tage(hass, anlage, freezer):
    from custom_components.heatnexus import diagnostics

    verwaltung, _ = anlage
    laufzeit = await _laufzeit(hass, verwaltung, freezer)
    laufzeit.tage_archiv = [
        {**tag, "nachgerechnet": i < 2} for i, tag in enumerate(ha._frosttage(3, -1.0))
    ]
    entry = hass.config_entries.async_entries("heatnexus")[0]

    (auszug,) = diagnostics.automatik_auszug(hass, entry)["heizkreise"]

    assert auszug["optimierer"]["nachgerechnete_tage"] == 2
    assert auszug["optimierer"]["archiv_nachgerechnet"] is False
