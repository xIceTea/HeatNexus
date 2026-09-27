"""Reiter „Automatik“: reine Hilfen in Node, Felder passend zum Server."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
import shutil
import subprocess

import pytest

from .conftest import load_standalone

WURZEL = Path(__file__).resolve().parents[1]
AUTOMATIK_JS = WURZEL / "custom_components" / "heatnexus" / "frontend" / "teile" / "automatik.js"
PRUEFUNG = Path(__file__).parent / "js" / "automatik-test.mjs"


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")
def test_hilfen_rechnen_richtig():
    ergebnis = subprocess.run(
        ["node", str(PRUEFUNG), str(AUTOMATIK_JS)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert ergebnis.returncode == 0, ergebnis.stderr
    assert ergebnis.stdout.strip() == "ok"


def test_jedes_einstellbare_feld_steht_in_der_oberflaeche():
    load_standalone("automatik")
    profile = load_standalone("automatik.profile")
    text = AUTOMATIK_JS.read_text(encoding="utf-8")
    for feld in fields(profile.Werte):
        assert f'name: "{feld.name}"' in text, feld.name


def test_jeder_zustand_hat_eine_beschriftung():
    load_standalone("automatik")
    load_standalone("automatik.profile")
    regel = load_standalone("automatik.regel")
    text = AUTOMATIK_JS.read_text(encoding="utf-8")
    for zustand in regel.Zustand:
        assert f"  {zustand.value}: " in text, zustand.value
