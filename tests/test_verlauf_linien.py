"""Die Linienwahl der Verlaufskarte: Chips, Suche, Standard, gemerkt über das Neuladen.

Gefahren wird in Node gegen die DOM-Attrappe (`js/verlauf-linien.mjs`); jedes
neue Element steht dort für eine frisch geladene Seite.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")

WURZEL = Path(__file__).resolve().parents[1]
PANEL_JS = WURZEL / "custom_components" / "heatnexus" / "frontend" / "heatnexus-panel.js"
LINIEN = Path(__file__).parent / "js" / "verlauf-linien.mjs"

SPEICHER = "heatnexus.verlauf_linien"
VORAUSWAHL = ["sensor.kessel", "sensor.puffer_oben"]


@pytest.fixture(scope="module")
def linien() -> dict:
    lauf = subprocess.run(
        ["node", str(LINIEN), str(PANEL_JS)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr or lauf.stdout
    return json.loads(lauf.stdout)


def test_ohne_gemerkte_wahl_gilt_die_vorauswahl(linien):
    assert linien["ohneWahl"] == {
        "linien": VORAUSWAHL,
        "chips": VORAUSWAHL,
        "standardVersteckt": True,
    }


def test_die_suche_trifft_titel_und_kennung_ohne_gewaehltes(linien):
    assert linien["suche"] == {
        "puffer": ["sensor.puffer_mitte"],
        "kennung": ["sensor.aussen"],
        "nichts": ["leer"],
    }


def test_escape_schliesst_die_vorschlaege(linien):
    assert linien["escape"] == {"vorher": True, "nachher": True}


def test_pfeil_und_enter_fuegen_den_markierten_vorschlag_hinzu(linien):
    enter = linien["enter"]
    assert enter["treffer"] == ["sensor.puffer_mitte", "sensor.aussen"]
    assert enter["chips"] == enter["linien"] == [*VORAUSWAHL, "sensor.aussen"]
    assert enter["feldLeer"] and enter["listeZu"]
    assert enter["standardVersteckt"] is False
    assert enter["geschrieben"] == {
        "key": SPEICHER,
        "value": {"Anlage A|48": [*VORAUSWAHL, "sensor.aussen"]},
    }


def test_das_kreuz_entfernt_eine_linie(linien):
    gewaehlt = ["sensor.puffer_oben", "sensor.aussen"]
    assert linien["entfernt"] == {
        "chips": gewaehlt,
        "geschrieben": {"key": SPEICHER, "value": {"Anlage A|48": gewaehlt}},
    }


def test_standard_stellt_die_vorauswahl_her_und_vergisst_die_wahl(linien):
    assert linien["standard"] == {
        "chips": VORAUSWAHL,
        "versteckt": True,
        "geschrieben": {"key": SPEICHER, "value": {}},
    }


def test_die_gemerkte_wahl_kommt_ohne_verschwundene_entitaeten_zurueck(linien):
    assert linien["gemerkt"] == ["sensor.kessel", "sensor.puffer_mitte"]


def test_die_wahl_gilt_nur_fuer_ihren_zeitraum(linien):
    assert linien["andererZeitraum"] == VORAUSWAHL


def test_ohne_verbliebene_linie_gilt_wieder_die_vorauswahl(linien):
    assert linien["verwaist"] == VORAUSWAHL


def test_eine_leere_wahl_bleibt_leer(linien):
    assert linien["abgewaehlt"] == {"linien": [], "hinweis": True}


def test_ohne_nutzerdaten_haelt_der_browser_die_wahl(linien):
    assert linien["imBrowser"] == {"Anlage A|48": ["sensor.puffer_mitte"]}
    assert linien["ausBrowser"] == ["sensor.puffer_mitte"]
