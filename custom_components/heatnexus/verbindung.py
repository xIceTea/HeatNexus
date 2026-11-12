"""Bewertung der Antwortzeiten einer Steuerung: Fenster, Zustand, Stunden und Bezug.

Ohne Home Assistant: Der Lauf in `verbindung_lauf.py` liefert Messwerte und hält den Stand.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from statistics import median

FENSTER_S = 900
MIN_ANFRAGEN = 20
MIN_ANTWORTEN = 20
GRENZE_FEHLER = 0.20
GRENZE_LIEGEN = 5
FAKTOR_TRAEGE = 1.5
# Ohne festen Abstand wäre bei einer schnellen Steuerung schon Rauschen „träge“.
ABSTAND_TRAEGE_MS = 150.0
BESTAETIGUNG = 3
MIN_STUNDE = 60
BEZUG_STUNDEN = 168
MIN_STUNDEN_BEZUG = 24

STABIL = "stabil"
TRAEGE = "traege"
UEBERLASTET = "ueberlastet"
GESTOERT = "gestoert"
SAMMELT = "sammelt"
ZUSTAENDE = (STABIL, TRAEGE, UEBERLASTET, GESTOERT, SAMMELT)
MELDEN = frozenset({UEBERLASTET, GESTOERT})
GUT = frozenset({STABIL, SAMMELT})


@dataclass(frozen=True)
class Fenster:
    """Antworten und Fehlantworten der letzten Viertelstunde."""

    median_ms: float | None
    antworten: int
    fehler: int

    @property
    def anfragen(self) -> int:
        return self.antworten + self.fehler

    @property
    def fehlerquote(self) -> float:
        return self.fehler / self.anfragen if self.anfragen else 0.0


@dataclass(frozen=True)
class Stand:
    """Geltender Zustand und der Kandidat, der ihn ablösen will."""

    zustand: str = SAMMELT
    kandidat: str | None = None
    folge: int = 0
    erster: bool = True


@dataclass(frozen=True)
class Stunde:
    """Eine abgeschlossene Stunde; Schlüssel in UTC, `2026-11-12T06`."""

    schluessel: str
    median_ms: float | None
    antworten: int
    gueltig: bool


def fenster(eintraege: Iterable[tuple[float, float | None]], jetzt: float) -> Fenster:
    """Einträge `(zeit, dauer_ms)` der letzten `FENSTER_S` Sekunden; `None` ist eine Fehlantwort."""
    grenze = jetzt - FENSTER_S
    dauern: list[float] = []
    fehler = 0
    for zeit, dauer in eintraege:
        if zeit < grenze:
            continue
        if dauer is None:
            fehler += 1
        else:
            dauern.append(dauer)
    wert = median(dauern) if len(dauern) >= MIN_ANTWORTEN else None
    return Fenster(wert, len(dauern), fehler)


def regel(f: Fenster, bezug_ms: float | None, abrufe_mit_rest: int) -> str | None:
    """Zustand nach den Regeln, erste zutreffende gilt; `None` bei zu wenig Anfragen."""
    if f.anfragen < MIN_ANFRAGEN:
        return None
    if f.fehlerquote >= GRENZE_FEHLER:
        return GESTOERT
    if abrufe_mit_rest >= GRENZE_LIEGEN:
        return UEBERLASTET
    if bezug_ms is None:
        return SAMMELT
    if (
        f.median_ms is not None
        and f.median_ms > FAKTOR_TRAEGE * bezug_ms
        and f.median_ms - bezug_ms >= ABSTAND_TRAEGE_MS
    ):
        return TRAEGE
    return STABIL


def fortschreiben(stand: Stand, ergebnis: str | None) -> Stand:
    """Ein neuer Zustand gilt erst nach `BESTAETIGUNG` gleichen Ergebnissen; der erste und jeder nach „sammelt“ sofort."""
    if ergebnis is None:
        return stand
    # „Sammelt“ ist kein Urteil; das erste echte Urteil gilt sofort.
    if stand.erster or stand.zustand == SAMMELT or ergebnis == stand.zustand:
        return Stand(ergebnis, erster=False)
    folge = stand.folge + 1 if ergebnis == stand.kandidat else 1
    if folge >= BESTAETIGUNG:
        return Stand(ergebnis, erster=False)
    return Stand(stand.zustand, ergebnis, folge, erster=False)


def stunde_abschliessen(schluessel: str, dauern: list[float], bewertungen: list[str]) -> Stunde:
    """Gültig mit genug Antworten, wenn der Zustand meist stabil oder sammelnd war."""
    ruhig = sum(1 for z in bewertungen if z in GUT)
    gueltig = len(dauern) >= MIN_STUNDE and ruhig * 2 > len(bewertungen)
    return Stunde(schluessel, median(dauern) if dauern else None, len(dauern), gueltig)


def stunden_kuerzen(stunden: list[Stunde], neu: Stunde) -> list[Stunde]:
    """Hängt `neu` an und behält die letzten `BEZUG_STUNDEN` Stunden."""
    return [*stunden, neu][-BEZUG_STUNDEN:]


def vorlaeufiger_bezug(f: Fenster, seit_start_s: float, abrufe_mit_rest: int) -> float | None:
    """Median der ersten vollen Viertelstunde, wenn sie ohne Störung und ohne Rest lief."""
    if seit_start_s < FENSTER_S or f.median_ms is None or abrufe_mit_rest:
        return None
    return None if f.fehlerquote >= GRENZE_FEHLER else f.median_ms


def bezug(stunden: list[Stunde]) -> float | None:
    """Median der gültigen Stundenmediane; unter `MIN_STUNDEN_BEZUG` keiner."""
    werte = [s.median_ms for s in stunden[-BEZUG_STUNDEN:] if s.gueltig and s.median_ms is not None]
    return median(werte) if len(werte) >= MIN_STUNDEN_BEZUG else None
