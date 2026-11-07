"""Welche Pflege an welchem Gerät entsteht; aus den Beschreibungen der Erkennung."""

from __future__ import annotations

from dataclasses import dataclass

from .pflege import LOGWIN, LOGWIN_KLASSE, PFLEGE, Pflege


@dataclass(frozen=True)
class Ziel:
    """Eine Pflege an einem Gerät; `max_feld` ist das `max` des Datenpunkts."""

    prefix: str
    device_id: str
    pflege: Pflege
    max_feld: object = None


def praefix(oid: str) -> str | None:
    """`/1/<Knoten>/<Funktion>` aus einer vollen Adresse; Sensoren tragen keinen eigenen Präfix."""
    teile = oid.strip("/").split("/")
    return "/" + "/".join(teile[:3]) if len(teile) >= 3 else None


def _zaehler(beschreibungen: list[dict]) -> list[Ziel]:
    gefunden = []
    for b in beschreibungen:
        oid, device_id = b.get("oid") or "", b.get("device_id")
        prefix = praefix(oid)
        for pflege in PFLEGE.get(b.get("fct_type"), ()):
            if device_id and prefix and pflege.adresse and oid == f"{prefix}{pflege.adresse}":
                gefunden.append(Ziel(prefix, device_id, pflege, b.get("max")))
    return gefunden


def _logwin(beschreibungen: list[dict], geraeteklasse: dict[str, str]) -> list[Ziel]:
    geraete: dict[str, str] = {}
    for b in beschreibungen:
        prefix = praefix(b.get("oid") or "")
        if b.get("fct_type") != 10 or not b.get("device_id") or prefix is None:
            continue
        if geraeteklasse.get(prefix.split("/")[2]) == LOGWIN_KLASSE:
            geraete.setdefault(prefix, b["device_id"])
    return [Ziel(p, device_id, pflege) for p, device_id in geraete.items() for pflege in LOGWIN]


def ziele(beschreibungen: list[dict], geraeteklasse: dict[str, str]) -> list[Ziel]:
    """Zählerpflege nach Funktionstyp, Kalenderpflege am LogWIN; geordnet nach Adresse."""
    gefunden = _zaehler(beschreibungen) + _logwin(beschreibungen, geraeteklasse)
    return sorted(gefunden, key=lambda z: (z.prefix, z.pflege.adresse or "", z.pflege.art))
