"""Puffermodul mit Kesselumschaltung (fctType 15).

Das Modul führt den Puffer: Fühler oben, mitte, unten und die Ladepumpe. Die
Umschaltventile wählen zusätzlich zwischen Festbrennstoff- und Automatikkessel.
"""

from __future__ import annotations

FCT_TYPE = 15
MODELL = "Umschaltung Kessel/Puffer"
RANG = 18
SYMBOL = "mdi:valve"
SCHAUBILD = "puffer"

EXTRA_OIDS: tuple[str, ...] = ("59/24",)
KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {"59/24": "Umschaltventil"}

NUR_BUS: tuple[str, ...] = ()


def _aktor(bit: int, name: str, endung: str) -> dict:
    """Ein Bit von `2/2` (Aktive Aktoren) als eigener Ein/Aus-Wert."""
    return {
        "oid": "/2/2/0",
        "name": name,
        "platform": "binary_sensor",
        "bit": bit,
        "key_suffix": endung,
        "device_class": "running",
    }


# Die Herstellerdatei zeigt an diesem Modul diese Bits von `2/2` einzeln an.
ENTITAETEN: list[dict] = [
    _aktor(1, "Pufferladepumpe", "pufferladepumpe"),
    _aktor(2, "Umschaltventil 1", "umschaltventil_1"),
    _aktor(3, "Umschaltventil 2", "umschaltventil_2"),
    _aktor(6, "Puffertransferpumpe", "puffertransferpumpe"),
]
