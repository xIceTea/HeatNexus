"""Wann eine Bedienung freigegeben ist.

Eine Regel nennt je Adresse die Werte, bei denen bedient werden darf. Alle
Regeln müssen gelten; ein fehlender Wert sperrt. Das Modul kommt ohne Home
Assistant aus.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def _ganzzahl(wert: object) -> str | None:
    """`3.0` und `3` gelten als derselbe Schaltwert."""
    try:
        return str(int(float(str(wert))))
    except (TypeError, ValueError):
        return None


def adressen(regeln: Mapping[str, Sequence[str]] | None, praefix: str) -> list[str]:
    """Die vollständigen OIDs, die eine Regel liest."""
    return [f"{praefix}/{adresse}/0" for adresse in regeln or {}]


def freigegeben(
    regeln: Mapping[str, Sequence[str]] | None,
    praefix: str,
    werte: Mapping[str, object],
) -> bool:
    """Ob jede Regel mit den aktuellen Werten erfüllt ist."""
    for adresse, erlaubt in (regeln or {}).items():
        ist = _ganzzahl(werte.get(f"{praefix}/{adresse}/0"))
        if ist is None or ist not in {_ganzzahl(w) for w in erlaubt}:
            return False
    return True
