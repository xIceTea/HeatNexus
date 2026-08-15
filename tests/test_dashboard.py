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
    assert dashboard._vorrang({"name": "Betriebsphase"}) < dashboard._vorrang(
        {"name": "Nachstellzeit"}
    )


def test_der_vorrang_gilt_auch_ohne_deutschen_namen(dashboard):
    """Sonst rutschte die Betriebsphase in einer fremden Sprache ans Ende."""
    fremd = {"name": "Operating phase", "schluessel": "operating_phase"}
    assert dashboard._vorrang(fremd) < dashboard._vorrang({"name": "Nachstellzeit"})


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


def test_skala_rundet_auf_hunderter(dashboard):
    assert dashboard._skala(None) == 100
    assert dashboard._skala(0) == 100
    assert dashboard._skala(37) == 100
    assert dashboard._skala(101) == 200
    assert dashboard._skala(1180) == 1200


def test_gleichnamige_anlagenteile_werden_erkannt(dashboard):
    anlagen = [
        {"name": "Heizhaus", "teile": [{"name": "B-PLMi PUFFER"}, {"name": "PuroWIN"}]},
        {"name": "Wohnhaus", "teile": [{"name": "B-PLMi PUFFER"}]},
    ]
    assert dashboard._mehrfach_vergebene_namen(anlagen) == {"B-PLMi PUFFER"}


def test_anlage_steht_vor_dem_anlagenteil(dashboard):
    anlage = {"name": "Heizhaus"}
    assert dashboard._voller_name(anlage, {"name": "PuroWIN"}) == "Heizhaus · PuroWIN"
    assert dashboard._voller_name({"name": ""}, {"name": "PuroWIN"}) == "PuroWIN"


def test_symbol_je_anlagenteil(dashboard):
    assert dashboard._symbol(25) == "mdi:fire"
    assert dashboard._symbol(16) == "mdi:storage-tank"
    assert dashboard._symbol(None) == dashboard.SYMBOL_UNBEKANNT


# ---------------------------------------------------------------------------
# Rückfragen vor Eingriffen
# ---------------------------------------------------------------------------
def test_rueckfrage_nur_bei_eingriffen(dashboard):
    assert dashboard.rueckfrage("Serviceausbrand")
    assert dashboard.rueckfrage("Reinigung bestätigt")
    assert dashboard.rueckfrage("Gewählter Brennstoff")
    # Harmlose Werte bleiben ohne Nachfrage – sonst klickt man sie blind weg.
    assert dashboard.rueckfrage("WW Einmalladung") == ""
    assert dashboard.rueckfrage("Kesseltemperatur Ist") == ""


def test_gefaehrliche_taste_bekommt_bestaetigung(dashboard):
    eintrag = {
        "entity_id": "button.serviceausbrand",
        "name": "Serviceausbrand",
        "bereich": "button",
    }
    karte = dashboard._karte(eintrag)
    aktion = karte["icon_tap_action"]
    assert aktion["perform_action"] == "button.press"
    assert aktion["confirmation"]["text"]
    # Das Tippen auf die Kachel selbst bleibt die Detailansicht.
    assert "tap_action" not in karte


def test_schalter_wird_umgeschaltet_statt_ausgeloest(dashboard):
    eintrag = {"entity_id": "switch.estrich", "name": "Estrichprogramm", "bereich": "switch"}
    assert dashboard._karte(eintrag)["icon_tap_action"]["action"] == "toggle"


def test_harmlose_kachel_bleibt_unveraendert(dashboard):
    eintrag = {
        "entity_id": "sensor.kesseltemperatur_ist",
        "name": "Kesseltemperatur Ist",
        "bereich": "sensor",
    }
    assert "icon_tap_action" not in dashboard._karte(eintrag)


def test_ohne_schaltbare_plattform_keine_bestaetigung(dashboard):
    """Ein Anzeigewert mit brenzligem Namen bekommt keine Schaltaktion."""
    eintrag = {
        "entity_id": "sensor.serviceausbrand_zaehler",
        "name": "Serviceausbrand Zähler",
        "bereich": "sensor",
    }
    assert "icon_tap_action" not in dashboard._karte(eintrag)


# ---------------------------------------------------------------------------
# Export: das erzeugte Dashboard zum Selberbauen
# ---------------------------------------------------------------------------
def test_der_export_ist_gueltiges_yaml():
    """Der Text muss sich unverändert wieder einlesen lassen."""
    import yaml

    from custom_components.heatnexus.dashboard import als_yaml

    konfiguration = {
        "title": "Heizung",
        "views": [
            {"title": "Übersicht", "path": "uebersicht", "cards": [{"type": "tile"}]},
        ],
    }
    text = als_yaml(konfiguration)
    assert yaml.safe_load(text) == konfiguration


def test_der_export_behaelt_die_reihenfolge():
    """Alphabetisch sortiert stünde `views` vor `title` – schlecht zu lesen."""
    from custom_components.heatnexus.dashboard import als_yaml

    text = als_yaml({"title": "Heizung", "views": []})
    assert text.index("title:") < text.index("views:")


def test_der_export_schreibt_umlaute_aus():
    """Entwichene Zeichen wären im Rohkonfigurations-Editor unlesbar."""
    from custom_components.heatnexus.dashboard import als_yaml

    assert "Übersicht" in als_yaml({"title": "Übersicht"})
