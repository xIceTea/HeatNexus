"""Binary sensor platform for the Windhager integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .entity import MeldungsQuelle, WindhagerEntity, async_setup_entities

# Der Coordinator holt jeden Wert gebündelt, und die Anfragen an die Anlage
# begrenzt der Client über seine eigene Warteschlange. Eine zweite Bremse in
# Home Assistant würde nur den Abruf verzögern, den es gar nicht gibt.
PARALLEL_UPDATES = 0

DEVICE_CLASS_MAP = {
    "problem": BinarySensorDeviceClass.PROBLEM,
    "running": BinarySensorDeviceClass.RUNNING,
    "power": BinarySensorDeviceClass.POWER,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Windhager binary sensors from a config entry."""
    async_setup_entities(
        hass,
        entry,
        async_add_entities,
        {
            "binary_sensor": WindhagerBinarySensor,
            "stoerung": WindhagerStoerungBinarySensor,
        },
    )


class WindhagerBinarySensor(WindhagerEntity, BinarySensorEntity):
    """Binary sensor: on when the numeric value is non-zero.

    Pump outputs report their speed (e.g. "100") instead of 1, so any
    value != 0 counts as on.
    """

    def __init__(self, coordinator, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        device_class = device_info.get("device_class")
        if device_class in DEVICE_CLASS_MAP:
            self._attr_device_class = DEVICE_CLASS_MAP[device_class]

    @property
    def is_on(self) -> bool | None:
        value = self.int_value
        if value is None:
            return None
        return value != 0


class WindhagerStoerungBinarySensor(MeldungsQuelle, WindhagerEntity, BinarySensorEntity):
    """Ein an: an diesem Anlagenteil steht eine Störung an.

    Dieselbe Quelle wie der Klartext-Sensor (``FExxmsg``), nur als Ja/Nein mit
    der Geräteklasse ``problem``.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool | None:
        if self._raw is None:
            return None
        return bool(self._meldungen)

    @property
    def extra_state_attributes(self):
        if self._raw is None:
            return None
        msgs = self._meldungen
        # Nur, was eine Meldung braucht. Codes und Rohwert führt der
        # Klartext-Sensor desselben Anlagenteils.
        return {
            "anzahl": len(msgs),
            "stoerungstext": " | ".join(m["text"] for m in msgs),
        }
