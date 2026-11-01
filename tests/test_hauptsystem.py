"""Hauptsystem der Oberfläche: welcher Wärmeerzeuger vorn steht.

Eine Anlage mit einem Kessel muss genauso aussehen wie vorher; erst
Wärmepumpe und Hybridmanager bringen Abschnitte und Spalten.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


def _e(entity_id: str, name: str) -> dict:
    return {
        "entity_id": entity_id,
        "name": name,
        "bereich": "sensor",
        "hat_wert": True,
        "schluessel": None,
        "kategorie": None,
    }


@pytest.fixture
def hs():
    from custom_components.heatnexus.panel import hauptsystem

    return hauptsystem


@pytest.fixture
def teile():
    biowin = {
        "name": "BioWIN",
        "fct_type": 9,
        "entitaeten": [_e("sensor.phase", "Betriebsphase"), _e("sensor.kl", "Kesselleistung")],
    }
    aerowin = {
        "name": "AeroWIN",
        "fct_type": 7,
        "entitaeten": [
            _e("sensor.wp_phase", "Betriebsphase"),
            _e("sensor.cop", "COP aktuell"),
            _e("sensor.vl", "Vorlauftemperatur"),
        ],
    }
    hybrid = {
        "name": "Hybrid",
        "fct_type": 26,
        "entitaeten": [_e("sensor.art", "Betriebsart"), _e("sensor.sg", "SG Ready Status")],
    }
    return biowin, aerowin, hybrid


def test_ein_kessel_allein_bleibt_wie_bisher(hs, teile):
    from custom_components.heatnexus.panel.muster import STATUS
    from custom_components.heatnexus.panel.suche import zeilen_aus

    biowin, _, _ = teile
    anlage = {"teile": [biowin]}
    alle = biowin["entitaeten"]
    assert hs.status(anlage, alle) == zeilen_aus(alle, STATUS)
    assert hs.nebensysteme(anlage) == []
    assert hs.teile_geordnet(anlage) == [biowin]


@pytest.mark.parametrize(
    ("wahl", "erwartet"),
    [
        ("auto", "hybrid"),
        ("hybrid", "hybrid"),
        ("waermepumpe", "waermepumpe"),
        ("kessel", "kessel"),
        ("unbekannt", "hybrid"),
    ],
)
def test_die_wahl_wird_aufgeloest(hs, teile, wahl, erwartet):
    assert hs.aufloesen(wahl, hs.erzeuger({"teile": list(teile)})) == erwartet


def test_ohne_hybridmanager_gewinnt_automatisch_die_waermepumpe(hs, teile):
    biowin, aerowin, _ = teile
    assert hs.aufloesen("auto", hs.erzeuger({"teile": [biowin, aerowin]})) == "waermepumpe"
    # Eine Wahl, die es an der Anlage nicht gibt, fällt auf die Automatik zurück.
    assert hs.aufloesen("hybrid", hs.erzeuger({"teile": [biowin, aerowin]})) == "waermepumpe"


def test_am_hybridmanager_zeigt_der_status_wer_laeuft(hs, teile):
    anlage = {"teile": list(teile), "hauptsystem": "auto"}
    zeilen = hs.status(anlage, [])
    assert zeilen[0] == {"abschnitt": "Hybrid"}
    titel = [z.get("titel") for z in zeilen[1:]]
    assert titel[:2] == ["Betriebsart", "SG Ready"]
    # Je Erzeuger eine Zeile mit seinem Betriebszustand, unter seinem Namen.
    assert {"AeroWIN", "BioWIN"} <= set(titel)
    assert [s["titel"] for s in hs.nebensysteme(anlage)] == ["AeroWIN", "BioWIN"]


def test_der_kessel_als_hauptsystem(hs, teile):
    anlage = {"teile": list(teile), "hauptsystem": "kessel"}
    zeilen = hs.status(anlage, [])
    assert zeilen[0] == {"abschnitt": "BioWIN"}
    assert [s["titel"] for s in hs.nebensysteme(anlage)] == ["Hybrid", "AeroWIN"]


@pytest.mark.parametrize(
    ("wahl", "reihe"),
    [
        ("auto", ["AeroWIN", "Hybrid", "BioWIN"]),
        ("waermepumpe", ["AeroWIN", "Hybrid", "BioWIN"]),
        ("kessel", ["BioWIN", "Hybrid", "AeroWIN"]),
    ],
)
def test_im_schaubild_steht_die_umschaltung_zwischen_den_erzeugern(hs, teile, wahl, reihe):
    biowin, aerowin, hybrid = teile
    anlage = {"teile": [biowin, hybrid, aerowin], "hauptsystem": wahl}
    assert [t["name"] for t in hs.teile_geordnet(anlage)] == reihe
