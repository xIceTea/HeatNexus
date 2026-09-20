"""Sensoren für abgeleitete Werte: Zuwächse, Laufzeiten, Schaltpunkte, Abstände.

Sie leben von einem anderen Datenpunkt und merken sich ihren Bezug über den
Neustart; `zahl_aus_zustand` liest den gespeicherten Zustand zurück.
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from ..entity import WindhagerEntity
from ..helpers import get_oid_raw, get_oid_value
from .gemeinsam import DEVICE_CLASSES, zahl_aus_zustand


class WindhagerAbleitungSensor(WindhagerEntity, SensorEntity):
    """Zuwachs eines Zählerstands seit einem Bezugspunkt.

    Bezug ist der Tagesbeginn oder der letzte Brennerstart; die Anlage selbst
    führt nur Gesamtstände. Gelesen wird die Adresse des Zählers, ohne einen
    zusätzlichen Abruf.
    """

    _attr_state_class = SensorStateClass.TOTAL
    # Angaben für den Neustart, nicht für den Verlauf: Sie ändern sich bei
    # jedem Abruf. Angezeigt werden sie weiterhin, den Stand nach einem
    # Neustart holt `RestoreEntity` und nicht die Datenbank.
    _unrecorded_attributes = frozenset({"basis", "marke"})
    # Der Bezugspunkt steht in den Attributen, und Home Assistant schreibt
    # Attribute nur, solange eine Entität verfügbar ist. Ohne dies verlöre sie
    # ihn, sobald die Anlage einen Abruf lang keinen Wert liefert.
    _require_value_for_available = False

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
        self._basis = zahl_aus_zustand(alt.attributes.get("basis"))
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
        # Ohne gelesenen Auslöser gibt es keinen Bezugspunkt.
        marke = self._bezugsmarke
        if marke is None:
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


class WindhagerLaufzeitSensor(WindhagerEntity, SensorEntity):
    """Wie lange das Aggregat läuft: der laufende Lauf oder die Tagessumme.

    Gemessen wird an der Betriebsphase: Verlässt sie die Ruhe, läuft die Uhr;
    kehrt sie zurück, steht sie. Verglichen werden die Zahlencodes der
    Enum-Tabelle, weil Beschriftungen mit Sprache und Baureihe wechseln.
    """

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "min"
    _attr_suggested_display_precision = 0
    _unrecorded_attributes = frozenset({"laeuft", "beginn", "letzte_dauer", "heute", "tag"})
    # Stand und Tagesmarke stehen in den Attributen, und die schreibt Home
    # Assistant nur bei verfügbarer Entität. Ohne dies ginge die Tagessumme
    # verloren, sobald die Anlage einen Abruf lang schweigt.
    _require_value_for_available = False

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        self._laufphasen = set(device_info.get("laufphasen") or ())
        self._tageswert = device_info.get("type") == "laufzeit_heute"
        self._attr_state_class = (
            SensorStateClass.TOTAL if self._tageswert else SensorStateClass.MEASUREMENT
        )
        self._beginn: datetime | None = None
        self._letzte: float = 0.0
        self._heute: float = 0.0
        self._tag: str | None = None

    @property
    def _laeuft(self) -> bool | None:
        """Ob die Anlage gerade brennt – None, solange keine Phase vorliegt."""
        wert = self.int_value
        return None if wert is None else wert in self._laufphasen

    async def async_added_to_hass(self) -> None:
        """Den angefangenen Brand und die Tagessumme wieder aufnehmen."""
        await super().async_added_to_hass()
        alt = await self.async_get_last_state()
        if alt is None:
            return
        with contextlib.suppress(TypeError, ValueError):
            self._beginn = dt_util.parse_datetime(alt.attributes.get("beginn") or "")
        self._letzte = zahl_aus_zustand(alt.attributes.get("letzte_dauer")) or 0.0
        self._heute = zahl_aus_zustand(alt.attributes.get("heute")) or 0.0
        self._tag = alt.attributes.get("tag")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Den Lauf fortschreiben, bevor der Zustand geschrieben wird."""
        self._fortschreiben()
        super()._handle_coordinator_update()

    def _fortschreiben(self) -> None:
        laeuft = self._laeuft
        if laeuft is None:
            return
        jetzt = dt_util.utcnow()
        tag = dt_util.now().date().isoformat()
        if tag != self._tag:
            self._tag = tag
            self._heute = 0.0
        if laeuft and self._beginn is None:
            self._beginn = jetzt
        elif not laeuft and self._beginn is not None:
            self._letzte = self._minuten()
            self._heute += self._letzte
            self._beginn = None

    def _minuten(self) -> float:
        if not self._beginn:
            return 0.0
        return round((dt_util.utcnow() - self._beginn).total_seconds() / 60, 1)

    @property
    def native_value(self) -> float | None:
        if self._laeuft is None:
            return None
        laufend = self._minuten()
        if self._tageswert:
            return round(self._heute + laufend, 1)
        # Läuft gerade nichts, bleibt der letzte Lauf stehen – eine Null sagte
        # nur, dass es still ist, und das steht im Attribut.
        return laufend if self._beginn else self._letzte

    @property
    def extra_state_attributes(self):
        """Der Stand überlebt einen Neustart nur, wenn er im Zustand steht."""
        return {
            "laeuft": bool(self._beginn),
            "beginn": self._beginn.isoformat() if self._beginn else None,
            "letzte_dauer": self._letzte,
            "heute": round(self._heute, 1),
            "tag": self._tag,
        }


