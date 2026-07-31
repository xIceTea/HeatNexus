"""Sensor platform for the Windhager integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform

from . import DOMAIN
from .const import ERROR_TEXTS
from .entity import WindhagerEntity
from .error_texts import parse_messages
from .exceptions import WindhagerValueError

_LOGGER = logging.getLogger(__name__)

STATE_CLASS_MAP = {
    "measurement": SensorStateClass.MEASUREMENT,
    "total": SensorStateClass.TOTAL,
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
}


# Schaltpunkt: {"time": "HH:MM", "value": <Temperatur>}
_SWITCHPOINT_SCHEMA = vol.Schema(
    {
        vol.Required("time"): cv.matches_regex(r"^\d{1,2}:\d{2}$"),
        vol.Required("value"): vol.Coerce(float),
    }
)
# Block: Wochentage + Schaltpunkte
_BLOCK_SCHEMA = vol.Schema(
    {
        vol.Optional("weekdays"): [cv.string],
        vol.Required("switch_points"): [_SWITCHPOINT_SCHEMA],
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Windhager sensors from a config entry."""
    platform = entity_platform.async_get_current_platform()
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

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    for device_info in coordinator.data.get("devices", []):
        dev_type = device_info.get("type")
        if dev_type == "temperature":
            entities.append(WindhagerTemperatureSensor(coordinator, device_info))
        elif dev_type == "sensor":
            entities.append(WindhagerGenericSensor(coordinator, device_info))
        elif dev_type == "enum_sensor":
            entities.append(WindhagerEnumSensor(coordinator, device_info))
        elif dev_type == "string_sensor":
            entities.append(WindhagerStringSensor(coordinator, device_info))
        elif dev_type == "error_sensor":
            entities.append(WindhagerErrorTextSensor(coordinator, device_info))
        elif dev_type == "time_program":
            entities.append(WindhagerTimeProgramSensor(coordinator, device_info))
        elif dev_type == "device_status":
            entities.append(WindhagerDeviceStatusSensor(coordinator, device_info))
        elif dev_type == "message_text":
            entities.append(WindhagerMessageTextSensor(coordinator, device_info))
        elif dev_type in ("total", "total_increasing"):
            entities.append(WindhagerPelletSensor(coordinator, device_info))

    async_add_entities(entities)


