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


def test_das_stylesheet_wird_geteilt_und_nicht_neu_angelegt(befund):
    assert befund["stilknoten"] == 0
    assert befund["geteilteBoegen"] == 1
    assert befund["bogenGeteilt"] is True


def test_ein_fenster_hat_rolle_und_beschriftung(befund):
    assert befund["fensterRolle"] == ["dialog", "true"]
    assert befund["fensterBeschriftet"] is True


def test_ein_offenes_fenster_uebersteht_den_neuaufbau(befund):
    assert befund["fensterNachNeuaufbau"] == 1


def test_escape_schliesst_das_fenster_und_loest_den_hoerer(befund):
    assert befund["fensterNachEscape"] == 0
    assert befund["tastenhoerer"] == 0
    assert befund["fokusZurueck"] is True


def test_der_abbau_schliesst_offene_fenster(befund):
    assert befund["fensterNachAbbau"] == 0
    assert befund["tastenhoererNachAbbau"] == 0


def test_reiter_haben_roving_tabindex_und_flaeche(befund):
    assert befund["reiterTabindex"].count("0") == 1
    assert befund["reiterSteuernFlaeche"] is True
    assert befund["flaecheBeschriftet"] >= 1


def test_pfeiltaste_bewegt_den_fokus_im_reiter(befund):
    assert befund["pfeilFokus"] is True


def test_werkzeugmenue_oeffnet_und_schliesst_per_tastatur(befund):
    assert befund["menueOffen"] is True
    assert befund["menueFokus"] is True
    assert befund["menueNachEscape"] == [True, True]


def test_menutaste_nur_wo_die_seitenleiste_nicht_fest_steht(befund):
    assert befund["menuetaste"] == {"breit": "none", "schmal": "", "versteckteLeiste": ""}
