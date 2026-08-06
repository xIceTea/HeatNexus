"""Shared base entity for the Windhager integration."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ENUMS,
    FCT_MODELL,
    NACHFASS_ANZAHL,
    NACHFASS_INTERVALL,
    OID_HARDWAREVERSION,
    OID_SOFTWAREVERSION,
    SIGNAL_NEUE_ENTITAETEN,
)
from .device_db import get_enum
from .helpers import parse_value

_LOGGER = logging.getLogger(__name__)

CATEGORY_MAP = {
    "diagnostic": EntityCategory.DIAGNOSTIC,
    "config": EntityCategory.CONFIG,
}

# Nur lesbare Entitäten dürfen nicht als "Konfiguration" eingeordnet werden –
# Home Assistant weist sie sonst beim Anlegen zurück.
NUR_LESEND = {
    "sensor",
    "temperature",
    "enum_sensor",
    "string_sensor",
    "error_sensor",
    "time_program",
    "device_status",
    "message_text",
    "binary_sensor",
    "total",
    "total_increasing",
}


@callback
def async_setup_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    klassen: dict[str, type],
) -> None:
    """Entitäten einer Plattform anlegen – auch später nachgemeldete.

    Beim Einrichten sind zunächst nur die Kerndatenpunkte bekannt; der
    vollständige Abzug der Anlage läuft im Hintergrund weiter. Sobald er
    fertig ist, werden die zusätzlich gefundenen Entitäten nachgereicht.
    """
    coordinators = hass.data[DOMAIN][entry.entry_id]["coordinators"]
    bekannt: set[str] = set()

    @callback
    def _anlegen() -> None:
        neu = []
        for coordinator in coordinators.values():
            for beschreibung in (coordinator.data or {}).get("devices", []):
                klasse = klassen.get(beschreibung.get("type"))
                kennung = beschreibung.get("id")
                if klasse is None or not kennung or kennung in bekannt:
                    continue
                bekannt.add(kennung)
                neu.append(klasse(coordinator, beschreibung))
        if neu:
            async_add_entities(neu)

    _anlegen()
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEUE_ENTITAETEN.format(entry.entry_id), _anlegen)
    )


def _modulwert(coordinator: Any, beschreibung: dict, gn_mn: str) -> str | None:
    """Einen Datenpunkt lesen, den jedes Modul über sich selbst führt.

    Software- und Hardwarestand kommen über den `object`-Endpunkt und stehen
    als Text im Abruf. Fehlt der Wert – etwa weil die Anlage noch eingelesen
    wird –, bleibt das Feld leer, statt eine Null zu behaupten.
    """
    prefix = beschreibung.get("prefix")
    if not prefix or not getattr(coordinator, "data", None):
        return None
    wert = coordinator.data.get("oids", {}).get(f"{prefix}/{gn_mn}/0")
    return str(wert).strip() or None if wert not in (None, "") else None


def _seriennummer(coordinator: Any, beschreibung: dict) -> str | None:
    """Die `neuronId` des Knotens, an dem diese Funktion hängt.

    Sie bildet ohnehin schon jede Entitätskennung – sie steht nur bisher
    nirgends, wo man sie ablesen könnte.
    """
    prefix = beschreibung.get("prefix") or ""
    teile = prefix.split("/")
    if len(teile) < 3:
        return None
    return (getattr(coordinator.client, "neuron_by_node", None) or {}).get(teile[2])


def geraet_info(coordinator: Any, beschreibung: dict) -> DeviceInfo:
    """Gerätezuordnung einer Entität.

    Aufbau: Heizungsanlage (Konfigurationseintrag) → Steuerung (Adresse) →
    Funktion (Kessel, Heizkreis, Puffer …), an der die Entität hängt.
    """
    funktion = (beschreibung.get("device_name") or "").strip()
    steuerung = (getattr(coordinator, "label", "") or "").strip()
    # Der Steuerungsname vorne hält die Geräteliste sortiert und macht
    # gleichnamige Funktionen zweier Steuerungen unterscheidbar.
    name = f"{steuerung} · {funktion}" if steuerung and steuerung != funktion else funktion
    fct_type = beschreibung.get("fct_type")
    info = DeviceInfo(
        identifiers={(DOMAIN, beschreibung.get("device_id"))},
        name=name,
        manufacturer="Windhager",
        # Der von Hand vergebene Anlagenname steht schon oben; als Modell
        # gehört dorthin, **was** das Gerät ist.
        model=FCT_MODELL.get(fct_type) or funktion,
        via_device=(DOMAIN, steuerung_kennung(coordinator)),
    )
    if seriennummer := _seriennummer(coordinator, beschreibung):
        info["serial_number"] = seriennummer
    if software := _modulwert(coordinator, beschreibung, OID_SOFTWAREVERSION):
        info["sw_version"] = software
    if hardware := _modulwert(coordinator, beschreibung, OID_HARDWAREVERSION):
        info["hw_version"] = hardware
    return info


def steuerung_kennung(coordinator: Any) -> str:
    """Kennung des Steuerungs-Geräts, an dem die Funktionen hängen.

    Vorzugsweise aus den Seriennummern der Anlage; erst wenn die noch nicht
    gelesen sind, bleibt die Adresse als Rückfall.
    """
    eigene = getattr(coordinator.client, "steuerung_kennung", None)
    if callable(eigene) and (kennung := eigene()):
        return kennung
    return f"{coordinator.entry.entry_id}_{coordinator.host}"


class WindhagerEntity(CoordinatorEntity, RestoreEntity):
    """Base entity bound to one OID descriptor from the client.

    ``has_entity_name`` bedeutet: Der hier gesetzte Name ist der Name des
    Datenpunkts allein ("Kesseltemperatur Ist"). Den Gerätenamen stellt Home
    Assistant selbst voran – in der Anzeige wie in der ``entity_id``. Erst
    dadurch heißt eine Entität ``sensor.heizhaus_purowin_kesseltemperatur_ist``
    statt ``sensor.kesseltemperatur_ist_4``.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator)
        self._descriptor = device_info
        self._alter_zustand: str | None = None
        self._oid = device_info.get("oid")
        self._attr_unique_id = device_info.get("id")
        self._attr_name = device_info.get("name")
        if device_info.get("icon"):
            self._attr_icon = device_info["icon"]
        if device_info.get("enabled_default") is False:
            self._attr_entity_registry_enabled_default = False
        category = device_info.get("category")
        if category == "config" and device_info.get("type") in NUR_LESEND:
            # Nur lesbare Werte dürfen nicht als "Konfiguration" gelten – und
            # sie sind auch keine Gerätediagnose, sondern ganz normale
            # Messwerte (Heizkurve, Grenzwerte). Also ohne Einordnung.
            category = None
        if category in CATEGORY_MAP:
            self._attr_entity_category = CATEGORY_MAP[category]
        self._attr_device_info = geraet_info(coordinator, device_info)

    # Zeitprogramme werden über den object-Endpunkt gelesen, nicht über das
    # OID-Polling – solche Entities setzen das Flag auf False.
    _register_poll_oid = True

    # Nur-lesende Sensoren zeigen nach einem Neustart ihren letzten Wert, bis
    # der erste Abruf durch ist. Für bedienbare Entitäten ist das nichts: Ein
    # wiederhergestellter Sollwert, der nicht dem der Anlage entspricht, ist
    # schlimmer als ein leeres Feld.
    _wiederherstellbar = False

    # ------------------------------------------------------------------
    async def async_added_to_hass(self) -> None:
        """Beim Aktivieren der Entity ihre OID zum Polling anmelden.

        HA fügt nur tatsächlich aktivierte Entities hinzu – deaktivierte
        (z.B. Service-Datenpunkte) registrieren sich daher nicht und werden
        nicht gepollt. Aktiviert der Nutzer eine Service-Entity, wird ihre
        OID hier registriert und ab dem nächsten Poll mit abgefragt.

        Außerdem wird hier der zuletzt bekannte Zustand geholt: Nach einem
        Neustart von Home Assistant stünde sonst bis zum ersten Abruf überall
        „nicht verfügbar".
        """
        await super().async_added_to_hass()
        if self._register_poll_oid and self._oid:
            self.coordinator.client.register_poll_oid(self._oid)
            # **Den einen Wert sofort holen, nicht erst beim nächsten Takt.**
            # Wer eine abgeschaltete Entität einschaltet, lädt damit den ganzen
            # Eintrag neu – und sah danach bis zu dreißig Sekunden lang „nicht
            # verfügbar", obwohl alle anderen Werte längst standen. Gelesen wird
            # nur diese Adresse; der Rest kommt mit dem regulären Abruf.
            self._wert_sofort_holen()
        if not self._wiederherstellbar:
            return
        alt = await self.async_get_last_state()
        if alt is not None and alt.state not in (None, "", "unknown", "unavailable"):
            self._alter_zustand = alt.state

    # ------------------------------------------------------------------
    @property
    def letzter_zustand(self) -> str | None:
        """Der Zustand vor dem Neustart – nur solange die Anlage schweigt.

        Sobald ein eigener Wert vorliegt, gilt ausschließlich dieser. Ein
        gespeicherter Zustand darf einen frischen niemals überstimmen.
        """
        if self.raw_value is not None:
            return None
        return self._alter_zustand

    async def async_will_remove_from_hass(self) -> None:
        """Beim Entfernen/Deaktivieren die OID wieder abmelden."""
        if self._register_poll_oid and self._oid:
            self.coordinator.client.unregister_poll_oid(self._oid)
        await super().async_will_remove_from_hass()

    @property
    def raw_value(self) -> str | None:
        """Raw string value of this entity's OID."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("oids", {}).get(self._oid)

    @property
    def float_value(self) -> float | None:
        return parse_value(self.raw_value, float, self._oid)

    @property
    def int_value(self) -> int | None:
        return parse_value(self.raw_value, int, self._oid)

    @property
    def enum_map(self) -> dict[int, str]:
        key = self._descriptor.get("enum") or ""
        return ENUMS.get(key) or get_enum(key) or {}

    # Writable platforms set this to False so write-only datapoints
    # (readable only with 409/Conflict, e.g. 39/95) stay operable.
    _require_value_for_available = True

    @property
    def available(self) -> bool:
        if not self._require_value_for_available:
            return super().available
        if self.raw_value is not None:
            return super().available
        # Der wiederhergestellte Zustand ist ein Wert – sonst wäre die Entität
        # nach einem Neustart „nicht verfügbar" und zeigte ihn gar nicht erst.
        return super().available and self._alter_zustand is not None

    async def _async_write(self, value: str) -> None:
        """Write a value to this entity's OID and refresh."""
        await self.coordinator.client.update(self._oid, value)
        await self.coordinator.async_request_refresh()
        self._nachfassen(value)

    # ------------------------------------------------------------------
    def _wert_sofort_holen(self) -> None:
        """Die eigene Adresse einmal lesen, ohne auf den Takt zu warten.

        Nur, wenn noch kein Wert vorliegt: Nach einem gewöhnlichen Neustart
        steht er längst in den Abrufdaten, und ein zweiter Zugriff wäre eine
        Anfrage an die Anlage ohne jeden Gewinn.
        """
        if not self.hass or not self._oid:
            return
        vorhanden = (self.coordinator.data or {}).get("oids", {})
        if self._oid in vorhanden:
            return
        self.hass.async_create_task(self._sofort_lauf())

    async def _sofort_lauf(self) -> None:
        try:
            aktuell = await self.coordinator.client.fetch_oids([self._oid])
        except Exception as err:
            _LOGGER.debug("Sofortabruf für %s fehlgeschlagen: %s", self._oid, err)
            return
        daten = self.coordinator.data
        if daten is None or not aktuell or not self.hass:
            return
        daten.setdefault("oids", {}).update(aktuell)
        with contextlib.suppress(Exception):
            self.coordinator.async_update_listeners()

    def _nachfassen(self, erwartet: str | None = None) -> None:
        """Den geschriebenen Datenpunkt kurz engmaschig nachlesen.

        Die Anlage nimmt einen Auftrag entgegen und arbeitet ihn ab; der
        Abruf unmittelbar danach liest deshalb oft noch den alten Wert. Ohne
        Nachfassen stünde bis zum nächsten Takt der alte Stand da, und die
        Bedienung wirkte folgenlos.

        Gelesen wird nur diese eine Adresse – nicht das ganze Poll-Set.
        """
        if not self._oid or not self.hass:
            return
        self.hass.async_create_task(self._nachfass_lauf(erwartet))

    async def _nachfass_lauf(self, erwartet: str | None) -> None:
        for _ in range(NACHFASS_ANZAHL):
            await asyncio.sleep(NACHFASS_INTERVALL)
            if not self.hass:
                return
            try:
                aktuell = await self.coordinator.client.fetch_oids([self._oid])
            except Exception as err:
                _LOGGER.debug("Nachfassen für %s fehlgeschlagen: %s", self._oid, err)
                return
            daten = self.coordinator.data
            if daten is None or not aktuell:
                continue
            daten.setdefault("oids", {}).update(aktuell)
            with contextlib.suppress(Exception):
                self.coordinator.async_update_listeners()
            # Sobald die Anlage den erwarteten Wert meldet, ist nichts mehr
            # nachzufassen.
            if erwartet is not None and str(aktuell.get(self._oid)) == str(erwartet):
                return
