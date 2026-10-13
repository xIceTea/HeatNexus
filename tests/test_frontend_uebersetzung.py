"""Jeder übersetzte Text der Oberfläche hat eine englische Fassung."""

from __future__ import annotations

import json
from pathlib import Path
import re

WURZEL = Path(__file__).parent.parent / "custom_components" / "heatnexus"
# Hilfetexte stehen als `hilfe: "…"` in Tabellen und gehen erst im Fenster durch `_t`.
AUFRUF = re.compile(r'(?:\bt\(|\._t\(|\._tMit\(|\bhilfe:)\s*"([^"]+)"')
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


def _betriebsarten() -> dict[str, str]:
    quelle = (WURZEL / "frontend" / "ordnung.js").read_text(encoding="utf-8")
    block = re.search(r"BETRIEBSARTEN = \{(.*?)\};", quelle, re.S).group(1)
    return dict(re.findall(r'(\d+): "([^"]+)"', block))


def test_betriebsarten_gleichen_den_voreinstellungen_des_thermostats():
    deutsch = json.loads((WURZEL / "translations" / "de.json").read_text(encoding="utf-8"))
    klima = deutsch["entity"]["climate"]["heatnexus_climate"]
    assert _betriebsarten() == klima["state_attributes"]["preset_mode"]["state"]


def test_jede_betriebsart_steht_in_jedem_woerterbuch():
    for sprache in ("en", "nl"):
        datei = WURZEL / "sprachen" / f"{sprache}.json"
        woerterbuch = json.loads(datei.read_text(encoding="utf-8"))
        fehlen = sorted(set(_betriebsarten().values()) - set(woerterbuch))
        assert not fehlen, f"{sprache} ohne: {fehlen}"


def test_die_seite_holt_keine_texte_aus_der_sprache_von_home_assistant():
    """Home Assistant übersetzt in die Sprache des Nutzers, die Seite folgt der Option."""
    treffer = [
        datei.name
        for datei in (WURZEL / "frontend").rglob("*.js")
        if re.search(r"formatEntityAttribute(Value|Name)", datei.read_text(encoding="utf-8"))
    ]
    assert not treffer
