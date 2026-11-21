"""Binary sensor platform for the Windhager integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from . import bedingung, texte, waermequelle
from .automatik.entitaeten import anmelden as automatik_anmelden
from .automatik.system import BINAER_ARTEN as SYSTEM_BINAER
from .automatik.system import anmelden as system_anmelden
from .entity import MeldungsQuelle, WindhagerEntity, async_setup_entities
from .helpers import parse_value

# Der Coordinator holt jeden Wert gebündelt, und die Anfragen an die Anlage
# begrenzt der Client über seine eigene Warteschlange. Eine zweite Bremse in
# Home Assistant würde nur den Abruf verzögern, den es gar nicht gibt.
PARALLEL_UPDATES = 0

DEVICE_CLASS_MAP = {
    "problem": BinarySensorDeviceClass.PROBLEM,
    "running": BinarySensorDeviceClass.RUNNING,
    "power": BinarySensorDeviceClass.POWER,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Windhager binary sensors from a config entry."""
    automatik_anmelden(hass, entry, async_add_entities, "stoerung")
    for art in SYSTEM_BINAER:
        system_anmelden(hass, entry, async_add_entities, art)
    async_setup_entities(
        hass,
        entry,
        async_add_entities,
        {
            "binary_sensor": WindhagerBinarySensor,
            "stoerung": WindhagerStoerungBinarySensor,
        },
    )
    # Eine Wärmequelle steht in einem eigenen Subeintrag, nicht im Abzug der
    # Anlage. Ihre Entität gehört zu diesem Subeintrag – nur so führt die
    # Geräteseite zu seinem Ändern-Dialog.
    for coordinator in entry.runtime_data["coordinators"].values():
        for beschreibung in waermequelle.beschreibungen(entry, coordinator):
            async_add_entities(
                [WaermequelleBinarySensor(coordinator, beschreibung)],
                config_subentry_id=beschreibung["subentry_id"],
            )


class WindhagerBinarySensor(WindhagerEntity, BinarySensorEntity):
    """Binary sensor: on when the numeric value is non-zero.

    Pump outputs report their speed (e.g. "100") instead of 1, so any
    value != 0 counts as on.
    """

    def __init__(self, coordinator, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        device_class = device_info.get("device_class")
        if device_class in DEVICE_CLASS_MAP:
            self._attr_device_class = DEVICE_CLASS_MAP[device_class]

    @property
    def _oder_adressen(self) -> list[tuple[str, int | None]]:
        """Vollständige OIDs der zusätzlichen Einschaltquellen, je mit Bit."""
        praefix = self._praefix_der_funktion
        if not praefix:
            return []
        return [
            (f"{praefix}/{q['adresse']}/0", q.get("bit"))
            for q in self._descriptor.get("oder") or []
        ]

    @property
    def _oder_im_abruf(self) -> list[str]:
        """Nur Adressen, die die Anlage führt; eine fehlende kostete jeden Lauf eine Anfrage."""
        bekannt = getattr(self.coordinator.client, "oids", None)
        return [oid for oid, _ in self._oder_adressen if bekannt is None or oid in bekannt]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        for oid in self._oder_im_abruf:
            self.coordinator.client.register_poll_oid(oid)

    async def async_will_remove_from_hass(self) -> None:
        for oid in self._oder_im_abruf:
            self.coordinator.client.unregister_poll_oid(oid)
        await super().async_will_remove_from_hass()

    @property
    def available(self) -> bool:
        # Fehlt der eigene Wert, entscheiden die weiteren Quellen allein.
        return super().available or (
            self.coordinator.last_update_success and bool(self._oder_werte())
        )

    def _eigener_wert(self) -> bool | None:
        value = self.int_value
        if value is None:
            return None
        if (bit := self._descriptor.get("bit")) is not None:
            return bool(value >> int(bit) & 1)
        if (an_bei := self._descriptor.get("an_bei")) is not None:
            return value in an_bei
        return value != 0

    def _oder_werte(self) -> list[bool]:
        werte = (self.coordinator.data or {}).get("oids", {})
        ergebnis = []
        for oid, bit in self._oder_adressen:
            if (zahl := parse_value(werte.get(oid), float, oid)) is None:
                continue
            ergebnis.append(bool(int(zahl) >> int(bit) & 1) if bit is not None else zahl > 0)
        return ergebnis

    @property
    def is_on(self) -> bool | None:
        eigen = self._eigener_wert()
        weitere = self._oder_werte()
        if eigen is None and not weitere:
            return None
        return bool(eigen) or any(weitere)


class WindhagerStoerungBinarySensor(MeldungsQuelle, WindhagerEntity, BinarySensorEntity):
    """Ein an: an diesem Anlagenteil steht eine Störung an.

    Dieselbe Quelle wie der Klartext-Sensor (``FExxmsg``), nur als Ja/Nein mit
    der Geräteklasse ``problem``.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool | None:
        if self._raw is None:
            return None
        return bool(self._meldungen)

    @property
    def extra_state_attributes(self):
        if self._raw is None:
            return None
        msgs = self._meldungen
        # Nur, was eine Meldung braucht. Codes und Rohwert führt der
        # Klartext-Sensor desselben Anlagenteils.
        return {
            "anzahl": len(msgs),
            "stoerungstext": " | ".join(m["text"] for m in msgs),
        }


class WaermequelleBinarySensor(RestoreEntity, BinarySensorEntity):
    """Ein an: diese Wärmequelle liefert gerade Wärme.

    Sie hängt an keinem Datenpunkt der Anlage, sondern an fremden Entitäten
    in Home Assistant. Der vorige Zustand zählt mit: Bedingungen mit
    getrennter Ein- und Ausschaltschwelle brauchen ihn.
    """

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    # Die Entität hängt an Zustandsereignissen, nicht an einem Takt.
    # Abgefragt gäbe es nichts zu holen, geschrieben würde trotzdem.
    _attr_should_poll = False

    def __init__(self, coordinator: Any, beschreibung: dict) -> None:
        self._regel = dict(beschreibung.get("bedingung") or {})
        self._beobachtet = bedingung.quellen(self._regel)
        self._attr_unique_id = beschreibung["id"]
        self._attr_name = texte.woerterbuch_des_koordinators(coordinator)("Wärmelieferung")
        self._attr_device_info = waermequelle.geraet_info(coordinator, beschreibung)
        self._laeuft = False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (letzter := await self.async_get_last_state()) is not None:
            self._laeuft = letzter.state == "on"
        self.async_on_remove(
            async_track_state_change_event(self.hass, self._beobachtet, self._quelle_geaendert)
        )
        self._auswerten()

    @callback
    def _quelle_geaendert(self, event) -> None:
        # Nur ein echter Wechsel gehört in den Verlauf: Ein Leistungssensor
        # meldet im Sekundentakt, ohne dass die Quelle an- oder ausgeht.
        vorher = self._laeuft
        self._auswerten()
        if self._laeuft != vorher:
            self.async_write_ha_state()

    @callback
    def _auswerten(self) -> None:
        """Die Bedingung mit den aktuellen Zuständen prüfen."""
        werte = {
            kennung: zustand.state if (zustand := self.hass.states.get(kennung)) else None
            for kennung in self._beobachtet
        }
        self._laeuft = bedingung.erfuellt(self._regel, werte, self._laeuft)

    @property
    def is_on(self) -> bool:
        return self._laeuft
