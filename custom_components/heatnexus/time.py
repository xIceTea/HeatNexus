"""Time platform for the Windhager integration (Freigabe-/Startzeiten)."""

from __future__ import annotations

from datetime import time as dt_time
import logging

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DOMAIN
from .entity import WindhagerEntity

_LOGGER = logging.getLogger(__name__)


def parse_time(value: str | None) -> dt_time | None:
    """Parse 'HH:MM' or 'HH:MM:SS' into a time object."""
    if not value:
        return None
    parts = value.strip().split(":")
    try:
        if len(parts) >= 2:
            return dt_time(int(parts[0]), int(parts[1]))
    except (ValueError, TypeError):
        pass
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Windhager time entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        WindhagerTime(coordinator, device_info)
        for device_info in coordinator.data.get("devices", [])
        if device_info.get("type") == "time"
    ]
    async_add_entities(entities)


class WindhagerTime(WindhagerEntity, TimeEntity):
    """Writable time datapoint (e.g. Zuführung Freigabezeit)."""

    _require_value_for_available = False

    @property
    def native_value(self) -> dt_time | None:
        value = parse_time(self.raw_value)
        if value is None and self.raw_value is not None:
            _LOGGER.debug(
                "Unparseable time value %r for %s (%s)",
                self.raw_value,
                self.name,
                self._oid,
            )
        return value

    async def async_set_value(self, value: dt_time) -> None:
        await self._async_write(value.strftime("%H:%M"))
