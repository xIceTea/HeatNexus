"""Temperatur-Zeitprogramme der Heizkreise: Sollwert zur Zeit, Ende der Komfortzeit.

Ein Schaltpunkt gilt bis zum nächsten; vor dem ersten gilt der letzte des
Vortags weiter. Ohne Home Assistant.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

TAGE = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")


def _minuten(text: Any) -> int | None:
    teile = str(text).strip().split(":")
    if len(teile) != 2 or not all(t.isdigit() for t in teile):
        return None
    stunde, minute = int(teile[0]), int(teile[1])
    return stunde * 60 + minute if stunde < 24 and minute < 60 else None


def _punkte(bloecke: Any, tag: date) -> list[tuple[int, float]]:
    code = TAGE[tag.weekday()]
    punkte: list[tuple[int, float]] = []
    for block in bloecke if isinstance(bloecke, list) else []:
        if not isinstance(block, dict) or code not in (block.get("weekdays") or []):
            continue
        for punkt in block.get("switchPoints") or []:
            minute = _minuten((punkt or {}).get("time"))
            try:
                wert = float((punkt or {}).get("value"))
            except (TypeError, ValueError):
                continue
            if minute is not None:
                punkte.append((minute, wert))
    return sorted(punkte)


def soll_je_minute(bloecke: Any, tag: date) -> list[tuple[int, float]]:
    """Schaltpunkte des Tages; vorn der letzte Wert des Vortags ab 0:00."""
    heute = _punkte(bloecke, tag)
    gestern = _punkte(bloecke, tag - timedelta(days=1)) or heute
    if not gestern:
        return []
    if heute and heute[0][0] == 0:
        return heute
    return [(0, gestern[-1][1]), *heute]


def soll_um(bloecke: Any, zeit: datetime) -> float | None:
    """Sollwert zur angegebenen Zeit; None, wenn kein Programm gilt."""
    punkte = soll_je_minute(bloecke, zeit.date())
    minute = zeit.hour * 60 + zeit.minute
    gueltig = [wert for start, wert in punkte if start <= minute]
    return gueltig[-1] if gueltig else None


def horizont(bloecke: Any, jetzt: datetime, rueckfall: time = time(22, 0)) -> datetime:
    """Erste Zeit nach jetzt, zu der der Sollwert unter den aktuellen fällt; sonst der Rückfall."""
    aktuell = soll_um(bloecke, jetzt)
    minute = jetzt.hour * 60 + jetzt.minute
    if aktuell is not None:
        for start, wert in soll_je_minute(bloecke, jetzt.date()):
            if start > minute and wert < aktuell:
                return jetzt.replace(hour=start // 60, minute=start % 60, second=0, microsecond=0)
    return jetzt.replace(hour=rueckfall.hour, minute=rueckfall.minute, second=0, microsecond=0)
