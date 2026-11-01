"""Abweichung der Uhr der Steuerung von Home Assistant, als Sensor am Gerät „Steuerung“.

Eine falsch gehende Uhr verschiebt Zeitprogramme und Meldungszeiten, etwa nach einer Zeitumstellung.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN
from ..entity import steuerung_kennung


def kennung(coordinator: Any) -> str:
    """Kennung des Sensors „Uhrabweichung“ einer Steuerung."""
    return f"{steuerung_kennung(coordinator)}-uhrabweichung"


def kennungen(coordinators: dict) -> set[str]:
    """Die Sensoren der Steuerungen, die ihre Uhrzeit melden."""
    return {
        kennung(coordinator)
        for coordinator in coordinators.values()
        if (coordinator.data or {}).get("systemzeit") is not None
    }


class UhrabweichungSensor(CoordinatorEntity, SensorEntity):
    """Wie weit die Uhr der Steuerung vor (positiv) oder nach (negativ) Home Assistant geht."""

    _attr_has_entity_name = True
    _attr_translation_key = "uhrabweichung"
    _attr_icon = "mdi:clock-alert-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _unrecorded_attributes = frozenset({"uhrzeit"})

    def __init__(self, coordinator: Any) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = kennung(coordinator)
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, steuerung_kennung(coordinator))})

    @property
    def _zeit(self) -> dict | None:
        return (self.coordinator.data or {}).get("systemzeit")

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._zeit is not None

    @property
    def native_value(self) -> int | None:
        return (self._zeit or {}).get("abweichung")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return {"uhrzeit": self._zeit["uhrzeit"]} if self._zeit else None


def anmelden(hass: HomeAssistant, entry: Any, async_add_entities: Any) -> None:
    """Je Steuerung einen Sensor, sobald sie ihre Uhrzeit meldet."""
    bekannt: set[str] = set()

    @callback
    def _pruefen() -> None:
        neu = []
        for coordinator in entry.runtime_data["coordinators"].values():
            if (coordinator.data or {}).get("systemzeit") is None:
                continue
            if (eigene := kennung(coordinator)) not in bekannt:
                bekannt.add(eigene)
                neu.append(UhrabweichungSensor(coordinator))
        if neu:
            async_add_entities(neu)

    _pruefen()
    for coordinator in entry.runtime_data["coordinators"].values():
        entry.async_on_unload(coordinator.async_add_listener(_pruefen))
