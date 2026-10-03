"""Geräte finden und verknüpfen, über die Fassungen von Home Assistant hinweg.

Ab 2026.9 ist eine Gerätekennung nur innerhalb eines Konfigurationseintrags
eindeutig. Gesucht wird deshalb je Eintrag, verknüpft über die Geräte-ID statt
über die Kennung. Ältere Fassungen kennen beides nicht.
"""

from __future__ import annotations

import inspect
from typing import Any

import attr
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

# Die neue Verknüpfung erkennt man an der Schnittstelle, nicht an der Fassungsnummer.
VERKNUEPFUNG_PER_ID = (
    "via_device_id" in inspect.signature(dr.DeviceRegistry.async_get_or_create).parameters
)

# Ab 2026.9 gehört ein Gerät genau einem Untereintrag; verschoben wird dann über das Ziel.
VERSCHIEBEN_PER_ZIEL = (
    "new_config_subentry_id" in inspect.signature(dr.DeviceRegistry.async_update_device).parameters
)

# Ein Gerät mit eigenem `config_subentry_id` gehört genau einem Eintrag; die Sammelangabe ist abgekündigt.
EIN_EINTRAG_JE_GERAET = "config_subentry_id" in attr.fields_dict(dr.DeviceEntry)


def untereintraege(geraet: Any, entry_id: str) -> set[str | None]:
    """Die Untereinträge des Eintrags, denen das Gerät angehört; `None` steht für den Eintrag selbst."""
    if EIN_EINTRAG_JE_GERAET:
        return {geraet.config_subentry_id} if geraet.config_entry_id == entry_id else set()
    return geraet.config_entries_subentries.get(entry_id) or set()


def in_untereintrag_verschieben(registry: Any, geraet: Any, entry_id: str, sub_id: str) -> None:
    """Ein Gerät des Eintrags in einen seiner Untereinträge verschieben."""
    if VERSCHIEBEN_PER_ZIEL:
        registry.async_update_device(
            geraet.id, new_config_entry_id=entry_id, new_config_subentry_id=sub_id
        )
        return
    # Erst dazu, dann weg: Ein Gerät ohne Eintrag entfernt Home Assistant.
    registry.async_get_or_create(
        config_entry_id=entry_id, config_subentry_id=sub_id, identifiers=set(geraet.identifiers)
    )
    registry.async_update_device(
        geraet.id, remove_config_entry_id=entry_id, remove_config_subentry_id=None
    )


def geraet_suchen(registry: Any, kennung: str, entry_id: str | None) -> Any:
    """Das Gerät des Eintrags mit dieser Kennung, oder `None`; ohne Eintrag über die Kennung allein.

    Die Suche über die Kennung allein ist ab 2026.9 abgekündigt; ohne Eintrag geht sie das Register durch.
    """
    suche = getattr(registry, "async_get_device_by_identifier", None)
    if suche is None:
        return registry.async_get_device(identifiers={(DOMAIN, kennung)})
    if entry_id:
        return suche((DOMAIN, kennung), entry_id)
    return next((g for g in registry.devices.values() if (DOMAIN, kennung) in g.identifiers), None)


def kurzname(name: str | None) -> str:
    """Name ohne das vorangestellte Anlagenkürzel."""
    return (name or "").split(" · ")[-1].strip()


def geraetename(hass: Any, kennung: str, entry_id: str | None, rueckfall: str) -> str:
    """Name des Geräts wie in der Geräteliste, ohne Anlagenkürzel; ohne Gerät der Rückfall."""
    geraet = geraet_suchen(dr.async_get(hass), kennung, entry_id)
    name = (geraet.name_by_user or geraet.name) if geraet is not None else None
    return kurzname(name) if name else rueckfall


def uebergeordnet(hass: Any, kennung: str, entry_id: str) -> dict[str, Any]:
    """Der Verweis auf das übergeordnete Gerät, als Feld für die Geräteangaben.

    Fehlt das übergeordnete Gerät, entfällt der Verweis.
    """
    if not VERKNUEPFUNG_PER_ID or hass is None:
        return {"via_device": (DOMAIN, kennung)}
    geraet = geraet_suchen(dr.async_get(hass), kennung, entry_id)
    return {"via_device_id": geraet.id} if geraet is not None else {}
