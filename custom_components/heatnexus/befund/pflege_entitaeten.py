"""Pflege als Entitäten: Termin als Datumssensor, letzte Erledigung als Datum, Taste am LogWIN."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.components.date import DateEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import pflege
from .entitaeten import ZielEntitaet, je_ziel_anmelden
from .pflegelauf import pflegeziele_von
from .pflegeziele import Ziel


class _Pflege(ZielEntitaet):
    """Gemeinsamer Teil: Pflegestand des Ziels im Archiv."""

    _ziel: Ziel

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


class PflegeTermin(_Pflege, SensorEntity):
    """Wann die Pflege fällig ist; Rest, Abnahme und Verlässlichkeit als Attribute."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, anlage_id: str, ziel: Ziel) -> None:
        super().__init__(anlage_id, ziel)
        self._attr_unique_id = pflege.befund_kennung(ziel.device_id, f"pflege_{ziel.pflege.art}")
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


def _taste(anlage_id: str, ziel: Ziel) -> list[PflegeErledigt]:
    return [PflegeErledigt(anlage_id, ziel)] if ziel.pflege.weise == pflege.KALENDER else []


@callback
def anmelden_sensor(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    """Je Pflege einen Datumssensor mit dem Termin."""
    je_ziel_anmelden(hass, entry, add, pflegeziele_von, lambda s, z: [PflegeTermin(s.anlage_id, z)])


@callback
def anmelden_datum(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    """Je Pflege ein Datum der letzten Erledigung."""
    je_ziel_anmelden(
        hass, entry, add, pflegeziele_von, lambda s, z: [PflegeZuletzt(s.anlage_id, z)]
    )


@callback
def anmelden_taste(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    """Eine Taste je Pflege ohne Zähler."""
    je_ziel_anmelden(hass, entry, add, pflegeziele_von, lambda s, z: _taste(s.anlage_id, z))
