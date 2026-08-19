"""Bestehende Einträge auf die dauerhaften Kennungen umstellen.

Bis 0.1.0-beta.18 hingen Geräte- und Entitätskennungen an der IP-Adresse der
Anlage (``192-168-178-100-1-60-0-0-7-0``). Ein Adresswechsel legte damit alles
neu an: eigene Namen, Bereichszuordnung, Verlauf und Automationen waren weg.

Seit beta.19 tragen sie die ``neuronId`` – die Seriennummer des Bausteins, die
die Anlage in ihrer Struktur mitliefert. Sie bleibt gleich, egal unter welcher
Adresse die Anlage erreichbar ist.

Dieses Modul benennt vorhandene Einträge einmalig um. Die Zuordnung ist
eindeutig, weil jede Beschreibung beide Kennungen kennt: ``alt_id`` die
frühere, ``id`` die neue. Nichts wird gelöscht und nichts neu angelegt –
alle Anpassungen des Nutzers bleiben damit erhalten.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Kennungsendungen, deren ``entity_id`` bleibt. Ihr Anzeigename darf sich
# ändern, ihre Kennung nicht: Sie steckt in fremden Automationen und Karten.
BLEIBENDE_KENNUNGEN = ("-laufzeit", "-laufzeit-heute")


def _beschreibungen(coordinators: dict) -> list[dict[str, Any]]:
    return [
        beschreibung
        for coordinator in coordinators.values()
        for beschreibung in (coordinator.data or {}).get("devices", [])
    ]


def _geraete_umstellen(hass: HomeAssistant, beschreibungen: list[dict[str, Any]]) -> int:
    """Gerätekennungen von der Adresse auf die Seriennummer umstellen."""
    registry = dr.async_get(hass)
    paare = {
        b["alt_device_id"]: b["device_id"]
        for b in beschreibungen
        if b.get("alt_device_id") and b.get("device_id") and b["alt_device_id"] != b["device_id"]
    }

    umgestellt = 0
    for alt, neu in paare.items():
        geraet = registry.async_get_device(identifiers={(DOMAIN, alt)})
        if geraet is None:
            continue
        if registry.async_get_device(identifiers={(DOMAIN, neu)}) is not None:
            # Das Ziel gibt es schon – dann ist die Umstellung gelaufen und
            # dies hier ein Überbleibsel.
            continue
        kennungen = {i for i in geraet.identifiers if i != (DOMAIN, alt)}
        kennungen.add((DOMAIN, neu))
        registry.async_update_device(geraet.id, new_identifiers=kennungen)
        umgestellt += 1
        _LOGGER.debug("Gerätekennung %s -> %s", alt, neu)
    return umgestellt


def _entitaeten_umstellen(
    hass: HomeAssistant, entry: ConfigEntry, beschreibungen: list[dict[str, Any]]
) -> int:
    """Entitätskennungen umstellen."""
    registry = er.async_get(hass)
    paare = {
        b["alt_id"]: b["id"]
        for b in beschreibungen
        if b.get("alt_id") and b.get("id") and b["alt_id"] != b["id"]
    }
    vorhanden = {
        eintrag.unique_id: eintrag
        for eintrag in er.async_entries_for_config_entry(registry, entry.entry_id)
    }

    umgestellt = 0
    for alt, neu in paare.items():
        eintrag = vorhanden.get(alt)
        if eintrag is None or neu in vorhanden:
            continue
        registry.async_update_entity(eintrag.entity_id, new_unique_id=neu)
        umgestellt += 1
        _LOGGER.debug("Entitätskennung %s -> %s", alt, neu)
    return umgestellt


def _freie_kennung(registry: er.EntityRegistry, eintrag: Any, gewuenscht: str) -> str:
    """Eine freie ``entity_id`` vorschlagen, über die Fassungen hinweg.

    Drei Bauarten sind im Umlauf: mit eigener Kennung als Ausnahme, ohne sie,
    und unter neuem Namen. Ohne alle drei bricht die Angleichung beim Start.
    """
    if (neuere := getattr(registry, "async_get_available_entity_id", None)) is not None:
        return neuere(eintrag.domain, gewuenscht, current_entity_id=eintrag.entity_id)
    try:
        return registry.async_generate_entity_id(
            eintrag.domain, gewuenscht, current_entity_id=eintrag.entity_id
        )
    except TypeError:
        return registry.async_generate_entity_id(eintrag.domain, gewuenscht)


def _entity_ids_umstellen(hass: HomeAssistant, entry: ConfigEntry) -> int:
    """Entitäts-IDs auf das Schema „Gerät + Datenpunkt" bringen.

    Umbenannt wird nur bei freiem Zielnamen; eine vom Nutzer benannte Entität
    bleibt unangetastet, dort steckt eine Entscheidung drin.
    """
    registry = er.async_get(hass)
    geraete = dr.async_get(hass)

    umbenannt = 0
    for eintrag in list(er.async_entries_for_config_entry(registry, entry.entry_id)):
        if eintrag.name:
            continue
        if str(eintrag.unique_id or "").endswith(BLEIBENDE_KENNUNGEN):
            continue
        geraet = geraete.async_get(eintrag.device_id) if eintrag.device_id else None
        if geraet is None:
            continue
        geraetename = geraet.name_by_user or geraet.name or ""
        teile = [geraetename]
        if eintrag.original_name:
            teile.append(eintrag.original_name)
        # `async_generate_entity_id` ist seit HA 2027.2 abgekündigt; die neue
        # Funktion heißt anders und gibt es in älteren Fassungen noch nicht.
        # Deshalb erst die neue versuchen, dann die alte.
        vorschlag = _freie_kennung(registry, eintrag, " ".join(t for t in teile if t))
        if vorschlag == eintrag.entity_id:
            continue
        # Ein angehängter Zähler heißt: Der eigentliche Name ist belegt. Dann
        # bringt die Umbenennung nichts und wird gelassen.
        if vorschlag.rsplit("_", 1)[-1].isdigit():
            continue
        registry.async_update_entity(eintrag.entity_id, new_entity_id=vorschlag)
        umbenannt += 1
        _LOGGER.debug("Entität %s -> %s", eintrag.entity_id, vorschlag)
    return umbenannt


def async_kennungen_umstellen(hass: HomeAssistant, entry: ConfigEntry, coordinators: dict) -> None:
    """Die einmalige Umstellung ausführen.

    Läuft bei jedem Start, findet danach aber nichts mehr zu tun: Die alten
    Kennungen existieren dann nicht mehr.
    """
    beschreibungen = _beschreibungen(coordinators)
    if not beschreibungen:
        return

    geraete = _geraete_umstellen(hass, beschreibungen)
    entitaeten = _entitaeten_umstellen(hass, entry, beschreibungen)
    if geraete or entitaeten:
        _LOGGER.info(
            "Auf dauerhafte Kennungen umgestellt: %d Geräte, %d Entitäten. "
            "Ein Wechsel der IP-Adresse legt jetzt nichts mehr neu an.",
            geraete,
            entitaeten,
        )


def async_entity_ids_umstellen(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Die Entitäts-IDs an das Namensschema angleichen."""
    umbenannt = _entity_ids_umstellen(hass, entry)
    if umbenannt:
        _LOGGER.info(
            "%d Entitäten umbenannt – die Kennung enthält jetzt Anlage und Anlagenteil.",
            umbenannt,
        )
