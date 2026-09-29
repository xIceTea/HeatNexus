"""Dekodierung der Windhager-Störungen aus dem FE01msg-Feld.

Die Geräte-Discovery liefert je Gerät ein FE01msg, z.B. "PUR 09  OK" (kein
Fehler) oder "PUR 09E346" (Fehler 346). Mehrere Störungen reihen sich als
weitere E<code>-Einträge an. Die Codes werden über error_texts_<sprache>.json
(generiert aus den offiziellen Windhager-emStrIds) in Klartext + Handlungs-
empfehlung übersetzt.
"""

from __future__ import annotations

from functools import lru_cache
import json
import os
import re

# Code-Muster im FE01msg: E=Fehler, A=Alarm, I=Info, gefolgt von der Nummer.
_CODE_RE = re.compile(r"([EAI])(\d{2,4})")
_KATEGORIE = {"E": "FE", "A": "AL", "I": "IN"}
# Sprachen mit mitgelieferter Tabelle; die übrigen fallen auf Deutsch zurück.
SPRACHEN = ("de", "en", "nl")
_ART = {
    "de": {"E": "Fehler", "A": "Alarm", "I": "Info"},
    "en": {"E": "Error", "A": "Alarm", "I": "Info"},
    "nl": {"E": "Fout", "A": "Alarm", "I": "Info"},
}
_UNBEKANNT = {"de": "Unbekannter Code", "en": "Unknown code", "nl": "Onbekende code"}
_KEINE = {"de": "Keine Störung", "en": "No fault", "nl": "Geen storing"}


def textsprache(sprache: str | None) -> str:
    """Die Sprache, in der Meldungstexte erscheinen."""
    return sprache if sprache in SPRACHEN else "de"


def keine_stoerung(sprache: str | None = "de") -> str:
    """Der Zustand, wenn nichts ansteht."""
    return _KEINE[textsprache(sprache)]


def unbekannt(code: int, sprache: str | None = "de") -> str:
    """Der Zustand für einen Code, den keine Tabelle kennt."""
    return f"{_UNBEKANNT[textsprache(sprache)]} {code}"


def klartext(code: int, sprache: str) -> str | None:
    """Der Text zu einem Code aus der Tabelle genau dieser Sprache."""
    tabelle = _table(textsprache(sprache))
    for c in ("FE", "AL", "IN"):
        if entry := tabelle.get(f"{c}{code}"):
            return entry.get("text")
    return None


@lru_cache(maxsize=len(SPRACHEN))
def _table(sprache: str = "de") -> dict:
    if sprache not in SPRACHEN:
        return {}
    path = os.path.join(os.path.dirname(__file__), f"error_texts_{sprache}.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _lookup(cat: str, code: int, sprache: str = "de") -> dict:
    """Eintrag zu Kategorie+Code, mit Fallback über alle Kategorien und auf Deutsch."""
    for table in (_table(sprache), _table("de")):
        for c in (cat, "FE", "AL", "IN"):
            entry = table.get(f"{c}{code}")
            if entry:
                return entry
    return {}


def parse_messages(raw: str | None, zusatz: dict | None = None, sprache: str = "de") -> list[dict]:
    """Aktive Störungen aus einem FE01msg-String extrahieren.

    'PUR 09E346' -> [{'code': 346, 'kind': 'Fehler',
                      'text': 'Verkleidungstür offen',
                      'info': 'Verkleidungstür schließen, ...'}]
    'PUR 09  OK' -> []

    ``zusatz`` sind die Störungstexte, die die Anlage selbst mitführt. Sie
    gelten vor der mitgelieferten Tabelle, weil sie zur Fassung der Steuerung
    und zur eingestellten Sprache passen. Eine Handlungsempfehlung führt die
    Steuerung nicht mit; die bleibt aus der Tabelle der ``sprache``.
    """
    treffer = _CODE_RE.findall(raw or "")
    if not treffer:
        return []
    out: list[dict] = []
    seen: set[int] = set()
    # Nach dem Ablegen als JSON sind die Schlüssel Text statt Zahl. Die Tabelle
    # der Anlage umfasst alle Codes ihrer Baureihe; sie erst hier umzuschreiben
    # hält den Normalfall – keine Störung – frei von dieser Arbeit.
    vom_geraet = {int(code): text for code, text in (zusatz or {}).items()}
    sprache = textsprache(sprache)
    for letter, num in treffer:
        code = int(num)
        if code in seen:
            continue
        seen.add(code)
        entry = _lookup(_KATEGORIE.get(letter, "FE"), code, sprache)
        out.append(
            {
                "code": code,
                "kind": _ART[sprache].get(letter, _ART[sprache]["E"]),
                "text": vom_geraet.get(code) or entry.get("text", _UNBEKANNT[sprache]),
                "info": entry.get("info"),
            }
        )
    return out


def preload() -> None:
    """Störungstexte einlesen (siehe device_db.preload)."""
    for sprache in SPRACHEN:
        _table(sprache)
