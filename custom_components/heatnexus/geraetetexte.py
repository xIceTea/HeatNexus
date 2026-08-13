"""Textwerk der Steuerung (`/res/xml/`).

Jede Steuerung führt die Klartexte ihrer Datenpunkte selbst mit, je Sprache
eine Datei. Diese Quelle geht mit der Fassung der Anlage mit, während die
mitgelieferte Datenbank nur Deutsch kennt.

Das Modul bleibt frei von Home Assistant und aiohttp: Der Abruf wird als
Rückruf hereingereicht, gelesen wird reiner Text.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
from xml.etree import ElementTree as ET

_LOGGER = logging.getLogger(__name__)

SPRACHEN = ("de", "en", "fr", "it")
SPRACHE_AUTO = "auto"


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


# Auf Deutsch trägt nur die Namensdatei etwas bei: Aufzählungs- und
# Ebenentexte stehen in der Datenbank, und die Störungstexte der Steuerung
# sind eine Teilmenge der gepflegten Tabelle.
_DATEIEN = {
    "namen": ("VarIdentTexte", namen_lesen),
    "enums": ("AufzaehlTexte", enums_lesen),
    "ebenen": ("EbenenTexte", ebenen_lesen),
    "stoerungen": ("ErrorTexte", stoerungen_lesen),
}
_NUR_NAMEN = ("namen",)


def sprache_aufloesen(gewaehlt: str | None, ha_sprache: str | None) -> str:
    """Die Sprache bestimmen, in der die Steuerung gelesen wird.

    Die Wahl des Nutzers hat Vorrang; ohne Wahl gilt die Sprache von Home
    Assistant. Was die Steuerung nicht führt, fällt auf Deutsch zurück.
    """
    if gewaehlt and gewaehlt != SPRACHE_AUTO:
        return gewaehlt if gewaehlt in SPRACHEN else "de"
    kurz = (ha_sprache or "").split("-")[0].lower()
    return kurz if kurz in SPRACHEN else "de"


async def laden(hole, sprache: str) -> Texte:
    """Textwerk der Steuerung lesen.

    ``hole`` liest eine Datei unterhalb von ``/res/`` und gibt ``None``
    zurück, wenn die Anlage sie nicht kennt. Fehlt eine Datei oder ist sie
    unlesbar, fehlt nur ihr Anteil – der Erkennungslauf geht weiter.
    """
    schluessel = _NUR_NAMEN if sprache == "de" else tuple(_DATEIEN)
    pfade = [f"xml/{_DATEIEN[s][0]}_{sprache}.xml" for s in schluessel]
    try:
        rohdaten = await asyncio.gather(*(hole(p) for p in pfade))
    except Exception as fehler:
        _LOGGER.debug("Textwerk der Steuerung nicht abrufbar: %s", fehler)
        return Texte()
    teile = {s: _DATEIEN[s][1](roh or "") for s, roh in zip(schluessel, rohdaten, strict=True)}
    return Texte(**teile)
