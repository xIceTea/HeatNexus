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


def test_empfehlen_ist_ein_gueltiger_modus(konfig):
    assert konfig.MODI == ("beobachten", "empfehlen", "schalten")
    assert konfig.pruefen(roh(modus="empfehlen"))["modus"] == "empfehlen"


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
        ("sensor.bienendach_yieldday", True),
        ("sensor.opendtu_1410f4_yield_day", True),
        ("sensor.marstek_venus_system_daily_solar_energy", True),
        ("sensor.shellypro3em_total_energy", False),
        ("sensor.waschmaschine_energie", False),
        ("sensor.hoymiles_ms_a2_solarh_9201610_month_eq", False),
        ("sensor.hoymiles_ms_a2_solarh_9201610_total_eq", False),
        ("sensor.hoymiles_ms_a2_solarh_9201610_meter_from_grid", False),
        ("sensor.hoymiles_ms_a2_solarh_9201610_bms_charging", False),
        ("sensor.bienendach_yieldtotal", False),
        ("sensor.pv_ertrag_total", False),
    ],
)
def test_pv_ist_nur_nach_pv_aussehende_zaehler(konfig, entity_id, passt):
    assert konfig.pv_ist_passt(entity_id) is passt


def test_ein_restwert_als_pv_prognose_wird_verworfen(konfig):
    """Der Restwert schrumpft im Lauf des Tages; Quote und Lernfaktor wären falsch."""
    k = konfig.pruefen(roh(pv="sensor.energy_production_today_remaining"))
    assert k["pv"] is None
    assert konfig.pruefen(roh(pv="sensor.energy_production_today"))["pv"] == (
        "sensor.energy_production_today"
    )


def test_thermostat_zaehlt_als_raum(konfig):
    k = konfig.pruefen(roh(raeume=["climate.bad", "sensor.kueche_temperatur"]))
    assert k["raeume"] == ["climate.bad", "sensor.kueche_temperatur"]


@pytest.mark.parametrize(
    ("eingabe", "erwartet"), [(20.5, 20.5), ("21", 21.0), (40, None), ("x", None), (None, None)]
)
def test_wunschtemperatur_nur_im_zulaessigen_bereich(konfig, eingabe, erwartet):
    assert konfig.pruefen(roh(raum_ziel=eingabe))["raum_ziel"] == erwartet


def test_sonnentag_laesst_sich_abschalten(konfig):
    k = konfig.pruefen(roh(eigene={"sonnentag": False}))
    assert k["eigene"] == {"sonnentag": False}


def test_erstes_thermostat_schaltet_den_sonnentag_ab(konfig):
    k = konfig.pruefen(roh(raeume=["climate.bad"]))
    assert konfig.klima_vorgabe(k, [])["eigene"] == {"sonnentag": False}


def test_vorhandene_thermostate_lassen_den_sonnentag_in_ruhe(konfig):
    k = konfig.pruefen(roh(raeume=["climate.bad", "climate.kueche"]))
    assert konfig.klima_vorgabe(k, ["climate.bad"])["eigene"] == {}


def test_ohne_thermostat_bleibt_der_sonnentag_an(konfig):
    k = konfig.pruefen(roh())
    assert konfig.klima_vorgabe(k, [])["eigene"] == {}


def test_vorrangquellen_sind_eine_begrenzte_liste(konfig):
    quellen = [f"binary_sensor.quelle_{i}" for i in range(8)]
    k = konfig.pruefen(roh(vorrang=[*quellen, "kein id"]))
    assert k["vorrang"] == quellen[: konfig.LISTEN_MAX["vorrang"]]
    assert konfig.pruefen(roh())["vorrang"] == []
