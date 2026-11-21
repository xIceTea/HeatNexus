"""Registrierte Entitäten und Geräte ohne Datenpunkt finden, melden und entfernen.

Eine verwaiste Entität entsteht, wenn die Anlage einen Datenpunkt nicht mehr
liefert oder eine neue Fassung ihn nicht mehr anlegt. Stillgelegt wird sie
sofort, entfernt erst auf Ansage: Löschen kostet Name, Bereich und Verlauf.
"""

from __future__ import annotations

import logging
import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from . import waermequelle
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCHLUESSEL = "verwaiste_entitaeten"
HINWEIS = SCHLUESSEL + "_{entry_id}"
# Merkmal in den Entitätsoptionen der Registrierung: Der Nutzer behält die Entität.
BEHALTEN = "behalten"


def _automatik(hass: HomeAssistant | None, entry: ConfigEntry) -> dict[str, str]:
    # Die Entitäten einer Automatik hängen an keinem Datenpunkt der Anlage.
    if hass is None:
        return {}
    from .automatik.verwaltung import verwaltung_holen

    return verwaltung_holen(hass).kennungen(entry.entry_id)


def _stoerspeicher(coordinators: dict) -> dict[str, str]:
    # Der Störspeicher hängt an der Steuerung, nicht an einem Datenpunkt.
    from .sensor.stoerspeicher import kennungen

    return dict.fromkeys(kennungen(coordinators), "sensor")


def _uhrzeit(coordinators: dict) -> dict[str, str]:
    # Die Uhrabweichung hängt an der Steuerung, nicht an einem Datenpunkt.
    from .sensor.uhrzeit import kennungen

    return dict.fromkeys(kennungen(coordinators), "sensor")


def _anlagenzustand(coordinators: dict) -> dict[str, str]:
    # Den Anlagenzustand legt jede Steuerung an; er hängt an keinem Datenpunkt.
    from .sensor.anlagenzustand import kennung

    return {kennung(coordinator): "sensor" for coordinator in coordinators.values()}


def _verbindung(coordinators: dict) -> dict[str, str]:
    # Verbindung und Antwortzeit hängen an der Steuerung, nicht an einem Datenpunkt.
    from .sensor.verbindung import kennungen

    return dict.fromkeys(kennungen(coordinators), "sensor")


def _befund(hass: HomeAssistant | None, entry: ConfigEntry) -> dict[str, str]:
    # Die Befund-Sensoren stehen in keinem Abzug; sie folgen den Heizkreisen und Kesseln.
    from .befund.laufzeit import kennungen

    return kennungen(entry, hass)


@callback
def bekannte_kennungen(
    entry: ConfigEntry, coordinators: dict, hass: HomeAssistant | None = None
) -> dict[str, bool]:
    """Kennung -> ob die Erkennung sie ab Werk einschaltet.

    Wärmequellen stehen nicht im Abzug der Anlage; ohne sie hier gälte jede
    von ihnen als verwaist.
    """
    bekannt = {
        beschreibung.get("id"): beschreibung.get("enabled_default", True)
        for coordinator in coordinators.values()
        for beschreibung in (coordinator.data or {}).get("devices", [])
    }
    quellen = dict.fromkeys(waermequelle.kennungen(entry, coordinators), True)
    eigene = {
        **_automatik(hass, entry),
        **_befund(hass, entry),
        **_stoerspeicher(coordinators),
        **_anlagenzustand(coordinators),
        **_uhrzeit(coordinators),
        **_verbindung(coordinators),
    }
    return bekannt | quellen | dict.fromkeys(eigene, True)


@callback
def abzug_steht(coordinators: dict) -> bool:
    """Ob der Bestand aussagekräftig ist.

    Vor dem Vollabzug ist die Liste unvollständig, und ein Abruf ohne Daten
    heißt nicht, dass es keine Datenpunkte gibt – er kann in die
    Zeitüberschreitung gelaufen sein.
    """
    return all(
        getattr(coordinator.client, "_vollstaendig", False)
        and (coordinator.data or {}).get("devices")
        for coordinator in coordinators.values()
    )


