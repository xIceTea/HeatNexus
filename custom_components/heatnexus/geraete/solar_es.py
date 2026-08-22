"""Solar ES (fctType 13).

Nur im Schaubild belegt: Der Hersteller führt die Funktion dort als Solarteil,
einen Modellnamen und einen Rang nennt er nicht.
"""

from __future__ import annotations

FCT_TYPE = 13
MODELL = None
RANG = None
SYMBOL = None
SCHAUBILD = "solar"

EXTRA_OIDS: tuple[str, ...] = ()
KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {}

NUR_BUS: tuple[str, ...] = ()
ENTITAETEN: list[dict] = []
