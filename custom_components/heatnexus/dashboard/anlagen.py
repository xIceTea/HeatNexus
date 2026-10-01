"""Die Anlagen aus den Registrierungen: Teile, Rang, Symbol und sichtbare Entitäten.

Dieselbe Liste speist Dashboard, Karte und Panel.
"""

from __future__ import annotations

import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .. import waermequelle
from ..bezeichnung import bezeichnung_lesen
from ..const import (
    AUTOMATIK_GERAET_ENDUNG,
    CONF_AUSSENTEMPERATUR,
    CONF_KESSELART,
    CONF_KESSELWERT,
    CONF_MODULPUMPE,
    DOMAIN,
    KESSELART_AUTO,
    KESSELWERT_LEISTUNG,
    QUELLEN_RANG,
    QUELLEN_SYMBOLE,
)
from ..helpers import enum_texte, mustername
from ..kanonisch import gnmn, ist_ableitung
from ..kanonisch import schluessel as kanonischer_schluessel
from ..rechte import darf_lesen
from ..schema import passt as _passt
from ..schema import traegt as _traegt
from ..symbole import symbol_je_fct
from .muster import FCT_RANG, OHNE_WERT, RANG_UNBEKANNT, UEBERSICHT_VORRANG


def gewaehlte_aussentemperatur(hass: HomeAssistant) -> str | None:
    """Die in den Optionen gewählte Außentemperatur, sofern es die Entität noch gibt.

    Eine verschwundene Wahl gilt als keine; dann greift die erkannte.
    """
    for eintrag in hass.config_entries.async_entries(DOMAIN):
        gewaehlt = (eintrag.options or {}).get(CONF_AUSSENTEMPERATUR)
        if gewaehlt and (hass.states.get(gewaehlt) or er.async_get(hass).async_get(gewaehlt)):
            return str(gewaehlt)
    return None


def kurzname(name: str | None) -> str:
    """Name ohne das vorangestellte Anlagenkürzel."""
    return (name or "").split(" · ")[-1].strip()


def rang(fct_type: Any, art: str | None = None) -> int:
    """Platz eines Anlagenteils in der fachlichen Reihenfolge."""
    if art in QUELLEN_RANG:
        return QUELLEN_RANG[art]
    try:
        return FCT_RANG.get(int(fct_type), RANG_UNBEKANNT)
    except (TypeError, ValueError):
        return RANG_UNBEKANNT


def symbol(fct_type: Any, art: str | None = None) -> str:
    """Symbol eines Anlagenteils."""
    if art in QUELLEN_SYMBOLE:
        return QUELLEN_SYMBOLE[art]
    return symbol_je_fct(fct_type)


def vorrang(eintrag: dict) -> int:
    """Position eines Werts in der Übersicht; kleiner heißt weiter oben.

    Auch hier gewinnt die Adresse: „Heizkreispumpe Nachlauf" träfe sonst die
    Zeile der Pumpe, bevor die Pumpe selbst an ihre kommt.
    """
    for platz, zeile in enumerate(UEBERSICHT_VORRANG):
        if _traegt(eintrag, zeile[1]):
            return platz
    for platz, zeile in enumerate(UEBERSICHT_VORRANG):
        if _passt(mustername(eintrag), (zeile[0],)):
            return platz
    return len(UEBERSICHT_VORRANG)


def trifft(eintrag: dict, muster: tuple[re.Pattern, ...], *schluessel: str) -> bool:
    """Erst am kanonischen Schlüssel, sonst am Namen.

    Der fehlende Schlüssel darf nicht als „passt nicht" gelten: Auf der
    Serviceebene gibt es Datenpunkte, die dieselbe Adresse an einer anderen
    Funktion tragen, und die Muster sind dort bisher die einzige Auskunft.
    """
    return _traegt(eintrag, schluessel) or _passt(mustername(eintrag), muster)


