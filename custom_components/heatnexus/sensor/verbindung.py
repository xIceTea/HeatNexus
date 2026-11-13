"""Verbindung und Antwortzeit je Steuerung als diagnostische Sensoren."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN
from ..entity import steuerung_kennung
from ..verbindung import ZUSTAENDE

ENDUNGEN = ("verbindung", "antwortzeit")


def kennungen(coordinators: dict) -> list[str]:
    """Kennungen beider Sensoren aller Steuerungen."""
    return [
        f"{steuerung_kennung(coordinator)}-{endung}"
        for coordinator in coordinators.values()
        for endung in ENDUNGEN
    ]


class _VerbindungBasis(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: Any, endung: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{steuerung_kennung(coordinator)}-{endung}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, steuerung_kennung(coordinator))})
        self._auswerten()

    def _auswerten(self) -> None:
        # Nach dem Entladen fehlt der Lauf; der letzte Wert bleibt stehen.
        if (lauf := self.coordinator.verbindung) is not None:
            self._aus_lauf(lauf)

    def _aus_lauf(self, lauf: Any) -> None:
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        # Der Koordinator weckt nur bei geänderten Daten; die Bewertung ändert sich auch ohne sie.
        await super().async_added_to_hass()
        if (lauf := self.coordinator.verbindung) is not None:
            self.async_on_remove(lauf.abonnieren(self._bewertet))

    @callback
    def _bewertet(self) -> None:
        self._auswerten()
        self.async_write_ha_state()


class VerbindungSensor(_VerbindungBasis):
    """Wie gut die Steuerung antwortet, gemessen an ihrem eigenen Verlauf."""

    _attr_translation_key = "verbindung"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(ZUSTAENDE)
    # Kennzahlen, die sich bei jedem Abruf ändern; die Oberfläche liest sie aus dem Zustand.
    _unrecorded_attributes = frozenset(
        {"abruf_ms", "median_ms", "fehlerquote", "antworten", "noch_offen", "abrufe_mit_rest"}
    )

    def __init__(self, coordinator: Any) -> None:
        super().__init__(coordinator, "verbindung")

    def _aus_lauf(self, lauf: Any) -> None:
        self._attr_native_value = lauf.stand.zustand
        self._attr_extra_state_attributes = lauf.attribute()


class AntwortzeitSensor(_VerbindungBasis):
    """Median der Antwortzeit im letzten Abruf."""

    _attr_translation_key = "antwortzeit"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: Any) -> None:
        super().__init__(coordinator, "antwortzeit")

    def _aus_lauf(self, lauf: Any) -> None:
        wert = lauf.abruf_ms
        self._attr_native_value = None if wert is None else round(wert)


def anmelden(hass: HomeAssistant, entry: Any, async_add_entities: Any) -> None:
    """Je Steuerung beide Sensoren, gleich beim Einrichten."""
    async_add_entities(
        sensor(coordinator)
        for coordinator in entry.runtime_data["coordinators"].values()
        if coordinator.verbindung is not None
        for sensor in (VerbindungSensor, AntwortzeitSensor)
    )
