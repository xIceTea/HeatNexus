"""Wärmepumpe (fctType 27).

Ohne gepflegte Datenpunkttabelle: Name, Rang, Symbol und Schaubildteil sind
belegt, die Datenpunkte kommen aus den Menü-Ebenen der Anlage, dazu die Kernwerte des
Herstellers.
"""

from __future__ import annotations

from . import statuszeilen

FCT_TYPE = 27
MODELL = "Wärmepumpe"
# Die Typenliste des Herstellers führt die Klasse 2016 als AeroWIN Deluxe.
MODELLE_JE_KLASSE: dict[str, str] = {"2016": "AeroWIN Deluxe Wärmepumpe"}
# Hinter den Kesseln: Am Hybridmanager kommt der Kessel von links, die Wärmepumpe von rechts.
RANG = 11
SYMBOL = "mdi:heat-pump"
SCHAUBILD = "kessel"

# Kernwerte, die der Hersteller über seine Modbus-Schnittstelle ausgibt; nur Anzeigewerte.
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
    "59/79",
)
STATUSZEILEN = statuszeilen.WAERMEPUMPE
KESSELART: str | None = "waermepumpe"

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {"59/79": "PV-Überschuss"}

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

# Was der Befund für den Gütegrad liest; Phase 4 ist Heizbetrieb. Es gibt nur Gesamtzähler;
# je Größe gilt die erste gemeldete Adresse.
BEFUND = {
    "waermepumpe": {
        "vorlauf": "/50/76/0",
        "phase": "/50/70/0",
        "phasen_heizen": (4,),
        "luft": "/52/12/0",
        "leistung": "/50/26/0",
        "eheizung": "/56/5/0",
        "waerme": ("/60/18/0", "/52/59/0"),
        "strom": ("/52/81/0", "/52/120/0"),
        "kuehlen": ("/60/19/0", "/52/63/0"),
        "bh": "/52/50/0",
    }
}
