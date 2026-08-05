"""HeatNexus – Heizungen in Home Assistant."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import timedelta
import logging

# Nur die Funktion, nicht das Modul: Diese Datei *ist* der Namensraum des
# Pakets. Sobald Home Assistant die Plattform `heatnexus.time` lädt, setzt
# Python sie als Attribut `time` auf das Paket – und überschreibt damit ein
# hier stehendes `import time`. Danach zeigt `time.monotonic` auf die
# Plattformdatei und der Aufruf scheitert. Ob das passiert, hing bisher am
# Wettlauf zwischen Plattform-Import und Einrichtung.
from time import monotonic

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from . import device_db, error_texts
from .blueprints import async_install_blueprints
from .client import WindhagerHttpClient
from .const import (
    CONF_DASHBOARD,
    CONF_ENABLE_ADVANCED,
    CONF_LABEL,
    CONF_LEVELS,
    CONF_MELDUNG_EINLESEN,
    CONF_PANEL,
    CONF_SYSTEMS,
    CONF_UPDATE_INTERVAL,
    CONF_WRITABLE_ADVANCED,
    DEFAULT_LEVELS,
    DEFAULT_USERNAME,
    DISCOVERY_MAX_AGE_DAYS,
    DISCOVERY_STORE_VERSION,
    DOMAIN,
    INIT_TIMEOUT,
    SIGNAL_NEUE_ENTITAETEN,
    UPDATE_INTERVAL,
)
from .dashboard import async_remove_dashboard, async_setup_dashboard
from .entity import steuerung_kennung
from .migration import async_entity_ids_umstellen, async_kennungen_umstellen

_LOGGER = logging.getLogger(__name__)

# Sekunden, die die Erfolgsmeldung dem Anlegen der nachgemeldeten Entitäten
# einräumt.
MELDUNG_VERZOEGERUNG = 10

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
    """Gewählter Umfang einer Anlage (Ebenen, Freigaben, Intervall, Zugang)."""
    options = entry.options or {}
    je_anlage = options.get(host) or {}
    system = next((s for s in _systems(entry) if s.get(CONF_HOST) == host), {})
    return {
        "levels": list(je_anlage.get(CONF_LEVELS, DEFAULT_LEVELS)),
        "enable_advanced": bool(je_anlage.get(CONF_ENABLE_ADVANCED, False)),
        "writable_advanced": bool(je_anlage.get(CONF_WRITABLE_ADVANCED, False)),
        "update_interval": int(options.get(CONF_UPDATE_INTERVAL, UPDATE_INTERVAL)),
        "username": system.get(CONF_USERNAME) or DEFAULT_USERNAME,
    }


def _scope_fingerprint(scope: dict) -> str:
    """Kennung des Umfangs – ändert er sich, ist der Erkennungsstand ungültig.

    Der Zugang gehört dazu: „Service" sieht Datenpunkte, die „USER" gar nicht
    erst geliefert bekommt. Ein Wechsel muss die Anlage neu einlesen.
    """
    return (
        ",".join(scope["levels"])
        + f"|{int(scope['enable_advanced'])}{int(scope['writable_advanced'])}"
        + f"|{scope.get('username', DEFAULT_USERNAME)}"
    )


def _discovery_cache_valid(stored, host: str, fingerprint: str) -> bool:
    """Gespeicherten Erkennungsstand auf Gültigkeit prüfen.

    Die Version der Integration steht bewusst **nicht** in dieser Prüfung:
    Sonst läse HeatNexus nach jeder Aktualisierung die ganze Anlage neu ein –
    30 bis 120 Sekunden, in denen kaum etwas dasteht, obwohl sich an der
    Anlage nichts geändert hat. Ein Versionswechsel löst stattdessen einen
    Abgleich im Hintergrund aus (siehe `_veraltet`): Die bekannten Werte sind
    sofort da, Neues kommt nach.

    Was den Stand weiterhin verwirft: eine andere Anlage, ein geänderter
    Umfang (Ebenen, Freigaben, Zugang), zu hohes Alter – und der Dienst
    `heatnexus.rediscover`.
    """
    if not isinstance(stored, dict) or "data" not in stored:
        return False
    if stored.get("host") != host:
        return False
    if stored.get("scope") != fingerprint:
        return False
    saved = dt_util.parse_datetime(stored.get("saved") or "")
    if saved is None:
        return False
    return (dt_util.utcnow() - saved).days <= DISCOVERY_MAX_AGE_DAYS


def _veraltet(stored, version: str) -> bool:
    """Prüfen, ob der Stand aus einer anderen Fassung der Integration stammt."""
    return isinstance(stored, dict) and stored.get("version") != version


class WindhagerDataUpdateCoordinator(DataUpdateCoordinator):
    """Fragt eine Anlage zyklisch ab."""

    def __init__(self, hass, client, entry, host, label, update_interval=UPDATE_INTERVAL):
        """Coordinator für genau eine Anlage."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {host}",
            update_interval=timedelta(seconds=update_interval),
            # Unveränderte Daten lösen keinen Durchlauf durch alle Entitäten
            # aus. Eine Anlage im Standby meldet minutenlang dieselben Werte;
            # bei 167 Entitäten ist das jedes Mal ein vollständiger Rundlauf
            # ohne Ergebnis.
            #
            # Achtung, das hat eine Nebenwirkung: Was sich nur *mit der Zeit*
            # ändert, darf nicht am Takt des Coordinators hängen. Die
            # optimistische Anzeige des Thermostats prüft ihren Ablauf deshalb
            # seither in der Eigenschaft selbst (`_optimistisch_gueltig`) und
            # nicht mehr nur beim Eintreffen neuer Daten.
            always_update=False,
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
            async with asyncio.timeout(30):
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
    await async_install_blueprints(hass, version)
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

    async def _anlage_vorbereiten(system: dict) -> tuple:
        """Eine Anlage verbinden und ihren ersten Abruf machen.

        Bewusst als eigene Aufgabe: Die Anlagen wurden bisher nacheinander
        eingerichtet – bei zwei Anlagen wartete die zweite, bis die erste ihren
        vollständigen Erstabruf hinter sich hatte. Da beide über getrennte
        Verbindungen laufen, gibt es keinen Grund dafür.
        """
        host = system[CONF_HOST]
        label = system.get(CONF_LABEL) or host
        scope = _scope(entry, host)
        fingerprint = _scope_fingerprint(scope)

        client = WindhagerHttpClient(
            host=host,
            password=system[CONF_PASSWORD],
            username=scope["username"],
            levels=scope["levels"],
            enable_advanced=scope["enable_advanced"],
            writable_advanced=scope["writable_advanced"],
            update_interval=scope["update_interval"],
        )

        # Erkennungsstand: erst Arbeitsspeicher, dann Platte, sonst neu lesen.
        store = Store(hass, DISCOVERY_STORE_VERSION, _store_key(entry, host))
        cache_key = f"{host}|{fingerprint}"
        restored = False
        # Nach einer Aktualisierung wird der bekannte Stand zwar benutzt, im
        # Hintergrund aber gegen die Anlage abgeglichen.
        abgleichen = False
        if (cached := mem_cache.get(cache_key)) is not None:
            client.restore_discovery(cached)
            restored = True
        else:
            stored = await store.async_load()
            if _discovery_cache_valid(stored, host, fingerprint):
                client.restore_discovery(stored["data"])
                mem_cache[cache_key] = stored["data"]
                restored = True
                abgleichen = _veraltet(stored, version)
                if abgleichen:
                    _LOGGER.info(
                        "%s: Erkennungsstand stammt aus Fassung %s – die Werte sind sofort "
                        "da, der Abgleich mit der Anlage läuft im Hintergrund.",
                        host,
                        stored.get("version"),
                    )

        if not restored:
            # Nur Grunddaten abwarten – der Vollabzug folgt im Hintergrund.
            try:
                async with asyncio.timeout(INIT_TIMEOUT):
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
        return host, label, coordinator, client, store, fingerprint, cache_key, restored, abgleichen

    begonnen = monotonic()
    ergebnisse = await asyncio.gather(*(_anlage_vorbereiten(s) for s in systeme))

    coordinators: dict[str, WindhagerDataUpdateCoordinator] = {}
    nachzuladen: list[tuple] = []
    for (
        host,
        label,
        coordinator,
        client,
        store,
        fingerprint,
        cache_key,
        restored,
        abgleichen,
    ) in ergebnisse:
        coordinators[host] = coordinator

        # Die Steuerung als Untergerät der Heizungsanlage. Ihre Kennung stammt
        # aus den Seriennummern der Anlage und übersteht damit einen Wechsel
        # der IP-Adresse; die alte, adressgebundene Kennung wird vorher
        # umgeschrieben.
        alte_kennung = f"{entry.entry_id}_{host}"
        kennung = steuerung_kennung(coordinator)
        if kennung != alte_kennung:
            _steuerung_umstellen(registry, alte_kennung, kennung)
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, kennung)},
            name=label,
            manufacturer="Windhager",
            model="Steuerung",
            via_device=(DOMAIN, entry.entry_id),
        )

        if not restored or abgleichen:
            nachzuladen.append((coordinator, client, store, host, fingerprint, cache_key, restored))

    _LOGGER.info(
        "%d Anlage(n) verbunden in %.1f s (%s)",
        len(coordinators),
        monotonic() - begonnen,
        ", ".join(f"{c.host}: {c.client.request_count} Anfragen" for c in coordinators.values()),
    )

    hintergrund: list = []
    hass.data[DOMAIN][entry.entry_id] = {
        "name": hub_name,
        "coordinators": coordinators,
        "hintergrund": hintergrund,
        # Der Umfang, mit dem dieser Eintrag geladen wurde. Ändert der Nutzer
        # ihn, lässt sich daran erkennen, ob er etwas abgewählt hat.
        "umfang": {system[CONF_HOST]: _scope(entry, system[CONF_HOST]) for system in systeme},
        # Anlagen, deren Vollabzug noch läuft – für die Meldung an den Nutzer.
        "einlesen_offen": {eintrag[3] for eintrag in nachzuladen},
    }
    # Erst die Kennungen umstellen, dann die Plattformen anlegen: Sonst
    # entstünden neben den umbenannten Einträgen zusätzlich neue.
    async_kennungen_umstellen(hass, entry, coordinators)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _geraetenamen_angleichen(registry, entry, coordinators)
    async_entity_ids_umstellen(hass, entry)
    _abgewaehlte_entitaeten_stilllegen(hass, entry, coordinators)

    if (entry.options or {}).get(CONF_DASHBOARD, True):
        await async_setup_dashboard(hass)
    else:
        # Abgewählt: der Seitenleisten-Eintrag verschwindet beim nächsten Laden.
        await async_remove_dashboard(hass)

    await _oberflaeche_anwenden(hass, bool((entry.options or {}).get(CONF_PANEL, False)), version)

    # Gemeldet wird nur das echte Ersteinlesen, nicht der Abgleich nach einem
    # Update – und auch das nur, wenn der Nutzer es eingeschaltet hat.
    if any(not eintrag[6] for eintrag in nachzuladen) and meldung_erwuenscht(entry.options):
        _einlesen_melden(hass, entry)

    for coordinator, client, store, host, fingerprint, cache_key, war_im_cache in nachzuladen:
        hintergrund.append(
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
                    war_im_cache,
                ),
                name=f"{DOMAIN}_vollabzug_{host}",
            )
        )

    return True


