"""HeatNexus – Heizungen in Home Assistant."""

from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from . import device_db, error_texts
from .client import WindhagerHttpClient
from .const import (
    CONF_DASHBOARD,
    CONF_ENABLE_ADVANCED,
    CONF_LABEL,
    CONF_LEVELS,
    CONF_SYSTEMS,
    CONF_UPDATE_INTERVAL,
    CONF_WRITABLE_ADVANCED,
    DEFAULT_LEVELS,
    DISCOVERY_MAX_AGE_DAYS,
    DISCOVERY_STORE_VERSION,
    DOMAIN,
    INIT_TIMEOUT,
    SIGNAL_NEUE_ENTITAETEN,
    UPDATE_INTERVAL,
)
from .dashboard import (
    async_register_frontend,
    async_remove_dashboard,
    async_setup_dashboard,
)

_LOGGER = logging.getLogger(__name__)

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


def _preload_data() -> None:
    """Geräte-Datenbank und Störungstexte in den Zwischenspeicher holen."""
    device_db.preload()
    error_texts.preload()


def _store_key(entry: ConfigEntry, host: str) -> str:
    """Ablageort des Erkennungsstands einer Anlage."""
    return f"{DOMAIN}_discovery_{entry.entry_id}_{host.replace('.', '_')}"


def _systems(entry: ConfigEntry) -> list[dict]:
    """Anlagen dieses Eintrags."""
    return list(entry.data.get(CONF_SYSTEMS, []))


def _scope(entry: ConfigEntry, host: str) -> dict:
    """Gewählter Umfang einer Anlage (Ebenen, Freigaben, Intervall)."""
    options = entry.options or {}
    je_anlage = options.get(host) or {}
    return {
        "levels": list(je_anlage.get(CONF_LEVELS, DEFAULT_LEVELS)),
        "enable_advanced": bool(je_anlage.get(CONF_ENABLE_ADVANCED, False)),
        "writable_advanced": bool(je_anlage.get(CONF_WRITABLE_ADVANCED, False)),
        "update_interval": int(options.get(CONF_UPDATE_INTERVAL, UPDATE_INTERVAL)),
    }


def _scope_fingerprint(scope: dict) -> str:
    """Kennung des Umfangs – ändert er sich, ist der Erkennungsstand ungültig."""
    return (
        ",".join(scope["levels"])
        + f"|{int(scope['enable_advanced'])}{int(scope['writable_advanced'])}"
    )


def _discovery_cache_valid(stored, host: str, version: str, fingerprint: str) -> bool:
    """Gespeicherten Erkennungsstand auf Gültigkeit prüfen."""
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


