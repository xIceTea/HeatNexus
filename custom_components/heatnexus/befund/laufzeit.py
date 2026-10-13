"""Befund in Home Assistant: je Anlage alle fünf Minuten sammeln, stündlich verdichten, speichern."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..automatik.eingaben import raum_messung, raumwert
from ..automatik.seitenleiste import entfernen as meldung_entfernen
from ..automatik.seitenleiste import melden as meldung_setzen
from ..automatik.tagesansicht import hausmodell_stand
from ..automatik.verwaltung import Verwaltung, verwaltung_holen
from ..const import DOMAIN
from ..erkennungsstand import systems
from ..helpers import get_oid_value
from ..registrierung import geraet_suchen
from ..texte import woerterbuch
from . import auswertung
from .archiv import STUNDE, Archiv

_LOGGER = logging.getLogger(__name__)
TAKT = timedelta(minutes=5)
SPEICHERN_S = 60
NACHRECHNEN_TAGE = 400
NACHRECHNEN_FASSUNG = 2
HEIZKREIS = {"at": "/0/0/0", "vl": "/1/2/0", "vi": "/0/2/0", "soll": "/1/1/0"}
RESTZEIT = "/2/10/0"
TA_HEIZ = "/3/21/0"
TA_ABSENK = "/3/2/0"
STARTS = "/2/80/0"
BH = "/2/81/0"
LEISTUNG = "/0/9/0"
# Nennleistung: PuroWIN führt sie unter `39/61`, andere Wärmeerzeuger unter `11/2`.
NENN = ("/39/61/0", "/11/2/0")
KESSEL = {"starts": STARTS, "bh": BH, "leistung": LEISTUNG}
SCHLUESSEL = f"{DOMAIN}_befund"
# Neue Sammler eines Eintrags; neuer Stand einer Anlage.
SIGNAL_NEU = f"{DOMAIN}_befund_neu_{{}}"
SIGNAL_STAND = f"{DOMAIN}_befund_stand_{{}}"
ARTEN_KREIS = ("waermespeicher", "heizgrenze", "raeume", "naechte", "vorlauf")
ARTEN_KESSEL = ("laufzeit", "energie")
# Namen wie im Reiter; in der Seitenleiste nennt die Meldung, wozu es einen Hinweis gibt.
TITEL = {
    "waermespeicher": "Wärmespeicher des Hauses",
    "heizgrenze": "Heizgrenze im Betrieb",
    "raeume": "Räume erreichen ihr Ziel",
    "naechte": "Übergangszeit nachts",
    "vorlauf": "Vorlauf erreicht sein Soll",
    "laufzeit": "Starts und Laufzeit",
    "energie": "Energie je Heizgradtag",
}
# Der Sensor hinter dem Bild eines Befunds; Heizkreis oder Kessel.
QUELLE = {"vorlauf": HEIZKREIS["vi"], "laufzeit": BH, "energie": LEISTUNG}


def befund_holen(hass: HomeAssistant) -> BefundVerwaltung:
    """Die eine Verwaltung des Befunds."""
    if SCHLUESSEL not in hass.data:
        hass.data[SCHLUESSEL] = BefundVerwaltung(hass)
    return hass.data[SCHLUESSEL]


def speicher(hass: HomeAssistant, entry_id: str, host: str) -> Store:
    """Der Speicher einer Anlage; der Schlüssel trägt Eintrag und Adresse ohne Punkte."""
    return Store(hass, 1, f"{DOMAIN}.befund_{entry_id}_{host.replace('.', '_')}")


async def eintrag_entfernt(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Die Archive eines gelöschten Eintrags verwerfen."""
    for system in systems(entry):
        await speicher(hass, entry.entry_id, str(system.get(CONF_HOST) or "")).async_remove()


def kessel_praefixe(coordinator: Any) -> list[str]:
    """Jede Funktion mit Brennerstarts `2/80` ist ein Kessel."""
    oids = (coordinator.data or {}).get("oids") or {}
    return sorted({k[: -len(STARTS)] for k in oids if k.endswith(STARTS)})


def kessel_geraet(coordinator: Any, prefix: str) -> str | None:
    """Das Gerät eines Kessels; Sensor-Beschreibungen tragen nur ihre volle Adresse."""
    oid = f"{prefix}{STARTS}"
    geraete = (coordinator.data or {}).get("devices") or []
    return next((d["device_id"] for d in geraete if d.get("oid") == oid), None)


