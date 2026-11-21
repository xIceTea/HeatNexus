"""Tagesverlauf für den Diagnoseexport: Schaltzustände und Temperaturen der letzten 24 Stunden.

Ein Export zeigt sonst nur den Augenblick. Ob eine Pumpe beim Laden meldet, sieht man erst im Verlauf.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, tzinfo
from functools import partial
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Ein Heiztag samt Nacht; eigener Wert, weil der Export unabhängig von der Automatik bleibt.
ZURUECK = timedelta(hours=24)
RASTER_MINUTEN = 10
# Mehr Wechsel als das: Der Wert springt laufend und geht wie eine Temperatur ins Raster.
HOECHSTENS = 500

# Deskriptortyp -> Bereich der Entität. Zeit, Datum und Texte bleiben draußen: Sie wechseln
# im Minutentakt und sagen über den Betrieb nichts.
BEREICH_JE_TYP = {
    "temperature": "sensor",
    "enum_sensor": "sensor",
    "sensor": "sensor",
    "binary_sensor": "binary_sensor",
    "select": "select",
    "switch": "switch",
}


def art(typ: str | None, einheit: str | None) -> str | None:
    """Wie ein Datenpunkt in den Verlauf eingeht: `wechsel`, `raster` oder gar nicht."""
    if typ == "temperature":
        return "raster"
    if typ == "sensor":
        # Drehzahlen, Stellwerte, Beladegrad; Zähler und Laufzeiten nicht.
        return "wechsel" if einheit == "%" else None
    return "wechsel" if typ in BEREICH_JE_TYP else None


def auswahl(beschreibungen: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Kennung -> Art, Bereich, Einheit und Name der Datenpunkte, die in den Verlauf gehören."""
    ergebnis: dict[str, dict[str, Any]] = {}
    for beschreibung in beschreibungen:
        typ, einheit = beschreibung.get("type"), beschreibung.get("unit")
        if (wie := art(typ, einheit)) and beschreibung.get("id"):
            ergebnis[beschreibung["id"]] = {
                "art": wie,
                "bereich": BEREICH_JE_TYP[typ],
                "einheit": "°C" if typ == "temperature" else einheit,
                "name": beschreibung.get("name"),
            }
    return ergebnis


def _zahl(wert: str) -> float | None:
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


def _raster(reihe: list[tuple[datetime, str]]) -> list[tuple[datetime, str]]:
    """Je Abschnitt ein Wert: der höchste, damit ein kurzer Pumpenlauf nicht verschwindet.

    Die Abschnitte liegen in UTC; die doppelte Stunde der Zeitumstellung bleibt getrennt.
    """
    je_abschnitt: dict[datetime, list[str]] = {}
    for zeit, wert in reihe:
        utc = zeit.astimezone(UTC)
        abschnitt = utc.replace(minute=utc.minute - utc.minute % RASTER_MINUTEN, second=0)
        je_abschnitt.setdefault(abschnitt.replace(microsecond=0), []).append(wert)
    ergebnis = []
    for abschnitt, werte in sorted(je_abschnitt.items()):
        zahlen = [z for z in map(_zahl, werte) if z is not None]
        ergebnis.append((abschnitt, werte[-1] if len(zahlen) < len(werte) else _hoechster(werte)))
    return ergebnis


def _hoechster(werte: list[str]) -> str:
    return max(werte, key=lambda wert: _zahl(wert) or 0.0)


def _ohne_wiederholung(reihe: list[tuple[datetime, str]]) -> list[tuple[datetime, str]]:
    ergebnis: list[tuple[datetime, str]] = []
    for zeit, wert in reihe:
        if not ergebnis or ergebnis[-1][1] != wert:
            ergebnis.append((zeit, wert))
    return ergebnis


def ausduennen(reihe: list[tuple[datetime, str]], wie: str, zone: tzinfo) -> list[list[str]]:
    """Zeit mit Versatz und Wert, ohne Wiederholungen; im Raster ein Wert je Abschnitt."""
    genau = wie == "wechsel"
    if genau:
        reihe = _ohne_wiederholung(reihe)
        genau = len(reihe) <= HOECHSTENS
    if not genau:
        reihe = _ohne_wiederholung(_raster(reihe))
    stelle = "seconds" if genau else "minutes"
    return [[zeit.astimezone(zone).isoformat(timespec=stelle), wert] for zeit, wert in reihe]


def _entitaeten(hass: Any, entry: Any, gewaehlt: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Kennung -> entity_id der aktiven Entitäten im passenden Bereich."""
    from homeassistant.helpers import entity_registry as er

    return {
        eintrag.unique_id: eintrag.entity_id
        for eintrag in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if eintrag.disabled_by is None
        and eintrag.unique_id in gewaehlt
        and eintrag.domain == gewaehlt[eintrag.unique_id]["bereich"]
    }


async def tagesverlauf(hass: Any, entry: Any, coordinators: dict[str, Any]) -> dict[str, Any]:
    """Der Verlauf der letzten 24 Stunden, je Datenpunkt unter seiner Kennung."""
    if "recorder" not in hass.config.components:
        return {"aufgezeichnet": False}
    from homeassistant.components.recorder import get_instance, history
    from homeassistant.util import dt as dt_util

    try:
        gewaehlt = auswahl(
            [b for c in coordinators.values() for b in (c.data or {}).get("devices", [])]
        )
        kennungen = _entitaeten(hass, entry, gewaehlt)
        jetzt = dt_util.utcnow()
        abfrage = partial(
            history.get_significant_states,
            hass,
            jetzt - ZURUECK,
            jetzt,
            list(kennungen.values()),
            significant_changes_only=False,
            no_attributes=True,
        )
        zustaende = await get_instance(hass).async_add_executor_job(abfrage) if kennungen else {}
    except Exception as fehler:  # der Verlauf ist eine Zugabe, der Export entsteht auch ohne ihn
        _LOGGER.debug("Diagnose: Verlauf nicht lesbar: %s", fehler)
        return {"aufgezeichnet": True, "fehler": type(fehler).__name__}
    zone = dt_util.get_default_time_zone()
    entitaeten = {}
    for kennung, entity_id in kennungen.items():
        angaben = gewaehlt[kennung]
        reihe = [(z.last_changed, z.state) for z in zustaende.get(entity_id, [])]
        entitaeten[kennung] = {
            "name": angaben["name"],
            "einheit": angaben["einheit"],
            "werte": ausduennen(reihe, angaben["art"], zone),
        }
    stunden = int(ZURUECK.total_seconds() // 3600)
    return {"aufgezeichnet": True, "stunden": stunden, "entitaeten": entitaeten}
