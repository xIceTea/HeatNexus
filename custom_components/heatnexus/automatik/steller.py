"""Entscheidungen der Automatik als Schreibvorgänge an der Steuerung.

Kennt die Bauart des Heizkreises, das Tagesbudget und den Beobachtungsmodus.
Merkt sich, was die Automatik selbst gesetzt hat; nur das stellt sie zurück.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
import logging
from typing import Any

from .regel import NUR_WW, PROGRAMMWAHL, Aktion, Entscheidung, Gedaechtnis, absenkung_laeuft

_LOGGER = logging.getLogger(__name__)

OID_BETRIEBSWAHL = "/3/50/0"
OID_TEMPERATUR = "/3/4/0"
OID_DAUER = "/2/10/0"
WW_BETRIEB = 6
STANDBY = 0
PROGRAMM_1 = 1
# Betriebsarten (`2/9`), in denen die Anlage die Betriebswahl selbst umstellt.
WW_LADUNG = frozenset({3, 17, 18})
PROTOKOLL_MAX = 200
TOLERANZ_MIN = 5.0
# Der Abruf zeigt einen eigenen Schreibvorgang erst mit Verzug.
SCHONFRIST = timedelta(minutes=3)
# Nach einer Ablehnung wartet der Steller, mit jeder weiteren doppelt so lang.
SPERRE_START = timedelta(minutes=30)
SPERRE_MAX = timedelta(hours=6)
# Mehr heizen ist die sichere Richtung; das Budget begrenzt nur das Gegenteil.
RUECKKEHR = frozenset({"zurueck", "absenkung_ende"})

Schreiber = Callable[[str, str], Awaitable[None]]


def nur_ww_wert(angeboten: Iterable[int]) -> int:
    """„Nur Warmwasser" je Bauart: WW-Betrieb, wo es ihn gibt, sonst Standby."""
    return WW_BETRIEB if WW_BETRIEB in set(angeboten) else STANDBY


@dataclass(frozen=True)
class Stand:
    """Was der Steller über seine eigenen Eingriffe weiß; liegt im Store."""

    tag: str = ""
    eingriffe: int = 0
    betriebswahl_vorher: int | None = None
    erwartet: int | None = None
    zuletzt: str | None = None
    ablehnungen: int = 0
    gesperrt_bis: str | None = None
    protokoll: tuple[dict[str, Any], ...] = ()

    def als_dict(self) -> dict[str, Any]:
        daten = asdict(self)
        daten["protokoll"] = list(self.protokoll)
        return daten

    @classmethod
    def aus_dict(cls, roh: Any) -> Stand:
        """Aus dem Store; Unlesbares ergibt einen leeren Stand."""
        if not isinstance(roh, Mapping):
            return cls()
        try:
            return cls(
                tag=str(roh.get("tag") or ""),
                eingriffe=int(roh.get("eingriffe") or 0),
                betriebswahl_vorher=_ganzzahl(roh.get("betriebswahl_vorher")),
                erwartet=_ganzzahl(roh.get("erwartet")),
                zuletzt=_zeitpunkt(roh.get("zuletzt")),
                ablehnungen=int(roh.get("ablehnungen") or 0),
                gesperrt_bis=_zeitpunkt(roh.get("gesperrt_bis")),
                protokoll=tuple(e for e in roh.get("protokoll") or () if isinstance(e, dict))[
                    :PROTOKOLL_MAX
                ],
            )
        except (TypeError, ValueError):
            return cls()


def _ganzzahl(wert: Any) -> int | None:
    return None if wert is None else int(wert)


def _zeitpunkt(wert: Any) -> str | None:
    # Ein unlesbarer Zeitpunkt ließe später jeden Lauf scheitern.
    try:
        return datetime.fromisoformat(wert).isoformat() if wert else None
    except (TypeError, ValueError):
        return None


