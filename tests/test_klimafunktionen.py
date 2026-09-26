"""Welche Funktionstypen ein Thermostat bekommen.

Läuft ohne Home Assistant; die Erkennung selbst prüft `test_heizkreis_infinity`.
"""

from __future__ import annotations

from .conftest import load_standalone


def test_beide_heizkreis_baureihen_sind_klimafunktionen():
    const = load_standalone("const")
    assert {1, 14} <= const.FCT_CLIMATE_TYPES


def test_kessel_und_puffer_bekommen_kein_thermostat():
    const = load_standalone("const")
    assert not {const.FCT_PUROWIN, const.FCT_BIOWIN, const.FCT_BUFFER} & const.FCT_CLIMATE_TYPES
