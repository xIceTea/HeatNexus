"""Badges der Kopfzeile: Kennwerte, bald fällige Wartung, anliegende Störung."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .. import geraete
from ..automatik.verwaltung import system_unique_id
from ..const import CONF_AUSSENTEMPERATUR, DOMAIN
from ..texte import woerterbuch
from . import auswahl
from .muster import WARTUNG_HINWEIS_STUNDEN, WARTUNG_KURZNAMEN

# Namen der Kennwert-Badges; bei mehreren Kesseln einer Anlage steht der Name des Teils.
KESSEL = "Kessel"
VORRAT = ("fuel_storage_status", "Vorrat")

# Badges des laufenden Eingriffs: Art der System-Entität, Name; sichtbar nur bei „an“.
EINGRIFFE = (("sonnentag_aktiv", "Sonnentag"), ("nur_ww_aktiv", "Nur Warmwasser"))

# Eine Badge vor dem Zusammensetzen: Entität, Name, Sichtbarkeit.
Eintrag = tuple[str, str, list[dict[str, Any]] | None]


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
    """Außentemperatur (gewählt oder erste gemeldete), Status der Automatik, laufender Eingriff."""
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
    ergebnis = [badge(aussen, "Außen")] if aussen else []
    if automatik := _automatik(hass, eintraege):
        status, eintrag = automatik
        ergebnis.append(badge(status, "Automatik"))
        for art, name in EINGRIFFE:
            if entity_id := _aktive_entitaet(hass, "binary_sensor", eintrag, art):
                bedingung = [{"condition": "state", "entity": entity_id, "state": "on"}]
                ergebnis.append(badge(entity_id, name, bedingung))
    return ergebnis


def _aktive_entitaet(
    hass: HomeAssistant, domaene: str, eintrag: ConfigEntry, art: str
) -> str | None:
    """Die System-Entität einer Art, sofern sie registriert und nicht abgeschaltet ist."""
    register = er.async_get(hass)
    kennung = system_unique_id(eintrag.entry_id, art)
    entity_id = register.async_get_entity_id(domaene, DOMAIN, kennung)
    if entity_id and not register.async_get(entity_id).disabled_by:
        return entity_id
    return None


def _automatik(hass: HomeAssistant, eintraege: list[ConfigEntry]) -> tuple[str, ConfigEntry] | None:
    """Statusentität und Eintrag der ersten Automatik, die nicht abgeschaltet ist."""
    for eintrag in eintraege:
        if entity_id := _aktive_entitaet(hass, "sensor", eintrag, "status"):
            return entity_id, eintrag
    return None


def kopfzeile(hass: HomeAssistant, anlagen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Alle Badges der Kopfzeile: erst die allgemeinen, dann die je Anlage."""
    return [*allgemein(hass, anlagen), *anlagenbadges(anlagen, woerterbuch(hass))]
