"""Zugriff auf die Anlage: ein Client, der alles Gerätewissen hält.

Das Paket ist nach Aufgaben geschnitten; die Klasse setzt sich aus den Mixins
zusammen. Was hier steht, ist die Schnittstelle nach außen.
"""

from __future__ import annotations

from .abruf import _ist_zeitprogramm
from .erkennung import (
    DESKRIPTOR_VORGABE,
    NAME_OVERRIDES,
    _name_override,
    _statische_positionen,
)
from .kern import WindhagerHttpClient

__all__ = [
    "DESKRIPTOR_VORGABE",
    "NAME_OVERRIDES",
    "WindhagerHttpClient",
    "_ist_zeitprogramm",
    "_name_override",
    "_statische_positionen",
]
