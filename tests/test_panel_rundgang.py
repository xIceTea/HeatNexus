"""Der Rundgang durch die Oberfläche.

**Geprüft wird, was ohne Browser prüfbar ist.** Die Aufnahme selbst hängt an
einem kopflosen Browser und am installierten Frontend-Paket; ein Vergleich auf
das fertige GIF wäre in der CI nur eine Fehlalarmquelle. Was sich prüfen lässt
und worauf es ankommt: dass der Rundgang die Reiter zeigt, die es gibt, dass
die Störung wirklich als Störung in der Zustandstabelle landet und dass die
Klartexte der Betriebsarten gefunden werden.

Der Anlass: Der Auftritt mit der Störung unterscheidet sich vom ruhigen
Betrieb nur durch ein einziges Attribut (`stoerung_aktiv`). Fällt das weg,
zeigt der Rundgang achtmal dieselbe heile Welt – und niemandem fällt es auf.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

WERKZEUG = Path(__file__).parent.parent / "tools" / "build_panel_rundgang.py"


@pytest.fixture(scope="module")
def rundgang():
    """Das Werkzeug lädt Home Assistant nach, aber keinen Browser."""
    spec = importlib.util.spec_from_file_location("panel_rundgang", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


# ---------------------------------------------------------------------------
# Der Ablauf
# ---------------------------------------------------------------------------
def test_der_rundgang_zeigt_nur_reiter_die_es_gibt(rundgang):
    """Ein Tippfehler im Reiternamen ergäbe eine leere Aufnahme."""
    quelle = (
        Path(__file__).parent.parent
        / "custom_components"
        / "heatnexus"
        / "frontend"
        / "heatnexus-panel.js"
    ).read_text(encoding="utf-8")
    for auftritt in rundgang.AUFTRITTE:
        assert f'"{auftritt["reiter"]}"' in quelle, auftritt["reiter"]


def test_jeder_auftritt_hat_eine_dauer_und_einen_titel(rundgang):
    """Ohne Dauer stünde das Bild still, ohne Titel wüsste niemand, was läuft."""
    for auftritt in rundgang.AUFTRITTE:
        assert auftritt["dauer"] > 0
        assert auftritt["titel"]


def test_der_rundgang_zeigt_eine_stoerung(rundgang):
    """Was die Anlage im Ernstfall zeigt, gehört in den Rundgang."""
    mit_stoerung = [a for a in rundgang.AUFTRITTE if a.get("zustand")]
    assert mit_stoerung, "kein Auftritt mit Störung"


def test_die_stoerung_kommt_wirklich_in_der_zustandstabelle_an(rundgang):
    """Der Balken oben hängt an genau diesem Attribut."""
    from beispielanlage import zustaende

    ruhe = zustaende()
    assert ruhe["sensor.meldung_klartext"]["attributes"]["stoerung_aktiv"] is False

    laut = zustaende(rundgang.STOERUNG)
    eintrag = laut["sensor.meldung_klartext"]
    assert eintrag["attributes"]["stoerung_aktiv"] is True
    assert "Aschelade" in eintrag["state"]


def test_die_uebrigen_zustaende_bleiben_bei_einer_stoerung_stehen(rundgang):
    """Überschrieben wird ein Datenpunkt, nicht die ganze Anlage."""
    from beispielanlage import zustaende

    laut = zustaende(rundgang.STOERUNG)
    assert laut["sensor.kesseltemperatur_ist"]["state"] == "72.4"


# ---------------------------------------------------------------------------
# Was die Oberfläche zum Zeichnen braucht
# ---------------------------------------------------------------------------
def test_die_betriebsarten_haben_klartexte(rundgang):
    """Sonst stünde am Thermostat die nackte Zahl der Anlage."""
    klartexte = rundgang.presets()
    assert klartexte.get("0") == "Standby"
    assert klartexte.get("4") == "Heizbetrieb"


def test_die_symbolnamen_werden_auch_aus_der_oberflaeche_gelesen(rundgang):
    """Ein Teil der Symbole steht nicht in den Daten, sondern im Quelltext."""
    namen = rundgang._symbolnamen({"symbol": "mdi:fire"})
    assert "fire" in namen
    # Aus `bausteine.js` – nur dort, nicht in den Daten.
    assert "chevron-down" in namen
    assert all(" " not in name for name in namen)


def test_die_aufteilung_entsteht_aus_der_beispielanlage(rundgang):
    """Dieselbe Anlage wie im Schaubild – sonst zeigte das README zwei Häuser."""
    daten = rundgang.panel_daten()
    anlage = daten["anlagen"][0]
    assert anlage["name"] == "Heizhaus"
    assert anlage["kennwerte"], "keine Kennwerte"
    assert anlage["status"], "kein Systemstatus"
    assert anlage["zeitprogramme"], "keine Zeitprogramme"
    assert anlage["steuerung"]["heizkreise"], "kein Heizkreis in der Steuerung"


def test_das_zeitprogramm_traegt_lesbare_schaltpunkte(rundgang):
    """Die Oberfläche liest `switchPoints`; `switch_points` ergäbe leere Balken."""
    from beispielanlage import zustaende

    bloecke = zustaende()["sensor.heizprogramm"]["attributes"]["blocks"]
    assert bloecke
    for block in bloecke:
        assert block["switchPoints"], block
        for punkt in block["switchPoints"]:
            assert ":" in punkt["time"]


def test_das_bild_liegt_vor(rundgang):
    """Fehlt es, zeigt die Dokumentation ein totes Bild."""
    assert rundgang.ZIEL.exists(), (
        f"{rundgang.ZIEL.name} fehlt – python tools/build_panel_rundgang.py"
    )