def skala(wert: float | None) -> int:
    """Obere Grenze einer Restlaufzeit-Skala, auf 100 aufgerundet."""
    if not wert or wert <= 0:
        return 100
    return max(100, -(-int(wert) // 100) * 100)


def _beschreibungen(hass: HomeAssistant):
    """Jede Datenpunktbeschreibung aller geladenen Anlagen."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        eintrag = getattr(entry, "runtime_data", None)
        if not isinstance(eintrag, dict):
            continue
        for coordinator in (eintrag.get("coordinators") or {}).values():
            yield from (coordinator.data or {}).get("devices", [])


def _fct_je_geraet(hass: HomeAssistant) -> dict[str, Any]:
    """Funktionstyp je Gerätekennung aus den Beschreibungen der Anlagen."""
    zuordnung: dict[str, Any] = {}
    for beschreibung in _beschreibungen(hass):
        kennung = beschreibung.get("device_id")
        if kennung and beschreibung.get("fct_type") is not None:
            zuordnung.setdefault(kennung, beschreibung["fct_type"])
    return zuordnung


def _auswahltexte(hass: HomeAssistant) -> dict[str, dict[int, str]]:
    """Auswahltexte je Entitätskennung, so wie die Entität sie anzeigt."""
    zuordnung: dict[str, dict[int, str]] = {}
    for beschreibung in _beschreibungen(hass):
        if (kennung := beschreibung.get("id")) and (texte := enum_texte(beschreibung)):
            zuordnung.setdefault(kennung, texte)
    return zuordnung


def _deutsche_namen(hass: HomeAssistant) -> dict[str, str]:
    """Deutscher Datenpunktname je Entitätskennung, unabhängig von Sprache und Umbenennung."""
    return {b["id"]: mustername(b) for b in _beschreibungen(hass) if b.get("id")}


def quellen_nach_geraet(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Bauart und Laufrad je Gerätekennung der Wärmequellen.

    Sie stehen in den Subeinträgen, nicht im Abzug der Anlage, und tragen
    deshalb keinen Funktionstyp.
    """
    zuordnung: dict[str, dict[str, Any]] = {}
    for entry in hass.config_entries.async_entries(DOMAIN):
        eintrag = getattr(entry, "runtime_data", None)
        if not isinstance(eintrag, dict):
            continue
        for coordinator in (eintrag.get("coordinators") or {}).values():
            for beschreibung in waermequelle.beschreibungen(entry, coordinator):
                zuordnung.setdefault(
                    beschreibung["id"],
                    {"art": beschreibung["art"], "pumpe": bool(beschreibung.get("pumpe"))},
                )
    return zuordnung


# Vorgabe, solange eine Anlage noch keine eigene Wahl gespeichert hat.
_SCHAUBILD_STANDARD = (KESSELART_AUTO, KESSELWERT_LEISTUNG, False)


def _schaubildwahl_je_geraet(hass: HomeAssistant) -> dict[str, tuple[str, str, bool]]:
    """Eingestellte Schaubild-Optionen je Gerätekennung.

    Die Option liegt je Anlage unter deren Adresse; die Geräte tragen sie nicht.
    Der Umweg über die Koordinatoren stellt die Verbindung her – dieselbe
    Zuordnung wie beim Funktionstyp.
    """
    zuordnung: dict[str, str] = {}
    for entry in hass.config_entries.async_entries(DOMAIN):
        eintrag = getattr(entry, "runtime_data", None)
        if not isinstance(eintrag, dict):
            continue
        optionen = entry.options or {}
        for host, coordinator in (eintrag.get("coordinators") or {}).items():
            je_host = optionen.get(host) or {}
            wahl = (
                je_host.get(CONF_KESSELART) or KESSELART_AUTO,
                je_host.get(CONF_KESSELWERT) or KESSELWERT_LEISTUNG,
                bool(je_host.get(CONF_MODULPUMPE, False)),
            )
            for beschreibung in (coordinator.data or {}).get("devices", []):
                if kennung := beschreibung.get("device_id"):
                    zuordnung.setdefault(kennung, wahl)
    return zuordnung


_MELDUNGSARTEN = ("fe01stoerung", "fe01text", "fe01liste", "fe01")


def _meldungsart(kennung: str) -> str | None:
    """Welcher Meldungssensor eines Knotens das ist, sonst nichts."""
    endung = kennung.rsplit("-", 1)[-1]
    return endung if endung in _MELDUNGSARTEN else None


def anlagen_lesen(hass: HomeAssistant, benutzer: Any = None) -> list[dict[str, Any]]:
    """Anlagen mit ihren Anlagenteilen und deren sichtbaren Entitäten.

    Der Aufbau der Geräte spiegelt die Anlage wider: Heizungsanlage →
    Steuerung (eine Adresse) → Funktion. Die Steuerung trägt den Namen, den
    der Nutzer bei der Einrichtung vergeben hat ("Kesselhaus", "Werkstatt"), und
    genau der macht zwei gleichnamige Pufferlademodule unterscheidbar.
    """
    geraete_registry = dr.async_get(hass)
    entitaeten_registry = er.async_get(hass)
    fct_je_geraet = _fct_je_geraet(hass)
    quellen_je_geraet = quellen_nach_geraet(hass)
    schaubildwahl_je_geraet = _schaubildwahl_je_geraet(hass)
    auswahltexte = _auswahltexte(hass)
    deutsche_namen = _deutsche_namen(hass)

    # Nur die eigenen Geräte: Home Assistant prüft die Form der Kennungen nicht,
    # und fremde Integrationen halten sich nicht immer an das Paar.
    eigene = (
        geraet
        for entry in hass.config_entries.async_entries(DOMAIN)
        for geraet in dr.async_entries_for_config_entry(geraete_registry, entry.entry_id)
    )
    teile: dict[str, dict[str, Any]] = {}
    for geraet in eigene:
        kennung = next((w for bereich, w in geraet.identifiers if bereich == DOMAIN), None)
        if kennung is None:
            continue
        # Die Automatik hat ihren eigenen Reiter und ist kein Teil der Anlage.
        if kennung.endswith(AUTOMATIK_GERAET_ENDUNG):
            continue
        fct = fct_je_geraet.get(kennung)
        quelle = quellen_je_geraet.get(kennung) or {}
        art = quelle.get("art")
        teile[geraet.id] = {
            "name": kurzname(geraet.name_by_user or geraet.name),
            "id": geraet.id,
            "anlage_id": geraet.via_device_id,
            "fct_type": fct,
            "art": art,
            "quellenpumpe": bool(quelle.get("pumpe")),
            "rang": rang(fct, art),
            "symbol": symbol(fct, art),
            "kesselart_wahl": schaubildwahl_je_geraet.get(kennung, _SCHAUBILD_STANDARD)[0],
            "kesselwert_wahl": schaubildwahl_je_geraet.get(kennung, _SCHAUBILD_STANDARD)[1],
            "modulpumpe_wahl": schaubildwahl_je_geraet.get(kennung, _SCHAUBILD_STANDARD)[2],
            "entitaeten": [],
        }

    for eintrag in entitaeten_registry.entities.values():
        if eintrag.platform != DOMAIN:
            continue
        if eintrag.disabled_by is not None or eintrag.hidden_by is not None:
            continue
        # Was Home Assistant dem Anfragenden verwehrt, steht auch hier nicht.
        if not darf_lesen(benutzer, eintrag.entity_id):
            continue
        teil = teile.get(eintrag.device_id)
        if teil is None:
            continue
        zustand = hass.states.get(eintrag.entity_id)
        hat_wert = bool(zustand) and zustand.state.lower() not in OHNE_WERT
        try:
            zahl = float(zustand.state) if hat_wert else None
        except (TypeError, ValueError):
            zahl = None
        bereich = eintrag.entity_id.split(".")[0]
        teil["entitaeten"].append(
            {
                "entity_id": eintrag.entity_id,
                "name": kurzname(eintrag.name or eintrag.original_name or eintrag.entity_id),
                # Muster und Hilfetexte sind deutsch und suchen hier, nicht im Anzeigenamen.
                "name_de": deutsche_namen.get(eintrag.unique_id)
                or kurzname(eintrag.original_name or eintrag.name or eintrag.entity_id),
                # Der sprachunabhängige Schlüssel, sofern der Datenpunkt einen
                # hat. Er kommt aus der Adresse in der Kennung und nicht aus
                # dem Namen – siehe `kanonisch.py`. Wo er fehlt, bleibt es beim
                # Namensmuster.
                "schluessel": kanonischer_schluessel(eintrag.unique_id, bereich),
                # Die rohe Datenpunktadresse. Sie erlaubt den Abgleich mit den
                # Ebenenlisten der Geräte-Datenbank – dort steht auch für
                # Baureihen etwas, für die es hier kein Namensmuster gibt.
                "adresse": gnmn(eintrag.unique_id),
                # Dazugewählte Ableitung statt eines Messwerts der Anlage. Die
                # festen Listen der Oberfläche übergehen sie.
                "abgeleitet": ist_ableitung(eintrag.unique_id),
                "kategorie": eintrag.entity_category,
                "bereich": bereich,
                "hat_wert": hat_wert,
                "wert": zahl,
                # Der Zustand als Text: Zahlen stehen in "wert", aber die
                # Kesselart wird am gemeldeten Brennstoff erkannt, und der ist
                # ein Wort.
                "text": zustand.state if hat_wert else None,
                "state_class": (zustand.attributes.get("state_class") if zustand else None),
                # Auswahltexte nach Wert: Vergleiche über den Wert gelten in jeder Sprache.
                "optionen": auswahltexte.get(eintrag.unique_id, {}),
                # Eigene Bezeichnung eines Zeitprogramms; der Name bleibt der der Anlage.
                "bezeichnung": bezeichnung_lesen(eintrag),
                # Meldungssensoren des Knotens (`client/gemeinsam.MELDUNGS_SENSOREN`).
                "meldungsart": _meldungsart(eintrag.unique_id),
            }
        )

    # Anlagenteile ihren Steuerungen zuordnen; die Steuerungen selbst tragen
    # keine Entitäten und erscheinen nur als Gruppe.
    anlagen: dict[str, dict[str, Any]] = {}
    for teil in teile.values():
        if not teil["entitaeten"]:
            continue
        anlage_id = teil["anlage_id"] or teil["id"]
        gruppe = anlagen.setdefault(
            anlage_id,
            {
                # Die Kennung der Steuerung. Sie überlebt eine erneute
                # Erkennung und unterscheidet zwei gleich aufgebaute Anlagen –
                # der Name täte das auch, bis ihn jemand ändert.
                "id": anlage_id,
                "name": kurzname((teile.get(anlage_id) or {}).get("name")),
                "teile": [],
            },
        )
        gruppe["teile"].append(teil)
        teil["entitaeten"].sort(key=lambda e: e["name"])

    for gruppe in anlagen.values():
        gruppe["teile"].sort(key=lambda t: (t["rang"], t["name"]))
        # Welcher zweite Wert am Kessel steht. Die erste ausdrückliche Angabe
        # gilt; ohne Angabe bleibt es bei der Leistung.
        gruppe["kesselwert"] = next(
            (t["kesselwert_wahl"] for t in gruppe["teile"] if t.get("kesselwert_wahl")),
            KESSELWERT_LEISTUNG,
        )
        # Erst wenn eine Anlage eine Pumpe am Modul bestätigt, steht sie im Bild.
        gruppe["modulpumpe"] = any(t.get("modulpumpe_wahl") for t in gruppe["teile"])

    return sorted(anlagen.values(), key=lambda a: a["name"])


def voller_name(anlage: dict[str, Any], teil: dict[str, Any]) -> str:
    """Anlagenteil mit vorangestellter Anlage."""
    return f"{anlage['name']} · {teil['name']}" if anlage["name"] else teil["name"]
