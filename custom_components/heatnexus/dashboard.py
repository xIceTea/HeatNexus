"""Mitgeliefertes Dashboard bereitstellen.

Die Dashboard-Strategie liegt als JavaScript bei und baut die Ansichten zur
Laufzeit aus den erkannten Geräten. Auf Wunsch wird zusätzlich ein fertiges
Dashboard in der Seitenleiste angelegt.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DASHBOARD_TITEL, DASHBOARD_URL, DOMAIN, JS_URL

_LOGGER = logging.getLogger(__name__)

_JS_DATEI = Path(__file__).parent / "frontend" / "heatnexus-dashboard.js"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Die Dashboard-Strategie im Browser verfügbar machen."""
    if hass.data.get(f"{DOMAIN}_frontend"):
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig(JS_URL, str(_JS_DATEI), cache_headers=False)]
    )
    frontend.add_extra_js_url(hass, JS_URL)
    hass.data[f"{DOMAIN}_frontend"] = True
    _LOGGER.debug("Dashboard-Strategie bereitgestellt: %s", JS_URL)


def _sammlung(hass: HomeAssistant):
    """Verwaltung der Dashboards, falls verfügbar."""
    daten = hass.data.get("lovelace")
    return getattr(daten, "dashboards_collection", None)


async def async_setup_dashboard(hass: HomeAssistant) -> None:
    """Ein Dashboard in der Seitenleiste anlegen, falls noch keines besteht."""
    await async_register_frontend(hass)

    sammlung = _sammlung(hass)
    if sammlung is None:
        _LOGGER.warning(
            "Dashboard konnte nicht angelegt werden. Es lässt sich von Hand hinzufügen: "
            "Einstellungen, Dashboards, Dashboard hinzufügen, dann die Strategie "
            "custom:heatnexus eintragen."
        )
        return

    if any(eintrag.get("url_path") == DASHBOARD_URL for eintrag in sammlung.async_items()):
        return

    try:
        await sammlung.async_create_item(
            {
                "allow_single_word": True,
                "icon": "mdi:fire",
                "title": DASHBOARD_TITEL,
                "url_path": DASHBOARD_URL,
                "require_admin": False,
                "show_in_sidebar": True,
            }
        )
        speicher = hass.data["lovelace"].dashboards.get(DASHBOARD_URL)
        if speicher is not None:
            await speicher.async_save({"strategy": {"type": "custom:heatnexus"}})
        _LOGGER.info("Dashboard %s angelegt", DASHBOARD_TITEL)
    except Exception as err:
        _LOGGER.warning("Dashboard konnte nicht angelegt werden: %s", err)


async def async_remove_dashboard(hass: HomeAssistant) -> None:
    """Das angelegte Dashboard wieder entfernen."""
    sammlung = _sammlung(hass)
    if sammlung is None:
        return
    for eintrag in list(sammlung.async_items()):
        if eintrag.get("url_path") == DASHBOARD_URL:
            with contextlib.suppress(Exception):
                await sammlung.async_delete_item(eintrag["id"])
                _LOGGER.info("Dashboard %s entfernt", DASHBOARD_TITEL)
