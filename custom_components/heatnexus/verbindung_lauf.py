"""Verbindung einer Steuerung: Stand nach jedem Abruf, Stundenspeicher, Reparatureintrag."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import logging
from statistics import median
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store

from . import verbindung as vb
from .client.antwortzeit import Messreihe
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
SPEICHERN_NACH_S = 60
DAUER_MELDUNG_S = 1800


def store_key(entry_id: str, host: str) -> str:
    """Speicherschlüssel der Stundenwerte einer Steuerung."""
    return f"{DOMAIN}_antwortzeit_{entry_id}_{host.replace('.', '_')}"


def issue_key(entry_id: str, host: str) -> str:
    """Kennung des Reparatureintrags einer Steuerung."""
    return f"verbindung_{entry_id}_{host}"


def stunde_jetzt() -> str:
    """Stundenschlüssel in UTC; die Zeitumstellung belegt so keine Stunde doppelt."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H")


def _stunde_lesen(roh: Any, jetzt: str) -> vb.Stunde | None:
    """Eine gespeicherte Stunde; `None` für alles, was nicht dazu passt."""
    try:
        schluessel, median_ms, antworten, gueltig = roh
        antworten = int(antworten)
    except (TypeError, ValueError):
        return None
    if not isinstance(schluessel, str) or schluessel > jetzt:
        return None
    if median_ms is not None and (
        isinstance(median_ms, bool) or not isinstance(median_ms, int | float)
    ):
        return None
    return vb.Stunde(schluessel, median_ms, antworten, bool(gueltig))


def _stunden_lesen(daten: dict[str, Any], jetzt: str) -> list[vb.Stunde]:
    stunden = [_stunde_lesen(roh, jetzt) for roh in daten.get("stunden") or []]
    return [s for s in stunden if s is not None][-vb.BEZUG_STUNDEN :]


def _vorlaeufig_lesen(daten: dict[str, Any]) -> float | None:
    """Der gespeicherte vorläufige Bezug; alles außer einer positiven Zahl gilt als keiner."""
    wert = daten.get("vorlaeufig")
    if isinstance(wert, bool) or not isinstance(wert, int | float) or wert <= 0:
        return None
    return float(wert)


