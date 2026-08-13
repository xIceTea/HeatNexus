"""Button platform for the Windhager integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .entity import WindhagerEntity, async_setup_entities

# Der Coordinator holt jeden Wert gebündelt, und die Anfragen an die Anlage
# begrenzt der Client über seine eigene Warteschlange. Eine zweite Bremse in
# Home Assistant würde nur den Abruf verzögern, den es gar nicht gibt.
PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Windhager buttons from a config entry."""
    async_setup_entities(hass, entry, async_add_entities, {"button": WindhagerButton})


class WindhagerButton(WindhagerEntity, ButtonEntity):
    """Button that writes a fixed value to a datapoint when pressed.

    Used e.g. for "Serviceausbrand starten" (writes 6 to 9/75) and
    "Sonden zurücksetzen". For destructive actions add a confirmation in
    the dashboard:

        type: button
        entity: button.purowin_serviceausbrand_starten
        confirmation:
          text: Serviceausbrand wirklich starten? Der Vorgang dauert ca. 1 Stunde
                und kann nicht abgebrochen werden.
    """

    _require_value_for_available = False

    def __init__(self, coordinator, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        self._press_value = device_info.get("press_value", "1")

    async def async_press(self) -> None:
        _LOGGER.warning(
            "Button %s pressed, writing %s to %s",
            self.name,
            self._press_value,
            self._oid,
        )
        await self._async_write(self._press_value)
