"""Automatik eines Heizkreises zur Laufzeit: Auslöser, Eingänge, Ablauf.

Ereignisse setzen nur ein Merkzeichen. Ausgewertet wird im Takt von fünf
Minuten und zu den Entscheidungszeiten des Profils.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import date, datetime, time, timedelta
import logging
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from ..const import DOMAIN, PANEL_URL
from ..helpers import get_oid_value
from ..registrierung import geraetename
from ..texte import woerterbuch
from . import eingaben, hausmodell, korrektur, nachladen, profile, regel, stundenmodus, tagesansicht
from .optimierung import OptimierungMixin
from .quellen import QuellenMixin, ortszeit
from .steller import Stand, Steller, braucht_bestaetigung, nur_ww_wert
from .vorausschau import VorausschauMixin

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
# So lange wartet die Regel nach dem Start auf den ersten Abruf der Werte in `ABRUF`.
STEUERUNG_WARTEN = timedelta(minutes=10)
MODUS_ARTEN = ("absenkung", "nur_ww", "heizpause")
# Diese Adressen braucht die Automatik, auch wenn keine Entität sie abonniert.
# Heizgrenzen der Steuerung (`3/21`, `3/2`) gehören dazu: an ihnen richtet sich die Regel aus.
# Der Vorlauf-Ist dient nur dem Hausmodell; die Regel wartet nicht darauf.
VORLAUF_IST = "/0/2/0"
ABRUF = ("/2/9/0", "/0/0/0", "/1/2/0", "/3/21/0", "/3/2/0", VORLAUF_IST)
HEIZGRENZEN = {
    "heizbetrieb": ("/3/21/0", "Heizbetrieb"),
    "absenkbetrieb": ("/3/2/0", "Absenkbetrieb"),
}

SIGNAL_AKTUALISIERT = f"{DOMAIN}_automatik_{{}}"
SIGNAL_SYSTEM = f"{DOMAIN}_automatik_system_{{}}"
EREIGNIS_EMPFEHLUNG = f"{DOMAIN}_automatik_empfehlung"
EMPFEHLUNG_MAX = timedelta(hours=6)
# So lange gilt nach einer Rücknahme der Raumsoll vor dem Eingriff, solange `1/1` noch den geschriebenen zeigt.
SOLL_NACHLAUF = timedelta(minutes=10)
# Dieselbe Prüfung innerhalb dieser Zeit steht nur einmal im Protokoll, etwa bei mehreren Moduswechseln.
GEPRUEFT_RUHE = timedelta(minutes=15)


def _messwert(zustand: Any) -> Any:
    """Was sich bei einem lebendigen Fühler ändert: der Zustand oder die Ist-Temperatur."""
    merkmal = eingaben.messmerkmal(zustand.entity_id)
    return zustand.attributes.get(merkmal) if merkmal else zustand.state


def _ganzzahl(wert: float | None) -> int | None:
    return None if wert is None else int(wert)


def _kommazahl(wert: Any) -> float | None:
    """Eine Zahl aus dem Store; Unlesbares ergibt nichts."""
    if isinstance(wert, bool) or not isinstance(wert, int | float):
        return None
    return float(wert)


def _tageswerte(roh: Any) -> dict[str, float]:
    """Minuten je Tag aus dem Store; Unlesbares entfällt."""
    if not isinstance(roh, dict):
        return {}
    return {str(k): w for k, v in roh.items() if (w := _kommazahl(v)) is not None}


def naechster_morgen(jetzt: datetime) -> datetime:
    """Das nächste 05:00 nach `jetzt`; so lange hält eine Pause."""
    ziel = jetzt.replace(hour=PAUSE_BIS_STUNDE, minute=0, second=0, microsecond=0)
    return ziel if ziel > jetzt else ziel + timedelta(days=1)


def _gueltige_empfehlung(wert: Any) -> dict[str, Any] | None:
    """Eine gespeicherte Empfehlung gilt nur vollständig und mit lesbarer Zeit."""
    if not isinstance(wert, dict) or not isinstance(wert.get("begruendung"), str):
        return None
    try:
        regel.Zustand(wert["zustand"])
        seit = datetime.fromisoformat(wert["seit"])
    except (KeyError, TypeError, ValueError):
        return None
    return wert if seit.tzinfo is not None else None


def _gueltig_verworfen(wert: Any) -> dict[str, Any]:
    """Verworfene Zustände eines Tages; alles Unlesbare zählt als nichts verworfen."""
    if not isinstance(wert, dict) or not isinstance(wert.get("tag"), str):
        return {}
    zustaende = wert.get("zustaende")
    if not isinstance(zustaende, list) or not all(isinstance(z, str) for z in zustaende):
        return {}
    return {"tag": wert["tag"], "zustaende": zustaende}


def _verlauf_laden(roh: Any) -> dict[str, Any]:
    """Der gespeicherte Tagesverlauf; Fremdes ergibt einen leeren."""
    verlauf = roh if isinstance(roh, dict) else {}
    return {"datum": str(verlauf.get("datum") or ""), "stunden": dict(verlauf.get("stunden") or {})}


class Laufzeit(QuellenMixin, VorausschauMixin, OptimierungMixin):
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
        # Die Steuerung meldet Umlaute mitunter als Ersatzzeichen; das Gerät trägt den gepflegten Namen.
        self._rohname: str = beschreibung.get("device_name") or self.device_id
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
        self._stufen_laden(z)
        self.pausiert_bis = ortszeit(z.get("pausiert_bis"))
        self.beobachtet_seit = ortszeit(z.get("beobachtet_seit")) or dt_util.now()
        # Ohne Vorgeschichte gilt der Start als letzte Anforderung; das verzögert nur Warmwasser.
        self.anforderung_zuletzt = ortszeit(z.get("anforderung_zuletzt")) or dt_util.now()
        self.pv_tage = _tageswerte(z.get("pv_tage"))
        try:
            self.zustand = regel.Zustand(z.get("zustand") or regel.Zustand.PROGRAMM)
        except ValueError:
            self.zustand = regel.Zustand.PROGRAMM
        self.begruendung = str(z.get("begruendung") or "")
        self._grenzen_laden(z)
        self.temperatur = korrektur.Temperaturkorrektur(z.get("temperatur"))
        self.pv = korrektur.Pvkorrektur(z.get("pv"))
        self.verlauf: dict[str, Any] = _verlauf_laden(z.get("verlauf"))
        self._optimierung_laden(z)
        self.lage: regel.Lage | None = None
        self.stunden: list[dict[str, Any]] = []
        self._tage: list[tuple[date, float | None, float | None]] = []
        self._prognose_zeit: datetime | None = None
        self._verlauf: deque[tuple[float, float]] = deque(maxlen=VERLAUF_LAENGE)
        self._fenster_bis: datetime | None = None
        self._weg_seit: datetime | None = None
        self._daten_fehlen_seit: datetime | None = None
        self._raeume_fehlen_seit: datetime | None = None
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
        self.vorrang_verlauf = _tageswerte(z.get("vorrang_verlauf"))
        # Wie lange Sonnentag und nur Warmwasser heute an der Steuerung galten.
        modus = z.get("modus_lauf")
        self.modus_lauf = (
            {art: eingaben.lauf_aus_dict(modus.get(art)) for art in MODUS_ARTEN}
            if isinstance(modus, dict)
            else self._lauf_aus_protokoll(dt_util.now())
        )
        self._gestartet = dt_util.now()
        self._wartet = False
        self._lieferbeginn_am: date | None = None
        self._offenes_laden(z)

    # --- Eigenschaften -------------------------------------------------------
    @property
    def werte(self) -> profile.Werte:
        return profile.werte(
            self.konfig["profil"], self.konfig.get("eigene"), self.konfig["ausrichtung"]
        )

    @property
    def prognose_frisch(self) -> bool:
        """Ob die Wetterprognose jünger als sechs Stunden ist."""
        zeit = self._prognose_zeit
        return zeit is not None and dt_util.now() - zeit <= PROGNOSE_MAX_ALTER

    @property
    def aktiv(self) -> bool:
        return bool(self.konfig.get("aktiv"))

    @property
    def beobachten(self) -> bool:
        return self.konfig.get("modus") == "beobachten"

    @property
    def bezeichnung(self) -> str:
        """„Anlage · Heizkreis“; zwei Anlagen führen oft gleichnamige Heizkreise."""
        anlage = getattr(self.coordinator, "label", None)
        return f"{anlage} · {self.name}" if anlage else self.name

    @property
    def empfehlen(self) -> bool:
        """Eingriffe, die weniger heizen, warten auf eine Bestätigung."""
        return self.konfig.get("modus") == "empfehlen"

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
            "vorrang_verlauf": dict(self.vorrang_verlauf),
            "modus_lauf": {
                art: eingaben.lauf_als_dict(lauf) for art, lauf in self.modus_lauf.items()
            },
            "zustand": self.zustand.value,
            "begruendung": self.begruendung,
            "grenze_steuerung": self.grenze_zuletzt,
            "grenze_absenk": self.absenk_zuletzt,
            "empfehlung": self.empfehlung,
            "verworfen": self.verworfen,
            "hausmodell": hausmodell.als_dict(self.hausmodell) if self.hausmodell else None,
            "hausmodell_tag": self._fehler_tag,
            **self.optimierung_als_dict(),
        }

    # --- Lebenszyklus --------------------------------------------------------
    async def starten(self, entscheidungszeit: bool = False) -> None:
        """Auslöser anmelden, Prognose holen, einmal auswerten."""
        self._gestartet = dt_util.now()
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
            async_track_time_change(self.hass, self._stundentakt, minute=0, second=5)
        )
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
        await self.auswerten(entscheidungszeit)
        self._nachladen = self.hass.async_create_background_task(
            nachladen.heute_nachtragen(self.hass, self), f"heatnexus_automatik_{self.device_id}"
        )
        self._lernen_starten()
        self._optimierung_starten()

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
        self._lernen_beenden()
        self._optimierung_beenden()
        client = self.coordinator.client
        for adresse in ABRUF:
            client.unregister_poll_oid(f"{self.prefix}{adresse}")

    async def neu_starten(self, konfig: dict[str, Any], entscheidungszeit: bool = False) -> None:
        """Mit geänderten Einstellungen weiterlaufen; der Zustand bleibt."""
        self.stoppen()
        self.konfig = konfig
        await self.starten(entscheidungszeit)

    # --- Auslöser ------------------------------------------------------------
    @callback
    def _merken(self, *_: Any) -> None:
        self._geaendert = True
        if self._wartet and not self._steuerung_fehlt(dt_util.now()):
            self._wartet = False
            self.hass.async_create_task(self.auswerten())

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
        # Läuft gerade eine Auswertung, holt der nächste Lauf die Entscheidung nach.
        self._entscheidung_offen = True
        self._geaendert = True
        await self.auswerten()

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
        # Eine Bestätigung, die während des Laufs kam, wartet nicht auf den nächsten Takt.
        if self._bestaetigt_offen and not self._wartet:
            self.hass.async_create_task(self.auswerten())

    async def _auswerten(self, entscheidungszeit: bool) -> None:
        self._geaendert = False
        bestaetigung = self._bestaetigung()
        entscheidungszeit = entscheidungszeit or self._entscheidung_offen or bool(bestaetigung)
        self._entscheidung_offen = False
        jetzt = dt_util.now()
        self._daempfen(jetzt)
        self._lernen(jetzt)
        self._vorrang_fortschreiben(jetzt)
        self._ablauf_merken(jetzt)
        lage = self._lage(jetzt, entscheidungszeit)
        self.lage = lage
        if not self.aktiv:
            self.empfehlung = None
            self._setzen(regel.Zustand.AUS, "Automatik ausgeschaltet.")
            return
        self._wartet = self._steuerung_fehlt(jetzt)
        if self._wartet:
            self._geaendert = True
            self._bestaetigt_offen |= bestaetigung is not None
            # Die Werte stehen schon in der Lage; die Sensoren zeigen sie, auch wenn die Regel noch wartet.
            async_dispatcher_send(self.hass, SIGNAL_AKTUALISIERT.format(self.device_id))
            async_dispatcher_send(self.hass, SIGNAL_SYSTEM.format(self.entry_id))
            return
        if not self.beobachten and (
            grund := self.steller.handeingriff(
                self.gedaechtnis,
                jetzt=jetzt,
                betriebswahl=lage.betriebswahl,
                rest_min=self._wert("/2/10/0"),
                betriebsart=_ganzzahl(self._wert("/2/9/0")),
                raumsoll=self._wert("/1/1/0"),
            )
        ):
            self._pausieren(jetzt, grund)
            lage = replace(lage, pausiert_bis=self.pausiert_bis)
        entscheidung = regel.entscheiden(lage, self.gedaechtnis, self.werte)
        bestaetigt = self._bestaetigt(bestaetigung, entscheidung)
        entscheidung = self._ohne_verworfenes(entscheidung, bestaetigt, jetzt)
        angenommen = await self.steller.ausfuehren(
            entscheidung,
            jetzt=jetzt,
            betriebswahl=lage.betriebswahl,
            budget=self._budget(bestaetigt),
            beobachten=self.beobachten,
            erzwingen=self._erzwingen or bestaetigt,
            empfehlen=self.empfehlen and not bestaetigt,
        )
        self._erzwingen = False
        if angenommen:
            self.gedaechtnis = entscheidung.gedaechtnis
        elif self.steller.erledigt:
            self.gedaechtnis = regel.nach_teilerfolg(self.gedaechtnis, self.steller.erledigt, jetzt)
        self._sicherheit_pruefen(entscheidung, angenommen)
        self.steller.abgleichen(self.gedaechtnis, jetzt)
        if entscheidungszeit and not entscheidung.aktionen:
            self._geprueft(jetzt, entscheidung.begruendung)
        if self.steller.empfohlen:
            self._empfohlen(jetzt, entscheidung, entscheidungszeit)
            return
        self._empfehlung_pruefen(jetzt, entscheidung, entscheidungszeit, angenommen, bestaetigt)
        self._setzen(entscheidung.zustand, entscheidung.begruendung)

    def _geprueft(self, jetzt: datetime, text: str) -> None:
        letzter = next(iter(self.steller.stand.protokoll), None)
        if (
            letzter is not None
            and letzter.get("art") == "geprueft"
            and letzter.get("text") == text
            and jetzt - datetime.fromisoformat(letzter["zeit"]) < GEPRUEFT_RUHE
        ):
            return
        self.steller.vermerken(jetzt, "geprueft", text)

    def _setzen(self, zustand: regel.Zustand, begruendung: str) -> None:
        self.zustand = zustand
        self.begruendung = begruendung
        self._modus_fortschreiben(dt_util.now())
        self._aktion_merken(dt_util.now())
        self._seitenleiste()
        self._speichern()
        async_dispatcher_send(self.hass, SIGNAL_AKTUALISIERT.format(self.device_id))
        async_dispatcher_send(self.hass, SIGNAL_SYSTEM.format(self.entry_id))

    # --- Empfehlung ----------------------------------------------------------
    def _offenes_laden(self, z: dict[str, Any]) -> None:
        """Was auf einen Lauf wartet: Entscheidungszeit, Bestätigung, offene Empfehlung."""
        self._entscheidung_offen = False
        self._bestaetigt_offen = False
        self.empfehlung: dict[str, Any] | None = _gueltige_empfehlung(z.get("empfehlung"))
        self.verworfen: dict[str, Any] = _gueltig_verworfen(z.get("verworfen"))
        self._soll_ersatz: tuple[float, float, datetime] | None = None
        self._hausmodell_laden(z)
        # Was zuletzt in der Seitenleiste steht: Beginn und Begründung der Empfehlung.
        self._gemeldet: tuple[str, str] | None = None

    def _taste(self, art: str) -> str | None:
        """Die Entität einer Taste; sie entsteht erst nach dem ersten Lauf."""
        from .verwaltung import unique_id

        return er.async_get(self.hass).async_get_entity_id(
            "button", DOMAIN, unique_id(self.device_id, art)
        )

    def _seitenleiste(self) -> None:
        """Eine offene Empfehlung steht in der Seitenleiste; ist sie erledigt, verschwindet sie."""
        empfehlung = self.empfehlung if self.empfehlen and self.werte.melden else None
        if empfehlung is None:
            self.meldung_entfernen()
            return
        stand = (empfehlung["seit"], empfehlung["begruendung"])
        if stand == self._gemeldet:
            return
        w = woerterbuch(self.hass)
        verweis = f"[{w('Im Reiter Automatik übernehmen oder verwerfen')}](/{PANEL_URL})"
        persistent_notification.async_create(
            self.hass,
            f"{w.satz(empfehlung['begruendung'])}\n\n{verweis}",
            title=f"{w('Empfehlung der Automatik')} – {self.bezeichnung}",
            notification_id=f"{DOMAIN}_empfehlung_{self.device_id}",
        )
        self._gemeldet = stand

    def meldung_entfernen(self) -> None:
        """Die Benachrichtigung zur Empfehlung aus der Seitenleiste nehmen."""
        if self._gemeldet is not None:
            persistent_notification.async_dismiss(
                self.hass, f"{DOMAIN}_empfehlung_{self.device_id}"
            )
            self._gemeldet = None

    def _heute_verworfen(self, jetzt: datetime) -> list[str]:
        if self.verworfen.get("tag") != jetzt.date().isoformat():
            return []
        return list(self.verworfen["zustaende"])

    def _ohne_verworfenes(
        self, entscheidung: regel.Entscheidung, bestaetigt: bool, jetzt: datetime
    ) -> regel.Entscheidung:
        """Was heute verworfen wurde, wird nicht erneut empfohlen; an der Steuerung bleibt alles."""
        if bestaetigt or not self.empfehlen or not braucht_bestaetigung(entscheidung.aktionen):
            return entscheidung
        if entscheidung.zustand.value not in self._heute_verworfen(jetzt):
            return entscheidung
        zustand = regel.zustand_aus(self.gedaechtnis, jetzt)
        text = f"Verworfen: {entscheidung.begruendung}"
        return regel.Entscheidung(zustand, (), text, self.gedaechtnis)

    def _bestaetigung(self) -> bool | None:
        """Eine offene Bestätigung abholen: `None` ohne, sonst die Entscheidungszeit der Empfehlung."""
        offen, self._bestaetigt_offen = self._bestaetigt_offen, False
        if not offen or self.empfehlung is None:
            return None
        return bool(self.empfehlung.get("entscheidungszeit"))

    def _bestaetigt(self, bestaetigung: bool | None, entscheidung: regel.Entscheidung) -> bool:
        """Die Zustimmung gilt nur für den Zustand, den der Nutzer gesehen hat."""
        if bestaetigung is None or self.empfehlung is None:
            return False
        if not braucht_bestaetigung(entscheidung.aktionen):
            return True
        return entscheidung.zustand.value == self.empfehlung["zustand"]

    def _budget(self, bestaetigt: bool) -> int:
        """Eine Bestätigung ist die Entscheidung des Nutzers; das Tagesbudget hält sie nicht auf."""
        if not bestaetigt:
            return self.werte.budget
        return max(self.werte.budget, self.steller.stand.eingriffe + 1)

    def _empfohlen(
        self, jetzt: datetime, entscheidung: regel.Entscheidung, entscheidungszeit: bool
    ) -> None:
        """An der Steuerung bleibt alles, wie es ist; der Zustand zeigt das, die Begründung den Vorschlag."""
        self._empfehlung_merken(jetzt, entscheidung, entscheidungszeit)
        zustand = regel.zustand_aus(self.gedaechtnis, jetzt)
        self._setzen(zustand, f"Empfehlung: {entscheidung.begruendung}")

    def _empfehlung_merken(
        self, jetzt: datetime, entscheidung: regel.Entscheidung, entscheidungszeit: bool
    ) -> None:
        """Eine neue Empfehlung melden; dieselbe bleibt still und frischt nur ihre Begründung auf."""
        neu = entscheidung.zustand.value
        if self.empfehlung is not None and self.empfehlung.get("zustand") == neu:
            self.empfehlung = {**self.empfehlung, "begruendung": entscheidung.begruendung}
            return
        self.empfehlung = {
            "zustand": neu,
            "begruendung": entscheidung.begruendung,
            "seit": jetzt.isoformat(),
            "entscheidungszeit": entscheidungszeit,
        }
        self.hass.bus.async_fire(
            EREIGNIS_EMPFEHLUNG,
            {
                "heizkreis": self.device_id,
                "name": self.bezeichnung,
                "zustand": neu,
                "begruendung": woerterbuch(self.hass).satz(entscheidung.begruendung),
                "taste": self._taste("empfehlung_uebernehmen"),
                "verwerfen": self._taste("empfehlung_verwerfen"),
            },
        )

    def _empfehlung_pruefen(
        self,
        jetzt: datetime,
        entscheidung: regel.Entscheidung,
        entscheidungszeit: bool,
        angenommen: bool,
        bestaetigt: bool,
    ) -> None:
        """Eine offene Empfehlung gilt, bis sie überholt ist."""
        if self.empfehlung is None:
            return
        seit = datetime.fromisoformat(self.empfehlung["seit"])
        if (
            (angenommen and (entscheidung.aktionen or bestaetigt))
            or entscheidungszeit
            or jetzt - seit > EMPFEHLUNG_MAX
            or not self.empfehlen
        ):
            self.empfehlung = None

    async def empfehlung_uebernehmen(self) -> None:
        """Die offene Empfehlung ausführen: Die Regel rechnet sofort neu und darf schreiben."""
        if self.empfehlung is None:
            return
        # Läuft gerade eine Auswertung, holt der nächste Lauf die Bestätigung nach.
        self._bestaetigt_offen = True
        self._geaendert = True
        await self.auswerten()

    async def empfehlung_verwerfen(self) -> None:
        """Die offene Empfehlung verwerfen; derselbe Vorschlag kommt heute nicht wieder."""
        if self.empfehlung is None:
            return
        jetzt = dt_util.now()
        tag = jetzt.date().isoformat()
        zustand = self.empfehlung["zustand"]
        self.verworfen = {"tag": tag, "zustaende": sorted({*self._heute_verworfen(jetzt), zustand})}
        if zustand == regel.Zustand.HEIZPAUSE.value:
            # Ohne Heizpause rechnet die Regel neu; ein Ausstieg aus nur Warmwasser bleibt möglich.
            self.gedaechtnis = replace(self.gedaechtnis, pause_sperre=tag)
        self.steller.vermerken(jetzt, "verworfen", self.empfehlung["begruendung"])
        self.empfehlung = None
        self._geaendert = True
        await self.auswerten()

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
                erledigt = self.steller.erledigt
                self.gedaechtnis = regel.nach_teilerfolg(self.gedaechtnis, erledigt, jetzt)
                self._meldung(kennung, "automatik_ruecknahme")
                self._speichern()
                return
        ir.async_delete_issue(self.hass, DOMAIN, kennung)
        g = self.gedaechtnis
        if aktionen and g.absenkung_soll is not None and g.absenkung_basis is not None:
            self._soll_ersatz = (g.absenkung_soll, g.absenkung_basis, jetzt)
        self.gedaechtnis = regel.Gedaechtnis()
        self.steller.freigeben()
        self._speichern()

    async def heizgrenzen_setzen(self, werte: dict[str, float]) -> None:
        """Heizgrenzen der Steuerung von Hand setzen: kein Budget, kein Eingriff der Automatik."""
        geschrieben: dict[str, float] = {}
        fehler: Exception | None = None
        for name, wert in werte.items():
            try:
                await self.coordinator.client.update(
                    f"{self.prefix}{HEIZGRENZEN[name][0]}", f"{wert:.1f}"
                )
            except Exception as grund:  # jede Ablehnung der Steuerung geht als Meldung zurück
                fehler = grund
                break
            geschrieben[name] = wert
        # Was schon an der Steuerung steht, gehört ins Protokoll, auch wenn der Rest scheiterte.
        if geschrieben:
            self._heizgrenzen_vermerken(geschrieben)
        if fehler is not None:
            offen = ", ".join(HEIZGRENZEN[n][1] for n in werte if n not in geschrieben)
            raise ValueError(f"Die Steuerung hat {offen} nicht übernommen: {fehler}") from fehler

    def _heizgrenzen_vermerken(self, werte: dict[str, float]) -> None:
        text = ", ".join(
            f"{HEIZGRENZEN[name][1]} {wert:.1f} °C".replace(".", ",")
            for name, wert in werte.items()
        )
        paare = [(HEIZGRENZEN[name][0], f"{wert:.1f}") for name, wert in werte.items()]
        self.steller.vermerken(
            dt_util.now(), "einstellung", f"Heizgrenzen der Steuerung: {text}.", paare
        )
        self._geaendert = True
        self._speichern()
        if (auffrischen := getattr(self.coordinator, "async_request_refresh", None)) is not None:
            self.hass.async_create_task(auffrischen())
        async_dispatcher_send(self.hass, SIGNAL_AKTUALISIERT.format(self.device_id))

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
    def _grenzen_laden(self, z: dict[str, Any]) -> None:
        """Heizgrenzen sind Einstellungen; bis zum ersten Abruf gelten die zuletzt gelesenen."""
        self.grenze_zuletzt: float | None = _kommazahl(z.get("grenze_steuerung"))
        self.absenk_zuletzt: float | None = _kommazahl(z.get("grenze_absenk"))

    def _stufen_laden(self, z: dict[str, Any]) -> None:
        """Die gedämpfte AT mit ihrem Zeitpunkt und dem Beginn der laufenden Dämpfung."""
        stufen = z.get("stufen")
        self.stufen: tuple[float, float] | None = (
            (float(stufen[0]), float(stufen[1])) if isinstance(stufen, list | tuple) else None
        )
        self.stufen_zeit = ortszeit(z.get("stufen_zeit"))
        self.stufen_start = ortszeit(z.get("stufen_start"))

    def _heizgrenze(self) -> float | None:
        if (wert := self._wert("/3/21/0")) is not None:
            self.grenze_zuletzt = wert
        self.grenze_absenk()
        return self.grenze_zuletzt

    def grenze_absenk(self) -> float | None:
        """TA Absenkbetrieb (`3/2`); bis zum ersten Abruf nach dem Start die zuletzt gelesene."""
        if (wert := self._wert("/3/2/0")) is not None:
            self.absenk_zuletzt = wert
        return self.absenk_zuletzt

    def _ablauf_merken(self, jetzt: datetime) -> None:
        """Läuft eine eigene Absenkung ab, gilt bis zum Abruf der Raumsoll vor dem Eingriff."""
        g = self.gedaechtnis
        if (
            g.absenkung_bis is not None
            and g.absenkung_bis <= jetzt
            and g.absenkung_soll is not None
            and g.absenkung_basis is not None
            and self._soll_ersatz is None
        ):
            self._soll_ersatz = (g.absenkung_soll, g.absenkung_basis, jetzt)

    def _soll(self, jetzt: datetime) -> float | None:
        """Raumsoll `1/1`; direkt nach einer Rücknahme steht dort bis zum Abruf der geschriebene Wert."""
        soll = self._wert("/1/1/0")
        if self._soll_ersatz is None:
            return soll
        geschrieben, basis, seit = self._soll_ersatz
        if soll is not None and abs(soll - geschrieben) < 0.05 and jetzt - seit < SOLL_NACHLAUF:
            return basis
        self._soll_ersatz = None
        return soll

    def _wert(self, adresse: str) -> float | None:
        return get_oid_value(self.coordinator, adresse, self.prefix)

    def wert(self, adresse: str) -> float | None:
        """Ein Wert des Heizkreises, Adresse relativ zum Präfix."""
        return self._wert(adresse)

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
        self._tag_beginnen(dt_util.now().date().isoformat())
        eintrag = self.verlauf["stunden"].setdefault(str(stunde), {})
        for name, wert in werte.items():
            if wert is not None and eintrag.get(name) is None:
                eintrag[name] = wert

    def _aktion_merken(self, jetzt: datetime) -> None:
        """Was in dieser Stunde an der Steuerung gilt; spätere Stunden zeigen nur den Plan."""
        self._tag_beginnen(jetzt.date().isoformat())
        stunde = self.verlauf["stunden"].setdefault(str(jetzt.hour), {})
        stunde["aktion"] = tagesansicht.aktion(self.gedaechtnis, jetzt.hour, jetzt.date())

    def _steuerung_fehlt(self, jetzt: datetime) -> bool:
        """Ob Werte aus `ABRUF` seit dem Start noch nie gelesen wurden; gilt höchstens `STEUERUNG_WARTEN`."""
        oids = (self.coordinator.data or {}).get("oids") or {}
        fehlt = any(
            f"{self.prefix}{adresse}" not in oids for adresse in ABRUF if adresse != VORLAUF_IST
        )
        return fehlt and jetzt - self._gestartet < STEUERUNG_WARTEN

    def _lauf_aus_protokoll(self, jetzt: datetime) -> dict[str, eingaben.Lauf]:
        """Ohne gespeicherte Laufzeiten der heutige Stand aus den geschriebenen Eingriffen."""
        minuten = stundenmodus.minuten(
            self.steller.stand.protokoll, jetzt.date(), jetzt, nur_ww_wert(self.steller.angeboten)
        )
        heute = jetzt.date().isoformat()
        return {art: eingaben.Lauf(heute, minuten[art]) for art in MODUS_ARTEN}

    def _modus_fortschreiben(self, jetzt: datetime) -> None:
        """Laufzeiten der Modi; im Beobachten ging nichts an die Steuerung."""
        g = self.gedaechtnis
        absenkung = regel.absenkung_laeuft(g, jetzt)
        laeuft = {
            "absenkung": absenkung and g.absenkung_art != regel.PAUSE,
            "nur_ww": g.saison == regel.NUR_WW,
            "heizpause": absenkung and g.absenkung_art == regel.PAUSE,
        }
        self.modus_lauf = {
            art: eingaben.lauf_fortschreiben(lauf, jetzt, laeuft[art] and not self.beobachten)
            for art, lauf in self.modus_lauf.items()
        }

    @callback
    def _stundentakt(self, _jetzt: datetime) -> None:
        """Zur vollen Stunde vermerken, was gilt; eine ruhige Stunde bliebe sonst leer."""
        jetzt = dt_util.now()
        self._modus_fortschreiben(jetzt)
        self._aktion_merken(jetzt)
        self._speichern()
        async_dispatcher_send(self.hass, SIGNAL_SYSTEM.format(self.entry_id))

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
        self._tag_beginnen(jetzt.date().isoformat())
        stunde = self.verlauf["stunden"].setdefault(str(jetzt.hour), {})
        if "at" not in stunde:
            gedaempft = round(self.stufen[1], 2) if self.stufen else None
            stunde.update(at=at, raum=self._raum(), gedaempft=gedaempft, **self._stundenfelder())

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

    @property
    def name(self) -> str:
        """Name des Heizkreises wie in der Geräteliste."""
        return geraetename(self.hass, self.device_id, self.entry_id, self._rohname)

    def _stundenwerte(self, jetzt: datetime) -> list[tuple[datetime, float | None]]:
        """Korrigierte Stundenprognose von heute und morgen, mit Zeitpunkt."""
        werte = []
        for tag in (jetzt.date(), jetzt.date() + timedelta(days=1)):
            for stunde, prognose in self.stundenprognose(tag).items():
                zeit = datetime.combine(tag, time(stunde), jetzt.tzinfo)
                werte.append((zeit, prognose["korrigiert"]))
        return werte

    def _at_vorstunde(self, jetzt: datetime) -> float | None:
        if self.verlauf.get("datum") != jetzt.date().isoformat():
            return None
        stunde = (self.verlauf.get("stunden") or {}).get(str(max(jetzt.hour - 1, 0))) or {}
        return stunde.get("at")

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
        # Genug Räume: mindestens die Hälfte der eingerichteten liefert einen Wert.
        if 2 * len(messungen) >= len(self.konfig["raeume"]) and messungen:
            self._raeume_fehlen_seit = None
        elif self._raeume_fehlen_seit is None:
            self._raeume_fehlen_seit = jetzt
        untergang = self.sonne(jetzt.date())[1]
        lage = regel.Lage(
            jetzt=jetzt,
            at=at,
            at_gedaempft=self.stufen[1] if self.stufen else None,
            at_vor_einer_stunde=self._at_vorstunde(jetzt),
            soll=self._soll(jetzt),
            raeume=tuple((m.ist, m.ziel) for m in messungen if not m.aus),
            aus=tuple(m.ist for m in messungen if m.aus),
            raum_art=self.konfig["raum_art"],
            ruhig=self._ruhig(jetzt),
            sonnenquote=self.sonnenquote(jetzt.date(), self.konfig.get("pv")),
            mittel_heute=self.tagesmittel(jetzt.date()),
            mittel_morgen=self.tagesmittel(jetzt.date() + timedelta(days=1)),
            minimum_bis_morgen=eingaben.minimum_bis_morgen(self._stundenwerte(jetzt), jetzt),
            sonnenuntergang=untergang,
            betriebswahl=_ganzzahl(self._wert("/3/50/0")),
            betriebsart=_ganzzahl(self._wert("/2/9/0")),
            grenze_steuerung=self._heizgrenze(),
            daten_ok=daten_ok,
            daten_fehlen_seit=self._daten_fehlen_seit,
            raeume_fehlen_seit=self._raeume_fehlen_seit,
            fenster_offen=self._fenster(jetzt),
            abwesend=self._abwesend(jetzt),
            pausiert_bis=self.pausiert_bis,
            entscheidungszeit=entscheidungszeit,
            absenkung_moeglich=self._wert("/2/10/0") is not None,
            at_steuerung=self._wert("/0/0/0"),
            vl_soll=self._wert("/1/2/0"),
            beobachten=self.beobachten,
            **self._vorrang_lage(jetzt),
        )
        return replace(
            lage,
            vorhersage=self.vorhersage_fuer(jetzt, lage),
            modell_freigegeben=hausmodell.freigegeben(self.hausmodell),
        )
