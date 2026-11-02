"""Wärmepumpe (fctType 27).

Ohne gepflegte Datenpunkttabelle: Name, Rang, Symbol und Schaubildteil sind
belegt, die Datenpunkte kommen aus den Menü-Ebenen der Anlage, dazu die Kernwerte des
Herstellers.
"""

from __future__ import annotations

from . import statuszeilen

FCT_TYPE = 27
MODELL = "Wärmepumpe"
RANG = 10
SYMBOL = "mdi:heat-pump"
SCHAUBILD = "kessel"

# Kernwerte, die der Hersteller über seine Modbus-Schnittstelle ausgibt; nur Anzeigewerte.
STATUSZEILEN = statuszeilen.KESSEL
EXTRA_OIDS: tuple[str, ...] = (
    "50/26",
    "50/70",
    "50/76",
    "52/49",
    "52/50",
    "52/54",
    "52/57",
    "52/59",
    "52/63",
    "52/121",
    "54/49",
    "56/29",
    "59/45",
    "59/71",
)
KESSELART: str | None = "waermepumpe"

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {}

NUR_BUS: tuple[str, ...] = ()

# Zählerstände ohne Schreibschutz der Steuerung: als Anzeige, damit sie in die Langzeitstatistik gehen.
NUR_ANZEIGE: tuple[str, ...] = (
    "52/49",  # Anzahl Starts Heizen
    "52/50",  # Betriebsstunden Heizen
    "52/54",  # Betriebsstunden Kühlen
    "52/57",  # Anzahl Starts Kühlen
    "52/59",  # Wärmemenge Heizen
    "52/63",  # Energiemenge Kühlen
    "56/29",  # Betriebsstunden
    "59/71",  # Anzahl Starts
)
ENTITAETEN: list[dict] = []
