"""Verbindung einer Steuerung: Stand nach jedem Abruf, Stundenspeicher, Reparatureintrag."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import logging
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
        self._problem_seit: float | None = None
        self._gemeldet: str | None = None
        self._beendet = False
        self._zuhoerer: set[Callable[[], None]] = set()
        self.stand = vb.Stand()
        self.fenster = vb.Fenster(None, 0, 0)
        self.bezug_ms = vb.bezug(stunden)
        self.abrufe_mit_rest = 0
        self.noch_offen = 0
        # Ein Eintrag aus einem früheren Lauf gehört zu keinem Zustand mehr.
        ir.async_delete_issue(hass, DOMAIN, issue_key(entry_id, host))

    @classmethod
    async def laden(
        cls, hass: HomeAssistant, entry_id: str, host: str, label: str
    ) -> VerbindungLauf:
        store: Store = Store(hass, STORE_VERSION, store_key(entry_id, host))
        try:
            daten = await store.async_load() or {}
        except Exception as err:
            _LOGGER.warning("Gespeicherte Antwortzeiten von %s nicht lesbar: %s", host, err)
            daten = {}
        return cls(hass, entry_id, host, label, store, _stunden_lesen(daten, stunde_jetzt()))

    def nach_abruf(self, messreihe: Messreihe, noch_offen: int) -> None:
        """Nach jedem Abruf: Stunde prüfen, Fenster bilden, Zustand fortschreiben, melden."""
        if self._beendet:
            return
        jetzt = messreihe.jetzt()
        self._stunde_pruefen(messreihe)
        self.noch_offen = noch_offen
        self.abrufe_mit_rest = self.abrufe_mit_rest + 1 if noch_offen else 0
        self.fenster = vb.fenster(messreihe.eintraege(), jetzt)
        ergebnis = vb.regel(self.fenster, self.bezug_ms, self.abrufe_mit_rest)
        self.stand = vb.fortschreiben(self.stand, ergebnis)
        self._bewertungen.append(self.stand.zustand)
        self._melden(jetzt)
        for rueckruf in tuple(self._zuhoerer):
            rueckruf()

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
            "stunden": [[s.schluessel, s.median_ms, s.antworten, s.gueltig] for s in self._stunden]
        }

    def _melden(self, jetzt: float) -> None:
        """Melden nach `DAUER_MELDUNG_S` im Problem; ein Wechsel ersetzt den Eintrag sofort."""
        zustand = self.stand.zustand
        if zustand not in vb.MELDEN:
            self._problem_seit = None
            if self._gemeldet:
                self._zuruecknehmen()
            return
        if self._problem_seit is None:
            self._problem_seit = jetzt
        if self._gemeldet == zustand:
            return
        if self._gemeldet is None and jetzt - self._problem_seit < DAUER_MELDUNG_S:
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
        return {
            "anlage": self._label or self._host,
            "median": "–" if median_ms is None else str(round(median_ms)),
            "fehlerquote": str(round(self.fenster.fehlerquote * 100)),
        }

    def attribute(self) -> dict[str, Any]:
        """Kennzahlen für die Entität und die Diagnose."""
        return {
            "bezug_ms": None if self.bezug_ms is None else round(self.bezug_ms),
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