@callback
def erwartete_domaenen(
    entry: ConfigEntry, coordinators: dict, hass: HomeAssistant | None = None
) -> dict[str, str]:
    """Kennung -> Domäne, in der sie heute entsteht.

    Nur für Arten, deren Plattform schon angelegt ist. Was `TYP_DOMAENE` noch
    nicht kennt, bleibt draußen – sonst gälte es beim ersten Start als verwaist.
    """
    from .entity import TYP_DOMAENE

    domaenen = {
        beschreibung.get("id"): TYP_DOMAENE[beschreibung["type"]]
        for coordinator in coordinators.values()
        for beschreibung in (coordinator.data or {}).get("devices", [])
        if beschreibung.get("id") and beschreibung.get("type") in TYP_DOMAENE
    }
    quellen = dict.fromkeys(waermequelle.kennungen(entry, coordinators), "binary_sensor")
    eigene = (
        _automatik(hass, entry)
        | _befund(hass, entry)
        | _stoerspeicher(coordinators)
        | _anlagenzustand(coordinators)
        | _uhrzeit(coordinators)
        | _verbindung(coordinators)
    )
    return domaenen | quellen | eigene


@callback
def finden(
    hass: HomeAssistant, entry: ConfigEntry, coordinators: dict, *, behaltene: bool = False
) -> list[er.RegistryEntry]:
    """Einträge, deren Kennung fehlt oder in einer anderen Domäne steht.

    Der Plattformwechsel eines Datenpunkts lässt die alte Zeile stehen. Was der
    Nutzer behalten will, zählt nur mit `behaltene=True`.
    """
    if not coordinators or not abzug_steht(coordinators):
        return []
    from .automatik.verwaltung import AUTOMATIK_MARKE, verwaltung_holen

    geladen = verwaltung_holen(hass).geladen
    bekannt = bekannte_kennungen(entry, coordinators, hass)
    domaenen = erwartete_domaenen(entry, coordinators, hass)
    registry = er.async_get(hass)
    verwaist = []
    for eintrag in er.async_entries_for_config_entry(registry, entry.entry_id):
        # Ohne gelesenen Store ist eine Automatik unbekannt, nicht verwaist.
        if not geladen and AUTOMATIK_MARKE in eintrag.unique_id:
            continue
        if not behaltene and behalten(eintrag):
            continue
        if eintrag.unique_id not in bekannt:
            verwaist.append(eintrag)
            continue
        erwartet = domaenen.get(eintrag.unique_id)
        if erwartet and eintrag.domain != erwartet:
            verwaist.append(eintrag)
    return verwaist


def behalten(eintrag: er.RegistryEntry) -> bool:
    """Ob der Nutzer die Entität ohne Datenpunkt behalten will."""
    return bool(eintrag.options.get(DOMAIN, {}).get(BEHALTEN))


@callback
def merken(hass: HomeAssistant, eintraege: list[er.RegistryEntry]) -> None:
    """Die Entitäten behalten: Der Hinweis zählt sie nicht mehr."""
    registry = er.async_get(hass)
    for eintrag in eintraege:
        optionen = {**eintrag.options.get(DOMAIN, {}), BEHALTEN: True}
        registry.async_update_entity_options(eintrag.entity_id, DOMAIN, optionen)


@callback
def merkliste_aufraeumen(hass: HomeAssistant, entry: ConfigEntry, verwaist: set[str]) -> None:
    """Das Merkmal bei Entitäten löschen, deren Datenpunkt wieder da ist.

    Fällt der Datenpunkt später erneut weg, fragt der Hinweis wieder nach.
    """
    registry = er.async_get(hass)
    for eintrag in er.async_entries_for_config_entry(registry, entry.entry_id):
        if eintrag.entity_id in verwaist or not behalten(eintrag):
            continue
        optionen = {k: v for k, v in eintrag.options[DOMAIN].items() if k != BEHALTEN}
        registry.async_update_entity_options(eintrag.entity_id, DOMAIN, optionen or None)


