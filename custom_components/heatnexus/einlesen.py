"""Der Vollabzug im Hintergrund und die Meldungen dazu.

`async_setup_entry` liest nur den Kern; hier läuft der Rest, legt den
Erkennungsstand ab und meldet, wenn alle Anlagen durch sind.
"""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import CONF_MELDUNG_EINLESEN, DOMAIN, SIGNAL_NEUE_ENTITAETEN
from .erkennungsstand import laufzeitdaten, umfang_der_anlage
from .stilllegung import abgewaehlte_entitaeten_stilllegen

_LOGGER = logging.getLogger(__name__)


# Sekunden, die die Erfolgsmeldung dem Anlegen der nachgemeldeten Entitäten
# einräumt.
MELDUNG_VERZOEGERUNG = 10


def meldungs_id(entry: ConfigEntry) -> str:
    """Kennung der Einlese-Meldung dieses Eintrags."""
    return f"{DOMAIN}_einlesen_{entry.entry_id}"


def meldung_erwuenscht(optionen) -> bool:
    """Prüfen, ob die Meldungen zum Einlesen erscheinen sollen.

    Beide Meldungen – „liest die Anlage ein" und „ist bereit" – hängen an
    derselben Option und teilen sich eine Kennung: Die zweite *ersetzt* die
    erste. Prüft nur eine von beiden die Option, erscheint die andere aus dem
    Nichts.
    """
    return bool((optionen or {}).get(CONF_MELDUNG_EINLESEN, False))


def _entitaeten_anzahl(hass: HomeAssistant, entry: ConfigEntry) -> int:
    """Wie viele Entitäten dieser Eintrag angelegt hat."""
    return len(er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id))


def einlesen_melden(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ankündigen, dass die Anlage noch eingelesen wird.

    Eine Anlage liefert ihre Datenpunkte nicht auf einen Schlag: Zuerst
    entsteht der Grundstock, der Rest kommt über den Vollabzug im Hintergrund
    nach. Ohne Hinweis sieht der Nutzer eine Handvoll Entitäten und hält die
    Einrichtung für gescheitert.
    """
    if not meldung_erwuenscht(entry.options):
        return
    persistent_notification.async_create(
        hass,
        (
            f"**{entry.title}** wird gerade vollständig eingelesen.\n\n"
            f"Bisher angelegt: {_entitaeten_anzahl(hass, entry)} Entitäten. "
            "Je nach Anlage dauert es 30 bis 120 Sekunden, bis alle Werte da "
            "sind – Sie müssen nichts tun, die Meldung meldet sich wieder."
        ),
        title="HeatNexus liest die Anlage ein",
        notification_id=meldungs_id(entry),
    )


def _einlesen_abgeschlossen(hass: HomeAssistant, entry: ConfigEntry, host: str) -> None:
    """Eine Anlage ist durch; sind alle durch, das Ergebnis melden."""
    daten = laufzeitdaten(entry)
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
        notification_id=meldungs_id(entry),
    )


async def vollabzug(
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
    daten = laufzeitdaten(entry)
    if daten:
        abgewaehlte_entitaeten_stilllegen(hass, entry, daten["coordinators"])

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
            # Der Umfang zusätzlich zum Fingerabdruck: Die Zeichenkette sagt,
            # *dass* sich etwas geändert hat, das Wörterbuch sagt *was*.
            "umfang": umfang_der_anlage(hass, entry, host),
            # Die Sprache steht hier und nicht im Fingerabdruck: Ein Wechsel
            # macht den Stand nicht ungültig, er löst nur den Abgleich aus.
            "sprache": client.sprache,
            "saved": dt_util.utcnow().isoformat(),
            "data": data,
        }
    )
