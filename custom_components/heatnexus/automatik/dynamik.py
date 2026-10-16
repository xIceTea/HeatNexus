"""Ruhe in der Automatik: Ein Wechsel kommt erst, wenn er mehrere Takte hält.

Die Regel liefert, was sie jetzt wollte. Hier entscheidet sich, ob das schon gilt.
Reine Funktionen, ohne Home Assistant.
"""

from __future__ import annotations

from datetime import datetime

from .profile import Werte


def fruehester_beginn(w: Werte, jetzt: datetime, aufgang: datetime | None) -> datetime | None:
    """Ab wann am Tag von `jetzt` die Sonne als Anlass gilt; `None` heißt ohne Sperre."""
    if w.beginn_art == "aus":
        return None
    if w.beginn_art == "aufgang" and aufgang is not None:
        return aufgang
    stunde, minute = (int(teil) for teil in w.beginn_uhrzeit.split(":"))
    return jetzt.replace(hour=stunde, minute=minute, second=0, microsecond=0)
