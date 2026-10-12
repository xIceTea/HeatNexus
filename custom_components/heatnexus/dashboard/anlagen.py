"""Die Anlagen aus den Registrierungen: Teile, Rang, Symbol und sichtbare Entitäten.

Dieselbe Liste speist Dashboard, Karte und Panel.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .. import device_db, geraete, texte, waermequelle
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
from ..helpers import enum_texte, knoten, mustername
from ..kanonisch import gnmn, ist_ableitung
from ..kanonisch import schluessel as kanonischer_schluessel
from ..rechte import darf_lesen
from ..registrierung import kurzname
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


def _koordinatoren(hass: HomeAssistant):
    """Jeder Koordinator aller geladenen Anlagen."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        eintrag = getattr(entry, "runtime_data", None)
        if isinstance(eintrag, dict):
            yield from (eintrag.get("coordinators") or {}).values()


def _beschreibungen(hass: HomeAssistant):
    """Jede Datenpunktbeschreibung aller geladenen Anlagen."""
    for coordinator in _koordinatoren(hass):
        yield from (coordinator.data or {}).get("devices", [])


def _fct_je_geraet(hass: HomeAssistant) -> dict[str, tuple[Any, str | None]]:
    """Funktionstyp und deutsches Werksmodell je Gerätekennung.

    Das Modell folgt weder der Sprache noch einer Umbenennung des Geräts.
    """
    zuordnung: dict[str, tuple[Any, str | None]] = {}
    # Erst eine Beschreibung mit Knoten legt das Modell fest; ohne Knoten gilt
    # das Modell des Funktionstyps nur, bis eine mit Knoten kommt.
    mit_knoten: set[str] = set()
    for coordinator in _koordinatoren(hass):
        klassen = getattr(getattr(coordinator, "client", None), "geraeteklasse", None) or {}
        for beschreibung in (coordinator.data or {}).get("devices", []):
            kennung, fct = beschreibung.get("device_id"), beschreibung.get("fct_type")
            if not kennung or fct is None or kennung in mit_knoten:
                continue
            knoten_nr = knoten(beschreibung)
            if knoten_nr is not None:
                mit_knoten.add(kennung)
            elif kennung in zuordnung:
                continue
            zuordnung[kennung] = (fct, geraete.modell(fct, klassen.get(knoten_nr)))
    return zuordnung


def _auswahltexte(beschreibungen: list[dict[str, Any]]) -> dict[str, dict[int, str]]:
    """Auswahltexte je Entitätskennung, so wie die Entität sie anzeigt."""
    zuordnung: dict[str, dict[int, str]] = {}
    for beschreibung in beschreibungen:
        if (kennung := beschreibung.get("id")) and (texte := enum_texte(beschreibung)):
            zuordnung.setdefault(kennung, texte)
    return zuordnung


def _deutsche_namen(hass: HomeAssistant, beschreibungen: list[dict[str, Any]]):
    """Deutscher Datenpunktname einer Registrierung, unabhängig von Sprache und Umbenennung.

    Fehlt die Beschreibung, gilt bei fremder Sprache der Herstellername der Adresse.
    """
    namen = {b["id"]: mustername(b) for b in beschreibungen if b.get("id")}
    sprachen = {
        e.entry_id: texte.sprache_des_eintrags(hass, e)
        for e in hass.config_entries.async_entries(DOMAIN)
    }

    def name_de(eintrag) -> str:
        if name := namen.get(eintrag.unique_id):
            return name
        fremd = sprachen.get(eintrag.config_entry_id, "de") != "de"
        if fremd and (adresse := gnmn(eintrag.unique_id)) and (name := device_db.get_name(adresse)):
            return name
        return kurzname(eintrag.original_name or eintrag.name or eintrag.entity_id)

    return name_de


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


def woerterbuch_der_anlage(hass: HomeAssistant, anlage: dict[str, Any]) -> texte.Woerterbuch:
    """Das Wörterbuch des Eintrags, zu dem die Anlage gehört; ohne Eintrag das gemeinsame."""
    if eintrag := anlage.get("eintrag"):
        return texte.woerterbuch_des_eintrags(hass, eintrag)
    return texte.woerterbuch(hass)


