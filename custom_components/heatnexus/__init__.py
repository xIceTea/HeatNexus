"""HeatNexus – Heizungen in Home Assistant."""

from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from . import device_db, error_texts
from .client import WindhagerHttpClient
from .const import (
    CONF_ENABLE_ADVANCED,
    CONF_LEVELS,
    CONF_UPDATE_INTERVAL,
    CONF_WRITABLE_ADVANCED,
    DEFAULT_LEVELS,
    DISCOVERY_MAX_AGE_DAYS,
    DISCOVERY_STORE_VERSION,
    DOMAIN,
    INIT_TIMEOUT,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _preload_data() -> None:
    """Geräte-Datenbank und Störungstexte in den Zwischenspeicher holen."""
    device_db.preload()
    error_texts.preload()


def _store_key(entry: ConfigEntry) -> str:
    return f"{DOMAIN}_discovery_{entry.entry_id}"


def _scope(entry: ConfigEntry) -> dict:
    """Gewählter Umfang der Integration (Ebenen, Freigaben, Intervall)."""
    options = entry.options or {}
    return {
        "levels": list(options.get(CONF_LEVELS, DEFAULT_LEVELS)),
        "enable_advanced": bool(options.get(CONF_ENABLE_ADVANCED, False)),
        "writable_advanced": bool(options.get(CONF_WRITABLE_ADVANCED, False)),
        "update_interval": int(options.get(CONF_UPDATE_INTERVAL, UPDATE_INTERVAL)),
    }


def _scope_fingerprint(scope: dict) -> str:
    """Kennung des Umfangs – ändert er sich, ist der Discovery-Cache ungültig."""
    return (
        ",".join(scope["levels"])
        + f"|{int(scope['enable_advanced'])}{int(scope['writable_advanced'])}"
    )


def _discovery_cache_valid(stored, host: str, version: str, fingerprint: str) -> bool:
    """Persistenten Discovery-Cache auf Gültigkeit prüfen."""
    if not isinstance(stored, dict) or "data" not in stored:
        return False
    if stored.get("host") != host or stored.get("version") != version:
        return False
    if stored.get("scope") != fingerprint:
        return False
    saved = dt_util.parse_datetime(stored.get("saved") or "")
    if saved is None:
        return False
    return (dt_util.utcnow() - saved).days <= DISCOVERY_MAX_AGE_DAYS


PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.TIME,
    Platform.DATE,
]


class WindhagerDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Windhager data."""

    def __init__(self, hass, client, entry, update_interval: int = UPDATE_INTERVAL):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        self.client = client
        self.entry = entry
        self.consecutive_timeouts = 0

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            _LOGGER.debug("Starting data update from Windhager device")
            async with async_timeout.timeout(30):
                data = await self.client.fetch_all()
                self.consecutive_timeouts = 0
                return data
        except TimeoutError as err:
            self.consecutive_timeouts += 1
            _LOGGER.warning(
                "Timeout fetching data from %s (attempt %d)",
                self.entry.data["host"],
                self.consecutive_timeouts,
            )
            if self.consecutive_timeouts >= 3:
                raise UpdateFailed(
                    f"Multiple consecutive timeouts communicating with API: {err}"
                ) from err
            # Return last known good data if available
            return self.data if self.data else None
        except Exception as err:
            _LOGGER.error("Error fetching data from %s: %s", self.entry.data["host"], str(err))
            raise UpdateFailed(f"Error communicating with API: {err}") from err


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up heatnexus integration from a config entry."""
    _LOGGER.info("Setting up HeatNexus integration for %s", entry.data["host"])

    hass.data.setdefault(DOMAIN, {})
    _async_register_rediscover_service(hass)

    # Mitgelieferte Datendateien außerhalb der Ereignisschleife einlesen.
    await hass.async_add_executor_job(_preload_data)

    scope = _scope(entry)
    fingerprint = _scope_fingerprint(scope)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    client = WindhagerHttpClient(
        host=entry.data["host"],
        password=entry.data["password"],
        levels=scope["levels"],
        enable_advanced=scope["enable_advanced"],
        writable_advanced=scope["writable_advanced"],
    )

    # Die einmalige Discovery + Metadaten-Abfrage (jeder Datenpunkt wird einmal
    # gelesen, um Typ/Grenzen/Einheit zu bestimmen) ist DER teure Schritt beim
    # Start. Das Ergebnis wird gecacht:
    #   1) im RAM   -> überlebt einen Config-Entry-Reload (Entity aktivieren)
    #   2) auf Platte (Store) -> überlebt einen HA-Neustart
    # Neu erkannt wird nur, wenn die Integration aktualisiert wurde (andere
    # Version), der Cache zu alt ist, oder der Dienst heatnexus.rediscover läuft.
    host = entry.data["host"]
    mem_cache = hass.data[DOMAIN].setdefault("_discovery_cache", {})
    store = Store(hass, DISCOVERY_STORE_VERSION, _store_key(entry))
    integration = await async_get_integration(hass, DOMAIN)
    version = str(integration.version)

    cache_key = f"{host}|{fingerprint}"
    restored = False
    cached = mem_cache.get(cache_key)
    if cached:
        client.restore_discovery(cached)
        restored = True
    else:
        stored = await store.async_load()
        if _discovery_cache_valid(stored, host, version, fingerprint):
            client.restore_discovery(stored["data"])
            mem_cache[cache_key] = stored["data"]
            restored = True
            _LOGGER.debug("Windhager: Discovery aus persistentem Cache geladen (%s)", host)

    if not restored:
        _LOGGER.info(
            "Windhager: Erstinitialisierung/Discovery für %s (einmalig, kann etwas dauern)…",
            host,
        )
        try:
            async with async_timeout.timeout(INIT_TIMEOUT):
                await client.async_init()
        except TimeoutError as err:
            await client.close()
            raise ConfigEntryNotReady(f"Timeout bei der Erstinitialisierung von {host}") from err
        except Exception as err:
            await client.close()
            raise ConfigEntryNotReady(
                f"Fehler bei der Erstinitialisierung von {host}: {err}"
            ) from err

    coordinator = WindhagerDataUpdateCoordinator(hass, client, entry, scope["update_interval"])
    await coordinator.async_config_entry_first_refresh()

    # Cache erst nach dem ersten Refresh schreiben (dann ist auch geklärt, ob
    # der object-Endpunkt/Zeitprogramme lokal unterstützt werden und nicht
    # lesbare Datenpunkte sind bereits entfernt). RAM + Platte.
    if not restored:
        data = client.export_discovery()
        mem_cache[cache_key] = data
        await store.async_save(
            {
                "version": version,
                "host": host,
                "scope": fingerprint,
                "saved": dt_util.utcnow().isoformat(),
                "data": data,
            }
        )

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _async_register_rediscover_service(hass: HomeAssistant) -> None:
    """Dienst heatnexus.rediscover: Cache verwerfen und neu erkennen."""
    if hass.services.has_service(DOMAIN, "rediscover"):
        return

    async def _handle_rediscover(call: ServiceCall) -> None:
        hass.data.get(DOMAIN, {}).get("_discovery_cache", {}).clear()
        for e in hass.config_entries.async_entries(DOMAIN):
            await Store(hass, DISCOVERY_STORE_VERSION, _store_key(e)).async_remove()
            await hass.config_entries.async_reload(e.entry_id)

    hass.services.async_register(DOMAIN, "rediscover", _handle_rediscover)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Nach geänderten Optionen neu laden (anderer Umfang = andere Entities)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading HeatNexus integration for %s", entry.data["host"])
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.client.close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
