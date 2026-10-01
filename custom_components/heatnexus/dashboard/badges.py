"""Badges der Kopfzeile: Kennwerte, bald fällige Wartung, anliegende Störung."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .. import geraete
from ..automatik.system import kreisnamen
from ..automatik.verwaltung import DATEN_SCHLUESSEL, system_unique_id, unique_id
from ..const import DOMAIN
from ..texte import woerterbuch
from . import auswahl
from .anlagen import gewaehlte_aussentemperatur
from .muster import WARTUNG_HINWEIS_STUNDEN, WARTUNG_KURZNAMEN

# Namen der Kennwert-Badges; bei mehreren Kesseln einer Anlage steht der Name des Teils.
KESSEL = "Kessel"
VORRAT = ("fuel_storage_status", "Vorrat")

# Zustände, in denen ein Heizkreis seinem Programm folgt; nur Abweichungen zeigen eine Badge.
PLANMAESSIG = ["programm", "aus"]

# Eine Badge vor dem Zusammensetzen: Entität, Name, Sichtbarkeit.
Eintrag = tuple[str, str, list[dict[str, Any]] | None]


def badge(
    entity_id: str,
    name: str,
    sichtbar: list[dict[str, Any]] | None = None,
    inhalt: str | None = None,
) -> dict[str, Any]:
    """Eine beschriftete Badge; mit Bedingung nur sichtbar, solange sie zutrifft.

    `inhalt` zeigt statt des Zustands ein Attribut der Entität.
    """
    ergebnis: dict[str, Any] = {
        "type": "entity",
        "entity": entity_id,
        "name": name,
        "show_name": True,
    }
    if inhalt:
        ergebnis["state_content"] = inhalt
    if sichtbar:
        ergebnis["visibility"] = sichtbar
    return ergebnis


def _mit_wert(teil: dict[str, Any], schluessel: str) -> dict[str, Any] | None:
    return next(
        (e for e in teil["entitaeten"] if e.get("schluessel") == schluessel and e["hat_wert"]),
        None,
    )


def _erste(anlage: dict[str, Any], schluessel: str) -> dict[str, Any] | None:
    return next((e for teil in anlage["teile"] if (e := _mit_wert(teil, schluessel))), None)


def _ist_kessel(teil: dict[str, Any]) -> bool:
    """Wärmeerzeuger ist, was das Schaubild als Kessel zeichnet."""
    try:
        return geraete.SCHAUBILD_ARTEN.get(int(teil.get("fct_type"))) == "kessel"
    except (TypeError, ValueError):
        return False


def _name(anlage: dict[str, Any], name: str, mehrere: bool) -> str:
    return f"{anlage['name']} · {name}" if mehrere and anlage["name"] else name


def _gleich(text: str) -> str:
    return text


def _kennwerte(anlage: dict[str, Any], uebersetze: Callable[[str], str]) -> list[Eintrag]:
    """Betriebsphase je Wärmeerzeuger, dazu der erste Vorratsbehälter."""
    phasen = [
        (teil, e)
        for teil in anlage["teile"]
        if _ist_kessel(teil) and (e := _mit_wert(teil, "operating_phase"))
    ]
    einer = len(phasen) == 1
    ergebnis: list[Eintrag] = [
        (e["entity_id"], uebersetze(KESSEL) if einer else teil["name"], None) for teil, e in phasen
    ]
    if vorrat := _erste(anlage, VORRAT[0]):
        ergebnis.append((vorrat["entity_id"], uebersetze(VORRAT[1]), None))
    return ergebnis


def _wartung(anlage: dict[str, Any], uebersetze: Callable[[str], str]) -> list[Eintrag]:
    """Restlaufzeiten, sichtbar erst unter der Hinweisgrenze."""
    return [
        (
            e["entity_id"],
            uebersetze(name),
            [
                {
                    "condition": "numeric_state",
                    "entity": e["entity_id"],
                    "below": WARTUNG_HINWEIS_STUNDEN,
                }
            ],
        )
        for schluessel, name in WARTUNG_KURZNAMEN.items()
        if (e := _erste(anlage, schluessel))
    ]


def _stoerungen(anlage: dict[str, Any]) -> list[Eintrag]:
    """Je Anlagenteil die Störung, sichtbar nur solange sie anliegt."""
    return [
        (
            sensor["entity_id"],
            teil["name"],
            [{"condition": "state", "entity": sensor["entity_id"], "state": "on"}],
        )
        for teil in anlage["teile"]
        if (sensor := auswahl.stoerung(teil))
    ]


def anlagenbadges(
    anlagen: list[dict[str, Any]], uebersetze: Callable[[str], str] = _gleich
) -> list[dict[str, Any]]:
    """Je Anlage Kessel, Vorrat, bald fällige Wartung und anliegende Störungen.

    Feste Namen werden übersetzt, bevor der Anlagenname davorkommt: Den
    zusammengesetzten Text kennt kein Wörterbuch.
    """
    mehrere = len(anlagen) > 1
    return [
        badge(entity_id, _name(anlage, name, mehrere), sichtbar)
        for anlage in anlagen
        for entity_id, name, sichtbar in (
            *_kennwerte(anlage, uebersetze),
            *_wartung(anlage, uebersetze),
            *_stoerungen(anlage),
        )
    ]


def allgemein(hass: HomeAssistant, anlagen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Außentemperatur (gewählt oder erste gemeldete), dann je Automatik Status und Heizkreise."""
    eintraege = hass.config_entries.async_entries(DOMAIN)
    aussen = gewaehlte_aussentemperatur(hass) or next(
        (
            e["entity_id"]
            for a in anlagen
            for t in a["teile"]
            for e in t["entitaeten"]
            if e.get("schluessel") == "outdoor_temperature" and e["hat_wert"]
        ),
        None,
    )
    ergebnis = [badge(aussen, "Außen")] if aussen else []
    return [*ergebnis, *_automatiken(hass, eintraege)]


