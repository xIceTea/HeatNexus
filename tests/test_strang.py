"""Strang im Schaubild: Reihenplanung und Aufbau im Panel, in Node gefahren."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")

FRONTEND = Path(__file__).parent.parent / "custom_components" / "heatnexus" / "frontend"
JS = Path(__file__).parent / "js"


def _node(skript: str, *argumente: Path) -> str:
    lauf = subprocess.run(
        ["node", str(JS / skript), *map(str, argumente)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr or lauf.stdout
    return lauf.stdout


def test_reihenplanung():
    """Ausgeglichene Reihen, Obergrenze beim Verkleinern, Rückfall bei zu wenig Platz."""
    assert _node("strang-test.mjs", FRONTEND / "teile" / "strang.js").strip() == "ok"


PANEL_JS = FRONTEND / "heatnexus-panel.js"


@pytest.fixture(scope="module")
def reihen() -> dict:
    """Den Aufbau des Strangs im Panel in Node fahren."""
    return json.loads(_node("strang-reihen.mjs", PANEL_JS))


def test_standard_ist_umbrechen_mit_mittlerer_groesse(reihen):
    assert reihen["standard"] == {"modus": "umbrechen", "groesse": 120}


def test_schmale_karte_bricht_ausgeglichen_um(reihen):
    """Sieben Teile zu 120 px in 700 px: Reihen mit vier und drei Teilen."""
    assert reihen["vorMessung"] == 1
    assert reihen["schmal"] == ["480px", "360px"]


def test_jede_reihe_zeigt_live_werte(reihen):
    """Zwei Pumpenmarken, zwei Reihen: Jede Hülle trägt beide Marken und bindet sie."""
    assert reihen["laufen"] == [True, True, True, True]


def test_unsichtbare_marken_sind_nicht_fokussierbar(reihen):
    """Bei 1448 Breite liegt die 50-%-Marke in Teil 3 (Reihe 1), die 90-%-Marke in Teil 6 (Reihe 2)."""
    erste, zweite = reihen["fokus"]
    assert erste["marken"] == [["50%", "0", None], ["90%", "-1", "true"]]
    assert zweite["marken"] == [["50%", "-1", "true"], ["90%", "0", None]]
    assert erste["alt"] == "Anlagenschaubild"
    assert zweite["alt"] == ""


def test_gleiche_aufteilung_baut_nicht_neu(reihen):
    assert reihen["ohneNeubau"] is True


def test_breite_karte_eine_reihe_ohne_liegengebliebene_bindungen(reihen):
    assert reihen["breit"] == ["840px"]
    assert reihen["bindungen"] == 1
    assert reihen["getrennt"] is True


def test_abbruch_verwirft_den_vorgemerkten_umbau(reihen):
    """Der Umbau läuft im nächsten Bild; nach dem Abbau der Oberfläche bleibt er aus."""
    assert reihen["nachAbbruch"] == ["840px"]


def test_verkleinern_bleibt_in_einer_reihe_unter_der_obergrenze(reihen):
    assert len(reihen["verkleinern"]) == 1
    assert float(reihen["verkleinern"][0].removesuffix("px")) < 700


def test_ohne_wahl_bleibt_das_bild_wie_bisher(reihen):
    """Die Lovelace-Karte hat keine Darstellung; dort bleibt die Hülle direkt in der Karte."""
    assert reihen["ohneWahl"] == {"strang": 0, "huellen": 1}
