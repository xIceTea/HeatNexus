"""Die selbst gewählte Anordnung der Karten.

Der Kern ist eine einzige Rechnung: Eine gespeicherte Reihenfolge trifft auf
die Karten, die es *jetzt* gibt. Sie muss zwei Dinge zugleich können – die
Wahl des Nutzers halten und neu erkannte Anlagenteile einsortieren, ohne dass
sich alles verschiebt. Genau daran hängt die Zusage, dass ein zusätzlicher
Heizkreis die Anordnung nicht zerreißt.

Die Rechnung steht zweimal: als ``helpers.ordnung_anwenden`` für den Server und
als ``ordnungAnwenden`` in ``frontend/heatnexus-panel.js`` für den Browser. Der
letzte Test hier hält beide gegeneinander – zwei Fassungen, die auseinander
laufen, wären schlimmer als eine falsche.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

ORDNUNG_JS = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "heatnexus"
    / "frontend"
    / "ordnung.js"
)


# ---------------------------------------------------------------------------
# Reihenfolge
# ---------------------------------------------------------------------------
def test_ohne_gespeichertes_gilt_die_standardreihenfolge(helpers):
    standard = ["seite", "schaubild", "status"]
    assert helpers.ordnung_anwenden(standard, []) == standard


def test_gespeicherte_reihenfolge_schlaegt_die_standardreihenfolge(helpers):
    standard = ["seite", "schaubild", "status"]
    assert helpers.ordnung_anwenden(standard, ["status", "seite", "schaubild"]) == [
        "status",
        "seite",
        "schaubild",
    ]


def test_neue_karte_landet_an_ihrem_standardplatz_nicht_am_ende(helpers):
    """Ein neu erkannter Heizkreis rutscht neben seinesgleichen.

    Das ist die eigentliche Zusage: Der Nutzer hat „kessel" nach vorn gezogen,
    danach kommt ein zweiter Heizkreis dazu. Der gehört hinter den ersten – und
    nicht ans Ende, wo ihn niemand sucht.
    """
    standard = ["heizkreis:a", "heizkreis:b", "warmwasser", "kessel"]
    gespeichert = ["kessel", "heizkreis:a", "warmwasser"]
    assert helpers.ordnung_anwenden(standard, gespeichert) == [
        "kessel",
        "heizkreis:a",
        "heizkreis:b",
        "warmwasser",
    ]


def test_neue_erste_karte_kommt_nach_vorn(helpers):
    """Ohne Vorgänger bleibt nur der Anfang."""
    standard = ["neu", "kessel", "warmwasser"]
    assert helpers.ordnung_anwenden(standard, ["kessel", "warmwasser"]) == [
        "neu",
        "kessel",
        "warmwasser",
    ]


def test_verschwundene_karte_faellt_weg(helpers):
    """Was die Anlage nicht mehr meldet, taucht nicht als Lücke auf."""
    standard = ["kessel", "warmwasser"]
    assert helpers.ordnung_anwenden(standard, ["lagerraum", "warmwasser", "kessel"]) == [
        "warmwasser",
        "kessel",
    ]


def test_verschwundene_karte_gibt_ihren_platz_nicht_auf(helpers):
    """Kommt sie zurück, steht sie wieder da, wo sie war.

    Eine Anlage, die einmal nicht antwortet, soll die Anordnung nicht dauerhaft
    verändern. Der Speicher behält die Kennung; nur die Anzeige lässt sie weg.
    """
    gespeichert = ["lagerraum", "warmwasser", "kessel"]
    assert helpers.ordnung_anwenden(["kessel", "warmwasser"], gespeichert) == [
        "warmwasser",
        "kessel",
    ]
    # Später ist sie wieder da – und zwar an ihrem alten Platz.
    assert helpers.ordnung_anwenden(["kessel", "lagerraum", "warmwasser"], gespeichert) == [
        "lagerraum",
        "warmwasser",
        "kessel",
    ]


def test_reihenfolge_ist_stabil(helpers):
    """Zweimal anwenden ändert nichts mehr."""
    standard = ["a", "b", "c", "d"]
    einmal = helpers.ordnung_anwenden(standard, ["c", "a"])
    assert helpers.ordnung_anwenden(standard, einmal) == einmal


def test_keine_karte_geht_verloren_und_keine_doppelt(helpers):
    standard = ["a", "b", "c", "d", "e"]
    ergebnis = helpers.ordnung_anwenden(standard, ["e", "b", "unbekannt"])
    assert sorted(ergebnis) == sorted(standard)
    assert len(ergebnis) == len(set(ergebnis))


# ---------------------------------------------------------------------------
# Zusammenführen beim Speichern
# ---------------------------------------------------------------------------
def test_speichern_verliert_nicht_sichtbare_karten_nicht(helpers):
    """Unter „Alle" zeigt ein Reiter nur die Karten einer Anlage.

    Wird dort umsortiert, darf die gespeicherte Reihenfolge die Karten der
    anderen Anlage nicht verlieren – sonst wäre deren Anordnung weg, sobald
    jemand woanders eine Karte anfasst.
    """
    alt = ["heizkreis:a", "heizkreis:b", "kessel", "warmwasser"]
    neu_sichtbar = ["kessel", "heizkreis:a", "warmwasser"]
    zusammen = helpers.reihenfolge_mischen(neu_sichtbar, alt)
    assert "heizkreis:b" in zusammen
    assert zusammen.index("heizkreis:b") == zusammen.index("heizkreis:a") + 1
    assert [e for e in zusammen if e in neu_sichtbar] == neu_sichtbar


# ---------------------------------------------------------------------------
# Server und Browser dürfen nicht auseinanderlaufen
# ---------------------------------------------------------------------------
FAELLE = [
    (["a", "b", "c"], []),
    (["a", "b", "c"], ["c", "b", "a"]),
    (["a", "b", "c", "d"], ["d", "a"]),
    (["neu", "a", "b"], ["b", "a"]),
    (["a", "b"], ["weg", "b", "a"]),
    ([], ["a", "b"]),
    (["a", "b", "c", "d", "e"], ["e", "c"]),
]


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")
def test_browser_rechnet_genauso(helpers, tmp_path):
    """Die Fassung im Browser muss dasselbe herausbekommen wie die hier."""
    # Das Modul wird **geladen**, nicht aus einer größeren Datei
    # herausgeschnitten. Bis 1.5.0 lagen die Funktionen mitten in der
    # Panel-Datei, und der Test schnitt sie zwischen zwei Markierungen heraus.
    # Das prüfte nebenbei die ganze Datei auf gültiges JavaScript und hat so
    # zweimal einen Backtick im CSS-Kommentar gefunden – diese Prüfung
    # übernimmt jetzt `test_module_sind_gueltiges_javascript`.
    skript = tmp_path / "pruefung.mjs"
    adresse = ORDNUNG_JS.resolve().as_uri()
    skript.write_text(
        f'import {{ ordnungAnwenden }} from "{adresse}";\n'
        "const faelle = JSON.parse(process.argv[2]);\n"
        "console.log(JSON.stringify(faelle.map(([s, g]) => ordnungAnwenden(s, g))));\n",
        encoding="utf-8",
    )
    ausgabe = subprocess.run(
        ["node", str(skript), json.dumps(FAELLE)],
        capture_output=True,
        text=True,
        check=True,
    )
    erwartet = [helpers.ordnung_anwenden(standard, gespeichert) for standard, gespeichert in FAELLE]
    assert json.loads(ausgabe.stdout) == erwartet


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")
def test_module_sind_gueltiges_javascript(tmp_path):
    """Jedes Modul der Oberfläche muss sich laden lassen.

    Diese Prüfung hing bisher als Nebenwirkung am Test darüber. Sie hat zweimal
    denselben Fehler gefunden – ein Backtick in einem CSS-Kommentar beendet das
    Template-Literal, und die Datei ist kein gültiges JavaScript mehr –, und
    deshalb steht sie jetzt für sich und deckt **alle** Module ab.
    """
    ordner = ORDNUNG_JS.parent
    module = sorted(p for p in ordner.glob("*.js"))
    assert module, "keine Module gefunden"

    # Node kennt keinen Browser. Ohne diese Attrappen scheitert das Laden an
    # `extends HTMLElement`, und der Test prüfte nur noch sich selbst. Sie
    # sind bewusst so dünn wie möglich: Geprüft wird, dass die Dateien
    # gültiges JavaScript sind und ihr Rumpf durchläuft – nicht, was sie
    # zeichnen.
    attrappen = (
        "globalThis.HTMLElement = class {};\n"
        "globalThis.customElements = { get: () => undefined, define: () => {} };\n"
        "globalThis.document = { createElement: () => ({ style: {} }) };\n"
        "globalThis.window = globalThis;\n"
    )
    zeilen = [f'await import("{p.resolve().as_uri()}");' for p in module]
    skript = tmp_path / "laden.mjs"
    skript.write_text(attrappen + "\n".join(zeilen) + '\nconsole.log("ok");\n', encoding="utf-8")

    ausgabe = subprocess.run(["node", str(skript)], capture_output=True, text=True)
    assert ausgabe.returncode == 0, (
        f"Ein Modul der Oberfläche ist kein gültiges JavaScript: {ausgabe.stderr[:800]}"
    )
