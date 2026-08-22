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
from .error_texts import parse_messages
from .helpers import parse_value
from .lon import ungueltig as lon_ungueltig

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
    "stoerung",
    "binary_sensor",
    "total",
    "total_increasing",
    "zaehler_heute",
    "zaehler_start",
    "laufzeit",
    "laufzeit_heute",
}


# Welche Domäne eine Art von Datenpunkt bekommt. Wird beim Anlegen der
# Plattformen gefüllt, damit die Zuordnung nicht doppelt gepflegt wird.
TYP_DOMAENE: dict[str, str] = {}


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
    # Die Klasse steht in der Datei ihrer Plattform – daraus kommt die Domäne.
    for typ, klasse in klassen.items():
        TYP_DOMAENE[typ] = klasse.__module__.rsplit(".", 1)[-1]

    coordinators = entry.runtime_data["coordinators"]
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


def _funktionspraefix(beschreibung: dict) -> str | None:
    """Der Funktionspräfix `/1/<Knoten>/<Funktion>` einer Beschreibung.

    Das Feld ``prefix`` führt nur die Thermostat-Beschreibung; alle übrigen
    tragen ihre Adresse allein in der OID. Sie hat die Form
    `/1/<Knoten>/<Funktion>/<gn>/<mn>/<idx>` – ein knotenweiter Datenpunkt
    dagegen `/1/<Knoten>/<gn>/<mn>/<idx>` und damit **keinen** Funktionsteil.
    Genau daran wird unterschieden.
    """
    if prefix := beschreibung.get("prefix"):
        return prefix
    teile = str(beschreibung.get("oid") or "").strip("/").split("/")
    return "/" + "/".join(teile[:3]) if len(teile) == 6 else None


def _knoten(beschreibung: dict) -> str | None:
    """Die Knotennummer, an der diese Beschreibung hängt."""
    quelle = beschreibung.get("prefix") or beschreibung.get("oid") or ""
    teile = str(quelle).strip("/").split("/")
    return teile[1] if len(teile) >= 2 else None


def _modulwert(coordinator: Any, beschreibung: dict, gn_mn: str) -> str | None:
    """Einen Datenpunkt lesen, den jedes Modul über sich selbst führt.

    Software- und Hardwarestand stehen als Text im Abruf. Fehlt der Wert – etwa
    weil die Anlage noch eingelesen wird –, bleibt das Feld leer, statt eine
    Null zu behaupten.
    """
    prefix = _funktionspraefix(beschreibung)
    if not prefix or not getattr(coordinator, "data", None):
        return None
    wert = coordinator.data.get("oids", {}).get(f"{prefix}/{gn_mn}/0")
    return str(wert).strip() or None if wert not in (None, "") else None


def _seriennummer(coordinator: Any, beschreibung: dict) -> str | None:
    """Die `neuronId` des Knotens, an dem diese Funktion hängt.

    Sie bildet ohnehin schon jede Entitätskennung – sie steht nur bisher
    nirgends, wo man sie ablesen könnte.
    """
    if (knoten := _knoten(beschreibung)) is None:
        return None
    return (getattr(coordinator.client, "neuron_by_node", None) or {}).get(knoten)


def _werksbezeichnung(coordinator: Any, beschreibung: dict) -> str | None:
    """Wie der Hersteller den Baustein nennt, an dem diese Funktion hängt."""
    if (knoten := _knoten(beschreibung)) is None:
        return None
    return (getattr(coordinator.client, "werksbezeichnung", None) or {}).get(knoten)


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
        # gehört dorthin, **was** das Gerät ist. Kennt die kuratierte Tabelle
        # den Funktionstyp nicht, nennt die Anlage selbst die Werksbezeichnung
        # ihres Bausteins – für fremde Baureihen die einzige belastbare Angabe.
        model=FCT_MODELL.get(fct_type) or _werksbezeichnung(coordinator, beschreibung) or funktion,
        via_device=(DOMAIN, steuerung_kennung(coordinator)),
    )
    if seriennummer := _seriennummer(coordinator, beschreibung):
        info["serial_number"] = seriennummer
    if software := _modulwert(coordinator, beschreibung, OID_SOFTWAREVERSION):
        info["sw_version"] = software
    if hardware := _modulwert(coordinator, beschreibung, OID_HARDWAREVERSION):
        info["hw_version"] = hardware
    return info


