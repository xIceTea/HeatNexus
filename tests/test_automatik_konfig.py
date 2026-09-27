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
