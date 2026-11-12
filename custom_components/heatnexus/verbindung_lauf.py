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


def _stunden_lesen(daten: dict[str, Any], jetzt: str) -> list[vb.Stunde]:
    stunden = []
    for roh in daten.get("stunden") or []:
        try:
            schluessel, median_ms, antworten, gueltig = roh
        except (TypeError, ValueError):
            continue
        if not isinstance(schluessel, str) or schluessel > jetzt:
            continue
        stunden.append(vb.Stunde(schluessel, median_ms, int(antworten), bool(gueltig)))
    return stunden[-vb.BEZUG_STUNDEN :]


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
        self._seit: float | None = None
        self._gemeldet: str | None = None
        self.stand = vb.Stand()
        self.fenster = vb.Fenster(None, 0, 0)
        self.bezug_ms = vb.bezug(stunden)
        self.abrufe_mit_rest = 0
        self.noch_offen = 0

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
        jetzt = messreihe.jetzt()
        self._stunde_pruefen(messreihe)
        self.noch_offen = noch_offen
        self.abrufe_mit_rest = self.abrufe_mit_rest + 1 if noch_offen else 0
        self.fenster = vb.fenster(messreihe.eintraege(), jetzt)
        alt = self.stand.zustand
        ergebnis = vb.regel(self.fenster, self.bezug_ms, self.abrufe_mit_rest)
        self.stand = vb.fortschreiben(self.stand, ergebnis)
        if self._seit is None or self.stand.zustand != alt:
            self._seit = jetzt
        self._bewertungen.append(self.stand.zustand)
        self._melden(jetzt)

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
        zustand = self.stand.zustand
        if zustand not in vb.MELDEN:
            if self._gemeldet:
                self.entladen()
            return
        if self._gemeldet == zustand or jetzt - (self._seit or jetzt) < DAUER_MELDUNG_S:
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
        def ms(wert: float | None) -> str:
            return "–" if wert is None else str(round(wert))

        return {
            "anlage": self._label or self._host,
            "median": ms(self.fenster.median_ms),
            "bezug": ms(self.bezug_ms),
            "fehlerquote": f"{self.fenster.fehlerquote * 100:.1f}",
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

    def entladen(self) -> None:
        """Reparatureintrag zurücknehmen."""
        ir.async_delete_issue(self.hass, DOMAIN, issue_key(self._entry_id, self._host))
        self._gemeldet = None
