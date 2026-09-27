"""Schalter, Modus und Zustand der Automatik als Entitäten am Heizkreis.

Sie hängen am vorhandenen Heizkreis-Gerät und folgen der Laufzeit über ein
Signal; abgefragt wird nichts.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN
from .konfig import MODI
from .laufzeit import SIGNAL_AKTUALISIERT, Laufzeit
from .regel import Zustand
from .verwaltung import SIGNAL_NEU, Verwaltung, unique_id, verwaltung_holen


class AutomatikEntitaet(Entity):
    """Gemeinsame Grundlage: Kennung, Gerät, Signal."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    ART = ""

    def __init__(self, verwaltung: Verwaltung, device_id: str) -> None:
        self._verwaltung = verwaltung
        self._device_id = device_id
        self._attr_unique_id = unique_id(device_id, self.ART)
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def _laufzeit(self) -> Laufzeit | None:
        return self._verwaltung.laufzeiten.get(self._device_id)

    @property
    def available(self) -> bool:
        return self._laufzeit is not None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_AKTUALISIERT.format(self._device_id), self._aktualisiert
            )
        )

    @callback
    def _aktualisiert(self) -> None:
        self.async_write_ha_state()


class AutomatikSchalter(AutomatikEntitaet, SwitchEntity):
    """Automatik an oder aus."""

    ART = "schalter"
    _attr_translation_key = "automatik"

    @property
    def is_on(self) -> bool | None:
        return self._laufzeit.aktiv if self._laufzeit else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._verwaltung.einstellen(self._device_id, {"aktiv": True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._verwaltung.einstellen(self._device_id, {"aktiv": False})


class AutomatikModus(AutomatikEntitaet, SelectEntity):
    """Beobachten oder Schalten."""

    ART = "modus"
    _attr_translation_key = "automatik_modus"
    _attr_options = list(MODI)

    @property
    def current_option(self) -> str | None:
        return self._laufzeit.konfig.get("modus") if self._laufzeit else None

    async def async_select_option(self, option: str) -> None:
        await self._verwaltung.einstellen(self._device_id, {"modus": option})


class AutomatikZustand(AutomatikEntitaet, SensorEntity):
    """Was die Automatik gerade tut, mit Begründung."""

    ART = "zustand"
    _attr_translation_key = "automatik_zustand"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [zustand.value for zustand in Zustand]
    # Der Satz ändert sich mit jeder Messung; im Verlauf wäre er nur Ballast.
    _unrecorded_attributes = frozenset({"begruendung"})

    @property
    def native_value(self) -> str | None:
        return self._laufzeit.zustand.value if self._laufzeit else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        laufzeit = self._laufzeit
        if laufzeit is None:
            return {}
        return {
            "begruendung": laufzeit.begruendung,
            "pausiert_bis": laufzeit.pausiert_bis.isoformat() if laufzeit.pausiert_bis else None,
            "eingriffe_heute": laufzeit.steller.stand.eingriffe,
        }


KLASSEN: dict[str, type[AutomatikEntitaet]] = {
    "schalter": AutomatikSchalter,
    "modus": AutomatikModus,
    "zustand": AutomatikZustand,
}


@callback
def anmelden(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback, art: str
) -> None:
    """Entitäten einer Art anlegen – jetzt und für später eingerichtete Automatiken."""
    verwaltung = verwaltung_holen(hass)
    bekannt: set[str] = set()

    @callback
    def _anlegen() -> None:
        eigene = {
            device_id
            for device_id, laufzeit in verwaltung.laufzeiten.items()
            if laufzeit.entry_id == entry.entry_id
        }
        bekannt.intersection_update(eigene)
        neu = [KLASSEN[art](verwaltung, device_id) for device_id in eigene - bekannt]
        bekannt.update(eigene)
        if neu:
            async_add_entities(neu)

    _anlegen()
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEU.format(entry.entry_id), _anlegen)
    )
