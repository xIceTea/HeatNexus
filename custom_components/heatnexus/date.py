"""Date platform for the Windhager integration (z.B. Urlaubsprogramm)."""

from __future__ import annotations

from datetime import date as dt_date
from datetime import datetime
import logging

from homeassistant.components.date import DateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .entity import WindhagerEntity, async_setup_entities

_LOGGER = logging.getLogger(__name__)


def parse_date(value: str | None) -> dt_date | None:
    """Parse the Windhager date format 'TT.MM.JJJJ'."""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%d.%m.%Y").date()
    except (ValueError, TypeError):
        return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Windhager date entities from a config entry."""
    async_setup_entities(hass, entry, async_add_entities, {"date": WindhagerDate})


class WindhagerDate(WindhagerEntity, DateEntity):
    """Writable date datapoint, e.g. 'Urlaubsprogramm bis Datum' (3/78)."""

    _require_value_for_available = False

    @property
    def native_value(self) -> dt_date | None:
        value = parse_date(self.raw_value)
        if value is None and self.raw_value not in (None, "-"):
            _LOGGER.debug("Unparseable date %r for %s (%s)", self.raw_value, self.name, self._oid)
        return value

    async def async_set_value(self, value: dt_date) -> None:
        await self._async_write(value.strftime("%d.%m.%Y"))