def geraete_der_anlage(coordinator: Any) -> list[tuple[str, str, tuple[str, ...]]]:
    """Je Heizkreis und Kessel: Kennung im Befund, Gerät, Arten der Sensoren."""
    liste = [
        (b["device_id"], b["device_id"], ARTEN_KREIS)
        for b in (coordinator.data or {}).get("devices") or []
        if b.get("type") == "climate" and b.get("device_id")
    ]
    for p in kessel_praefixe(coordinator):
        if (device_id := kessel_geraet(coordinator, p)) is not None:
            liste.append((p, device_id, ARTEN_KESSEL))
    return liste


def kennungen(entry: ConfigEntry) -> dict[str, str]:
    """Kennung -> Domäne aller Befund-Sensoren; ohne sie gälten sie beim Aufräumen als verwaist."""
    coordinators = ((getattr(entry, "runtime_data", None) or {}).get("coordinators")) or {}
    return {
        unique_id(device_id, art): "sensor"
        for coordinator in coordinators.values()
        for _, device_id, arten in geraete_der_anlage(coordinator)
        for art in arten
    }


def unique_id(device_id: str, art: str) -> str:
    """Kennung eines Befund-Sensors am Gerät des Heizkreises oder Kessels."""
    return f"{device_id}-befund-{art}"


def quelle_entitaet(register: Any, device_id: str, adresse: str) -> str | None:
    """Die Sensor-Entität einer Adresse am Gerät, nach dem Kennungsschema der Integration."""
    return _entitaet(register, device_id, adresse)


def _entitaet(register: Any, device_id: str, adresse: str) -> str | None:
    kennung = f"{device_id}-{adresse.strip('/').replace('/', '-')}"
    return register.async_get_entity_id("sensor", DOMAIN, kennung)


def _stunde(zeile: dict[str, Any]) -> str:
    start = zeile["start"]
    zeit = dt_util.utc_from_timestamp(start) if isinstance(start, int | float) else start
    return dt_util.as_local(zeit).strftime(STUNDE)


