"""Wärmepumpe (fctType 7).

Ohne gepflegte Datenpunkttabelle: Die Datenpunkte kommen aus den Menü-Ebenen
der Anlage, dazu Wärmemengen, Betriebsstunden, Starts und COP aus Gruppe 52.
"""

from __future__ import annotations

FCT_TYPE = 7
MODELL = "Wärmepumpe"
RANG = 10
SYMBOL = "mdi:heat-pump"
SCHAUBILD = "kessel"

# Gruppe 52 steht in keinem Menü der Steuerung; abgeglichen mit der App an einer BioWIN Hybrid.
EXTRA_OIDS: tuple[str, ...] = (
    "52/50",
    "52/51",
    "52/52",
    "52/53",
    "52/56",
    "52/59",
    "52/60",
    "52/61",
    "52/62",
    "52/87",
    "52/89",
)
KESSELART: str | None = "waermepumpe"

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {}

NUR_BUS: tuple[str, ...] = ()
ENTITAETEN: list[dict] = []
