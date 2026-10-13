"""Lebenszyklus der Oberfläche in Node: Neuaufbau, Hörer, Zeitgeber, Dialoge, Tastatur."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")

WURZEL = Path(__file__).resolve().parents[1]
PANEL_JS = WURZEL / "custom_components" / "heatnexus" / "frontend" / "heatnexus-panel.js"
LAUF = Path(__file__).parent / "js" / "panel-lebenszyklus.mjs"


@pytest.fixture(scope="module")
def befund() -> dict:
    lauf = subprocess.run(
        ["node", str(LAUF), str(PANEL_JS)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr or lauf.stdout
    return json.loads(lauf.stdout)


def test_der_neuaufbau_haeuft_keine_klickhoerer_an(befund):
    assert befund["klickhoererNachFuenfAufbauten"] <= 1


def test_gleiche_daten_loesen_keinen_neuaufbau_aus(befund):
    assert befund["neuaufbauBeiGleichenDaten"] is False


def test_fremde_entitaeten_loesen_keine_aktualisierung_aus(befund):
    assert befund["durchlaeufeBeiFremderEntitaet"] == 0


def test_gelesene_entitaeten_werden_je_bild_einmal_aktualisiert(befund):
    assert befund["durchlaeufeBeiGelesenerEntitaet"] == 1


def test_der_abbau_beendet_zeitgeber(befund):
    assert befund["zeitgeberNachAbbau"] == 0


def test_der_abbau_schreibt_die_wartende_anordnung(befund):
    assert befund["gespeichertBeimAbbau"] == 1
