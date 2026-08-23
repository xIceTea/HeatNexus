"""IO5500 Energiezählkreise (fctType 12).

Der Name steht wörtlich in `MapToInstance.xml` des Herstellers. Wo die Funktion
im Weg der Wärme sitzt, sagt er nicht — sie steht deshalb hinten.
"""

from __future__ import annotations

FCT_TYPE = 12
MODELL = "IO5500 (Energiezählkreise)"
RANG = None
SYMBOL = "mdi:counter"
SCHAUBILD = None

KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {}

EXTRA_OIDS: tuple[str, ...] = ()
NUR_BUS: tuple[str, ...] = ()
ENTITAETEN: list[dict] = []
