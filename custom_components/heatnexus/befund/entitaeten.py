"""Die Werte des Befunds als Sensoren an Heizkreis und Kessel; so führt Home Assistant den Verlauf."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN, SIGNAL_NEUE_ENTITAETEN
from .laufzeit import SIGNAL_NEU, SIGNAL_STAND, befund_holen, unique_id

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


@callback
def anmelden(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Sensoren anlegen, sobald die Sammler des Eintrags stehen; sie starten nach den Plattformen."""
    bekannt: set[str] = set()

    @callback
    def _anlegen() -> None:
        neu = []
        for sammler in befund_holen(hass).sammler.values():
            if sammler.entry.entry_id != entry.entry_id:
                continue
            for kennung, device_id, arten in sammler.geraete():
                for art in arten:
                    if unique_id(device_id, art) not in bekannt:
                        bekannt.add(unique_id(device_id, art))
                        neu.append(BefundSensor(sammler.anlage_id, kennung, device_id, art))
        if neu:
            async_add_entities(neu)

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
