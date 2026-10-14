"""Jeder deutsche Text im Quelltext ist in jeder Sprache übersetzbar.

Die übrigen Wächter prüfen je einen bekannten Weg zum Nutzer. Dieser prüft
umgekehrt: Was deutsch im Quelltext steht, braucht einen Eintrag oder einen
Grund in `AUSNAHMEN`.
"""

from __future__ import annotations

import ast
import re

import pytest

from .conftest import COMPONENT_DIR as PAKET
from .conftest import load_standalone

_TEXTE = load_standalone("texte")
# Jede Sprache außer der Quelle; eine neue Sprache wird ohne Zutun mitgeprüft.
SPRACHEN = tuple(s for s in _TEXTE.SPRACHEN if s != _TEXTE.QUELLSPRACHE)

DEUTSCH = re.compile(
    r"[äöüÄÖÜß]|\b(und|der|die|das|nicht|bis|von|mit|keine|seit|oder|für|zum|zur|Uhr|"
    r"heute|Wert|wird|ist|sich|ein|eine|den|dem|steht|schon|erst)\b"
)
# Aufrufe, deren Text nie beim Nutzer ankommt oder einen eigenen Weg hat.
NICHT_ANGEZEIGT = {
    "debug",
    "info",
    "warning",
    "error",
    "exception",
    "critical",
    "compile",
    "search",
    "match",
    "fullmatch",
    "sub",
    "findall",
    "split",
    "namensmuster",
    "mit_text",
    "Invalid",
    # Programmierfehler; `HomeAssistantError` und Verwandte zählen weiter.
    "AssertionError",
    "ValueError",
    "TypeError",
    "KeyError",
    "RuntimeError",
}
# Dateien und Konstanten mit eigenem Übersetzungsweg.
AUSNAHMEN_DATEI = {
    "geraete": "Datenpunktnamen; Wächter test_jeder_feste_name_der_erkennung_steht_in_jeder_sprache",
    "diagnostics.py": "Diagnose-Export, nur für den Entwickler",
    "automatik/regel.py": "Sätze aus Teilen; Wächter test_jede_begruendung_kommt_auf_englisch_an",
    "automatik/tagesansicht.py": "Sätze aus Teilen; Wächter test_jede_begruendung_kommt_auf_englisch_an",
}
# Ein Text, der nur ins Protokoll geht; der Name steht am Ort der Zuweisung.
NUR_PROTOKOLL = {"Metadaten unvollständig"}
AUSNAHMEN_KONSTANTE = {
    "ERROR_TEXTS": "deutscher Rückfall; fremde Sprachen nehmen error_texts_<s>.json",
    "SPRACHE_BESCHRIFTUNG": "Rückfall der Auswahlliste; übersetzt über translations/*/selector",
    "KESSELART_BESCHRIFTUNG": "Rückfall der Auswahlliste; übersetzt über translations/*/selector",
    "_WORTE": "Tabelle führt jede Sprache selbst",
}


@pytest.fixture(scope="module")
def buecher():
    return {s: _TEXTE.Woerterbuch(s) for s in SPRACHEN}


