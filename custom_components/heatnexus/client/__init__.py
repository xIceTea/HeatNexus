"""Zugriff auf die Anlage: ein Client, der alles Gerätewissen hält.

Das Paket ist nach Aufgaben geschnitten; die Klasse setzt sich aus den Mixins
zusammen. Was hier steht, ist die Schnittstelle nach außen.
"""

from __future__ import annotations

from .abruf import ist_zeitprogramm
from .erkennung import (
    DESKRIPTOR_VORGABE,
    NAME_OVERRIDES,
    name_override,
    statische_positionen,
)
from .kern import WindhagerHttpClient

__all__ = [
    "DESKRIPTOR_VORGABE",
    "NAME_OVERRIDES",
    "WindhagerHttpClient",
    "ist_zeitprogramm",
    "name_override",
    "statische_positionen",
]