class WindhagerDataUpdateCoordinator(DataUpdateCoordinator):
    """Fragt eine Anlage zyklisch ab."""

    def __init__(self, hass, client, entry, host, label, update_interval=UPDATE_INTERVAL):
        """Coordinator für genau eine Anlage."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {host}",
            update_interval=timedelta(seconds=update_interval),
        )
        self.client = client
        self.entry = entry
        self.host = host
        self.label = label
        self.hub_name = entry.data.get(CONF_NAME) or entry.title
        self.consecutive_timeouts = 0

    async def _async_update_data(self):
        """Werte der Anlage holen."""
        try:
            async with async_timeout.timeout(30):
                data = await self.client.fetch_all()
                self.consecutive_timeouts = 0
                return data
        except TimeoutError as err:
            self.consecutive_timeouts += 1
            _LOGGER.warning(
                "Zeitüberschreitung beim Abruf von %s (Versuch %d)",
                self.host,
                self.consecutive_timeouts,
            )
            if self.consecutive_timeouts >= 3:
                raise UpdateFailed(f"Anlage {self.host} antwortet wiederholt nicht: {err}") from err
            return self.data if self.data else None
        except Exception as err:
            _LOGGER.error("Fehler beim Abruf von %s: %s", self.host, err)
            raise UpdateFailed(f"Fehler bei der Abfrage von {self.host}: {err}") from err


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Einen Konfigurationseintrag mit einer oder mehreren Anlagen einrichten."""
    systeme = _systems(entry)
    if not systeme:
        raise ConfigEntryNotReady("Keine Anlage im Konfigurationseintrag hinterlegt")

    hass.data.setdefault(DOMAIN, {})
    _async_register_rediscover_service(hass)
    await hass.async_add_executor_job(_preload_data)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    integration = await async_get_integration(hass, DOMAIN)
    version = str(integration.version)
    mem_cache = hass.data[DOMAIN].setdefault("_discovery_cache", {})
    hub_name = entry.data.get(CONF_NAME) or entry.title

    # Übergeordnetes Gerät: die Heizungsanlage als Ganzes.
    registry = dr.async_get(hass)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=hub_name,
        manufacturer="Windhager",
        model="Heizungsanlage",
    )

    coordinators: dict[str, WindhagerDataUpdateCoordinator] = {}
    nachzuladen: list[tuple] = []

    for system in systeme:
        host = system[CONF_HOST]
        label = system.get(CONF_LABEL) or host
        scope = _scope(entry, host)
        fingerprint = _scope_fingerprint(scope)

        client = WindhagerHttpClient(
            host=host,
            password=system[CONF_PASSWORD],
            levels=scope["levels"],
            enable_advanced=scope["enable_advanced"],
            writable_advanced=scope["writable_advanced"],
        )

        # Erkennungsstand: erst Arbeitsspeicher, dann Platte, sonst neu lesen.
        store = Store(hass, DISCOVERY_STORE_VERSION, _store_key(entry, host))
        cache_key = f"{host}|{fingerprint}"
        restored = False
        if (cached := mem_cache.get(cache_key)) is not None:
            client.restore_discovery(cached)
            restored = True
        else:
            stored = await store.async_load()
            if _discovery_cache_valid(stored, host, version, fingerprint):
                client.restore_discovery(stored["data"])
                mem_cache[cache_key] = stored["data"]
                restored = True

        if not restored:
            # Nur Grunddaten abwarten – der Vollabzug folgt im Hintergrund.
            try:
                async with async_timeout.timeout(INIT_TIMEOUT):
                    await client.async_init_basic()
            except TimeoutError as err:
                await client.close()
                raise ConfigEntryNotReady(f"Zeitüberschreitung beim Verbinden mit {host}") from err
            except Exception as err:
                await client.close()
                raise ConfigEntryNotReady(f"Fehler beim Verbinden mit {host}: {err}") from err

        coordinator = WindhagerDataUpdateCoordinator(
            hass, client, entry, host, label, scope["update_interval"]
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators[host] = coordinator

        # Die Anlage selbst als Untergerät der Heizungsanlage.
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{host}")},
            name=label,
            manufacturer="Windhager",
            model="Steuerung",
            via_device=(DOMAIN, entry.entry_id),
        )

        if not restored:
            nachzuladen.append((coordinator, client, store, host, fingerprint, cache_key))

    hass.data[DOMAIN][entry.entry_id] = {"name": hub_name, "coordinators": coordinators}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _geraetenamen_angleichen(registry, entry, coordinators)
    _verwaiste_entitaeten_entfernen(hass, entry, coordinators)

    if (entry.options or {}).get(CONF_DASHBOARD, True):
        await async_setup_dashboard(hass)
    else:
        await async_register_frontend(hass)

    for coordinator, client, store, host, fingerprint, cache_key in nachzuladen:
        entry.async_create_background_task(
            hass,
            _vollabzug(
                hass,
                entry,
                coordinator,
                client,
                store,
                host,
                fingerprint,
                cache_key,
                mem_cache,
                version,
            ),
            name=f"{DOMAIN}_vollabzug_{host}",
        )

    return True


