"""Die Wörterbücher der Oberfläche.

Der deutsche Text ist der Schlüssel. Ein Eintrag, der nicht mehr im Quelltext
steht, fällt niemandem auf; ein fehlender lässt die Stelle deutsch. Geprüft
wird deshalb beides gegen die Texte, die die Oberfläche wirklich setzt.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import load_standalone

ORDNER = Path(__file__).parent.parent / "custom_components" / "heatnexus" / "sprachen"


@pytest.fixture(scope="module")
def texte():
    """Das Modul kommt ohne Home Assistant aus."""
    return load_standalone("texte")


def test_jede_sprache_ist_eine_flache_zuordnung():
    """Ein verschachtelter Eintrag würde stumm nie greifen."""
    for datei in ORDNER.glob("*.json"):
        inhalt = json.loads(datei.read_text(encoding="utf-8"))
        assert all(isinstance(v, str) and v for v in inhalt.values()), datei.name


def test_deutsch_bleibt_ohne_woerterbuch(texte):
    """Die Quellsprache schlägt nichts nach."""
    assert texte.Woerterbuch("de")("Übersicht") == "Übersicht"
    assert texte.Woerterbuch("de").fuer_frontend == {}


def test_englisch_uebersetzt(texte):
    """Ein bekannter Text kommt englisch zurück, ein unbekannter unverändert."""
    englisch = texte.Woerterbuch("en")
    assert englisch("Übersicht") == "Overview"
    assert englisch("Nebengelass") == "Nebengelass"


def test_unbekannte_sprache_faellt_auf_englisch(texte):
    """Wer fremd wählt, versteht die deutsche Quelle meist nicht."""
    assert texte.Woerterbuch("it")("Übersicht") == "Overview"


def test_nur_bekannte_felder_werden_uebersetzt(texte):
    """Ein selbst vergebener Name steht in denselben Feldern und darf nicht wandern."""
    baum = {"titel": "Übersicht", "entity": "sensor.uebersicht", "kinder": [{"titel": "Wartung"}]}
    ergebnis = texte.uebersetze_baum(baum, texte.Woerterbuch("en"))
    assert ergebnis["titel"] == "Overview"
    assert ergebnis["entity"] == "sensor.uebersicht"
    assert ergebnis["kinder"][0]["titel"] == "Maintenance"


def test_jede_kachelbeschriftung_ist_uebersetzt(texte):
    """Ein neuer Text ohne Eintrag bliebe in jeder Sprache deutsch."""
    muster = load_standalone("panel.muster")
    beschriftungen = {
        zeile[1]
        for name in dir(muster)
        if not name.startswith("_") and isinstance(tabelle := getattr(muster, name), tuple)
        for zeile in tabelle
        if isinstance(zeile, tuple) and len(zeile) >= 2 and isinstance(zeile[1], str)
    }
    # Diese Begriffe lauten auf Englisch gleich und brauchen keinen Eintrag.
    GLEICH = {"HeatNexus", "Eco", "Comfort", "Auto", "Name"}
    englisch = texte.Woerterbuch("en")
    fehlen = sorted(b for b in beschriftungen - GLEICH if englisch(b) == b)
    assert not fehlen, f"ohne englische Fassung: {fehlen}"
