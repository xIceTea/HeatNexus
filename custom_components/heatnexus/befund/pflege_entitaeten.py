"""Pflege als Entitäten: Termin als Datumssensor, letzte Erledigung als Datum, Taste am LogWIN."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.components.date import DateEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from ..const import DOMAIN, SIGNAL_NEUE_ENTITAETEN
from . import pflege
from .laufzeit import SIGNAL_NEU, SIGNAL_STAND, Sammler, befund_holen
from .pflegelauf import pflegeziele_von
from .pflegeziele import Ziel


class _Pflege:
    """Gemeinsamer Teil: Sammler, Ziel, Gerät und Aktualisierung über das Befund-Signal."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, anlage_id: str, ziel: Ziel) -> None:
        self._anlage_id = anlage_id
        self._ziel = ziel
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, ziel.device_id)})

    @property
    def _sammler(self) -> Sammler | None:
        return befund_holen(self.hass).sammler.get(self._anlage_id)

    def _eintrag(self) -> dict[str, Any]:
        s = self._sammler
        return s.archiv.pflege_eintrag(self._ziel.prefix, self._ziel.pflege.art) if s else {}

    def _zuletzt_setzen(self, tag: date) -> None:
        if (s := self._sammler) is None:
            return
        eintrag = self._eintrag() | {"zuletzt": tag.isoformat(), "gemeldet": None}
        s.archiv.pflege_setzen(self._ziel.prefix, self._ziel.pflege.art, eintrag)
        s.speichern()
        s.aktualisieren()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_STAND.format(self._anlage_id), self.async_write_ha_state
            )
        )


class PflegeTermin(_Pflege, SensorEntity):
    """Wann die Pflege fällig ist; Rest, Abnahme und Verlässlichkeit als Attribute."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, anlage_id: str, ziel: Ziel) -> None:
        super().__init__(anlage_id, ziel)
        self._attr_unique_id = f"{ziel.device_id}-befund-pflege-{ziel.pflege.art}"
        self._attr_translation_key = f"befund_pflege_{ziel.pflege.art}"

    @property
    def _befund(self) -> dict[str, Any]:
        s = self._sammler
        art = f"pflege_{self._ziel.pflege.art}"
        return (s.befund(self._ziel.device_id, art) if s else None) or {}

    @property
    def native_value(self) -> date | None:
        datum = (self._befund.get("angaben") or {}).get("datum")
        return date.fromisoformat(datum) if datum else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        b = self._befund
        a = b.get("angaben") or {}
        return {
            "status": b.get("status"),
            "verlaesslichkeit": b.get("stufe"),
            "rest_h": a.get("rest_h"),
            "abnahme_je_tag": a.get("abnahme_je_tag"),
            "zuletzt": a.get("zuletzt"),
        }


class PflegeZuletzt(_Pflege, DateEntity):
    """Wann die Pflege zuletzt erledigt wurde; von Hand setzbar, ein erkannter Sprung überschreibt."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, anlage_id: str, ziel: Ziel) -> None:
        super().__init__(anlage_id, ziel)
        self._attr_unique_id = f"{ziel.device_id}-pflege-{ziel.pflege.art}-zuletzt"
        self._attr_translation_key = f"pflege_{ziel.pflege.art}_zuletzt"

    @property
    def native_value(self) -> date | None:
        zuletzt = self._eintrag().get("zuletzt")
        return date.fromisoformat(zuletzt) if zuletzt else None

    async def async_set_value(self, value: date) -> None:
        self._zuletzt_setzen(value)


class PflegeErledigt(_Pflege, ButtonEntity):
    """Pflege ohne Zähler: die Taste trägt heute als letzte Erledigung ein."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, anlage_id: str, ziel: Ziel) -> None:
        super().__init__(anlage_id, ziel)
        self._attr_unique_id = f"{ziel.device_id}-pflege-{ziel.pflege.art}-erledigt"
        self._attr_translation_key = f"pflege_{ziel.pflege.art}_erledigt"

    async def async_press(self) -> None:
        self._zuletzt_setzen(dt_util.now().date())


def _taste(anlage_id: str, ziel: Ziel) -> PflegeErledigt | None:
    return PflegeErledigt(anlage_id, ziel) if ziel.pflege.weise == pflege.KALENDER else None


def _anmelden(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add: AddEntitiesCallback,
    bauen: Callable[[str, Ziel], Any],
) -> None:
    bekannt: set[str] = set()

    @callback
    def _anlegen() -> None:
        neu = []
        for sammler in befund_holen(hass).sammler.values():
            if sammler.entry.entry_id != entry.entry_id:
                continue
            for ziel in pflegeziele_von(sammler.coordinator):
                entitaet = bauen(sammler.anlage_id, ziel)
                if entitaet is not None and entitaet.unique_id not in bekannt:
                    bekannt.add(entitaet.unique_id)
                    neu.append(entitaet)
        if neu:
            add(neu)

    _anlegen()
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEU.format(entry.entry_id), _anlegen)
    )
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEUE_ENTITAETEN.format(entry.entry_id), _anlegen)
    )


@callback
def anmelden_sensor(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    """Je Pflege einen Datumssensor mit dem Termin."""
    _anmelden(hass, entry, add, PflegeTermin)


@callback
def anmelden_datum(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    """Je Pflege ein Datum der letzten Erledigung."""
    _anmelden(hass, entry, add, PflegeZuletzt)


@callback
def anmelden_taste(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    """Eine Taste je Pflege ohne Zähler."""
    _anmelden(hass, entry, add, _taste)
