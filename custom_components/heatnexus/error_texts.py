"""Dekodierung der Windhager-Störungen aus dem FE01msg-Feld.

Die Geräte-Discovery liefert je Gerät ein FE01msg, z.B. "PUR 09  OK" (kein
Fehler) oder "PUR 09E346" (Fehler 346). Mehrere Störungen reihen sich als
weitere E<code>-Einträge an. Die Codes werden über error_texts_de.json
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
_KIND = {"E": ("FE", "Fehler"), "A": ("AL", "Alarm"), "I": ("IN", "Info")}


@lru_cache(maxsize=1)
def _table() -> dict:
    path = os.path.join(os.path.dirname(__file__), "error_texts_de.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _lookup(cat: str, code: int) -> dict:
    """Eintrag zu Kategorie+Code, mit Fallback über alle Kategorien."""
    table = _table()
    entry = table.get(f"{cat}{code}")
    if entry:
        return entry
    for c in ("FE", "AL", "IN"):
        entry = table.get(f"{c}{code}")
        if entry:
            return entry
    return {}


def parse_messages(raw: str | None) -> list[dict]:
    """Aktive Störungen aus einem FE01msg-String extrahieren.

    'PUR 09E346' -> [{'code': 346, 'kind': 'Fehler',
                      'text': 'Verkleidungstür offen',
                      'info': 'Verkleidungstür schließen, ...'}]
    'PUR 09  OK' -> []
    """
    out: list[dict] = []
    seen: set[int] = set()
    for letter, num in _CODE_RE.findall(raw or ""):
        code = int(num)
        if code in seen:
            continue
        seen.add(code)
        cat, word = _KIND.get(letter, ("FE", "Fehler"))
        entry = _lookup(cat, code)
        out.append(
            {
                "code": code,
                "kind": word,
                "text": entry.get("text", "Unbekannter Code"),
                "info": entry.get("info"),
            }
        )
    return out
