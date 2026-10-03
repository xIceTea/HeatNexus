"""Die Frontend-Dateien ausliefern.

Oberfläche und Lovelace-Karte liegen im selben Ordner und werden über
denselben statischen Pfad angeboten. Die Fassung steckt **im Pfad**, nicht als
Fragezeichen dahinter: Der Service Worker von Home Assistant vergleicht
Adressen ohne Suchteil und lieferte sonst die alte Datei weiter aus.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

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


async def _ressourcen(hass: HomeAssistant) -> Any:
    """Die geladenen Ressourcen von Lovelace, sofern sie in der Oberfläche gepflegt werden."""
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA
    except ImportError:  # pragma: no cover
        return None
    ressourcen = getattr(hass.data.get(LOVELACE_DATA), "resources", None)
    if not hasattr(ressourcen, "async_create_item"):
        return None
    await ressourcen.async_get_info()
    return ressourcen


def _eigene_ressourcen(ressourcen: Any) -> list[dict[str, Any]]:
    return [
        r for r in ressourcen.async_items() if str(r.get("url", "")).startswith(KARTE_VERZEICHNIS)
    ]


async def karte_als_ressource(hass: HomeAssistant, version: str = "") -> None:
    """Das Kartenmodul zusätzlich als Lovelace-Ressource führen, eine je Installation.

    Zusatzmodule kennt nur eine Seite, die nach dem Start der Integration geladen
    wurde; Ressourcen lädt das Dashboard selbst, auch auf Cast-Geräten.
    """
    ressourcen = await _ressourcen(hass)
    if ressourcen is None:
        return
    adresse = karte_js_pfad(version)
    eigene = _eigene_ressourcen(ressourcen)
    if not eigene:
        await ressourcen.async_create_item({"res_type": "module", "url": adresse})
        return
    erste, *rest = eigene
    if erste.get("url") != adresse:
        await ressourcen.async_update_item(erste["id"], {"res_type": "module", "url": adresse})
    for ueberzaehlig in rest:
        await ressourcen.async_delete_item(ueberzaehlig["id"])


async def karte_ressource_entfernen(hass: HomeAssistant) -> None:
    """Die Ressource der Karte entfernen, wenn die Integration geht."""
    ressourcen = await _ressourcen(hass)
    if ressourcen is None:
        return
    for eigene in _eigene_ressourcen(ressourcen):
        await ressourcen.async_delete_item(eigene["id"])
