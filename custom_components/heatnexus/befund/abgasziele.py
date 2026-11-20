"""Welche Kessel einen Abgaswächter bekommen; aus den Beschreibungen der Erkennung."""

from __future__ import annotations

from dataclasses import dataclass

from ..geraete import BEFUND
from .pflegeziele import praefix

ABGAS = "/0/11/0"
BRENNSTOFF_PUROWIN = "/38/127/0"
# Je Funktionstyp der Abgaswächter: Bezugspflege, Geräteklassen, Auswertung ohne Leistung.
ABGASWAECHTER: dict[int, dict] = {fct: b["abgas"] for fct, b in BEFUND.items() if b.get("abgas")}


@dataclass(frozen=True)
class AbgasZiel:
    """Ein Kessel mit Abgasfühler; `bezug_art` ist die Pflege, nach der der Bezug neu beginnt.

    `ohne_leistung`: Die Steuerung meldet keine Leistung; die Auswertung kommt ohne sie aus.
    """

    prefix: str
    device_id: str
    fct_type: int
    ohne_leistung: bool
    bezug_art: str


def ziele(beschreibungen: list[dict], geraeteklasse: dict[str, str]) -> list[AbgasZiel]:
    """Nach Funktionstyp, wo der Eintrag es verlangt nach Geräteklasse; geordnet nach Adresse."""
    gefunden: dict[str, AbgasZiel] = {}
    for b in beschreibungen:
        oid, fct, device_id = b.get("oid") or "", b.get("fct_type"), b.get("device_id")
        prefix = praefix(oid)
        eintrag = ABGASWAECHTER.get(fct)
        if eintrag is None or not device_id or not prefix or oid != prefix + ABGAS:
            continue
        klassen = eintrag.get("klassen")
        if klassen and geraeteklasse.get(prefix.split("/")[2]) not in klassen:
            continue
        ohne_leistung = bool(eintrag.get("ohne_leistung"))
        ziel = AbgasZiel(prefix, device_id, fct, ohne_leistung, eintrag["bezug"])
        gefunden.setdefault(prefix, ziel)
    return [gefunden[p] for p in sorted(gefunden)]