def steuerung_info(coordinator: Any) -> dict[str, str]:
    """Modell und Firmwarestand der Steuerung für ihre Geräteseite.

    Die Angaben stammen aus `info/deviceinfo`. Die dort ebenfalls gelieferte
    Seriennummer bleibt bewusst draußen: Sie identifiziert die Anlage und
    stünde damit auf einer Seite, von der Bildschirmabzüge in Fehlerberichte
    wandern. In der Diagnose steht sie geschwärzt.
    """
    auskunft = getattr(coordinator.client, "geraeteinfo", None) or {}
    info = {"model": str(auskunft.get("device") or "").strip() or "Steuerung"}
    if fassung := str(auskunft.get("version") or "").strip():
        info["sw_version"] = fassung
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


class MeldungsQuelle:
    """Entitäten, deren Wert aus der Gerätemeldung (`FExxmsg`) entsteht.

    Der Rohtext kommt aus der /1-Discovery, nicht aus dem OID-Abruf, und wird
    je Abruf einmal ausgewertet. Vor `WindhagerEntity` einordnen, damit
    `available` hier greift.
    """

    _register_poll_oid = False

    def __init__(self, coordinator: Any, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        self._node_id = str(device_info.get("node_id"))
        self._roh_zuletzt: str | None = None
        self._meldungen_zuletzt: list[dict] = []

    @property
    def _raw(self) -> str | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("status", {}).get(self._node_id)

    @property
    def _meldungen(self) -> list[dict]:
        roh = self._raw
        if roh != self._roh_zuletzt:
            self._roh_zuletzt = roh
            self._meldungen_zuletzt = parse_messages(roh, self._descriptor.get("stoerungstexte"))
        return self._meldungen_zuletzt

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._raw is not None


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

    async def async_update(self) -> None:
        """Nur diesen einen Datenpunkt neu lesen.

        `homeassistant.update_entity` landet über `CoordinatorEntity` sonst bei
        `async_request_refresh` – und das ist ein **vollständiger** Durchlauf
        über alle aktiven OIDs. Auf einer Anlage mit knapp zwei Sekunden
        Antwortzeit dauert der zwanzig Sekunden und mehr.

        Genau darauf wartet aber die Oberfläche, wenn sie nach einer Bedienung
        nachfasst: Nach dem Beenden einer Warmwasserladung lief die Ladepumpe
        im Schaubild weiter, obwohl die Anlage längst umgeschaltet hatte. Ein
        gezielter Abruf braucht eine Anfrage.

        Dieselbe Bauart benutzt das Thermostat schon für seinen Nachlade-Burst.
        """
        if not self._oid or self.coordinator.data is None:
            await super().async_update()
            return
        try:
            gelesen = await self.coordinator.client.fetch_oids([self._oid])
        except Exception as err:
            # Nachfassen ist eine Beschleunigung, keine Pflicht: Der reguläre
            # Durchlauf holt den Wert ohnehin.
            _LOGGER.debug("Gezieltes Nachlesen von %s fehlgeschlagen: %s", self._oid, err)
            return
        if not gelesen:
            return
        self.coordinator.data.setdefault("oids", {}).update(gelesen)
        # Nur die Zuhörer wecken – kein zweiter Durchlauf durch die Anlage.
        self.coordinator.async_update_listeners()

    @property
    def raw_value(self) -> str | None:
        """Raw string value of this entity's OID.

        Ein nicht angeschlossener Fühler meldet keinen leeren Wert, sondern die
        Ungültig-Marke seines LonMark-Typs (327,67 °C, 163,835 %). Sie gilt
        deshalb als kein Wert – bei Netzwerkvariablen wie bei Temperaturen.
        """
        if not self.coordinator.data:
            return None
        wert = self.coordinator.data.get("oids", {}).get(self._oid)
        marke_moeglich = self._descriptor.get("nv_name") or self._descriptor.get("type") in (
            "temperature",
        )
        if marke_moeglich and lon_ungueltig(wert):
            return None
        return wert

    @property
    def float_value(self) -> float | None:
        return parse_value(self.raw_value, float, self._oid)

    @property
    def int_value(self) -> int | None:
        return parse_value(self.raw_value, int, self._oid)

    @property
    def enum_map(self) -> dict[int, str]:
        # Was die Anlage selbst benennt, hat Vorrang: Es passt zu ihrer
        # Fassung und zur eingestellten Sprache. Auf Deutsch ist das Feld
        # leer, dort führt die gepflegte Tabelle.
        #
        # `int(...)`, weil der Erkennungsstand als JSON abgelegt wird und
        # Schlüssel dabei zu Text werden. Ohne die Umwandlung fände die
        # Zuordnung nach dem Neustart nichts mehr.
        if geraet := self._descriptor.get("enum_texte"):
            return {int(wert): text for wert, text in geraet.items()}
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
