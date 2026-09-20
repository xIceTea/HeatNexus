"""Sensor platform for the Windhager integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
import voluptuous as vol

from ..entity import WindhagerEntity, async_setup_entities
from .ableitungen import (
    WindhagerAbleitungSensor,
    WindhagerLaufzeitSensor,
    WindhagerSchaltpunktAbstandSensor,
    WindhagerSchaltpunktSensor,
    WindhagerWarmwasserAbstandSensor,
)
from .gemeinsam import DEVICE_CLASSES, STATE_CLASS_MAP, zahl_aus_zustand
from .meldungen import (
    WindhagerDeviceStatusSensor,
    WindhagerErrorTextSensor,
    WindhagerMessageListSensor,
    WindhagerMessageTextSensor,
)
from .zeitprogramm import _BLOCK_SCHEMA, _SWITCHPOINT_SCHEMA, WindhagerTimeProgramSensor

_LOGGER = logging.getLogger(__name__)


# Der Coordinator holt jeden Wert gebündelt, und die Anfragen an die Anlage
# begrenzt der Client über seine eigene Warteschlange. Eine zweite Bremse in
# Home Assistant würde nur den Abruf verzögern, den es gar nicht gibt.
PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Windhager sensors from a config entry."""
    platform = entity_platform.async_get_current_platform()

    # Die Meldungsliste ist **unsere** Liste; dieser Dienst leert sie. Am
    # Bediengerät der Anlage ändert er nichts – das steht auch in der
    # Beschreibung, weil eine geleerte Liste sonst wie ein quittierter Fehler
    # aussieht.
    platform.async_register_entity_service("meldungen_loeschen", {}, "leeren")

    # Service zum Schreiben eines Zeitprogramms (Heiz-/WW-Programm). Ziel ist
    # eine Zeitprogramm-Sensor-Entity. Entweder mehrere "blocks" (volle
    # Kontrolle, je Block Wochentage + Schaltpunkte) ODER vereinfacht
    # "switch_points" (+ optional "weekdays", Standard: täglich).
    platform.async_register_entity_service(
        "set_time_program",
        {
            vol.Optional("weekdays"): [cv.string],
            vol.Optional("switch_points"): [_SWITCHPOINT_SCHEMA],
            vol.Optional("blocks"): [_BLOCK_SCHEMA],
        },
        "async_set_time_program",
    )

    async_setup_entities(
        hass,
        entry,
        async_add_entities,
        {
            "temperature": WindhagerTemperatureSensor,
            "sensor": WindhagerGenericSensor,
            "enum_sensor": WindhagerEnumSensor,
            "string_sensor": WindhagerStringSensor,
            "error_sensor": WindhagerErrorTextSensor,
            "time_program": WindhagerTimeProgramSensor,
            "device_status": WindhagerDeviceStatusSensor,
            "message_text": WindhagerMessageTextSensor,
            "message_list": WindhagerMessageListSensor,
            "total": WindhagerPelletSensor,
            "total_increasing": WindhagerPelletSensor,
            "zaehler_heute": WindhagerAbleitungSensor,
            "zaehler_start": WindhagerAbleitungSensor,
            "schaltpunkt": WindhagerSchaltpunktSensor,
            "schaltpunkt_abstand": WindhagerSchaltpunktAbstandSensor,
            "ww_abstand": WindhagerWarmwasserAbstandSensor,
            "laufzeit": WindhagerLaufzeitSensor,
            "laufzeit_heute": WindhagerLaufzeitSensor,
        },
    )


class WindhagerTemperatureSensor(WindhagerEntity, SensorEntity):
    """Temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1
    _wiederherstellbar = True

    @property
    def native_value(self) -> float | None:
        wert = self.float_value
        return wert if wert is not None else zahl_aus_zustand(self.letzter_zustand)


class WindhagerGenericSensor(WindhagerEntity, SensorEntity):
    """Generic numeric sensor.

    Einheit, Geräteklasse, Statistikklasse und Anzeigegenauigkeit stehen im
    Deskriptor – der Client leitet sie aus der Einheitentabelle ab. Ohne
    Statistikklasse führt Home Assistant keinen Langzeitverlauf; ohne
    Geräteklasse fehlt dem Wert Symbol und Umrechnung.
    """

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        self._attr_native_unit_of_measurement = device_info.get("unit")
        state_class = device_info.get("state_class")
        if state_class in STATE_CLASS_MAP:
            self._attr_state_class = STATE_CLASS_MAP[state_class]
        device_class = device_info.get("device_class")
        if device_class in DEVICE_CLASSES:
            self._attr_device_class = SensorDeviceClass(device_class)
        if (stellen := device_info.get("precision")) is not None:
            self._attr_suggested_display_precision = stellen

    @property
    def native_value(self) -> float | None:
        wert = self.float_value
        return wert if wert is not None else zahl_aus_zustand(self.letzter_zustand)


class WindhagerEnumSensor(WindhagerEntity, SensorEntity):
    """Read-only sensor that maps a numeric value to its German enum text.

    The device reports the actually possible values in its metadata
    ("enum": "[0,1,...]"); unknown values get a generic label so the
    ENUM device class contract (value in options) always holds.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _wiederherstellbar = True

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        # Die Liste in "enum" nennt die Werte, die das Gerät zur *Auswahl*
        # anbietet. Für einen reinen Anzeigesensor ist das keine Schranke: Der
        # Puffer meldet "Pufferspeicher", wählbar wäre nur "Standby". Wird die
        # Anzeige daran ausgerichtet, steht dort dauerhaft "Unbekannt".
        # Angezeigt wird deshalb aus der vollen Tabelle.
        werte = set(self.enum_map) | set(device_info.get("allowed") or ())
        self._labels = {v: self.enum_map.get(v, f"Unbekannt ({v})") for v in sorted(werte)}

    @staticmethod
    def _ersatzname(raw: int) -> str:
        return f"Unbekannt ({raw})"

    @property
    def options(self) -> list[str]:
        """Mögliche Zustände.

        Die Geräteklasse ENUM verlangt, dass der aktuelle Zustand in dieser
        Liste steht – auch ein unbekannter Wert muss also aufgenommen werden,
        sonst verwirft Home Assistant den Zustand mit einer Fehlermeldung.
        """
        namen = set(self._labels.values())
        if (aktuell := self.native_value) is not None:
            namen.add(aktuell)
        return sorted(namen)

    @property
    def native_value(self) -> str | None:
        raw = self.int_value
        if raw is None:
            return self.letzter_zustand
        label = self._labels.get(raw)
        if label is None:
            _LOGGER.debug(
                "Enum-Wert %s nicht in der Tabelle für %s (%s)", raw, self.name, self._oid
            )
            return self._ersatzname(raw)
        return label


class WindhagerStringSensor(WindhagerEntity, SensorEntity):
    """Sensor that exposes the raw string value (e.g. times, versions)."""

    _wiederherstellbar = True

    @property
    def native_value(self) -> str | None:
        return self.raw_value if self.raw_value is not None else self.letzter_zustand


class WindhagerPelletSensor(WindhagerEntity, SensorEntity):
    """Pellet/fuel consumption sensor (legacy)."""

    _attr_native_unit_of_measurement = "t"
    _wiederherstellbar = True

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        state_class = device_info.get("type")
        if state_class in STATE_CLASS_MAP:
            self._attr_state_class = STATE_CLASS_MAP[state_class]

    @property
    def native_value(self) -> float | None:
        wert = self.float_value
        return wert if wert is not None else zahl_aus_zustand(self.letzter_zustand)