class Sammler:
    """Eine Anlage, also ein Coordinator: Heizkreise und Kessel, ein Archiv, ein Store."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, coordinator: Any, anlage_id: str
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.anlage_id = anlage_id
        self.archiv = Archiv()
        self.letzter: dict[str, Any] | None = None
        # Je Heizkreis die Befunde, deren Hinweis zuletzt in der Seitenleiste stand.
        self._gemeldet: dict[str, frozenset[str]] = {}
        # Die übrigen Sammler desselben Eintrags; die Verwaltung setzt sie.
        self.nachbarn: Any = list
        self._store = speicher(
            hass, entry.entry_id, str(getattr(coordinator, "host", "") or anlage_id)
        )
        self._aufgabe: Any = None

    # --- Speicher -----------------------------------------------------------
    async def laden(self) -> None:
        self.archiv = Archiv.aus_dict(await self._store.async_load())
        if self.archiv.nachgerechnet < NACHRECHNEN_FASSUNG:
            self._aufgabe = self.hass.async_create_background_task(
                self.nachrechnen(), f"heatnexus_befund_{self.anlage_id}"
            )
        self.aktualisieren()

    def speichern(self) -> None:
        self._store.async_delay_save(self.archiv.als_dict, SPEICHERN_S)

    async def beenden(self) -> None:
        if self._aufgabe is not None and not self._aufgabe.done():
            self._aufgabe.cancel()
        await self._store.async_save(self.archiv.als_dict())

    # --- Quellen ------------------------------------------------------------
    def kreise(self) -> list[dict[str, Any]]:
        """Die Klima-Beschreibungen der Heizkreise dieser Anlage."""
        return [b for c, b in Verwaltung.heizkreise(self.entry) if c is self.coordinator]

    def geraete(self) -> list[tuple[str, str, tuple[str, ...]]]:
        return geraete_der_anlage(self.coordinator)

    def _wert(self, prefix: str, adresse: str) -> float | None:
        return get_oid_value(self.coordinator, adresse, prefix)

    def _nenn(self, prefix: str) -> float | None:
        return next((w for a in NENN if (w := self._wert(prefix, a))), None)

    def _raeume(self, device_id: str) -> dict[str, list[float | None]]:
        """Ist und Ziel je Raum; ein Fühler ohne eigenes Ziel nimmt das Raumziel der Automatik."""
        konfig = verwaltung_holen(self.hass).konfig(device_id) or {}
        raeume = {}
        for kennung in konfig.get("raeume", []):
            zustand = self.hass.states.get(kennung)
            if zustand is None:
                continue
            messung = raum_messung(kennung, zustand.state, zustand.attributes)
            if messung is not None and not messung.aus:
                ziel = messung.ziel if messung.ziel is not None else konfig.get("raum_ziel")
                raeume[kennung] = [messung.ist, ziel]
        return raeume

    # --- Sammeln ------------------------------------------------------------
    async def messen(self, jetzt: datetime) -> None:
        """Ein Wert je Heizkreis und Kessel; nach jeder abgeschlossenen Stunde speichern."""
        zeit = dt_util.as_local(jetzt).replace(tzinfo=None)
        geschlossen = False
        for b in self.kreise():
            p = b.get("prefix", "")
            werte: dict[str, Any] = {n: self._wert(p, a) for n, a in HEIZKREIS.items()}
            werte["eingriff"] = (self._wert(p, RESTZEIT) or 0) > 0
            werte["raeume"] = self._raeume(b["device_id"])
            geschlossen |= self.archiv.messen(b["device_id"], zeit, werte)
        for p in kessel_praefixe(self.coordinator):
            nenn, leistung = self._nenn(p), self._wert(p, LEISTUNG)
            kw = leistung / 100 * nenn if leistung is not None and nenn else None
            zaehler = {"starts": self._wert(p, STARTS), "bh": self._wert(p, BH), "kw": kw}
            geschlossen |= self.archiv.messen_kessel(p, zeit, zaehler)
        if geschlossen:
            self.archiv.kuerzen(zeit.date())
            self.speichern()
            self.aktualisieren()

    # --- Nachrechnen ----------------------------------------------------------
    def _reihen(self) -> dict[tuple[str, str], dict[str, str]]:
        """Je Heizkreis und Kessel die Entitäten, deren Langzeitstatistik nachgetragen wird."""
        register = er.async_get(self.hass)
        reihen: dict[tuple[str, str], dict[str, str]] = {}
        for b in self.kreise():
            felder = {n: _entitaet(register, b["device_id"], a) for n, a in HEIZKREIS.items()}
            reihen[("hk", b["device_id"])] = {n: e for n, e in felder.items() if e}
        for p in kessel_praefixe(self.coordinator):
            if device_id := kessel_geraet(self.coordinator, p):
                felder = {n: _entitaet(register, device_id, a) for n, a in KESSEL.items()}
                reihen[("k", p)] = {n: e for n, e in felder.items() if e}
        return reihen

    async def _statistik(self, ids: set[str]) -> dict[str, list[dict[str, Any]]]:
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.statistics import (
            statistics_during_period,
        )

        ende = dt_util.start_of_local_day()
        anfang = ende - timedelta(days=NACHRECHNEN_TAGE)
        return await get_instance(self.hass).async_add_executor_job(
            statistics_during_period, self.hass, anfang, ende, ids, "hour", None, {"mean", "state"}
        )

    def _stunden_aus(
        self, art: str, felder: dict[str, str], statistik: dict[str, list[dict[str, Any]]]
    ) -> dict[str, dict[str, Any]]:
        stunden: dict[str, dict[str, Any]] = {}
        for name, entity_id in felder.items():
            for zeile in statistik.get(entity_id, []):
                wert = zeile.get("mean") if zeile.get("mean") is not None else zeile.get("state")
                stunden.setdefault(_stunde(zeile), {})[name] = wert
        if art == "hk":
            for stunde in stunden.values():
                stunde |= {"eingriff": False, "raeume": {}}
        return stunden

    def _kessel_stunden(self, prefix: str, stunden: dict[str, dict[str, Any]]) -> None:
        nenn = self._nenn(prefix)
        for stunde in stunden.values():
            leistung = stunde.pop("leistung", None)
            stunde["kwh"] = leistung / 100 * nenn if leistung is not None and nenn else None

    async def nachrechnen(self) -> int:
        """Vergangene Stunden aus der Langzeitstatistik; vorhandene bleiben, Räume füllen sich live."""
        if "recorder" not in self.hass.config.components:
            return 0
        reihen = self._reihen()
        ids = {e for felder in reihen.values() for e in felder.values()}
        statistik = await self._statistik(ids) if ids else {}
        neu = 0
        for (art, kennung), felder in reihen.items():
            stunden = self._stunden_aus(art, felder, statistik)
            if art == "hk":
                neu += self.archiv.nachtragen(kennung, stunden)
            else:
                self._kessel_stunden(kennung, stunden)
                neu += self.archiv.nachtragen_kessel(kennung, stunden)
        self.archiv.nachgerechnet = NACHRECHNEN_FASSUNG
        self.archiv.kuerzen(dt_util.now().date())
        self.speichern()
        self.aktualisieren()
        return neu

    # --- Auswerten ------------------------------------------------------------
    def _kreis(self, b: dict[str, Any]) -> auswertung.Kreis:
        verwaltung = verwaltung_holen(self.hass)
        p, device_id = b.get("prefix", ""), b["device_id"]
        konfig = verwaltung.konfig(device_id) or {}
        laufzeit = verwaltung.laufzeiten.get(device_id)
        ist = [paar[0] for paar in self._raeume(device_id).values()]
        return auswertung.Kreis(
            kennung=device_id,
            name=b.get("device_name") or device_id,
            raeume=list(konfig.get("raeume", [])),
            modell=hausmodell_stand(laufzeit) if laufzeit is not None else None,
            raum=raumwert(ist, konfig.get("raum_art", "mittel")) if ist else None,
            ta_heiz=self._wert(p, TA_HEIZ),
            ta_absenk=self._wert(p, TA_ABSENK),
        )

    def _kessel(self, prefix: str) -> auswertung.Kessel:
        starts, bh = self._wert(prefix, STARTS), self._wert(prefix, BH)
        return auswertung.Kessel(
            kennung=prefix,
            name=getattr(self.coordinator, "label", "") or prefix,
            nennleistung=self._nenn(prefix),
            zaehler=(starts, bh) if starts and bh else None,
        )

    def heiztage(self) -> dict[str, bool]:
        kennungen = [b["device_id"] for b in self.kreise()]
        return auswertung.heiztage(self.archiv, kennungen)

    def _versorgte_heiztage(self) -> dict[str, bool]:
        """Heiztage der Anlagen ohne eigenen Kessel; ihre Wärme kommt aus diesem."""
        versorgt: dict[str, bool] = {}
        for nachbar in self.nachbarn():
            if kessel_praefixe(nachbar.coordinator):
                continue
            for datum, geheizt in nachbar.heiztage().items():
                versorgt[datum] = versorgt.get(datum, False) or geheizt
        return versorgt

    def kontext(self) -> auswertung.Kontext:
        kessel = [self._kessel(p) for p in kessel_praefixe(self.coordinator)]
        kreise = [self._kreis(b) for b in self.kreise()]
        land = getattr(self.hass.config, "country", None)
        versorgt = self._versorgte_heiztage() if kessel else {}
        return auswertung.Kontext(
            land, kreise, kessel, waermequelle_extern=not kessel, versorgte_heiztage=versorgt
        )

    def stand(self, kontext: auswertung.Kontext | None = None) -> dict[str, Any]:
        ergebnis = auswertung.anlage(self.archiv, kontext or self.kontext())
        return ergebnis | {"anlage": self.anlage_id, "stand": dt_util.now().isoformat()}

    def aktualisieren(self) -> None:
        """Den Stand für die Sensoren neu rechnen; sie lesen ihn über das Signal."""
        try:
            self.letzter = self.stand()
        except Exception:  # die Sensoren behalten den letzten Stand
            _LOGGER.debug("Befund %s: Auswertung fehlgeschlagen", self.anlage_id, exc_info=True)
            return
        async_dispatcher_send(self.hass, SIGNAL_STAND.format(self.anlage_id))

    def melden(self) -> None:
        """Hinweise je Heizkreis in die Seitenleiste, wenn er es will; nur bei geänderten Hinweisen."""
        verwaltung = verwaltung_holen(self.hass)
        for b in self.kreise():
            device_id = b["device_id"]
            konfig = verwaltung.konfig(device_id) or {}
            hinweise = (
                frozenset(
                    x["art"]
                    for a in (self.letzter or {}).get("abschnitte", [])
                    if a["kennung"] == device_id
                    for x in a["befunde"]
                    if x["status"] == "hinweis"
                )
                if konfig.get("befund_melden")
                else frozenset()
            )
            if hinweise == self._gemeldet.get(device_id, frozenset()):
                continue
            self._gemeldet[device_id] = hinweise
            if not hinweise:
                meldung_entfernen(self.hass, "befund", device_id)
                continue
            w = woerterbuch(self.hass)
            namen = ", ".join(w(TITEL[art]) for art in sorted(hinweise))
            name = b.get("device_name") or device_id
            text = w("{name}: Der Befund meldet einen Hinweis zu {befunde}.").replace(
                "{name}", name
            )
            meldung_setzen(
                self.hass,
                "befund",
                device_id,
                w("Befund"),
                text.replace("{befunde}", namen),
                w("Zum Befund"),
            )

    def befund(self, kennung: str, art: str) -> dict[str, Any] | None:
        """Haus und Heizkreis tragen dieselbe Kennung; gesucht wird über beide Abschnitte."""
        abschnitte = (self.letzter or {}).get("abschnitte", [])
        befunde = (b for a in abschnitte if a["kennung"] == kennung for b in a["befunde"])
        return next((b for b in befunde if b["art"] == art), None)


class BefundVerwaltung:
    """Alle Sammler; ein gemeinsamer Takt je Eintrag."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.sammler: dict[str, Sammler] = {}
        self._abmelden: dict[str, Any] = {}

    def anlagen(self) -> list[str]:
        return list(self.sammler)

    def stand(self, anlage_id: str) -> dict[str, Any] | None:
        sammler = self.sammler.get(anlage_id)
        return sammler.stand() if sammler else None

    def _anlage_id(self, entry: ConfigEntry, coordinator: Any) -> str:
        """Wie im Panel das Gerät der Steuerung; ohne Gerät Eintrag und Adresse."""
        register = dr.async_get(self.hass)
        for b in (coordinator.data or {}).get("devices") or []:
            geraet = geraet_suchen(register, b.get("device_id") or "", entry.entry_id)
            if geraet is not None and geraet.via_device_id:
                return geraet.via_device_id
        return f"{entry.entry_id}_{getattr(coordinator, 'host', '') or id(coordinator)}"

    async def eintrag_starten(self, entry: ConfigEntry) -> None:
        coordinators = ((getattr(entry, "runtime_data", None) or {}).get("coordinators")) or {}
        for coordinator in coordinators.values():
            sammler = Sammler(self.hass, entry, coordinator, self._anlage_id(entry, coordinator))
            sammler.nachbarn = self._nachbarn(sammler)
            try:
                await sammler.laden()
            except Exception:  # ein defekter Befund darf die Einrichtung nicht aufhalten
                _LOGGER.warning(
                    "Befund %s: Speicher nicht lesbar", sammler.anlage_id, exc_info=True
                )
            self.sammler[sammler.anlage_id] = sammler
        async_dispatcher_send(self.hass, SIGNAL_NEU.format(entry.entry_id))
        if entry.entry_id not in self._abmelden:
            self._abmelden[entry.entry_id] = async_track_time_interval(self.hass, self._takt, TAKT)

    def _nachbarn(self, sammler: Sammler) -> Any:
        eintrag = sammler.entry.entry_id
        return lambda: [
            s for s in self.sammler.values() if s.entry.entry_id == eintrag and s is not sammler
        ]

    async def _takt(self, jetzt: datetime) -> None:
        for sammler in list(self.sammler.values()):
            try:
                await sammler.messen(jetzt)
                sammler.melden()
            except Exception:  # der Befund ist eine Zugabe; der Betrieb läuft weiter
                _LOGGER.debug("Befund %s: Messung fehlgeschlagen", sammler.anlage_id, exc_info=True)

    async def eintrag_stoppen(self, entry: ConfigEntry) -> None:
        if (abmelden := self._abmelden.pop(entry.entry_id, None)) is not None:
            abmelden()
        for anlage_id, sammler in list(self.sammler.items()):
            if sammler.entry.entry_id == entry.entry_id:
                await sammler.beenden()
                del self.sammler[anlage_id]
