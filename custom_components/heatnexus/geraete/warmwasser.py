"""Warmwasser (fctType 2).

Ohne gepflegte Datenpunkttabelle: Name, Rang, Symbol und Schaubildteil sind
belegt, die Datenpunkte kommen aus den Menü-Ebenen der Anlage, dazu die Kernwerte des
Herstellers.
"""

from __future__ import annotations

FCT_TYPE = 2
MODELL = "Warmwasser"
# Geräteklasse aus der `programId`. Die Klasse 1417 ist die AeroWIN EVO.
MODELLE_JE_KLASSE: dict[str, str] = {"1417": "Warmwasser (AeroWIN EVO)"}
RANG = 42
SYMBOL = "mdi:water-boiler"
SCHAUBILD = "wasser"

# Kernwerte, die der Hersteller über seine Modbus-Schnittstelle ausgibt; nur Anzeigewerte.
EXTRA_OIDS: tuple[str, ...] = (
    "0/4",
    "1/4",
    "0/118",
    "1/118",
    "2/9",
)
KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
# Die Pumpen gibt es als Zustand und als Prozentwert; der Wert trägt den Zusatz.
NAMEN: dict[str, str] = {
    "58/52": "WW-Ladepumpe Drehzahl",
    "59/18": "WW-Zirkulationspumpe Drehzahl",
}

NUR_BUS: tuple[str, ...] = ()

# Zirkulation nach Betriebsart der Zirkulationspumpe `5/6`; aus (0) braucht keinen ihrer Werte.
BEDINGUNGEN: dict[str, list[dict]] = {
    "0/118": [{"oid": "5/6", "values": ["1", "2", "3"]}],
    "1/118": [{"oid": "5/6", "values": ["1", "2", "3"]}],
    "59/18": [{"oid": "5/6", "values": ["2"]}],
    "5/64": [{"oid": "5/6", "values": ["2"]}],
    "5/65": [{"oid": "5/6", "values": ["1", "3"]}],
}
ENTITAETEN: list[dict] = []
