"""Werte im Schaubild: Lage und Größe aus der Darstellung, Wertleiste je Reihe, Füllstand im Bild."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")

PANEL_JS = (
    Path(__file__).parent.parent
    / "custom_components"
    / "heatnexus"
    / "frontend"
    / "heatnexus-panel.js"
)
SKRIPT = Path(__file__).parent / "js" / "schaubild-werte.mjs"


@pytest.fixture(scope="module")
def werte() -> dict:
    lauf = subprocess.run(
        ["node", str(SKRIPT), str(PANEL_JS)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr or lauf.stdout
    return json.loads(lauf.stdout)


def test_unter_dem_bild_steht_jede_zahl_in_der_spalte_ihres_anlagenteils(werte):
    """Zwei Reihen zu 4 und 3 Teilen; jede Zahl trägt ihren Namen."""
    assert werte["unter_leisten"] == [
        [["Vorratsbehälter63 %"], [], [], ["Kessel71.5 °C"]],
        [[], [], ["COP3.6"]],
    ]
    assert werte["unter_marken"] == []


def test_mit_wertleiste_waechst_das_fenster(werte):
    assert werte["unter_hoehe"] == ["", ""]


def test_im_bild_gibt_es_keine_wertleiste(werte):
    assert werte["bild_leisten"] == [None, None]
    assert "COP 3.6" in werte["bild_marken"]
    # Am Behälter steht im Bild nur die Zahl, ohne das Wort „Vorratsbehälter“.
    assert "63 %" in werte["bild_marken"]
    assert not any("Vorratsbehälter" in marke for marke in werte["bild_marken"])


def test_im_bild_steht_jede_zahl_nur_in_ihrer_reihe(werte):
    """Die Zahlen liegen ungeschnitten über der Zeichnung und zeigen sich nur einmal."""
    assert werte["bild_je_reihe"] == [["71.5 °C", "63 %"], ["COP 3.6"]]


def test_automatisch_folgt_der_tatsaechlichen_breite(werte):
    """Beim Verkleinern zählt die Breite eines Teils, nicht die gewählte Größe."""
    assert werte["auto_schmal"] == 1
    assert werte["auto_schmal_leiste"] is True
    assert werte["auto_breit_leiste"] is False


def test_der_befuellgrad_bleibt_bei_null_prozent_weg(werte):
    assert werte["lager_null"] == ["71.5 °C", "COP 3.6"]


def test_der_behaelter_zeigt_seine_stufe_mit_koernung_und_umriss(werte):
    assert werte["behaelter"] == ["voll", False, ["koerner", "umriss"]]


def test_die_groesse_der_werte_setzt_das_schriftmass(werte):
    """„Mittel“ ist das bisherige Maß und gilt ohne Wahl."""
    assert werte["schrift"] == [1, 1.25, 1.5, 1.25]


def test_der_befuellgrad_fuellt_den_behaelter_sonst_gilt_die_feste_hoehe(werte):
    assert werte["lagerfuellung"] == [
        ["anteil", False, "37%"],
        ["anteil", False, "33.85%"],
        ["anteil", False, "33.85%"],
    ]


def test_der_luefter_laeuft_an_der_leistung_oder_an_der_waermelieferung(werte):
    """Eine fremde Wärmepumpe meldet keine Leistung; ihr Lüfter folgt der Wärmelieferung."""
    assert werte["luefter"] == [[True, True], [False, False]]


def test_der_puffer_zeigt_ohne_wahl_zwei_zahlen(werte):
    assert werte["puffer_zwei"]["marken"] == ["60.5 °C", "46.6 °C"]
    assert werte["puffer_zwei"]["wort"] == "50%"


def test_mit_drei_pufferwerten_rueckt_das_wort_nach_oben(werte):
    assert werte["puffer_drei"]["marken"] == ["60.5 °C", "46.6 °C", "50.7 °C"]
    assert werte["puffer_drei"]["wort"] == "30%"


def test_der_tooltip_nennt_mitte_und_beladegrad(werte):
    assert werte["puffer_zwei"]["titel"] == (
        "Puffer – oben 60.5 °C, mitte 50.7 °C, unten 46.6 °C, Beladegrad 38 %"
    )


def test_ohne_beladegrad_bleibt_der_tooltip_bei_den_fuehlern(werte):
    assert werte["puffer_ohne_beladegrad"]["titel"] == (
        "Puffer – oben 60.5 °C, mitte 50.7 °C, unten 46.6 °C"
    )
