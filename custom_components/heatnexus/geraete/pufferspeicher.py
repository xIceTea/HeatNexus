"""Pufferspeicher neuerer Bauart (fctType 21).

Ohne gepflegte Datenpunkttabelle: Name, Rang, Symbol und Schaubildteil sind
belegt, die Datenpunkte kommen aus den Menü-Ebenen der Anlage.
"""

from __future__ import annotations

FCT_TYPE = 21
MODELL = "Pufferspeicher"
RANG = 22
SYMBOL = "mdi:storage-tank"
SCHAUBILD = "puffer"
KERNWERTE: tuple[str, ...] = ("buffer_top", "buffer_bottom")
RUNDINSTRUMENTE: tuple[tuple[str, dict], ...] = (
    ("buffer_top", {"min": 0, "max": 95, "severity": {"green": 60, "yellow": 80, "red": 90}}),
    ("buffer_bottom", {"min": 0, "max": 95, "severity": {"green": 40, "yellow": 70, "red": 85}}),
)

EXTRA_OIDS: tuple[str, ...] = ()
KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {}

NUR_BUS: tuple[str, ...] = ()
ENTITAETEN: list[dict] = []
