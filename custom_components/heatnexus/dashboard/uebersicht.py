"""Reiter „Übersicht“: Meldungen, Kennwerte und je Anlage Bild, Kernwerte, Thermostate, Tasten."""

from __future__ import annotations

from typing import Any

from . import auswahl
from .anlage import schaubild
from .anlagen import voller_name
from .karten import abschnitt, ansicht, kachel, meldungskarte, pfad_anlage


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


def _meldungen(anlagen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        meldungskarte(text, voller_name(anlage, teil), stoerung)
        for anlage in anlagen
        for teil in anlage["teile"]
        if (text := auswahl.klartext(teil)) and (stoerung := auswahl.stoerung(teil))
    ]


def _anlagenspalte(anlage: dict[str, Any], als_karte: bool) -> list[dict[str, Any]]:
    karten: list[dict[str, Any]] = []
    if bild := schaubild(anlage, als_karte, mit_liste=False):
        karten.append(bild)
    for teil in anlage["teile"]:
        karten += [kachel(e) for e in auswahl.kernwerte(teil)]
    for teil in anlage["teile"]:
        karten += [kachel(e) for e in auswahl.thermostate(teil)]
    for teil in anlage["teile"]:
        karten += [kachel(e) for e in auswahl.tasten(teil)]
    return abschnitt(anlage["name"] or "Anlage", karten, ziel=pfad_anlage(anlage))


def uebersicht(
    anlagen: list[dict[str, Any]], als_karte: bool, badges: list[dict[str, Any]]
) -> dict[str, Any]:
    """Übersichtsansicht mit Meldungen, je Anlage einem Abschnitt und Störungsbadges."""
    meldungen = _meldungen(anlagen)
    abschnitte = abschnitt("Meldungen", meldungen, stil="subtitle", spanne=3)
    if abschnitte:
        # Die Überschrift ist sichtbar, solange eine der Meldungen es ist.
        bedingungen = [b for karte in meldungen for b in karte["visibility"]]
        abschnitte[0]["cards"][0]["visibility"] = (
            bedingungen
            if len(bedingungen) == 1
            else [{"condition": "or", "conditions": bedingungen}]
        )
    for anlage in anlagen:
        abschnitte += _anlagenspalte(anlage, als_karte)
    return ansicht(
        "Übersicht", "uebersicht", abschnitte, badges=[*badges, *stoerungsbadges(anlagen)]
    )
