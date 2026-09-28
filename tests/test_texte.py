"""Die Wörterbücher der Oberfläche.

Der deutsche Text ist der Schlüssel. Ein Eintrag, der nicht mehr im Quelltext
steht, fällt niemandem auf; ein fehlender lässt die Stelle deutsch. Geprüft
wird deshalb beides gegen die Texte, die die Oberfläche wirklich setzt.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from .conftest import load_standalone

ORDNER = Path(__file__).parent.parent / "custom_components" / "heatnexus" / "sprachen"
PLATZHALTER = re.compile(r"\{(\w+)\}")


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


@pytest.mark.parametrize(
    ("deutsch", "englisch"),
    [
        ("Sonnentag – 21,0 °C bis 16:54.", "Sunny day – 21,0 °C until 16:54."),
        (
            "Heizt nach Programm – gedämpfte AT 16,8 °C, Raum 21,3 °C. Die Räume fordern Wärme an.",
            "Heating by program – damped outdoor temp. 16,8 °C, room 21,3 °C. The rooms call for heat.",
        ),
        (
            "Absenkung von Hand beendet. Pausiert bis 05:00.",
            "Setback ended by hand. Paused until 05:00.",
        ),
        ("Außen 3,0 °C – zurück ins Programm.", "Outdoor 3,0 °C – back to the program."),
        ("Räume −0,6 K – zurück ins Programm.", "Rooms −0,6 K – back to the program."),
        (
            "Estrich an der Steuerung – keine Eingriffe.",
            "Screed drying at the controller – no interventions.",
        ),
        (
            "Heizgrenzen der Steuerung: Heizbetrieb 18,0 °C, Absenkbetrieb 5,0 °C.",
            "Controller heating limits: Heating mode 18,0 °C, setback mode 5,0 °C.",
        ),
        ("Solaranlage liefert – 21,0 °C bis 16:54.", "Solaranlage delivers – 21,0 °C until 16:54."),
    ],
)
def test_saetze_mit_zahlen_kommen_uebersetzt(texte, deutsch, englisch):
    """Ein Satz mit Werten trifft sein Muster; die Werte bleiben, eingebettete Sätze werden mit übersetzt."""
    assert texte.Woerterbuch("en").satz(deutsch) == englisch


def test_unbekannter_satz_bleibt_deutsch(texte):
    """Ohne passendes Muster bleibt der Satz stehen, auf Deutsch sowieso."""
    assert texte.Woerterbuch("en").satz("Etwas ganz anderes 12 %.") == "Etwas ganz anderes 12 %."
    assert (
        texte.Woerterbuch("de").satz("Sonnentag – 21,0 °C bis 16:54.")
        == "Sonnentag – 21,0 °C bis 16:54."
    )


def test_jede_uebersetzung_traegt_die_platzhalter_ihres_schluessels():
    """Ein vergessener oder umbenannter Platzhalter ließe einen Wert verschwinden."""
    for datei in ORDNER.glob("*.json"):
        for deutsch, fremd in json.loads(datei.read_text(encoding="utf-8")).items():
            assert sorted(PLATZHALTER.findall(deutsch)) == sorted(PLATZHALTER.findall(fremd)), (
                datei.name,
                deutsch,
            )


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


class _Eintrag:
    """Ein Konfigurationseintrag, so weit die Sprachwahl ihn braucht."""

    def __init__(self, optionen):
        self.options = optionen


class _Hass:
    """Home Assistant, so weit die Sprachwahl es braucht."""

    def __init__(self, sprache, eintraege):
        self.config = type("Konfig", (), {"language": sprache})()
        self.config_entries = type(
            "Eintraege", (), {"async_entries": staticmethod(lambda _domain: eintraege)}
        )()


def test_ohne_eintrag_bleibt_es_deutsch(texte):
    """Ohne eingerichtete Anlage gibt es nichts zu übersetzen."""
    assert texte.sprache_der_oberflaeche(_Hass("en", [])) == "de"


def test_die_gewaehlte_sprache_sticht(texte):
    """Eine feste Wahl gilt, auch wenn Home Assistant anders steht."""
    hass = _Hass("en", [_Eintrag({"sprache": "de"})])
    assert texte.sprache_der_oberflaeche(hass) == "de"


def test_automatisch_folgt_home_assistant(texte):
    """Ohne Wahl gilt die Sprache von Home Assistant."""
    assert texte.sprache_der_oberflaeche(_Hass("en", [_Eintrag({"sprache": "auto"})])) == "en"
    assert texte.sprache_der_oberflaeche(_Hass("fr", [_Eintrag({})])) == "fr"


def test_regionalkennung_faellt_weg(texte):
    """„en-GB" ist Englisch; das Wörterbuch kennt nur den Sprachteil."""
    assert texte.sprache_der_oberflaeche(_Hass("en-GB", [_Eintrag({})])) == "en"