class _BezugMerker:
    """Merkt den letzten Bezugswert ungleich null.

    Ohne Anforderung meldet die Anlage null; der Schaltpunkt der letzten
    Ladung bleibt trotzdem die beste Auskunft.
    """

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        self._gehalten: float | None = None
        self._seit: datetime | None = None

    @property
    def _anstehend(self) -> float | None:
        """Der Wert, den die Anlage gerade meldet. Jede Klasse liest anders."""
        raise NotImplementedError

    @property
    def _bezug(self) -> float | None:
        """Der anstehende Wert, sonst der zuletzt gesehene."""
        return self._anstehend or self._gehalten

    async def async_added_to_hass(self) -> None:
        """Den letzten Bezug aus dem gespeicherten Zustand aufnehmen."""
        await super().async_added_to_hass()
        alt = await self.async_get_last_state()
        if alt is None:
            return
        self._gehalten = zahl_aus_zustand(alt.attributes.get("bezug"))
        with contextlib.suppress(TypeError, ValueError):
            self._seit = dt_util.parse_datetime(alt.attributes.get("seit") or "")

    @callback
    def _handle_coordinator_update(self) -> None:
        self._bezug_merken()
        super()._handle_coordinator_update()

    def _bezug_merken(self) -> None:
        wert = self._anstehend
        if wert and wert != self._gehalten:
            self._gehalten = wert
            self._seit = dt_util.utcnow()

    @property
    def _merk_attribute(self) -> dict[str, Any]:
        """Bezug, ob er gehalten wird, und seit wann."""
        anstehend = self._anstehend
        return {
            "bezug": anstehend or self._gehalten,
            "gehalten": not anstehend and self._gehalten is not None,
            "seit": self._seit.isoformat() if self._seit else None,
        }


