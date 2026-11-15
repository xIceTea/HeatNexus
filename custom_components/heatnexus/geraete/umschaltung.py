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

# `22/50` und `1/7` stehen im Menü des Moduls, aber in keiner Herstellerebene.
# `2/9` führt die Herstellerebene, das Menü des Moduls nicht.
EXTRA_OIDS: tuple[str, ...] = ("59/24", "22/50", "1/7", "2/9")
KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
# „Pufferladepumpe“ trägt schon der Zustand aus `2/2`.
# `1/7` ist die Anforderung der Verbraucher an den Kessel, nicht dessen Sollwert.
NAMEN: dict[str, str] = {
    "59/24": "Umschaltventil",
    "22/50": "Pufferladepumpe Drehzahl",
    "1/7": "Anforderung an den Kessel",
}

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
# Bit 1 blieb an einer Anlage während der Ladung aus; deshalb ab Werk deaktiviert.
# Bit 2 und 3 sind die zwei Laufrichtungen desselben Umschaltventils.
ENTITAETEN: list[dict] = [
    {**_aktor(1, "Pufferladepumpe", "pufferladepumpe"), "enabled_default": False},
    _aktor(2, "Umschaltventil Richtung 1", "umschaltventil_1"),
    _aktor(3, "Umschaltventil Richtung 2", "umschaltventil_2"),
    _aktor(6, "Puffertransferpumpe", "puffertransferpumpe"),
    # Die Betriebsart steht auf „Automatikkessel“ oder „FB-Kessel“, solange die
    # Pufferladepumpe läuft; bei „Pufferspeicher“ wird der Puffer entladen. Pumpenbit
    # und Drehzahl schalten zusätzlich ein, falls die Betriebsart nachhinkt.
    {
        "oid": "/2/9/0",
        "name": "Pufferladung",
        "platform": "binary_sensor",
        "an_bei": (14, 15),
        "oder": ({"adresse": "2/2", "bit": 1}, {"adresse": "22/50"}),
        "key_suffix": "pufferladung",
        "device_class": "running",
    },
    # Die Betriebsart selbst, damit Verlauf und Diagnose zeigen, ob das Modul
    # vom Automatik- oder vom FB-Kessel lädt oder entlädt. Ohne Zusatz, damit
    # die Kennung der Entität aus den Herstellerebenen erhalten bleibt.
    {
        "oid": "/2/9/0",
        "name": "Betriebsart",
        "platform": "enum_sensor",
        "enum": "2/9",
    },
]

# Der Kessel spiegelt Puffertemperaturen und Beladegrad des Moduls. Das Modul
# führt sie selbst; am Kessel stünden sie ein zweites Mal.
SPIEGEL: dict[int, tuple[str, ...]] = {10: ("0/15", "0/16", "0/17", "23/87")}

# `20/2` Pufferspeicher und `20/0` Automatikkessel legen fest, was das Modul führt:
# ohne Puffer keine Ladung, ohne Automatikkessel keine Umschaltventile.
BEDINGUNGEN: dict[str, list[dict]] = {
    "2/9:pufferladung": [{"oid": "20/2", "values": ["1"]}],
    "2/2:umschaltventil_1": [{"oid": "20/0", "values": ["1"]}],
    "2/2:umschaltventil_2": [{"oid": "20/0", "values": ["1"]}],
}
