"""Switch platform for the Windhager integration (Betreiberebene)."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .entity import WindhagerEntity, async_setup_entities

# Der Coordinator holt jeden Wert gebündelt, und die Anfragen an die Anlage
# begrenzt der Client über seine eigene Warteschlange. Eine zweite Bremse in
# Home Assistant würde nur den Abruf verzögern, den es gar nicht gibt.
PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Windhager switches from a config entry."""
    async_setup_entities(hass, entry, async_add_entities, {"switch": WindhagerSwitch})


class WindhagerSwitch(WindhagerEntity, SwitchEntity):
    """Writable Ja/Nein (1/0) datapoint."""

    _require_value_for_available = False

    @property
    def is_on(self) -> bool | None:
        value = self.int_value
        if value is None:
            return None
        return value != 0

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_write("1")

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_write("0")
