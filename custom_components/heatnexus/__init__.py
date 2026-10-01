"""HeatNexus – Heizungen in Home Assistant."""

from __future__ import annotations

import asyncio
import contextlib
from copy import deepcopy
import logging

# Nur die Funktion, nicht das Modul: Diese Datei *ist* der Namensraum des
# Pakets. Sobald Home Assistant die Plattform `heatnexus.time` lädt, setzt
# Python sie als Attribut `time` auf das Paket – und überschreibt damit ein
# hier stehendes `import time`. Danach zeigt `time.monotonic` auf die
# Plattformdatei und der Aufruf scheitert. Ob das passiert, hing bisher am
# Wettlauf zwischen Plattform-Import und Einrichtung.
from time import monotonic
from types import MappingProxyType
from typing import NamedTuple

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_integration

from . import device_db, error_texts, verwaiste, waermequelle
from .automatik.verwaltung import verwaltung_holen
from .blueprints import async_install_blueprints
from .client import WindhagerHttpClient
from .const import (
    CONF_DASHBOARD,
    CONF_LABEL,
    CONF_MARKEN,
    CONF_PANEL,
    CONF_QUELLEN,
    CONF_STARTWERTE,
    CONF_VORLAGEN,
    DISCOVERY_STORE_VERSION,
    DOMAIN,
    INIT_TIMEOUT,
    STARTWERTE_VORGABE,
    SUBEINTRAG_QUELLE,
)
from .coordinator import WindhagerDataUpdateCoordinator
from .dashboard import async_remove_dashboard, async_setup_dashboard
from .dienste import async_register_dashboard_export, async_register_rediscover_service
from .einlesen import meldungs_id, vollabzuege_starten
from .entity import steuerung_info, steuerung_kennung
from .erkennungsstand import (
    abgleich_noetig,
    discovery_cache_valid,
    laufzeitdaten,
    laufzeitdaten_anlegen,
    neustart_hinweis,
    nur_anzeige_geaendert,
    nur_automatik_untereintrag_geaendert,
    store_key,
    systems,
    umfang_der_anlage,
    umfang_fingerprint,
    untereintraege_abzug,
)
from .exceptions import mit_text
from .karte import async_setup_karte
from .migration import (
    async_entity_ids_umstellen,
    async_kennungen_umstellen,
    geraetenamen_angleichen,
    steuerung_umstellen,
)
from .registrierung import uebergeordnet
from .stilllegung import (
    abgewaehlte_entitaeten_stilllegen,
    abwahl_im_stand,
    abwahl_vormerken,
    umfang_verkleinert,
)
from .texte import woerterbuch

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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Wärmequellen aus den Optionen in eigene Subeinträge überführen.

    Ihre Kennung wandert mit; an ihr hängt die Entität, und ein neuer Wert
    würde Name, Bereich und Verlauf verlieren.
    """
    if entry.version != 2 or entry.minor_version >= 2:
        return True

    optionen = dict(entry.options)
    for host, je_anlage in list(optionen.items()):
        if not isinstance(je_anlage, dict) or CONF_QUELLEN not in je_anlage:
            continue
        for quelle in waermequelle.quellen_pruefen(je_anlage.get(CONF_QUELLEN)):
            hass.config_entries.async_add_subentry(
                entry,
                ConfigSubentry(
                    data=MappingProxyType(
                        {
                            CONF_HOST: host,
                            "id": quelle["id"],
                            "art": quelle["art"],
                            "pumpe": quelle["pumpe"],
                            "bedingung": quelle["bedingung"],
                        }
                    ),
                    subentry_type=SUBEINTRAG_QUELLE,
                    title=quelle["name"],
                    unique_id=None,
                ),
            )
        optionen[host] = {k: v for k, v in je_anlage.items() if k != CONF_QUELLEN}

    hass.config_entries.async_update_entry(entry, options=optionen, minor_version=2)
    return True


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Die Dienste anmelden, bevor eine Anlage eingerichtet ist.

    Sie hängen nicht an einem einzelnen Konfigurationseintrag: `rediscover`
    liest alle ein. Angemeldet in `async_setup_entry` gäbe es den Dienst ohne
    eingerichtete Anlage gar nicht – eine Automation, die ihn aufruft, wäre
    schon beim Speichern ungültig.
    """
    hass.data.setdefault(DOMAIN, {})
    async_register_rediscover_service(hass)
    async_register_dashboard_export(hass)
    # Das Kartenmodul steht vor jeder Anlage bereit: Eine Seite, die während der
    # Einrichtung lädt, kennt es sonst nicht. Es hängt nicht am Panel-Schalter.
    integration = await async_get_integration(hass, DOMAIN)
    await async_setup_karte(hass, str(integration.version))
    return True


