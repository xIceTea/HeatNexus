"""Reiter „Wartung“ und „Auswertung“, je Anlage gegliedert."""

from __future__ import annotations

from typing import Any

from .anlagen import skala, trifft, voller_name
from .karten import abschnitt, ansicht, kachel, ueberschrift
from .muster import (
    VERLAUF,
    VERLAUF_MAX,
    VERLAUF_SCHLUESSEL,
    WARTUNG_RESTLAUFZEIT,
    WARTUNG_RESTLAUFZEIT_SCHLUESSEL,
    WARTUNG_WEITERE,
    WARTUNG_WEITERE_SCHLUESSEL,
)


def _restlaufzeit(e: dict[str, Any]) -> dict[str, Any]:
    # Die Skala folgt dem Stand: Wartungsintervalle reichen von Dutzenden bis über tausend Stunden.
    return {
        "type": "gauge",
        "entity": e["entity_id"],
        "name": e["name"].replace("Laufzeit bis ", ""),
        "needle": True,
        "min": 0,
        "max": skala(e["wert"]),
        "severity": {"green": 20, "yellow": 5, "red": 0},
    }


def wartung(anlagen: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Restlaufzeiten, Zähler und Brennstoff je Anlagenteil."""
    abschnitte: list[dict[str, Any]] = []
    for anlage in anlagen:
        for teil in anlage["teile"]:
            werte = [e for e in teil["entitaeten"] if e["hat_wert"]]
            rest = [
                e
                for e in werte
                if trifft(e, WARTUNG_RESTLAUFZEIT, *WARTUNG_RESTLAUFZEIT_SCHLUESSEL)
            ]
            weitere = [e for e in werte if trifft(e, WARTUNG_WEITERE, *WARTUNG_WEITERE_SCHLUESSEL)]
            karten = [*(_restlaufzeit(e) for e in rest), *(kachel(e) for e in weitere)]
            abschnitte += abschnitt(voller_name(anlage, teil), karten)
    return ansicht("Wartung", "wartung", abschnitte) if abschnitte else None


def auswertung(anlagen: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Zählerzuwachs und Verläufe, je Anlage gegliedert."""
    abschnitte: list[dict[str, Any]] = []
    for anlage in anlagen:
        teil_abschnitte: list[dict[str, Any]] = []
        zaehler = [
            e
            for teil in anlage["teile"]
            for e in teil["entitaeten"]
            if e["state_class"] == "total_increasing"
        ]
        for zeitraum, beschriftung in (("day", "heute"), ("month", "dieser Monat")):
            karten = [
                {
                    "type": "statistic",
                    "entity": e["entity_id"],
                    "name": e["name"],
                    "stat_type": "change",
                    "period": {"calendar": {"period": zeitraum}},
                }
                for e in zaehler
            ]
            # „Zähler – heute“ steht als Satzmuster im Wörterbuch; die Anlage steht darüber.
            teil_abschnitte += abschnitt(f"Zähler – {beschriftung}", karten, stil="subtitle")
        for teil in anlage["teile"]:
            verlauf = [
                e
                for e in teil["entitaeten"]
                if e["hat_wert"]
                and e["bereich"] == "sensor"
                and trifft(e, VERLAUF, *VERLAUF_SCHLUESSEL)
            ]
            graph = {
                "type": "history-graph",
                "hours_to_show": 48,
                "entities": [
                    {"entity": e["entity_id"], "name": e["name"]} for e in verlauf[:VERLAUF_MAX]
                ],
            }
            teil_abschnitte += abschnitt(teil["name"], [graph] if verlauf else [])
        if teil_abschnitte and anlage["name"]:
            # Eine Überschrift über volle Breite trennt die Anlagen.
            teil_abschnitte.insert(
                0, {"type": "grid", "column_span": 3, "cards": [ueberschrift(anlage["name"])]}
            )
        abschnitte += teil_abschnitte
    return ansicht("Auswertung", "auswertung", abschnitte) if abschnitte else None