def anlage_in_sprache(
    daten: dict[str, Any], buch: texte.Woerterbuch, gemeinsam: texte.Woerterbuch
) -> dict[str, Any]:
    """Die Daten einer Anlage für den Browser, übersetzt mit dem Wörterbuch ihres Eintrags.

    Weicht ihre Sprache von der gemeinsamen ab, reist das Wörterbuch mit: Der
    Browser beschriftet damit, was zu dieser Anlage gehört.
    """
    fertig = {**texte.uebersetze_baum(daten, buch), "sprache": buch.sprache}
    if buch.sprache != gemeinsam.sprache:
        fertig["texte"] = buch.fuer_frontend
    return fertig


def _gruppe_abschliessen(gruppe: dict[str, Any]) -> None:
    """Teile ordnen und die Schaubildwahl der Anlage aus ihren Teilen ableiten."""
    gruppe["teile"].sort(key=lambda t: (t["rang"], t["name"]))
    # Welcher zweite Wert am Kessel steht. Die erste ausdrückliche Angabe
    # gilt; ohne Angabe bleibt es bei der Leistung.
    gruppe["kesselwert"] = next(
        (t["kesselwert_wahl"] for t in gruppe["teile"] if t.get("kesselwert_wahl")),
        KESSELWERT_LEISTUNG,
    )
    # Erst wenn eine Anlage eine Pumpe am Modul bestätigt, steht sie im Bild.
    gruppe["modulpumpe"] = any(t.get("modulpumpe_wahl") for t in gruppe["teile"])


@dataclass(frozen=True)
class _Lesestand:
    """Was je Gerät und je Entität einmal aus den Koordinatoren gelesen wird."""

    fct_je_geraet: dict[str, tuple[Any, str | None]]
    quellen_je_geraet: dict[str, dict[str, Any]]
    schaubildwahl_je_geraet: dict[str, tuple[str, str, bool]]
    auswahltexte: dict[str, dict[int, str]]
    deutsche_namen: Callable[[Any], str]


def _lesestand(hass: HomeAssistant) -> _Lesestand:
    beschreibungen = list(_beschreibungen(hass))
    return _Lesestand(
        fct_je_geraet=_fct_je_geraet(hass),
        quellen_je_geraet=quellen_nach_geraet(hass),
        schaubildwahl_je_geraet=_schaubildwahl_je_geraet(hass),
        auswahltexte=_auswahltexte(beschreibungen),
        deutsche_namen=_deutsche_namen(hass, beschreibungen),
    )


def _teil(entry_id: str, geraet: Any, kennung: str, stand: _Lesestand) -> dict[str, Any]:
    """Ein Anlagenteil aus seinem Gerät, noch ohne Entitäten."""
    fct, modell = stand.fct_je_geraet.get(kennung, (None, None))
    quelle = stand.quellen_je_geraet.get(kennung) or {}
    art = quelle.get("art")
    kesselart, kesselwert, modulpumpe = stand.schaubildwahl_je_geraet.get(
        kennung, _SCHAUBILD_STANDARD
    )
    return {
        "name": kurzname(geraet.name_by_user or geraet.name),
        "id": geraet.id,
        "anlage_id": geraet.via_device_id,
        "eintrag": entry_id,
        "fct_type": fct,
        "modell": modell,
        "art": art,
        "quellenpumpe": bool(quelle.get("pumpe")),
        "rang": rang(fct, art),
        "symbol": symbol(fct, art),
        "kesselart_wahl": kesselart,
        "kesselwert_wahl": kesselwert,
        "modulpumpe_wahl": modulpumpe,
        "entitaeten": [],
    }


def _eigene_teile(hass: HomeAssistant, stand: _Lesestand) -> dict[str, dict[str, Any]]:
    """Die Anlagenteile der eigenen Geräte, nach Gerätekennung der Registry."""
    geraete_registry = dr.async_get(hass)
    # Nur die eigenen Geräte: Home Assistant prüft die Form der Kennungen nicht,
    # und fremde Integrationen halten sich nicht immer an das Paar.
    eigene = (
        (entry.entry_id, geraet)
        for entry in hass.config_entries.async_entries(DOMAIN)
        for geraet in dr.async_entries_for_config_entry(geraete_registry, entry.entry_id)
    )
    teile: dict[str, dict[str, Any]] = {}
    for entry_id, geraet in eigene:
        kennung = next((w for bereich, w in geraet.identifiers if bereich == DOMAIN), None)
        if kennung is None:
            continue
        # Die Automatik hat ihren eigenen Reiter und ist kein Teil der Anlage.
        if kennung.endswith(AUTOMATIK_GERAET_ENDUNG):
            continue
        teile[geraet.id] = _teil(entry_id, geraet, kennung, stand)
    return teile


