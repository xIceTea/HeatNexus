"""Switch platform for the Windhager integration (Betreiberebene)."""

from __future__ import annotations

import time

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import VORMERK_MAX_ALTER_S
from .entity import WindhagerEntity, async_setup_entities
from .helpers import get_oid_raw, parse_value

# Der Coordinator holt jeden Wert gebündelt, und die Anfragen an die Anlage
# begrenzt der Client über seine eigene Warteschlange. Eine zweite Bremse in
# Home Assistant würde nur den Abruf verzögern, den es gar nicht gibt.
PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Windhager switches from a config entry."""
    async_setup_entities(hass, entry, async_add_entities, {"switch": WindhagerSwitch})


class WindhagerSwitch(WindhagerEntity, SwitchEntity):
    """Schreibbarer Datenpunkt mit zwei Zuständen.

    Ab Werk 1 und 0; `ein_wert` und `aus_wert` in der Beschreibung setzen andere Werte.
    Mit `zustand_oid` kommt der Zustand von dort, geschrieben wird die eigene Adresse.
    """

    _require_value_for_available = False

    def __init__(self, coordinator, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        # Jede Beschreibung führt die Felder, meist leer – deshalb `or`
        # statt eines Vorgabewerts im Zugriff.
        self._ein = str(device_info.get("ein_wert") or "1")
        self._aus = str(device_info.get("aus_wert") or "0")
        self._zustand_oid = device_info.get("zustand_oid")
        self._zustand_aus = {int(w) for w in device_info.get("zustand_aus") or ()}
        self._geschrieben_um: float | None = None

    async def async_added_to_hass(self) -> None:
        """Die Zustandsadresse mit abrufen, auch wenn ihr eigener Sensor abgeschaltet ist."""
        await super().async_added_to_hass()
        if self._zustand_oid:
            self.coordinator.client.register_poll_oid(self._zustand_oid)

    async def async_will_remove_from_hass(self) -> None:
        if self._zustand_oid:
            self.coordinator.client.unregister_poll_oid(self._zustand_oid)
        await super().async_will_remove_from_hass()

    @property
    def _gewaehlt(self) -> bool | None:
        """Was an der eigenen Adresse steht, gelesen oder eben geschrieben."""
        value = self.int_value
        if value is None:
            return None
        if self._ein == "1" and self._aus == "0":
            return value != 0
        return str(value) == self._ein

    @property
    def is_on(self) -> bool | None:
        gewaehlt = self._gewaehlt
        if not self._zustand_oid:
            return gewaehlt
        zustand = parse_value(get_oid_raw(self.coordinator, self._zustand_oid), int)
        if zustand is None:
            return gewaehlt
        laeuft = zustand not in self._zustand_aus
        # Bis die Betriebsart dem Schreiben folgt, gilt der geschriebene Wert.
        geschrieben = self._geschrieben_um
        if geschrieben is not None and time.monotonic() - geschrieben < VORMERK_MAX_ALTER_S:
            return laeuft if gewaehlt is None else gewaehlt
        return laeuft

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_write(self._ein)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_write(self._aus)

    async def _async_write(self, value: str) -> None:
        self._geschrieben_um = time.monotonic()
        await super()._async_write(value)

    def _nachfassen(self, erwartet: str | None = None) -> None:
        """Neben der eigenen Adresse die Zustandsadresse lesen, bis sie sich bewegt."""
        if not self._zustand_oid or not self.hass:
            super()._nachfassen(erwartet)
            return
        bekannt = (self.coordinator.data or {}).get("oids", {})
        self.coordinator.nachfassen(
            [self._oid, self._zustand_oid],
            vorher={self._zustand_oid: bekannt.get(self._zustand_oid)},
        )
