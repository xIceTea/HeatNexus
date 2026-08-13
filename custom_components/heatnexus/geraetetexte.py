"""Textwerk der Steuerung (`/res/xml/`).

Jede Steuerung führt die Klartexte ihrer Datenpunkte selbst mit, je Sprache
eine Datei. Diese Quelle geht mit der Fassung der Anlage mit, während die
mitgelieferte Datenbank nur Deutsch kennt.

Das Modul bleibt frei von Home Assistant und aiohttp: Der Abruf wird als
Rückruf hereingereicht, gelesen wird reiner Text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from xml.etree import ElementTree as ET

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Texte:
    """Was eine Steuerung an Klartext über sich selbst hergibt."""

    namen: dict[str, str] = field(default_factory=dict)
    enums: dict[str, dict[int, str]] = field(default_factory=dict)
    ebenen: dict[str, str] = field(default_factory=dict)
    stoerungen: dict[int, str] = field(default_factory=dict)

    def __bool__(self) -> bool:
        """Wahr, sobald die Anlage irgendeinen Text geliefert hat."""
        return bool(self.namen or self.enums or self.ebenen or self.stoerungen)


def _wurzel(xml: str) -> ET.Element | None:
    """XML einlesen; unlesbares ergibt ``None``."""
    if not xml or not xml.strip():
        return None
    try:
        return ET.fromstring(xml)
    except ET.ParseError as fehler:
        _LOGGER.debug("Textdatei nicht lesbar: %s", fehler)
        return None


def namen_lesen(xml: str) -> dict[str, str]:
    """Datenpunktnamen als ``gn/mn`` -> Text."""
    wurzel = _wurzel(xml)
    if wurzel is None:
        return {}
    namen: dict[str, str] = {}
    for gruppe in wurzel:
        for eintrag in gruppe:
            if text := (eintrag.text or "").strip():
                namen[f"{gruppe.get('id')}/{eintrag.get('id')}"] = text
    return namen


def enums_lesen(xml: str) -> dict[str, dict[int, str]]:
    """Aufzählungstexte als ``gn/mn`` -> {Wert: Text}."""
    wurzel = _wurzel(xml)
    if wurzel is None:
        return {}
    enums: dict[str, dict[int, str]] = {}
    for gruppe in wurzel:
        for eintrag in gruppe:
            werte: dict[int, str] = {}
            for wert in eintrag:
                text = (wert.text or "").strip()
                if not text:
                    continue
                try:
                    werte[int(wert.get("id"))] = text
                except (TypeError, ValueError):
                    continue
            if werte:
                enums[f"{gruppe.get('id')}/{eintrag.get('id')}"] = werte
    return enums


def ebenen_lesen(xml: str) -> dict[str, str]:
    """Ebenenbezeichnungen als ``fcttyp/ebene`` -> Text."""
    wurzel = _wurzel(xml)
    if wurzel is None:
        return {}
    ebenen: dict[str, str] = {}
    for art in wurzel:
        for ebene in art:
            if text := (ebene.text or "").strip():
                ebenen[f"{art.get('id')}/{ebene.get('id')}"] = text
    return ebenen


def stoerungen_lesen(xml: str) -> dict[int, str]:
    """Störungstexte als Code -> Text."""
    wurzel = _wurzel(xml)
    if wurzel is None:
        return {}
    texte: dict[int, str] = {}
    for eintrag in wurzel:
        text = (eintrag.get("text") or "").strip()
        if not text:
            continue
        try:
            texte[int(eintrag.get("code"))] = text
        except (TypeError, ValueError):
            continue
    return texte