def _marken_je_anlage_uebernehmen(
    hass: HomeAssistant, entry: ConfigEntry, systeme: list[dict]
) -> None:
    """Eine allgemeine Labelauswahl in die Anlagen übernehmen.

    Die Auswahl gehört zur Anlage; gemeinsam gewählt stünde dieselbe Karte
    an jeder Anlage.
    """
    optionen = dict(entry.options or {})
    gewaehlt = optionen.pop(CONF_MARKEN, None)
    if not gewaehlt:
        return
    for system in systeme:
        host = system.get(CONF_HOST)
        je_anlage = dict(optionen.get(host) or {})
        je_anlage.setdefault(CONF_MARKEN, list(gewaehlt))
        optionen[host] = je_anlage
    hass.config_entries.async_update_entry(entry, options=optionen)


class _Anlage(NamedTuple):
    """Eine verbundene Anlage mit allem, was Plattformen und Vollabzug brauchen."""

    host: str
    label: str
    coordinator: WindhagerDataUpdateCoordinator
    client: WindhagerHttpClient
    store: Store
    fingerprint: str
    cache_key: str
    restored: bool
    abgleichen: bool


def _client_bauen(system: dict, scope: dict) -> WindhagerHttpClient:
    """Den Client einer Anlage mit ihrem Umfang anlegen."""
    return WindhagerHttpClient(
        host=system[CONF_HOST],
        password=system[CONF_PASSWORD],
        username=scope["username"],
        levels=scope["levels"],
        enable_advanced=scope["enable_advanced"],
        writable_advanced=scope["writable_advanced"],
        zeitwerte=scope["zeitwerte"],
        zusatzwerte=scope["zusatzwerte"],
        lon=scope["lon"],
        lon_grundumfang=scope["lon_grundumfang"],
        update_interval=scope["update_interval"],
        sprache=scope["sprache"],
    )


async def _erkennungsstand_laden(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: WindhagerHttpClient,
    store: Store,
    host: str,
    scope: dict,
    fingerprint: str,
    cache_key: str,
    mem_cache: dict,
    version: str,
) -> tuple[bool, bool]:
    """Den Erkennungsstand übernehmen: erst Arbeitsspeicher, dann Platte.

    Liefert, ob ein Stand übernommen wurde und ob er im Hintergrund gegen die
    Anlage abzugleichen ist – das gilt nach einer Aktualisierung.
    """
    if (cached := mem_cache.get(cache_key)) is not None:
        client.restore_discovery(cached)
        return True, False
    stored = await store.async_load()
    # Ein kleiner gewordener Umfang verwirft den Stand – und genau
    # hier ist die Abwahl noch ablesbar.
    if abwahl_im_stand(stored, scope):
        abwahl_vormerken(hass, entry)
    if not discovery_cache_valid(stored, host, fingerprint):
        return False, False
    client.restore_discovery(stored["data"])
    mem_cache[cache_key] = stored["data"]
    abgleichen = abgleich_noetig(stored, version, scope["sprache"])
    neustart_hinweis(hass, entry, host, stored.get("sprache", "de") != scope["sprache"])
    if abgleichen:
        _LOGGER.info(
            "%s: Erkennungsstand stammt aus Fassung %s und Sprache %s – die "
            "Werte sind sofort da, der Abgleich mit der Anlage läuft im "
            "Hintergrund.",
            host,
            stored.get("version"),
            stored.get("sprache", "de"),
        )
    return True, abgleichen


