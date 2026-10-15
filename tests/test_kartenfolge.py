"""Reihenfolge nach Kartenart: Gruppieren, Schieben und Ablegen aus `frontend/ordnung.js`."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

ORDNUNG_JS = (
    Path(__file__).parents[1] / "custom_components" / "heatnexus" / "frontend" / "ordnung.js"
).resolve()

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")

GEMISCHT = ["a|seite", "a|hk:1", "b|seite", "b|hk:2", "a|status"]
GRUPPEN = ["a|hk:1", "b|hk:2", "alle|status"]
ABLAGE = ["alle|seite", "a|hk:1", "b|hk:2", "alle|status"]

# Je Fall ein Ausdruck; alle laufen in einem einzigen Node-Prozess.
FAELLE = {
    "arten": '["a|seite", "a|heizkreis:geraet-1", "alle|stoerungen", "seite"].map(kartenart)',
    "geordnet": f"nachArtOrdnen({json.dumps(GEMISCHT)})",
    "in_gruppe": f'artSchritt({json.dumps(GRUPPEN)}, "a|hk:1", 1)',
    "gruppenrand": f'artSchritt({json.dumps(GRUPPEN)}, "b|hk:2", 1)',
    "am_ende": '(() => { const f = ["alle|seite", "alle|status"]; return artSchritt(f, "alle|status", 1) === f; })()',
    "fremde_art": f'artAblegen({json.dumps(ABLAGE)}, "b|hk:2", "alle|seite", true)',
    "eigene_art": f'artAblegen({json.dumps(ABLAGE)}, "b|hk:2", "a|hk:1", true)',
    "flach_schritt": 'schritt(["x", "y", "z"], "x", 1)',
    "flach_rand": '(() => { const f = ["x", "y"]; return schritt(f, "y", 1) === f; })()',
    "flach_ablegen": 'ablegen(["x", "y", "z"], "z", "x", true)',
}


@pytest.fixture(scope="module")
def ergebnis(tmp_path_factory):
    skript = tmp_path_factory.mktemp("kartenfolge") / "pruefung.mjs"
    zeilen = ",\n".join(f"  {json.dumps(name)}: {ausdruck}" for name, ausdruck in FAELLE.items())
    skript.write_text(
        "import { ablegen, artAblegen, artSchritt, kartenart, nachArtOrdnen, schritt } from "
        f'"{ORDNUNG_JS.as_uri()}";\n'
        f"console.log(JSON.stringify({{\n{zeilen}\n}}));\n",
        encoding="utf-8",
    )
    ausgabe = subprocess.run(
        ["node", str(skript)], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return json.loads(ausgabe.stdout)


def test_die_art_steht_zwischen_anlage_und_geraet(ergebnis):
    assert ergebnis["arten"] == ["seite", "heizkreis", "stoerungen", "seite"]


def test_gleiche_arten_ruecken_in_der_folge_ihrer_ersten_nennung_zusammen(ergebnis):
    assert ergebnis["geordnet"] == ["a|seite", "b|seite", "a|hk:1", "b|hk:2", "a|status"]


def test_ein_schritt_bleibt_in_der_gruppe_solange_es_geht(ergebnis):
    assert ergebnis["in_gruppe"] == ["b|hk:2", "a|hk:1", "alle|status"]


def test_am_gruppenrand_wandert_die_ganze_gruppe(ergebnis):
    assert ergebnis["gruppenrand"] == ["alle|status", "a|hk:1", "b|hk:2"]


def test_am_ende_bleibt_die_folge_dieselbe(ergebnis):
    assert ergebnis["am_ende"] is True


def test_ablegen_in_einer_fremden_art_nimmt_die_gruppe_mit(ergebnis):
    assert ergebnis["fremde_art"] == ["a|hk:1", "b|hk:2", "alle|seite", "alle|status"]


def test_ablegen_in_der_eigenen_art_ordnet_nur_dort(ergebnis):
    assert ergebnis["eigene_art"] == ["alle|seite", "b|hk:2", "a|hk:1", "alle|status"]


def test_ohne_arten_schiebt_und_legt_die_flache_folge(ergebnis):
    assert ergebnis["flach_schritt"] == ["y", "x", "z"]
    assert ergebnis["flach_rand"] is True
    assert ergebnis["flach_ablegen"] == ["z", "x", "y"]
