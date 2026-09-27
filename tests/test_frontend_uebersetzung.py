"""Jeder übersetzte Text der Oberfläche hat eine englische Fassung."""

from __future__ import annotations

import json
from pathlib import Path
import re

WURZEL = Path(__file__).parent.parent / "custom_components" / "heatnexus"
# Hilfetexte stehen als `hilfe: "…"` in Tabellen und gehen erst im Fenster durch `_t`.
AUFRUF = re.compile(r'(?:\bt\(|\._t\(|\bhilfe:)\s*"([^"]+)"')
# Texte, die auf Englisch genauso lauten.
GLEICH = {"+ Block", "Block", "HeatNexus"}


def test_jeder_uebersetzte_text_steht_in_en_json():
    englisch = json.loads((WURZEL / "sprachen" / "en.json").read_text(encoding="utf-8"))
    verwendet = {
        text
        for datei in (WURZEL / "frontend").rglob("*.js")
        for text in AUFRUF.findall(datei.read_text(encoding="utf-8"))
        if re.search(r"[^\W\d_]", text)
    }

    fehlen = sorted(verwendet - set(englisch) - GLEICH)

    assert not fehlen, f"ohne englische Fassung: {fehlen}"
