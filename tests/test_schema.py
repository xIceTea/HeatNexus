"""Anlagenschaubild: Aufbau der Grafik und Lage der Beschriftungen."""

from __future__ import annotations

import base64

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def schema():
    """Das Modul kommt ohne Home Assistant aus und wird direkt geladen."""
    return load_standalone("schema")


def _teil(name: str, fct: int, werte: list[tuple[str, str]]) -> dict:
    return {
        "name": name,
        "fct_type": fct,
        "entitaeten": [{"entity_id": eid, "name": n, "hat_wert": True} for eid, n in werte],
    }


@pytest.fixture
def anlage():
    return [
        _teil(
            "PuroWIN",
            25,
            [("sensor.kessel_ist", "Kesseltemperatur Ist"), ("sensor.leistung", "Kesselleistung")],
        ),
        _teil(
            "B-PLMi PUFFER",
            16,
            [
                ("sensor.tpe", "Puffer oben Temperatur (TPE)"),
                ("sensor.tpa", "Puffer unten Temperatur (TPA)"),
            ],
        ),
    ]


def test_karte_ist_ein_bild_mit_beschriftungen(schema, anlage):
    karte = schema.anlagenschema(anlage)
    assert karte["type"] == "picture-elements"
    assert karte["image"].startswith("data:image/svg+xml;base64,")
    # Je Anlagenteil zwei Werte.
    assert len(karte["elements"]) == 4
    assert {e["entity"] for e in karte["elements"]} == {
        "sensor.kessel_ist",
        "sensor.leistung",
        "sensor.tpe",
        "sensor.tpa",
    }


def test_bild_enthaelt_die_namen(schema, anlage):
    karte = schema.anlagenschema(anlage)
    svg = base64.b64decode(karte["image"].split(",", 1)[1]).decode("utf-8")
    assert svg.startswith("<svg")
    assert "PuroWIN" in svg
    assert "B-PLMi PUFFER" in svg
    assert "</svg>" in svg


def test_beschriftungen_liegen_im_bild(schema, anlage):
    for element in schema.anlagenschema(anlage)["elements"]:
        for achse in ("top", "left"):
            anteil = float(element["style"][achse].rstrip("%"))
            assert 0 < anteil < 100


def test_ohne_messwerte_kein_schaubild(schema):
    assert schema.anlagenschema([]) is None
    ohne = [_teil("ZSP-PTS", 20, [("sensor.x", "Pumpendrehzahl")])]
    assert schema.anlagenschema(ohne) is None


def test_spitze_klammern_im_namen_zerlegen_das_bild_nicht(schema):
    teil = _teil("Kessel <b>", 25, [("sensor.k", "Kesseltemperatur Ist")])
    svg = base64.b64decode(schema.anlagenschema([teil])["image"].split(",", 1)[1]).decode("utf-8")
    assert "<b>" not in svg
    assert "&lt;b&gt;" in svg


def test_schaubild_entsteht_auch_ohne_werte(schema, anlage):
    """Beim ersten Aufbau ist die Anlage noch nicht eingelesen.

    Verlangte das Schaubild einen vorhandenen Wert, bliebe der Reiter „Anlage"
    dauerhaft leer – der Fehler aus 1.0.0.
    """
    for teil in anlage:
        for eintrag in teil["entitaeten"]:
            eintrag["hat_wert"] = False

    bild = schema.anlagenschema(anlage)
    assert bild is not None
    assert len(bild["elements"]) == 4


def test_anlagenteil_ohne_passenden_messwert_faellt_weg(schema):
    """Ein leerer Kasten hilft niemandem."""
    ohne = [{"name": "Rätsel", "fct_type": 99, "entitaeten": []}]
    assert schema.anlagenschema(ohne) is None
