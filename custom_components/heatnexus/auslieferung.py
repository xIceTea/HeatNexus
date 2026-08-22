"""Die Frontend-Dateien ausliefern.

Oberfläche und Lovelace-Karte liegen im selben Ordner und werden über
denselben statischen Pfad angeboten. Die Fassung steckt **im Pfad**, nicht als
Fragezeichen dahinter: Der Service Worker von Home Assistant vergleicht
Adressen ohne Suchteil und lieferte sonst die alte Datei weiter aus.
"""

from __future__ import annotations

import logging
from pathlib import Path

from aiohttp import web
from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    KARTE_VERZEICHNIS,
    karte_js_pfad,
    karte_verzeichnis,
    panel_verzeichnis,
)

_LOGGER = logging.getLogger(__name__)

_FRONTEND = Path(__file__).parent / "frontend"


async def async_dateien_ausliefern(hass: HomeAssistant, version: str = "") -> None:
    """Den Ordner anbieten – unter dem Fassungspfad und unter dem festen.

    Das Panel lädt bei jedem Öffnen neu und verträgt den Fassungspfad. Die
    Karte steht in einer Seite, die offen bleibt; für sie muss die Adresse von
    gestern weiter antworten.
    """
    registriert: set[str] = hass.data.setdefault(f"{DOMAIN}_panel_dateien", set())
    neu = [
        StaticPathConfig(ordner, str(_FRONTEND), cache_headers=False)
        for ordner in (panel_verzeichnis(version), karte_verzeichnis(version), KARTE_VERZEICHNIS)
        if ordner not in registriert
    ]
    if neu:
        await hass.http.async_register_static_paths(neu)
        registriert.update(pfad.url_path for pfad in neu)
    _fassungspfade_anbieten(hass)


def datei_im_ordner(name: str) -> Path | None:
    """Den Pfad zu einer Frontend-Datei prüfen.

    Nur Dateien aus dem Ordner selbst; alles andere gibt es nicht.
    """
    ziel = (_FRONTEND / name).resolve()
    if ziel.is_file() and ziel.is_relative_to(_FRONTEND.resolve()):
        return ziel
    return None


def _fassungspfade_anbieten(hass: HomeAssistant) -> None:
    """Jeden Fassungspfad der Karte beantworten, auch einen alten.

    Der Browser behält die Seite mit dem Pfad der vorigen Fassung. Antwortet
    der nicht mehr, fehlt das Kartenmodul und das Dashboard meldet einen
    Konfigurationsfehler, bis jemand den Zwischenspeicher leert.
    """
    if hass.data.get(f"{DOMAIN}_karte_pfade"):
        return

    async def _ausliefern(request: web.Request) -> web.FileResponse:
        ziel = datei_im_ordner(request.match_info["datei"])
        if ziel is None:
            raise web.HTTPNotFound
        return web.FileResponse(ziel)

    hass.http.app.router.add_route(
        "GET", f"{KARTE_VERZEICHNIS}-{{fassung}}/{{datei:.+}}", _ausliefern
    )
    hass.data[f"{DOMAIN}_karte_pfade"] = True


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
