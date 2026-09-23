"""BioWIN Pelletskessel (fctType 9).

Jeder Datenpunkt ist aus zwei unabhängigen Quellen belegt. Plattform und
Schreibrecht folgen den Metadaten, die BioWIN-Anlagen tatsächlich melden.
"""

from __future__ import annotations

FCT_TYPE = 9
MODELL = "BioWIN Pelletskessel"
RANG = 10
SYMBOL = "mdi:fire"
SCHAUBILD = "kessel"

EXTRA_OIDS: tuple[str, ...] = ()

# Was diese Baureihe nur über den LON-Bus hergibt. Die Brennkammertemperatur
# steht in der Serviceebene des Herstellers, wird als Datenpunkt aber nicht
# von jeder Anlage angeboten.
KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {
    # Die Tabelle nennt hier nur den Messgrößenteil; wozu er gehört, sagt erst
    # die Einheit und der Bereich, den die Anlage meldet.
    "9/90": "Kaminkehrer Restlaufzeit",
    "12/98": "Saugzuggebläse Drehzahl Minimum",
    "12/99": "Saugzuggebläse Drehzahl Maximum",
    "12/100": "Fördermenge Bereich",
    "12/101": "Fördermenge Istwert",
    "12/104": "Fördermenge Korrektur",
    "14/79": "Heizflächenreinigung Beginn Sperrzeit",
    "14/80": "Heizflächenreinigung Dauer",
}

NUR_BUS: tuple[str, ...] = ("Brennkammertemperatur", "Gebläsedrehzahl", "Pelletsvorrat")

# Jeder Eintrag ist doppelt belegt: über die `overview`-Ebene des Herstellers
# und über ein öffentliches BioWIN-II-Projekt an einer laufenden Anlage. Die
# Wartungszähler liegen anders als beim PuroWIN (20/61..63 statt 39/91..93).
ENTITAETEN: list[dict] = [
    # --- Titelbild / Infoebene (read only) ---
    {"oid": "/0/7/0", "name": "Kesseltemperatur Ist", "platform": "temperature"},
    {"oid": "/1/7/0", "name": "Kesseltemperatur Soll", "platform": "temperature"},
    {
        "oid": "/0/9/0",
        "name": "Kesselleistung",
        "platform": "sensor",
        "unit": "%",
        "state_class": "measurement",
    },
    {"oid": "/0/11/0", "name": "Abgastemperatur", "platform": "temperature"},
    {"oid": "/2/1/0", "name": "Betriebsphase", "platform": "enum_sensor", "enum": "2/1"},
    {"oid": "/2/59/0", "name": "Betriebsart", "platform": "enum_sensor", "enum": "2/59"},
    {
        "oid": "/2/80/0",
        "name": "Brennerstarts",
        "platform": "sensor",
        "state_class": "total_increasing",
    },
    {
        "oid": "/2/81/0",
        "name": "Betriebsstunden",
        "platform": "sensor",
        "unit": "h",
        "state_class": "total_increasing",
    },
    {
        "oid": "/0/22/0",
        "name": "Pumpensteuerung Drehzahl",
        "platform": "sensor",
        "unit": "%",
        "state_class": "measurement",
    },
    # Restlaufzeiten: "measurement" wie beim PuroWIN – nur so entsteht ein
    # Langzeitverlauf, aus dem sich ablesen lässt, wann zuletzt gereinigt
    # wurde. Die Adressen sind die des BioWIN, nicht die des PuroWIN.
    {
        "oid": "/20/61/0",
        "name": "Laufzeit bis Reinigung",
        "platform": "sensor",
        "unit": "h",
        "state_class": "measurement",
        "icon": "mdi:broom",
    },
    {
        "oid": "/20/62/0",
        "name": "Laufzeit bis Hauptreinigung",
        "platform": "sensor",
        "unit": "h",
        "state_class": "measurement",
        "icon": "mdi:broom",
    },
    {
        "oid": "/20/63/0",
        "name": "Laufzeit bis Wartung",
        "platform": "sensor",
        "unit": "h",
        "state_class": "measurement",
        "icon": "mdi:wrench-clock",
    },
    {
        "oid": "/23/100/0",
        "name": "Brennstoffverbrauch seit Befüllung",
        "platform": "sensor",
        "icon": "mdi:sack",
    },
    {
        "oid": "/23/103/0",
        "name": "Brennstoffverbrauch gesamt",
        "platform": "sensor",
        "icon": "mdi:sack",
    },
    # Betreiberebene beider BioWIN-Geräteklassen, an der Anlage schreibbar.
    # Meldet die Steuerung Schreibschutz, entsteht daraus die Anzeige.
    {
        "oid": "/14/19/0",
        "name": "Betriebsart Zuführung",
        "platform": "select",
        "enum": "14/19",
        "category": "config",
        "icon": "mdi:transfer",
    },
]
