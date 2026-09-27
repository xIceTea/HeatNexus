"""Einstellungen der Automatik: was gespeichert wird und was abgewiesen."""

from __future__ import annotations

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def konfig():
    load_standalone("automatik")
    load_standalone("automatik.profile")
    return load_standalone("automatik.konfig")


def roh(**felder):
    basis = {
        "heizkreis": "SN1-2-0",
        "heizflaechen": "heizkoerper",
        "raeume": ["sensor.wohnzimmer_temperatur"],
        "wetter": "weather.forecast_home",
    }
    basis.update(felder)
    return basis


def test_vollstaendige_einstellung_wird_ergaenzt(konfig):
    k = konfig.pruefen(roh())
    assert k["profil"] == "schnell"
    assert k["modus"] == "beobachten"
    assert k["aktiv"] is True
    assert k["raum_art"] == "mittel"
    assert k["personen"] == []
    assert k["pv"] is None
    assert k["eigene"] == {}


@pytest.mark.parametrize(
    "fehlt", [{"heizkreis": ""}, {"raeume": []}, {"raeume": ["kein id"]}, {"wetter": None}]
)
def test_unvollstaendiges_wird_abgewiesen(konfig, fehlt):
    assert konfig.pruefen(roh(**fehlt)) is None


def test_listen_ohne_doppelte_und_ungueltige(konfig):
    k = konfig.pruefen(
        roh(
            raeume=["sensor.a", "sensor.a", "Sensor.B", "sensor.c"],
            personen=["person.x", 3],
            fenster=["binary_sensor.fenster"] * 3,
        )
    )
    assert k["raeume"] == ["sensor.a", "sensor.c"]
    assert k["personen"] == ["person.x"]
    assert k["fenster"] == ["binary_sensor.fenster"]


def test_zu_viele_raeume_werden_gekappt(konfig):
    k = konfig.pruefen(roh(raeume=[f"sensor.r{i}" for i in range(15)]))
    assert len(k["raeume"]) == konfig.LISTEN_MAX["raeume"]


def test_eigene_werte_nur_als_abweichung(konfig):
    k = konfig.pruefen(roh(profil="standard", eigene={"absenkung_k": 2.0, "hysterese": 1.0}))
    assert k["eigene"] == {"absenkung_k": 2.0}


def test_unbekannter_modus_und_profil_fallen_zurueck(konfig):
    k = konfig.pruefen(roh(modus="turbo", profil="x", heizflaechen="flaeche"))
    assert k["modus"] == "beobachten"
    assert k["profil"] == "traege"


@pytest.mark.parametrize(
    ("entity_id", "passt"),
    [
        ("sensor.wohnzimmer_wohnzimmer_temperatur", True),
        ("sensor.kuche_temperatur", True),
        ("sensor.wohnzimmer_wohnzimmer_taupunkt", False),
        ("sensor.wohnzimmer_wohnzimmer_ziel", False),
        ("sensor.bad_bad_oberflachentemperatur", False),
        ("sensor.shellyplus1pm_d4d4_switch_0_device_temperature", False),
        ("sensor.fritz_box_6890_lte_cpu_temperatur", False),
        ("sensor.heizkreis_raumtemperatur_soll", False),
    ],
)
def test_nur_raumtemperaturen_stehen_zur_wahl(konfig, entity_id, passt):
    assert konfig.raumfuehler_passt(entity_id) is passt


@pytest.mark.parametrize(
    ("entity_id", "passt"),
    [
        ("sensor.energy_production_today", True),
        ("sensor.energy_production_today_remaining", False),
        ("sensor.energy_production_tomorrow", False),
        ("sensor.energy_current_hour", False),
        ("sensor.energy_next_hour", False),
    ],
)
def test_nur_die_tagesprognose_steht_als_pv_zur_wahl(konfig, entity_id, passt):
    assert konfig.pv_passt(entity_id) is passt


def test_pv_ist_und_lernfenster_werden_gespeichert(konfig):
    k = konfig.pruefen(roh(pv_ist="sensor.hoymiles_today_eq", eigene={"lernfenster": 7}))
    assert k["pv_ist"] == "sensor.hoymiles_today_eq"
    assert k["eigene"] == {"lernfenster": 7}


@pytest.mark.parametrize(
    ("entity_id", "passt"),
    [
        ("sensor.hoymiles_ms_a2_solarh_9201610_today_eq", True),
        ("sensor.wechselrichter_ertrag_heute", True),
        ("sensor.pv_tagesertrag_gesamt", True),
        ("sensor.shellypro3em_total_energy", False),
        ("sensor.waschmaschine_energie", False),
    ],
)
def test_pv_ist_nur_nach_pv_aussehende_zaehler(konfig, entity_id, passt):
    assert konfig.pv_ist_passt(entity_id) is passt
