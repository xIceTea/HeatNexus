"""Sensor platform for the Windhager integration."""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .const import ERROR_TEXTS
from .entity import MeldungsQuelle, WindhagerEntity, async_setup_entities
from .error_texts import parse_messages
from .exceptions import WindhagerValueError
from .helpers import get_oid_value

_LOGGER = logging.getLogger(__name__)

STATE_CLASS_MAP = {
    "measurement": SensorStateClass.MEASUREMENT,
    "total": SensorStateClass.TOTAL,
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
}

# Geräteklassen, die aus der Einheitentabelle kommen können. Was Home Assistant
# nicht kennt, bleibt lieber ohne Klasse als mit einer falschen.
DEVICE_CLASSES = {klasse.value for klasse in SensorDeviceClass}


def _zahl(zustand: str | None) -> float | None:
    """Einen gespeicherten Zustand als Zahl lesen (oder gar nicht)."""
    if zustand is None:
        return None
    try:
        return float(zustand)
    except (TypeError, ValueError):
        return None


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
        return wert if wert is not None else _zahl(self.letzter_zustand)


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
        return wert if wert is not None else _zahl(self.letzter_zustand)


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
        return wert if wert is not None else _zahl(self.letzter_zustand)


class WindhagerAbleitungSensor(WindhagerEntity, SensorEntity):
    """Zuwachs eines Zählerstands seit einem Bezugspunkt.

    Bezug ist der Tagesbeginn oder der letzte Brennerstart; die Anlage selbst
    führt nur Gesamtstände. Gelesen wird die Adresse des Zählers, ohne einen
    zusätzlichen Abruf.
    """

    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        self._attr_native_unit_of_measurement = device_info.get("unit")
        device_class = device_info.get("device_class")
        if device_class in DEVICE_CLASSES:
            self._attr_device_class = SensorDeviceClass(device_class)
        self._ausloeser_oid = device_info.get("ausloeser_oid")
        self._basis: float | None = None
        self._marke: str | None = None

    @property
    def _bezugsmarke(self) -> str | None:
        """Woran der Bezugspunkt hängt: Tagesdatum oder Stand der Brennerstarts."""
        if self._ausloeser_oid is None:
            return dt_util.now().date().isoformat()
        stand = get_oid_value(self.coordinator, self._ausloeser_oid)
        return None if stand is None else str(stand)

    async def async_added_to_hass(self) -> None:
        """Bezugspunkt aus dem letzten Zustand übernehmen, Auslöser anmelden."""
        await super().async_added_to_hass()
        if self._ausloeser_oid:
            self.coordinator.client.register_poll_oid(self._ausloeser_oid)
        alt = await self.async_get_last_state()
        if alt is None:
            return
        self._basis = _zahl(alt.attributes.get("basis"))
        self._marke = alt.attributes.get("marke")
        with contextlib.suppress(TypeError, ValueError):
            self._attr_last_reset = dt_util.parse_datetime(alt.attributes.get("last_reset") or "")

    async def async_will_remove_from_hass(self) -> None:
        """Den Auslöser wieder abmelden."""
        if self._ausloeser_oid:
            self.coordinator.client.unregister_poll_oid(self._ausloeser_oid)
        await super().async_will_remove_from_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Vor dem Schreiben prüfen, ob der Bezugspunkt weiterrückt."""
        self._bezugspunkt_pruefen()
        super()._handle_coordinator_update()

    def _bezugspunkt_pruefen(self) -> None:
        wert = self.float_value
        if wert is None:
            return
        marke = self._bezugsmarke
        if marke is None and self._ausloeser_oid:
            # Der Auslöser ist noch nicht gelesen; ohne ihn kein Bezugspunkt.
            return
        # Ein kleinerer Stand heißt: Der Zähler der Anlage hat neu begonnen.
        if self._basis is None or marke != self._marke or wert < self._basis:
            self._basis = wert
            self._marke = marke
            self._attr_last_reset = (
                dt_util.utcnow() if self._ausloeser_oid else dt_util.start_of_local_day()
            )

    @property
    def native_value(self) -> float | None:
        wert = self.float_value
        if wert is None or self._basis is None:
            return None
        return round(wert - self._basis, 3)

    @property
    def extra_state_attributes(self):
        """Der Bezugspunkt überlebt einen Neustart nur, wenn er im Zustand steht."""
        return {
            "basis": self._basis,
            "marke": self._marke,
            "last_reset": self._attr_last_reset.isoformat() if self._attr_last_reset else None,
        }


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


class WindhagerDeviceStatusSensor(MeldungsQuelle, WindhagerEntity, SensorEntity):
    """Per-device status/notification from the FE01msg field.

    Die /1-Discovery liefert je Gerät ein FE01msg, z.B. "PUR 09  OK" oder
    "PCM 00  OK". Endet es auf "OK", liegt keine Störung an; sonst steht hier
    die anstehende Meldung (InfoWIN-Benachrichtigung). Attribut `ok` erlaubt
    einfache Automationen ("ist eine Störung aktiv?").
    """

    _attr_icon = "mdi:message-alert-outline"

    @property
    def native_value(self) -> str | None:
        msg = self._raw
        if msg is None:
            return None
        return msg.strip()[:255]

    @property
    def extra_state_attributes(self):
        msg = self._raw
        if msg is None:
            return None
        return {"ok": msg.strip().upper().endswith("OK"), "raw": msg}


class WindhagerMessageTextSensor(MeldungsQuelle, WindhagerEntity, SensorEntity):
    """Klartext der aktiven Störungen aus dem FE01msg (Code -> Text).

    State zeigt nur den Klartext, z.B. "Verkleidungstür offen" (mehrere getrennt
    durch " | "), bzw. "Keine Störung". Code, Art (Fehler/Alarm/Info) und
    Handlungsempfehlung stehen im Attribut `meldungen` (Liste) für die
    Markdown-Darstellung bzw. zum Nachschlagen.
    """

    _attr_icon = "mdi:alert-circle-outline"

    @property
    def native_value(self) -> str | None:
        if self._raw is None:
            return None
        msgs = self._meldungen
        if not msgs:
            return "Keine Störung"
        # Nur der Klartext (Code/Art stehen im Attribut 'meldungen').
        parts = [m["text"] for m in msgs]
        return " | ".join(parts)[:255]

    @property
    def extra_state_attributes(self):
        if self._raw is None:
            return None
        msgs = self._meldungen
        return {
            "anzahl": len(msgs),
            "stoerung_aktiv": len(msgs) > 0,
            "meldungen": msgs,
            "rohwert": self._raw,
        }


class WindhagerMessageListSensor(WindhagerEntity, SensorEntity):
    """Fortlaufende Liste aller Meldungen, die diese Anlage gezeigt hat.

    **Warum es sie gibt.** ``FE01msg`` nennt nur, was gerade anliegt. Wer die
    Verkleidungstür öffnet und wieder schließt, sieht die Meldung kommen und
    gehen – hinterher steht nirgends, dass sie da war. Das Bediengerät führt
    dafür eine Liste mit Papierkorb; über die Schnittstelle ist sie nicht zu
    bekommen. Geprüft an der Anlage: ``2/96`` – die Adresse, die die
    Weboberfläche der Steuerung dafür benutzt – antwortet an jeder Funktion mit
    ``409 invalid Identifier``, und von 24 denkbaren Endpunktnamen kennt die
    Steuerung keinen einzigen (``errorlog``, ``errors``, ``message``,
    ``messages``, ``alarm``, ``alarms``, ``log``, ``history``).

    **Das hier ist deshalb unsere Liste, nicht die des Kessels.** Sie beginnt,
    wenn die Integration eingerichtet wird, und der Dienst
    ``heatnexus.meldungen_loeschen`` leert *sie* – am Bediengerät ändert das
    nichts. Wer das verwechselt, hält eine geleerte Liste für einen
    quittierten Fehler.

    Je Code ein Eintrag, ohne Dubletten, mit erstem und letztem Auftreten und
    einem Zähler. Der Zustand ist die Anzahl; die Einträge stehen im Attribut.
    Sie überleben einen Neustart über ``RestoreEntity``.
    """

    _attr_icon = "mdi:format-list-bulleted"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "Meldungen"
    # Quelle ist die /1-Discovery, nicht das OID-Polling.
    _register_poll_oid = False
    # Der Zustand ist die Länge der eigenen Liste, kein Wert der Anlage. Ohne
    # das gälte die Entität als wertlos und damit dauerhaft als nicht
    # verfügbar – auch dann, wenn sie Einträge führt.
    _require_value_for_available = False

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        self._node_id = str(device_info.get("node_id"))
        # code -> Eintrag. Ein Wörterbuch, damit derselbe Fehler beim zweiten
        # Auftreten seinen Zähler hochsetzt statt eine Dublette anzulegen.
        self._eintraege: dict[int, dict] = {}

    async def async_added_to_hass(self) -> None:
        """Die gesammelten Meldungen über einen Neustart hinweg mitnehmen."""
        await super().async_added_to_hass()
        letzter = await self.async_get_last_state()
        if letzter is None:
            return
        for eintrag in letzter.attributes.get("meldungen") or []:
            with contextlib.suppress(TypeError, ValueError, AttributeError):
                self._eintraege[int(eintrag["code"])] = dict(eintrag)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Neue Meldungen aufnehmen, bevor der Zustand geschrieben wird."""
        self._aufnehmen()
        super()._handle_coordinator_update()

    def _aufnehmen(self) -> None:
        roh = (self.coordinator.data or {}).get("status", {}).get(self._node_id)
        if roh is None:
            return
        jetzt = dt_util.utcnow().isoformat(timespec="seconds")
        for meldung in parse_messages(roh, self._descriptor.get("stoerungstexte")):
            vorhanden = self._eintraege.get(meldung["code"])
            if vorhanden is None:
                self._eintraege[meldung["code"]] = {
                    **meldung,
                    "zuerst": jetzt,
                    "zuletzt": jetzt,
                    "anzahl": 1,
                }
                continue
            # Dieselbe Meldung im nächsten Abruf ist kein neues Ereignis –
            # sonst zählte eine offene Tür alle 30 Sekunden weiter hoch.
            vorhanden["zuletzt"] = jetzt

    @callback
    def leeren(self) -> None:
        """Die Liste verwerfen – nur unsere, nicht die der Anlage."""
        self._eintraege.clear()
        # Wie in `entity._nachfassen`: Ohne angemeldete Entität gibt es
        # nichts zu schreiben. Home Assistant leitet einen Dienst zwar nur an
        # angemeldete Entitäten weiter, aber ein Aufruf ohne `hass` wäre ein
        # Absturz statt einer wirkungslosen Zeile.
        if self.hass:
            self.async_write_ha_state()

    @property
    def native_value(self) -> int:
        return len(self._eintraege)

    @property
    def extra_state_attributes(self):
        # Neueste zuerst: Wer nachschaut, sucht meist das Letzte.
        eintraege = sorted(
            self._eintraege.values(), key=lambda e: e.get("zuletzt") or "", reverse=True
        )
        return {"meldungen": eintraege, "eigene_liste": True}


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
        "Mo": "Mo",
        "Tu": "Di",
        "We": "Mi",
        "Th": "Do",
        "Fr": "Fr",
        "Sa": "Sa",
        "Su": "So",
    }

    @property
    def _blocks(self):
        if not self.coordinator.data:
            return None
        blocks = self.coordinator.data.get("objects", {}).get(self._oid)
        # Die Anlage liefert unter derselben Typkennung auch einfache Werte
        # (z.B. Modulinfo). Nur echte Schaltprogramme darstellen.
        if not isinstance(blocks, list):
            return None
        return [b for b in blocks if isinstance(b, dict)] or None

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
    # Schreiben (Service heatnexus.set_time_program)
    # ------------------------------------------------------------------
    ALL_DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    # Eingabe (deutsch ODER englisch) -> von der API erwartete Codes
    _DAY_NORMALIZE = {
        "mo": "Mo",
        "di": "Tu",
        "tu": "Tu",
        "mi": "We",
        "we": "We",
        "do": "Th",
        "th": "Th",
        "fr": "Fr",
        "sa": "Sa",
        "so": "Su",
        "su": "Su",
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

    # Die Anlage nimmt je Tag bzw. Block höchstens sechs Schaltzeiten an.
    # Besser hier ablehnen als die Anlage kommentarlos kürzen lassen.
    MAX_SCHALTPUNKTE = 6

    @classmethod
    def _norm_points(cls, points: list) -> list:
        if len(points) > cls.MAX_SCHALTPUNKTE:
            raise WindhagerValueError(
                f"Höchstens {cls.MAX_SCHALTPUNKTE} Schaltpunkte je Block, "
                f"angegeben wurden {len(points)}"
            )
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

    async def async_set_time_program(self, switch_points=None, weekdays=None, blocks=None) -> None:
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
            raise WindhagerValueError("Bitte 'switch_points' oder 'blocks' angeben")

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

        # Sofort nachlesen und die Anzeige damit versorgen. Zeitprogramme
        # laufen im langsamen Takt mit; ohne das stünde hier bis zu mehrere
        # Minuten lang der Stand von vor der Änderung – wer die Karte gleich
        # wieder öffnet, glaubt, das Schreiben sei fehlgeschlagen.
        geschrieben = await client.refresh_object(full_oid)
        if geschrieben is not None and (daten := self.coordinator.data) is not None:
            daten.setdefault("objects", {})[full_oid] = geschrieben
            self.coordinator.async_update_listeners()
        await self.coordinator.async_request_refresh()