class Steller:
    """Schreibt Entscheidungen eines Heizkreises an die Steuerung."""

    def __init__(
        self,
        prefix: str,
        angeboten: Iterable[int],
        schreiben: Schreiber,
        stand: Stand | None = None,
    ) -> None:
        self._prefix = prefix
        self._angeboten = tuple(angeboten)
        self._schreiben = schreiben
        self.stand = stand or Stand()

    @property
    def angeboten(self) -> tuple[int, ...]:
        """Die Betriebswahlen, die der Heizkreis anbietet."""
        return self._angeboten

    def vermerken(
        self, jetzt: datetime, art: str, text: str, werte: Iterable[tuple[str, str]] = ()
    ) -> None:
        """Einen Eintrag vorne ins Protokoll legen."""
        eintrag = {
            "zeit": jetzt.isoformat(),
            "art": art,
            "text": text,
            "werte": [[oid, wert] for oid, wert in werte],
        }
        protokoll = (eintrag, *self.stand.protokoll)[:PROTOKOLL_MAX]
        self.stand = replace(self.stand, protokoll=protokoll)

    def schreibvorgaenge(self, aktion: Aktion) -> list[tuple[str, str]]:
        """Adressen und Werte einer Aktion, relativ zum Heizkreis."""
        if aktion.art == "nur_ww":
            return [(OID_BETRIEBSWAHL, str(nur_ww_wert(self._angeboten)))]
        if aktion.art == "zurueck":
            vorher = self.stand.betriebswahl_vorher
            return [(OID_BETRIEBSWAHL, str(PROGRAMM_1 if vorher is None else vorher))]
        if aktion.art == "absenken":
            return [(OID_TEMPERATUR, f"{aktion.soll:.1f}"), (OID_DAUER, str(aktion.minuten))]
        if aktion.art == "absenkung_ende":
            return [(OID_DAUER, "0")]
        raise ValueError(f"Unbekannte Aktion: {aktion.art}")

    async def ausfuehren(
        self,
        entscheidung: Entscheidung,
        *,
        jetzt: datetime,
        betriebswahl: int | None,
        budget: int,
        beobachten: bool,
        erzwingen: bool = False,
    ) -> bool:
        """Schreibt die Aktionen; `True`, wenn alles angenommen oder nur beobachtet wurde."""
        self._tag_wechseln(jetzt)
        if not entscheidung.aktionen:
            return True
        paare = [p for aktion in entscheidung.aktionen for p in self.schreibvorgaenge(aktion)]
        if beobachten:
            self.vermerken(jetzt, "haette", entscheidung.begruendung, paare)
            return True
        if not erzwingen and self._gesperrt(jetzt):
            return False
        zaehlt = any(
            aktion.art not in RUECKKEHR and not aktion.sicherheit
            for aktion in entscheidung.aktionen
        )
        if zaehlt and self.stand.eingriffe >= budget:
            self._budget_vermerken(jetzt, budget, paare)
            return False
        try:
            for oid, wert in paare:
                await self._schreiben(f"{self._prefix}{oid}", wert)
        except Exception as fehler:  # jede Ablehnung gehört ins Protokoll
            self._abgelehnt(jetzt, fehler, paare)
            return False
        self.stand = replace(self.stand, ablehnungen=0, gesperrt_bis=None)
        self._merken(entscheidung.aktionen, betriebswahl, jetzt, zaehlt)
        self.vermerken(jetzt, "geschrieben", entscheidung.begruendung, paare)
        return True

    def _gesperrt(self, jetzt: datetime) -> bool:
        bis = self.stand.gesperrt_bis
        return bis is not None and jetzt < datetime.fromisoformat(bis)

    def _budget_vermerken(self, jetzt: datetime, budget: int, paare: list[tuple[str, str]]) -> None:
        letzter = self.stand.protokoll[0] if self.stand.protokoll else {}
        if letzter.get("art") == "budget" and letzter.get("zeit", "")[:10] == self.stand.tag:
            return
        text = f"Tagesbudget von {budget} Eingriffen erreicht – nicht geschrieben."
        self.vermerken(jetzt, "budget", text, paare)

    def _abgelehnt(self, jetzt: datetime, fehler: Exception, paare: list[tuple[str, str]]) -> None:
        anzahl = self.stand.ablehnungen + 1
        sperre = min(SPERRE_START * 2 ** (anzahl - 1), SPERRE_MAX)
        bis = jetzt + sperre
        self.stand = replace(self.stand, ablehnungen=anzahl, gesperrt_bis=bis.isoformat())
        _LOGGER.warning("Automatik %s: Eingriff abgelehnt: %s", self._prefix, fehler)
        text = (
            f"Die Steuerung hat den Eingriff abgelehnt: {fehler}. Nächster Versuch ab {bis:%H:%M}."
        )
        self.vermerken(jetzt, "abgelehnt", text, paare)

    def handeingriff(
        self,
        g: Gedaechtnis,
        *,
        jetzt: datetime,
        betriebswahl: int | None,
        rest_min: float | None,
        betriebsart: int | None,
    ) -> str | None:
        """Beschreibt einen Eingriff von Hand gegen eine laufende eigene Aktion."""
        if betriebsart is not None and betriebsart in WW_LADUNG:
            return None
        if self.stand.zuletzt and jetzt - datetime.fromisoformat(self.stand.zuletzt) < SCHONFRIST:
            return None
        erwartet = self.stand.erwartet
        if erwartet is not None and betriebswahl is not None and betriebswahl != erwartet:
            return f"Betriebswahl von Hand auf {betriebswahl} gestellt."
        if absenkung_laeuft(g, jetzt) and rest_min is not None:
            soll_rest = (g.absenkung_bis - jetzt).total_seconds() / 60
            if rest_min <= 0 and soll_rest > TOLERANZ_MIN:
                return "Absenkung von Hand beendet."
            if rest_min > soll_rest + TOLERANZ_MIN:
                return "Absenkung von Hand geändert."
        return None

    def abgleichen(self, g: Gedaechtnis, jetzt: datetime) -> None:
        """Ohne eigenen Eingriff gibt es nichts zu überwachen."""
        if g.saison != NUR_WW and not absenkung_laeuft(g, jetzt):
            self.freigeben()

    def freigeben(self) -> None:
        """Erwartung und gemerkte Betriebswahl vergessen."""
        self.stand = replace(self.stand, erwartet=None, betriebswahl_vorher=None)

    def _tag_wechseln(self, jetzt: datetime) -> None:
        tag = jetzt.date().isoformat()
        if tag != self.stand.tag:
            self.stand = replace(self.stand, tag=tag, eingriffe=0)

    def _merken(
        self,
        aktionen: tuple[Aktion, ...],
        betriebswahl: int | None,
        jetzt: datetime,
        zaehlt: bool,
    ) -> None:
        eingriffe = self.stand.eingriffe + (1 if zaehlt else 0)
        stand = replace(self.stand, eingriffe=eingriffe, zuletzt=jetzt.isoformat())
        for aktion in aktionen:
            if aktion.art == "nur_ww":
                vorher = betriebswahl if betriebswahl in PROGRAMMWAHL else stand.betriebswahl_vorher
                stand = replace(
                    stand, betriebswahl_vorher=vorher, erwartet=nur_ww_wert(self._angeboten)
                )
            elif aktion.art == "zurueck":
                stand = replace(stand, betriebswahl_vorher=None, erwartet=None)
            elif aktion.art == "absenken" and stand.erwartet is None:
                stand = replace(stand, erwartet=betriebswahl)
        self.stand = stand