async def _grunddaten_lesen(client: WindhagerHttpClient, host: str) -> None:
    """Nur die Grunddaten abwarten – der Vollabzug folgt im Hintergrund."""
    try:
        async with asyncio.timeout(INIT_TIMEOUT):
            await client.async_init_basic()
    except TimeoutError as err:
        await client.close()
        raise mit_text(ConfigEntryNotReady, "verbinden_zeitueberschreitung", anlage=host) from err
    except Exception as err:
        await client.close()
        raise mit_text(ConfigEntryNotReady, "verbinden_fehler", anlage=host, fehler=err) from err


async def _geraeteinfo_nachholen(
    client: WindhagerHttpClient, mem_cache: dict, cache_key: str
) -> None:
    """Modell und Firmwarestand zu einem Erkennungsstand ohne sie nachlesen.

    Zwei Anfragen genügen, statt bis zum nächsten Neu-Einlesen ein Gerät ohne
    diese Angaben zu zeigen.
    """
    with contextlib.suppress(Exception):
        await client._lese_geraeteinfo()
        await client._lese_knotendaten()
        # Gleich in den Zwischenspeicher zurück, sonst zahlt jedes
        # weitere Laden dieselben zwei Anfragen erneut.
        mem_cache[cache_key] = client.export_discovery()


async def _vorabstand_setzen(
    entry: ConfigEntry,
    client: WindhagerHttpClient,
    coordinator: WindhagerDataUpdateCoordinator,
    host: str,
) -> None:
    """Den ersten Stand aus dem Lesespeicher der Anlage übernehmen.

    Damit entstehen die Entitäten gleich mit Wert; der erste Abruf
    überschreibt ihn wenige Sekunden später.
    """
    try:
        stand = await client.vorabstand(
            int((entry.options or {}).get(CONF_STARTWERTE, STARTWERTE_VORGABE))
        )
    except Exception as fehler:
        # Der Vorabstand ist eine Beigabe; ein Fehler darf die Einrichtung
        # nicht anhalten, aber auch nicht spurlos bleiben.
        _LOGGER.debug("%s: kein Vorabstand: %s", host, fehler)
    else:
        if stand:
            coordinator.async_set_updated_data(stand)


async def _anlage_vorbereiten(
    hass: HomeAssistant, entry: ConfigEntry, system: dict, mem_cache: dict, version: str
) -> _Anlage:
    """Eine Anlage verbinden und ihren ersten Abruf machen.

    Bewusst als eigene Aufgabe: Nacheinander eingerichtet wartet jede
    Anlage, bis die vorige ihren vollständigen Erstabruf hinter sich hat.
    Da sie über getrennte Verbindungen laufen, gibt es keinen Grund dafür.
    """
    host = system[CONF_HOST]
    label = system.get(CONF_LABEL) or host
    scope = umfang_der_anlage(hass, entry, host)
    fingerprint = umfang_fingerprint(scope)
    client = _client_bauen(system, scope)

    store = Store(hass, DISCOVERY_STORE_VERSION, store_key(entry, host))
    # Die Sprache gehört in den Schlüssel, nicht in den Fingerabdruck: Ein
    # Wechsel soll den Stand von der Platte holen und abgleichen, statt
    # den Stand im Arbeitsspeicher unverändert weiterzureichen.
    cache_key = f"{host}|{fingerprint}|{scope['sprache']}"
    restored, abgleichen = await _erkennungsstand_laden(
        hass, entry, client, store, host, scope, fingerprint, cache_key, mem_cache, version
    )
    if not restored:
        await _grunddaten_lesen(client, host)
    if restored and not client.geraeteinfo:
        await _geraeteinfo_nachholen(client, mem_cache, cache_key)

    coordinator = WindhagerDataUpdateCoordinator(
        hass, client, entry, host, label, scope["update_interval"]
    )
    await _vorabstand_setzen(entry, client, coordinator, host)
    await coordinator.async_config_entry_first_refresh()
    return _Anlage(
        host, label, coordinator, client, store, fingerprint, cache_key, restored, abgleichen
    )


def _heizungsanlage_anmelden(
    hass: HomeAssistant, registry: dr.DeviceRegistry, entry: ConfigEntry, hub_name: str
) -> None:
    """Das übergeordnete Gerät anmelden: die Heizungsanlage als Ganzes."""
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=hub_name,
        manufacturer="Windhager",
        model=woerterbuch(hass)("Heizungsanlage"),
    )


