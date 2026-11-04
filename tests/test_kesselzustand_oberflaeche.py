"""Kesselzustand im Kopf der Übersicht: Auswertung in Node."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

WURZEL = Path(__file__).resolve().parents[1]
MODUL = WURZEL / "custom_components" / "heatnexus" / "frontend" / "teile" / "kesselzustand.js"
PRUEFUNG = Path(__file__).parent / "js" / "kesselzustand-test.mjs"


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")
def test_der_kesselzustand_folgt_der_vorrangfolge():
    lauf = subprocess.run(
        ["node", str(PRUEFUNG), str(MODUL)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr
    assert lauf.stdout.strip() == "ok"
