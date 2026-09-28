"""Das Gerät „HeatNexus Automatik“ je Eintrag: Überblick über alle Automatiken.

Die Automatik je Heizkreis hängt als eigenes Gerät darunter. Das System-Gerät
entsteht mit der ersten Automatik und verschwindet mit der letzten.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN
from . import kennzahlen
from .laufzeit import SIGNAL_SYSTEM, Laufzeit
from .verwaltung import (
    SIGNAL_NEU,
    Verwaltung,
    system_kennung,
    system_unique_id,
    verwaltung_holen,
)

__all__ = ["system_kennung", "system_unique_id"]


class SystemEntitaet(Entity):
    """Grundlage: Kennung, Gerät, Signal des Eintrags."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    ART = ""

    def __init__(self, verwaltung: Verwaltung, entry_id: str) -> None:
        self._verwaltung = verwaltung
        self._entry_id = entry_id
        self._attr_unique_id = system_unique_id(entry_id, self.ART)
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, system_kennung(entry_id))})

    @property
    def _laufzeiten(self) -> list[Laufzeit]:
        return [
            laufzeit
            for laufzeit in self._verwaltung.laufzeiten.values()
            if laufzeit.entry_id == self._entry_id
        ]

    @property
    def available(self) -> bool:
        return bool(self._laufzeiten)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_SYSTEM.format(self._entry_id), self._aktualisiert
            )
        )

    @callback
    def _aktualisiert(self) -> None:
        self.async_write_ha_state()


class SystemStatus(SystemEntitaet, SensorEntity):
    """Der schwerste Zustand aller Automatiken, je Heizkreis als Attribut."""

    ART = "status"
    _attr_translation_key = "automatik_system_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(kennzahlen.STATUS)

    @property
    def native_value(self) -> str | None:
        return kennzahlen.schwerster([kennzahlen.status(lz) for lz in self._laufzeiten])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"heizkreise": {lz.name: kennzahlen.status(lz) for lz in self._laufzeiten}}


class SystemAutomatiken(SystemEntitaet, SensorEntity):
    """Wie viele Automatiken eingerichtet sind."""

    ART = "automatiken"
    _attr_translation_key = "automatik_system_automatiken"

    @property
    def native_value(self) -> int:
        return len(self._laufzeiten)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"heizkreise": [lz.name for lz in self._laufzeiten]}


class SystemEingriffe(SystemEntitaet, SensorEntity):
    """Eingriffe aller Automatiken heute."""

    ART = "eingriffe"
    _attr_translation_key = "automatik_system_eingriffe"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        return sum(kennzahlen.eingriffe_heute(lz) for lz in self._laufzeiten)


class SystemLetzterEingriff(SystemEntitaet, SensorEntity):
    """Der jüngste Eingriff über alle Heizkreise, mit Grund und Heizkreis."""

    ART = "letzter_eingriff"
    _attr_translation_key = "automatik_system_letzter_eingriff"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _unrecorded_attributes = frozenset({"text"})

    def _juengster(self) -> tuple[datetime, str, str] | None:
        kandidaten = [
            (kennzahlen.zeit(eintrag), eintrag["text"], lz.name)
            for lz in self._laufzeiten
            if (eintrag := kennzahlen.letzter_eingriff(lz))
        ]
        return max(kandidaten, key=lambda k: k[0]) if kandidaten else None

    @property
    def native_value(self) -> datetime | None:
        juengster = self._juengster()
        return juengster[0] if juengster else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        juengster = self._juengster()
        return {"text": juengster[1], "heizkreis": juengster[2]} if juengster else {}


class SystemNaechsteEntscheidung(SystemEntitaet, SensorEntity):
    """Die früheste nächste Entscheidung aller Automatiken."""

    ART = "naechste_entscheidung"
    _attr_translation_key = "automatik_system_naechste_entscheidung"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        zeiten = [z for lz in self._laufzeiten if (z := kennzahlen.naechste_entscheidung(lz))]
        return min(zeiten) if zeiten else None


class SystemStoerung(SystemEntitaet, BinarySensorEntity):
    """An, sobald eine Automatik gestört ist."""

    ART = "stoerung"
    _attr_translation_key = "automatik_system_stoerung"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        return any(kennzahlen.gestoert(lz) for lz in self._laufzeiten)


class SystemPrognose(SystemEntitaet, BinarySensorEntity):
    """An, solange jede Automatik eine frische Wetterprognose hat."""

    ART = "prognose"
    _attr_translation_key = "automatik_system_prognose"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        return bool(self._laufzeiten) and all(lz.prognose_frisch for lz in self._laufzeiten)


KLASSEN: dict[str, type[SystemEntitaet]] = {
    "status": SystemStatus,
    "automatiken": SystemAutomatiken,
    "eingriffe": SystemEingriffe,
    "letzter_eingriff": SystemLetzterEingriff,
    "naechste_entscheidung": SystemNaechsteEntscheidung,
    "stoerung": SystemStoerung,
    "prognose": SystemPrognose,
}
BINAER_ARTEN = ("stoerung", "prognose")
SENSOR_ARTEN = tuple(art for art in KLASSEN if art not in BINAER_ARTEN)


@callback
def anmelden(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback, art: str
) -> None:
    """Eine System-Entität anlegen, sobald der Eintrag eine Automatik hat."""
    verwaltung = verwaltung_holen(hass)
    angelegt = False

    @callback
    def _anlegen() -> None:
        nonlocal angelegt
        vorhanden = any(lz.entry_id == entry.entry_id for lz in verwaltung.laufzeiten.values())
        if vorhanden and not angelegt:
            async_add_entities([KLASSEN[art](verwaltung, entry.entry_id)])
        angelegt = vorhanden

    _anlegen()
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEU.format(entry.entry_id), _anlegen)
    )