class WindhagerTemperatureSensor(WindhagerEntity, SensorEntity):
    """Temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        return self.float_value


class WindhagerGenericSensor(WindhagerEntity, SensorEntity):
    """Generic numeric sensor."""

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        self._attr_native_unit_of_measurement = device_info.get("unit")
        state_class = device_info.get("state_class")
        if state_class in STATE_CLASS_MAP:
            self._attr_state_class = STATE_CLASS_MAP[state_class]

    @property
    def native_value(self) -> float | None:
        return self.float_value


class WindhagerEnumSensor(WindhagerEntity, SensorEntity):
    """Read-only sensor that maps a numeric value to its German enum text.

    The device reports the actually possible values in its metadata
    ("enum": "[0,1,...]"); unknown values get a generic label so the
    ENUM device class contract (value in options) always holds.
    """

    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        allowed = device_info.get("allowed")
        values = allowed if allowed else sorted(self.enum_map)
        self._labels = {v: self.enum_map.get(v, f"Unbekannt ({v})") for v in values}
        # ENUM device class requires the list of possible options
        self._attr_options = sorted(set(self._labels.values()))

    @property
    def native_value(self) -> str | None:
        raw = self.int_value
        if raw is None:
            return None
        label = self._labels.get(raw)
        if label is None:
            _LOGGER.debug(
                "Enum value %s outside allowed range for %s (%s)",
                raw, self.name, self._oid,
            )
        return label


class WindhagerStringSensor(WindhagerEntity, SensorEntity):
    """Sensor that exposes the raw string value (e.g. times, versions)."""

    @property
    def native_value(self) -> str | None:
        return self.raw_value


class WindhagerPelletSensor(WindhagerEntity, SensorEntity):
    """Pellet/fuel consumption sensor (legacy)."""

    _attr_native_unit_of_measurement = "t"

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        state_class = device_info.get("type")
        if state_class in STATE_CLASS_MAP:
            self._attr_state_class = STATE_CLASS_MAP[state_class]

    @property
    def native_value(self) -> float | None:
        return self.float_value


class WindhagerErrorTextSensor(WindhagerEntity, SensorEntity):
    """Maps a Windhager alarm code (e.g. 0/97) to its German error text."""

    _attr_icon = "mdi:alert-circle-outline"

    @property
    def native_value(self) -> str | None:
        code = self.int_value
        if code is None:
            return None
        if code == 0:
            return "Keine Störung"
        text = ERROR_TEXTS.get(code)
        if text is None:
            return f"Unbekannter Code {code}"
        return f"{code}: {text}"

    @property
    def extra_state_attributes(self):
        return {"code": self.int_value}


class WindhagerDeviceStatusSensor(WindhagerEntity, SensorEntity):
    """Per-device status/notification from the FE01msg field.

    Die /1-Discovery liefert je Gerät ein FE01msg, z.B. "PUR 09  OK" oder
    "PCM 00  OK". Endet es auf "OK", liegt keine Störung an; sonst steht hier
    die anstehende Meldung (InfoWIN-Benachrichtigung). Attribut `ok` erlaubt
    einfache Automationen ("ist eine Störung aktiv?").
    """

    _attr_icon = "mdi:message-alert-outline"
    # kommt aus der /1-Discovery, nicht aus dem OID-Polling
    _register_poll_oid = False

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        self._node_id = str(device_info.get("node_id"))

    @property
    def _message(self) -> str | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("status", {}).get(self._node_id)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._message is not None

    @property
    def native_value(self) -> str | None:
        msg = self._message
        if msg is None:
            return None
        return msg.strip()[:255]

    @property
    def extra_state_attributes(self):
        msg = self._message
        if msg is None:
            return None
        return {"ok": msg.strip().upper().endswith("OK"), "raw": msg}


class WindhagerMessageTextSensor(WindhagerEntity, SensorEntity):
    """Klartext der aktiven Störungen aus dem FE01msg (Code -> Text).

    State zeigt nur den Klartext, z.B. "Verkleidungstür offen" (mehrere getrennt
    durch " | "), bzw. "Keine Störung". Code, Art (Fehler/Alarm/Info) und
    Handlungsempfehlung stehen im Attribut `meldungen` (Liste) für die
    Markdown-Darstellung bzw. zum Nachschlagen.
    """

    _attr_icon = "mdi:alert-circle-outline"
    _register_poll_oid = False

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        self._node_id = str(device_info.get("node_id"))

    @property
    def _raw(self) -> str | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("status", {}).get(self._node_id)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._raw is not None

    @property
    def native_value(self) -> str | None:
        if self._raw is None:
            return None
        msgs = parse_messages(self._raw)
        if not msgs:
            return "Keine Störung"
        # Nur der Klartext (Code/Art stehen im Attribut 'meldungen').
        parts = [m["text"] for m in msgs]
        return " | ".join(parts)[:255]

    @property
    def extra_state_attributes(self):
        if self._raw is None:
            return None
        msgs = parse_messages(self._raw)
        return {
            "anzahl": len(msgs),
            "stoerung_aktiv": len(msgs) > 0,
            "meldungen": msgs,
            "rohwert": self._raw,
        }


class WindhagerTimeProgramSensor(WindhagerEntity, SensorEntity):
    """Read-only view of a Windhager time program (Heiz-/WW-Programm).

    Gelesen über den object-Endpunkt: eine Liste von Blöcken, je Block mit
    Wochentagen und Schaltpunkten {time, value}. Der State zeigt eine kompakte
    Zusammenfassung, die kompletten Daten stehen in den Attributen (für
    Automationen / spätere Schreibfunktion).
    """

    _attr_icon = "mdi:calendar-clock"
    # Zeitprogramme werden über den object-Endpunkt gelesen, nicht via lookup.
    _register_poll_oid = False

    _DAY_DE = {
        "Mo": "Mo", "Tu": "Di", "We": "Mi", "Th": "Do",
        "Fr": "Fr", "Sa": "Sa", "Su": "So",
    }

    @property
    def _blocks(self):
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("objects", {}).get(self._oid)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._blocks is not None

    @classmethod
    def _fmt_days(cls, days: list) -> str:
        if not days:
            return "?"
        if len(days) == 7:
            return "täglich"
        return ", ".join(cls._DAY_DE.get(d, d) for d in days)

    @staticmethod
    def _fmt_points(points: list) -> str:
        out = []
        for p in points or []:
            t = p.get("time", "?")
            v = p.get("value")
            out.append(f"{t}→{v}°" if v is not None else f"{t}→–")
        return ", ".join(out) if out else "keine Schaltpunkte"

    @property
    def native_value(self) -> str | None:
        blocks = self._blocks
        if not blocks:
            return None
        parts = [
            f"{self._fmt_days(b.get('weekdays', []))}: "
            f"{self._fmt_points(b.get('switchPoints', []))}"
            for b in blocks
        ]
        text = " | ".join(parts)
        # HA-States dürfen max. 255 Zeichen haben.
        return text[:255]

    @property
    def extra_state_attributes(self):
        blocks = self._blocks
        if not blocks:
            return None
        return {"blocks": blocks}

    # ------------------------------------------------------------------
    # Schreiben (Service windhager.set_time_program)
    # ------------------------------------------------------------------
    ALL_DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    # Eingabe (deutsch ODER englisch) -> von der API erwartete Codes
    _DAY_NORMALIZE = {
        "mo": "Mo", "di": "Tu", "tu": "Tu", "mi": "We", "we": "We",
        "do": "Th", "th": "Th", "fr": "Fr", "sa": "Sa", "so": "Su", "su": "Su",
    }

    @classmethod
    def _norm_days(cls, days: list) -> list:
        out = []
        for d in days:
            key = str(d).strip().lower()
            code = cls._DAY_NORMALIZE.get(key)
            if code is None:
                raise WindhagerValueError(f"Unbekannter Wochentag: {d}")
            if code not in out:
                out.append(code)
        # in Wochenreihenfolge sortieren
        return [d for d in cls.ALL_DAYS if d in out]

    @staticmethod
    def _norm_points(points: list) -> list:
        out = []
        for p in points:
            t = str(p["time"]).strip()
            h, m = t.split(":")
            hh, mm = int(h), int(m)
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                raise WindhagerValueError(f"Ungültige Uhrzeit: {t}")
            val = float(p["value"])
            # Gerät erwartet ganze Zahl ohne Nachkommastelle, sonst .x
            num = int(val) if float(val).is_integer() else round(val, 1)
            out.append({"time": f"{hh:02d}:{mm:02d}", "value": num})
        out.sort(key=lambda x: x["time"])
        return out

    async def async_set_time_program(
        self, switch_points=None, weekdays=None, blocks=None
    ) -> None:
        """Write the time program via the object endpoint.

        Liest zuerst das aktuelle Objekt, ersetzt nur 'value' und schreibt das
        vollständige, gerätekonforme Objekt zurück (alle übrigen Felder bleiben
        erhalten). Damit wird nichts ungewollt verstellt.
        """
        d = self._descriptor
        full_oid = d.get("oid")
        if not full_oid or d.get("type") != "time_program":
            raise WindhagerValueError("Diese Entität ist kein beschreibbares Zeitprogramm")
        if d.get("write_prot"):
            raise WindhagerValueError("Dieses Zeitprogramm ist schreibgeschützt")

        if blocks:
            value = [
                {
                    "weekdays": self._norm_days(b.get("weekdays") or self.ALL_DAYS),
                    "switchPoints": self._norm_points(b["switch_points"]),
                }
                for b in blocks
            ]
        elif switch_points:
            value = [
                {
                    "weekdays": self._norm_days(weekdays or self.ALL_DAYS),
                    "switchPoints": self._norm_points(switch_points),
                }
            ]
        else:
            raise WindhagerValueError(
                "Bitte 'switch_points' oder 'blocks' angeben"
            )

        client = self.coordinator.client
        # Aktuelles Objekt als Envelope lesen (Felder wie OID/typeId erhalten).
        data, status = await client.fetch_object(full_oid)
        if status == 200 and isinstance(data, dict):
            payload = dict(data)
            payload.pop("timestamp", None)
        else:
            payload = {
                "OID": full_oid,
                "typeId": d.get("typeId", 30),
                "subtypeId": d.get("subtypeId", 14),
            }
        payload["value"] = value

        await client.write_object(full_oid, payload)
        await self.coordinator.async_request_refresh()
