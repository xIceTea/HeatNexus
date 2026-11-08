"""Ein Neuaufbau des Panels hält die Scrolllage, gleich aus welchem Abschnitt er kommt."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

TEILE = (
    Path(__file__).resolve().parents[1] / "custom_components" / "heatnexus" / "frontend" / "teile"
)

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")


def test_neuaufbau_an_ort_steht_in_den_bausteinen(tmp_path):
    # Die Darstellung braucht den Neuaufbau ohne Sprung; die Automatik darf dafür nicht nötig sein.
    skript = tmp_path / "scrolllage.mjs"
    skript.write_text(
        "globalThis.HTMLElement = class {};\n"
        f'const {{ BausteineMixin }} = await import("{(TEILE / "bausteine.js").as_uri()}");\n'
        "class Flaeche extends BausteineMixin(class {}) {\n"
        "  constructor() { super(); this.scrollTop = 120; this.parentElement = null; }\n"
        "  _zeichnen() { this.gezeichnet = true; this.scrollTop = 0; }\n"
        "}\n"
        "const flaeche = new Flaeche();\n"
        "flaeche._zeichnenAnOrt();\n"
        "console.log(JSON.stringify([flaeche.gezeichnet, flaeche.scrollTop]));\n",
        encoding="utf-8",
    )
    ausgabe = subprocess.run(["node", str(skript)], capture_output=True, text=True, check=True)
    assert json.loads(ausgabe.stdout) == [True, 120]
