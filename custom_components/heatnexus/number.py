"""Number platform for the Windhager integration (Betreiberebene)."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DOMAIN
from .entity import WindhagerEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Windhager numbers from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        WindhagerNumber(coordinator, device_info)
        for device_info in coordinator.data.get("devices", [])
        if device_info.get("type") == "number"
    ]
    async_add_entities(entities)


class WindhagerNumber(WindhagerEntity, NumberEntity):
    """Writable number with enforced min/max/step from the Betreiberebene."""

    _require_value_for_available = False

    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        self._attr_native_min_value = float(device_info.get("min", 0))
        self._attr_native_max_value = float(device_info.get("max", 100))
        self._attr_native_step = float(device_info.get("step", 1))
        self._attr_native_unit_of_measurement = device_info.get("unit")
        if device_info.get("device_class") == "temperature":
            self._attr_device_class = NumberDeviceClass.TEMPERATURE

    @property
    def native_value(self) -> float | None:
        return self.float_value

    async def async_set_native_value(self, value: float) -> None:
        # Clamp defensively, HA UI should already enforce the limits
        value = max(self._attr_native_min_value, min(self._attr_native_max_value, value))
        if self._attr_native_step >= 1 and float(value).is_integer():
            payload = str(int(value))
        else:
            payload = f"{value:.1f}"
        await self._async_write(payload)
