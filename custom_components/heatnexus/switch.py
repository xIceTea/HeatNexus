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
    """Schreibbarer Datenpunkt mit zwei Zuständen.

    Ab Werk 1 und 0. Eine Betriebswahl kennt andere Werte: Der Kaminkehrer
    steht auf 3 und kehrt mit 1 in den normalen Betrieb zurück.
    """

    _require_value_for_available = False

    def __init__(self, coordinator, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        # Jede Beschreibung führt die Felder, meist leer – deshalb `or`
        # statt eines Vorgabewerts im Zugriff.
        self._ein = str(device_info.get("ein_wert") or "1")
        self._aus = str(device_info.get("aus_wert") or "0")

    @property
    def is_on(self) -> bool | None:
        value = self.int_value
        if value is None:
            return None
        if self._ein == "1" and self._aus == "0":
            return value != 0
        return str(value) == self._ein

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_write(self._ein)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_write(self._aus)
