"""Geräte finden und verknüpfen, über die Fassungen von Home Assistant hinweg.

Ab 2026.9 ist eine Gerätekennung nur innerhalb eines Konfigurationseintrags
eindeutig. Gesucht wird deshalb je Eintrag, verknüpft über die Geräte-ID statt
über die Kennung. Ältere Fassungen kennen beides nicht.
"""

from __future__ import annotations

import inspect
from typing import Any

from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

# Die neue Verknüpfung erkennt man an der Schnittstelle, nicht an der Fassungsnummer.
VERKNUEPFUNG_PER_ID = (
    "via_device_id" in inspect.signature(dr.DeviceRegistry.async_get_or_create).parameters
)


def geraet_suchen(registry: Any, kennung: str, entry_id: str) -> Any:
    """Das Gerät des Eintrags mit dieser Kennung, oder `None`."""
    suche = getattr(registry, "async_get_device_by_identifier", None)
    if suche is not None:
        return suche((DOMAIN, kennung), entry_id)
    return registry.async_get_device(identifiers={(DOMAIN, kennung)})


def uebergeordnet(hass: Any, kennung: str, entry_id: str) -> dict[str, Any]:
    """Der Verweis auf das übergeordnete Gerät, als Feld für die Geräteangaben.

    Fehlt das übergeordnete Gerät, entfällt der Verweis.
    """
    if not VERKNUEPFUNG_PER_ID or hass is None:
        return {"via_device": (DOMAIN, kennung)}
    geraet = geraet_suchen(dr.async_get(hass), kennung, entry_id)
    return {"via_device_id": geraet.id} if geraet is not None else {}
