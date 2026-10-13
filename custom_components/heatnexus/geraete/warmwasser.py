"""Warmwasser (fctType 2).

Ohne gepflegte Datenpunkttabelle: Name, Rang, Symbol und Schaubildteil sind
belegt, die Datenpunkte kommen aus den Menü-Ebenen der Anlage.
"""

from __future__ import annotations

FCT_TYPE = 2
MODELL = "Warmwasser"
RANG = 42
SYMBOL = "mdi:water-boiler"
SCHAUBILD = "wasser"

EXTRA_OIDS: tuple[str, ...] = ()
KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
# Die Pumpen gibt es als Zustand und als Prozentwert; der Wert trägt den Zusatz.
NAMEN: dict[str, str] = {
    "58/52": "WW-Ladepumpe Drehzahl",
    "59/18": "WW-Zirkulationspumpe Drehzahl",
}

NUR_BUS: tuple[str, ...] = ()
ENTITAETEN: list[dict] = []
