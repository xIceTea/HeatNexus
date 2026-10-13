"""Die gemeinsame Form jedes Befunds: Wert, Status, Verlässlichkeit, Angaben für Text und Bild."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

UNAUFFAELLIG = "unauffaellig"
HINWEIS = "hinweis"
SAMMELT = "sammelt"
BRAUCHT_DATEN = "braucht_daten"
VORLAEUFIG = "vorlaeufig"
BELASTBAR = "belastbar"


@dataclass(frozen=True)
class Befund:
    """Ein Kennwert; `angaben` trägt Zahlen für Unterzeile, Vergleich und Diagramm."""

    art: str
    status: str
    wert: float | None = None
    einheit: str = ""
    stufe: str = SAMMELT
    angaben: dict[str, Any] = field(default_factory=dict)
    grund: str | None = None


def stufe(anzahl: int, vorlaeufig: int, belastbar: int) -> str:
    """Wie verlässlich ein Wert aus `anzahl` Tagen ist."""
    if anzahl >= belastbar:
        return BELASTBAR
    return VORLAEUFIG if anzahl >= vorlaeufig else SAMMELT


def fehlt(art: str, grund: str) -> Befund:
    """Ein Befund ohne Grundlage; `grund` nennt, was fehlt."""
    return Befund(art, BRAUCHT_DATEN, grund=grund)


def status_aus(stufe_: str, auffaellig: bool) -> str:
    """Solange gesammelt wird, gibt es keinen Hinweis; danach entscheidet der Befund."""
    if stufe_ == SAMMELT:
        return SAMMELT
    return HINWEIS if auffaellig else UNAUFFAELLIG
