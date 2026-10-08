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
RAUMSOLL_TOLERANZ = 0.3
# Der Abruf zeigt einen eigenen Schreibvorgang erst mit Verzug.
SCHONFRIST = timedelta(minutes=3)
# Nach einer Ablehnung wartet der Steller, mit jeder weiteren doppelt so lang.
SPERRE_START = timedelta(minutes=30)
SPERRE_MAX = timedelta(hours=6)
# Eine abgelehnte Sicherheitsaktion versucht es nach dieser festen Frist wieder, ohne Verdopplung.
SPERRE_SICHERHEIT = timedelta(minutes=15)
# Mehr heizen ist die sichere Richtung; das Budget begrenzt nur das Gegenteil.
RUECKKEHR = frozenset({"zurueck", "absenkung_ende"})
# Diese Eingriffe heizen weniger; im Modus „empfehlen" warten sie auf eine Bestätigung.
BESTAETIGEN = frozenset({"nur_ww", "absenken", "pause"})

Schreiber = Callable[[str, str], Awaitable[None]]


def braucht_bestaetigung(aktionen: Iterable[Aktion]) -> bool:
    """Ob eine Entscheidung einen bestätigungspflichtigen Eingriff enthält und keinen der Sicherheit.

    Auch Verlängern und Erneuern warten; ohne Zustimmung endet der Eingriff an der Steuerung von selbst.
    """
    liste = list(aktionen)
    if any(aktion.sicherheit for aktion in liste):
        return False
    return any(aktion.art in BESTAETIGEN for aktion in liste)


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


