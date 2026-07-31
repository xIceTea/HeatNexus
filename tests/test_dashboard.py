"""Aufbau des mitgelieferten Dashboards.

Geprüft werden die Bausteine, die die Reihenfolge und die Kartenwahl
bestimmen – ohne laufende Home-Assistant-Instanz.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def dashboard():
    from custom_components.heatnexus import dashboard as modul

    return modul


def test_kurzname_entfernt_steuerungspraefix(dashboard):
    assert dashboard._kurzname("Heizhaus · PuroWIN") == "PuroWIN"
    assert dashboard._kurzname("PuroWIN") == "PuroWIN"
    assert dashboard._kurzname(None) == ""


def test_kessel_steht_vor_puffer_und_heizkreis(dashboard):
    kessel = dashboard._rang(25)
    puffer = dashboard._rang(16)
    heizkreis = dashboard._rang(14)
    zirkulation = dashboard._rang(20)
    assert kessel < puffer < heizkreis < zirkulation


def test_unbekannter_funktionstyp_kommt_zuletzt(dashboard):
    assert dashboard._rang(None) == dashboard.RANG_UNBEKANNT
    assert dashboard._rang("keine Zahl") == dashboard.RANG_UNBEKANNT
    assert dashboard._rang(999) == dashboard.RANG_UNBEKANNT
    assert dashboard._rang(25) < dashboard._rang(999)


def test_betriebsphase_steht_vor_beliebigem_wert(dashboard):
    assert dashboard._vorrang("Betriebsphase") < dashboard._vorrang("Nachstellzeit")


def test_thermostat_bekommt_eigene_karte(dashboard):
    eintrag = {"entity_id": "climate.heizkreis", "name": "Heizkreis", "bereich": "climate"}
    assert dashboard._karte(eintrag)["type"] == "thermostat"


def test_kesseltemperatur_wird_rundinstrument(dashboard):
    eintrag = {
        "entity_id": "sensor.kesseltemperatur_ist",
        "name": "Kesseltemperatur Ist",
        "bereich": "sensor",
    }
    karte = dashboard._karte(eintrag, rundinstrument=True)
    assert karte["type"] == "gauge"
    # Ohne ausdrückliche Anforderung bleibt es eine schlichte Kachel.
    assert dashboard._karte(eintrag)["type"] == "tile"


def test_leerer_abschnitt_entfaellt(dashboard):
    assert dashboard._abschnitt("Messwerte", []) == []
    abschnitt = dashboard._abschnitt("Messwerte", [{"type": "tile"}])
    assert abschnitt[0]["cards"][0]["heading"] == "Messwerte"
