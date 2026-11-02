"""Abschnitt „Regelung“ im Systemstatus: Hybridmanager, SG Ready und Automatik.

Erst ab zwei Erzeugern. Mit einem Erzeuger bleibt SG Ready bei den Zeilen der
Anlage, und die Karte sieht aus wie ohne diesen Abschnitt.
"""

from __future__ import annotations

from typing import Any

from ..dashboard.anlagen import erzeuger_von
from ..geraete.statuszeilen import GEMEINSAM
from .hybrid import rolle
from .suche import erster, zeilen_aus

# Woran die Zeile des Hybridmanagers erkennt, welcher Erzeuger gerade liefert.
LEISTUNG = r"kesselleistung|^aktuelle leistung$"


def _kennung(entitaeten: list[dict[str, Any]], muster: str) -> str | None:
    treffer = erster(entitaeten, muster)
    return treffer["entity_id"] if treffer else None


def _hybridmanager(anlage: dict[str, Any], erzeuger: list[dict[str, Any]]) -> dict | None:
    """Betriebsart des Hybridmanagers und die Leistung jedes Erzeugers."""
    teil = next((t for t in anlage["teile"] if rolle(t) == "hybrid"), None)
    if teil is None:
        return None
    lieferanten = [
        {"name": e["name"], "entity": leistung}
        for e in erzeuger
        if (leistung := _kennung(e["entitaeten"], LEISTUNG))
    ]
    return {
        "betriebsart": _kennung(teil["entitaeten"], r"^betriebsart$"),
        "lieferanten": lieferanten,
    }


def regelung(anlage: dict[str, Any]) -> dict[str, Any] | None:
    """Was unter den Erzeugern steht; die Automatik trägt erst das Panel ein."""
    erzeuger = erzeuger_von(anlage["teile"])
    if len(erzeuger) < 2:
        return None
    alle = [e for teil in anlage["teile"] for e in teil["entitaeten"]]
    vorlage = tuple(
        (z.muster, z.titel, z.symbol, z.schluessel) for z in GEMEINSAM if z.panel and z.regelung
    )
    return {
        "hybrid": _hybridmanager(anlage, erzeuger),
        "zeilen": zeilen_aus(alle, vorlage),
        "automatik": None,
    }
