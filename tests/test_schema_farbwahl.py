"""Farbsatz und Helligkeit als zwei Wahlen: Übersetzung alter Werte, Fassungen, Palette je Kombination."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

KOMPONENTE = Path(__file__).parents[1] / "custom_components" / "heatnexus"
ORDNUNG_JS = KOMPONENTE / "frontend" / "ordnung.js"

# Alte Werte bis 1.15 und was aus ihnen wird.
ALTE_WERTE = {
    "auto": ("home_assistant", "auto"),
    "dunkel": ("heatnexus", "dunkel"),
    "hell": ("heatnexus", "hell"),
    "terrakotta": ("terrakotta", "dunkel"),
    "petrol": ("petrol", "dunkel"),
    "pflaume": ("pflaume", "dunkel"),
    "windhager": ("windhager", "hell"),
    "windhager_dunkel": ("windhager", "dunkel"),
}


@pytest.fixture(scope="module")
def farben():
    pfad = KOMPONENTE / "schema" / "farben.py"
    spec = importlib.util.spec_from_file_location("hn_farben_farbwahl", pfad)
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


def _im_browser(tmp_path, rumpf: str):
    skript = tmp_path / "farbwahl.mjs"
    skript.write_text(
        f'import * as o from "{ORDNUNG_JS.resolve().as_uri()}";\n{rumpf}\n', encoding="utf-8"
    )
    ausgabe = subprocess.run(
        ["node", str(skript)], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return json.loads(ausgabe.stdout)


def test_der_server_uebersetzt_jeden_alten_wert(farben):
    for alt, (satz, helligkeit) in ALTE_WERTE.items():
        neu = farben.farbwahl_uebersetzen({"farbsatz": alt, "kopf": "farbig"})
        assert neu == {"farbsatz": satz, "helligkeit": helligkeit, "kopf": "farbig"}, alt


def test_eine_gesetzte_helligkeit_bleibt_stehen(farben):
    """Wer beides gespeichert hat, wählte im neuen Fenster; dort gibt es nichts zu übersetzen."""
    einstellungen = {"farbsatz": "terrakotta", "helligkeit": "auto"}
    assert farben.farbwahl_uebersetzen(einstellungen) == einstellungen
    assert farben.farbwahl_uebersetzen({"kopf": "farbig"}) == {"kopf": "farbig"}


def test_jeder_satz_nennt_seine_fassungen(farben):
    assert farben.FARBSAETZE[0] == "home_assistant"
    assert set(farben.FASSUNGEN) == set(farben.FARBSAETZE) - {"home_assistant"}
    for satz, fassungen in farben.FASSUNGEN.items():
        assert fassungen and set(fassungen) <= {"hell", "dunkel"}, satz


def test_jeder_satz_gibt_es_hell_und_dunkel(farben):
    for satz, fassungen in farben.FASSUNGEN.items():
        assert fassungen == ("hell", "dunkel"), satz


def test_jede_fassung_hat_ihre_schaubildtabelle(farben):
    """Nur die Grundzeichnung, HeatNexus dunkel, braucht keine."""
    erwartet = {
        f"{satz}_{fassung}" for satz, fassungen in farben.FASSUNGEN.items() for fassung in fassungen
    } - {"heatnexus_dunkel"}
    assert set(farben.FARBABBILDUNGEN) == erwartet


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")
def test_oberflaeche_und_server_kennen_dieselben_saetze(farben, tmp_path):
    im_browser = _im_browser(
        tmp_path,
        "console.log(JSON.stringify({saetze: o.FARBSAETZE.map((s) => [s.schluessel, s.fassungen]),"
        " helligkeiten: o.HELLIGKEITEN.map((h) => h.schluessel)}));",
    )
    assert [satz for satz, _ in im_browser["saetze"]] == list(farben.FARBSAETZE)
    for satz, fassungen in im_browser["saetze"]:
        assert fassungen == list(farben.FASSUNGEN.get(satz, ())), satz
    assert im_browser["helligkeiten"] == list(farben.HELLIGKEITEN)


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")
def test_der_browser_uebersetzt_jeden_alten_wert(tmp_path):
    alt = list(ALTE_WERTE)
    ergebnis = _im_browser(
        tmp_path,
        f"console.log(JSON.stringify({json.dumps(alt)}.map((w) => o.farbwahl(w, ''))));",
    )
    assert [(e["farbsatz"], e["helligkeit"]) for e in ergebnis] == list(ALTE_WERTE.values())


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")
def test_unbekanntes_faellt_auf_den_standard(tmp_path):
    ergebnis = _im_browser(
        tmp_path,
        "console.log(JSON.stringify([o.farbwahl('gibtsnicht', 'grell'), o.farbwahl('', '')]));",
    )
    assert ergebnis == [{"farbsatz": "home_assistant", "helligkeit": "auto"}] * 2


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")
def test_satz_und_helligkeit_ergeben_die_palette(tmp_path):
    """„Automatisch“ folgt Home Assistant; die gewählte Fassung gilt, wo der Satz sie hat."""
    faelle = [
        ["heatnexus", "auto", True],
        ["heatnexus", "auto", False],
        ["heatnexus", "hell", True],
        ["windhager", "dunkel", False],
        ["terrakotta", "hell", False],
        ["home_assistant", "hell", False],
    ]
    ergebnis = _im_browser(
        tmp_path,
        f"console.log(JSON.stringify({json.dumps(faelle)}.map(([s, h, d]) =>"
        " [o.paletteSchluessel(s, h, d), o.schaubildSchluessel(s, h, d)])));",
    )
    assert ergebnis == [
        ["heatnexus_dunkel", "heatnexus_dunkel"],
        ["heatnexus_hell", "heatnexus_hell"],
        ["heatnexus_hell", "heatnexus_hell"],
        ["windhager_dunkel", "windhager_dunkel"],
        ["terrakotta_hell", "terrakotta_hell"],
        [None, "heatnexus_hell"],
    ]


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")
def test_jede_fassung_hat_eine_palette(farben, tmp_path):
    paletten = _im_browser(tmp_path, "console.log(JSON.stringify(o.PALETTEN));")
    erwartet = {
        f"{satz}_{fassung}" for satz, fassungen in farben.FASSUNGEN.items() for fassung in fassungen
    }
    assert set(paletten) == erwartet
