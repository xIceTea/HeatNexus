"""Die Grenze für Komplexität und Länge der Funktionen.

Neue Funktionen bleiben unter der Grenze; festgeschriebene dürfen nicht wachsen.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]


def _regel():
    pfad = WURZEL / "tools" / "strukturregel.py"
    spezifikation = importlib.util.spec_from_file_location("strukturregel", pfad)
    modul = importlib.util.module_from_spec(spezifikation)
    spezifikation.loader.exec_module(modul)
    return modul


def test_neue_funktion_unter_der_grenze_ist_frei() -> None:
    regel = _regel()
    assert regel.pruefen({"a.py::f": {"komplexitaet": 15, "zeilen": 80}}, {}) == []


def test_neue_funktion_ueber_der_grenze_scheitert() -> None:
    regel = _regel()
    befunde = regel.pruefen({"a.py::f": {"komplexitaet": 16, "zeilen": 10}}, {})
    assert befunde == ["a.py::f – komplexitaet 16, erlaubt 15"]


def test_festgeschriebene_funktion_darf_nicht_wachsen() -> None:
    regel = _regel()
    stand = {"a.py::f": {"zeilen": 120}}
    assert regel.pruefen({"a.py::f": {"komplexitaet": 3, "zeilen": 120}}, stand) == []
    assert regel.pruefen({"a.py::f": {"komplexitaet": 3, "zeilen": 121}}, stand) == [
        "a.py::f – zeilen 121, erlaubt 120"
    ]


def test_festgeschriebene_funktion_haelt_die_grenze_der_anderen_groesse() -> None:
    regel = _regel()
    stand = {"a.py::f": {"zeilen": 120}}
    befunde = regel.pruefen({"a.py::f": {"komplexitaet": 16, "zeilen": 100}}, stand)
    assert befunde == ["a.py::f – komplexitaet 16, erlaubt 15"]
