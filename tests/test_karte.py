"""Nutzdaten des Schaubilds – gemeinsame Grundlage von Oberfläche und Karte."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from .conftest import load_standalone

KARTE_JS = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "heatnexus"
    / "frontend"
    / "heatnexus-schaubild-karte.js"
)
DURCHLAUF = Path(__file__).resolve().parent / "js" / "karte-durchlauf.mjs"


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


# ---------------------------------------------------------------------------
# Die Karte im Browser
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def durchlauf(schema, tmp_path_factory):
    """Die Karte einmal in Node aufbauen und die Bilanz zurückgeben."""
    if shutil.which("node") is None:
        pytest.skip("node nicht vorhanden")
    teile = [
        _teil(
            "PuroWIN",
            25,
            [("sensor.kessel", "Kesseltemperatur Ist"), ("sensor.leistung", "Kesselleistung")],
        ),
        _teil(
            "B-PLMi PUFFER",
            16,
            [
                ("sensor.tpe", "Puffer oben Temperatur (TPE)"),
                ("sensor.tpa", "Puffer unten Temperatur (TPA)"),
                ("switch.pufferladepumpe", "Pufferladepumpe"),
            ],
        ),
        _teil(
            "UML Heizkreis",
            14,
            [
                ("sensor.vorlauf", "Vorlauftemperatur Ist"),
                ("switch.heizkreispumpe", "Heizkreispumpe"),
                ("sensor.mischer", "Mischer Stellwert"),
            ],
        ),
    ]
    anlagen = schema.schaubild_daten(
        [
            {"id": "anlage-1", "name": "Heizhaus", "teile": teile},
            {"id": "anlage-2", "name": "Wohnhaus", "teile": teile},
        ]
    )
    daten = tmp_path_factory.mktemp("karte") / "anlagen.json"
    daten.write_text(json.dumps(anlagen), encoding="utf-8")
    ausgabe = subprocess.run(
        ["node", str(DURCHLAUF), KARTE_JS.as_uri(), str(daten)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert ausgabe.returncode == 0, ausgabe.stderr
    return json.loads(ausgabe.stdout)


def test_die_karte_meldet_sich_beim_laden_an(durchlauf):
    """Home Assistant wartet nicht: Das Element muss sofort dastehen."""
    assert durchlauf["sofortRegistriert"] is True
    assert durchlauf["inKartenauswahl"] is True


def test_die_karte_bringt_eine_erstkonfiguration_mit(durchlauf):
    assert durchlauf["stubHatTyp"] is True


def test_der_editor_stellt_die_anlagen_zur_auswahl(durchlauf):
    """Ein Textfeld zwang zum Abtippen und meldete bei jedem Buchstaben Unsinn."""
    assert durchlauf["editorElement"] == "heatnexus-schaubild-editor"
    assert durchlauf["editorFelder"] == ["anlage", "farbsatz", "animation"]
    assert durchlauf["editorAnlagen"] == ["Heizhaus", "Wohnhaus"]


def test_groesse_kommt_ohne_hass_aus(durchlauf):
    """`getCardSize` und `getGridOptions` laufen vor dem ersten `hass`."""
    assert durchlauf["groesseOhneHass"] > 0
    assert durchlauf["rasterOhneHass"]["columns"] == 12


def test_die_karte_zeigt_das_schaubild(durchlauf):
    assert durchlauf["bildVorhanden"] is True
    assert durchlauf["bildAdresse"].startswith("data:image/svg+xml")


def test_die_gewaehlte_anlage_gilt(durchlauf):
    assert durchlauf["zweiteAnlageAnders"] is True


def test_ein_unbekannter_farbsatz_wird_abgewiesen(durchlauf):
    """Erst der Fehler lässt Home Assistant auf den YAML-Editor zurückfallen."""
    assert durchlauf["unbekannterSatzWirft"] is True


def test_ohne_anlage_steht_ein_hinweis(durchlauf):
    assert durchlauf["hinweisOhneAnlage"] is True


def test_die_bewegung_laesst_sich_abschalten(durchlauf):
    """Wer es ruhig will, behält trotzdem alle Zustände."""
    assert durchlauf["ohneAnimationRuhig"] is True
    assert durchlauf["mitAnimationBewegt"] is True


def test_die_stichleitungen_kehren_beim_entnehmen_um(durchlauf):
    """Beim Entladen verlässt die Wärme den Speicher oben, nicht andersherum."""
    assert durchlauf["senkrechteVorhanden"] > 0
    assert durchlauf["beimEntnehmenRueckwaerts"] is True
    assert durchlauf["beimLadenVorwaerts"] is True


def test_die_ueberlagerungen_folgen_dem_farbsatz(durchlauf):
    """Mischer, Heizkörper und Schichtung liegen über dem Bild, nicht darin."""
    assert durchlauf["grundfarbenMitgeliefert"] == 4
    assert durchlauf["stutzenVorhanden"] is True
    assert durchlauf["stutzenOhneDunkelwert"] is True
