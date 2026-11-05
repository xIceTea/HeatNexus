"""Die letzte Wettervorhersage je Wetter-Entität in einer eigenen Datei.

Sie wechselt stündlich und gehört deshalb nicht zu den Einstellungen. Nach einem Neustart
trägt sie die Automatik, bis der Wetterdienst wieder antwortet.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)
FASSUNG = 1
SCHLUESSEL = f"{DOMAIN}.automatik_prognose"

Prognosen = dict[tuple[str, str], tuple[datetime, list[dict[str, Any]]]]


def ablage(hass: HomeAssistant) -> Store:
    """Der Store der Vorhersagen."""
    return Store(hass, FASSUNG, SCHLUESSEL)


def abzug(prognosen: Prognosen) -> dict[str, Any]:
    """Die Vorhersagen als Inhalt der Ablage; eine leere Antwort hilft nach einem Neustart nicht."""
    return {
        "prognosen": [
            {"wetter": wetter, "art": art, "zeit": zeit.isoformat(), "daten": daten}
            for (wetter, art), (zeit, daten) in prognosen.items()
            if daten
        ]
    }


async def laden(store: Store) -> Prognosen:
    """Die abgelegten Vorhersagen; Unlesbares zählt nicht und verhindert keinen Start."""
    try:
        roh = await store.async_load()
    except Exception:  # eine unlesbare Ablage darf die Automatik nicht verhindern
        _LOGGER.warning("Automatik: Ablage der Wettervorhersage unlesbar")
        return {}
    eintraege = roh.get("prognosen") if isinstance(roh, dict) else None
    prognosen: Prognosen = {}
    for eintrag in eintraege if isinstance(eintraege, list) else []:
        if not isinstance(eintrag, dict):
            continue
        zeit = dt_util.parse_datetime(str(eintrag.get("zeit")))
        daten = eintrag.get("daten")
        if zeit is not None and daten and isinstance(daten, list):
            prognosen[(str(eintrag.get("wetter")), str(eintrag.get("art")))] = (zeit, daten)
    return prognosen
