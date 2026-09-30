"""Badges der Kopfzeile: Kennwerte, bald fällige Wartung, anliegende Störung."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ..automatik.verwaltung import system_unique_id
from ..const import CONF_AUSSENTEMPERATUR, DOMAIN
from ..texte import woerterbuch
from . import auswahl
from .muster import WARTUNG_HINWEIS_STUNDEN, WARTUNG_KURZNAMEN

# Kennwerte je Anlage: kanonischer Schlüssel und Name der Badge.
ANLAGENWERTE = (("operating_phase", "Kessel"), ("fuel_storage_status", "Vorrat"))


def badge(
    entity_id: str, name: str, sichtbar: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Eine beschriftete Badge; mit Bedingung nur sichtbar, solange sie zutrifft."""
    ergebnis: dict[str, Any] = {
        "type": "entity",
        "entity": entity_id,
        "name": name,
        "show_name": True,
    }
    if sichtbar:
        ergebnis["visibility"] = sichtbar
    return ergebnis


def _erste(anlage: dict[str, Any], schluessel: str) -> dict[str, Any] | None:
    return next(
        (
            e
            for teil in anlage["teile"]
            for e in teil["entitaeten"]
            if e.get("schluessel") == schluessel and e["hat_wert"]
        ),
        None,
    )


def _name(anlage: dict[str, Any], name: str, mehrere: bool) -> str:
    return f"{anlage['name']} · {name}" if mehrere and anlage["name"] else name


def _gleich(text: str) -> str:
    return text


def anlagenbadges(
    anlagen: list[dict[str, Any]], uebersetze: Callable[[str], str] = _gleich
) -> list[dict[str, Any]]:
    """Je Anlage Kessel, Vorrat, bald fällige Wartung und anliegende Störungen.

    Feste Namen werden übersetzt, bevor der Anlagenname davorkommt: Den
    zusammengesetzten Text kennt kein Wörterbuch.
    """
    mehrere = len(anlagen) > 1
    ergebnis: list[dict[str, Any]] = []
    for anlage in anlagen:
        for schluessel, name in ANLAGENWERTE:
            if e := _erste(anlage, schluessel):
                ergebnis.append(badge(e["entity_id"], _name(anlage, uebersetze(name), mehrere)))
        for schluessel, name in WARTUNG_KURZNAMEN.items():
            if e := _erste(anlage, schluessel):
                bald = [
                    {
                        "condition": "numeric_state",
                        "entity": e["entity_id"],
                        "below": WARTUNG_HINWEIS_STUNDEN,
                    }
                ]
                ergebnis.append(
                    badge(e["entity_id"], _name(anlage, uebersetze(name), mehrere), bald)
                )
        for teil in anlage["teile"]:
            if sensor := auswahl.stoerung(teil):
                an = [{"condition": "state", "entity": sensor["entity_id"], "state": "on"}]
                ergebnis.append(
                    badge(sensor["entity_id"], _name(anlage, teil["name"], mehrere), an)
                )
    return ergebnis


def allgemein(hass: HomeAssistant, anlagen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Außentemperatur (gewählt oder erste gemeldete) und Status der Automatik."""
    eintraege = hass.config_entries.async_entries(DOMAIN)
    aussen = next(
        (w for e in eintraege if (w := (e.options or {}).get(CONF_AUSSENTEMPERATUR))), None
    )
    aussen = aussen or next(
        (
            e["entity_id"]
            for a in anlagen
            for t in a["teile"]
            for e in t["entitaeten"]
            if e.get("schluessel") == "outdoor_temperature" and e["hat_wert"]
        ),
        None,
    )
    paare = ((aussen, "Außen"), (_automatik(hass, eintraege), "Automatik"))
    return [badge(eid, name) for eid, name in paare if eid]


def _automatik(hass: HomeAssistant, eintraege: list[ConfigEntry]) -> str | None:
    """Die Statusentität der ersten Automatik, die nicht abgeschaltet ist."""
    register = er.async_get(hass)
    for eintrag in eintraege:
        kennung = system_unique_id(eintrag.entry_id, "status")
        entity_id = register.async_get_entity_id("sensor", DOMAIN, kennung)
        if entity_id and not register.async_get(entity_id).disabled_by:
            return entity_id
    return None


def kopfzeile(hass: HomeAssistant, anlagen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Alle Badges der Kopfzeile; jede Entität nur einmal."""
    gesehen: set[str] = set()
    ergebnis: list[dict[str, Any]] = []
    for b in (*allgemein(hass, anlagen), *anlagenbadges(anlagen, woerterbuch(hass))):
        if b["entity"] not in gesehen:
            gesehen.add(b["entity"])
            ergebnis.append(b)
    return ergebnis
