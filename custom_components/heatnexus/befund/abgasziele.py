"""Welche Kessel einen Abgaswächter bekommen; aus den Beschreibungen der Erkennung."""

from __future__ import annotations

from dataclasses import dataclass

from .pflege import LOGWIN_KLASSE
from .pflegeziele import praefix

ABGAS = "/0/11/0"
BRENNSTOFF_PUROWIN = "/38/127/0"
# Gas-Brennwertgeräte kondensieren; ihre Abgastemperatur sagt nichts über Belag am Tauscher.
FUNKTIONSTYPEN = (9, 25, 10)


@dataclass(frozen=True)
class AbgasZiel:
    """Ein Kessel mit Abgasfühler; `bezug_art` ist die Pflege, nach der der Bezug neu beginnt."""

    prefix: str
    device_id: str
    fct_type: int
    logwin: bool
    bezug_art: str


def ziele(beschreibungen: list[dict], geraeteklasse: dict[str, str]) -> list[AbgasZiel]:
    """BioWIN und PuroWIN nach Funktionstyp, LogWIN nach Geräteklasse; geordnet nach Adresse."""
    gefunden: dict[str, AbgasZiel] = {}
    for b in beschreibungen:
        oid, fct, device_id = b.get("oid") or "", b.get("fct_type"), b.get("device_id")
        prefix = praefix(oid)
        if fct not in FUNKTIONSTYPEN or not device_id or not prefix or oid != prefix + ABGAS:
            continue
        logwin = fct == 10
        if logwin and geraeteklasse.get(prefix.split("/")[2]) != LOGWIN_KLASSE:
            continue
        art = "jahresreinigung" if logwin else "hauptreinigung"
        gefunden.setdefault(prefix, AbgasZiel(prefix, device_id, fct, logwin, art))
    return [gefunden[p] for p in sorted(gefunden)]