def _automatiken(hass: HomeAssistant, eintraege: list[ConfigEntry]) -> list[dict[str, Any]]:
    """Je Eintrag der Status der Automatik, dahinter die Badges seiner Heizkreise."""
    status = {
        e.entry_id: entity_id
        for e in eintraege
        if (entity_id := _aktive_entitaet(hass, system_unique_id(e.entry_id, "status")))
    }
    mehrere = len(status) > 1
    ergebnis: list[dict[str, Any]] = []
    for eintrag in eintraege:
        if entity_id := status.get(eintrag.entry_id):
            name = f"Automatik · {eintrag.title}" if mehrere and eintrag.title else "Automatik"
            ergebnis.append(badge(entity_id, name))
        ergebnis.extend(_kreise(hass, eintrag))
    return ergebnis


def _kreise(hass: HomeAssistant, eintrag: ConfigEntry) -> list[dict[str, Any]]:
    """Je Heizkreis die Begründung, sichtbar nur solange er vom Programm abweicht."""
    verwaltung = hass.data.get(DATEN_SCHLUESSEL)
    if verwaltung is None:
        return []
    laufzeiten = [lz for lz in verwaltung.laufzeiten.values() if lz.entry_id == eintrag.entry_id]
    namen = kreisnamen(laufzeiten)
    return [
        badge(
            entity_id,
            namen[lz.device_id],
            [{"condition": "state", "entity": entity_id, "state_not": PLANMAESSIG}],
            inhalt="begruendung",
        )
        for lz in laufzeiten
        if (entity_id := _aktive_entitaet(hass, unique_id(lz.device_id, "zustand")))
    ]


def _aktive_entitaet(hass: HomeAssistant, kennung: str) -> str | None:
    """Der Sensor zur Kennung, sofern er registriert und nicht abgeschaltet ist."""
    register = er.async_get(hass)
    entity_id = register.async_get_entity_id("sensor", DOMAIN, kennung)
    if entity_id and not register.async_get(entity_id).disabled_by:
        return entity_id
    return None


def kopfzeile(hass: HomeAssistant, anlagen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Alle Badges der Kopfzeile: erst die allgemeinen, dann die je Anlage."""
    return [*allgemein(hass, anlagen), *anlagenbadges(anlagen, woerterbuch(hass))]