def _ausgenommen(baum: ast.AST) -> set[int]:
    """Knoten, deren Text nicht angezeigt wird: Docstrings, Protokoll, Muster, Ausnahmen."""
    weg: set[int] = set()
    for knoten in ast.walk(baum):
        if (
            isinstance(knoten, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and ast.get_docstring(knoten, clean=False) is not None
        ):
            weg.add(id(knoten.body[0].value))
        if isinstance(knoten, ast.Call):
            f = knoten.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name in NICHT_ANGEZEIGT:
                weg.update(id(a) for a in ast.walk(knoten))
            # Bei `replace` ist nur das Gesuchte kein Anzeigetext.
            if name == "replace" and knoten.args:
                weg.update(id(a) for a in ast.walk(knoten.args[0]))
        ziele = [*getattr(knoten, "targets", []), getattr(knoten, "target", None)]
        if any(getattr(z, "id", "") in AUSNAHMEN_KONSTANTE for z in ziele):
            weg.update(id(a) for a in ast.walk(knoten))
    return weg


def _anzeigetexte(baum: ast.AST):
    """Deutsche Literale; ein f-String zählt als ganzer Satz mit Platzhalterwerten."""
    weg = _ausgenommen(baum)
    for knoten in ast.walk(baum):
        if id(knoten) in weg:
            continue
        if isinstance(knoten, ast.JoinedStr):
            weg.update(id(a) for teil in knoten.values for a in ast.walk(teil))
            text = "".join(t.value if isinstance(t, ast.Constant) else "7" for t in knoten.values)
        elif isinstance(knoten, ast.Constant) and isinstance(knoten.value, str):
            text = knoten.value
        else:
            continue
        # Kleingeschriebene Texte sind Suchmuster für Namen, keine Anzeige.
        if len(text) < 4 or text == text.lower() or not DEUTSCH.search(text):
            continue
        # Formatangaben wie `%s` stehen nur in Protokollzeilen.
        if re.search(r"%[sdr]", text) or text in NUR_PROTOKOLL:
            continue
        yield knoten.lineno, text


def _quellen():
    for datei in sorted(PAKET.rglob("*.py")):
        relativ = datei.relative_to(PAKET).as_posix()
        if not any(relativ == a or relativ.startswith(a + "/") for a in AUSNAHMEN_DATEI):
            yield relativ, datei


@pytest.fixture(scope="module")
def anzeigetexte():
    """Einmal gelesen, für jede Sprache geprüft."""
    return [
        (relativ, zeile, text)
        for relativ, datei in _quellen()
        for zeile, text in _anzeigetexte(ast.parse(datei.read_text(encoding="utf-8")))
    ]


@pytest.mark.parametrize("sprache", SPRACHEN)
def test_kein_deutscher_text_im_python_ohne_eintrag(buecher, anzeigetexte, sprache):
    """Ein Text ohne Eintrag erscheint in der fremden Sprache deutsch."""
    buch = buecher[sprache]
    fehlend = [
        f"{relativ}:{zeile} {text[:90]!r}"
        for relativ, zeile, text in anzeigetexte
        if buch.satz(text) == text
    ]
    assert not fehlend, "\n".join(fehlend)


# Template-Strings im Browser: deutsch nur über `_t`/`_tMit` mit Eintrag.
VORLAGE = re.compile(r"`([^`]*)`")


def _ohne_code(vorlage: str) -> str:
    """Den Text einer Vorlage ohne `${…}`, auch verschachtelt."""
    text, tiefe, i = [], 0, 0
    while i < len(vorlage):
        if vorlage.startswith("${", i):
            tiefe, i = tiefe + 1, i + 2
            continue
        if tiefe and vorlage[i] == "{":
            tiefe += 1
        elif tiefe and vorlage[i] == "}":
            tiefe -= 1
        elif not tiefe:
            text.append(vorlage[i])
        i += 1
    return "".join(text)


# Kommentare tragen Backticks als Codezeichen; ohne sie paaren sich die Vorlagen richtig.
KOMMENTAR = re.compile(r"/\*.*?\*/|^\s*//.*?$", re.DOTALL | re.MULTILINE)


def test_kein_deutscher_template_string_im_frontend():
    """`` `schon ${x} °C` `` geht an jedem Wörterbuch vorbei, auch über mehrere Zeilen."""
    fehlend = []
    for datei in sorted((PAKET / "frontend").rglob("*.js")):
        if datei.parent.name == "stil":
            continue
        quelle = KOMMENTAR.sub("", datei.read_text(encoding="utf-8"))
        for vorlage in VORLAGE.finditer(quelle):
            text = _ohne_code(vorlage.group(1))
            # Meldungen für die Konsole des Entwicklers, nicht für den Nutzer.
            if "Error(" in quelle[max(vorlage.start() - 12, 0) : vorlage.start()] or "<" in text:
                continue
            if re.search(r"[A-Za-zÄÖÜäöüß]{3}", text) and DEUTSCH.search(text):
                fehlend.append(f"{datei.relative_to(PAKET).as_posix()}: {text.strip()[:100]!r}")
    assert not fehlend, "\n".join(fehlend)