class VerbindungLauf:
    """Hält Fenster, Zustand und Bezug einer Steuerung und meldet anhaltende Probleme."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        host: str,
        label: str,
        store: Store,
        stunden: list[vb.Stunde],
        stunde: Callable[[], str] = stunde_jetzt,
        vorlaeufig: float | None = None,
    ) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._host = host
        self._label = label
        self._store = store
        self._stunden = stunden
        self._stunde = stunde
        self._laufende = stunde()
        self._bewertungen: list[str] = []
        # Dauer des Problems über gelungene Abrufe und die Zeit der letzten Bewertung darin.
        self._problem_s = 0.0
        self._problem_zuletzt: float | None = None
        self._gemeldet: str | None = None
        self._beendet = False
        self._zuhoerer: set[Callable[[], None]] = set()
        self.stand = vb.Stand()
        self.fenster = vb.Fenster(None, 0, 0)
        self.bezug_ms = vb.bezug(stunden)
        self.abrufe_mit_rest = 0
        self.noch_offen = 0
        self._letzter_median: float | None = None
        # Median des letzten Abrufs für die Anzeige; die Bewertung nimmt das ruhigere Fenster.
        self.abruf_ms: float | None = None
        # Bis der Bezug aus den Stunden steht, gilt der Median der ersten ruhigen Viertelstunde.
        self._start: float | None = None
        self._vorlaeufig = vorlaeufig
        # Ein Eintrag aus einem früheren Lauf gehört zu keinem Zustand mehr.
        ir.async_delete_issue(hass, DOMAIN, issue_key(entry_id, host))

    @classmethod
    async def laden(
        cls, hass: HomeAssistant, entry_id: str, host: str, label: str
    ) -> VerbindungLauf:
        store: Store = Store(hass, STORE_VERSION, store_key(entry_id, host))
        try:
            daten = await store.async_load() or {}
            stunden = _stunden_lesen(daten, stunde_jetzt())
            vorlaeufig = _vorlaeufig_lesen(daten)
        except Exception as err:
            _LOGGER.warning("Gespeicherte Antwortzeiten von %s nicht lesbar: %s", host, err)
            stunden, vorlaeufig = [], None
        return cls(hass, entry_id, host, label, store, stunden, vorlaeufig=vorlaeufig)

    def nach_abruf(self, messreihe: Messreihe, noch_offen: int, erfolgreich: bool = True) -> None:
        """Nach jedem Abruf: Stunde prüfen, Fenster bilden, Zustand fortschreiben, melden."""
        if self._beendet:
            return
        jetzt = messreihe.jetzt()
        self._stunde_pruefen(messreihe)
        dauern = messreihe.abruf_abholen()
        self.abruf_ms = median(dauern) if dauern else None
        # Ein gescheiterter Abruf sagt nichts über liegengebliebene Werte; die Folge bleibt stehen.
        if erfolgreich:
            self.noch_offen = noch_offen
            self.abrufe_mit_rest = self.abrufe_mit_rest + 1 if noch_offen else 0
        self.fenster = vb.fenster(messreihe.eintraege(), jetzt)
        if self.fenster.median_ms is not None:
            self._letzter_median = self.fenster.median_ms
        self._vorlaeufig_pruefen(jetzt)
        ergebnis = vb.regel(self.fenster, self.wirksamer_bezug, self.abrufe_mit_rest)
        self.stand = vb.fortschreiben(self.stand, ergebnis)
        self._bewertungen.append(self.stand.zustand)
        self._melden(jetzt, erfolgreich)
        for rueckruf in tuple(self._zuhoerer):
            rueckruf()

    def _vorlaeufig_pruefen(self, jetzt: float) -> None:
        if self._start is None:
            self._start = jetzt
        if self.bezug_ms is None and self._vorlaeufig is None:
            self._vorlaeufig = vb.vorlaeufiger_bezug(
                self.fenster, jetzt - self._start, self.abrufe_mit_rest
            )
            if self._vorlaeufig is not None:
                self._store.async_delay_save(self._daten, SPEICHERN_NACH_S)

    @property
    def wirksamer_bezug(self) -> float | None:
        """Der Bezug aus den Stunden, bis dahin der vorläufige."""
        return self.bezug_ms if self.bezug_ms is not None else self._vorlaeufig

    def abonnieren(self, rueckruf: Callable[[], None]) -> Callable[[], None]:
        """`rueckruf` folgt jeder Bewertung, auch wenn sich die Werte der Anlage nicht ändern."""
        self._zuhoerer.add(rueckruf)
        return lambda: self._zuhoerer.discard(rueckruf)

    def _stunde_pruefen(self, messreihe: Messreihe) -> None:
        aktuell = self._stunde()
        if aktuell == self._laufende:
            return
        fertig = vb.stunde_abschliessen(
            self._laufende, messreihe.stunde_abholen(), self._bewertungen
        )
        self._stunden = vb.stunden_kuerzen(self._stunden, fertig)
        self.bezug_ms = vb.bezug(self._stunden)
        self._bewertungen = []
        self._laufende = aktuell
        self._store.async_delay_save(self._daten, SPEICHERN_NACH_S)

    def _daten(self) -> dict[str, Any]:
        return {
            "stunden": [[s.schluessel, s.median_ms, s.antworten, s.gueltig] for s in self._stunden],
            "vorlaeufig": self._vorlaeufig,
        }

    def _melden(self, jetzt: float, erfolgreich: bool) -> None:
        """Melden nach `DAUER_MELDUNG_S` im Problem; ein Wechsel ersetzt den Eintrag sofort.

        Einen gescheiterten Abruf meldet der Koordinator; er legt hier nichts an und zählt nicht mit.
        """
        zustand = self.stand.zustand
        if zustand not in vb.MELDEN:
            self._problem_s, self._problem_zuletzt = 0.0, None
            if self._gemeldet:
                self._zuruecknehmen()
            return
        if erfolgreich and self._problem_zuletzt is not None:
            self._problem_s += jetzt - self._problem_zuletzt
        self._problem_zuletzt = jetzt
        if not erfolgreich or self._gemeldet == zustand:
            return
        if self._gemeldet is None and self._problem_s < DAUER_MELDUNG_S:
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_key(self._entry_id, self._host),
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"verbindung_{zustand}",
            translation_placeholders=self._platzhalter(),
        )
        self._gemeldet = zustand

    def _platzhalter(self) -> dict[str, str]:
        median_ms = self.fenster.median_ms
        if median_ms is None:
            median_ms = self._letzter_median
        return {
            "anlage": self._label or self._host,
            "median": "–" if median_ms is None else str(round(median_ms)),
            "fehlerquote": str(round(self.fenster.fehlerquote * 100)),
        }

    def attribute(self) -> dict[str, Any]:
        """Kennzahlen für die Entität und die Diagnose."""
        bezug = self.wirksamer_bezug
        return {
            "bezug_ms": None if bezug is None else round(bezug),
            "bezug_vorlaeufig": self.bezug_ms is None and bezug is not None,
            "abruf_ms": None if self.abruf_ms is None else round(self.abruf_ms),
            "median_ms": None if self.fenster.median_ms is None else round(self.fenster.median_ms),
            "fehlerquote": round(self.fenster.fehlerquote * 100, 1),
            "antworten": self.fenster.antworten,
            "noch_offen": self.noch_offen,
            "abrufe_mit_rest": self.abrufe_mit_rest,
            "gueltige_stunden": sum(1 for s in self._stunden if s.gueltig),
        }

    def diagnose(self) -> dict[str, Any]:
        return {"zustand": self.stand.zustand, **self.attribute(), **self._daten()}

    def _zuruecknehmen(self) -> None:
        ir.async_delete_issue(self.hass, DOMAIN, issue_key(self._entry_id, self._host))
        self._gemeldet = None

    async def async_entladen(self) -> None:
        """Bewertung beenden, Eintrag zurücknehmen und die Stunden sofort speichern."""
        self._beendet = True
        self._zuruecknehmen()
        await self._store.async_save(self._daten())
