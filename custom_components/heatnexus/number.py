"""Number platform for the Windhager integration (Betreiberebene)."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .entity import WindhagerEntity, async_setup_entities

# Der Coordinator holt jeden Wert gebündelt, und die Anfragen an die Anlage
# begrenzt der Client über seine eigene Warteschlange. Eine zweite Bremse in
# Home Assistant würde nur den Abruf verzögern, den es gar nicht gibt.
PARALLEL_UPDATES = 0

# Die Einheitentabelle liefert Geräteklassen für alle Plattformen; das
# Zahlenfeld kennt davon weniger als der Sensor (keine Dauer, keine Energie).
DEVICE_CLASSES = {klasse.value for klasse in NumberDeviceClass}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Windhager numbers from a config entry."""
    async_setup_entities(hass, entry, async_add_entities, {"number": WindhagerNumber})


class WindhagerNumber(WindhagerEntity, NumberEntity):
    """Writable number with enforced min/max/step from the Betreiberebene."""

    _require_value_for_available = False

    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        # Der Deskriptor trägt die Schlüssel immer – ohne Angabe der Anlage
        # aber mit dem Wert None. `float(None)` würde die Entity beim Anlegen
        # abbrechen und die ganze Plattform mitreißen; deshalb `or`.
        self._attr_native_min_value = float(device_info.get("min") or 0)
        self._attr_native_max_value = float(device_info.get("max") or 100)
        self._attr_native_step = float(device_info.get("step") or 1)
        self._attr_native_unit_of_measurement = device_info.get("unit")
        device_class = device_info.get("device_class")
        if device_class in DEVICE_CLASSES:
            self._attr_device_class = NumberDeviceClass(device_class)

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
