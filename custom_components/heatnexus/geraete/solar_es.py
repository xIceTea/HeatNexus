"""Solar ES (fctType 13).

Der Name steht wörtlich in `MapToInstance.xml` des Herstellers, dazu die
Ebenen „Kollektor 1/2" und „Speicher 1–4".
"""

from __future__ import annotations

FCT_TYPE = 13
MODELL = "Solar ES"
RANG = 44
SYMBOL = "mdi:solar-power-variant"
SCHAUBILD = "solar"

EXTRA_OIDS: tuple[str, ...] = ()
KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {}

NUR_BUS: tuple[str, ...] = ()
ENTITAETEN: list[dict] = []
