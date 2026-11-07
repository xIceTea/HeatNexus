"""Wärmepumpe als Entitäten: Tag der Verdampferreinigung als Datum und als Taste."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.components.date import DateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from ..const import DOMAIN, SIGNAL_NEUE_ENTITAETEN
from .laufzeit import SIGNAL_NEU, SIGNAL_STAND, Sammler, befund_holen
from .waermepumpelauf import PFLEGE_ART, WpZiel, ziele_von


class _Verdampfer:
    """Gemeinsamer Teil: der Tag steht im Pflegestand des Archivs, der Bezug beginnt dort neu."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, anlage_id: str, ziel: WpZiel) -> None:
        self._anlage_id = anlage_id
        self._ziel = ziel
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, ziel.device_id)})

    @property
    def _sammler(self) -> Sammler | None:
        return befund_holen(self.hass).sammler.get(self._anlage_id)

    def _zuletzt(self) -> str | None:
        s = self._sammler
        return s.archiv.pflege_eintrag(self._ziel.prefix, PFLEGE_ART).get("zuletzt") if s else None

    def _setzen(self, tag: date) -> None:
        if (s := self._sammler) is None:
            return
        s.archiv.pflege_setzen(self._ziel.prefix, PFLEGE_ART, {"zuletzt": tag.isoformat()})
        s.speichern()
        s.aktualisieren()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_STAND.format(self._anlage_id), self.async_write_ha_state
            )
        )


class VerdampferGereinigt(_Verdampfer, DateEntity):
    """Wann der Verdampfer zuletzt gereinigt wurde."""

    def __init__(self, anlage_id: str, ziel: WpZiel) -> None:
        super().__init__(anlage_id, ziel)
        self._attr_unique_id = f"{ziel.device_id}-verdampfer-zuletzt"
        self._attr_translation_key = "verdampfer_zuletzt"

    @property
    def native_value(self) -> date | None:
        zuletzt = self._zuletzt()
        return date.fromisoformat(zuletzt) if zuletzt else None

    async def async_set_value(self, value: date) -> None:
        self._setzen(value)


class VerdampferErledigt(_Verdampfer, ButtonEntity):
    """Die Taste trägt heute als Tag der Verdampferreinigung ein."""

    def __init__(self, anlage_id: str, ziel: WpZiel) -> None:
        super().__init__(anlage_id, ziel)
        self._attr_unique_id = f"{ziel.device_id}-verdampfer-erledigt"
        self._attr_translation_key = "verdampfer_erledigt"

    async def async_press(self) -> None:
        self._setzen(dt_util.now().date())


def _anmelden(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add: AddEntitiesCallback,
    bauen: Callable[[str, WpZiel], Any],
) -> None:
    bekannt: set[str] = set()

    @callback
    def _anlegen() -> None:
        neu = []
        for sammler in befund_holen(hass).sammler.values():
            if sammler.entry.entry_id != entry.entry_id:
                continue
            for ziel in ziele_von(sammler.coordinator):
                entitaet = bauen(sammler.anlage_id, ziel)
                if entitaet.unique_id not in bekannt:
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
def anmelden_datum(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    """Je Wärmepumpe das Datum der Verdampferreinigung."""
    _anmelden(hass, entry, add, VerdampferGereinigt)


@callback
def anmelden_taste(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    """Je Wärmepumpe eine Taste „Verdampfer gereinigt“."""
    _anmelden(hass, entry, add, VerdampferErledigt)