class WindhagerSchaltpunktSensor(_BezugMerker, WindhagerEntity, SensorEntity):
    """Die Temperatur, bei der die Anlage schaltet.

    Sollwert und Hysterese führt die Steuerung getrennt; wann tatsächlich
    geschaltet wird, ergibt sich erst aus beiden.
    """

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _unrecorded_attributes = frozenset(
        {"sollwert", "hysterese", "anteil", "bezug", "gehalten", "seit"}
    )
    # Der Sollwert steht nur an, solange etwas angefordert wird. Dazwischen
    # bleibt der Schaltpunkt leer, die Entität aber bedienbar.
    _require_value_for_available = False

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        self._hysterese_oid = device_info.get("ausloeser_oid")
        self._anteil = float(device_info.get("anteil") or 0)
        self._hysterese_vorgabe = zahl_aus_zustand(device_info.get("hysterese_vorgabe"))

    @property
    def _anstehend(self) -> float | None:
        return self.float_value

    async def async_added_to_hass(self) -> None:
        """Die Hysterese mit abrufen, sie steht sonst auf der Serviceebene still."""
        await super().async_added_to_hass()
        if self._hysterese_oid:
            self.coordinator.client.register_poll_oid(self._hysterese_oid)

    async def async_will_remove_from_hass(self) -> None:
        if self._hysterese_oid:
            self.coordinator.client.unregister_poll_oid(self._hysterese_oid)
        await super().async_will_remove_from_hass()

    @property
    def _hysterese(self) -> float | None:
        """Der abgerufene Wert, sonst der beim Einlesen gelesene."""
        live = zahl_aus_zustand(get_oid_value(self.coordinator, self._hysterese_oid))
        return live if live is not None else self._hysterese_vorgabe

    @property
    def native_value(self) -> float | None:
        """Bezug plus Anteil der Hysterese, auf ein Zehntel gerundet."""
        bezug = self._bezug
        hysterese = self._hysterese
        if not bezug or hysterese is None:
            return None
        return round(bezug + self._anteil * hysterese, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Woraus sich der Wert ergibt, damit er nachvollziehbar bleibt."""
        return {
            "sollwert": self.float_value,
            "hysterese": self._hysterese,
            "anteil": self._anteil,
            **self._merk_attribute,
        }


class WindhagerSchaltpunktAbstandSensor(_BezugMerker, WindhagerEntity, SensorEntity):
    """Wie weit die gemessene Temperatur noch vom Schaltpunkt entfernt ist.

    Der Schaltpunkt sagt, *wo* geschaltet wird; für eine Automation zählt,
    *wie weit* es noch dahin ist. Negativ heißt: Die Schwelle ist überschritten.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "K"
    _attr_suggested_display_precision = 1
    _unrecorded_attributes = frozenset({"gemessen", "schaltpunkt", "bezug", "gehalten", "seit"})
    # Der Bezug steht nur an, solange angefordert wird. Ohne ihn bleibt der
    # Abstand leer, die Entität aber bedienbar.
    _require_value_for_available = False

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        self._bezugs_oid = device_info.get("bezugs_oid")
        self._hysterese_oid = device_info.get("ausloeser_oid")
        self._anteil = float(device_info.get("anteil") or 0)
        self._hysterese_vorgabe = zahl_aus_zustand(device_info.get("hysterese_vorgabe"))

    @property
    def _anstehend(self) -> float | None:
        """Eigene Adresse statt der Nachbarentität: Die ist dazuwählbar."""
        return zahl_aus_zustand(get_oid_value(self.coordinator, self._bezugs_oid))

    async def async_added_to_hass(self) -> None:
        """Bezug und Hysterese mit abrufen, sie liegen auf der Serviceebene."""
        await super().async_added_to_hass()
        for oid in (self._bezugs_oid, self._hysterese_oid):
            if oid:
                self.coordinator.client.register_poll_oid(oid)

    async def async_will_remove_from_hass(self) -> None:
        for oid in (self._bezugs_oid, self._hysterese_oid):
            if oid:
                self.coordinator.client.unregister_poll_oid(oid)
        await super().async_will_remove_from_hass()

    @property
    def _schaltpunkt(self) -> float | None:
        """Bezugswert plus Anteil der Hysterese – dieselbe Rechnung wie dort."""
        bezug = self._bezug
        hysterese = zahl_aus_zustand(get_oid_value(self.coordinator, self._hysterese_oid))
        if hysterese is None:
            hysterese = self._hysterese_vorgabe
        if not bezug or hysterese is None:
            return None
        return bezug + self._anteil * hysterese

    @property
    def native_value(self) -> float | None:
        gemessen = self.float_value
        schaltpunkt = self._schaltpunkt
        if gemessen is None or schaltpunkt is None:
            return None
        return round(gemessen - schaltpunkt, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Woraus sich der Abstand ergibt."""
        return {
            "gemessen": self.float_value,
            "schaltpunkt": self._schaltpunkt,
            **self._merk_attribute,
        }


class WindhagerWarmwasserAbstandSensor(WindhagerEntity, SensorEntity):
    """Abstand bis zum nächsten Schaltpunkt der Warmwasserbereitung.

    Positiv heißt: so viele Kelvin bis zum nächsten Schaltpunkt. Negativ
    heißt: Die Schwelle ist überschritten.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "K"
    _attr_suggested_display_precision = 1
    # Ohne Sollwert bleibt der Wert leer, die Entität aber bedienbar.
    _require_value_for_available = False

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        self._soll_oid = device_info.get("soll_oid")
        self._hysterese_oid = device_info.get("hysterese_oid")
        self._zustand_oid = device_info.get("zustand_oid")
        self._hysterese_vorgabe = zahl_aus_zustand(device_info.get("hysterese_vorgabe"))

    async def async_added_to_hass(self) -> None:
        """Die drei Hilfsadressen mit abrufen."""
        await super().async_added_to_hass()
        for oid in (self._soll_oid, self._hysterese_oid, self._zustand_oid):
            if oid:
                self.coordinator.client.register_poll_oid(oid)

    async def async_will_remove_from_hass(self) -> None:
        for oid in (self._soll_oid, self._hysterese_oid, self._zustand_oid):
            if oid:
                self.coordinator.client.unregister_poll_oid(oid)
        await super().async_will_remove_from_hass()

    @property
    def _laedt(self) -> bool:
        """Ob die Ladepumpe läuft. Ohne Wert gilt die wartende Phase.

        Der Rohwert, nicht die Zahl: Die Anlage meldet `0`/`1`, und daraus
        eine Fließkommazahl zu machen verlöre den Vergleich.
        """
        roh = get_oid_raw(self.coordinator, self._zustand_oid)
        if roh is None:
            return False
        return str(roh).strip().lower() in ("1", "on", "true", "ja")

    @property
    def native_value(self) -> float | None:
        ist = self.float_value
        soll = zahl_aus_zustand(get_oid_value(self.coordinator, self._soll_oid))
        if ist is None or soll is None:
            return None
        # Eine Regel für beide Abstände: Kelvin bis zum nächsten Schaltpunkt,
        # negativ heißt überschritten. Während der Ladung ist das der Sollwert,
        # davor der Sollwert abzüglich der Hysterese.
        if self._laedt:
            return round(soll - ist, 1)
        hysterese = zahl_aus_zustand(get_oid_value(self.coordinator, self._hysterese_oid))
        if hysterese is None:
            hysterese = self._hysterese_vorgabe
        if hysterese is None:
            return None
        return round(ist - (soll - hysterese), 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Woraus sich der Abstand ergibt."""
        return {
            "ist": self.float_value,
            "soll": zahl_aus_zustand(get_oid_value(self.coordinator, self._soll_oid)),
            "laedt": self._laedt,
        }
