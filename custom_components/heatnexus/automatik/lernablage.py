"""Lernstunden je Heizkreis in einer eigenen Datei, unabhängig vom Löschen der Aufzeichnung.

Der Recorder hält Zustände nur einige Tage; ohne Ablage schrumpft das Lernfenster auf diese Spanne.
Geschrieben wird einmal je Lernlauf, nicht im Takt der Automatik.
"""

from __future__ import annotations

from datetime import date
import logging
import math
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..const import DOMAIN
from .hausmodell import Stunde

_LOGGER = logging.getLogger(__name__)
FASSUNG = 1
NACHKOMMA = 3


def _store(hass: HomeAssistant, device_id: str) -> Store:
    return Store(hass, FASSUNG, f"{DOMAIN}.hausmodell_{device_id}")


def _zahl(wert: Any, leer: bool = False) -> float | None:
    """Eine endliche Zahl; `leer` erlaubt `None`."""
    if wert is None and leer:
        return None
    if isinstance(wert, bool) or not isinstance(wert, int | float) or not math.isfinite(wert):
        raise ValueError(wert)
    return float(wert)


def _stunde(roh: Any) -> Stunde:
    raum, danach, at, sonne, wind, heizen = roh
    return Stunde(
        _zahl(raum), _zahl(danach, True), _zahl(at), _zahl(sonne), _zahl(wind, True), _zahl(heizen)
    )


def _runden(wert: float | None) -> float | None:
    return None if wert is None else round(wert, NACHKOMMA)


async def laden(hass: HomeAssistant, device_id: str, heiz_art: str) -> dict[date, list[Stunde]]:
    """Die abgelegten Tage; Stunden einer anderen Heizart oder Unlesbares zählen nicht."""
    try:
        roh = await _store(hass, device_id).async_load()
    except Exception:  # eine unlesbare Ablage darf das Lernen nicht verhindern
        _LOGGER.warning("Automatik %s: Ablage der Lernstunden unlesbar", device_id)
        return {}
    if not isinstance(roh, dict) or roh.get("heiz_art") != heiz_art:
        return {}
    tage: dict[date, list[Stunde]] = {}
    for tag, stunden in (roh.get("tage") or {}).items():
        try:
            tage[date.fromisoformat(tag)] = [_stunde(s) for s in stunden]
        except (TypeError, ValueError):
            continue
    return tage


async def sichern(
    hass: HomeAssistant, device_id: str, heiz_art: str, tage: dict[date, list[Stunde]]
) -> None:
    """Die Tage des Lernfensters ablegen; ältere fallen weg."""
    daten = {
        "heiz_art": heiz_art,
        "tage": {
            tag.isoformat(): [
                [_runden(getattr(s, feld)) for feld in Stunde.__dataclass_fields__] for s in stunden
            ]
            for tag, stunden in sorted(tage.items())
        },
    }
    await _store(hass, device_id).async_save(daten)


async def entfernen(hass: HomeAssistant, device_id: str) -> None:
    """Die Ablage löschen, etwa nach anderen Räumen oder mit der Automatik."""
    await _store(hass, device_id).async_remove()
