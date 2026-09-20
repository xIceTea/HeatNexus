"""Die Dienste der Integration: `rediscover` und `dashboard_ausgeben`."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.storage import Store

from .const import DISCOVERY_STORE_VERSION, DOMAIN
from .dashboard import dashboard_als_yaml
from .erkennungsstand import laufzeitdaten, store_key, systems


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
            raise ServiceValidationError("Es ist keine Anlage eingerichtet.")
        return {"yaml": dashboard_als_yaml(hass)}

    hass.services.async_register(
        DOMAIN,
        "dashboard_ausgeben",
        _handle_export,
        supports_response=SupportsResponse.ONLY,
    )


def async_register_rediscover_service(hass: HomeAssistant) -> None:
    """Dienst heatnexus.rediscover: Erkennungsstand verwerfen und neu lesen."""
    if hass.services.has_service(DOMAIN, "rediscover"):
        return

    async def _handle_rediscover(call: ServiceCall) -> dict[str, Any]:
        """Erkennungsstand verwerfen, neu einlesen und sagen, was dabei herauskam.

        Der Lauf dauert je nach Anlage 30 bis 120 Sekunden. Ohne Rückgabe stand
        hinterher nur „Dienst ausgeführt" da, und ob die Anlage nun mehr, weniger
        oder dasselbe meldet, musste man sich aus der Entitätsliste
        zusammensuchen.
        """
        eintraege = hass.config_entries.async_entries(DOMAIN)
        if not eintraege:
            raise ServiceValidationError(
                "Es ist keine Anlage eingerichtet, die neu eingelesen werden könnte."
            )
        hass.data.get(DOMAIN, {}).get("_discovery_cache", {}).clear()
        anlagen: list[dict[str, Any]] = []
        for eintrag in eintraege:
            for system in systems(eintrag):
                await Store(
                    hass, DISCOVERY_STORE_VERSION, store_key(eintrag, system[CONF_HOST])
                ).async_remove()
            await hass.config_entries.async_reload(eintrag.entry_id)
            daten = laufzeitdaten(eintrag) or {}
            for host, coordinator in (daten.get("coordinators") or {}).items():
                client = getattr(coordinator, "client", None)
                if client is None:
                    continue
                anlagen.append(
                    {
                        "anlage": getattr(coordinator, "label", None) or host,
                        "entitaeten": len(getattr(client, "devices", []) or []),
                        "zyklisch_abgefragt": len(getattr(client, "poll_oids", None) or []),
                        "zeitprogramme": len(getattr(client, "time_programs", []) or []),
                    }
                )
        return {"anlagen": anlagen}

    hass.services.async_register(
        DOMAIN,
        "rediscover",
        _handle_rediscover,
        supports_response=SupportsResponse.OPTIONAL,
    )
