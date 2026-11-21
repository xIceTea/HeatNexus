"""Die Editoren bieten nur Werte im Raster der Anlage an: 15 min, 0,5 und den Bereich des Programms."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

TESTS = Path(__file__).resolve().parent
FRONTEND = TESTS.parent / "custom_components" / "heatnexus" / "frontend"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")


@pytest.fixture(scope="module")
def editor(tmp_path_factory) -> dict:
    skript = tmp_path_factory.mktemp("raster") / "raster.mjs"
    skript.write_text(
        f"""
import {{ browserAttrappe }} from "{(TESTS / "js" / "dom-attrappe.mjs").as_uri()}";
browserAttrappe();
const zp = await import("{(FRONTEND / "zeitprogramm.js").as_uri()}");
const {{ zeileneditorKnoten }} = await import("{(FRONTEND / "zeileneditor.js").as_uri()}");

const grenzen = {{ ...zp.skala([], "raum"), bereich: zp.wertebereich({{ bereich: [5, 30] }}) }};
const felder = (knoten) => {{
  const alle = [];
  const gehen = (k) => {{ if (k.tagName === "INPUT") alle.push(k); (k.children || []).forEach(gehen); }};
  gehen(knoten);
  return alle;
}};
const aendern = (feld, wert) => {{ feld.value = wert; feld.ausloesen("change"); return feld.value; }};

const modell = {{ tage: ["Mo"], punkte: [{{ zeit: 360, wert: 21 }}] }};
const zeile = zeileneditorKnoten(modell, {{ grenzen, speichern: () => [], abbrechen: () => {{}} }});
const [zeit, wert] = felder(zeile);
const zeile_felder = {{ zeit_schritt: zeit.step, wert_schritt: wert.step, min: wert.min, max: wert.max }};
const zeile_zeit = [aendern(zeit, "06:07"), aendern(zeit, "23:58")];
const zeile_wert = [aendern(wert, "21.3"), aendern(wert, "35"), aendern(wert, "2")];

const dialog = zp.editorKnoten([{{ tage: ["Mo"], punkte: [{{ zeit: 360, wert: 21 }}] }}], {{ grenzen }});
const [dzeit, dwert] = felder(dialog.knoten);
const dialog_felder = {{ zeit_schritt: dzeit.step, min: dwert.min, max: dwert.max }};
aendern(dzeit, "08:08");
aendern(dwert, "19.8");

console.log(JSON.stringify({{
  zeile_felder, zeile_zeit, zeile_wert, modell: modell.punkte,
  dialog_felder, dialog: dialog.lesen()[0].punkte,
  ohne_bereich: zp.wertebereich({{}}),
  raster: [zp.aufZeitraster(7), zp.aufZeitraster(8), zp.aufZeitraster(1439), zp.aufWertraster(19.25)],
}}));
""",
        encoding="utf-8",
    )
    ausgabe = subprocess.run(
        ["node", str(skript)], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return json.loads(ausgabe.stdout)


def test_felder_tragen_raster_und_bereich(editor):
    assert editor["zeile_felder"] == {
        "zeit_schritt": "900",
        "wert_schritt": "0.5",
        "min": "5",
        "max": "30",
    }
    assert editor["dialog_felder"] == {"zeit_schritt": "900", "min": "5", "max": "30"}


def test_eingaben_springen_ins_raster(editor):
    assert editor["zeile_zeit"] == ["06:00", "23:45"]
    assert editor["zeile_wert"] == ["21.5", "30", "5"]
    assert editor["modell"] == [{"zeit": 1425, "wert": 5}]
    assert editor["dialog"] == [{"zeit": 495, "wert": 20}]


def test_ohne_bereich_gilt_das_format(editor):
    assert editor["ohne_bereich"] == {"min": 0, "max": 127.5}
    assert editor["raster"] == [0, 15, 1425, 19.5]
