"""Automatik- und Zusatzkessel (fctType 10).

Die Tabelle führt nur, was Windhager auf die Titelseite legt, in keiner
Bedienebene aber nennt. Alles Übrige kommt aus den Menü-Ebenen der Anlage.
"""

from __future__ import annotations

FCT_TYPE = 10
MODELL = "Automatik-/Zusatzkessel"
RANG = 14
SYMBOL = "mdi:fire"
SCHAUBILD = "kessel"

EXTRA_OIDS: tuple[str, ...] = ()
KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {}

NUR_BUS: tuple[str, ...] = ()
# `0/7` und `2/59` stehen in der Übersichtsebene des Herstellers, in keiner
# Bedienebene aber drin. Ohne Eintrag hier blieben beide abgeschaltet, und
# ohne Kesseltemperatur fällt der Kessel aus dem Schaubild.
ENTITAETEN: list[dict] = [
    {"oid": "/0/7/0", "name": "Kesseltemperatur Ist", "platform": "temperature"},
    {"oid": "/2/59/0", "name": "Betriebsart", "platform": "enum_sensor", "enum": "2/59"},
]
