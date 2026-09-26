"""Heizkreis Infinity PLUS (fctType 1).

Ohne gepflegte Datenpunkttabelle: Name, Rang, Symbol und Schaubildteil sind
belegt, die Datenpunkte kommen aus den Menü-Ebenen der Anlage.
"""

from __future__ import annotations

FCT_TYPE = 1
MODELL = "Heizkreis (Infinity PLUS)"
RANG = 30
SYMBOL = "mdi:radiator"
SCHAUBILD = "heizkreis"

EXTRA_OIDS: tuple[str, ...] = ()
KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {
    # Die Herstellertabelle nennt Programme und Sollwerte für Raum- und
    # Vorlauftemperatur gleich. Die Vorlaufwerte tragen deshalb ihre Größe im Namen.
    "58/78": "Programm 1 Vorlauftemperatur",
    "58/79": "Programm 2 Vorlauftemperatur",
    "58/80": "Programm 3 Vorlauftemperatur",
    "58/81": "Vorlauftemperatur Heizbetrieb",
    "58/82": "Vorlauftemperatur Absenkbetrieb",
}

NUR_BUS: tuple[str, ...] = ()
ENTITAETEN: list[dict] = []
