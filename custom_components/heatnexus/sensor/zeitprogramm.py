"""Der Zeitprogramm-Sensor: liest das Objekt, trägt den Dienst `set_time_program`."""

from __future__ import annotations

import math

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from ..client.gemeinsam import gnmn_aus_oid
from ..const import (
    PROGRAMMART,
    PROGRAMMGRENZEN,
    PROGRAMMGRENZEN_FORMAT,
    WERTRASTER,
    ZEITRASTER_MINUTEN,
)
from ..entity import WindhagerEntity
from ..error_texts import textsprache
from ..exceptions import WindhagerValueError, mit_text

# Schaltpunkt: {"time": "HH:MM", "value": <Temperatur>}
SCHALTPUNKT_SCHEMA = vol.Schema(
    {
        vol.Required("time"): cv.matches_regex(r"^\d{1,2}:\d{2}$"),
        vol.Required("value"): vol.Coerce(float),
    }
)


# Block: Wochentage + Schaltpunkte
BLOCK_SCHEMA = vol.Schema(
    {
        vol.Optional("weekdays"): [cv.string],
        vol.Required("switch_points"): [SCHALTPUNKT_SCHEMA],
    }
)


# Nur Untertyp 14 führt Schaltpunkte. Ein Fensterprogramm (Untertyp 7) verlöre beim
# Schreiben von Schaltpunkten alle Fenster.
SCHALTPUNKTE_UNTERTYP = 14


def _traegt_schaltpunkte(objekt: dict) -> bool:
    return str(objekt.get("subtypeId", SCHALTPUNKTE_UNTERTYP)) == str(SCHALTPUNKTE_UNTERTYP)


def _zahl(wert: float) -> str:
    return str(int(wert)) if float(wert).is_integer() else str(wert)


def _ist_zahl(wert: object) -> bool:
    try:
        float(wert)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return True


