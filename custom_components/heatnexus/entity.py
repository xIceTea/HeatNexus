"""Shared base entity for the Windhager integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENUMS, SIGNAL_NEUE_ENTITAETEN
from .device_db import get_enum
from .helpers import parse_value

CATEGORY_MAP = {
    "diagnostic": EntityCategory.DIAGNOSTIC,
    "config": EntityCategory.CONFIG,
}


@callback
def async_setup_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    klassen: dict[str, type],
) -> None:
    """Entitäten einer Plattform anlegen – auch später nachgemeldete.

    Beim Einrichten sind zunächst nur die Kerndatenpunkte bekannt; der
    vollständige Abzug der Anlage läuft im Hintergrund weiter. Sobald er
    fertig ist, werden die zusätzlich gefundenen Entitäten nachgereicht.
    """
    coordinators = hass.data[DOMAIN][entry.entry_id]["coordinators"]
    bekannt: set[str] = set()

    @callback
    def _anlegen() -> None:
        neu = []
        for coordinator in coordinators.values():
            for beschreibung in (coordinator.data or {}).get("devices", []):
                klasse = klassen.get(beschreibung.get("type"))
                kennung = beschreibung.get("id")
                if klasse is None or not kennung or kennung in bekannt:
                    continue
                bekannt.add(kennung)
                neu.append(klasse(coordinator, beschreibung))
        if neu:
            async_add_entities(neu)

    _anlegen()
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEUE_ENTITAETEN.format(entry.entry_id), _anlegen)
    )


def geraet_info(coordinator: Any, beschreibung: dict) -> DeviceInfo:
    """Gerätezuordnung einer Entität.

    Aufbau: Heizungsanlage (Konfigurationseintrag) → Steuerung (Adresse) →
    Funktion (Kessel, Heizkreis, Puffer …), an der die Entität hängt.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, beschreibung.get("device_id"))},
        name=beschreibung.get("device_name"),
        manufacturer="Windhager",
        model=beschreibung.get("device_name"),
        via_device=(DOMAIN, f"{coordinator.entry.entry_id}_{coordinator.host}"),
    )


class WindhagerEntity(CoordinatorEntity):
    """Base entity bound to one OID descriptor from the client."""

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator)
        self._descriptor = device_info
        self._oid = device_info.get("oid")
        self._attr_unique_id = device_info.get("id")
        self._attr_name = device_info.get("name")
        if device_info.get("icon"):
            self._attr_icon = device_info["icon"]
        if device_info.get("enabled_default") is False:
            self._attr_entity_registry_enabled_default = False
        category = device_info.get("category")
        if category in CATEGORY_MAP:
            self._attr_entity_category = CATEGORY_MAP[category]
        self._attr_device_info = geraet_info(coordinator, device_info)

    # Zeitprogramme werden über den object-Endpunkt gelesen, nicht über das
    # OID-Polling – solche Entities setzen das Flag auf False.
    _register_poll_oid = True

    # ------------------------------------------------------------------
    async def async_added_to_hass(self) -> None:
        """Beim Aktivieren der Entity ihre OID zum Polling anmelden.

        HA fügt nur tatsächlich aktivierte Entities hinzu – deaktivierte
        (z.B. Service-Datenpunkte) registrieren sich daher nicht und werden
        nicht gepollt. Aktiviert der Nutzer eine Service-Entity, wird ihre
        OID hier registriert und ab dem nächsten Poll mit abgefragt.
        """
        await super().async_added_to_hass()
        if self._register_poll_oid and self._oid:
            self.coordinator.client.register_poll_oid(self._oid)

    async def async_will_remove_from_hass(self) -> None:
        """Beim Entfernen/Deaktivieren die OID wieder abmelden."""
        if self._register_poll_oid and self._oid:
            self.coordinator.client.unregister_poll_oid(self._oid)
        await super().async_will_remove_from_hass()

    @property
    def raw_value(self) -> str | None:
        """Raw string value of this entity's OID."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("oids", {}).get(self._oid)

    @property
    def float_value(self) -> float | None:
        return parse_value(self.raw_value, float, self._oid)

    @property
    def int_value(self) -> int | None:
        return parse_value(self.raw_value, int, self._oid)

    @property
    def enum_map(self) -> dict[int, str]:
        key = self._descriptor.get("enum") or ""
        return ENUMS.get(key) or get_enum(key) or {}

    # Writable platforms set this to False so write-only datapoints
    # (readable only with 409/Conflict, e.g. 39/95) stay operable.
    _require_value_for_available = True

    @property
    def available(self) -> bool:
        if not self._require_value_for_available:
            return super().available
        return super().available and self.raw_value is not None

    async def _async_write(self, value: str) -> None:
        """Write a value to this entity's OID and refresh."""
        await self.coordinator.client.update(self._oid, value)
        await self.coordinator.async_request_refresh()
