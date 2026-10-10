"""Reiter „Übersicht“: Meldungen, dann je Anlage Schaubild und die Karten ihrer Teile.

Der Rahmen steht in der gemeinsamen Sprache, jeder Anlagenabschnitt in der Sprache seiner Anlage.
"""

from __future__ import annotations

from typing import Any

from ..texte import LOVELACE_FELDER, Woerterbuch, uebersetze_baum
from .anlage import meldungsabschnitt, schaubild
from .kacheln import VOLLE_BREITE, anlagenkarten
from .karten import ansicht, pfad_anlage, ueberschrift

# Beschriftungen der eigenen Karten; sie gehen wie die Lovelace-Felder durch das Wörterbuch.
KARTENFELDER = LOVELACE_FELDER | {
    "ueberschrift",
    "gross_name",
    "titel",
    "name_oben",
    "name_mitte",
    "name_unten",
    "an",
    "aus",
}


def _in_sprache(daten: Any, buch: Woerterbuch | None) -> Any:
    return daten if buch is None else uebersetze_baum(daten, buch, KARTENFELDER)


def _bild(anlage: dict[str, Any], als_karte: bool) -> dict[str, Any] | None:
    """Schaubild ohne Werteliste, so breit wie der Abschnitt."""
    bild = schaubild(anlage, als_karte, mit_liste=False)
    if bild and als_karte:
        bild = {**bild, "liste": "aus", "grid_options": {**VOLLE_BREITE, "rows": "auto"}}
    return bild


def anlagenabschnitt(anlage: dict[str, Any], als_karte: bool) -> list[dict[str, Any]]:
    """Der Abschnitt einer Anlage: Überschrift, Schaubild, Karten ihrer Teile."""
    kopf = {
        **ueberschrift(anlage["name"] or "Anlage", ziel=pfad_anlage(anlage)),
        "icon": "mdi:fire",
    }
    bild = _bild(anlage, als_karte)
    karten = [*([bild] if bild else []), *anlagenkarten(anlage)]
    return [{"type": "grid", "cards": [kopf, *karten]}] if karten else []


def uebersicht(
    anlagen: list[dict[str, Any]],
    als_karte: bool,
    badges: list[dict[str, Any]],
    gemeinsam: Woerterbuch | None = None,
    buecher: list[Woerterbuch] | None = None,
) -> dict[str, Any]:
    """Übersichtsansicht; ohne Wörterbücher bleiben alle Texte deutsch."""
    rahmen = _in_sprache(
        ansicht("Übersicht", "uebersicht", meldungsabschnitt(anlagen), badges=badges), gemeinsam
    )
    sprachen = buecher or [None] * len(anlagen)
    abschnitte = [
        abschnitt
        for anlage, buch in zip(anlagen, sprachen, strict=True)
        for abschnitt in _in_sprache(anlagenabschnitt(anlage, als_karte), buch)
    ]
    return {**rahmen, "sections": [*rahmen["sections"], *abschnitte]}