def _steuerung_anmelden(
    hass: HomeAssistant, registry: dr.DeviceRegistry, entry: ConfigEntry, anlage: _Anlage
) -> None:
    """Die Steuerung als Untergerät der Heizungsanlage anmelden.

    Ihre Kennung stammt aus den Seriennummern und übersteht einen Wechsel der
    IP-Adresse; die alte, adressgebundene Kennung wird vorher umgeschrieben.
    """
    alte_kennung = f"{entry.entry_id}_{anlage.host}"
    kennung = steuerung_kennung(anlage.coordinator)
    if kennung != alte_kennung:
        steuerung_umstellen(registry, entry.entry_id, alte_kennung, kennung)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, kennung)},
        name=anlage.label,
        manufacturer="Windhager",
        **uebergeordnet(hass, entry.entry_id, entry.entry_id),
        **steuerung_info(anlage.coordinator),
    )


async def _entitaeten_einrichten(
    hass: HomeAssistant,
    entry: ConfigEntry,
    registry: dr.DeviceRegistry,
    coordinators: dict[str, WindhagerDataUpdateCoordinator],
) -> None:
    """Die Registrierung umstellen und die Plattformen anlegen."""
    # Erst die Kennungen umstellen, dann die Plattformen anlegen: Sonst
    # entstünden neben den umbenannten Einträgen zusätzlich neue.
    async_kennungen_umstellen(hass, entry, coordinators)
    # Vor den Plattformen: Ein Gerät, das noch am Haupteintrag hängt, stünde
    # sonst neben seinem Subeintrag ein zweites Mal in der Übersicht.
    waermequelle.geraete_entflechten(registry, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    geraetenamen_angleichen(registry, entry, coordinators)
    await verwaltung_holen(hass).eintrag_starten(entry)
    async_entity_ids_umstellen(hass, entry)
    # Beim ersten Lauf steht in der Registrierung noch der alte Anzeigename –
    # die Plattformen melden ihn erst danach an. Ein zweiter Lauf, sobald Home
    # Assistant steht, spart den Umweg über einen weiteren Start.
    entry.async_on_unload(
        async_at_started(hass, lambda _hass: async_entity_ids_umstellen(hass, entry))
    )
    abgewaehlte_entitaeten_stilllegen(hass, entry, coordinators)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Einen Konfigurationseintrag mit einer oder mehreren Anlagen einrichten."""
    systeme = systems(entry)
    if not systeme:
        raise mit_text(ConfigEntryNotReady, "keine_anlage_im_eintrag")

    _marken_je_anlage_uebernehmen(hass, entry, systeme)

    hass.data.setdefault(DOMAIN, {})
    async_register_rediscover_service(hass)
    async_register_dashboard_export(hass)
    await hass.async_add_executor_job(_preload_data)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    integration = await async_get_integration(hass, DOMAIN)
    version = str(integration.version)
    await async_install_blueprints(hass, version, (entry.options or {}).get(CONF_VORLAGEN))
    mem_cache = hass.data[DOMAIN].setdefault("_discovery_cache", {})
    hub_name = entry.data.get(CONF_NAME) or entry.title

    registry = dr.async_get(hass)
    _heizungsanlage_anmelden(hass, registry, entry, hub_name)

    begonnen = monotonic()
    anlagen = await asyncio.gather(
        *(_anlage_vorbereiten(hass, entry, s, mem_cache, version) for s in systeme)
    )

    coordinators: dict[str, WindhagerDataUpdateCoordinator] = {}
    nachzuladen: list[_Anlage] = []
    for anlage in anlagen:
        coordinators[anlage.host] = anlage.coordinator
        _steuerung_anmelden(hass, registry, entry, anlage)
        if not anlage.restored or anlage.abgleichen:
            nachzuladen.append(anlage)

    _LOGGER.info(
        "%d Anlage(n) verbunden in %.1f s (%s)",
        len(coordinators),
        monotonic() - begonnen,
        ", ".join(f"{c.host}: {c.client.request_count} Anfragen" for c in coordinators.values()),
    )

    hintergrund: list = []
    # Am Konfigurationseintrag, nicht in `hass.data`: Der Eintrag räumt seine
    # Laufzeitdaten selbst ab. In `hass.data` bleibt nur, was mehreren
    # Einträgen gehört (Erkennungsstände, vorgemerkte Abwahl).
    entry.runtime_data = laufzeitdaten_anlegen(
        hass,
        entry,
        hub_name,
        version,
        coordinators,
        hintergrund,
        {anlage.host for anlage in nachzuladen},
    )
    await _entitaeten_einrichten(hass, entry, registry, coordinators)

    await _oberflaechen_einrichten(hass, entry, version)

    hintergrund.extend(vollabzuege_starten(hass, entry, nachzuladen, mem_cache, version))
    return True


async def _oberflaechen_einrichten(hass: HomeAssistant, entry: ConfigEntry, version: str) -> None:
    """Dashboard und eigene Oberfläche nach den Optionen an- oder abmelden."""
    if (entry.options or {}).get(CONF_DASHBOARD, True):
        await async_setup_dashboard(hass)
    else:
        # Abgewählt: der Seitenleisten-Eintrag verschwindet beim nächsten Laden.
        await async_remove_dashboard(hass)

    await _oberflaeche_anwenden(hass, bool((entry.options or {}).get(CONF_PANEL, False)), version)


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


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Nach geänderten Optionen neu laden (anderer Umfang = andere Entitäten).

    Vorher wird festgehalten, ob dabei etwas *abgewählt* wurde: Nur dann darf
    der nächste Ladevorgang die betroffenen Entitäten wirklich entfernen.
    """
    daten = laufzeitdaten(entry) or {}
    untereintraege = untereintraege_abzug(entry)
    if dict(entry.options or {}) == daten.get("optionen") and nur_automatik_untereintrag_geaendert(
        daten.get("untereintraege") or {}, untereintraege
    ):
        daten["untereintraege"] = untereintraege
        await verwaltung_holen(hass).untereintrag_pruefen(entry)
        return
    if nur_anzeige_geaendert(daten.get("optionen") or {}, dict(entry.options or {})):
        # Das Dashboard wird bei jedem Öffnen neu gebaut, die Oberfläche nicht:
        # Sie trägt einen Abzug aus dem Augenblick der Anmeldung. Ohne
        # Auffrischen zeigte ihr erster Aufbau noch die alte Zeichnung.
        daten["optionen"] = deepcopy(dict(entry.options or {}))
        if (entry.options or {}).get(CONF_PANEL, False):
            integration = await async_get_integration(hass, DOMAIN)
            await _oberflaeche_anwenden(hass, True, str(integration.version))
        return
    alt = daten.get("umfang") or {}
    neu = {
        system[CONF_HOST]: umfang_der_anlage(hass, entry, system[CONF_HOST])
        for system in systems(entry)
    }
    if alt and umfang_verkleinert(alt, neu):
        abwahl_vormerken(hass, entry)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Einen Konfigurationseintrag entladen."""
    await verwaltung_holen(hass).eintrag_stoppen(entry)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        daten = laufzeitdaten(entry) or {}
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
        # Die Laufzeitdaten ausdrücklich abräumen. An ihnen hängen der
        # Zeitgeber der Einlese-Meldung und die Geräteliste des Dashboards;
        # bleiben sie stehen, meldet HeatNexus eine Anlage als bereit, die es
        # nicht mehr gibt.
        entry.runtime_data = None
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Gespeicherten Erkennungsstand und Dashboard abräumen."""
    await verwaltung_holen(hass).eintrag_entfernt(entry.entry_id)
    persistent_notification.async_dismiss(hass, meldungs_id(entry))
    verwaiste.hinweis_pflegen(hass, entry, 0)
    for system in systems(entry):
        await Store(
            hass, DISCOVERY_STORE_VERSION, store_key(entry, system[CONF_HOST])
        ).async_remove()
    if not hass.config_entries.async_entries(DOMAIN):
        await async_remove_dashboard(hass)
        await _oberflaeche_anwenden(hass, False)
