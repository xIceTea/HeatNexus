"""Der Reiter „Wartung": Restlaufzeiten, Brennstoff, Zählerstände."""

from __future__ import annotations

from typing import Any

from ..dashboard.anlagen import trifft
from ..dashboard.muster import (
    WARTUNG_RESTLAUFZEIT,
    WARTUNG_RESTLAUFZEIT_SCHLUESSEL,
    WARTUNG_WEITERE,
    WARTUNG_WEITERE_SCHLUESSEL,
)
from .muster import (
    WARTUNG_BRENNSTOFF,
    WARTUNG_BRENNSTOFF_SCHLUESSEL,
)


def wartung(anlage: dict[str, Any]) -> dict[str, Any]:
    """Der Reiter „Wartung": Restlaufzeiten, Brennstoff, Zählerstände."""
    alle = [e for teil in anlage["teile"] for e in teil["entitaeten"]]

    def zeilen(bedingung) -> list[dict[str, str]]:
        return [
            {"entity": e["entity_id"], "titel": e["name"]}
            for e in alle
            if e["kategorie"] is None and bedingung(e)
        ]

    return {
        "restlaufzeiten": zeilen(
            lambda e: trifft(e, WARTUNG_RESTLAUFZEIT, *WARTUNG_RESTLAUFZEIT_SCHLUESSEL)
        ),
        "brennstoff": zeilen(
            lambda e: (
                trifft(e, WARTUNG_BRENNSTOFF, *WARTUNG_BRENNSTOFF_SCHLUESSEL)
                and not trifft(e, WARTUNG_RESTLAUFZEIT, *WARTUNG_RESTLAUFZEIT_SCHLUESSEL)
            )
        ),
        # Zählerstände erkennt man an der Statistikklasse, nicht am Namen.
        # `total` gehört dazu: Ein Tageswert ist ein Zählerstand, er beginnt
        # nur jeden Tag neu.
        "zaehler": zeilen(lambda e: e.get("state_class") in ("total_increasing", "total")),
        "weitere": zeilen(
            lambda e: (
                trifft(e, WARTUNG_WEITERE, *WARTUNG_WEITERE_SCHLUESSEL)
                and not trifft(e, WARTUNG_RESTLAUFZEIT, *WARTUNG_RESTLAUFZEIT_SCHLUESSEL)
                and not trifft(e, WARTUNG_BRENNSTOFF, *WARTUNG_BRENNSTOFF_SCHLUESSEL)
                and e.get("state_class") not in ("total_increasing", "total")
            )
        ),
    }