def _auf_zeitraster(t: str) -> str:
    """HH:MM auf die nächste Viertelstunde; die letzte des Tages ist 23:45."""
    h, m = t.split(":")
    hh, mm = int(h), int(m)
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise mit_text(WindhagerValueError, "uhrzeit_ungueltig", uhrzeit=t)
    letzte = 24 * 60 - ZEITRASTER_MINUTEN
    minute = min(letzte, round((hh * 60 + mm) / ZEITRASTER_MINUTEN) * ZEITRASTER_MINUTEN)
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _auf_wertraster(val: float, grenzen: tuple[float, float]) -> float:
    """Auf 0,5 runden, halbe Schritte aufwärts wie in der Oberfläche; außerhalb der Grenzen abweisen."""
    gerundet = math.floor(val / WERTRASTER + 0.5) * WERTRASTER
    unten, oben = grenzen
    if not unten <= gerundet <= oben:
        raise mit_text(
            WindhagerValueError,
            "wert_ausserhalb",
            wert=_zahl(val),
            min=_zahl(unten),
            max=_zahl(oben),
        )
    return gerundet


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
    # Die Anlage meldet je nach Baureihe deutsche oder englische Kürzel.
    _DAY_EN = {de: en for en, de in _DAY_DE.items()}
    _DAY_NL = {
        **dict(zip(_DAY_DE, ("Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"), strict=True)),
        **dict(zip(_DAY_DE.values(), ("Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"), strict=True)),
    }
    _WORTE = {
        "de": ("täglich", "keine Schaltpunkte"),
        "en": ("daily", "no switch points"),
        "nl": ("dagelijks", "geen schakelpunten"),
    }

    # Ein Programm nur aus 0 und 1 schaltet; eine Solltemperatur von 1 °C gibt es nicht.
    _SCHALTWORTE = {
        "de": ("Aus", "Ein"),
        "en": ("Off", "On"),
        "nl": ("Uit", "Aan"),
    }

    @classmethod
    def _schaltet(cls, blocks: list, art: str | None = None) -> bool:
        if art is not None:
            return art == "schalt"
        werte = [p.get("value") for b in blocks for p in b.get("switchPoints", [])]
        return bool(werte) and all(w in (0, 1) for w in werte)

    @property
    def _art(self) -> str | None:
        """Die Programmart nach der Adresse; ohne Eintrag entscheiden die Werte."""
        return PROGRAMMART.get(gnmn_aus_oid(self._oid) or "")

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
    def _spannen(cls, days: list) -> list[list[str]] | None:
        """Wochentage als Läufe aufeinanderfolgender Tage; mit unbekanntem Tag `None`."""
        codes = [cls._DAY_NORMALIZE.get(str(d).strip().lower()) for d in days]
        if None in codes:
            return None
        laeufe: list[list[str]] = []
        for code in (c for c in cls.ALL_DAYS if c in codes):
            if laeufe and cls.ALL_DAYS.index(code) == cls.ALL_DAYS.index(laeufe[-1][-1]) + 1:
                laeufe[-1].append(code)
            else:
                laeufe.append([code])
        return laeufe

    @classmethod
    def _fmt_days(cls, days: list, sprache: str = "de") -> str:
        """Ab drei Nachbartagen eine Spanne „Mo–Fr“, wie im Reiter Zeitprogramme."""
        if not days:
            return "?"
        if len(days) == 7:
            return cls._WORTE[sprache][0]
        tage = {"de": cls._DAY_DE, "nl": cls._DAY_NL}.get(sprache, cls._DAY_EN)
        laeufe = cls._spannen(days)
        if laeufe is None:
            return ", ".join(tage.get(d, d) for d in days)
        teile = []
        for lauf in laeufe:
            namen = [tage.get(code, code) for code in lauf]
            teile.append(f"{namen[0]}–{namen[-1]}" if len(namen) > 2 else ", ".join(namen))
        return ", ".join(teile)

    @staticmethod
    def _grad(wert: float, sprache: str) -> str:
        """„27,5 °C“; Englisch mit Punkt."""
        text = _zahl(round(float(wert), 1))
        return f"{text if sprache == 'en' else text.replace('.', ',')} °C"

    @classmethod
    def _fmt_points(cls, points: list, sprache: str = "de", schaltet: bool = False) -> str:
        out = []
        for p in points or []:
            t = p.get("time", "?")
            v = p.get("value")
            if schaltet:
                out.append(f"{t}→{cls._SCHALTWORTE[sprache][v]}")
            else:
                out.append(f"{t}→{cls._grad(v, sprache) if _ist_zahl(v) else '–'}")
        return ", ".join(out) if out else cls._WORTE[sprache][1]

    _FENSTERWORT = {"de": "kein Zeitfenster", "en": "no time window", "nl": "geen tijdvenster"}

    @classmethod
    def _fmt_fenster(cls, fenster: list, sprache: str = "de") -> str:
        """Fenster eines Untertyp-7-Programms; 00:00–00:00 ist unbenutzt, Ende 00:00 heißt 24:00."""
        out = []
        for f in fenster or []:
            start, stop = str(f.get("start", "")), str(f.get("stop", ""))
            if not start or start == stop:
                continue
            out.append(f"{start}–{'24:00' if stop == '00:00' else stop}")
        return ", ".join(out) if out else cls._FENSTERWORT[sprache]

    _TARIFWORT = {"de": "Tarif", "en": "Tariff", "nl": "Tarief"}

    @classmethod
    def _fmt_tarife(cls, points: list, sprache: str = "de") -> str:
        """Schaltpunkte des Stromtarifprogramms: Wert 0–4 heißt Tarif 1–5."""
        wort = cls._TARIFWORT[sprache]
        out = [
            f"{p.get('time', '?')}→{wort} {int(p['value']) + 1}"
            if isinstance(p.get("value"), int | float)
            else f"{p.get('time', '?')}→–"
            for p in points or []
        ]
        return ", ".join(out) if out else cls._WORTE[sprache][1]

    def _fmt_block(self, block: dict, sprache: str, schaltet: bool) -> str:
        if isinstance(block.get("values"), list):
            return self._fmt_fenster(block["values"], sprache)
        punkte = block.get("switchPoints", [])
        if self._art == "tarif":
            return self._fmt_tarife(punkte, sprache)
        return self._fmt_points(punkte, sprache, schaltet)

    @property
    def native_value(self) -> str | None:
        blocks = self._blocks
        if not blocks:
            return None
        sprache = textsprache(self._sprache)
        schaltet = self._schaltet(blocks, self._art)
        parts = [
            f"{self._fmt_days(b.get('weekdays', []), sprache)}: {self._fmt_block(b, sprache, schaltet)}"
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
    # Eingabe in jeder angezeigten Sprache, gekürzt oder ausgeschrieben -> Code der API.
    # Deutsch und Niederländisch teilen sich „di" und „do" mit derselben Bedeutung.
    _DAY_NORMALIZE = {
        name: code
        for code, namen in zip(
            ALL_DAYS,
            (
                ("mo", "montag", "monday", "ma", "maandag"),
                ("di", "tu", "dienstag", "tuesday", "dinsdag"),
                ("mi", "we", "mittwoch", "wednesday", "wo", "woensdag"),
                ("do", "th", "donnerstag", "thursday", "donderdag"),
                ("fr", "freitag", "friday", "vr", "vrijdag"),
                ("sa", "samstag", "saturday", "za", "zaterdag"),
                ("so", "su", "sonntag", "sunday", "zo", "zondag"),
            ),
            strict=True,
        )
        for name in namen
    }

    @classmethod
    def _norm_days(cls, days: list) -> list:
        out = []
        for d in days:
            key = str(d).strip().lower()
            code = cls._DAY_NORMALIZE.get(key)
            if code is None:
                raise mit_text(WindhagerValueError, "wochentag_unbekannt", tag=d)
            if code not in out:
                out.append(code)
        # in Wochenreihenfolge sortieren
        return [d for d in cls.ALL_DAYS if d in out]

    # Die Anlage nimmt je Tag bzw. Block höchstens sechs Schaltzeiten an.
    # Besser hier ablehnen als die Anlage kommentarlos kürzen lassen.
    MAX_SCHALTPUNKTE = 6

    @classmethod
    def _norm_points(
        cls,
        points: list,
        schalt: bool = False,
        grenzen: tuple[float, float] = PROGRAMMGRENZEN_FORMAT,
    ) -> list:
        if len(points) > cls.MAX_SCHALTPUNKTE:
            raise mit_text(
                WindhagerValueError,
                "zu_viele_schaltpunkte",
                hoechstens=cls.MAX_SCHALTPUNKTE,
                anzahl=len(points),
            )
        out = []
        for p in points:
            zeit = _auf_zeitraster(str(p["time"]).strip())
            val = float(p["value"])
            if schalt and val not in (0, 1):
                raise mit_text(WindhagerValueError, "schaltwert_ungueltig")
            val = _auf_wertraster(val, grenzen)
            # Gerät erwartet ganze Zahl ohne Nachkommastelle, sonst .x
            num = int(val) if float(val).is_integer() else round(val, 1)
            if any(punkt["time"] == zeit for punkt in out):
                raise mit_text(WindhagerValueError, "schaltzeit_doppelt", uhrzeit=zeit)
            out.append({"time": zeit, "value": num})
        out.sort(key=lambda x: x["time"])
        return out

    @property
    def _grenzen(self) -> tuple[float, float]:
        """Der Wertebereich dieses Programms nach seiner Adresse."""
        return PROGRAMMGRENZEN.get(gnmn_aus_oid(self._oid) or "", PROGRAMMGRENZEN_FORMAT)

    def _schreibbar_pruefen(self, d: dict) -> None:
        """Ablehnen, was der Dienst nicht schreiben darf, bevor etwas an die Anlage geht."""
        if not d.get("oid") or d.get("type") != "time_program":
            raise mit_text(WindhagerValueError, "kein_zeitprogramm")
        if d.get("write_prot"):
            raise mit_text(WindhagerValueError, "zeitprogramm_geschuetzt")
        # Der Dienst schreibt nur Schaltpunkte mit Temperatur oder Ein/Aus, keine Tarife.
        if self._art == "tarif" or not _traegt_schaltpunkte(d):
            raise mit_text(WindhagerValueError, "zeitprogramm_nicht_aenderbar")

    async def async_set_time_program(self, switch_points=None, weekdays=None, blocks=None) -> None:
        """Write the time program via the object endpoint.

        Liest zuerst das aktuelle Objekt, ersetzt nur 'value' und schreibt das
        vollständige, gerätekonforme Objekt zurück (alle übrigen Felder bleiben
        erhalten). Damit wird nichts ungewollt verstellt.
        """
        d = self._descriptor
        full_oid = d.get("oid")
        self._schreibbar_pruefen(d)
        schalt = self._art == "schalt"
        grenzen = self._grenzen

        if blocks:
            value = [
                {
                    "weekdays": self._norm_days(b.get("weekdays") or self.ALL_DAYS),
                    "switchPoints": self._norm_points(b["switch_points"], schalt, grenzen),
                }
                for b in blocks
            ]
        elif switch_points:
            value = [
                {
                    "weekdays": self._norm_days(weekdays or self.ALL_DAYS),
                    "switchPoints": self._norm_points(switch_points, schalt, grenzen),
                }
            ]
        else:
            raise mit_text(WindhagerValueError, "schaltpunkte_fehlen")

        client = self.coordinator.client
        # Aktuelles Objekt als Envelope lesen (Felder wie OID/typeId erhalten).
        data, status = await client.fetch_object(full_oid)
        if status == 200 and isinstance(data, dict):
            if not _traegt_schaltpunkte(data):
                raise mit_text(WindhagerValueError, "zeitprogramm_nicht_aenderbar")
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
