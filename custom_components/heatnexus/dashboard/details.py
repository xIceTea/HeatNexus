"""Unteransicht je Anlagenteil: alles, was der Teil führt, nach Zweck gegliedert."""

from __future__ import annotations

from typing import Any

from . import auswahl
from .anlagen import voller_name
from .karten import abschnitt, ansicht, kachel, pfad_anlage, pfad_teil


def unteransicht(anlage: dict[str, Any], teil: dict[str, Any]) -> dict[str, Any] | None:
    """Unteransicht mit allen Entitäten eines Anlagenteils, nach Zweck gegliedert."""
    abschnitte = [
        *abschnitt(
            "Bedienung", [kachel(e) for e in [*auswahl.thermostate(teil), *auswahl.bedienung(teil)]]
        ),
        *abschnitt("Messwerte", [kachel(e) for e in auswahl.messwerte(teil)]),
        *abschnitt("Zeitprogramme", [kachel(e) for e in auswahl.zeitprogramme(teil)]),
        *abschnitt("Einstellungen", [kachel(e) for e in auswahl.einstellungen(teil)]),
        *abschnitt("Diagnose", [kachel(e) for e in auswahl.diagnose(teil)]),
    ]
    if not abschnitte:
        return None
    return ansicht(
        voller_name(anlage, teil), pfad_teil(teil), abschnitte, zurueck=pfad_anlage(anlage)
    )
