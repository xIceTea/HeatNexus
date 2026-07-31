"""Eigene Oberfläche für die Heizung.

Meldet einen eigenen Eintrag in der Seitenleiste an, hinter dem eine
Anlagenübersicht steht: Kennwerte, Schaubild, Heizkreise, Warmwasser,
Störungen, Verlauf und Schnellzugriff – in einer Anordnung, die sich mit
Lovelace-Karten nicht bauen lässt.

**Die Aufteilung entsteht hier, nicht im Browser.** Python sucht die
Entitäten zusammen und legt sie als fertige Struktur in die Panel-Konfiguration;
die Datei im Browser stellt sie nur dar und holt sich die aktuellen Werte aus
``hass.states``. Damit bleibt die gesamte Gerätekenntnis an einer Stelle, und
im Browser liegt nichts, was bei einer neuen Anlage angepasst werden müsste.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
import re
from typing import Any

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    PANEL_ELEMENT,
    PANEL_JS_PFAD,
    PANEL_TITEL,
    PANEL_URL,
)
from .dashboard import _anlagen, _muster, _passt
from .schema import anlagenschema

_LOGGER = logging.getLogger(__name__)

_JS_DATEI = Path(__file__).parent / "frontend" / "heatnexus-panel.js"

# Der wichtigste Wert eines Anlagenteils, für die Liste links.
KENNWERT = (
    (r"kesseltemperatur ist", "Kesseltemperatur", "mdi:fire"),
    (r"puffer oben", "Puffer oben", "mdi:storage-tank"),
    (r"warmwassertemperatur", "Warmwasser", "mdi:water-boiler"),
    (r"raumtemperatur ist", "Raumtemperatur", "mdi:home-thermometer"),
    (r"vorlauftemperatur ist", "Vorlauf", "mdi:radiator"),
    (r"^temperatur ist$", "Temperatur", "mdi:thermometer"),
    (r"r(ü|ue)cklauf temperatur", "Rücklauf", "mdi:pipe"),
)

# Systemstatus rechts: Zeile für Zeile, in dieser Reihenfolge.
STATUS = (
    (r"betriebsphase", "Betriebszustand", "mdi:state-machine"),
    (r"au(ß|ss)entemperatur", "Außentemperatur", "mdi:thermometer"),
    (r"kesselleistung", "Kesselleistung", "mdi:fire"),
    (r"aktueller brennstoff", "Brennstoff", "mdi:sack"),
    (r"vorratsbeh", "Vorratsbehälter", "mdi:battery-70"),
    (r"laufzeit bis ascheentleerung", "Bis Ascheentleerung", "mdi:delete-clock-outline"),
)

WARMWASSER = _muster(
    r"warmwasser",
    r"ww[- ]",
    r"zirkulation",
)

VERLAUF = _muster(
    r"kesseltemperatur ist",
    r"au(ß|ss)entemperatur",
)

# Schnellzugriff: bedienbare Datenpunkte, die man wirklich anfasst.
SCHNELLZUGRIFF = (
    (r"ww einmalladung", "Warmwasser laden", "mdi:water-boiler"),
    (r"serviceausbrand", "Serviceausbrand", "mdi:fire-off"),
    (r"reinigung best", "Reinigung bestätigen", "mdi:broom"),
    (r"betriebswahl", "Betriebswahl", "mdi:tune"),
    (r"gew(ä|ae)hlter brennstoff", "Brennstoff wählen", "mdi:sack"),
)


def _erster(entitaeten: list[dict[str, Any]], muster: str) -> dict[str, Any] | None:
    regex = re.compile(muster, re.IGNORECASE)
    for eintrag in entitaeten:
        if eintrag.get("hat_wert") and regex.search(eintrag["name"]):
            return eintrag
    return None


def _zeilen(
    entitaeten: list[dict[str, Any]], vorlage: tuple[tuple[str, str, str], ...]
) -> list[dict[str, str]]:
    """Aus einer Mustervorlage die vorhandenen Entitäten als Zeilen."""
    zeilen = []
    for muster, beschriftung, symbol in vorlage:
        if (treffer := _erster(entitaeten, muster)) is not None:
            zeilen.append(
                {
                    "entity": treffer["entity_id"],
                    "titel": beschriftung,
                    "symbol": symbol,
                }
            )
    return zeilen


def _anlage_daten(anlage: dict[str, Any]) -> dict[str, Any]:
    """Alles, was die Oberfläche für eine Anlage braucht."""
    alle = [e for teil in anlage["teile"] for e in teil["entitaeten"]]

    kennwerte = []
    for teil in anlage["teile"]:
        for muster, beschriftung, symbol in KENNWERT:
            if (treffer := _erster(teil["entitaeten"], muster)) is not None:
                kennwerte.append(
                    {
                        "entity": treffer["entity_id"],
                        "titel": teil["name"],
                        "untertitel": beschriftung,
                        "symbol": symbol,
                    }
                )
                break

    heizkreise = []
    for teil in anlage["teile"]:
        thermostat = next(
            (e for e in teil["entitaeten"] if e["bereich"] == "climate"),
            None,
        )
        if thermostat is None:
            continue
        heizkreise.append(
            {
                "entity": thermostat["entity_id"],
                "titel": teil["name"],
                "vorlauf": (
                    v["entity_id"]
                    if (v := _erster(teil["entitaeten"], r"vorlauftemperatur ist"))
                    else None
                ),
            }
        )

    warmwasser = [
        {"entity": e["entity_id"], "titel": e["name"]}
        for e in alle
        if e["hat_wert"] and e["kategorie"] is None and _passt(e["name"], WARMWASSER)
    ][:6]

    stoerungen = [
        {"entity": e["entity_id"], "titel": e["name"]}
        for e in alle
        if e["kategorie"] == "diagnostic" and "klartext" in e["name"].lower()
    ]

    schnellzugriff = []
    for teil in anlage["teile"]:
        for muster, beschriftung, symbol in SCHNELLZUGRIFF:
            treffer = next(
                (
                    e
                    for e in teil["entitaeten"]
                    if e["bereich"] in ("switch", "button", "select")
                    and re.search(muster, e["name"], re.IGNORECASE)
                ),
                None,
            )
            if treffer is not None:
                schnellzugriff.append(
                    {
                        "entity": treffer["entity_id"],
                        "titel": beschriftung,
                        "symbol": symbol,
                    }
                )

    bild = anlagenschema(anlage["teile"])
    return {
        "name": anlage["name"],
        "kennwerte": kennwerte,
        "status": _zeilen(alle, STATUS),
        "heizkreise": heizkreise,
        "warmwasser": warmwasser,
        "stoerungen": stoerungen,
        "schnellzugriff": schnellzugriff[:6],
        "verlauf": [e["entity_id"] for e in alle if e["hat_wert"] and _passt(e["name"], VERLAUF)][
            :2
        ],
        "schema": bild["image"] if bild else None,
        "schema_werte": (
            [
                {
                    "entity": el["entity"],
                    "left": el["style"]["left"],
                    "top": el["style"]["top"],
                }
                for el in bild["elements"]
            ]
            if bild
            else []
        ),
    }


def panel_daten(hass: HomeAssistant) -> dict[str, Any]:
    """Die vollständige Struktur für die Oberfläche."""
    return {"anlagen": [_anlage_daten(anlage) for anlage in _anlagen(hass)]}


async def async_setup_panel(hass: HomeAssistant) -> None:
    """Die Oberfläche in der Seitenleiste anmelden.

    Fehler bleiben folgenlos – das Dashboard und die Entitäten funktionieren
    auch ohne sie.
    """
    try:
        await _async_setup_panel(hass)
    except Exception as err:
        _LOGGER.warning("Oberfläche konnte nicht angemeldet werden: %s", err)


async def _async_setup_panel(hass: HomeAssistant) -> None:
    """Eigentliche Anmeldung."""
    if not hass.data.get(f"{DOMAIN}_panel_datei"):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(PANEL_JS_PFAD, str(_JS_DATEI), cache_headers=False)]
        )
        hass.data[f"{DOMAIN}_panel_datei"] = True

    daten = panel_daten(hass)
    if not daten["anlagen"]:
        return

    # update=True ersetzt eine bestehende Anmeldung – nötig, weil sich mit dem
    # Umfang auch die Aufteilung ändert.
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=PANEL_TITEL,
        sidebar_icon="mdi:radiator",
        frontend_url_path=PANEL_URL,
        config={
            "_panel_custom": {
                "name": PANEL_ELEMENT,
                "module_url": PANEL_JS_PFAD,
                "embed_iframe": False,
                "trust_external": False,
            },
            "daten": daten,
        },
        require_admin=False,
        update=True,
    )
    hass.data[f"{DOMAIN}_panel"] = True
    _LOGGER.info("Oberfläche %s in der Seitenleiste angemeldet", PANEL_TITEL)


async def async_remove_panel(hass: HomeAssistant) -> None:
    """Die Oberfläche wieder aus der Seitenleiste nehmen."""
    if not hass.data.pop(f"{DOMAIN}_panel", None):
        return
    with contextlib.suppress(Exception):
        frontend.async_remove_panel(hass, PANEL_URL)
    _LOGGER.info("Oberfläche %s entfernt", PANEL_TITEL)
