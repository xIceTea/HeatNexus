"""Ruhe in der Automatik: Ein Wechsel kommt erst, wenn er mehrere Takte hält.

Die Regel liefert, was sie jetzt wollte. Hier entscheidet sich, ob das schon gilt.
Reine Funktionen, ohne Home Assistant.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .profile import Werte
from .regel import (
    ABWESEND,
    PAUSE,
    SONNE,
    Entscheidung,
    Gedaechtnis,
    Lage,
    Zustand,
    abweichung,
    soll_bezug,
    zustand_aus,
)

EINGRIFFE = frozenset({Zustand.SONNENTAG, Zustand.NUR_WW, Zustand.HEIZPAUSE, Zustand.ABWESEND})
# Diese Zustände schützen oder halten an; sie warten auf keinen Takt.
SOFORT = frozenset({Zustand.SICHERHEIT, Zustand.PAUSIERT, Zustand.FENSTER, Zustand.KEINE_DATEN})
_JE_ART = {SONNE: Zustand.SONNENTAG, ABWESEND: Zustand.ABWESEND, PAUSE: Zustand.HEIZPAUSE}
_IN_SICHT = {
    Zustand.SONNENTAG: "Sonnentag in Sicht ({n} von {noetig}): {grund}",
    Zustand.NUR_WW: "Nur Warmwasser in Sicht ({n} von {noetig}): {grund}",
    Zustand.HEIZPAUSE: "Heizpause in Sicht ({n} von {noetig}): {grund}",
    Zustand.ABWESEND: "Abwesend in Sicht ({n} von {noetig}): {grund}",
}
_RUECKKEHR = "Rückkehr ins Programm in Sicht ({n} von {noetig}): {grund}"
_HAELT = "Hält bis {zeit}, dann neu prüfen: {grund}"


@dataclass(frozen=True)
class Verlauf:
    """Welcher Wechsel gerade gezählt wird und bis wann der letzte hält; lebt im Speicher."""

    kandidat: Zustand | None = None
    zaehler: int = 0
    halten_bis: datetime | None = None


@dataclass(frozen=True)
class Anstehend:
    """Ein Wechsel, den die Regel will, der aber noch nicht gilt."""

    zustand: Zustand
    zaehler: int
    noetig: int
    halten_bis: datetime | None = None


@dataclass(frozen=True)
class Ergebnis:
    """Was gilt, was weiter gezählt wird und was ansteht."""

    entscheidung: Entscheidung
    verlauf: Verlauf
    anstehend: Anstehend | None = None


def fruehester_beginn(w: Werte, jetzt: datetime, aufgang: datetime | None) -> datetime | None:
    """Ab wann am Tag von `jetzt` die Sonne als Anlass gilt; `None` heißt ohne Sperre."""
    if w.beginn_art == "aus":
        return None
    if w.beginn_art == "aufgang" and aufgang is not None:
        return aufgang
    stunde, minute = (int(teil) for teil in w.beginn_uhrzeit.split(":"))
    return jetzt.replace(hour=stunde, minute=minute, second=0, microsecond=0)


def laufend(g: Gedaechtnis, jetzt: datetime) -> Zustand:
    """Was an der Steuerung gilt; eine abgelaufene Absenkung zählt bis zum Aufräumen mit."""
    zustand = zustand_aus(g, jetzt)
    if zustand is Zustand.PROGRAMM and g.absenkung_art in _JE_ART:
        return _JE_ART[g.absenkung_art]
    return zustand


def _dringend(
    kandidat: Entscheidung, vorher: Zustand, lage: Lage, alt: Gedaechtnis, w: Werte
) -> bool:
    """Was schützt oder Wärme zurückholt, wartet nicht."""
    if kandidat.zustand in SOFORT or any(a.sicherheit for a in kandidat.aktionen):
        return True
    if vorher not in EINGRIFFE or kandidat.zustand in EINGRIFFE:
        return False
    soll = soll_bezug(lage, alt)
    kalt = soll is not None and bool(lage.raeume) and abweichung(lage, soll) < -w.rueckkehr_k
    heimgekehrt = vorher is Zustand.ABWESEND and not lage.abwesend
    abgeschaltet = vorher is Zustand.SONNENTAG and not w.sonnentag
    return kalt or lage.ruhig is False or heimgekehrt or abgeschaltet


def _bleiben(
    kandidat: Entscheidung, alt: Gedaechtnis, vorher: Zustand, a: Anstehend
) -> Entscheidung:
    if a.halten_bis is not None:
        text = _HAELT.format(zeit=a.halten_bis.strftime("%H:%M"), grund=kandidat.begruendung)
    else:
        muster = _IN_SICHT.get(kandidat.zustand, _RUECKKEHR)
        text = muster.format(n=a.zaehler, noetig=a.noetig, grund=kandidat.begruendung)
    return Entscheidung(vorher, (), text, alt)


def stabilisieren(
    kandidat: Entscheidung,
    alt: Gedaechtnis,
    verlauf: Verlauf,
    lage: Lage,
    w: Werte,
    *,
    takt: bool,
    erzwingen: bool = False,
) -> Ergebnis:
    """Den Kandidaten der Regel gelten lassen oder den laufenden Zustand halten."""
    jetzt, halten = lage.jetzt, verlauf.halten_bis
    vorher = laufend(alt, jetzt)
    if not kandidat.aktionen or kandidat.zustand is vorher:
        return Ergebnis(kandidat, Verlauf(halten_bis=halten) if takt else verlauf)
    if erzwingen or _dringend(kandidat, vorher, lage, alt, w):
        return Ergebnis(kandidat, Verlauf(halten_bis=jetzt + timedelta(minutes=w.halten_min)))
    noetig = w.beginn_laeufe if kandidat.zustand in EINGRIFFE else w.ende_laeufe
    if halten is not None and jetzt < halten:
        a = Anstehend(kandidat.zustand, 0, noetig, halten)
        return Ergebnis(_bleiben(kandidat, alt, vorher, a), Verlauf(halten_bis=halten), a)
    zaehler = verlauf.zaehler if verlauf.kandidat is kandidat.zustand else 0
    if not takt:
        a = Anstehend(kandidat.zustand, zaehler, noetig)
        return Ergebnis(_bleiben(kandidat, alt, vorher, a), verlauf, a)
    zaehler += 1
    if zaehler >= noetig:
        return Ergebnis(kandidat, Verlauf(halten_bis=jetzt + timedelta(minutes=w.halten_min)))
    a = Anstehend(kandidat.zustand, zaehler, noetig)
    neu = Verlauf(kandidat.zustand, zaehler, halten)
    return Ergebnis(_bleiben(kandidat, alt, vorher, a), neu, a)