def _entitaet(hass: HomeAssistant, eintrag: Any, stand: _Lesestand) -> dict[str, Any]:
    """Eine sichtbare Entität mit Zustand, Schlüssel und deutschem Namen."""
    zustand = hass.states.get(eintrag.entity_id)
    hat_wert = bool(zustand) and zustand.state.lower() not in OHNE_WERT
    try:
        zahl = float(zustand.state) if hat_wert else None
    except (TypeError, ValueError):
        zahl = None
    bereich = eintrag.entity_id.split(".")[0]
    return {
        "entity_id": eintrag.entity_id,
        "name": kurzname(eintrag.name or eintrag.original_name or eintrag.entity_id),
        # Muster und Hilfetexte sind deutsch und suchen hier, nicht im Anzeigenamen.
        "name_de": stand.deutsche_namen(eintrag),
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
        "optionen": stand.auswahltexte.get(eintrag.unique_id, {}),
        # Eigene Bezeichnung eines Zeitprogramms; der Name bleibt der der Anlage.
        "bezeichnung": bezeichnung_lesen(eintrag),
        # Meldungssensoren des Knotens (`client/gemeinsam.MELDUNGS_SENSOREN`).
        "meldungsart": _meldungsart(eintrag.unique_id),
    }


def _entitaeten_einsortieren(
    hass: HomeAssistant, teile: dict[str, dict[str, Any]], stand: _Lesestand, benutzer: Any
) -> None:
    """Jedem Teil seine sichtbaren Entitäten anhängen – je Gerät, nicht über die ganze Registry."""
    entitaeten_registry = er.async_get(hass)
    for geraet_id, teil in teile.items():
        for eintrag in er.async_entries_for_device(entitaeten_registry, geraet_id):
            if eintrag.platform != DOMAIN:
                continue
            if eintrag.disabled_by is not None or eintrag.hidden_by is not None:
                continue
            # Was Home Assistant dem Anfragenden verwehrt, steht auch hier nicht.
            if not darf_lesen(benutzer, eintrag.entity_id):
                continue
            teil["entitaeten"].append(_entitaet(hass, eintrag, stand))


def _gruppieren(teile: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Anlagenteile ihren Steuerungen zuordnen.

    Die Steuerungen selbst tragen keine Entitäten und erscheinen nur als Gruppe.
    """
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
                # Der Config-Eintrag; seine Sprache gilt für die Seiten der Anlage.
                "eintrag": teil["eintrag"],
                "teile": [],
            },
        )
        gruppe["teile"].append(teil)
        teil["entitaeten"].sort(key=lambda e: e["name"])

    for gruppe in anlagen.values():
        _gruppe_abschliessen(gruppe)
    return sorted(anlagen.values(), key=lambda a: a["name"])


def anlagen_lesen(hass: HomeAssistant, benutzer: Any = None) -> list[dict[str, Any]]:
    """Anlagen mit ihren Anlagenteilen und deren sichtbaren Entitäten.

    Der Aufbau der Geräte spiegelt die Anlage wider: Heizungsanlage →
    Steuerung (eine Adresse) → Funktion. Die Steuerung trägt den Namen, den
    der Nutzer bei der Einrichtung vergeben hat ("Kesselhaus", "Werkstatt"), und
    genau der macht zwei gleichnamige Pufferlademodule unterscheidbar.
    """
    stand = _lesestand(hass)
    teile = _eigene_teile(hass, stand)
    _entitaeten_einsortieren(hass, teile, stand, benutzer)
    return _gruppieren(teile)


def voller_name(anlage: dict[str, Any], teil: dict[str, Any]) -> str:
    """Anlagenteil mit vorangestellter Anlage."""
    return f"{anlage['name']} · {teil['name']}" if anlage["name"] else teil["name"]
