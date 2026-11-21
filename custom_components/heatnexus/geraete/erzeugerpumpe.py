"""Pumpe am Wärmeerzeuger (fctType 24).

Ohne gepflegte Datenpunkttabelle: Name, Rang, Symbol und Schaubildteil sind
belegt, die Datenpunkte kommen aus den Menü-Ebenen der Anlage.
"""

from __future__ import annotations

FCT_TYPE = 24
MODELL = "Pumpe Wärmeerzeuger"
RANG = 24
SYMBOL = "mdi:pump"
SCHAUBILD = "pumpenmodul"

EXTRA_OIDS: tuple[str, ...] = ("58/55",)
KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {"58/55": "Art des Wärmeerzeugers"}
TABELLEN: dict[str, dict[int, str]] = {"58/55": {1: "Manuell", 2: "Automatisch"}}

NUR_BUS: tuple[str, ...] = ()
ENTITAETEN: list[dict] = []
