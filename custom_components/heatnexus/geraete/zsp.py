"""Pumpen- und Relaismodul ZSP (fctType 20).

Pumpe, externe Wärmeanforderung und Sammelalarm; die Fühlereingänge
gehören dem Modul.
"""

from __future__ import annotations

FCT_TYPE = 20
MODELL = "Pumpen-/Relaismodul (ZSP)"
RANG = 50
SYMBOL = "mdi:pump"
SCHAUBILD = "pumpenmodul"

EXTRA_OIDS: tuple[str, ...] = ("0/7", "1/7", "4/92", "4/93")

KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {}

NUR_BUS: tuple[str, ...] = ()

# Die Namen sind die des Herstellers: `0/7` heißt hier „Kesseltemperatur" und
# meint den eigenen Fühlereingang des Moduls, nicht den Kessel dahinter.
ENTITAETEN: list[dict] = [
    {"oid": "/0/7/0", "name": "Kesseltemperatur", "platform": "temperature"},
    {"oid": "/1/7/0", "name": "Kesseltemperatur Soll", "platform": "temperature"},
    {
        "oid": "/0/22/0",
        "name": "Pumpendrehzahl",
        "platform": "sensor",
        "unit": "%",
        "state_class": "measurement",
    },
]
