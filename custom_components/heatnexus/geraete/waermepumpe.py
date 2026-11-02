"""Wärmepumpe (fctType 7).

Ohne gepflegte Datenpunkttabelle: Die Datenpunkte kommen aus den Menü-Ebenen
der Anlage, dazu Leistung und Betriebsphase sowie Wärmemengen, Betriebsstunden, Starts
und COP aus Gruppe 52.
"""

from __future__ import annotations

from . import statuszeilen

FCT_TYPE = 7
MODELL = "Wärmepumpe"
RANG = 10
SYMBOL = "mdi:heat-pump"
SCHAUBILD = "kessel"

# Abgeglichen mit der App an einer BioWIN Hybrid; Gruppe 52 steht in keinem Menü der Steuerung.
STATUSZEILEN = statuszeilen.KESSEL
EXTRA_OIDS: tuple[str, ...] = (
    "50/6",
    "50/26",
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

# Zählerstände, die die Steuerung ohne Schreibschutz meldet: Betriebsstunden,
# Starts und Wärmemengen, je gesamt und heute. Als Eingabefeld ließen sie sich
# aus Home Assistant überschreiben und fehlten in der Langzeitstatistik.
NUR_ANZEIGE: tuple[str, ...] = (
    "52/50",  # Betriebsstunden Heizen
    "52/51",  # Betriebsstunden Heizen heute
    "52/52",  # Betriebsstunden Warmwasser
    "52/53",  # Betriebsstunden Warmwasser heute
    "52/56",  # Anzahl Starts
    "52/59",  # Wärmemenge Heizen
    "52/60",  # Wärmemenge Heizen heute
    "52/61",  # Wärmemenge Warmwasser
    "52/62",  # Wärmemenge Warmwasser heute
)
ENTITAETEN: list[dict] = []
