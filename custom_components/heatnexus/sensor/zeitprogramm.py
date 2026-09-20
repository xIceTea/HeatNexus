"""Der Zeitprogramm-Sensor: liest das Objekt, trägt den Dienst `set_time_program`."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from ..entity import WindhagerEntity
from ..exceptions import WindhagerValueError

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
