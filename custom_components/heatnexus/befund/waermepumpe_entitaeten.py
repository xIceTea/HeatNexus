"""Wärmepumpe als Entitäten: Tag der Verdampferreinigung als Datum und als Taste."""

from __future__ import annotations

from datetime import date

from homeassistant.components.button import ButtonEntity
from homeassistant.components.date import DateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .entitaeten import ZielEntitaet, je_ziel_anmelden
from .waermepumpelauf import PFLEGE_ART, WpZiel, ziele_von


class _Verdampfer(ZielEntitaet):
    """Gemeinsamer Teil: der Tag steht im Pflegestand des Archivs, der Bezug beginnt dort neu."""

    _attr_entity_category = EntityCategory.CONFIG
    _ziel: WpZiel

    def _zuletzt(self) -> str | None:
        s = self._sammler
        return s.archiv.pflege_eintrag(self._ziel.prefix, PFLEGE_ART).get("zuletzt") if s else None

    def _setzen(self, tag: date) -> None:
        if (s := self._sammler) is None:
            return
        s.archiv.pflege_setzen(self._ziel.prefix, PFLEGE_ART, {"zuletzt": tag.isoformat()})
        s.speichern()
        s.aktualisieren()


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


@callback
def anmelden_datum(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    """Je Wärmepumpe das Datum der Verdampferreinigung."""
    je_ziel_anmelden(
        hass, entry, add, ziele_von, lambda s, z: [VerdampferGereinigt(s.anlage_id, z)]
    )


@callback
def anmelden_taste(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    """Je Wärmepumpe eine Taste „Verdampfer gereinigt“."""
    je_ziel_anmelden(hass, entry, add, ziele_von, lambda s, z: [VerdampferErledigt(s.anlage_id, z)])
