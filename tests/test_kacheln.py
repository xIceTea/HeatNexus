"""Die Karten der Übersicht im Browser-Nachbau: Anmeldung, Editor, fehlende Entitäten."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "custom_components" / "heatnexus" / "frontend"
DURCHLAUF = Path(__file__).resolve().parent / "js" / "kacheln-durchlauf.mjs"
NAMEN = ["heatnexus-leitwert", "heatnexus-kennwerte", "heatnexus-puffer"]


@pytest.fixture(scope="module")
def bilanz() -> dict:
    if shutil.which("node") is None:
        pytest.skip("node nicht vorhanden")
    lauf = subprocess.run(
        [
            "node",
            str(DURCHLAUF),
            (FRONTEND / "heatnexus-kacheln.js").as_uri(),
            (FRONTEND / "heatnexus-schaubild-karte.js").as_uri(),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr
    return json.loads(lauf.stdout)


def test_die_schaubild_datei_bringt_die_karten_mit(bilanz):
    assert bilanz["ueberSchaubildGeladen"] == NAMEN
    assert bilanz["inKartenauswahl"] == NAMEN


def test_jede_karte_hat_erstkonfiguration_und_formular(bilanz):
    assert all(bilanz["stub"].values())
    assert "werte" in bilanz["formular"]["heatnexus-kennwerte"]
    assert {"zustand", "gross", "neben"} <= set(bilanz["formular"]["heatnexus-leitwert"])
    assert {"oben", "mitte", "unten"} <= set(bilanz["formular"]["heatnexus-puffer"])


def test_fehlende_entitaeten_ergeben_striche_statt_fehler(bilanz):
    assert bilanz["ohneEntitaeten"] == dict.fromkeys(NAMEN, True)
    assert bilanz["leereKonfiguration"] is True


def test_werte_stehen_mit_einheit_und_farbe(bilanz):
    assert "Modulation" in bilanz["leitwertText"] and "71 °C" in bilanz["leitwertText"]
    assert "Leistung 55 %" in bilanz["leitwertText"]
    assert bilanz["leitwertAktiv"] is True
    assert bilanz["kennwerte"] == ["45,2 °C", "12 h", "läuft", "80 %"]
    assert bilanz["warnfarbe"] is True and bilanz["ohneWarnfarbe"] is True
    assert "68,0 °C" in bilanz["pufferText"] and bilanz["saeuleVerlauf"] is True


def test_ein_klick_oeffnet_den_verlauf(bilanz):
    assert bilanz["klickOeffnet"] == "sensor.vorlauf"
    assert bilanz["anzeige"] == "45,2 °C"
    assert bilanz["anzeigeFehlt"] == "–"
