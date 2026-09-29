"""Reiter „Übersicht“: Meldungen, Kennwerte und je Anlage Bild, Kernwerte, Thermostate, Tasten."""

from __future__ import annotations

from typing import Any

from ..helpers import mustername
from ..schema import passt
from . import auswahl
from .anlage import meldungsabschnitt, schaubild
from .karten import abschnitt, ansicht, kachel, pfad_anlage
from .muster import ABFRAGETASTE


def stoerungsbadges(anlagen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Eine Badge je Störungssensor, sichtbar nur, solange die Störung anliegt."""
    return [
        {
            "type": "entity",
            "entity": sensor["entity_id"],
            "visibility": [{"condition": "state", "entity": sensor["entity_id"], "state": "on"}],
        }
        for anlage in anlagen
        for teil in anlage["teile"]
        if (sensor := auswahl.stoerung(teil))
    ]


def _kernwerte(anlage: dict[str, Any]) -> list[dict[str, Any]]:
    """Kernwerte aller Teile; bei mehreren Teilen mit dem Teilnamen davor."""
    je_teil = [(teil, werte) for teil in anlage["teile"] if (werte := auswahl.kernwerte(teil))]
    if len(je_teil) < 2:
        return [e for _, werte in je_teil for e in werte]
    return [
        {**e, "name": f"{teil['name']} · {e['name']}"} for teil, werte in je_teil for e in werte
    ]


def _tasten(anlage: dict[str, Any]) -> list[dict[str, Any]]:
    """Die Tasten aller Teile; „Werte jetzt abfragen“ nur die des ersten Teils."""
    tasten = [e for teil in anlage["teile"] for e in auswahl.tasten(teil)]
    abfrage = [e for e in tasten if passt(mustername(e), ABFRAGETASTE)]
    return [e for e in tasten if e not in abfrage[1:]]


def _anlagenspalte(anlage: dict[str, Any], als_karte: bool) -> list[dict[str, Any]]:
    karten: list[dict[str, Any]] = []
    if bild := schaubild(anlage, als_karte, mit_liste=False):
        karten.append(bild)
    karten += [kachel(e) for e in _kernwerte(anlage)]
    for teil in anlage["teile"]:
        karten += [kachel(e) for e in auswahl.thermostate(teil)]
    karten += [kachel(e) for e in _tasten(anlage)]
    return abschnitt(anlage["name"] or "Anlage", karten, ziel=pfad_anlage(anlage))


def uebersicht(
    anlagen: list[dict[str, Any]], als_karte: bool, badges: list[dict[str, Any]]
) -> dict[str, Any]:
    """Übersichtsansicht mit Meldungen, je Anlage einem Abschnitt und Störungsbadges."""
    abschnitte = meldungsabschnitt(anlagen)
    for anlage in anlagen:
        abschnitte += _anlagenspalte(anlage, als_karte)
    return ansicht(
        "Übersicht", "uebersicht", abschnitte, badges=[*badges, *stoerungsbadges(anlagen)]
    )
