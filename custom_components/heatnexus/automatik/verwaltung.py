"""Alle Automatiken: Einstellungen und Zustand im Store, Start und Stopp je Eintrag.

Die Einstellungen liegen bewusst nicht in Subeinträgen: Deren Änderung weckt
die Update-Listener des Eintrags und kann die ganze Integration neu laden.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import AUTOMATIK_GERAET_ENDUNG, DOMAIN, SIGNAL_NEUE_ENTITAETEN
from . import konfig as konfig_modul
from .laufzeit import SIGNAL_AKTUALISIERT, Laufzeit

_LOGGER = logging.getLogger(__name__)

STORE_KEY = f"{DOMAIN}.automatik"
STORE_VERSION = 1
SPEICHER_VERZOEGERUNG_S = 30
DATEN_SCHLUESSEL = f"{DOMAIN}_automatik"
SIGNAL_NEU = f"{DOMAIN}_automatik_neu_{{}}"
DOMAENE_JE_ART = {
    "schalter": "switch",
    "modus": "select",
    "ausrichtung": "select",
    "zustand": "sensor",
    "gedaempft": "sensor",
    "heizgrenze": "sensor",
    "abweichung": "sensor",
    "sonnenquote": "sensor",
    "eingriffe": "sensor",
    "letzter_eingriff": "sensor",
    "naechste_entscheidung": "sensor",
    "stoerung": "binary_sensor",
}
ARTEN = tuple(DOMAENE_JE_ART)
SYSTEM_DOMAENE = {
    "status": "sensor",
    "automatiken": "sensor",
    "eingriffe": "sensor",
    "letzter_eingriff": "sensor",
    "naechste_entscheidung": "sensor",
    "stoerung": "binary_sensor",
    "prognose": "binary_sensor",
}
# Mehrere Heizkreise teilen sich meist eine Wetter-Entität; gefragt wird sie einmal.
PROGNOSE_GUELTIG = timedelta(minutes=50)


def verwaltung_holen(hass: HomeAssistant) -> Verwaltung:
    """Die eine Verwaltung je Home-Assistant-Instanz."""
    if (verwaltung := hass.data.get(DATEN_SCHLUESSEL)) is None:
        verwaltung = hass.data[DATEN_SCHLUESSEL] = Verwaltung(hass)
    return verwaltung


AUTOMATIK_MARKE = "-automatik-"


def system_kennung(entry_id: str) -> str:
    """Kennung des System-Geräts „HeatNexus Automatik“ eines Eintrags."""
    return f"{entry_id}{AUTOMATIK_GERAET_ENDUNG}"


def system_unique_id(entry_id: str, art: str) -> str:
    """Kennung einer System-Entität; die Marke `-automatik-` kennt auch die Suche nach Verwaisten."""
    return f"{entry_id}{AUTOMATIK_MARKE}system-{art}"


def geraet_kennung(device_id: str) -> str:
    """Kennung des Automatik-Geräts eines Heizkreises."""
    return f"{device_id}{AUTOMATIK_GERAET_ENDUNG}"


def unique_id(device_id: str, art: str) -> str:
    """Kennung einer Automatik-Entität; hängt an der Kennung des Heizkreises."""
    return f"{device_id}{AUTOMATIK_MARKE}{art}"


class Verwaltung:
    """Hält die Laufzeiten und den gemeinsamen Store."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store = Store(hass, STORE_VERSION, STORE_KEY)
        self._daten: dict[str, Any] = {"heizkreise": {}}
        self._geladen = False
        self.laufzeiten: dict[str, Laufzeit] = {}
        self._prognosen: dict[tuple[str, str], tuple[datetime, list[dict[str, Any]]]] = {}
        self._prognose_sperre = asyncio.Lock()

    async def laden(self) -> None:
        """Den Store einmal lesen."""
        if self._geladen:
            return
        roh = await self._store.async_load() or {}
        heizkreise = roh.get("heizkreise") if isinstance(roh, dict) else None
        self._daten = {"heizkreise": heizkreise if isinstance(heizkreise, dict) else {}}
        # Gespeichertes geht noch einmal durch die Prüfung; neue Regeln gelten auch für Altes.
        for eintrag in self._daten["heizkreise"].values():
            if isinstance(eintrag, dict) and (
                neu := konfig_modul.pruefen(eintrag.get("konfig") or {})
            ):
                eintrag["konfig"] = neu
        self._geladen = True

    @callback
    def speichern(self) -> None:
        """Verzögert sichern; viele Läufe kurz hintereinander ergeben einen Schreibvorgang."""
        self._store.async_delay_save(self._abzug, SPEICHER_VERZOEGERUNG_S)

    def _abzug(self) -> dict[str, Any]:
        for device_id, laufzeit in self.laufzeiten.items():
            if eintrag := self._daten["heizkreise"].get(device_id):
                eintrag["zustand"] = laufzeit.als_dict()
        return self._daten

    @property
    def geladen(self) -> bool:
        return self._geladen

    def kennungen(self, entry_id: str) -> dict[str, str]:
        """Kennung -> Domäne jeder Automatik-Entität eines Eintrags, System eingeschlossen."""
        kreise = {
            unique_id(device_id, art): DOMAENE_JE_ART[art]
            for device_id, eintrag in self._daten["heizkreise"].items()
            if (eintrag.get("konfig") or {}).get("entry_id") == entry_id
            for art in ARTEN
        }
        if not kreise:
            return {}
        return kreise | {system_unique_id(entry_id, art): d for art, d in SYSTEM_DOMAENE.items()}

    def _system_anlegen(self, entry: ConfigEntry) -> None:
        dr.async_get(self.hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, system_kennung(entry.entry_id))},
            name="HeatNexus Automatik",
            manufacturer="HeatNexus",
            model="Automatik-System",
        )

    def _system_entfernen(self, entry_id: str) -> None:
        """Mit der letzten Automatik des Eintrags gehen System-Entitäten und -Gerät."""
        register = er.async_get(self.hass)
        for art, domaene in SYSTEM_DOMAENE.items():
            kennung = system_unique_id(entry_id, art)
            if entity_id := register.async_get_entity_id(domaene, DOMAIN, kennung):
                register.async_remove(entity_id)
        geraete = dr.async_get(self.hass)
        if geraet := geraete.async_get_device(identifiers={(DOMAIN, system_kennung(entry_id))}):
            geraete.async_remove_device(geraet.id)

    def konfig(self, device_id: str) -> dict[str, Any] | None:
        """Die gespeicherten Einstellungen eines Heizkreises."""
        eintrag = self._daten["heizkreise"].get(device_id)
        return eintrag.get("konfig") if eintrag else None

    @staticmethod
    def heizkreise(entry: ConfigEntry) -> list[tuple[Any, dict[str, Any]]]:
        """Alle Heizkreise eines Eintrags: Coordinator und Klima-Beschreibung."""
        daten = getattr(entry, "runtime_data", None) or {}
        treffer: list[tuple[Any, dict[str, Any]]] = []
        for coordinator in (daten.get("coordinators") or {}).values():
            for beschreibung in (coordinator.data or {}).get("devices", []):
                if beschreibung.get("type") == "climate" and beschreibung.get("device_id"):
                    treffer.append((coordinator, beschreibung))
        return treffer

    async def prognose(self, wetter: str, art: str) -> list[dict[str, Any]] | None:
        """Stunden- oder Tagesprognose einer Wetter-Entität, kurz zwischengespeichert."""
        async with self._prognose_sperre:
            jetzt = dt_util.now()
            if (treffer := self._prognosen.get((wetter, art))) and jetzt - treffer[
                0
            ] < PROGNOSE_GUELTIG:
                return treffer[1]
            try:
                antwort = await self.hass.services.async_call(
                    "weather",
                    "get_forecasts",
                    {"entity_id": wetter, "type": art},
                    blocking=True,
                    return_response=True,
                )
            except HomeAssistantError as fehler:
                _LOGGER.debug("Automatik: Prognose %s von %s nicht lesbar: %s", art, wetter, fehler)
                return None
            daten = list(((antwort or {}).get(wetter) or {}).get("forecast") or [])
            self._prognosen[(wetter, art)] = (jetzt, daten)
            return daten

    # --- je Eintrag ----------------------------------------------------------
    async def eintrag_starten(self, entry: ConfigEntry) -> None:
        """Alle eingerichteten Automatiken des Eintrags starten."""
        await self.laden()
        await self._nachholen(entry)

        @callback
        def _neu() -> None:
            self.hass.async_create_task(self._nachholen(entry))

        entry.async_on_unload(
            async_dispatcher_connect(self.hass, SIGNAL_NEUE_ENTITAETEN.format(entry.entry_id), _neu)
        )

    async def _nachholen(self, entry: ConfigEntry) -> None:
        # Ein Heizkreis kann erst nach dem Vollabzug bekannt sein.
        for device_id, eintrag in list(self._daten["heizkreise"].items()):
            konfig = eintrag.get("konfig") or {}
            if konfig.get("entry_id") == entry.entry_id and device_id not in self.laufzeiten:
                await self._starten(entry, device_id)

    async def _starten(self, entry: ConfigEntry, device_id: str) -> bool:
        treffer = next((t for t in self.heizkreise(entry) if t[1]["device_id"] == device_id), None)
        eintrag = self._daten["heizkreise"].get(device_id)
        if treffer is None or eintrag is None:
            return False
        coordinator, beschreibung = treffer
        # Das System-Gerät muss stehen, bevor der Heizkreis darauf verweist.
        self._system_anlegen(entry)
        laufzeit = Laufzeit(
            self.hass,
            coordinator,
            beschreibung,
            eintrag["konfig"],
            eintrag.get("zustand"),
            self.speichern,
            entry.entry_id,
            self.prognose,
        )
        self.laufzeiten[device_id] = laufzeit
        async_dispatcher_send(self.hass, SIGNAL_NEU.format(entry.entry_id))
        await laufzeit.starten()
        return True

    async def eintrag_stoppen(self, entry: ConfigEntry) -> None:
        """Die Automatiken des Eintrags anhalten; ihr Zustand bleibt im Store."""
        self._abzug()
        for device_id, laufzeit in list(self.laufzeiten.items()):
            if laufzeit.entry_id == entry.entry_id:
                laufzeit.stoppen()
                del self.laufzeiten[device_id]
        await self._store.async_save(self._daten)

    async def eintrag_entfernt(self, entry_id: str) -> None:
        """Einstellungen eines gelöschten Eintrags verwerfen."""
        await self.laden()
        self._daten["heizkreise"] = {
            device_id: eintrag
            for device_id, eintrag in self._daten["heizkreise"].items()
            if (eintrag.get("konfig") or {}).get("entry_id") != entry_id
        }
        await self._store.async_save(self._daten)

    # --- Bedienung -----------------------------------------------------------
    async def einrichten(self, entry: ConfigEntry, roh: dict[str, Any]) -> dict[str, Any]:
        """Eine Automatik anlegen; sie startet im Beobachtungsmodus."""
        await self.laden()
        konfig = konfig_modul.pruefen({**roh, "entry_id": entry.entry_id, "modus": "beobachten"})
        if konfig is None:
            raise ValueError("Raumfühler und Wetter-Entität sind nötig.")
        konfig = konfig_modul.klima_vorgabe(konfig, [])
        device_id = konfig["heizkreis"]
        if device_id in self.laufzeiten:
            raise ValueError("Für diesen Heizkreis gibt es schon eine Automatik.")
        self._daten["heizkreise"][device_id] = {"konfig": konfig, "zustand": {}}
        if not await self._starten(entry, device_id):
            del self._daten["heizkreise"][device_id]
            raise ValueError("Diesen Heizkreis kennt die Anlage nicht.")
        self.speichern()
        return konfig

    async def einstellen(self, device_id: str, aenderung: dict[str, Any]) -> dict[str, Any]:
        """Einstellungen ändern; beim Wechsel ins Beobachten oder Aus zurücknehmen."""
        eintrag = self._daten["heizkreise"].get(device_id)
        if eintrag is None:
            raise ValueError("Für diesen Heizkreis gibt es keine Automatik.")
        alt = eintrag["konfig"]
        neu = konfig_modul.pruefen({**alt, **aenderung})
        if neu is None:
            raise ValueError("Raumfühler und Wetter-Entität sind nötig.")
        neu = konfig_modul.klima_vorgabe(neu, alt["raeume"])
        if (laufzeit := self.laufzeiten.get(device_id)) is not None:
            schaltete = alt["aktiv"] and alt["modus"] == "schalten"
            schaltet = neu["aktiv"] and neu["modus"] == "schalten"
            if schaltete and not schaltet:
                await laufzeit.zuruecknehmen()
            # Nur Beobachtetes verwerfen; ein nicht zurückgenommener Eingriff bleibt bekannt.
            if schaltet and alt["modus"] != "schalten":
                laufzeit.gedaechtnis_leeren()
            if neu["modus"] == "beobachten" and alt["modus"] != "beobachten":
                laufzeit.beobachtet_seit = dt_util.now()
            await laufzeit.neu_starten(neu)
        eintrag["konfig"] = neu
        self.speichern()
        async_dispatcher_send(self.hass, SIGNAL_AKTUALISIERT.format(device_id))
        return neu

    async def heizgrenzen(self, device_id: str, werte: dict[str, float]) -> None:
        """Heizgrenzen der Steuerung des Heizkreises setzen."""
        if (laufzeit := self.laufzeiten.get(device_id)) is None:
            raise ValueError("Für diesen Heizkreis gibt es keine Automatik.")
        await laufzeit.heizgrenzen_setzen(werte)

    async def uebernehmen(self, device_id: str) -> None:
        """Nach einem Handeingriff sofort weitermachen."""
        if (laufzeit := self.laufzeiten.get(device_id)) is None:
            raise ValueError("Für diesen Heizkreis gibt es keine Automatik.")
        await laufzeit.uebernehmen()

    async def entfernen(self, device_id: str) -> None:
        """Automatik löschen: eigene Eingriffe zurücknehmen, Entitäten abräumen."""
        if (laufzeit := self.laufzeiten.pop(device_id, None)) is not None:
            await laufzeit.zuruecknehmen()
            laufzeit.stoppen()
        entry_id = ((self._daten["heizkreise"].pop(device_id, None) or {}).get("konfig") or {}).get(
            "entry_id"
        )
        register = er.async_get(self.hass)
        for art in ARTEN:
            kennung = unique_id(device_id, art)
            if entity_id := register.async_get_entity_id(DOMAENE_JE_ART[art], DOMAIN, kennung):
                register.async_remove(entity_id)
        geraete = dr.async_get(self.hass)
        if geraet := geraete.async_get_device(identifiers={(DOMAIN, geraet_kennung(device_id))}):
            geraete.async_remove_device(geraet.id)
        if entry_id and not self.kennungen(entry_id):
            self._system_entfernen(entry_id)
            async_dispatcher_send(self.hass, SIGNAL_NEU.format(entry_id))
        await self._store.async_save(self._daten)