def _absenkung_von_hand(
    g: Gedaechtnis, jetzt: datetime, rest_min: float | None, raumsoll: float | None
) -> str | None:
    if rest_min is not None:
        soll_rest = (g.absenkung_bis - jetzt).total_seconds() / 60
        if rest_min <= 0 and soll_rest > TOLERANZ_MIN:
            return "Absenkung von Hand beendet."
        if rest_min > soll_rest + TOLERANZ_MIN:
            return "Absenkung von Hand geändert."
    # Während der eigenen Absenkung zeigt `1/1` den geschriebenen Raumsoll.
    if (
        raumsoll is not None
        and g.absenkung_soll is not None
        and abs(raumsoll - g.absenkung_soll) > RAUMSOLL_TOLERANZ
    ):
        return "Absenkung von Hand geändert."
    return None


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
        # Die Aktionen des letzten Schreibversuchs, die vollständig angenommen wurden.
        self.erledigt: tuple[Aktion, ...] = ()
        # Ob der letzte Lauf eine Empfehlung statt eines Schreibvorgangs ergab.
        self.empfohlen = False

    @property
    def angeboten(self) -> tuple[int, ...]:
        """Die Betriebswahlen, die der Heizkreis anbietet."""
        return self._angeboten

    def vermerken(
        self,
        jetzt: datetime,
        art: str,
        text: str,
        werte: Iterable[tuple[str, str]] = (),
        aktionen: Iterable[Aktion] = (),
    ) -> None:
        """Einen Eintrag vorne ins Protokoll legen."""
        eintrag = {
            "zeit": jetzt.isoformat(),
            "art": art,
            "text": text,
            "werte": [[oid, wert] for oid, wert in werte],
        }
        if arten := [aktion.art for aktion in aktionen]:
            eintrag["aktionen"] = arten
        protokoll = (eintrag, *self.stand.protokoll)[:PROTOKOLL_MAX]
        self.stand = replace(self.stand, protokoll=protokoll)

    def schreibvorgaenge(self, aktion: Aktion) -> list[tuple[str, str]]:
        """Adressen und Werte einer Aktion, relativ zum Heizkreis."""
        if aktion.art == "nur_ww":
            return [(OID_BETRIEBSWAHL, str(nur_ww_wert(self._angeboten)))]
        if aktion.art == "zurueck":
            vorher = self.stand.betriebswahl_vorher
            return [(OID_BETRIEBSWAHL, str(PROGRAMM_1 if vorher is None else vorher))]
        if aktion.art in ("absenken", "pause"):
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
        empfehlen: bool = False,
    ) -> bool:
        """Schreibt die Aktionen; `True`, wenn alles angenommen oder nur beobachtet wurde."""
        self.erledigt = ()
        self.empfohlen = False
        self._tag_wechseln(jetzt)
        if not entscheidung.aktionen:
            return True
        paare = [p for aktion in entscheidung.aktionen for p in self.schreibvorgaenge(aktion)]
        if beobachten:
            self.vermerken(jetzt, "haette", entscheidung.begruendung, paare, entscheidung.aktionen)
            return True
        if empfehlen and braucht_bestaetigung(entscheidung.aktionen):
            self.empfohlen = True
            self._empfehlung_vermerken(jetzt, entscheidung, paare)
            return False
        sicherheit = any(aktion.sicherheit for aktion in entscheidung.aktionen)
        if not erzwingen and self._gesperrt(jetzt, sicherheit):
            return False
        zaehlt = any(
            aktion.art not in RUECKKEHR and not aktion.sicherheit and not aktion.erneuern
            for aktion in entscheidung.aktionen
        )
        if zaehlt and self.stand.eingriffe >= budget:
            self._budget_vermerken(jetzt, budget, paare)
            return False
        try:
            for aktion in entscheidung.aktionen:
                for oid, wert in self.schreibvorgaenge(aktion):
                    await self._schreiben(f"{self._prefix}{oid}", wert)
                self.erledigt = (*self.erledigt, aktion)
        except Exception as fehler:  # jede Ablehnung gehört ins Protokoll
            # Was schon angenommen ist, gilt; sonst sähe es beim nächsten Lauf nach einem Handeingriff aus.
            if self.erledigt:
                self._merken(self.erledigt, betriebswahl, jetzt, False)
            self._abgelehnt(jetzt, fehler, paare, sicherheit)
            return False
        self.stand = replace(self.stand, ablehnungen=0, gesperrt_bis=None)
        self._merken(entscheidung.aktionen, betriebswahl, jetzt, zaehlt)
        self.vermerken(jetzt, "geschrieben", entscheidung.begruendung, paare, entscheidung.aktionen)
        return True

    def _gesperrt(self, jetzt: datetime, sicherheit: bool = False) -> bool:
        """Nach einer Ablehnung gesperrt; eine Sicherheitsaktion nur nach ihrer eigenen, und kurz."""
        if not sicherheit:
            bis = self.stand.gesperrt_bis
            return bis is not None and jetzt < datetime.fromisoformat(bis)
        letzte = next((e for e in self.stand.protokoll if e.get("art") == "abgelehnt"), None)
        if not letzte or not letzte.get("sicherheit"):
            return False
        return jetzt < datetime.fromisoformat(letzte["zeit"]) + SPERRE_SICHERHEIT

    def _budget_vermerken(self, jetzt: datetime, budget: int, paare: list[tuple[str, str]]) -> None:
        letzter = self.stand.protokoll[0] if self.stand.protokoll else {}
        if letzter.get("art") == "budget" and letzter.get("zeit", "")[:10] == self.stand.tag:
            return
        text = f"Tagesbudget von {budget} Eingriffen erreicht – nicht geschrieben."
        self.vermerken(jetzt, "budget", text, paare)

    def _empfehlung_vermerken(
        self, jetzt: datetime, entscheidung: Entscheidung, paare: list[tuple[str, str]]
    ) -> None:
        letzter = self.stand.protokoll[0] if self.stand.protokoll else {}
        werte = [[oid, wert] for oid, wert in paare]
        if letzter.get("art") == "empfohlen" and letzter.get("werte") == werte:
            return
        self.vermerken(jetzt, "empfohlen", entscheidung.begruendung, paare, entscheidung.aktionen)

    def _abgelehnt(
        self, jetzt: datetime, fehler: Exception, paare: list[tuple[str, str]], sicherheit: bool
    ) -> None:
        anzahl = self.stand.ablehnungen + 1
        sperre = (
            SPERRE_SICHERHEIT if sicherheit else min(SPERRE_START * 2 ** (anzahl - 1), SPERRE_MAX)
        )
        bis = jetzt + sperre
        self.stand = replace(self.stand, ablehnungen=anzahl, gesperrt_bis=bis.isoformat())
        text = (
            f"Die Steuerung hat den Eingriff abgelehnt: {fehler}. Nächster Versuch ab {bis:%H:%M}."
        )
        werte = [[oid, wert] for oid, wert in paare]
        letzter = self.stand.protokoll[0] if self.stand.protokoll else {}
        # Dieselbe Ablehnung noch einmal: Eintrag auffrischen statt das Protokoll zu füllen.
        if letzter.get("art") == "abgelehnt" and letzter.get("werte") == werte:
            _LOGGER.debug("Automatik %s: Eingriff erneut abgelehnt: %s", self._prefix, fehler)
            neu = {**letzter, "zeit": jetzt.isoformat(), "text": text, "sicherheit": sicherheit}
            self.stand = replace(self.stand, protokoll=(neu, *self.stand.protokoll[1:]))
            return
        _LOGGER.warning("Automatik %s: Eingriff abgelehnt: %s", self._prefix, fehler)
        self.vermerken(jetzt, "abgelehnt", text, paare)
        self.stand = replace(
            self.stand,
            protokoll=(
                {**self.stand.protokoll[0], "sicherheit": sicherheit},
                *self.stand.protokoll[1:],
            ),
        )

    def handeingriff(
        self,
        g: Gedaechtnis,
        *,
        jetzt: datetime,
        betriebswahl: int | None,
        rest_min: float | None,
        betriebsart: int | None,
        raumsoll: float | None = None,
    ) -> str | None:
        """Beschreibt einen Eingriff von Hand gegen eine laufende eigene Aktion."""
        if betriebsart is not None and betriebsart in WW_LADUNG:
            return None
        if self.stand.zuletzt and jetzt - datetime.fromisoformat(self.stand.zuletzt) < SCHONFRIST:
            return None
        erwartet = self.stand.erwartet
        if erwartet is not None and betriebswahl is not None and betriebswahl != erwartet:
            return f"Betriebswahl von Hand auf {betriebswahl} gestellt."
        if absenkung_laeuft(g, jetzt):
            return _absenkung_von_hand(g, jetzt, rest_min, raumsoll)
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
        # Die Betriebswahl, die nach der jeweils letzten Aktion an der Steuerung steht.
        wirksam = betriebswahl
        for aktion in aktionen:
            if aktion.art == "nur_ww":
                vorher = betriebswahl if betriebswahl in PROGRAMMWAHL else stand.betriebswahl_vorher
                wirksam = nur_ww_wert(self._angeboten)
                stand = replace(stand, betriebswahl_vorher=vorher, erwartet=wirksam)
            elif aktion.art == "zurueck":
                wirksam = int(self.schreibvorgaenge(aktion)[0][1])
                stand = replace(stand, betriebswahl_vorher=None, erwartet=None)
            elif aktion.art in ("absenken", "pause") and stand.erwartet is None:
                stand = replace(stand, erwartet=wirksam)
        self.stand = stand
