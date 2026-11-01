"""Der Reiter „Hybrid“: wie der Hybridmanager zwischen Kessel und Wärmepumpe wählt.

Nur an Anlagen mit Hybridmanager (fctType 26); sonst bleibt der Reiter leer.
"""

from __future__ import annotations

from typing import Any

from .hauptsystem import erzeuger
from .muster import HYBRID_GRENZEN, HYBRID_ZUSTAND
from .suche import erster, zeilen_aus

# Tage, die das Balkendiagramm der Wärmemengen zurückblickt.
TAGE_WAERME = 14
# Stunden der Verlaufsdiagramme.
STUNDEN_VERLAUF = 48
TARIFE = 5


def _kennung(entitaeten: list[dict[str, Any]], muster: str) -> str | None:
    treffer = erster(entitaeten, muster)
    return treffer["entity_id"] if treffer else None


def _liste(*kennungen: str | None) -> list[str]:
    return [k for k in kennungen if k]


def _wirtschaftlichkeit(hybrid: list[dict[str, Any]], wp: list[dict[str, Any]]) -> dict[str, Any]:
    """Die Eingaben für den Vergleich Pellets gegen Strom – gerechnet wird im Browser.

    Alle Werte tragen einen Namen aus der Geräte-Datenbank. Wärmepreis und
    Grenz-Leistungszahl entstehen aus ihnen.
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
        "zeitprogramm": _kennung(hybrid, r"^zeitprogramm stromtarife$"),
        "cop": _kennung(wp, r"^cop aktuell$"),
        "cop_heute": _kennung(wp, r"^ø cop heizen heute$"),
    }


def _diagramme(
    hybrid: list[dict[str, Any]], wp: list[dict[str, Any]], kessel: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Die Diagramme des Reiters als Karten-Konfiguration von Home Assistant."""
    verlauf = [
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
    karten = [
        {
            "titel": titel,
            "karte": {"type": "history-graph", "hours_to_show": STUNDEN_VERLAUF, "entities": e},
        }
        for titel, e in verlauf
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
    """Was der Reiter „Hybrid“ zeigt; ohne Hybridmanager nichts."""
    je_rolle = erzeuger(anlage)
    if not je_rolle["hybrid"]:
        return None
    hybrid_e = [e for t in je_rolle["hybrid"] for e in t["entitaeten"]]
    wp_e = [e for t in je_rolle["waermepumpe"] for e in t["entitaeten"]]
    kessel_e = [e for t in je_rolle["kessel"] for e in t["entitaeten"]]
    return {
        "zustand": zeilen_aus(hybrid_e, HYBRID_ZUSTAND),
        "grenzen": zeilen_aus(hybrid_e, HYBRID_GRENZEN),
        "wirtschaftlichkeit": _wirtschaftlichkeit(hybrid_e, wp_e),
        "diagramme": _diagramme(hybrid_e, wp_e, kessel_e),
    }
