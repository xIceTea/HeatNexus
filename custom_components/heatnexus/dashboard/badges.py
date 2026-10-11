"""Badges der Kopfzeile: Kennwerte, bald fällige Wartung, anliegende Störung."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ..automatik.system import kreisnamen
from ..automatik.verwaltung import DATEN_SCHLUESSEL, system_unique_id, unique_id
from ..const import DOMAIN
from ..texte import Woerterbuch, woerterbuch
from . import auswahl
from .anlagen import gewaehlte_aussentemperatur
from .kacheln import KESSEL as KESSELROLLE
from .kacheln import rolle
from .muster import WARTUNG_HINWEIS_STUNDEN, WARTUNG_KURZNAMEN

# Namen der Kennwert-Badges; bei mehreren Kesseln einer Anlage steht der Name des Teils.
KESSEL = "Kessel"
VORRAT = ("fuel_storage_status", "Vorrat")

# Zustände, in denen ein Heizkreis seinem Programm folgt; nur Abweichungen zeigen eine Badge.
PLANMAESSIG = ["programm", "aus"]

# Eine Badge vor dem Zusammensetzen: Entität, Name, Sichtbarkeit.
Eintrag = tuple[str, str, list[dict[str, Any]] | None]

# Aussehen der Badges in der Übersicht.
PHASE = {"show_state": True, "show_icon": True, "icon": "mdi:fire", "color": "deep-orange"}
VORRAT_LEER = {"show_state": True, "show_icon": True, "icon": "mdi:silo", "color": "red"}
WARTUNG_FARBE = "orange"
STOERUNG_FARBE = "red"
# Vorratsbehälter (`39/76`): 0 = Fehler, 1 = leer.
VORRAT_WARNWERTE = (0, 1)


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


def _name(anlage: dict[str, Any], name: str, mehrere: bool) -> str:
    return f"{anlage['name']} · {name}" if mehrere and anlage["name"] else name


def _gleich(text: str) -> str:
    return text


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


def _phasen(anlage: dict[str, Any], uebersetze: Callable[[str], str]) -> list[dict[str, Any]]:
    """Betriebsphase je Kessel; mit zwei Kesseln steht der Teilname hinter der Anlage."""
    kessel = [t for t in anlage["teile"] if rolle(t) == KESSELROLLE]
    name = anlage["name"] or uebersetze(KESSEL)
    return [
        badge(e["entity_id"], f"{name} · {teil['name']}" if len(kessel) > 1 else name) | PHASE
        for teil in kessel
        if (e := _mit_wert(teil, "operating_phase"))
    ]


def _vorrat(anlage: dict[str, Any], uebersetze: Callable[[str], str]) -> list[dict[str, Any]]:
    """Der Vorratsbehälter, sichtbar nur bei Fehler oder leer."""
    e = _erste(anlage, VORRAT[0])
    optionen = (e or {}).get("optionen") or {}
    zustaende = [optionen[w] for w in VORRAT_WARNWERTE if w in optionen]
    if not e or not zustaende:
        return []
    sichtbar = [{"condition": "state", "entity": e["entity_id"], "state": zustaende}]
    name = _name(anlage, uebersetze(VORRAT[1]), True)
    return [badge(e["entity_id"], name, sichtbar) | VORRAT_LEER]


def uebersicht_anlagenbadges(
    anlagen: list[dict[str, Any]], uebersetze: Callable[[str], str] = _gleich
) -> list[dict[str, Any]]:
    """Übersicht mehrerer Anlagen: Phasen, dann Wartung und Störung je Anlage, der Vorrat zuletzt."""
    hinweise = [
        badge(entity_id, _name(anlage, name, True), sichtbar) | {"color": farbe}
        for anlage in anlagen
        for farbe, eintraege in (
            (WARTUNG_FARBE, _wartung(anlage, uebersetze)),
            (STOERUNG_FARBE, _stoerungen(anlage)),
        )
        for entity_id, name, sichtbar in eintraege
    ]
    return [
        *(b for anlage in anlagen for b in _phasen(anlage, uebersetze)),
        *hinweise,
        *(b for anlage in anlagen for b in _vorrat(anlage, uebersetze)),
    ]


def uebersichtszeile(
    hass: HomeAssistant, anlagen: list[dict[str, Any]], uebersetze: Woerterbuch | None = None
) -> list[dict[str, Any]]:
    """Kopfzeile der Übersicht: Außen, die Badges der Anlagen, dann die Automatik."""
    buch = woerterbuch(hass) if uebersetze is None else uebersetze
    eintraege = hass.config_entries.async_entries(DOMAIN)
    return [
        *_aussen(hass, anlagen),
        *uebersicht_anlagenbadges(anlagen, buch),
        *_automatiken(hass, eintraege),
    ]


def _aussen(hass: HomeAssistant, anlagen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Außentemperatur: gewählt oder die erste gemeldete."""
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
    return [badge(aussen, "Außen")] if aussen else []


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
            inhalt="kurz",
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
