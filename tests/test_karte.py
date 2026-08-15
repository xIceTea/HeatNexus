"""Nutzdaten des Schaubilds – gemeinsame Grundlage von Oberfläche und Karte."""

from __future__ import annotations

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
        "entitaeten": [
            {
                "entity_id": eid,
                "name": n,
                "hat_wert": True,
                "bereich": eid.split(".")[0],
            }
            for eid, n in werte
        ],
    }


@pytest.fixture
def anlage():
    return {
        "id": "anlage-1",
        "name": "Heizhaus",
        "teile": [
            _teil(
                "PuroWIN",
                25,
                [
                    ("sensor.kessel_ist", "Kesseltemperatur Ist"),
                    ("sensor.leistung", "Kesselleistung"),
                ],
            ),
            _teil(
                "B-PLMi PUFFER",
                16,
                [
                    ("sensor.tpe", "Puffer oben Temperatur (TPE)"),
                    ("sensor.tpa", "Puffer unten Temperatur (TPA)"),
                ],
            ),
        ],
    }


FELDER = (
    "schema_svg",
    "schema_farben",
    "schema_werte",
    "schema_pumpen",
    "schema_leitungen",
    "schema_brenner",
    "schema_anforderung",
    "schema_mischer",
    "schema_heizkoerper",
    "schema_schichtung",
    "schema_lampen",
    "schema_speicher",
)


def test_nutzdaten_fuehren_alle_felder(schema, anlage):
    """Die Karte bekommt dieselben Felder wie die Oberfläche."""
    nutzdaten = schema.schaubild_nutzdaten(anlage)
    for feld in FELDER:
        assert feld in nutzdaten, feld


def test_die_zeichnung_geht_einmal_hinaus(schema, anlage):
    """Welcher Farbsatz gilt, weiß erst der Browser – er stellt selbst um."""
    nutzdaten = schema.schaubild_nutzdaten(anlage)
    assert nutzdaten["schema_svg"].startswith("<svg")
    assert set(nutzdaten["schema_farben"]) == {"hell", "terrakotta", "petrol", "pflaume"}


def test_werte_tragen_entitaet_und_lage(schema, anlage):
    """Ohne Lage kann die Karte die Beschriftung nicht setzen."""
    werte = schema.schaubild_nutzdaten(anlage)["schema_werte"]
    assert werte
    for eintrag in werte:
        assert eintrag["entity"]
        assert eintrag["left"].endswith("%")
        assert eintrag["top"].endswith("%")


def test_kartendaten_nennen_jede_anlage(schema, anlage):
    """Die Karte wählt ihre Anlage über die Kennung, nicht über die Reihenfolge."""
    zweite = {"id": "anlage-2", "name": "Wohnhaus", "teile": anlage["teile"]}
    daten = schema.schaubild_daten([anlage, zweite])
    assert [a["id"] for a in daten] == ["anlage-1", "anlage-2"]
    assert [a["name"] for a in daten] == ["Heizhaus", "Wohnhaus"]
    assert all(a["schema_svg"] for a in daten)


def test_kartendaten_ohne_anlage_bleiben_leer(schema):
    assert schema.schaubild_daten([]) == []


def test_anlage_ohne_messwert_bleibt_leer(schema):
    """Ein Bild aus leeren Kästen hilft niemandem."""
    leer = {"id": "anlage-2", "name": "Wohnhaus", "teile": [_teil("PuroWIN", 25, [])]}
    nutzdaten = schema.schaubild_nutzdaten(leer)
    assert nutzdaten["schema_svg"] is None
    assert nutzdaten["schema_werte"] == []
    assert nutzdaten["schema_leitungen"] is None
