"""Registrierte Entitäten ohne Datenpunkt finden, melden und entfernen.

Eine verwaiste Entität entsteht, wenn die Anlage einen Datenpunkt nicht mehr
liefert oder eine neue Fassung ihn nicht mehr anlegt. Stillgelegt wird sie
sofort, entfernt erst auf Ansage: Löschen kostet Name, Bereich und Verlauf.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCHLUESSEL = "verwaiste_entitaeten"
HINWEIS = SCHLUESSEL + "_{entry_id}"


@callback
def bekannte_kennungen(coordinators: dict) -> dict[str, bool]:
    """Kennung -> ob die Erkennung sie ab Werk einschaltet."""
    return {
        beschreibung.get("id"): beschreibung.get("enabled_default", True)
        for coordinator in coordinators.values()
        for beschreibung in (coordinator.data or {}).get("devices", [])
    }


@callback
def abzug_steht(coordinators: dict) -> bool:
    """Ob der Bestand aussagekräftig ist.

    Vor dem Vollabzug ist die Liste unvollständig, und ein Abruf ohne Daten
    heißt nicht, dass es keine Datenpunkte gibt – er kann in die
    Zeitüberschreitung gelaufen sein.
    """
    return all(
        getattr(coordinator.client, "_vollstaendig", False)
        and (coordinator.data or {}).get("devices")
        for coordinator in coordinators.values()
    )


@callback
def finden(hass: HomeAssistant, entry: ConfigEntry, coordinators: dict) -> list[er.RegistryEntry]:
    """Alle Einträge des Eintrags, deren Kennung im Bestand fehlt."""
    if not coordinators or not abzug_steht(coordinators):
        return []
    bekannt = bekannte_kennungen(coordinators)
    registry = er.async_get(hass)
    return [
        eintrag
        for eintrag in er.async_entries_for_config_entry(registry, entry.entry_id)
        if eintrag.unique_id not in bekannt
    ]


@callback
def hinweis_pflegen(hass: HomeAssistant, entry: ConfigEntry, anzahl: int) -> None:
    """Den Reparatureintrag setzen oder zurücknehmen."""
    kennung = HINWEIS.format(entry_id=entry.entry_id)
    if not anzahl:
        ir.async_delete_issue(hass, DOMAIN, kennung)
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        kennung,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=SCHLUESSEL,
        translation_placeholders={"anzahl": str(anzahl)},
        data={"entry_id": entry.entry_id},
    )


@callback
def entfernen(hass: HomeAssistant, entry: ConfigEntry, coordinators: dict) -> int:
    """Die Verwaiste löschen und den Hinweis zurücknehmen.

    Der Bestand wird dabei neu ermittelt: Zwischen Hinweis und Klick können
    Datenpunkte zurückgekommen sein.
    """
    registry = er.async_get(hass)
    entfernt = 0
    for eintrag in finden(hass, entry, coordinators):
        registry.async_remove(eintrag.entity_id)
        entfernt += 1
    hinweis_pflegen(hass, entry, 0)
    if entfernt:
        _LOGGER.info("%d Entitäten ohne Datenpunkt entfernt", entfernt)
    return entfernt
