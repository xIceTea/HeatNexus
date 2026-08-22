"""Wärmepumpe mit Energiemanagement (fctType 26).

Ohne gepflegte Datenpunkttabelle: Name, Rang, Symbol und Schaubildteil sind
belegt, die Datenpunkte kommen aus den Menü-Ebenen der Anlage.
"""

from __future__ import annotations

FCT_TYPE = 26
MODELL = "Wärmepumpe (Energiemanagement)"
RANG = 10
SYMBOL = "mdi:heat-pump"
SCHAUBILD = "kessel"

EXTRA_OIDS: tuple[str, ...] = ()
KESSELART: str | None = "waermepumpe"

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {}

NUR_BUS: tuple[str, ...] = ()
ENTITAETEN: list[dict] = []
