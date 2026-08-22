"""Pufferspeicher B-PLMi (fctType 16).

Trägt neben der Datenpunkttabelle die abgeleiteten Schaltpunkte und
den Rollenfilter des Moduls.
"""

from __future__ import annotations

FCT_TYPE = 16
MODELL = "Pufferspeicher (B-PLMi)"
RANG = 20
SYMBOL = "mdi:storage-tank"
SCHAUBILD = "puffer"

EXTRA_OIDS: tuple[str, ...] = ("0/7", "2/9", "4/82")

KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {}

NUR_BUS: tuple[str, ...] = ()

SCHALTPUNKTE: tuple[dict[str, object], ...] = (
    {
        "fct_type": 16,
        "bezug": "1/15",
        "hysterese": "9/35",
        "anteil": -0.5,
        "name": "Einschaltpunkt",
        # Gegen diese Temperatur läuft die Schwelle: Fällt sie darunter,
        # beginnt die Ladung. Daraus entsteht zusätzlich der Abstand in Kelvin.
        "messwert": "21/65",
        "abstand_name": "Einschaltpunkt Delta",
    },
    {
        "fct_type": 16,
        "bezug": "9/57",
        "hysterese": "9/35",
        "anteil": 1.0,
        "name": "Anforderungstemperatur",
    },
)

# Was der Rollenparameter des Moduls nicht einschließt, ist nicht verdrahtet.
# `nur_bei` nennt je Adresse die Werte, bei denen sie dazugehört.
ROLLEN: dict[str, object] = {
    "quelle": "20/4",
    "nur_bei": {
        # Die Transferpumpe nennt allein Modulfunktion 0.
        "22/75": (0,),
        # Der zweite Pufferfühler kommt erst mit „TPE/TPA" dazu.
        "21/66": (3, 4, 5),
        # Bei 0 fördert die Transferpumpe, sonst die Pumpe zum Erzeuger.
        "1/22": (1, 2, 3, 4, 5),
    },
}

ENTITAETEN: list[dict] = [
    # --- Infoebene (read only) ---
    {"oid": "/21/65/0", "name": "Puffer oben Temperatur (TPE)", "platform": "temperature"},
    {"oid": "/21/66/0", "name": "Puffer unten Temperatur (TPA)", "platform": "temperature"},
    {"oid": "/0/7/0", "name": "Kesseltemperatur", "platform": "temperature"},
    {"oid": "/0/8/0", "name": "Rücklauf Temperatur", "platform": "temperature"},
    {"oid": "/1/8/0", "name": "Rücklauf Sollwert", "platform": "temperature"},
    {
        "oid": "/1/22/0",
        "name": "Pufferladepumpe Drehzahl",
        "platform": "sensor",
        "unit": "%",
        "state_class": "measurement",
    },
    # Stellwert der Rücklaufhochhaltung, kein Kesselmischer. Deren Bauart
    # steht in `20/124` und trägt denselben Namen ohne Zusatz.
    {
        "oid": "/1/102/0",
        "name": "Rücklaufhochhaltung Stellwert",
        "platform": "sensor",
        "unit": "%",
        "state_class": "measurement",
    },
    {"oid": "/2/9/0", "name": "Betriebsart", "platform": "enum_sensor", "enum": "2/9"},
    {
        "oid": "/7/12/0",
        "name": "Drehzahlregelung Modus",
        "platform": "enum_sensor",
        "enum": "7/12",
        "category": "diagnostic",
    },
    # --- Betreiberebene (operate, schreibbar) ---
    {
        "oid": "/20/15/0",
        "name": "Betriebswahl",
        "platform": "select",
        "enum": "20/15",
        "category": "config",
    },
    # --- Serviceebene (schreibbar, Gerät kann Schreibzugriff verweigern) ---
    {
        "oid": "/20/14/0",
        "name": "Pufferladepumpe min Drehzahl",
        "platform": "number",
        "unit": "%",
        "min": 10,
        "max": 100,
        "step": 1,
        "category": "config",
    },
    {
        "oid": "/20/22/0",
        "name": "Pufferladepumpe max Drehzahl",
        "platform": "number",
        "unit": "%",
        "min": 50,
        "max": 100,
        "step": 1,
        "category": "config",
    },
    {
        "oid": "/9/32/0",
        "name": "Puffer Minimaltemperatur",
        "platform": "number",
        "unit": "°C",
        "min": 20,
        "max": 60,
        "step": 1,
        "category": "config",
        "device_class": "temperature",
    },
    {
        "oid": "/10/31/0",
        "name": "Puffer Maximaltemperatur",
        "platform": "number",
        "unit": "°C",
        "min": 60,
        "max": 100,
        "step": 1,
        "category": "config",
        "device_class": "temperature",
    },
    {
        "oid": "/20/28/0",
        "name": "Minimale Laufzeit Pufferladung",
        "platform": "number",
        "unit": "min",
        "min": 0,
        "max": 360,
        "step": 15,
        "category": "config",
    },
    {
        "oid": "/20/29/0",
        "name": "Laufzeitoptimierung Sollwert",
        "platform": "number",
        "unit": "°C",
        "min": 60,
        "max": 85,
        "step": 1,
        "category": "config",
        "device_class": "temperature",
    },
]