def _meldungs_id(entry: ConfigEntry) -> str:
    """Kennung der Einlese-Meldung dieses Eintrags."""
    return f"{DOMAIN}_einlesen_{entry.entry_id}"


def meldung_erwuenscht(optionen) -> bool:
    """Prüfen, ob die Meldungen zum Einlesen erscheinen sollen.

    Beide Meldungen – „liest die Anlage ein" und „ist bereit" – hängen an
    derselben Option und teilen sich eine Kennung: Die zweite *ersetzt* die
    erste. Prüft nur eine von beiden die Option, erscheint die andere aus dem
    Nichts. Genau das passierte bis 1.2.0-beta.4 mit der Abschlussmeldung.
    """
    return bool((optionen or {}).get(CONF_MELDUNG_EINLESEN, False))


def _entitaeten_anzahl(hass: HomeAssistant, entry: ConfigEntry) -> int:
    """Wie viele Entitäten dieser Eintrag angelegt hat."""
    return len(er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id))


def _einlesen_melden(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ankündigen, dass die Anlage noch eingelesen wird.

    Eine Anlage liefert ihre Datenpunkte nicht auf einen Schlag: Zuerst
    entsteht der Grundstock, der Rest kommt über den Vollabzug im Hintergrund
    nach. Ohne Hinweis sieht der Nutzer eine Handvoll Entitäten und hält die
    Einrichtung für gescheitert.
    """
    persistent_notification.async_create(
        hass,
        (
            f"**{entry.title}** wird gerade vollständig eingelesen.\n\n"
            f"Bisher angelegt: {_entitaeten_anzahl(hass, entry)} Entitäten. "
            "Je nach Anlage dauert es 30 bis 120 Sekunden, bis alle Werte da "
            "sind – Sie müssen nichts tun, die Meldung meldet sich wieder."
        ),
        title="HeatNexus liest die Anlage ein",
        notification_id=_meldungs_id(entry),
    )


def _einlesen_abgeschlossen(hass: HomeAssistant, entry: ConfigEntry, host: str) -> None:
    """Eine Anlage ist durch; sind alle durch, das Ergebnis melden."""
    daten = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not isinstance(daten, dict):
        return
    offen = daten.get("einlesen_offen")
    if not isinstance(offen, set):
        return
    offen.discard(host)
    if offen:
        return
    if not meldung_erwuenscht(entry.options):
        return

    persistent_notification.async_create(
        hass,
        (
            f"**{entry.title}** ist vollständig eingelesen: "
            f"{_entitaeten_anzahl(hass, entry)} Entitäten.\n\n"
            "Fachparameter der Service- und Werksebene sind bewusst "
            "deaktiviert angelegt; sie lassen sich einzeln einschalten."
        ),
        title="HeatNexus ist bereit",
        notification_id=_meldungs_id(entry),
    )


def _umfang_verkleinert(alt: dict[str, dict], neu: dict[str, dict]) -> bool:
    """Prüfen, ob der Nutzer am Umfang etwas abgewählt hat.

    Nur dann werden Entitäten wirklich gelöscht. Fällt dagegen ein Datenpunkt
    weg, weil ihn die Anlage nicht mehr liefert, steckt keine Entscheidung
    dahinter – dort wird nur stillgelegt.
    """
    for host, alt_umfang in alt.items():
        neu_umfang = neu.get(host)
        if neu_umfang is None:
            return True
        if set(neu_umfang["levels"]) < set(alt_umfang["levels"]):
            return True
        if alt_umfang["enable_advanced"] and not neu_umfang["enable_advanced"]:
            return True
    return False


def _abwahl_vormerken(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Merken, dass der nächste Ladevorgang nach einer Abwahl aufräumen darf."""
    hass.data.setdefault(DOMAIN, {}).setdefault("_abwahl", set()).add(entry.entry_id)


def _abwahl_abholen(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Die Vormerkung einlösen – sie gilt genau einmal."""
    offen = hass.data.get(DOMAIN, {}).get("_abwahl")
    if not isinstance(offen, set) or entry.entry_id not in offen:
        return False
    offen.discard(entry.entry_id)
    return True


def _abgewaehlte_entitaeten_stilllegen(
    hass: HomeAssistant, entry: ConfigEntry, coordinators: dict
) -> None:
    """Entitäten aufräumen, die es nach der aktuellen Auswahl nicht mehr gibt.

    Was mit ihnen geschieht, hängt davon ab, **warum** sie weg sind:

    * Der Nutzer hat eine Bedienebene **abgewählt** – eine bewusste
      Entscheidung. Dann werden die Einträge gelöscht, sonst stünden sie
      dauerhaft als abgeschaltete Zeilen in der Integrationsübersicht.
    * Die Anlage liefert den Datenpunkt nicht mehr (Umbau, andere Firmware).
      Dann werden sie nur **stillgelegt**: Kommt er zurück, sind eigene Namen,
      Symbole, Bereichszuordnung und Verlauf noch da.
    """
    vollstaendig = all(getattr(c.client, "_vollstaendig", False) for c in coordinators.values())
    if not vollstaendig:
        # Vor dem Vollabzug ist die Liste noch unvollständig – nichts anfassen.
        return

    loeschen = _abwahl_abholen(hass, entry)

    # Entitäten der Serviceebene sind absichtlich deaktiviert angelegt; sie
    # dürfen beim Wiederdazuwählen nicht versehentlich eingeschaltet werden.
    standardmaessig_an = {
        beschreibung.get("id"): beschreibung.get("enabled_default", True)
        for coordinator in coordinators.values()
        for beschreibung in (coordinator.data or {}).get("devices", [])
    }
    registry = er.async_get(hass)
    entfernt = 0
    for eintrag in list(er.async_entries_for_config_entry(registry, entry.entry_id)):
        if eintrag.unique_id not in standardmaessig_an:
            if loeschen:
                registry.async_remove(eintrag.entity_id)
                entfernt += 1
            elif eintrag.disabled_by is None:
                _LOGGER.debug("Lege abgewählte Entität %s still", eintrag.entity_id)
                registry.async_update_entity(
                    eintrag.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
                )
        elif (
            standardmaessig_an[eintrag.unique_id]
            and eintrag.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        ):
            # Wieder dazugewählt – die eigene Stilllegung wird aufgehoben.
            # Eine Abschaltung durch den Nutzer (disabled_by USER) bleibt.
            _LOGGER.debug("Nehme %s wieder in Betrieb", eintrag.entity_id)
            registry.async_update_entity(eintrag.entity_id, disabled_by=None)

    if entfernt:
        _LOGGER.info(
            "%d Entitäten entfernt, weil ihre Bedienebene abgewählt wurde. "
            "Beim Wiederdazuwählen werden sie neu angelegt.",
            entfernt,
        )


async def _oberflaeche_anwenden(hass: HomeAssistant, gewuenscht: bool, version: str = "") -> None:
    """Die eigene Oberfläche an- oder abmelden.

    Erst hier importiert: Sie ist eine Beigabe, und ein Problem mit ihr darf
    nicht die ganze Integration lahmlegen. Fehlt die Datei – etwa weil eine
    Aktualisierung unvollständig kopiert wurde –, laufen Entitäten und
    Dashboard trotzdem weiter.
    """
    try:
        from .panel import async_remove_panel, async_setup_panel
    except ImportError as err:
        _LOGGER.warning("Eigene Oberfläche nicht verfügbar: %s", err)
        return

    if gewuenscht:
        await async_setup_panel(hass, version)
    else:
        await async_remove_panel(hass)


def _steuerung_umstellen(registry, alt: str, neu: str) -> None:
    """Die Kennung des Steuerungs-Geräts auf die Seriennummer umschreiben."""
    geraet = registry.async_get_device(identifiers={(DOMAIN, alt)})
    if geraet is None or registry.async_get_device(identifiers={(DOMAIN, neu)}) is not None:
        return
    kennungen = {i for i in geraet.identifiers if i != (DOMAIN, alt)}
    kennungen.add((DOMAIN, neu))
    registry.async_update_device(geraet.id, new_identifiers=kennungen)
    _LOGGER.debug("Kennung der Steuerung %s -> %s", alt, neu)


def _geraetenamen_angleichen(registry, entry: ConfigEntry, coordinators: dict) -> None:
    """Namen bestehender Geräte an das aktuelle Schema angleichen.

    Home Assistant übernimmt geänderte Gerätenamen nicht immer von selbst.
    Eine eigene Umbenennung durch den Nutzer bleibt unangetastet.
    """
    for coordinator in coordinators.values():
        steuerung = registry.async_get_device(
            identifiers={(DOMAIN, steuerung_kennung(coordinator))}
        )
        for beschreibung in (coordinator.data or {}).get("devices", []):
            kennung = beschreibung.get("device_id")
            funktion = (beschreibung.get("device_name") or "").strip()
            if not kennung or not funktion:
                continue
            geraet = registry.async_get_device(identifiers={(DOMAIN, kennung)})
            if geraet is None:
                continue
            gewuenscht = f"{coordinator.label} · {funktion}"
            if (
                coordinator.label
                and coordinator.label != funktion
                and geraet.name != gewuenscht
                and steuerung is not None
            ):
                registry.async_update_device(geraet.id, name=gewuenscht, via_device_id=steuerung.id)


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
    war_im_cache: bool = False,
) -> None:
    """Die Anlage im Hintergrund vollständig einlesen.

    Home Assistant läuft zu diesem Zeitpunkt bereits; die zusätzlich
    gefundenen Entitäten werden anschließend nachgemeldet.

    Mit ``war_im_cache`` ist es kein Ersteinlesen, sondern der Abgleich nach
    einer Aktualisierung: Die Anzeige steht schon, hier kommt nur dazu, was
    die neue Fassung zusätzlich erkennt.
    """
    try:
        await client.async_init(erzwingen=war_im_cache)
    except asyncio.CancelledError:
        # Der Eintrag wird gerade entladen – kein Grund für eine Warnung.
        raise
    except Exception as err:
        _LOGGER.warning("%s konnte nicht vollständig eingelesen werden: %s", host, err)
        _einlesen_abgeschlossen(hass, entry, host)
        return

    await coordinator.async_refresh()
    async_dispatcher_send(hass, SIGNAL_NEUE_ENTITAETEN.format(entry.entry_id))
    daten = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if daten:
        _abgewaehlte_entitaeten_stilllegen(hass, entry, daten["coordinators"])

    # Die nachgemeldeten Entitäten werden erst angelegt, nachdem dieser Ablauf
    # den Dispatcher verlassen hat – die Erfolgsmeldung wartet das ab, sonst
    # nennt sie eine zu kleine Zahl.
    async_call_later(
        hass, MELDUNG_VERZOEGERUNG, lambda _jetzt: _einlesen_abgeschlossen(hass, entry, host)
    )

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
    """Nach geänderten Optionen neu laden (anderer Umfang = andere Entitäten).

    Vorher wird festgehalten, ob dabei etwas *abgewählt* wurde: Nur dann darf
    der nächste Ladevorgang die betroffenen Entitäten wirklich entfernen.
    """
    alt = (hass.data.get(DOMAIN, {}).get(entry.entry_id) or {}).get("umfang") or {}
    neu = {system[CONF_HOST]: _scope(entry, system[CONF_HOST]) for system in _systems(entry)}
    if alt and _umfang_verkleinert(alt, neu):
        _abwahl_vormerken(hass, entry)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Einen Konfigurationseintrag entladen."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        daten = hass.data[DOMAIN].pop(entry.entry_id, {})
        # Erst den Vollabzug beenden, dann die Verbindung schließen. Andersherum
        # läuft die Hintergrundaufgabe in eine geschlossene Verbindung und
        # meldet „Connector is closed".
        for aufgabe in daten.get("hintergrund", []):
            aufgabe.cancel()
        for aufgabe in daten.get("hintergrund", []):
            with contextlib.suppress(asyncio.CancelledError):
                await aufgabe
        for coordinator in daten.get("coordinators", {}).values():
            await coordinator.client.close()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Gespeicherten Erkennungsstand und Dashboard abräumen."""
    persistent_notification.async_dismiss(hass, _meldungs_id(entry))
    for system in _systems(entry):
        await Store(
            hass, DISCOVERY_STORE_VERSION, _store_key(entry, system[CONF_HOST])
        ).async_remove()
    if not hass.config_entries.async_entries(DOMAIN):
        await async_remove_dashboard(hass)
        await _oberflaeche_anwenden(hass, False)
