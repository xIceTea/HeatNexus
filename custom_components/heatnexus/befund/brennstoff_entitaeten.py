"""Brennstoff als Entitäten: Vorrat mit Lieferdienst, Heizwert bzw. Füllmenge, Datum „reicht bis“."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from ..const import DOMAIN, SIGNAL_NEUE_ENTITAETEN
from . import brennstoff
from .abgasziele import AbgasZiel
from .brennstofflauf import einstellung, liefern, vorgabe, ziele_von
from .laufzeit import SIGNAL_NEU, SIGNAL_STAND, Sammler, befund_holen


class _Lager:
    """Gemeinsamer Teil: Sammler, Kessel, Lager und Aktualisierung über das Befund-Signal."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, anlage_id: str, ziel: AbgasZiel) -> None:
        self._anlage_id = anlage_id
        self._ziel = ziel
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, ziel.device_id)})

    @property
    def _sammler(self) -> Sammler | None:
        return befund_holen(self.hass).sammler.get(self._anlage_id)

    def _vorgabe(self) -> dict[str, Any]:
        s = self._sammler
        return vorgabe(s.coordinator, self._ziel) if s else {}

    def _lager(self) -> dict[str, Any]:
        s = self._sammler
        return self._vorgabe() | (s.archiv.lager(self._ziel.prefix) if s else {})

    def _befund(self) -> dict[str, Any]:
        s = self._sammler
        return (s.befund(self._ziel.device_id, "brennstoff") if s else None) or {}

    def _speichern(self, lager: dict[str, Any]) -> None:
        if (s := self._sammler) is None:
            return
        s.archiv.lager_setzen(self._ziel.prefix, lager)
        s.speichern()
        s.aktualisieren()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_STAND.format(self._anlage_id), self.async_write_ha_state
            )
        )


class BrennstoffReichweite(_Lager, SensorEntity):
    """Bis wann der Vorrat reicht; Vorrat, Verbrauch und Korrektur als Attribute."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, anlage_id: str, ziel: AbgasZiel) -> None:
        super().__init__(anlage_id, ziel)
        self._attr_unique_id = f"{ziel.device_id}-befund-brennstoff"
        self._attr_translation_key = "befund_brennstoff"

    @property
    def native_value(self) -> date | None:
        datum = (self._befund().get("angaben") or {}).get("datum")
        return date.fromisoformat(datum) if datum else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        b = self._befund()
        a = b.get("angaben") or {}
        return {
            "status": b.get("status"),
            "verlaesslichkeit": b.get("stufe"),
            **{k: a.get(k) for k in ("bestand", "einheit", "je_tag", "korrektur")},
        }


class BrennstoffVorrat(_Lager, NumberEntity):
    """Der Vorrat im Lager; ein gezählter Stand und der Dienst `brennstoff_geliefert` lernen dazu."""

    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0.0
    _attr_native_max_value = 100000.0
    _attr_native_step = 0.01

    def __init__(self, anlage_id: str, ziel: AbgasZiel) -> None:
        super().__init__(anlage_id, ziel)
        self._attr_unique_id = f"{ziel.device_id}-brennstoffvorrat"
        self._attr_translation_key = "brennstoffvorrat"

    @property
    def native_unit_of_measurement(self) -> str | None:
        return brennstoff.EINHEIT.get(self._vorgabe().get("art", "pellets"))

    @property
    def native_value(self) -> float | None:
        return (self._befund().get("angaben") or {}).get("bestand")

    async def async_set_native_value(self, value: float) -> None:
        # Ein gezählter Stand ist eine Befüllung ohne Menge: Der Rest korrigiert die Rechnung.
        await self.async_geliefert(menge=0.0, rest=float(value))

    async def async_geliefert(self, menge: float, rest: float | None = None) -> None:
        if (s := self._sammler) is None:
            return
        liefern(s.archiv, self._ziel.prefix, self._vorgabe(), menge, rest, dt_util.now().date())
        s.speichern()
        s.aktualisieren()


class BrennstoffEinstellung(_Lager, NumberEntity):
    """Heizwert je Lagereinheit oder, am LogWIN, Füllmenge je Anheizvorgang."""

    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0.0
    _attr_native_max_value = 10000.0
    _attr_native_step = 1.0

    def __init__(self, anlage_id: str, ziel: AbgasZiel) -> None:
        super().__init__(anlage_id, ziel)
        self._schluessel = "fuellmenge" if ziel.logwin else "heizwert"
        self._attr_unique_id = f"{ziel.device_id}-brennstoff-{self._schluessel}"
        self._attr_translation_key = f"brennstoff_{self._schluessel}"

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self._ziel.logwin:
            return "kg"
        return f"kWh/{brennstoff.EINHEIT.get(self._vorgabe().get('art', 'pellets'))}"

    @property
    def native_value(self) -> float | None:
        lager = self._lager()
        if self._schluessel in lager:
            return lager[self._schluessel]
        return brennstoff.HEIZWERT.get(lager.get("art", "pellets"))

    async def async_set_native_value(self, value: float) -> None:
        lager = self._sammler.archiv.lager(self._ziel.prefix) if self._sammler else {}
        self._speichern(lager | {self._schluessel: float(value)})


def _anmelden(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add: AddEntitiesCallback,
    bauen: Callable[[Sammler, AbgasZiel], list[Any]],
) -> None:
    bekannt: set[str] = set()

    @callback
    def _anlegen() -> None:
        neu = []
        for sammler in befund_holen(hass).sammler.values():
            if sammler.entry.entry_id != entry.entry_id:
                continue
            for ziel in ziele_von(sammler.coordinator):
                for entitaet in bauen(sammler, ziel):
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
def anmelden_sensor(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    """Je Kessel mit Lager das Datum „reicht bis“."""
    _anmelden(hass, entry, add, lambda s, z: [BrennstoffReichweite(s.anlage_id, z)])


@callback
def anmelden_number(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    """Je Kessel mit Lager Vorrat und Heizwert bzw. Füllmenge."""
    _anmelden(hass, entry, add, _zahlen)


def _zahlen(sammler: Sammler, ziel: AbgasZiel) -> list[Any]:
    """Der Vorrat immer; Heizwert bzw. Füllmenge nur, wo die Rechnung sie braucht."""
    zahlen: list[Any] = [BrennstoffVorrat(sammler.anlage_id, ziel)]
    if einstellung(sammler.coordinator, ziel):
        zahlen.append(BrennstoffEinstellung(sammler.anlage_id, ziel))
    return zahlen
