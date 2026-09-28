"""Automatik eines Heizkreises zur Laufzeit: Auslöser, Eingänge, Ablauf.

Ereignisse setzen nur ein Merkzeichen. Ausgewertet wird im Takt von fünf
Minuten und zu den Entscheidungszeiten des Profils.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..helpers import get_oid_value
from . import eingaben, korrektur, nachladen, profile, regel
from .steller import Stand, Steller

_LOGGER = logging.getLogger(__name__)

TAKT = timedelta(minutes=5)
PROGNOSE_TAKT = timedelta(hours=1)
PROGNOSE_MAX_ALTER = timedelta(hours=6)
ABWESEND_NACH = timedelta(minutes=30)
# Ein ausgefallener Fühler meldet in HA seinen letzten Wert weiter; bleibt er so lange gleich, zählt er nicht.
RAUM_VERALTET = timedelta(hours=12)
STUFEN_FRISCH = timedelta(hours=3)
FENSTER_DAUER = timedelta(minutes=30)
PAUSE_BIS_STUNDE = 5
SICHERHEIT_WIEDERHOLEN_S = 60
VERLAUF_LAENGE = 64
# Diese Adressen braucht die Automatik, auch wenn keine Entität sie abonniert.
ABRUF = ("/2/9/0", "/0/0/0")

SIGNAL_AKTUALISIERT = f"{DOMAIN}_automatik_{{}}"


def ortszeit(wert: Any) -> datetime | None:
    """ISO-Text als Ortszeit; Unlesbares ergibt nichts."""
    if not wert:
        return None
    zeit = dt_util.parse_datetime(str(wert))
    return dt_util.as_local(zeit) if zeit else None


def _messwert(zustand: Any) -> Any:
    """Was sich bei einem lebendigen Fühler ändert: der Zustand oder die Ist-Temperatur."""
    merkmal = eingaben.messmerkmal(zustand.entity_id)
    return zustand.attributes.get(merkmal) if merkmal else zustand.state


def _ganzzahl(wert: float | None) -> int | None:
    return None if wert is None else int(wert)


def naechster_morgen(jetzt: datetime) -> datetime:
    """Das nächste 05:00 nach `jetzt`; so lange hält eine Pause."""
    ziel = jetzt.replace(hour=PAUSE_BIS_STUNDE, minute=0, second=0, microsecond=0)
    return ziel if ziel > jetzt else ziel + timedelta(days=1)


class Laufzeit:
    """Die Automatik eines Heizkreises."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: Any,
        beschreibung: dict[str, Any],
        konfig: dict[str, Any],
        zustand: dict[str, Any] | None,
        speichern: Callable[[], None],
        entry_id: str,
        prognose: Callable[[str, str], Awaitable[list[dict[str, Any]] | None]],
    ) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.entry_id = entry_id
        self.device_id: str = beschreibung["device_id"]
        self.prefix: str = beschreibung.get("prefix", "")
        self.name: str = beschreibung.get("device_name") or self.device_id
        self.konfig = konfig
        self._speichern = speichern
        self._prognose_quelle = prognose
        z = zustand or {}
        self.gedaechtnis = regel.gedaechtnis_aus_dict(z.get("gedaechtnis"))
        self.steller = Steller(
            self.prefix,
            beschreibung.get("preset_allowed") or [],
            coordinator.client.update,
            Stand.aus_dict(z.get("stand")),
        )
        stufen = z.get("stufen")
        self.stufen: tuple[float, float] | None = (
            (float(stufen[0]), float(stufen[1])) if isinstance(stufen, list | tuple) else None
        )
        self.stufen_zeit = ortszeit(z.get("stufen_zeit"))
        self.stufen_start = ortszeit(z.get("stufen_start"))
        self.pausiert_bis = ortszeit(z.get("pausiert_bis"))
        self.beobachtet_seit = ortszeit(z.get("beobachtet_seit")) or dt_util.now()
        # Ohne Vorgeschichte gilt der Start als letzte Anforderung; das verzögert nur Warmwasser.
        self.anforderung_zuletzt = ortszeit(z.get("anforderung_zuletzt")) or dt_util.now()
        self.pv_tage: dict[str, float] = {
            str(k): float(v) for k, v in (z.get("pv_tage") or {}).items()
        }
        try:
            self.zustand = regel.Zustand(z.get("zustand") or regel.Zustand.PROGRAMM)
        except ValueError:
            self.zustand = regel.Zustand.PROGRAMM
        self.begruendung = str(z.get("begruendung") or "")
        self.temperatur = korrektur.Temperaturkorrektur(z.get("temperatur"))
        self.pv = korrektur.Pvkorrektur(z.get("pv"))
        verlauf = z.get("verlauf") if isinstance(z.get("verlauf"), dict) else {}
        self.verlauf: dict[str, Any] = {
            "datum": str(verlauf.get("datum") or ""),
            "stunden": dict(verlauf.get("stunden") or {}),
        }
        self.lage: regel.Lage | None = None
        self.stunden: list[dict[str, Any]] = []
        self._tage: list[tuple[date, float | None, float | None]] = []
        self._prognose_zeit: datetime | None = None
        self._verlauf: deque[tuple[float, float]] = deque(maxlen=VERLAUF_LAENGE)
        self._fenster_bis: datetime | None = None
        self._weg_seit: datetime | None = None
        self._daten_fehlen_seit: datetime | None = None
        self._geaendert = True
        self._laeuft = False
        self._abmelden: list[Callable[[], None]] = []
        self._wiederholung: Callable[[], None] | None = None
        self._fehlschlaege = 0
        self._erzwingen = False
        self._nachladen: Any = None
        # Raumfühler, deren Wert laut Verlauf eingefroren ist; ein neuer Wert löst sie.
        self.eingefroren: set[str] = set()
        # Wie lange Wärmequellen mit Vorrang vor dem Kessel heute geliefert haben.
        self.vorrang = eingaben.lauf_aus_dict(z.get("vorrang"))
        self._lieferbeginn_am: date | None = None
        self._entscheidung_offen = False

    # --- Eigenschaften -------------------------------------------------------
    @property
    def werte(self) -> profile.Werte:
        return profile.werte(
            self.konfig["profil"], self.konfig.get("eigene"), self.konfig["ausrichtung"]
        )

    @property
    def aktiv(self) -> bool:
        return bool(self.konfig.get("aktiv"))

    @property
    def beobachten(self) -> bool:
        return self.konfig.get("modus") != "schalten"

    def als_dict(self) -> dict[str, Any]:
        """Was im Store bleibt."""
        return {
            "gedaechtnis": regel.gedaechtnis_als_dict(self.gedaechtnis),
            "stand": self.steller.stand.als_dict(),
            "stufen": list(self.stufen) if self.stufen else None,
            "stufen_zeit": self.stufen_zeit.isoformat() if self.stufen_zeit else None,
            "stufen_start": self.stufen_start.isoformat() if self.stufen_start else None,
            "pausiert_bis": self.pausiert_bis.isoformat() if self.pausiert_bis else None,
            "beobachtet_seit": self.beobachtet_seit.isoformat(),
            "anforderung_zuletzt": self.anforderung_zuletzt.isoformat(),
            "pv_tage": self.pv_tage,
            "temperatur": self.temperatur.als_dict(),
            "pv": self.pv.als_dict(),
            "verlauf": self.verlauf,
            "vorrang": eingaben.lauf_als_dict(self.vorrang),
            "zustand": self.zustand.value,
            "begruendung": self.begruendung,
        }

    # --- Lebenszyklus --------------------------------------------------------
    async def starten(self) -> None:
        """Auslöser anmelden, Prognose holen, einmal auswerten."""
        client = self.coordinator.client
        for adresse in ABRUF:
            client.register_poll_oid(f"{self.prefix}{adresse}")
        k = self.konfig
        quellen = [*k["raeume"], *k["personen"], *k["fenster"], *k["vorrang"]]
        quellen += [e for e in (k.get("pv"), k.get("pv_ist"), k.get("aussen")) if e]
        self._abmelden.append(async_track_state_change_event(self.hass, quellen, self._ereignis))
        self._abmelden.append(self.coordinator.async_add_listener(self._merken))
        self._abmelden.append(async_track_time_interval(self.hass, self._takt, TAKT))
        self._abmelden.append(
            async_track_time_interval(self.hass, self._prognose_takt, PROGNOSE_TAKT)
        )
        for uhrzeit in (self.werte.entscheidung, self.werte.nachpruefung):
            if uhrzeit:
                stunde, minute = (int(teil) for teil in uhrzeit.split(":"))
                self._abmelden.append(
                    async_track_time_change(
                        self.hass, self._entscheidungszeit, hour=stunde, minute=minute, second=0
                    )
                )
        await self._prognose_holen()
        await self.auswerten()
        self._nachladen = self.hass.async_create_background_task(
            nachladen.heute_nachtragen(self.hass, self), f"heatnexus_automatik_{self.device_id}"
        )

    def stoppen(self) -> None:
        """Alle Auslöser abmelden."""
        for abmelden in self._abmelden:
            abmelden()
        self._abmelden.clear()
        if self._wiederholung:
            self._wiederholung()
            self._wiederholung = None
        if self._nachladen is not None and not self._nachladen.done():
            self._nachladen.cancel()
        client = self.coordinator.client
        for adresse in ABRUF:
            client.unregister_poll_oid(f"{self.prefix}{adresse}")

    async def neu_starten(self, konfig: dict[str, Any]) -> None:
        """Mit geänderten Einstellungen weiterlaufen; der Zustand bleibt."""
        self.stoppen()
        self.konfig = konfig
        await self.starten()

    # --- Auslöser ------------------------------------------------------------
    @callback
    def _merken(self, *_: Any) -> None:
        self._geaendert = True

    @callback
    def _ereignis(self, event: Event) -> None:
        self._geaendert = True
        entity_id = event.data.get("entity_id")
        alt, neu = event.data.get("old_state"), event.data.get("new_state")
        veraendert = alt is None or neu is None or _messwert(alt) != _messwert(neu)
        if veraendert and alt is not None and neu is not None:
            self.eingefroren.discard(entity_id)
        if neu is not None and neu.attributes.get("hvac_action") == "heating":
            self.anforderung_zuletzt = dt_util.now()
        if veraendert and entity_id in self.konfig["raeume"]:
            self._raum_verfolgen()
        if entity_id in self.konfig["vorrang"]:
            self._vorrang_fortschreiben(dt_util.now())
            beginnt = neu is not None and neu.state == "on" and (alt is None or alt.state != "on")
            if beginnt:
                self._lieferbeginn()

    async def _takt(self, _jetzt: datetime) -> None:
        if self._geaendert:
            await self.auswerten()

    async def _entscheidungszeit(self, _jetzt: datetime) -> None:
        await self.auswerten(entscheidungszeit=True)

    async def _prognose_takt(self, _jetzt: datetime) -> None:
        await self._prognose_holen()
        self._geaendert = True

    # --- Ablauf --------------------------------------------------------------
    async def auswerten(self, entscheidungszeit: bool = False) -> None:
        """Ein Lauf der Regel; läuft nie doppelt."""
        if self._laeuft:
            return
        self._laeuft = True
        try:
            await self._auswerten(entscheidungszeit)
        finally:
            self._laeuft = False

    async def _auswerten(self, entscheidungszeit: bool) -> None:
        self._geaendert = False
        entscheidungszeit = entscheidungszeit or self._entscheidung_offen
        self._entscheidung_offen = False
        jetzt = dt_util.now()
        self._daempfen(jetzt)
        self._lernen(jetzt)
        self._vorrang_fortschreiben(jetzt)
        lage = self._lage(jetzt, entscheidungszeit)
        self.lage = lage
        if not self.aktiv:
            self._setzen(regel.Zustand.AUS, "Automatik ausgeschaltet.")
            return
        if not self.beobachten and (
            grund := self.steller.handeingriff(
                self.gedaechtnis,
                jetzt=jetzt,
                betriebswahl=lage.betriebswahl,
                rest_min=self._wert("/2/10/0"),
                betriebsart=_ganzzahl(self._wert("/2/9/0")),
            )
        ):
            self._pausieren(jetzt, grund)
            lage = replace(lage, pausiert_bis=self.pausiert_bis)
        entscheidung = regel.entscheiden(lage, self.gedaechtnis, self.werte)
        angenommen = await self.steller.ausfuehren(
            entscheidung,
            jetzt=jetzt,
            betriebswahl=lage.betriebswahl,
            budget=self.werte.budget,
            beobachten=self.beobachten,
            erzwingen=self._erzwingen,
        )
        self._erzwingen = False
        if angenommen:
            self.gedaechtnis = entscheidung.gedaechtnis
        self._sicherheit_pruefen(entscheidung, angenommen)
        self.steller.abgleichen(self.gedaechtnis, jetzt)
        if entscheidungszeit and not entscheidung.aktionen:
            self.steller.vermerken(jetzt, "geprueft", entscheidung.begruendung)
        self._setzen(entscheidung.zustand, entscheidung.begruendung)

    def _setzen(self, zustand: regel.Zustand, begruendung: str) -> None:
        self.zustand = zustand
        self.begruendung = begruendung
        self._speichern()
        async_dispatcher_send(self.hass, SIGNAL_AKTUALISIERT.format(self.device_id))

    def _pausieren(self, jetzt: datetime, grund: str) -> None:
        self.pausiert_bis = naechster_morgen(jetzt)
        self.gedaechtnis = regel.Gedaechtnis(saison=regel.HEIZEN, saison_seit=jetzt)
        self.steller.freigeben()
        text = f"{grund} Pausiert bis {self.pausiert_bis:%H:%M}."
        self.steller.vermerken(jetzt, "eingriff", text)

    async def uebernehmen(self) -> None:
        """Eine Pause nach Handeingriff sofort aufheben."""
        self.pausiert_bis = None
        await self.auswerten()

    async def zuruecknehmen(self) -> None:
        """Eigene Eingriffe zurücknehmen und das Gedächtnis leeren."""
        jetzt = dt_util.now()
        aktionen: list[regel.Aktion] = []
        if self.gedaechtnis.saison == regel.NUR_WW:
            aktionen.append(regel.Aktion("zurueck", sicherheit=True))
        if regel.absenkung_laeuft(self.gedaechtnis, jetzt):
            aktionen.append(regel.Aktion("absenkung_ende", sicherheit=True))
        kennung = f"automatik_ruecknahme_{self.device_id}"
        if aktionen:
            entscheidung = regel.Entscheidung(
                regel.Zustand.AUS,
                tuple(aktionen),
                "Eigene Eingriffe zurückgenommen.",
                regel.Gedaechtnis(),
            )
            if not await self.steller.ausfuehren(
                entscheidung,
                jetzt=jetzt,
                betriebswahl=_ganzzahl(self._wert("/3/50/0")),
                budget=0,
                beobachten=self.beobachten,
                erzwingen=True,
            ):
                # Das Gedächtnis bleibt, damit ein Wiedereinschalten den Eingriff kennt.
                self._meldung(kennung, "automatik_ruecknahme")
                self._speichern()
                return
        ir.async_delete_issue(self.hass, DOMAIN, kennung)
        self.gedaechtnis = regel.Gedaechtnis()
        self.steller.freigeben()
        self._speichern()

    def gedaechtnis_leeren(self) -> None:
        """Beim Wechsel vom Beobachten zum Schalten: Beobachtetes wurde nie geschrieben."""
        self.gedaechtnis = regel.Gedaechtnis()
        self.steller.freigeben()

    # --- Sicherheit ----------------------------------------------------------
    def _sicherheit_pruefen(self, entscheidung: regel.Entscheidung, angenommen: bool) -> None:
        sicherheit = any(aktion.sicherheit for aktion in entscheidung.aktionen)
        kennung = f"automatik_sicherheit_{self.device_id}"
        if not sicherheit or angenommen:
            if self._fehlschlaege:
                ir.async_delete_issue(self.hass, DOMAIN, kennung)
            self._fehlschlaege = 0
            return
        # Bis zur geplanten Wiederholung zählt kein weiterer Lauf als Fehlschlag.
        if self._wiederholung is not None:
            return
        self._fehlschlaege += 1
        if self._fehlschlaege == 1:
            self._wiederholung = async_call_later(
                self.hass, SICHERHEIT_WIEDERHOLEN_S, self._wiederholen
            )
            return
        self._meldung(kennung, "automatik_sicherheit")

    def _meldung(self, kennung: str, schluessel: str) -> None:
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            kennung,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=schluessel,
            translation_placeholders={"heizkreis": self.name},
        )

    async def _wiederholen(self, _jetzt: datetime) -> None:
        self._wiederholung = None
        # Der einmalige Sicherheitsversuch übergeht die Sperre nach einer Ablehnung.
        self._erzwingen = True
        await self.auswerten()

    # --- Eingänge ------------------------------------------------------------
    def _wert(self, adresse: str) -> float | None:
        return get_oid_value(self.coordinator, adresse, self.prefix)

    def zahl(self, entity_id: str | None) -> float | None:
        if not entity_id or (zustand := self.hass.states.get(entity_id)) is None:
            return None
        if zustand.state in nachladen.UNGUELTIG:
            return None
        try:
            return float(zustand.state)
        except ValueError:
            return None

    def seit(self, entity_id: str) -> datetime | None:
        """Seit wann der Sensor denselben Wert zeigt."""
        if (zustand := self.hass.states.get(entity_id)) is None:
            return None
        # Beim Thermostat ändert sich der Zustand nur mit der Betriebsart, der Messwert als Merkmal.
        return zustand.last_updated if eingaben.ist_thermostat(entity_id) else zustand.last_changed

    def messung(self, entity_id: str) -> eingaben.Messung | None:
        """Ist, eigenes Ziel und Wärmeanforderung eines Raums."""
        if (zustand := self.hass.states.get(entity_id)) is None:
            return None
        return eingaben.raum_messung(entity_id, zustand.state, zustand.attributes)

    def veraltet(self, entity_id: str) -> bool:
        """Ob ein Raumfühler zu lange denselben Wert zeigt."""
        if entity_id in self.eingefroren:
            return True
        seit = self.seit(entity_id)
        return seit is not None and dt_util.utcnow() - seit > RAUM_VERALTET

    def _messungen(self) -> list[eingaben.Messung]:
        """Alle gültigen Räume; ohne eigenes Ziel gilt die Wunschtemperatur der Einrichtung."""
        ergebnis = []
        for kennung in self.konfig["raeume"]:
            if self.veraltet(kennung) or (m := self.messung(kennung)) is None:
                continue
            if m.ziel is None and not m.aus:
                m = m._replace(ziel=self.konfig.get("raum_ziel"))
            ergebnis.append(m)
        return ergebnis

    def _raum(self, messungen: list[eingaben.Messung] | None = None) -> float | None:
        werte: list[float | None] = [
            m.ist for m in (self._messungen() if messungen is None else messungen)
        ]
        return eingaben.raumwert(werte, self.konfig["raum_art"])

    def _ruhig(self, jetzt: datetime) -> bool | None:
        """Ob seit zwei Stunden kein Thermostat Wärme anfordert; ohne Thermostat `None`."""
        if not eingaben.hat_thermostat(self.konfig["raeume"]):
            return None
        return jetzt - self.anforderung_zuletzt >= timedelta(hours=self.werte.ruhe_h)

    def _aussen(self) -> float | None:
        if self.konfig.get("aussen"):
            return self.zahl(self.konfig["aussen"])
        return self._wert("/0/0/0")

    def _daempfen(self, jetzt: datetime) -> None:
        if (at := self._aussen()) is None:
            return
        # Ohne Vorgeschichte das Tagesmittel: Nachmittags läge der Messwert weit darüber.
        if self.stufen is None and (mittel := self.tagesmittel(jetzt.date())):
            self.stufen = (mittel, mittel)
            self.stufen_zeit = jetzt
            self.stufen_start = jetzt
        dauer = (jetzt - self.stufen_zeit).total_seconds() if self.stufen_zeit else 0.0
        self.stufen = eingaben.daempfen(self.stufen, at, dauer, self.werte.tau_h)
        self.stufen_zeit = jetzt

    def aussen_entitaet(self) -> str | None:
        """Die Entität des Außenfühlers: eigene Wahl oder der Fühler des Heizkreises."""
        if self.konfig.get("aussen"):
            return self.konfig["aussen"]
        return er.async_get(self.hass).async_get_entity_id(
            "sensor", DOMAIN, f"{self.device_id}-0-0-0"
        )

    def stunde_nachtragen(self, stunde: int, **werte: float | None) -> None:
        """Werte einer vergangenen Stunde von heute ergänzen; Vorhandenes bleibt."""
        heute = dt_util.now().date().isoformat()
        if self.verlauf["datum"] != heute:
            self.verlauf = {"datum": heute, "stunden": {}}
        eintrag = self.verlauf["stunden"].setdefault(str(stunde), {})
        for name, wert in werte.items():
            if wert is not None and eintrag.get(name) is None:
                eintrag[name] = wert

    def stufen_uebernehmen(self, stufen: tuple[float, float], zeit: datetime) -> None:
        """Die aus dem Tag nachgerechnete gedämpfte AT übernehmen, wenn die eigene jünger ist."""
        # Ein heute gesetzter Startwert beruht auf einer Schätzung, der nachgerechnete auf Messwerten.
        # Nur einen eben geschätzten Wert ersetzen; ein laufender springt sonst bei jedem Neustart.
        if self.stufen_start is not None and dt_util.now() - self.stufen_start > STUFEN_FRISCH:
            return
        self.stufen = stufen
        self.stufen_zeit = zeit
        self.stufen_start = dt_util.start_of_local_day(zeit.date())

    def nachgetragen(self) -> None:
        """Nach dem Nachtragen speichern und die Oberfläche auffrischen."""
        self._speichern()
        async_dispatcher_send(self.hass, SIGNAL_AKTUALISIERT.format(self.device_id))

    def kwh(self, entity_id: str | None) -> float | None:
        if (wert := self.zahl(entity_id)) is None:
            return None
        zustand = self.hass.states.get(entity_id)
        einheit = str(zustand.attributes.get("unit_of_measurement") or "") if zustand else ""
        return wert / 1000 if einheit == "Wh" else wert

    def _lernen(self, jetzt: datetime) -> None:
        """Messwerte für die Prognosekorrektur und den Verlauf des Tages ablegen."""
        at = self._aussen()
        self.temperatur.messen(jetzt, at)
        self.pv.prognose_merken(jetzt, self.kwh(self.konfig.get("pv")))
        self._pv_tag_merken(jetzt)
        if self.konfig.get("pv_ist"):
            self.pv.ist_merken(jetzt, self.kwh(self.konfig["pv_ist"]))
        heute = jetzt.date().isoformat()
        if self.verlauf["datum"] != heute:
            self.verlauf = {"datum": heute, "stunden": {}}
        stunde = self.verlauf["stunden"].setdefault(str(jetzt.hour), {})
        if "at" not in stunde:
            gedaempft = round(self.stufen[1], 2) if self.stufen else None
            stunde.update(at=at, raum=self._raum(), gedaempft=gedaempft)

    def tagesmittel(self, tag: date) -> float | None:
        """Tagesmittel der Prognose, um den gelernten Versatz verschoben."""
        if (mittel := eingaben.tagesmittel(self._tage, tag)) is None:
            return None
        if not self.werte.anpassen:
            return mittel
        versatz = self.temperatur.tagesversatz(self.werte.lernfenster, dt_util.now().date())
        return mittel + (versatz or 0.0)

    def _prognose_des_tages_merken(self, stunden: list[dict[str, Any]]) -> None:
        # Die Stundenprognose beginnt mit der laufenden Stunde; Vergangenes hält der Verlauf.
        heute = dt_util.now().date()
        if self.verlauf["datum"] != heute.isoformat():
            self.verlauf = {"datum": heute.isoformat(), "stunden": {}}
        for eintrag in stunden:
            zeit = ortszeit(eintrag.get("datetime"))
            if zeit is None or zeit.date() != heute:
                continue
            stunde = self.verlauf["stunden"].setdefault(str(zeit.hour), {})
            stunde["prognose"] = eintrag.get("temperature")
            stunde["wolken"] = eintrag.get("cloud_coverage")

    def stundenprognose(self, tag: date) -> dict[int, dict[str, float | None]]:
        """Stundenprognose eines Tages: roh, korrigiert, Bewölkung."""
        fenster, heute = self.werte.lernfenster, dt_util.now().date()
        roh_je_stunde: dict[int, tuple[Any, Any]] = {}
        if self.verlauf["datum"] == tag.isoformat():
            for stunde, werte in self.verlauf["stunden"].items():
                if "prognose" in werte:
                    roh_je_stunde[int(stunde)] = (werte.get("prognose"), werte.get("wolken"))
        for eintrag in self.stunden:
            zeit = ortszeit(eintrag.get("datetime"))
            if zeit is not None and zeit.date() == tag:
                roh_je_stunde[zeit.hour] = (
                    eintrag.get("temperature"),
                    eintrag.get("cloud_coverage"),
                )
        ergebnis: dict[int, dict[str, float | None]] = {}
        for stunde, (roh, wolken) in roh_je_stunde.items():
            versatz = (
                self.temperatur.versatz(stunde, fenster, heute) if self.werte.anpassen else None
            )
            ergebnis[stunde] = {
                "roh": roh,
                "korrigiert": None if roh is None else round(roh + (versatz or 0.0), 1),
                "wolken": wolken,
            }
        return ergebnis

    def _raum_verfolgen(self) -> None:
        if (raum := self._raum()) is None:
            return
        jetzt = dt_util.now()
        if self._fenster_bis and self._verlauf and raum > self._verlauf[-1][1] + 0.1:
            self._fenster_bis = None
        self._verlauf.append((jetzt.timestamp(), raum))
        if self.konfig.get("fenster_erkennung") and eingaben.temperatursturz(
            list(self._verlauf), self.werte.fenster_k_je_h
        ):
            self._fenster_bis = jetzt + FENSTER_DAUER

    def _fenster(self, jetzt: datetime) -> bool:
        for kennung in self.konfig["fenster"]:
            if (zustand := self.hass.states.get(kennung)) and zustand.state == "on":
                return True
        return self._fenster_bis is not None and jetzt < self._fenster_bis

    def _abwesend(self, jetzt: datetime) -> bool:
        personen = self.konfig["personen"]
        if not personen:
            return False
        zustaende = [z.state if (z := self.hass.states.get(p)) else "" for p in personen]
        if any(zustand == "home" or zustand in nachladen.UNGUELTIG for zustand in zustaende):
            self._weg_seit = None
            return False
        self._weg_seit = self._weg_seit or jetzt
        return jetzt - self._weg_seit >= ABWESEND_NACH

    def sonne(self, tag: date) -> tuple[datetime | None, datetime | None]:
        """Sonnenauf- und -untergang des Tages in Ortszeit."""
        aufgang = get_astral_event_date(self.hass, "sunrise", tag)
        untergang = get_astral_event_date(self.hass, "sunset", tag)
        return (
            dt_util.as_local(aufgang) if aufgang else None,
            dt_util.as_local(untergang) if untergang else None,
        )

    def _pv_tag_merken(self, jetzt: datetime) -> None:
        """Die PV-Prognose des Tages als Maßstab für spätere Tage ablegen."""
        if (pv := self.zahl(self.konfig.get("pv"))) is None:
            return
        heute = jetzt.date().isoformat()
        self.pv_tage[heute] = max(pv, self.pv_tage.get(heute, 0.0))
        grenze = (jetzt.date() - timedelta(days=korrektur.PV_TAGE)).isoformat()
        self.pv_tage = {tag: wert for tag, wert in self.pv_tage.items() if tag > grenze}

    def sonnenquote(self, tag: date, pv_sensor: str | None) -> float | None:
        """Sonnenquote eines Tages; Betrieb und Vorschau rechnen sie gleich."""
        heute = dt_util.now().date()
        if self.konfig.get("pv_ist") and self.werte.anpassen:
            quote = korrektur.sonnenquote_korrigiert(
                self.kwh(pv_sensor),
                self.pv.faktor(self.werte.lernfenster, heute),
                self.pv.bester_ist(heute),
            )
            if quote is not None:
                return quote
        bisher = [wert for datum, wert in self.pv_tage.items() if datum != heute.isoformat()]
        if (quote := eingaben.sonnenquote_aus_pv(self.zahl(pv_sensor), bisher)) is not None:
            return quote
        aufgang, untergang = self.sonne(tag)
        if aufgang is None or untergang is None:
            return None
        return self.quote_aus_bewoelkung(tag, aufgang, untergang)

    def quote_aus_bewoelkung(
        self, tag: date, aufgang: datetime, untergang: datetime
    ) -> float | None:
        # Aus allen Stunden des Tages, auch den schon vergangenen aus dem Verlauf.
        stunden = [
            (aufgang.replace(hour=stunde, minute=0, second=0, microsecond=0), werte["wolken"])
            for stunde, werte in self.stundenprognose(tag).items()
        ]
        return eingaben.sonnenquote_aus_bewoelkung(stunden, aufgang, untergang)

    def _lage(self, jetzt: datetime, entscheidungszeit: bool) -> regel.Lage:
        messungen = self._messungen()
        if any(m.heizt for m in messungen):
            self.anforderung_zuletzt = jetzt
        raum = self._raum(messungen)
        at = self._aussen()
        frisch = (
            self._prognose_zeit is not None and jetzt - self._prognose_zeit <= PROGNOSE_MAX_ALTER
        )
        daten_ok = raum is not None and at is not None and frisch
        if daten_ok:
            self._daten_fehlen_seit = None
        elif self._daten_fehlen_seit is None:
            self._daten_fehlen_seit = jetzt
        untergang = self.sonne(jetzt.date())[1]
        return regel.Lage(
            jetzt=jetzt,
            at=at,
            at_gedaempft=self.stufen[1] if self.stufen else None,
            soll=self._wert("/1/1/0"),
            raeume=tuple((m.ist, m.ziel) for m in messungen if not m.aus),
            aus=tuple(m.ist for m in messungen if m.aus),
            raum_art=self.konfig["raum_art"],
            ruhig=self._ruhig(jetzt),
            sonnenquote=self.sonnenquote(jetzt.date(), self.konfig.get("pv")),
            mittel_heute=self.tagesmittel(jetzt.date()),
            mittel_morgen=self.tagesmittel(jetzt.date() + timedelta(days=1)),
            sonnenuntergang=untergang,
            betriebswahl=_ganzzahl(self._wert("/3/50/0")),
            betriebsart=_ganzzahl(self._wert("/2/9/0")),
            daten_ok=daten_ok,
            daten_fehlen_seit=self._daten_fehlen_seit,
            fenster_offen=self._fenster(jetzt),
            abwesend=self._abwesend(jetzt),
            pausiert_bis=self.pausiert_bis,
            entscheidungszeit=entscheidungszeit,
            absenkung_moeglich=self._wert("/2/10/0") is not None,
            **self._vorrang_lage(jetzt),
        )

    def _lieferbeginn(self) -> None:
        """Einmal am Tag sofort entscheiden, statt bis zur nächsten Entscheidungszeit zu warten."""
        heute = dt_util.now().date()
        if self._lieferbeginn_am == heute:
            return
        self._lieferbeginn_am = heute
        # Vorgemerkt: Läuft gerade eine Auswertung, holt der nächste Lauf die Entscheidung nach.
        self._entscheidung_offen = True
        self._geaendert = True
        self.hass.async_create_task(self.auswerten())

    def _vorrang_liefert(self) -> list[str]:
        return [
            kennung
            for kennung in self.konfig["vorrang"]
            if (zustand := self.hass.states.get(kennung)) is not None and zustand.state == "on"
        ]

    def _vorrang_fortschreiben(self, jetzt: datetime) -> None:
        if not self.konfig["vorrang"]:
            return
        liefert = bool(self._vorrang_liefert())
        self.vorrang = eingaben.lauf_fortschreiben(self.vorrang, jetzt, liefert)
        if liefert:
            self.stunde_nachtragen(jetzt.hour, vorrang=True)

    def _vorrang_lage(self, jetzt: datetime) -> dict[str, Any]:
        if not self.konfig["vorrang"]:
            return {}
        liefert = self._vorrang_liefert()
        return {
            "vorrang_laeuft": bool(liefert),
            "vorrang_minuten": eingaben.lauf_minuten(self.vorrang, jetzt),
            "vorrang_name": self._quellenname(liefert[0]) if liefert else None,
        }

    def _quellenname(self, entity_id: str) -> str:
        """Name des Geräts der Quelle; der Entitätsname allein heißt nur „Wärmelieferung“."""
        eintrag = er.async_get(self.hass).async_get(entity_id)
        geraet = (
            dr.async_get(self.hass).async_get(eintrag.device_id)
            if eintrag and eintrag.device_id
            else None
        )
        if geraet is not None and (name := geraet.name_by_user or geraet.name):
            return name
        zustand = self.hass.states.get(entity_id)
        return str(zustand.attributes.get("friendly_name") or entity_id) if zustand else entity_id

    async def _prognose(self, art: str) -> list[dict[str, Any]] | None:
        return await self._prognose_quelle(self.konfig["wetter"], art)

    async def _prognose_holen(self) -> None:
        stunden = await self._prognose("hourly")
        tage = await self._prognose("daily")
        if stunden is not None:
            self.stunden = stunden
            self._prognose_des_tages_merken(stunden)
            self.temperatur.vormerken(
                [
                    (zeit, eintrag.get("temperature"))
                    for eintrag in stunden
                    if (zeit := ortszeit(eintrag.get("datetime"))) is not None
                ],
                dt_util.now(),
            )
        if tage is not None:
            self._tage = [
                (zeit.date(), eintrag.get("temperature"), eintrag.get("templow"))
                for eintrag in tage
                if (zeit := ortszeit(eintrag.get("datetime"))) is not None
            ]
        if stunden is not None or tage is not None:
            self._prognose_zeit = dt_util.now()
