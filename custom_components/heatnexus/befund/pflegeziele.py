"""Welche Pflege an welchem Gerät entsteht; aus den Beschreibungen der Erkennung."""

from __future__ import annotations

from dataclasses import dataclass

from .pflege import KALENDERPFLEGE, PFLEGE, Pflege


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


def _kalender(beschreibungen: list[dict], geraeteklasse: dict[str, str]) -> list[Ziel]:
    geraete: dict[str, tuple[str, tuple[Pflege, ...]]] = {}
    for b in beschreibungen:
        prefix = praefix(b.get("oid") or "")
        if not b.get("device_id") or prefix is None:
            continue
        klasse = geraeteklasse.get(prefix.split("/")[2])
        if pflegen := KALENDERPFLEGE.get((b.get("fct_type"), klasse)):
            geraete.setdefault(prefix, (b["device_id"], pflegen))
    return [Ziel(p, d, pflege) for p, (d, pflegen) in geraete.items() for pflege in pflegen]


def ziele(beschreibungen: list[dict], geraeteklasse: dict[str, str]) -> list[Ziel]:
    """Zählerpflege nach Funktionstyp, Kalenderpflege nach Geräteklasse; geordnet nach Adresse."""
    gefunden = _zaehler(beschreibungen) + _kalender(beschreibungen, geraeteklasse)
    return sorted(gefunden, key=lambda z: (z.prefix, z.pflege.adresse or "", z.pflege.art))
