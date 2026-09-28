"""Kennzahlen einer Automatik, gemeinsam für die Sensoren von Heizkreis und System."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_util

from . import eingaben, regel
from .regel import Zustand

if TYPE_CHECKING:
    from .laufzeit import Laufzeit

# Aufsteigend nach Gewicht: Das System zeigt den schwersten Zustand seiner Automatiken.
STATUS = ("aus", "beobachten", "bereit", "eingriff", "pausiert", "stoerung")
_EINGRIFF = frozenset({Zustand.SONNENTAG, Zustand.NUR_WW, Zustand.ABWESEND})
_PAUSE = frozenset({Zustand.PAUSIERT, Zustand.FENSTER})


def gestoert(laufzeit: Laufzeit) -> bool:
    """Die Steuerung lehnt Eingriffe ab, oder die Sicherheitsregel greift."""
    gesperrt = laufzeit.steller.stand.gesperrt_bis
    bis = dt_util.parse_datetime(gesperrt) if gesperrt else None
    return laufzeit.zustand == Zustand.SICHERHEIT or (bis is not None and bis > dt_util.now())


def eingriffe_heute(laufzeit: Laufzeit) -> int:
    """Eingriffe heute; der Zähler des Vortags gilt nicht mehr."""
    stand = laufzeit.steller.stand
    return stand.eingriffe if stand.tag == dt_util.now().date().isoformat() else 0


def letzter_eingriff(laufzeit: Laufzeit) -> dict[str, Any] | None:
    """Der jüngste Protokolleintrag, der wirklich an die Steuerung ging."""
    return next(
        (e for e in laufzeit.steller.stand.protokoll if e.get("art") == "geschrieben"), None
    )


def zeit(eintrag: dict[str, Any] | None) -> datetime | None:
    """Zeitpunkt eines Protokolleintrags."""
    return datetime.fromisoformat(eintrag["zeit"]) if eintrag else None


def naechste_entscheidung(laufzeit: Laufzeit) -> datetime | None:
    """Die nächste Entscheidungszeit des Profils, heute oder morgen."""
    jetzt = dt_util.now()
    zeiten = []
    for uhrzeit in (laufzeit.werte.entscheidung, laufzeit.werte.nachpruefung):
        if not uhrzeit:
            continue
        stunde, minute = (int(teil) for teil in uhrzeit.split(":"))
        wann = jetzt.replace(hour=stunde, minute=minute, second=0, microsecond=0)
        zeiten.append(wann if wann > jetzt else wann + timedelta(days=1))
    return min(zeiten) if zeiten else None


def status(laufzeit: Laufzeit) -> str:
    """Ein Wort für den Zustand; im Beobachten zählt nichts als Eingriff."""
    if not laufzeit.aktiv:
        return "aus"
    if gestoert(laufzeit):
        return "stoerung"
    if laufzeit.zustand in _PAUSE:
        return "pausiert"
    if laufzeit.beobachten:
        return "beobachten"
    return "eingriff" if laufzeit.zustand in _EINGRIFF else "bereit"


def schwerster(werte: list[str]) -> str | None:
    """Der schwerste Zustand nach der Rangfolge in `STATUS`."""
    return max(werte, key=STATUS.index) if werte else None


def lauf_heute(lauf: eingaben.Lauf) -> float:
    """Stunden eines Laufs heute; ein Stand vom Vortag zählt nicht."""
    jetzt = dt_util.now()
    aktuell = eingaben.lauf_fortschreiben(lauf, jetzt, lauf.seit is not None)
    return round(eingaben.lauf_minuten(aktuell, jetzt) / 60, 2)


def modus_seit(laufzeit: Laufzeit) -> datetime | None:
    """Beginn des laufenden Modus; im Programm keiner."""
    g = laufzeit.gedaechtnis
    if g.saison == regel.NUR_WW:
        return g.saison_seit
    return g.absenkung_von if regel.absenkung_laeuft(g, dt_util.now()) else None


def schaltet(laufzeit: Laufzeit) -> bool:
    """Ob Eingriffe an die Steuerung gehen."""
    return laufzeit.aktiv and not laufzeit.beobachten
