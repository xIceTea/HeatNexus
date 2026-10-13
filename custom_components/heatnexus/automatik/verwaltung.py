"""Alle Automatiken: Einstellungen und Zustand im Store, Start und Stopp je Eintrag.

Die Einstellungen liegen bewusst nicht in Subeinträgen: Deren Änderung weckt
die Update-Listener des Eintrags und kann die ganze Integration neu laden.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from pathlib import Path
import shutil
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import (
    AUTOMATIK_GERAET_ENDUNG,
    DOMAIN,
    SIGNAL_NEUE_ENTITAETEN,
    SUBEINTRAG_AUTOMATIK,
)
from ..registrierung import (
    geraet_suchen,
    geraetename,
    in_untereintrag_verschieben,
    untereintraege,
)
from ..texte import woerterbuch
from . import konfig as konfig_modul
from .laufzeit import SIGNAL_AKTUALISIERT, Laufzeit

_LOGGER = logging.getLogger(__name__)

STORE_KEY = f"{DOMAIN}.automatik"
STORE_VERSION = 1
SPEICHER_VERZOEGERUNG_S = 30
# Läufe ohne neuen Zustand ändern nur Verlauf und Messwerte; die gehen gesammelt in den Store.
SPEICHER_RUHIG_S = 600
DATEN_SCHLUESSEL = f"{DOMAIN}_automatik"
SIGNAL_NEU = f"{DOMAIN}_automatik_neu_{{}}"
DOMAENE_JE_ART = {
    "schalter": "switch",
    "modus": "select",
    "ausrichtung": "select",
    "zustand": "sensor",
    "empfehlung": "sensor",
    "empfehlung_uebernehmen": "button",
    "empfehlung_verwerfen": "button",
    "gedaempft": "sensor",
    "heizgrenze": "sensor",
    "abweichung": "sensor",
    "sonnenquote": "sensor",
    "auskuehlzeit": "sensor",
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
    "sonnentag_heute": "sensor",
    "nur_ww_heute": "sensor",
    "vorrang_heute": "sensor",
    "absenkung_bis": "sensor",
    "modus_seit": "sensor",
    "raeume": "sensor",
    "prognose_max": "sensor",
    "prognose_mittel": "sensor",
    "prognosekorrektur": "sensor",
    "sonnentag_aktiv": "binary_sensor",
    "nur_ww_aktiv": "binary_sensor",
    "ueber_heizgrenze": "binary_sensor",
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


def _geraete_umhaengen(register: dr.DeviceRegistry, entry: ConfigEntry, sub_id: str) -> None:
    """Automatik-Geräte vom Haupteintrag in den Untereintrag verschieben.

    Hängt ein Gerät an beiden, steht es zweimal in der Übersicht der Integration.
    """
    for geraet in dr.async_entries_for_config_entry(register, entry.entry_id):
        zuordnung = untereintraege(geraet, entry.entry_id)
        if None not in zuordnung or not any(
            bereich == DOMAIN and str(wert).endswith(AUTOMATIK_GERAET_ENDUNG)
            for bereich, wert in geraet.identifiers
        ):
            continue
        in_untereintrag_verschieben(register, geraet, entry.entry_id, sub_id)


def _normalisiert(roh: Any) -> dict[str, Any]:
    """Nur Heizkreise mit Einstellungen als Zuordnung; Fremdes fällt weg und steht im Protokoll."""
    heizkreise = roh.get("heizkreise") if isinstance(roh, dict) else None
    ergebnis: dict[str, Any] = {}
    for device_id, eintrag in (heizkreise if isinstance(heizkreise, dict) else {}).items():
        if not isinstance(eintrag, dict) or not isinstance(eintrag.get("konfig"), dict):
            _LOGGER.warning("Automatik: unlesbarer Eintrag %s im Store verworfen", device_id)
            continue
        zustand = eintrag.get("zustand")
        ergebnis[str(device_id)] = {
            **eintrag,
            "zustand": zustand if isinstance(zustand, dict) else {},
        }
    return {"heizkreise": ergebnis}


def _sichern(pfad: str) -> None:
    """Eine unlesbare Datei neben sich kopieren, bevor der nächste Schreibvorgang sie ersetzt."""
    datei = Path(pfad)
    if datei.exists():
        shutil.copy2(datei, datei.with_name(f"{datei.name}.kaputt-{dt_util.now():%Y%m%d%H%M%S}"))


class _AutomatikStore(Store[dict[str, Any]]):
    """Eine andere Fassung des Stores geht durch dieselbe Prüfung wie jeder Ladevorgang."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        return _normalisiert(old_data)


