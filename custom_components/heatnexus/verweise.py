"""Gespeicherte Verweise auf Entitäten folgen, wenn deren ID umbenannt wird.

Automatik, Wärmequellen und die gewählte Außentemperatur halten Entitäts-IDs
fest. Ohne Nachziehen zeigten sie nach einer Umbenennung ins Leere.
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from . import waermequelle
from .automatik.verwaltung import verwaltung_holen
from .const import CONF_AUSSENTEMPERATUR, DOMAIN

_LOGGER = logging.getLogger(__name__)

AUTOMATIK_FELDER = ("wetter", "pv", "pv_ist", "aussen")
AUTOMATIK_LISTEN = ("raeume", "personen", "fenster", "vorrang")
BEDINGUNG_FELDER = ("quelle", "gegen")
_HORCHER = "verweise_horcher"


def automatik_umschreiben(konfig: Mapping[str, Any], alt: str, neu: str) -> dict[str, Any]:
    """Die geänderten Felder einer Automatik; leer, wenn sie `alt` nicht nennt."""
    aenderung: dict[str, Any] = {feld: neu for feld in AUTOMATIK_FELDER if konfig.get(feld) == alt}
    for feld in AUTOMATIK_LISTEN:
        liste = list(konfig.get(feld) or [])
        if alt in liste:
            aenderung[feld] = [neu if eintrag == alt else eintrag for eintrag in liste]
    return aenderung


def bedingung_umschreiben(regel: Mapping[str, Any], alt: str, neu: str) -> dict[str, Any] | None:
    """Die Bedingung mit der neuen ID; `None`, wenn sie `alt` nicht nennt."""
    if not any(regel.get(feld) == alt for feld in BEDINGUNG_FELDER):
        return None
    return {
        schluessel: neu if schluessel in BEDINGUNG_FELDER and wert == alt else wert
        for schluessel, wert in regel.items()
    }


@callback
def verweise_verfolgen(hass: HomeAssistant) -> None:
    """Einmal je Instanz am Entitätsregister horchen."""
    daten = hass.data.setdefault(DOMAIN, {})
    if _HORCHER in daten:
        return

    async def umbenannt(ereignis: Event) -> None:
        if ereignis.data.get("action") != "update":
            return
        alt, neu = ereignis.data.get("old_entity_id"), ereignis.data.get("entity_id")
        if alt and neu and alt != neu:
            await verweise_umschreiben(hass, alt, neu)

    daten[_HORCHER] = hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, umbenannt)


async def verweise_umschreiben(hass: HomeAssistant, alt: str, neu: str) -> None:
    """Jeden gespeicherten Verweis auf `alt` auf `neu` umstellen."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if (entry.options or {}).get(CONF_AUSSENTEMPERATUR) == alt:
            hass.config_entries.async_update_entry(
                entry, options={**entry.options, CONF_AUSSENTEMPERATUR: neu}
            )
        for sub in waermequelle.subeintraege(entry):
            regel = (sub.data or {}).get("bedingung")
            if isinstance(regel, Mapping) and (neue := bedingung_umschreiben(regel, alt, neu)):
                hass.config_entries.async_update_subentry(
                    entry, sub, data={**sub.data, "bedingung": neue}
                )
    verwaltung = verwaltung_holen(hass)
    await verwaltung.laden()
    for device_id, konfig in verwaltung.konfigurationen():
        if not (aenderung := automatik_umschreiben(konfig, alt, neu)):
            continue
        # Eine ungültige Automatik hält die übrigen nicht auf.
        try:
            await verwaltung.einstellen(device_id, aenderung)
        except ValueError as fehler:
            _LOGGER.warning("Automatik %s folgt %s nicht: %s", device_id, neu, fehler)
            continue
        _LOGGER.debug("Automatik %s folgt %s -> %s", device_id, alt, neu)
