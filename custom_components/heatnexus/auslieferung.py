"""Die Frontend-Dateien ausliefern.

Oberfläche und Lovelace-Karte liegen im selben Ordner und werden über
denselben statischen Pfad angeboten. Die Fassung steckt **im Pfad**, nicht als
Fragezeichen dahinter: Der Service Worker von Home Assistant vergleicht
Adressen ohne Suchteil und lieferte sonst die alte Datei weiter aus.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN, karte_js_pfad, panel_verzeichnis

_LOGGER = logging.getLogger(__name__)

_FRONTEND = Path(__file__).parent / "frontend"


async def async_dateien_ausliefern(hass: HomeAssistant, version: str = "") -> None:
    """Den Ordner unter seinem Fassungspfad anbieten – einmal je Fassung."""
    ordner = panel_verzeichnis(version)
    registriert: set[str] = hass.data.setdefault(f"{DOMAIN}_panel_dateien", set())
    if ordner in registriert:
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(ordner, str(_FRONTEND), cache_headers=False)]
    )
    registriert.add(ordner)


def karte_anmelden(hass: HomeAssistant, version: str = "") -> None:
    """Das Kartenmodul in jede Sitzung laden.

    Über `add_extra_js_url`, nicht als Lovelace-Ressource: Das lädt beim
    Seitenaufbau statt erst im Dashboard und braucht keinen Schritt des Nutzers.
    """
    if hass.data.get(f"{DOMAIN}_karte_js"):
        return
    frontend.add_extra_js_url(hass, karte_js_pfad(version))
    hass.data[f"{DOMAIN}_karte_js"] = True
    _LOGGER.debug("Kartenmodul unter %s angemeldet", karte_js_pfad(version))
