"""Automatik- und Zusatzkessel (fctType 10).

Ohne kuratierte Tabelle: Alles kommt aus den Menü-Ebenen der Anlage. Die
Übersichtsebene des Herstellers hebt Kesseltemperatur und Betriebsart auf info.
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
NAMEN: dict[str, str] = {"0/7": "Kesseltemperatur Ist"}

NUR_BUS: tuple[str, ...] = ()
ENTITAETEN: list[dict] = []
