"""Select platform for the Windhager integration (Betreiberebene)."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .entity import WindhagerEntity, async_setup_entities

# Der Coordinator holt jeden Wert gebündelt, und die Anfragen an die Anlage
# begrenzt der Client über seine eigene Warteschlange. Eine zweite Bremse in
# Home Assistant würde nur den Abruf verzögern, den es gar nicht gibt.
PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Windhager selects from a config entry."""
    async_setup_entities(hass, entry, async_add_entities, {"select": WindhagerSelect})


class WindhagerSelect(WindhagerEntity, SelectEntity):
    """Writable select mapped onto a Windhager enum datapoint.

    Enums can have gaps (e.g. Betriebswahl Puffer 20/15 has no value 5),
    therefore the mapping is dict based, never list-index based.
    """

    _require_value_for_available = False

    def __init__(self, coordinator, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        # value -> label and label -> value lookups
        self._value_to_label = dict(self.enum_map)
        allowed = device_info.get("allowed")
        if allowed:
            # restrict to values the device actually supports; unknown values
            # get a generic label so they are still selectable
            self._value_to_label = {v: self.enum_map.get(v, f"Wert {v}") for v in allowed}
        self._label_to_value: dict[str, int] = {}
        for value, label in self.enum_map.items():
            # first value wins if labels are duplicated
            self._label_to_value.setdefault(label, value)
        self._attr_options = [self._value_to_label[v] for v in sorted(self._value_to_label)]

    @property
    def current_option(self) -> str | None:
        raw = self.int_value
        if raw is None:
            return None
        label = self._value_to_label.get(raw)
        if label is None:
            _LOGGER.debug("Unknown enum value %s for %s (%s)", raw, self.name, self._oid)
        return label

    async def async_select_option(self, option: str) -> None:
        value = self._label_to_value.get(option)
        if value is None:
            _LOGGER.error("Unknown option %s for %s", option, self.name)
            return
        await self._async_write(str(value))