def _bestehende_geraete(entry: ConfigEntry, coordinators: dict) -> set[str]:
    """Gerätekennungen, die der Eintrag heute anlegt, auch ohne eine Entität daran."""
    from .automatik.verwaltung import system_kennung
    from .entity import steuerung_kennung

    kennungen = {entry.entry_id, system_kennung(entry.entry_id)}
    for coordinator in coordinators.values():
        kennungen.add(steuerung_kennung(coordinator))
        kennungen.update(
            beschreibung.get("device_id")
            for beschreibung in (coordinator.data or {}).get("devices", [])
        )
    return kennungen


@callback
def geraet_entfernbar(
    hass: HomeAssistant, entry: ConfigEntry, coordinators: dict, geraet: dr.DeviceEntry
) -> bool:
    """Ob der Nutzer das Gerät löschen darf: Die Anlage meldet nichts mehr, was daran hängt.

    Vor dem Vollabzug bleibt jedes Gerät. Ein Baustein, der nur schweigt,
    sähe sonst aus wie ein entfernter.
    """
    from .automatik.verwaltung import verwaltung_holen

    if not coordinators or not abzug_steht(coordinators) or not verwaltung_holen(hass).geladen:
        return False
    eigene = {wert for bereich, wert in geraet.identifiers if bereich == DOMAIN}
    if not eigene or eigene & _bestehende_geraete(entry, coordinators):
        return False
    bekannt = bekannte_kennungen(entry, coordinators, hass)
    entitaeten = er.async_entries_for_device(
        er.async_get(hass), geraet.id, include_disabled_entities=True
    )
    return not any(
        e.unique_id in bekannt for e in entitaeten if e.config_entry_id == entry.entry_id
    )


def liste(eintraege: list[er.RegistryEntry]) -> str:
    """Eine Markdown-Zeile je Entität: Kennung, dahinter ihr Name, nach Kennung sortiert."""
    zeilen = []
    for eintrag in sorted(eintraege, key=lambda e: e.entity_id):
        name = eintrag.name or eintrag.original_name
        zeilen.append(f"- `{eintrag.entity_id}`" + (f" – {_maskiert(name)}" if name else ""))
    return "\n".join(zeilen)


def _maskiert(text: str) -> str:
    """Zeichen, die Markdown oder HTML deuten würde, als Text."""
    return re.sub(r"([\\`*_\[\]<>#|~])", r"\\\1", text)


@callback
def hinweis_pflegen(hass: HomeAssistant, entry: ConfigEntry, anzahl: int) -> None:
    """Den Reparatureintrag setzen oder zurücknehmen."""
    kennung = HINWEIS.format(entry_id=entry.entry_id)
    if not anzahl:
        ir.async_delete_issue(hass, DOMAIN, kennung)
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        kennung,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=SCHLUESSEL,
        translation_placeholders={"anzahl": str(anzahl)},
        data={"entry_id": entry.entry_id},
    )


@callback
def hinweis_ohne_geraet(
    hass: HomeAssistant, entry: ConfigEntry, coordinators: dict, geraet: dr.DeviceEntry
) -> None:
    """Einen bestehenden Hinweis ohne die Entitäten des Geräts neu zählen, das gleich wegfällt."""
    if ir.async_get(hass).async_get_issue(DOMAIN, HINWEIS.format(entry_id=entry.entry_id)) is None:
        return
    rest = [e for e in finden(hass, entry, coordinators) if e.device_id != geraet.id]
    hinweis_pflegen(hass, entry, len(rest))


@callback
def entfernen(hass: HomeAssistant, entry: ConfigEntry, coordinators: dict) -> int:
    """Die Verwaiste löschen und den Hinweis zurücknehmen.

    Der Bestand wird dabei neu ermittelt: Zwischen Hinweis und Klick können
    Datenpunkte zurückgekommen sein.
    """
    registry = er.async_get(hass)
    entfernt = 0
    for eintrag in finden(hass, entry, coordinators):
        registry.async_remove(eintrag.entity_id)
        entfernt += 1
    hinweis_pflegen(hass, entry, 0)
    if entfernt:
        _LOGGER.info("%d Entitäten ohne Datenpunkt entfernt", entfernt)
    return entfernt
