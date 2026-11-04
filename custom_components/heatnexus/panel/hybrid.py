"""Der Hybridmanager: Karte „Hybridmanager“ in der Steuerung, Diagramme im Verlauf.

Nur an Anlagen mit Hybridmanager (fctType 26); sonst `None`.
"""

from __future__ import annotations

from typing import Any

from ..schema.werte import ART_JE_FCT, kesselart_des_teils
from .suche import erster

HYBRIDMANAGER = 26
# Tage, die das Balkendiagramm der Wärmemengen zurückblickt.
TAGE_WAERME = 14
# Stunden der Verlaufsdiagramme.
STUNDEN_VERLAUF = 48
TARIFE = 5


def rolle(teil: dict[str, Any]) -> str | None:
    """Hybridmanager, Wärmepumpe, Kessel – oder nichts davon."""
    try:
        fct = int(teil.get("fct_type"))
    except (TypeError, ValueError):
        return None
    if fct == HYBRIDMANAGER:
        return "hybrid"
    if ART_JE_FCT.get(fct) != "kessel":
        return None
    return "waermepumpe" if kesselart_des_teils(teil) == "waermepumpe" else "kessel"


def _entitaeten_je_rolle(anlage: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    je_rolle: dict[str, list[dict[str, Any]]] = {"hybrid": [], "waermepumpe": [], "kessel": []}
    for teil in anlage["teile"]:
        if art := rolle(teil):
            je_rolle[art].extend(teil["entitaeten"])
    return je_rolle


def _kennung(entitaeten: list[dict[str, Any]], muster: str) -> str | None:
    treffer = erster(entitaeten, muster)
    return treffer["entity_id"] if treffer else None


def _liste(*kennungen: str | None) -> list[str]:
    return [k for k in kennungen if k]


def _karte(hybrid: list[dict[str, Any]], wp: list[dict[str, Any]]) -> dict[str, Any]:
    """Pelletpreis, Stromtarife und die Eingaben des Kostenvergleichs.

    Gerechnet wird im Browser, damit ein geänderter Preis sofort den neuen
    Grenz-COP zeigt. Alle Werte tragen einen Namen aus der Geräte-Datenbank.
    """
    tarife = [
        {"nummer": n, "entity": kennung}
        for n in range(1, TARIFE + 1)
        if (kennung := _kennung(hybrid, rf"^tarif {n}$"))
    ]
    return {
        "kosten": _kennung(hybrid, r"^kosten pellets$"),
        "heizwert": _kennung(hybrid, r"^wärmemenge pellets"),
        "wirkungsgrad": _kennung(hybrid, r"^wirkungsgrad pelletskessel$"),
        "tarife": tarife,
        "cop": _kennung(wp, r"^cop aktuell$"),
        "cop_heute": _kennung(wp, r"^ø cop heizen heute$"),
        "sg_ready": _kennung(hybrid, r"^sg ready$"),
        "sg_status": _kennung(hybrid, r"^sg ready status$"),
    }


def _verlauf(
    hybrid: list[dict[str, Any]], wp: list[dict[str, Any]], kessel: list[dict[str, Any]]
) -> list[tuple[str, list[str]]]:
    return [
        (
            "Temperaturen",
            _liste(
                _kennung(hybrid, r"au(ß|ss)entemperatur"),
                _kennung(hybrid, r"^puffertemperatur$"),
                _kennung(wp, r"^vorlauftemperatur$"),
                _kennung(kessel, r"kesseltemperatur ist"),
            ),
        ),
        (
            "Wer heizt",
            _liste(_kennung(wp, r"^aktuelle leistung$"), _kennung(kessel, r"kesselleistung")),
        ),
        (
            "Leistungszahl",
            _liste(_kennung(wp, r"^cop aktuell$"), _kennung(wp, r"^ø cop heizen heute$")),
        ),
    ]


def _diagramme(
    hybrid: list[dict[str, Any]], wp: list[dict[str, Any]], kessel: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Die Diagramme für den Reiter „Verlauf“ als Karten-Konfiguration von Home Assistant."""
    karten = [
        {
            "titel": titel,
            "karte": {"type": "history-graph", "hours_to_show": STUNDEN_VERLAUF, "entities": e},
        }
        for titel, e in _verlauf(hybrid, wp, kessel)
        if e
    ]
    waerme = _liste(
        _kennung(wp, r"^wärmemenge heizen$"),
        _kennung(wp, r"^wärmemenge warmwasser$"),
        _kennung(kessel, r"^wärmemengenzähler$"),
    )
    if waerme:
        karten.append(
            {
                "titel": "Wärmemenge je Tag",
                "karte": {
                    "type": "statistics-graph",
                    "chart_type": "bar",
                    "period": "day",
                    "days_to_show": TAGE_WAERME,
                    "stat_types": ["change"],
                    "entities": waerme,
                },
            }
        )
    return karten


def hybrid(anlage: dict[str, Any]) -> dict[str, Any] | None:
    """Karte und Diagramme des Hybridmanagers; ohne Hybridmanager nichts."""
    je_rolle = _entitaeten_je_rolle(anlage)
    if not any(rolle(teil) == "hybrid" for teil in anlage["teile"]):
        return None
    return {
        "karte": _karte(je_rolle["hybrid"], je_rolle["waermepumpe"]),
        "diagramme": _diagramme(je_rolle["hybrid"], je_rolle["waermepumpe"], je_rolle["kessel"]),
    }
