"""Marken aus Home Assistant als eigene Karten der Oberfläche.

Auswahl, Benennung und Gruppierung erledigt Home Assistants Markenverwaltung;
hier entsteht daraus nur die Kartenbeschreibung.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr

from ..const import MARKEN_MAX_KARTEN, MARKEN_MAX_ZEILEN
from ..rechte import darf_lesen
from ..symbole import symbol_fuer_wert


def _zeile(hass: HomeAssistant, eintrag: er.RegistryEntry) -> dict[str, str]:
    """Name und Symbol einer fremden Entität; den Wert holt die Oberfläche.

    Sie bindet ihn im Browser an `hass.states` wie jede andere Statuszeile.
    """
    zustand = hass.states.get(eintrag.entity_id)
    attribute = dict(zustand.attributes) if zustand else {}
    name = (
        attribute.get("friendly_name") or eintrag.name or eintrag.original_name or eintrag.entity_id
    )
    symbol = attribute.get("icon") or eintrag.icon or symbol_fuer_wert({"name": name})
    return {"entity": eintrag.entity_id, "titel": name, "symbol": symbol}


def karten(
    hass: HomeAssistant, freigegeben: list[str], benutzer: Any = None
) -> list[dict[str, Any]]:
    """Je freigegebener Marke eine Karte, Zeilen nach Anzeigenamen sortiert."""
    marken = lr.async_get(hass)
    registry = er.async_get(hass)
    gebaut: list[dict[str, Any]] = []
    for kennung in freigegeben:
        marke = marken.async_get_label(kennung)
        if marke is None:
            continue
        zeilen = [
            _zeile(hass, eintrag)
            for eintrag in er.async_entries_for_label(registry, kennung)
            if darf_lesen(benutzer, eintrag.entity_id)
        ]
        zeilen.sort(key=lambda z: z["titel"].casefold())
        if not zeilen:
            continue
        gebaut.append(
            {"id": f"marke:{kennung}", "titel": marke.name, "zeilen": zeilen[:MARKEN_MAX_ZEILEN]}
        )
    return gebaut[:MARKEN_MAX_KARTEN]


def zeilen(
    hass: HomeAssistant, freigegeben: list[str], benutzer: Any = None
) -> list[dict[str, str]]:
    """Die Werte dieser Labels als einzelne Zeilen, ohne eigene Karte.

    Für Labels, die einer vorhandenen Gruppe zugeordnet sind. Jede Adresse
    erscheint einmal, auch wenn sie mehrere der Labels trägt.
    """
    registry = er.async_get(hass)
    gesehen: set[str] = set()
    gesammelt: list[dict[str, str]] = []
    for kennung in freigegeben:
        for eintrag in er.async_entries_for_label(registry, kennung):
            if eintrag.entity_id in gesehen or not darf_lesen(benutzer, eintrag.entity_id):
                continue
            gesehen.add(eintrag.entity_id)
            gesammelt.append(_zeile(hass, eintrag))
    gesammelt.sort(key=lambda z: z["titel"].casefold())
    return gesammelt[:MARKEN_MAX_ZEILEN]
