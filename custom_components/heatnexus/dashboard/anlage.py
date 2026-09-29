"""Arbeitsseite einer Anlage: je Anlagenteil Zeiger, Zustand, Bedienung und Details."""

from __future__ import annotations

from typing import Any

from ..const import KARTE_ELEMENT
from ..schema import anlagenschema
from . import auswahl
from .anlagen import trifft
from .karten import (
    abschnitt,
    ansicht,
    kachel,
    pfad_anlage,
    pfad_teil,
    ueberschrift,
    zeigerinstrument,
)
from .muster import ZUSTAND, ZUSTAND_SCHLUESSEL


def zustandswerte(anlage: dict[str, Any]) -> list[dict[str, Any]]:
    """Meldung, Betriebsphase, Außentemperatur – der Zustand in Kurzform."""
    return [
        e
        for teil in anlage["teile"]
        for e in teil["entitaeten"]
        # Einsteller bleiben draußen: Ein Grenzwert der Serviceebene heißt
        # mitunter wie der Messwert, den er begrenzt.
        if e["hat_wert"] and e.get("kategorie") is None and trifft(e, ZUSTAND, *ZUSTAND_SCHLUESSEL)
    ]


def schaubild(anlage: dict[str, Any], als_karte: bool, mit_liste: bool) -> dict[str, Any] | None:
    """Schaubild als eigene Karte (bewegt, im Editor offen) oder als feste Zeichnung."""
    if als_karte:
        karte: dict[str, Any] = {
            "type": f"custom:{KARTE_ELEMENT}",
            "anlage": anlage["id"],
            "farbsatz": "auto",
            "schrift": "normal",
            "animation": True,
            "liste": "rechts",
            "titel_bild": "",
            "titel_liste": "Zustand",
            # Volle Breite: Bild und Werteliste stehen nebeneinander.
            "grid_options": {"columns": 24, "rows": "auto"},
        }
        if mit_liste and (werte := zustandswerte(anlage)):
            karte["zusatzwerte"] = [e["entity_id"] for e in werte]
        return karte
    return anlagenschema(anlage["teile"], modulpumpe=anlage.get("modulpumpe", False))


def teilabschnitt(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Abschnitt eines Anlagenteils: Thermostate, Zeiger, Zustand und Bedienung."""
    zeiger = auswahl.zeigerinstrumente(teil)
    gezeigt = {e["entity_id"] for e, _ in zeiger}
    zustand = [e for e in auswahl.messwerte(teil) if e["entity_id"] not in gezeigt]
    bedienung = auswahl.bedienung(teil)
    karten: list[dict[str, Any]] = [
        *(kachel(e) for e in auswahl.thermostate(teil)),
        *(zeigerinstrument(e, skala) for e, skala in zeiger),
    ]
    if zustand:
        karten += [ueberschrift("Zustand", "subtitle"), *(kachel(e) for e in zustand)]
    if bedienung:
        karten += [ueberschrift("Bedienung", "subtitle"), *(kachel(e) for e in bedienung)]
    return abschnitt(teil["name"], karten, ziel=pfad_teil(teil))


def arbeitsseite(anlage: dict[str, Any], als_karte: bool, mit_schaubild: bool) -> dict[str, Any]:
    """Ansicht einer Anlage; mit Schaubild steht es als erster Abschnitt oben."""
    abschnitte: list[dict[str, Any]] = []
    if mit_schaubild and (bild := schaubild(anlage, als_karte, mit_liste=True)):
        abschnitte += abschnitt(anlage["name"] or "Anlage", [bild], spanne=2)
        if not als_karte:
            werte = zustandswerte(anlage)
            abschnitte += abschnitt("Zustand", [kachel(e) for e in werte], stil="subtitle")
    for teil in anlage["teile"]:
        abschnitte += teilabschnitt(teil)
    return ansicht(anlage["name"] or "Anlage", pfad_anlage(anlage), abschnitte)
