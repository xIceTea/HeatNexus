"""Entitäten einer Anlage nach Muster oder kanonischem Schlüssel finden."""

from __future__ import annotations

import re
from typing import Any

from ..helpers import mustername
from ..schema import passt as _passt
from ..schema import traegt as _traegt
from ..schema import treffer as _treffer
from .muster import (
    Zeile,
)


def erster(
    entitaeten: list[dict[str, Any]], muster: str, *schluessel: str
) -> dict[str, Any] | None:
    """Erste passende Entität; eine mit Wert hat Vorrang.

    Ein vorhandener Wert darf keine Bedingung sein: Beim ersten Aufbau ist die
    Anlage noch nicht fertig eingelesen. Was jetzt noch leer ist, bekommt
    trotzdem seine Zeile und füllt sich mit dem nächsten Abruf.

    Sind kanonische Schlüssel angegeben, zählen sie zuerst; das Muster bleibt
    der Rückfall (siehe `dashboard.anlagen.trifft`).
    """
    regex = re.compile(muster, re.IGNORECASE)
    treffer = _treffer(entitaeten, (regex,), *schluessel)
    if not treffer:
        return None
    return next((e for e in treffer if e.get("hat_wert")), treffer[0])


def zeilen_aus(
    entitaeten: list[dict[str, Any]], vorlage: tuple[Zeile, ...]
) -> list[dict[str, str]]:
    """Aus einer Mustervorlage die vorhandenen Entitäten als Zeilen."""
    zeilen = []
    for muster, beschriftung, symbol, schluessel in vorlage:
        if (treffer := erster(entitaeten, muster, *schluessel)) is not None:
            zeilen.append(
                {
                    "entity": treffer["entity_id"],
                    "titel": beschriftung,
                    "symbol": symbol,
                }
            )
    return zeilen


def eintrag_suchen(
    entitaeten: list[dict[str, Any]],
    muster: tuple,
    bereiche: tuple = (),
    *schluessel: str,
) -> dict[str, Any] | None:
    """Die erste passende Entität, optional auf Plattformen begrenzt.

    Sind kanonische Schlüssel angegeben, zählen sie zuerst; das Muster bleibt
    der Rückfall (siehe `schema.treffer`). Beide Durchläufe halten beim ersten
    Treffer an – die Liste einer Anlage wird oft durchsucht.
    """
    infrage = [e for e in entitaeten if e["bereich"] in bereiche] if bereiche else entitaeten
    return next((e for e in infrage if _traegt(e, schluessel)), None) or next(
        (e for e in infrage if _passt(mustername(e), muster)), None
    )


def kennung_suchen(
    entitaeten: list[dict[str, Any]],
    muster: tuple,
    bereiche: tuple = (),
    *schluessel: str,
) -> str | None:
    """Entity-ID der ersten passenden Entität."""
    treffer = eintrag_suchen(entitaeten, muster, bereiche, *schluessel)
    return treffer["entity_id"] if treffer else None
