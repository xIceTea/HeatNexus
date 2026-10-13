"""Gradtagzahl nach VDI 3807: Raum 20 °C, Heizgrenze 15 °C, in Österreich und der Schweiz 12 °C."""

from __future__ import annotations

RAUM = 20.0
GRENZE = 15.0
GRENZE_ALPEN = 12.0
LAENDER_ALPEN = frozenset({"AT", "CH", "LI"})


def rechengrenze(land: str | None) -> float:
    """Die Heizgrenze der Gradtagzahl für das Land aus den Einstellungen von Home Assistant."""
    return GRENZE_ALPEN if (land or "").upper() in LAENDER_ALPEN else GRENZE


def gradtag(tagesmittel: float, grenze: float) -> float:
    """Kelvin unter der Raumtemperatur an einem Tag unter der Heizgrenze, sonst 0."""
    return RAUM - tagesmittel if tagesmittel < grenze else 0.0
