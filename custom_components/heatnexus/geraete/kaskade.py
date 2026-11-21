"""Kaskade (fctType 4).

Ohne gepflegte Datenpunkttabelle: Name, Rang und Symbol sind belegt, die
Datenpunkte kommen aus den Menü-Ebenen der Anlage. Im Schaubild steht sie nicht,
weil sie die Kessel regelt, ohne selbst in der Leitung zu sitzen.
"""

from __future__ import annotations

FCT_TYPE = 4
MODELL = "Kaskade"
RANG = 16
SYMBOL = "mdi:layers-triple"
SCHAUBILD = None

EXTRA_OIDS: tuple[str, ...] = ()
KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {}

NUR_BUS: tuple[str, ...] = ()

# Die Herstellerdatei zeigt an der Kaskade Brenner und Pumpe des Zusatzkessels aus `2/2` an.
ENTITAETEN: list[dict] = [
    {
        "oid": "/2/2/0",
        "name": "Brenner ZSK",
        "platform": "binary_sensor",
        "bit": 12,
        "key_suffix": "brenner_zsk",
        "device_class": "running",
    },
    {
        "oid": "/2/2/0",
        "name": "Pumpe ZSK",
        "platform": "binary_sensor",
        "bit": 13,
        "key_suffix": "pumpe_zsk",
        "device_class": "running",
    },
]
