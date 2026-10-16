"""Die letzten Läufe der Regel je Heizkreis; ein Ringpuffer im Speicher, ohne Schreiblast."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from .bewertung import Bewertung
from .dynamik import Anstehend
from .regel import Zustand

DAUER = timedelta(hours=24)
HOECHSTENS = 300


def _merkmal(e: dict[str, Any]) -> tuple[Any, ...]:
    haken = tuple((b["name"], b["erfuellt"]) for b in e["bewertungen"])
    return (e["kandidat"], e["zustand"], e["zaehler"], e["ergebnis"], haken)


def eintrag(
    jetzt: datetime,
    kandidat: Zustand,
    zustand: Zustand,
    anstehend: Anstehend | None,
    ergebnis: str,
    bewertungen: tuple[Bewertung, ...],
) -> dict[str, Any]:
    """Ein Lauf als Eintrag für Panel und Diagnose."""
    halten = anstehend.halten_bis if anstehend else None
    return {
        "zeit": jetzt.isoformat(),
        "kandidat": kandidat.value,
        "zustand": zustand.value,
        "zaehler": anstehend.zaehler if anstehend else None,
        "noetig": anstehend.noetig if anstehend else None,
        "halten_bis": halten.isoformat() if halten else None,
        "ergebnis": ergebnis,
        "bewertungen": [asdict(b) for b in bewertungen],
    }


class Regellauf:
    """Neueste zuerst; ein Lauf ohne Änderung gegenüber dem letzten erzeugt keine Zeile."""

    def __init__(self) -> None:
        self._eintraege: deque[dict[str, Any]] = deque(maxlen=HOECHSTENS)
        self._letztes: tuple[Any, ...] | None = None

    def eintragen(self, e: dict[str, Any]) -> bool:
        """Den Lauf aufnehmen, wenn er sich vom letzten unterscheidet."""
        merkmal = _merkmal(e)
        if merkmal == self._letztes:
            return False
        self._letztes = merkmal
        self._eintraege.appendleft(e)
        return True

    def liste(self, jetzt: datetime) -> list[dict[str, Any]]:
        """Die Einträge der letzten 24 Stunden, neueste zuerst."""
        grenze = jetzt - DAUER
        while self._eintraege and datetime.fromisoformat(self._eintraege[-1]["zeit"]) < grenze:
            self._eintraege.pop()
        return list(self._eintraege)
