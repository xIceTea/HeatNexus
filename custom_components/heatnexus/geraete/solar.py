"""Solar (fctType 5).

Ohne gepflegte Datenpunkttabelle: Name, Rang, Symbol und Schaubildteil sind
belegt, die Datenpunkte kommen aus den Menü-Ebenen der Anlage, dazu die Kernwerte des
Herstellers.
"""

from __future__ import annotations

FCT_TYPE = 5
MODELL = "Solar"
RANG = 44
SYMBOL = "mdi:solar-power-variant"
SCHAUBILD = "solar"

# Kernwerte, die der Hersteller über seine Modbus-Schnittstelle ausgibt; nur Anzeigewerte.
EXTRA_OIDS: tuple[str, ...] = (
    "58/50",
    "58/56",
    "58/97",
    "43/99",
    "43/101",
)
KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {}

NUR_BUS: tuple[str, ...] = ()
ENTITAETEN: list[dict] = []
