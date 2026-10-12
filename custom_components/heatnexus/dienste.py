"""Die Dienste der Integration: `rediscover` und `dashboard_ausgeben`."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.storage import Store

from .const import DISCOVERY_STORE_VERSION, DOMAIN
from .dashboard import dashboard_als_yaml
from .erkennungsstand import laufzeitdaten, store_key, systems
from .exceptions import mit_text


def async_register_dashboard_export(hass: HomeAssistant) -> None:
    """Dienst heatnexus.dashboard_ausgeben: das Dashboard als YAML zum Kopieren."""
    if hass.services.has_service(DOMAIN, "dashboard_ausgeben"):
        return

    async def _handle_export(call: ServiceCall) -> dict[str, Any]:
        """Das erzeugte Dashboard als Text zurückgeben.

        Es entsteht bei jedem Öffnen neu und lässt sich deshalb nicht bearbeiten.
        Wer es anpassen will, legt mit diesem Text ein eigenes Dashboard an.
        """
        if not hass.config_entries.async_entries(DOMAIN):
            raise mit_text(ServiceValidationError, "keine_anlage")
        return {"yaml": dashboard_als_yaml(hass)}

    hass.services.async_register(
        DOMAIN,
        "dashboard_ausgeben",
        _handle_export,
        supports_response=SupportsResponse.ONLY,
    )


# So lange wartet `rediscover` auf den Vollabzug; danach meldet es den Stand bis dahin.
WARTEZEIT_VOLLABZUG = 300


def async_register_rediscover_service(hass: HomeAssistant) -> None:
    """Dienst heatnexus.rediscover: Erkennungsstand verwerfen und neu lesen."""
    if hass.services.has_service(DOMAIN, "rediscover"):
        return

    async def _handle_rediscover(call: ServiceCall) -> dict[str, Any]:
        """Erkennungsstand verwerfen, neu einlesen und sagen, was dabei herauskam.

        Gewartet wird auf den Vollabzug, höchstens `WARTEZEIT_VOLLABZUG`.
        `vollstaendig` sagt je Anlage, ob er in dieser Zeit fertig wurde.
        """
        eintraege = hass.config_entries.async_entries(DOMAIN)
        if not eintraege:
            raise mit_text(ServiceValidationError, "keine_anlage_zum_einlesen")
        hass.data.get(DOMAIN, {}).get("_discovery_cache", {}).clear()
        for eintrag in eintraege:
            for system in systems(eintrag):
                await Store(
                    hass, DISCOVERY_STORE_VERSION, store_key(eintrag, system[CONF_HOST])
                ).async_remove()
            await hass.config_entries.async_reload(eintrag.entry_id)
        aufgaben = [
            aufgabe
            for eintrag in eintraege
            for aufgabe in (laufzeitdaten(eintrag) or {}).get("hintergrund", [])
        ]
        if aufgaben:
            await asyncio.wait(aufgaben, timeout=WARTEZEIT_VOLLABZUG)
        return {"anlagen": [_bericht(h, c) for e in eintraege for h, c in _koordinatoren(e)]}

    hass.services.async_register(
        DOMAIN,
        "rediscover",
        _handle_rediscover,
        supports_response=SupportsResponse.OPTIONAL,
    )


def _koordinatoren(eintrag) -> list[tuple[str, Any]]:
    """Adresse und Koordinator jeder Anlage eines geladenen Eintrags."""
    daten = laufzeitdaten(eintrag) or {}
    return [
        (host, coordinator)
        for host, coordinator in (daten.get("coordinators") or {}).items()
        if getattr(coordinator, "client", None) is not None
    ]


def _bericht(host: str, coordinator: Any) -> dict[str, Any]:
    """Was das Einlesen einer Anlage ergab."""
    client = getattr(coordinator, "client", None)
    return {
        "anlage": getattr(coordinator, "label", None) or host,
        "entitaeten": len(getattr(client, "devices", []) or []),
        "zyklisch_abgefragt": len(getattr(client, "poll_oids", None) or []),
        "zeitprogramme": len(getattr(client, "time_programs", []) or []),
        "vollstaendig": bool(getattr(client, "_vollstaendig", False)),
    }
