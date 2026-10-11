"""Heizkreis UML und UMLZ (fctType 14).

Trägt neben der Datenpunkttabelle den Abstand bis zum nächsten
Schaltpunkt des Warmwassers.
"""

from __future__ import annotations

FCT_TYPE = 14
MODELL = "Heizkreis (UML/UMLZ)"
RANG = 30
SYMBOL = "mdi:radiator"
SCHAUBILD = "heizkreis"

# Zeitprogramme, Warmwasser- und Zirkulationswerte sowie die gemessene
# Raumtemperatur tauchen in keiner Menü-Ebene auf.
EXTRA_OIDS: tuple[str, ...] = (
    "0/1",
    "0/4",
    "0/118",
    "1/4",
    "1/65",
    "1/118",
    "2/9",
    "4/82",
    "3/61",
    "3/62",
    "3/63",
    "5/51",
    "5/61",
    "5/64",
    "5/65",
    "5/70",
    "5/71",
)

KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {
    # Menü „Frostschutzgrenzen": Die Herstellertabelle führt die Namen ohne
    # den Menütitel, unter dem sie am Gerät stehen.
    "3/0": "Frostschutzgrenze Raumtemperatur",
    "3/23": "Frostschutzgrenze Außentemperatur",
    "7/45": "Frostschutzgrenze Vorlauftemperatur",
    "5/58": "Frostschutzgrenze WW-Speicher",
}

NUR_BUS: tuple[str, ...] = ()

VERBRAUCHER_ABSTAND: tuple[dict[str, object], ...] = (
    {
        "fct_type": 14,
        "ist": "0/4",
        "soll": "1/4",
        "hysterese": "5/0",
        "zustand": "1/66",
        "name": "WW-Einschaltpunkt Delta",
        "schaltpunkt_name": "WW-Einschaltpunkt",
        "schaltpunkt_anteil": -1.0,
    },
)

ENTITAETEN: list[dict] = [
    # --- Infoebene Heizkreis / Warmwasser (read only) ---
    {"oid": "/0/0/0", "name": "Außentemperatur", "platform": "temperature"},
    {"oid": "/0/1/0", "name": "Raumtemperatur Ist", "platform": "temperature"},
    {"oid": "/1/1/0", "name": "Raumtemperatur Soll", "platform": "temperature"},
    {"oid": "/0/2/0", "name": "Vorlauftemperatur Ist", "platform": "temperature"},
    {"oid": "/1/2/0", "name": "Vorlauftemperatur Soll", "platform": "temperature"},
    {"oid": "/0/7/0", "name": "Kesseltemperatur Ist", "platform": "temperature"},
    {"oid": "/1/7/0", "name": "Kesseltemperatur Soll", "platform": "temperature"},
    {"oid": "/0/4/0", "name": "Warmwasser Ist-Temperatur", "platform": "temperature"},
    {"oid": "/1/4/0", "name": "Warmwasser Soll-Temperatur", "platform": "temperature"},
    {"oid": "/0/118/0", "name": "WW-Zirkulation Ist-Temperatur", "platform": "temperature"},
    {"oid": "/1/118/0", "name": "WW-Zirkulation Soll-Temperatur", "platform": "temperature"},
    {
        "oid": "/1/20/0",
        "name": "Heizkreispumpe",
        "platform": "binary_sensor",
        "device_class": "running",
    },
    {
        "oid": "/1/21/0",
        "name": "Mischer Stellwert",
        "platform": "sensor",
        "unit": "%",
        "state_class": "measurement",
    },
    {
        "oid": "/1/65/0",
        "name": "WW-Zirkulationspumpe",
        "platform": "binary_sensor",
        "device_class": "running",
    },
    # Der Modus der Zirkulationspumpe gehört zur Bedienung, obwohl der
    # Hersteller `5/6` auf der Serviceebene führt. Er entscheidet, welches der
    # beiden gleichnamigen Zirkulationsprogramme wirkt.
    {
        "oid": "/5/6/0",
        "name": "WW-Zirkulationspumpe Modus",
        "platform": "select",
        "enum": "5/6",
        "category": "config",
        "icon": "mdi:reload",
    },
    # Wie weit die Warmwassertemperatur unter den Sollwert fallen darf, bevor
    # die Anlage nachlädt (Werk 5 K, Bereich 1 bis 20 K). Gilt für jede
    # Ladung, nicht nur für die Einmalladung.
    {
        "oid": "/5/0/0",
        "name": "Hysterese Ein",
        "platform": "number",
        "unit": "K",
        "min": 1,
        "max": 20,
        "step": 0.5,
        "category": "config",
        "icon": "mdi:arrow-expand-vertical",
    },
    {
        "oid": "/1/66/0",
        "name": "WW-Ladepumpe",
        "platform": "binary_sensor",
        "device_class": "running",
    },
    {"oid": "/2/9/0", "name": "Betriebsart", "platform": "enum_sensor", "enum": "2/9"},
    # --- Betreiberebene (operate, schreibbar) ---
    {
        "oid": "/3/50/0",
        "name": "Betriebswahl",
        "platform": "select",
        "enum": "3/50",
        "category": "config",
    },
    {
        "oid": "/3/58/0",
        "name": "Behaglichkeitskorrektur",
        "platform": "number",
        "unit": "K",
        "min": -3.0,
        "max": 3.0,
        "step": 0.1,
        "category": "config",
    },
    {
        "oid": "/3/51/0",
        "name": "Raumtemperatur Heizbetrieb",
        "platform": "number",
        "unit": "°C",
        "min": 10,
        "max": 30,
        "step": 0.5,
        "category": "config",
        "device_class": "temperature",
    },
    {
        "oid": "/3/53/0",
        "name": "Raumtemperatur Absenkbetrieb",
        "platform": "number",
        "unit": "°C",
        "min": 10,
        "max": 30,
        "step": 0.5,
        "category": "config",
        "device_class": "temperature",
    },
    {
        "oid": "/5/51/0",
        "name": "WW Einmalladung Temperatur",
        "platform": "number",
        "unit": "°C",
        "min": 10,
        "max": 75,
        "step": 0.5,
        "category": "config",
        "device_class": "temperature",
    },
    {
        "oid": "/2/16/0",
        "name": "WW Einmalladung",
        "platform": "switch",
        "category": "config",
        "icon": "mdi:water-boiler",
    },
]
