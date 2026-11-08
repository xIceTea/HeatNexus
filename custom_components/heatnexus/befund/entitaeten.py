"""Die Werte des Befunds als Sensoren an Heizkreis und Kessel; so führt Home Assistant den Verlauf."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN, SIGNAL_NEUE_ENTITAETEN
from .laufzeit import SIGNAL_NEU, SIGNAL_STAND, Sammler, befund_holen, unique_id

# Einheit und Geräteklasse je Art; Energie je Heizgradtag in Kilowattstunden je Kelvintag.
ART: dict[str, tuple[str, SensorDeviceClass | None]] = {
    "waermespeicher": (UnitOfTime.HOURS, SensorDeviceClass.DURATION),
    "heizgrenze": (UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "raeume": ("%", None),
    "naechte": ("K", None),
    "vorlauf": ("%", None),
    "laufzeit": (UnitOfTime.HOURS, SensorDeviceClass.DURATION),
    "starts": ("%", None),
    "energie": ("kWh/Kd", None),
    "abgas": ("K", None),
    "abgasverlust": ("%", None),
    "arbeitszahl": ("%", None),
}


class BefundSensor(SensorEntity):
    """Ein Befund als Zahl; Stand und Verlässlichkeit stehen als Attribute."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, anlage_id: str, kennung: str, device_id: str, art: str) -> None:
        self._anlage_id = anlage_id
        self._kennung = kennung
        self._art = art
        self._attr_unique_id = unique_id(device_id, art)
        self._attr_translation_key = f"befund_{art}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})
        self._attr_native_unit_of_measurement, self._attr_device_class = ART[art]

    @property
    def _befund(self) -> dict[str, Any] | None:
        sammler = befund_holen(self.hass).sammler.get(self._anlage_id)
        return sammler.befund(self._kennung, self._art) if sammler else None

    @property
    def native_value(self) -> float | None:
        return (self._befund or {}).get("wert")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        b = self._befund or {}
        return {"status": b.get("status"), "verlaesslichkeit": b.get("stufe")}

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_STAND.format(self._anlage_id), self.async_write_ha_state
            )
        )


class ZielEntitaet:
    """Gemeinsamer Teil der Befund-Entitäten je Ziel: Sammler, Gerät und Aktualisierung."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, anlage_id: str, ziel: Any) -> None:
        self._anlage_id = anlage_id
        self._ziel = ziel
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, ziel.device_id)})

    @property
    def _sammler(self) -> Sammler | None:
        return befund_holen(self.hass).sammler.get(self._anlage_id)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_STAND.format(self._anlage_id), self.async_write_ha_state
            )
        )


@callback
def je_ziel_anmelden(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add: AddEntitiesCallback,
    ziele_von: Callable[[Any], Iterable[Any]],
    bauen: Callable[[Sammler, Any], Iterable[Any]],
) -> None:
    """Entitäten je Ziel anlegen; `bauen` liefert für ein Ziel keine, eine oder mehrere."""

    def _neu() -> Iterator[tuple[str, Callable[[], Any]]]:
        for sammler in befund_holen(hass).sammler.values():
            if sammler.entry.entry_id == entry.entry_id:
                for ziel in ziele_von(sammler.coordinator):
                    for entitaet in bauen(sammler, ziel):
                        yield entitaet.unique_id, lambda e=entitaet: e

    _anmelden(hass, entry, add, _neu)


@callback
def anmelden(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Sensoren anlegen, sobald die Sammler des Eintrags stehen; sie starten nach den Plattformen."""

    def _neu() -> Iterator[tuple[str, Callable[[], Any]]]:
        for sammler in befund_holen(hass).sammler.values():
            if sammler.entry.entry_id != entry.entry_id:
                continue
            for kennung, device_id, arten in sammler.geraete():
                for art in arten:
                    a = (sammler.anlage_id, kennung, device_id, art)
                    yield unique_id(device_id, art), lambda a=a: BefundSensor(*a)

    _anmelden(hass, entry, async_add_entities, _neu)


def _anmelden(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add: AddEntitiesCallback,
    neu_von: Callable[[], Iterable[tuple[str, Callable[[], Any]]]],
) -> None:
    """Neue Entitäten beim Start, bei neuen Sammlern, neuen Geräten und nach jedem Abruf."""
    bekannt: set[str] = set()

    @callback
    def _anlegen() -> None:
        neu = []
        for kennung, erzeugen in neu_von():
            if kennung not in bekannt:
                bekannt.add(kennung)
                neu.append(erzeugen())
        if neu:
            add(neu)

    _anlegen()
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEU.format(entry.entry_id), _anlegen)
    )
    # Ein Kessel steht erst nach dem ersten Abruf oder Einlesen fest; dann kommen seine Sensoren dazu.
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEUE_ENTITAETEN.format(entry.entry_id), _anlegen)
    )
    koordinatoren = ((getattr(entry, "runtime_data", None) or {}).get("coordinators")) or {}
    for koordinator in koordinatoren.values():
        entry.async_on_unload(koordinator.async_add_listener(_anlegen))
