"""Mitgeliefertes Dashboard bereitstellen.

Die Dashboard-Strategie liegt als JavaScript bei und baut die Ansichten zur
Laufzeit aus den erkannten Geräten. Zusätzlich meldet die Integration ein
eigenes Dashboard in der Seitenleiste an, dessen Inhalt nur aus dem Verweis
auf diese Strategie besteht.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DASHBOARD_TITEL, DASHBOARD_URL, DOMAIN, JS_URL

_LOGGER = logging.getLogger(__name__)

_JS_DATEI = Path(__file__).parent / "frontend" / "heatnexus-dashboard.js"
_INHALT: dict[str, Any] = {"strategy": {"type": "custom:heatnexus"}}


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


async def async_setup_dashboard(hass: HomeAssistant) -> None:
    """Dashboard in der Seitenleiste anmelden."""
    await async_register_frontend(hass)

    if hass.data.get(f"{DOMAIN}_dashboard"):
        return

    try:
        from homeassistant.components.lovelace.const import (
            LOVELACE_DATA,
            MODE_YAML,
        )
        from homeassistant.components.lovelace.dashboard import (
            LovelaceConfig,
        )
        from homeassistant.helpers.json import json_fragment
    except ImportError as err:  # pragma: no cover - ältere Home-Assistant-Fassung
        _LOGGER.warning("Dashboard nicht verfügbar: %s", err)
        return

    class HeatNexusDashboard(LovelaceConfig):
        """Verweist nur auf die Strategie; die Ansichten baut der Browser."""

        def __init__(self) -> None:
            """Dashboard ohne eigene Konfigurationsdatei."""
            super().__init__(hass, DASHBOARD_URL, {"mode": MODE_YAML})

        @property
        def mode(self) -> str:
            """Der Inhalt kommt aus der Integration, nicht aus dem Speicher."""
            return MODE_YAML

        async def async_get_info(self) -> dict[str, Any]:
            """Kurzinfo für die Dashboard-Übersicht."""
            return {"mode": MODE_YAML}

        async def async_load(self, force: bool) -> dict[str, Any]:
            """Inhalt des Dashboards."""
            return dict(_INHALT)

        async def async_json(self, force: bool) -> Any:
            """Inhalt als vorbereitetes JSON."""
            return json_fragment(json.dumps(_INHALT))

    daten = hass.data.get(LOVELACE_DATA)
    if daten is None:
        _LOGGER.warning("Dashboards stehen noch nicht bereit")
        return

    if DASHBOARD_URL not in daten.dashboards:
        daten.dashboards[DASHBOARD_URL] = HeatNexusDashboard()

    try:
        frontend.async_register_built_in_panel(
            hass,
            "lovelace",
            DASHBOARD_TITEL,
            "mdi:fire",
            DASHBOARD_URL,
            {"mode": MODE_YAML, "urlPath": DASHBOARD_URL},
            require_admin=False,
            update=True,
        )
    except ValueError:
        # Ein Panel mit dieser Adresse besteht bereits.
        pass

    hass.data[f"{DOMAIN}_dashboard"] = True
    _LOGGER.info("Dashboard %s in der Seitenleiste angemeldet", DASHBOARD_TITEL)


async def async_remove_dashboard(hass: HomeAssistant) -> None:
    """Das Dashboard wieder aus der Seitenleiste nehmen."""
    if not hass.data.pop(f"{DOMAIN}_dashboard", None):
        return
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA
    except ImportError:  # pragma: no cover
        return

    daten = hass.data.get(LOVELACE_DATA)
    if daten is not None:
        daten.dashboards.pop(DASHBOARD_URL, None)
    frontend.async_remove_panel(hass, DASHBOARD_URL)
    _LOGGER.info("Dashboard %s entfernt", DASHBOARD_TITEL)