class Verwaltung:
    """Hält die Laufzeiten und den gemeinsamen Store."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store = _AutomatikStore(hass, STORE_VERSION, STORE_KEY)
        self._lade_sperre = asyncio.Lock()
        self._daten: dict[str, Any] = {"heizkreise": {}}
        self._geladen = False
        self._geplant = False
        self.laufzeiten: dict[str, Laufzeit] = {}
        self._prognosen: dict[tuple[str, str], tuple[datetime, list[dict[str, Any]]]] = {}
        self._prognose_sperre = asyncio.Lock()
        # Je Wetter-Entität und Vorhersageart der letzte Fehler, bis ein Abruf gelingt.
        self.prognose_fehler: dict[tuple[str, str], tuple[datetime, str]] = {}

    async def laden(self) -> None:
        """Den Store einmal lesen; zwei Einträge, die zugleich starten, warten aufeinander."""
        async with self._lade_sperre:
            if self._geladen:
                return
            self._daten = _normalisiert(await self._roh_laden())
            # Gespeichertes geht noch einmal durch die Prüfung; neue Regeln gelten auch für Altes.
            for eintrag in self._daten["heizkreise"].values():
                if neu := konfig_modul.pruefen(eintrag["konfig"]):
                    eintrag["konfig"] = neu
            self._geladen = True

    async def _roh_laden(self) -> Any:
        """Der Inhalt des Stores; ist er unlesbar, bleibt eine Kopie und die Automatik beginnt leer."""
        try:
            return await self._store.async_load()
        except Exception:  # eine unlesbare Datei darf das Setup nicht verhindern
            _LOGGER.exception("Automatik: Store %s unlesbar, beginne ohne Einstellungen", STORE_KEY)
        try:
            await self.hass.async_add_executor_job(_sichern, self._store.path)
        except OSError as fehler:
            _LOGGER.error("Automatik: Store %s nicht gesichert: %s", STORE_KEY, fehler)
        return None

    @callback
    def speichern(self) -> None:
        """Verzögert sichern; viele Läufe kurz hintereinander ergeben einen Schreibvorgang."""
        self._geplant = True
        self._store.async_delay_save(self._abzug, SPEICHER_VERZOEGERUNG_S)

    @callback
    def speichern_ruhig(self) -> None:
        """Gedrosselt sichern; ein schon geplanter Schreibvorgang nimmt es mit."""
        if self._geplant:
            return
        self._geplant = True
        self._store.async_delay_save(self._abzug, SPEICHER_RUHIG_S)

    def _abzug(self) -> dict[str, Any]:
        self._geplant = False
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

    @staticmethod
    def subeintrag(entry: ConfigEntry) -> str | None:
        """Der Untereintrag, der die Geräte der Automatik bündelt; ohne ihn None."""
        return next(
            (
                sub.subentry_id
                for sub in (entry.subentries or {}).values()
                if sub.subentry_type == SUBEINTRAG_AUTOMATIK
            ),
            None,
        )

    def _subeintrag_anlegen(self, entry: ConfigEntry) -> str:
        """Nur ein Behälter für die Geräte: die Einstellungen bleiben im Store."""
        if (vorhanden := self.subeintrag(entry)) is not None:
            return vorhanden
        sub = ConfigSubentry(
            data=MappingProxyType({}),
            subentry_type=SUBEINTRAG_AUTOMATIK,
            title="HeatNexus Automatik",
            unique_id=SUBEINTRAG_AUTOMATIK,
        )
        self.hass.config_entries.async_add_subentry(entry, sub)
        return sub.subentry_id

    def _system_anlegen(self, entry: ConfigEntry) -> None:
        sub_id = self._subeintrag_anlegen(entry)
        register = dr.async_get(self.hass)
        # Erst umhängen: Ein vorhandenes Gerät darf `async_get_or_create` nicht stillschweigend verschieben.
        _geraete_umhaengen(register, entry, sub_id)
        register.async_get_or_create(
            config_entry_id=entry.entry_id,
            config_subentry_id=sub_id,
            identifiers={(DOMAIN, system_kennung(entry.entry_id))},
            name=woerterbuch(self.hass)("HeatNexus Automatik"),
            manufacturer="HeatNexus",
            model=woerterbuch(self.hass)("Automatik-System"),
        )

    def _system_entfernen(self, entry_id: str) -> None:
        """Mit der letzten Automatik des Eintrags gehen System-Entitäten und -Gerät."""
        register = er.async_get(self.hass)
        for art, domaene in SYSTEM_DOMAENE.items():
            kennung = system_unique_id(entry_id, art)
            if entity_id := register.async_get_entity_id(domaene, DOMAIN, kennung):
                register.async_remove(entity_id)
        geraete = dr.async_get(self.hass)
        if geraet := geraet_suchen(geraete, system_kennung(entry_id), entry_id):
            geraete.async_remove_device(geraet.id)
        if (entry := self.hass.config_entries.async_get_entry(entry_id)) and (
            sub_id := self.subeintrag(entry)
        ):
            self.hass.config_entries.async_remove_subentry(entry, sub_id)

    def eingerichtet(self, entry_id: str) -> list[str]:
        """Die Heizkreise des Eintrags, für die eine Automatik eingerichtet ist."""
        return [
            device_id
            for device_id, eintrag in self._daten["heizkreise"].items()
            if (eintrag.get("konfig") or {}).get("entry_id") == entry_id
        ]

    def konfigurationen(self) -> list[tuple[str, dict[str, Any]]]:
        """Heizkreis und Einstellungen jeder gespeicherten Automatik."""
        return [
            (device_id, eintrag["konfig"])
            for device_id, eintrag in self._daten["heizkreise"].items()
            if isinstance(eintrag, dict) and isinstance(eintrag.get("konfig"), dict)
        ]

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
        """Vorhersage einer Wetter-Entität, kurz zwischengespeichert; ein Fehler steht in `prognose_fehler`."""
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
                # Einmal als Warnung, danach leise, bis die Entität wieder liefert.
                _LOGGER.log(
                    logging.DEBUG if (wetter, art) in self.prognose_fehler else logging.WARNING,
                    "Automatik: %s liefert keine Vorhersage (%s): %s",
                    wetter,
                    art,
                    fehler,
                )
                self.prognose_fehler[(wetter, art)] = (jetzt, str(fehler) or type(fehler).__name__)
                return None
            self.prognose_fehler.pop((wetter, art), None)
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
                # Eine Automatik, die nicht startet, hält weder die anderen noch den Eintrag auf.
                try:
                    await self._starten(entry, device_id, im_hintergrund=True)
                except Exception:  # protokolliert und gemeldet in `_starten`
                    continue

    async def _starten(
        self, entry: ConfigEntry, device_id: str, im_hintergrund: bool = False
    ) -> bool:
        treffer = next((t for t in self.heizkreise(entry) if t[1]["device_id"] == device_id), None)
        eintrag = self._daten["heizkreise"].get(device_id)
        if treffer is None or eintrag is None:
            return False
        coordinator, beschreibung = treffer
        # Das System-Gerät muss stehen, bevor der Heizkreis darauf verweist.
        self._system_anlegen(entry)
        kennung = f"automatik_start_{device_id}"
        try:
            laufzeit = Laufzeit(
                self.hass,
                coordinator,
                beschreibung,
                eintrag["konfig"],
                eintrag.get("zustand"),
                self.speichern,
                entry.entry_id,
                self.prognose,
                self.speichern_ruhig,
            )
            self.laufzeiten[device_id] = laufzeit
            async_dispatcher_send(self.hass, SIGNAL_NEU.format(entry.entry_id))
            await laufzeit.starten(im_hintergrund=im_hintergrund)
        except Exception:
            name = geraetename(
                self.hass, device_id, entry.entry_id, beschreibung.get("device_name") or device_id
            )
            self._start_gescheitert(device_id, kennung, name)
            raise
        ir.async_delete_issue(self.hass, DOMAIN, kennung)
        return True

    def _start_gescheitert(self, device_id: str, kennung: str, name: str) -> None:
        _LOGGER.exception("Automatik %s: Start gescheitert", name)
        if (laufzeit := self.laufzeiten.pop(device_id, None)) is not None:
            laufzeit.stoppen()
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            kennung,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="automatik_start",
            translation_placeholders={"heizkreis": name},
        )

    async def eintrag_stoppen(self, entry: ConfigEntry) -> None:
        """Die Automatiken des Eintrags anhalten; ihr Zustand bleibt im Store.

        Ein laufender Lauf endet vorher; danach schreibt keine Automatik des Eintrags mehr.
        """
        gestoppt = [lz for lz in self.laufzeiten.values() if lz.entry_id == entry.entry_id]
        for laufzeit in gestoppt:
            laufzeit.stoppen()
        for laufzeit in gestoppt:
            await laufzeit.abwarten()
        self._abzug()
        for laufzeit in gestoppt:
            self.laufzeiten.pop(laufzeit.device_id, None)
        await self._store.async_save(self._daten)

    async def untereintrag_pruefen(self, entry: ConfigEntry) -> None:
        """Fehlt „HeatNexus Automatik“, obwohl Automatiken eingerichtet sind, hat der Nutzer sie gelöscht.

        Jede Automatik des Eintrags wird dann entfernt, eigene Eingriffe an der Steuerung zurückgenommen.
        """
        if self.subeintrag(entry) is not None:
            return
        for device_id in self.eingerichtet(entry.entry_id):
            await self.entfernen(device_id)

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
        try:
            gestartet = await self._starten(entry, device_id)
        except Exception as fehler:
            del self._daten["heizkreise"][device_id]
            # Die Antwort an das Panel nennt den Fehler; eine Reparaturmeldung bliebe ohne Automatik stehen.
            ir.async_delete_issue(self.hass, DOMAIN, f"automatik_start_{device_id}")
            raise ValueError("Die Automatik ließ sich nicht starten.") from fehler
        if not gestartet:
            del self._daten["heizkreise"][device_id]
            raise ValueError("Diesen Heizkreis kennt die Anlage nicht.")
        self.speichern()
        return konfig

    async def einstellen(self, device_id: str, aenderung: dict[str, Any]) -> dict[str, Any]:
        """Einstellungen ändern; ein Wechsel weg von „Automatisch" nimmt laufende Eingriffe zurück."""
        eintrag = self._daten["heizkreise"].get(device_id)
        if eintrag is None:
            raise ValueError("Für diesen Heizkreis gibt es keine Automatik.")
        alt = eintrag["konfig"]
        neu = konfig_modul.pruefen({**alt, **aenderung})
        if neu is None:
            raise ValueError("Raumfühler und Wetter-Entität sind nötig.")
        neu = konfig_modul.klima_vorgabe(neu, alt["raeume"])
        if (laufzeit := self.laufzeiten.get(device_id)) is not None:
            schreibt_alt = alt["aktiv"] and alt["modus"] != "beobachten"
            schreibt_neu = neu["aktiv"] and neu["modus"] != "beobachten"
            gewechselt = (alt["aktiv"], alt["modus"]) != (neu["aktiv"], neu["modus"])
            # Ohne „Automatisch" läuft kein Eingriff ohne Zustimmung weiter; die Regel rechnet sofort neu.
            selbst_neu = neu["aktiv"] and neu["modus"] == "schalten"
            # Kein Lauf mit den alten Einstellungen mehr, solange umgestellt wird.
            laufzeit.aussetzen()
            await laufzeit.abwarten()
            if schreibt_alt and not selbst_neu and gewechselt:
                await laufzeit.zuruecknehmen()
            # Nur Beobachtetes verwerfen; ein nicht zurückgenommener Eingriff bleibt bekannt.
            if schreibt_neu and alt["modus"] == "beobachten":
                laufzeit.gedaechtnis_leeren()
            if neu["modus"] == "beobachten" and alt["modus"] != "beobachten":
                laufzeit.beobachtet_seit = dt_util.now()
            await laufzeit.neu_starten(neu, entscheidungszeit=gewechselt and neu["aktiv"])
            # Andere Räume oder anderes Wetter: Das gelernte Hausmodell passt nicht mehr.
            if any(alt.get(k) != neu.get(k) for k in ("raeume", "raum_art", "wetter")):
                laufzeit.modell_neu_lernen()
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

    async def empfehlung_uebernehmen(self, device_id: str) -> None:
        """Die offene Empfehlung eines Heizkreises bestätigen."""
        if (laufzeit := self.laufzeiten.get(device_id)) is None:
            raise ValueError("Für diesen Heizkreis gibt es keine Automatik.")
        await laufzeit.empfehlung_uebernehmen()

    async def empfehlung_verwerfen(self, device_id: str) -> None:
        """Die offene Empfehlung eines Heizkreises verwerfen."""
        if (laufzeit := self.laufzeiten.get(device_id)) is None:
            raise ValueError("Für diesen Heizkreis gibt es keine Automatik.")
        await laufzeit.empfehlung_verwerfen()

    async def hausmodell_neu(self, device_id: str) -> None:
        """Das Hausmodell eines Heizkreises verwerfen und aus dem Verlauf neu lernen."""
        if (laufzeit := self.laufzeiten.get(device_id)) is None:
            raise ValueError("Für diesen Heizkreis gibt es keine Automatik.")
        laufzeit.modell_neu_lernen()

    async def entfernen(self, device_id: str) -> None:
        """Automatik löschen: eigene Eingriffe zurücknehmen, Entitäten abräumen."""
        if (laufzeit := self.laufzeiten.pop(device_id, None)) is not None:
            laufzeit.stoppen()
            await laufzeit.zuruecknehmen()
            laufzeit.meldung_entfernen()
            laufzeit.optimierung_entfernen()
        entry_id = ((self._daten["heizkreise"].pop(device_id, None) or {}).get("konfig") or {}).get(
            "entry_id"
        )
        register = er.async_get(self.hass)
        for art in ARTEN:
            kennung = unique_id(device_id, art)
            if entity_id := register.async_get_entity_id(DOMAENE_JE_ART[art], DOMAIN, kennung):
                register.async_remove(entity_id)
        geraete = dr.async_get(self.hass)
        if geraet := geraet_suchen(geraete, geraet_kennung(device_id), entry_id):
            geraete.async_remove_device(geraet.id)
        if entry_id and not self.kennungen(entry_id):
            self._system_entfernen(entry_id)
            async_dispatcher_send(self.hass, SIGNAL_NEU.format(entry_id))
        await self._store.async_save(self._daten)
