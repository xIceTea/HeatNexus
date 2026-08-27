"""Binary sensor platform for the Windhager integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from . import bedingung, waermequelle
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
    # Wärmequellen stehen in den Optionen, nicht im Abzug der Anlage. Ein
    # Neuladen nach geänderten Optionen legt sie neu an.
    async_add_entities(
        WaermequelleBinarySensor(coordinator, beschreibung)
        for coordinator in entry.runtime_data["coordinators"].values()
        for beschreibung in waermequelle.beschreibungen(entry, coordinator)
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


class WaermequelleBinarySensor(RestoreEntity, BinarySensorEntity):
    """Ein an: diese Wärmequelle liefert gerade Wärme.

    Sie hängt an keinem Datenpunkt der Anlage, sondern an fremden Entitäten
    in Home Assistant. Der vorige Zustand zählt mit: Bedingungen mit
    getrennter Ein- und Ausschaltschwelle brauchen ihn.
    """

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_name = "Wärmelieferung"

    def __init__(self, coordinator: Any, beschreibung: dict) -> None:
        self._regel = dict(beschreibung.get("bedingung") or {})
        self._beobachtet = bedingung.quellen(self._regel)
        self._attr_unique_id = beschreibung["id"]
        self._attr_device_info = waermequelle.geraet_info(coordinator, beschreibung)
        self._laeuft = False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (letzter := await self.async_get_last_state()) is not None:
            self._laeuft = letzter.state == "on"
        self.async_on_remove(
            async_track_state_change_event(self.hass, self._beobachtet, self._quelle_geaendert)
        )
        self._auswerten()

    @callback
    def _quelle_geaendert(self, event) -> None:
        self._auswerten()
        self.async_write_ha_state()

    @callback
    def _auswerten(self) -> None:
        """Die Bedingung mit den aktuellen Zuständen prüfen."""
        werte = {
            kennung: zustand.state if (zustand := self.hass.states.get(kennung)) else None
            for kennung in self._beobachtet
        }
        self._laeuft = bedingung.erfuellt(self._regel, werte, self._laeuft)

    @property
    def is_on(self) -> bool:
        return self._laeuft
