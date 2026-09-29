"""Kartenbausteine des Dashboards: Kachel, Zeiger, Überschrift, Abschnitt, Ansicht."""

from __future__ import annotations

from typing import Any

from ..const import DASHBOARD_URL
from ..helpers import mustername
from .muster import rueckfrage

# Bedienfelder direkt an der Kachel, je Plattform.
FEATURES: dict[str, list[dict[str, Any]]] = {
    "select": [{"type": "select-options"}],
    "number": [{"type": "numeric-input", "style": "buttons"}],
}


def adresse(pfad: str) -> str:
    """Pfad einer Ansicht innerhalb des Dashboards."""
    return f"/{DASHBOARD_URL}/{pfad}"


def pfad_anlage(anlage: dict[str, Any]) -> str:
    """Ansichtspfad einer Anlage."""
    return f"anlage-{anlage['id'][:8]}"


def pfad_teil(teil: dict[str, Any]) -> str:
    """Ansichtspfad eines Anlagenteils."""
    return f"teil-{teil['id'][:8]}"


def kachel(eintrag: dict[str, Any]) -> dict[str, Any]:
    """Passende Karte für eine Entität; Thermostat für Klima, sonst Kachel."""
    if eintrag["bereich"] == "climate":
        return {"type": "thermostat", "entity": eintrag["entity_id"]}
    karte: dict[str, Any] = {
        "type": "tile",
        "entity": eintrag["entity_id"],
        "name": eintrag["name"],
    }
    if eintrag["bereich"] in FEATURES:
        karte["features"] = FEATURES[eintrag["bereich"]]
    if (frage := rueckfrage(mustername(eintrag))) and (
        aktion := _schaltaktion(eintrag["bereich"], eintrag["entity_id"])
    ):
        # Nur das Symbol schaltet; ein Tippen auf die Kachel öffnet die Detailansicht.
        karte["icon_tap_action"] = {**aktion, "confirmation": {"text": frage}}
    return karte


def _schaltaktion(bereich: str, entity_id: str) -> dict[str, Any] | None:
    if bereich == "switch":
        return {"action": "toggle"}
    if bereich == "button":
        return {
            "action": "perform-action",
            "perform_action": "button.press",
            "target": {"entity_id": entity_id},
        }
    return None


def zeigerinstrument(eintrag: dict[str, Any], skala: dict[str, Any]) -> dict[str, Any]:
    """Zeigerinstrument mit Nadel und der Skala des Baureihenmoduls."""
    return {
        "type": "gauge",
        "entity": eintrag["entity_id"],
        "name": eintrag["name"],
        "needle": True,
        **skala,
    }


def ueberschrift(titel: str, stil: str = "title", ziel: str | None = None) -> dict[str, Any]:
    """Überschrift; mit Ziel führt ein Tippen auf diese Ansicht."""
    karte: dict[str, Any] = {"type": "heading", "heading": titel, "heading_style": stil}
    if ziel:
        karte["tap_action"] = {"action": "navigate", "navigation_path": adresse(ziel)}
    return karte


def abschnitt(
    titel: str,
    karten: list[dict[str, Any]],
    stil: str = "title",
    ziel: str | None = None,
    spanne: int = 0,
) -> list[dict[str, Any]]:
    """Ein Abschnitt mit Überschrift – oder keiner, wenn nichts drin ist."""
    if not karten:
        return []
    grid: dict[str, Any] = {"type": "grid", "cards": [ueberschrift(titel, stil, ziel), *karten]}
    if spanne > 1:
        grid["column_span"] = spanne
    return [grid]


def meldungskarte(
    klartext: dict[str, Any], titel: str, stoerung: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Je Störung Art, Code, Text und Abhilfe; mit Störungssensor nur, solange eine anliegt."""
    entitaet = klartext["entity_id"]
    inhalt = (
        f"{{% set m = state_attr('{entitaet}', 'meldungen') %}}"
        "{% if m %}{% for e in m %}**{{ e.kind }} {{ e.code }}: {{ e.text }}**"
        "{% if e.info %}  \n{{ e.info }}{% endif %}\n\n{% endfor %}"
        f"{{% else %}}{{{{ states('{entitaet}') }}}}{{% endif %}}"
    )
    karte: dict[str, Any] = {"type": "markdown", "title": titel, "content": inhalt}
    if stoerung:
        karte["visibility"] = [
            {"condition": "state", "entity": stoerung["entity_id"], "state": "on"}
        ]
    return karte


def ansicht(
    titel: str,
    pfad: str,
    abschnitte: list[dict[str, Any]],
    badges: list[dict[str, Any]] | None = None,
    zurueck: str | None = None,
) -> dict[str, Any]:
    """Eine Ansicht ohne Symbol: Home Assistant zeigt dann den Titel im Reiter."""
    ergebnis: dict[str, Any] = {
        "title": titel,
        "path": pfad,
        "type": "sections",
        "max_columns": 3,
        "sections": abschnitte,
    }
    if badges:
        ergebnis["badges"] = badges
    if zurueck:
        ergebnis["subview"] = True
        ergebnis["back_path"] = adresse(zurueck)
    return ergebnis