def _verwaiste_entitaeten_entfernen(
    hass: HomeAssistant, entry: ConfigEntry, coordinators: dict
) -> None:
    """Entitäten entfernen, die es nach der aktuellen Auswahl nicht mehr gibt.

    Wird der Umfang verkleinert (z.B. Werksebene abgewählt), blieben die
    bereits angelegten Entitäten sonst dauerhaft als „nicht verfügbar" stehen.
    """
    vollstaendig = all(getattr(c.client, "_vollstaendig", False) for c in coordinators.values())
    if not vollstaendig:
        # Vor dem Vollabzug ist die Liste noch unvollständig – nichts löschen.
        return

    gueltig = {
        beschreibung.get("id")
        for coordinator in coordinators.values()
        for beschreibung in (coordinator.data or {}).get("devices", [])
    }
    registry = er.async_get(hass)
    for eintrag in list(er.async_entries_for_config_entry(registry, entry.entry_id)):
        if eintrag.unique_id not in gueltig:
            _LOGGER.debug("Entferne verwaiste Entität %s", eintrag.entity_id)
            registry.async_remove(eintrag.entity_id)


def _geraetenamen_angleichen(registry, entry: ConfigEntry, coordinators: dict) -> None:
    """Namen bestehender Geräte an das aktuelle Schema angleichen.

    Home Assistant übernimmt geänderte Gerätenamen nicht immer von selbst.
    Eine eigene Umbenennung durch den Nutzer bleibt unangetastet.
    """
    for host, coordinator in coordinators.items():
        for beschreibung in (coordinator.data or {}).get("devices", []):
            kennung = beschreibung.get("device_id")
            funktion = (beschreibung.get("device_name") or "").strip()
            if not kennung or not funktion:
                continue
            geraet = registry.async_get_device(identifiers={(DOMAIN, kennung)})
            if geraet is None:
                continue
            gewuenscht = f"{coordinator.label} · {funktion}"
            if coordinator.label and coordinator.label != funktion and geraet.name != gewuenscht:
                registry.async_update_device(
                    geraet.id,
                    name=gewuenscht,
                    via_device_id=registry.async_get_device(
                        identifiers={(DOMAIN, f"{entry.entry_id}_{host}")}
                    ).id,
                )


async def _vollabzug(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator,
    client,
    store: Store,
    host: str,
    fingerprint: str,
    cache_key: str,
    mem_cache: dict,
    version: str,
) -> None:
    """Die Anlage im Hintergrund vollständig einlesen.

    Home Assistant läuft zu diesem Zeitpunkt bereits; die zusätzlich
    gefundenen Entitäten werden anschließend nachgemeldet.
    """
    try:
        await client.async_init()
    except Exception as err:
        _LOGGER.warning("%s konnte nicht vollständig eingelesen werden: %s", host, err)
        return

    await coordinator.async_refresh()
    async_dispatcher_send(hass, SIGNAL_NEUE_ENTITAETEN.format(entry.entry_id))
    daten = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if daten:
        _verwaiste_entitaeten_entfernen(hass, entry, daten["coordinators"])

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


def _async_register_rediscover_service(hass: HomeAssistant) -> None:
    """Dienst heatnexus.rediscover: Erkennungsstand verwerfen und neu lesen."""
    if hass.services.has_service(DOMAIN, "rediscover"):
        return

    async def _handle_rediscover(call: ServiceCall) -> None:
        hass.data.get(DOMAIN, {}).get("_discovery_cache", {}).clear()
        for eintrag in hass.config_entries.async_entries(DOMAIN):
            for system in _systems(eintrag):
                await Store(
                    hass, DISCOVERY_STORE_VERSION, _store_key(eintrag, system[CONF_HOST])
                ).async_remove()
            await hass.config_entries.async_reload(eintrag.entry_id)

    hass.services.async_register(DOMAIN, "rediscover", _handle_rediscover)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Nach geänderten Optionen neu laden (anderer Umfang = andere Entitäten)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Einen Konfigurationseintrag entladen."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        daten = hass.data[DOMAIN].pop(entry.entry_id, {})
        for coordinator in daten.get("coordinators", {}).values():
            await coordinator.client.close()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Beim Entfernen der letzten Anlage auch das Dashboard abräumen."""
    if not hass.config_entries.async_entries(DOMAIN):
        await async_remove_dashboard(hass)
