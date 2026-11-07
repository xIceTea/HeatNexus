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


def _knoten(prefix: str) -> str | None:
    teile = prefix.strip("/").split("/")
    return teile[1] if len(teile) >= 2 else None


def _zaehler(beschreibungen: list[dict]) -> list[Ziel]:
    gefunden = []
    for b in beschreibungen:
        oid, prefix, device_id = b.get("oid") or "", b.get("prefix") or "", b.get("device_id")
        for pflege in PFLEGE.get(b.get("fct_type"), ()):
            if device_id and pflege.adresse and oid == f"{prefix}{pflege.adresse}":
                gefunden.append(Ziel(prefix, device_id, pflege, b.get("max")))
    return gefunden


def _logwin(beschreibungen: list[dict], geraeteklasse: dict[str, str]) -> list[Ziel]:
    geraete: dict[str, str] = {}
    for b in beschreibungen:
        prefix = b.get("prefix") or ""
        if b.get("fct_type") != 10 or not b.get("device_id"):
            continue
        if geraeteklasse.get(_knoten(prefix) or "") == LOGWIN_KLASSE:
            geraete.setdefault(prefix, b["device_id"])
    return [Ziel(p, device_id, pflege) for p, device_id in geraete.items() for pflege in LOGWIN]


def ziele(beschreibungen: list[dict], geraeteklasse: dict[str, str]) -> list[Ziel]:
    """Zählerpflege nach Funktionstyp, Kalenderpflege am LogWIN; geordnet nach Adresse."""
    gefunden = _zaehler(beschreibungen) + _logwin(beschreibungen, geraeteklasse)
    return sorted(gefunden, key=lambda z: (z.prefix, z.pflege.adresse or "", z.pflege.art))
