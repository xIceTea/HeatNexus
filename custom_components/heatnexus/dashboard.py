"""Mitgeliefertes Dashboard.

Das Dashboard wird **in Home Assistant** aus der Geräte- und Entitätsliste
gebaut und als fertige Lovelace-Konfiguration ausgeliefert. Es gibt weder
eine Strategie-Datei im Browser noch feste Entitäts-IDs: Was die Anlage
liefert, erscheint; was fehlt, entfällt.

Der frühere Weg über eine JavaScript-Strategie hing daran, dass der Browser
das Modul rechtzeitig geladen hatte. Nach einem Neustart oder einer
Aktualisierung war das nicht der Fall und die Ansicht meldete nur
"Timeout waiting for strategy element". Serverseitig gebaut entfällt diese
ganze Fehlerquelle.

Aufbau: Übersicht (nach Anlage gruppiert) – Wartung – Auswertung – je
Anlagenteil eine Ansicht.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
from typing import Any

from homeassistant.components import frontend
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DASHBOARD_TITEL, DASHBOARD_URL, DOMAIN
from .schema import anlagenschema

_LOGGER = logging.getLogger(__name__)

# Fachliche Reihenfolge der Anlagenteile. Alphabetisch sortiert stünde der
# Puffer vor dem Kessel und ein von Hand benannter Heizkreis irgendwo
# dazwischen – hier bestimmt der Funktionstyp die Reihenfolge.
FCT_RANG: dict[int, int] = {
    25: 10,  # PuroWIN Hackgutkessel
    9: 10,  # BioWIN Pelletskessel
    1: 12,  # Kessel allgemein
    2: 12,
    10: 14,  # Kaskade / Zusatzkessel
    16: 20,  # Puffer
    14: 30,  # Heizkreis
    15: 32,  # Heizkreis / Umschaltung
    4: 40,  # Solar
    5: 42,  # Warmwasser
    6: 44,
    20: 50,  # Zirkulation
}
RANG_UNBEKANNT = 80

# Symbol je Anlagenteil für die Überschriften.
FCT_SYMBOL: dict[int, str] = {
    25: "mdi:fire",
    9: "mdi:fire",
    1: "mdi:fire",
    2: "mdi:fire",
    10: "mdi:fire",
    16: "mdi:storage-tank",
    14: "mdi:radiator",
    15: "mdi:radiator",
    4: "mdi:solar-power-variant",
    5: "mdi:water-boiler",
    6: "mdi:water-boiler",
    20: "mdi:pump",
}
SYMBOL_UNBEKANNT = "mdi:heating-coil"


def _muster(*ausdruecke: str) -> tuple[re.Pattern, ...]:
    return tuple(re.compile(a, re.IGNORECASE) for a in ausdruecke)


# Werte, die in der Übersicht zuerst stehen sollen.
UEBERSICHT_VORRANG = _muster(
    r"betriebsphase",
    r"betriebsart",
    r"betriebswahl",
    r"kesseltemperatur ist",
    r"kesselleistung",
    r"aktueller brennstoff",
    r"vorratsbeh",
    r"puffer oben",
    r"puffer unten",
    r"au(ß|ss)entemperatur",
    r"raumtemperatur ist",
    r"raumtemperatur soll",
    r"vorlauftemperatur ist",
    r"warmwasser",
    r"heizkreispumpe",
    r"pumpe",
    r"temperatur ist",
)

# Werte, die als Rundinstrument mehr sagen als eine Kachel.
RUNDINSTRUMENT: tuple[tuple[re.Pattern, dict], ...] = (
    (
        re.compile(r"kesseltemperatur ist", re.IGNORECASE),
        {"min": 0, "max": 95, "severity": {"green": 55, "yellow": 80, "red": 88}},
    ),
    (re.compile(r"kesselleistung", re.IGNORECASE), {"min": 0, "max": 100}),
    (
        re.compile(r"puffer oben", re.IGNORECASE),
        {"min": 0, "max": 95, "severity": {"green": 60, "yellow": 80, "red": 90}},
    ),
    (
        re.compile(r"puffer unten", re.IGNORECASE),
        {"min": 0, "max": 95, "severity": {"green": 40, "yellow": 70, "red": 85}},
    ),
)

# Wartungsansicht: Restlaufzeiten, Zähler, Brennstoff.
WARTUNG_RESTLAUFZEIT = _muster(r"laufzeit bis")
WARTUNG_WEITERE = _muster(
    r"vorratsbeh",
    r"aktueller brennstoff",
    r"gew(ä|ae)hlter brennstoff",
    r"reinigung best",
    r"betriebsstunden",
    r"brennerstarts",
    r"serviceausbrand",
)

# Schaubild-Ansicht: der Zustand der Anlage in Kurzform.
ZUSTAND = _muster(
    r"betriebsphase",
    r"meldung klartext",
    r"au(ß|ss)entemperatur",
    r"kesselleistung",
    r"aktueller brennstoff",
    r"vorratsbeh",
)

# Auswertung: was in einen Verlauf gehört.
VERLAUF = _muster(
    r"kesseltemperatur",
    r"abgastemperatur",
    r"puffer oben",
    r"puffer unten",
    r"vorlauftemperatur",
    r"raumtemperatur",
    r"au(ß|ss)entemperatur",
    r"kesselleistung",
    r"r(ü|ue)cklauf temperatur",
)

# Plattformen, die der Nutzer bedient statt nur abliest.
BEDIENBAR = frozenset({"climate", "select", "number", "switch", "button", "time", "date"})

# Eingriffe, bei denen vor dem Auslösen nachgefragt wird. Gefragt wird nur dort,
# wo ein Fehlgriff Arbeit macht, Brennstoff kostet oder die Anlage tagelang
# anders fährt – nicht aus Prinzip: Eine Rückfrage, die immer kommt, klickt man
# irgendwann blind weg.
RUECKFRAGE: tuple[tuple[re.Pattern, str], ...] = (
    (
        re.compile(r"^kessel$", re.IGNORECASE),
        "Damit wird der Kessel ein- bzw. ausgeschaltet. Ausgeschaltet heizt er "
        "weder Heizkreise noch Warmwasser – nur der Frostschutz bleibt aktiv.",
    ),
    (
        re.compile(r"serviceausbrand", re.IGNORECASE),
        "Der Kessel brennt den restlichen Brennstoff aus und geht danach in den "
        "Stillstand. Das dauert und verbraucht Brennstoff. Wirklich auslösen?",
    ),
    (
        re.compile(r"reinigung best", re.IGNORECASE),
        "Damit meldest du der Anlage, dass die Reinigung erledigt ist: Die "
        "Wartungszähler beginnen von vorn. Wirklich bestätigen?",
    ),
    # Die einzelnen Bestätigungstasten fragen jede für sich nach – sie setzen
    # je einen Wartungszähler zurück, und ein Fehlgriff fällt erst auf, wenn
    # die Anlage Monate später zu spät warnt.
    (
        re.compile(r"hauptreinigung und aschetonnen durchgef", re.IGNORECASE),
        "Wurde die Hauptreinigung durchgeführt und wurden die Aschetonnen "
        "entleert? Die Anlage setzt beide Zähler zurück.",
    ),
    (
        re.compile(r"hauptreinigung durchgef", re.IGNORECASE),
        "Wurde die Hauptreinigung durchgeführt? Die Anlage setzt den Zähler "
        "für die Hauptreinigung zurück.",
    ),
    (
        re.compile(r"^reinigung durchgef", re.IGNORECASE),
        "Wurde die Reinigung durchgeführt? Die Anlage setzt den Reinigungszähler zurück.",
    ),
    (
        re.compile(r"wartung durchgef", re.IGNORECASE),
        "Wurde die Wartung durchgeführt? Die Anlage setzt den Zähler für die Wartung zurück.",
    ),
    (
        re.compile(r"gew(ä|ae)hlter brennstoff", re.IGNORECASE),
        "Die Verbrennungsregelung stellt sich auf den gewählten Brennstoff ein. "
        "Passt die Angabe nicht zum tatsächlichen Vorrat, läuft der Kessel "
        "schlechter. Die Änderung wirkt erst, nachdem der Kessel am "
        "Hauptschalter aus- und wieder eingeschaltet wurde. Wirklich umstellen?",
    ),
    (
        re.compile(r"estrich", re.IGNORECASE),
        "Das Estrichprogramm fährt ein festes Temperaturprofil über Tage und "
        "lässt sich nicht einfach abbrechen. Wirklich starten?",
    ),
    (
        re.compile(r"legionellen", re.IGNORECASE),
        "Die Legionellenschaltung heizt den Speicher auf hohe Temperatur. Wirklich auslösen?",
    ),
    (
        re.compile(r"lagerraumbef(ü|ue)llung anfordern|lagerraum bef(ü|ue)llen", re.IGNORECASE),
        "Soll die Lagerraumbefüllung jetzt durchgeführt werden? Die Anlage "
        "gibt sie nur frei, wenn ihr Zustand das zulässt – ob sie freigegeben "
        "ist und wie lange noch, steht danach unter „Lagerraum befüllen”.",
    ),
)


def rueckfrage(name: str) -> str:
    """Rückfragetext für einen Datenpunkt – leer heißt: ohne Nachfrage."""
    for muster, text in RUECKFRAGE:
        if muster.search(name):
            return text
    return ""


# Zustände, mit denen sich keine Karte lohnt.
OHNE_WERT = frozenset({"unavailable", "unknown", "none", ""})

# Höchstzahl der Kacheln, die ein Anlagenteil in der Übersicht bekommt.
UEBERSICHT_MAX = 8
# Höchstzahl der Linien in einem Verlaufsdiagramm.
VERLAUF_MAX = 6


def _kurzname(name: str | None) -> str:
    """Name ohne das vorangestellte Anlagenkürzel."""
    return (name or "").split(" · ")[-1].strip()


def _rang(fct_type: Any) -> int:
    """Platz eines Anlagenteils in der fachlichen Reihenfolge."""
    try:
        return FCT_RANG.get(int(fct_type), RANG_UNBEKANNT)
    except (TypeError, ValueError):
        return RANG_UNBEKANNT


def _symbol(fct_type: Any) -> str:
    """Symbol eines Anlagenteils."""
    try:
        return FCT_SYMBOL.get(int(fct_type), SYMBOL_UNBEKANNT)
    except (TypeError, ValueError):
        return SYMBOL_UNBEKANNT


def _vorrang(name: str) -> int:
    """Position eines Werts in der Übersicht; kleiner heißt weiter oben."""
    for platz, muster in enumerate(UEBERSICHT_VORRANG):
        if muster.search(name):
            return platz
    return len(UEBERSICHT_VORRANG)


def _passt(name: str, muster: tuple[re.Pattern, ...]) -> bool:
    return any(m.search(name) for m in muster)


def _skala(wert: float | None) -> int:
    """Obere Grenze einer Restlaufzeit-Skala, auf 100 aufgerundet."""
    if not wert or wert <= 0:
        return 100
    return max(100, -(-int(wert) // 100) * 100)


def _fct_je_geraet(hass: HomeAssistant) -> dict[str, Any]:
    """Funktionstyp je Gerätekennung aus den Beschreibungen der Anlagen."""
    zuordnung: dict[str, Any] = {}
    for eintrag in hass.data.get(DOMAIN, {}).values():
        if not isinstance(eintrag, dict):
            continue
        for coordinator in (eintrag.get("coordinators") or {}).values():
            for beschreibung in (coordinator.data or {}).get("devices", []):
                kennung = beschreibung.get("device_id")
                if kennung and beschreibung.get("fct_type") is not None:
                    zuordnung.setdefault(kennung, beschreibung["fct_type"])
    return zuordnung


def _anlagen(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Anlagen mit ihren Anlagenteilen und deren sichtbaren Entitäten.

    Der Aufbau der Geräte spiegelt die Anlage wider: Heizungsanlage →
    Steuerung (eine Adresse) → Funktion. Die Steuerung trägt den Namen, den
    der Nutzer bei der Einrichtung vergeben hat ("Heizhaus", "Wohnhaus"), und
    genau der macht zwei gleichnamige Pufferlademodule unterscheidbar.
    """
    geraete_registry = dr.async_get(hass)
    entitaeten_registry = er.async_get(hass)
    fct_je_geraet = _fct_je_geraet(hass)

    teile: dict[str, dict[str, Any]] = {}
    for geraet in geraete_registry.devices.values():
        kennung = next((w for bereich, w in geraet.identifiers if bereich == DOMAIN), None)
        if kennung is None:
            continue
        fct = fct_je_geraet.get(kennung)
        teile[geraet.id] = {
            "name": _kurzname(geraet.name_by_user or geraet.name),
            "id": geraet.id,
            "anlage_id": geraet.via_device_id,
            "fct_type": fct,
            "rang": _rang(fct),
            "symbol": _symbol(fct),
            "entitaeten": [],
        }

    for eintrag in entitaeten_registry.entities.values():
        if eintrag.platform != DOMAIN:
            continue
        if eintrag.disabled_by is not None or eintrag.hidden_by is not None:
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
        teil["entitaeten"].append(
            {
                "entity_id": eintrag.entity_id,
                "name": _kurzname(eintrag.name or eintrag.original_name or eintrag.entity_id),
                "kategorie": eintrag.entity_category,
                "bereich": eintrag.entity_id.split(".")[0],
                "hat_wert": hat_wert,
                "wert": zahl,
                "state_class": (zustand.attributes.get("state_class") if zustand else None),
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
            {"name": _kurzname((teile.get(anlage_id) or {}).get("name")), "teile": []},
        )
        gruppe["teile"].append(teil)
        teil["entitaeten"].sort(key=lambda e: e["name"])

    for gruppe in anlagen.values():
        gruppe["teile"].sort(key=lambda t: (t["rang"], t["name"]))

    return sorted(anlagen.values(), key=lambda a: a["name"])


def _mehrfach_vergebene_namen(anlagen: list[dict[str, Any]]) -> set[str]:
    """Namen, die in mehr als einem Anlagenteil vorkommen.

    Zwei Pufferlademodule heißen beide "B-PLMi PUFFER". In den Reitern muss
    dann die Anlage davor, sonst sind sie nicht auseinanderzuhalten.
    """
    gesehen: dict[str, int] = {}
    for anlage in anlagen:
        for teil in anlage["teile"]:
            gesehen[teil["name"]] = gesehen.get(teil["name"], 0) + 1
    return {name for name, anzahl in gesehen.items() if anzahl > 1}


def _voller_name(anlage: dict[str, Any], teil: dict[str, Any]) -> str:
    """Anlagenteil mit vorangestellter Anlage."""
    return f"{anlage['name']} · {teil['name']}" if anlage["name"] else teil["name"]


# ---------------------------------------------------------------------------
# Karten
# ---------------------------------------------------------------------------
def _karte(eintrag: dict[str, Any], rundinstrument: bool = False) -> dict[str, Any]:
    """Passende Karte für eine Entität."""
    if eintrag["bereich"] == "climate":
        return {"type": "thermostat", "entity": eintrag["entity_id"]}
    if rundinstrument:
        for muster, form in RUNDINSTRUMENT:
            if muster.search(eintrag["name"]):
                return {
                    "type": "gauge",
                    "entity": eintrag["entity_id"],
                    "name": eintrag["name"],
                    "needle": True,
                    **form,
                }
    karte: dict[str, Any] = {
        "type": "tile",
        "entity": eintrag["entity_id"],
        "name": eintrag["name"],
    }
    if (frage := rueckfrage(eintrag["name"])) and (
        aktion := _schaltaktion(eintrag["bereich"], eintrag["entity_id"])
    ):
        # Nur das Symbol schaltet; ein Tippen auf die Kachel öffnet weiterhin
        # die Detailansicht und braucht keine Rückfrage.
        karte["icon_tap_action"] = {**aktion, "confirmation": {"text": frage}}
    return karte


def _schaltaktion(bereich: str, entity_id: str) -> dict[str, Any] | None:
    """Die Aktion, die das Symbol einer Kachel auslöst."""
    if bereich == "switch":
        return {"action": "toggle"}
    if bereich == "button":
        return {
            "action": "perform-action",
            "perform_action": "button.press",
            "target": {"entity_id": entity_id},
        }
    return None


def _ueberschrift(titel: str, symbol: str | None = None, stil: str = "title") -> dict[str, Any]:
    karte: dict[str, Any] = {"type": "heading", "heading": titel, "heading_style": stil}
    if symbol:
        karte["icon"] = symbol
    return karte


def _abschnitt(
    titel: str, karten: list[dict[str, Any]], symbol: str | None = None, stil: str = "title"
) -> list[dict[str, Any]]:
    """Ein Abschnitt mit Überschrift – oder gar keiner, wenn nichts drin ist."""
    if not karten:
        return []
    return [{"type": "grid", "cards": [_ueberschrift(titel, symbol, stil), *karten]}]


def _ansicht(
    titel: str, pfad: str, symbol: str, abschnitte: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "title": titel,
        "path": pfad,
        "icon": symbol,
        "type": "sections",
        "max_columns": 3,
        "sections": abschnitte,
    }


# ---------------------------------------------------------------------------
# Ansichten
# ---------------------------------------------------------------------------
def _uebersicht(anlagen: list[dict[str, Any]]) -> dict[str, Any]:
    """Erste Ansicht: je Anlagenteil die wichtigsten Werte."""
    abschnitte: list[dict[str, Any]] = []
    for anlage in anlagen:
        for teil in anlage["teile"]:
            messwerte = [
                e
                for e in teil["entitaeten"]
                if e["kategorie"] is None
                and e["hat_wert"]
                and e["bereich"] not in ("button", "time", "date")
            ]
            messwerte.sort(key=lambda e: (_vorrang(e["name"]), e["name"]))
            abschnitte += _abschnitt(
                _voller_name(anlage, teil),
                [_karte(e, rundinstrument=True) for e in messwerte[:UEBERSICHT_MAX]],
                teil["symbol"],
            )

    meldungen = [
        e
        for anlage in anlagen
        for teil in anlage["teile"]
        for e in teil["entitaeten"]
        if e["kategorie"] == "diagnostic" and "klartext" in e["name"].lower()
    ]
    abschnitte += _abschnitt(
        "Meldungen", [_karte(e) for e in meldungen], "mdi:alert-circle-outline"
    )

    return _ansicht("Übersicht", "uebersicht", "mdi:view-dashboard-outline", abschnitte)


def _anlagenbild(anlagen: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Ansicht „Anlage": das Schaubild mit den Werten darauf.

    Je Anlage ein Schaubild, darunter der Zustand in Kurzform – Meldung,
    Betriebsphase, Außentemperatur.
    """
    abschnitte: list[dict[str, Any]] = []
    for anlage in anlagen:
        bild = anlagenschema(anlage["teile"])
        if bild is None:
            continue
        abschnitte += _abschnitt(anlage["name"] or "Anlage", [bild], "mdi:sitemap-outline")

        zustand = [
            e
            for teil in anlage["teile"]
            for e in teil["entitaeten"]
            if e["hat_wert"] and _passt(e["name"], ZUSTAND)
        ]
        abschnitte += _abschnitt(
            "Zustand", [_karte(e) for e in zustand], "mdi:information-outline", stil="subtitle"
        )

    if not abschnitte:
        return None
    return _ansicht("Anlage", "anlage", "mdi:sitemap-outline", abschnitte)


def _wartung(anlagen: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Restlaufzeiten, Zähler und Brennstoff – alles, was Arbeit ankündigt."""
    abschnitte: list[dict[str, Any]] = []
    for anlage in anlagen:
        for teil in anlage["teile"]:
            restlaufzeit = [
                e
                for e in teil["entitaeten"]
                if e["hat_wert"] and _passt(e["name"], WARTUNG_RESTLAUFZEIT)
            ]
            weitere = [
                e
                for e in teil["entitaeten"]
                if e["hat_wert"] and _passt(e["name"], WARTUNG_WEITERE)
            ]
            if not restlaufzeit and not weitere:
                continue

            # Rundinstrument: Der Abstand zur Null ist auf einen Blick zu
            # sehen, eine Zahl allein sagt das nicht. Die Skala richtet sich
            # nach dem aktuellen Stand – die Wartungsintervalle der Anlagen
            # reichen von wenigen Dutzend bis über tausend Stunden.
            karten: list[dict[str, Any]] = [
                {
                    "type": "gauge",
                    "entity": e["entity_id"],
                    "name": e["name"].replace("Laufzeit bis ", ""),
                    "needle": True,
                    "min": 0,
                    "max": _skala(e["wert"]),
                    # Absteigend gelesen: unter 20 h gelb, unter 5 h rot.
                    "severity": {"green": 20, "yellow": 5, "red": 0},
                }
                for e in restlaufzeit
            ]
            karten += [_karte(e) for e in weitere]
            abschnitte += _abschnitt(_voller_name(anlage, teil), karten, "mdi:wrench-clock")

    if not abschnitte:
        return None
    return _ansicht("Wartung", "wartung", "mdi:wrench-clock", abschnitte)


def _auswertung(anlagen: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Verläufe und Zählerstände über die Zeit."""
    abschnitte: list[dict[str, Any]] = []

    # Zähler: Home Assistant führt für total_increasing eine Langzeitstatistik.
    # Damit lässt sich der Zuwachs eines Tages/Monats direkt anzeigen – ohne
    # Hilfsentität und ohne eigene Automation.
    zaehler = [
        (anlage, teil, e)
        for anlage in anlagen
        for teil in anlage["teile"]
        for e in teil["entitaeten"]
        if e["state_class"] == "total_increasing"
    ]
    for zeitraum, beschriftung in (("day", "heute"), ("month", "dieser Monat")):
        karten = [
            {
                "type": "statistic",
                "entity": e["entity_id"],
                "name": f"{e['name']} {beschriftung}",
                "stat_type": "change",
                "period": {"calendar": {"period": zeitraum}},
            }
            for _anlage, _teil, e in zaehler
        ]
        abschnitte += _abschnitt(f"Zähler – {beschriftung}", karten, "mdi:counter", stil="subtitle")

    for anlage in anlagen:
        for teil in anlage["teile"]:
            verlauf = [
                e
                for e in teil["entitaeten"]
                if e["hat_wert"] and e["bereich"] == "sensor" and _passt(e["name"], VERLAUF)
            ]
            if not verlauf:
                continue
            abschnitte += _abschnitt(
                _voller_name(anlage, teil),
                [
                    {
                        "type": "history-graph",
                        "hours_to_show": 48,
                        "entities": [
                            {"entity": e["entity_id"], "name": e["name"]}
                            for e in verlauf[:VERLAUF_MAX]
                        ],
                    }
                ],
                teil["symbol"],
            )

    if not abschnitte:
        return None
    return _ansicht("Auswertung", "auswertung", "mdi:chart-line", abschnitte)


def _geraeteansicht(
    anlage: dict[str, Any], teil: dict[str, Any], mehrdeutig: set[str]
) -> dict[str, Any]:
    """Eine Ansicht je Anlagenteil, nach Verwendungszweck gegliedert."""
    entitaeten = teil["entitaeten"]
    bedienbar = [e for e in entitaeten if e["bereich"] in BEDIENBAR]
    messwerte = [e for e in entitaeten if e not in bedienbar and e["kategorie"] is None]
    einstellungen = [e for e in entitaeten if e not in bedienbar and e["kategorie"] == "config"]
    diagnose = [e for e in entitaeten if e["kategorie"] == "diagnostic"]

    titel = _voller_name(anlage, teil) if teil["name"] in mehrdeutig else teil["name"]
    return _ansicht(
        titel,
        f"teil-{teil['id'][:8]}",
        teil["symbol"],
        [
            *_abschnitt("Bedienung", [_karte(e) for e in bedienbar], "mdi:tune"),
            *_abschnitt("Messwerte", [_karte(e) for e in messwerte], "mdi:gauge"),
            *_abschnitt("Einstellungen", [_karte(e) for e in einstellungen], "mdi:cog-outline"),
            *_abschnitt("Diagnose", [_karte(e) for e in diagnose], "mdi:stethoscope"),
        ],
    )


def dashboard_konfiguration(hass: HomeAssistant) -> dict[str, Any]:
    """Die vollständige Lovelace-Konfiguration des Dashboards."""
    anlagen = _anlagen(hass)
    if not anlagen:
        return {
            "title": DASHBOARD_TITEL,
            "views": [
                {
                    "title": "HeatNexus",
                    "cards": [
                        {
                            "type": "markdown",
                            "content": (
                                "### Keine Anlage gefunden\n\n"
                                "Richte die Integration **HeatNexus** unter "
                                "Einstellungen → Geräte & Dienste ein."
                            ),
                        }
                    ],
                }
            ],
        }

    mehrdeutig = _mehrfach_vergebene_namen(anlagen)
    views: list[dict[str, Any]] = [_uebersicht(anlagen)]
    for ansicht in (_anlagenbild(anlagen), _wartung(anlagen), _auswertung(anlagen)):
        if ansicht:
            views.append(ansicht)
    views += [
        _geraeteansicht(anlage, teil, mehrdeutig) for anlage in anlagen for teil in anlage["teile"]
    ]
    return {"title": DASHBOARD_TITEL, "views": views}


async def async_setup_dashboard(hass: HomeAssistant) -> None:
    """Dashboard in der Seitenleiste anmelden.

    Schlägt das fehl, bleibt die Integration trotzdem nutzbar – das
    Dashboard ist Beiwerk, keine Voraussetzung.
    """
    try:
        await _async_setup_dashboard(hass)
    except Exception as err:
        _LOGGER.warning("Dashboard konnte nicht angemeldet werden: %s", err)


async def _async_setup_dashboard(hass: HomeAssistant) -> None:
    """Eigentliche Anmeldung."""
    if hass.data.get(f"{DOMAIN}_dashboard"):
        return

    try:
        from homeassistant.components.lovelace.const import (
            LOVELACE_DATA,
            MODE_YAML,
        )
        from homeassistant.components.lovelace.dashboard import LovelaceConfig
        from homeassistant.helpers.json import json_fragment
    except ImportError as err:  # pragma: no cover - ältere Home-Assistant-Fassung
        _LOGGER.warning("Dashboard nicht verfügbar: %s", err)
        return

    class HeatNexusDashboard(LovelaceConfig):
        """Baut die Ansichten bei jedem Öffnen neu aus der Registry."""

        def __init__(self) -> None:
            """Dashboard ohne eigene Konfigurationsdatei."""
            super().__init__(hass, DASHBOARD_URL, {"mode": MODE_YAML})

        @property
        def mode(self) -> str:
            """Der Inhalt kommt aus der Integration, nicht aus dem Speicher."""
            return MODE_YAML

        async def async_get_info(self) -> dict[str, Any]:
            """Kurzinfo für die Dashboard-Übersicht."""
            return {"mode": MODE_YAML}

        async def async_load(self, force: bool) -> dict[str, Any]:
            """Inhalt des Dashboards."""
            return dashboard_konfiguration(hass)

        async def async_json(self, force: bool) -> Any:
            """Inhalt als vorbereitetes JSON."""
            return json_fragment(json.dumps(dashboard_konfiguration(hass)))

    daten = hass.data.get(LOVELACE_DATA)
    if daten is None:
        _LOGGER.warning("Dashboards stehen noch nicht bereit")
        return

    if DASHBOARD_URL not in daten.dashboards:
        daten.dashboards[DASHBOARD_URL] = HeatNexusDashboard()

    # Ein bestehendes Panel mit dieser Adresse ist kein Fehler.
    with contextlib.suppress(ValueError):
        # Ausschließlich benannte Parameter: Home Assistant hat die Reihenfolge
        # bereits erweitert (sidebar_default_visible), eine Übergabe nach
        # Position würde damit still die falschen Felder belegen.
        frontend.async_register_built_in_panel(
            hass,
            component_name="lovelace",
            sidebar_title=DASHBOARD_TITEL,
            sidebar_icon="mdi:fire",
            frontend_url_path=DASHBOARD_URL,
            config={"mode": MODE_YAML, "urlPath": DASHBOARD_URL},
            require_admin=False,
            update=True,
        )

    hass.data[f"{DOMAIN}_dashboard"] = True
    _LOGGER.info("Dashboard %s in der Seitenleiste angemeldet", DASHBOARD_TITEL)


async def async_remove_dashboard(hass: HomeAssistant) -> None:
    """Das Dashboard wieder aus der Seitenleiste nehmen."""
    if not hass.data.pop(f"{DOMAIN}_dashboard", None):
        return
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA
    except ImportError:  # pragma: no cover
        return

    daten = hass.data.get(LOVELACE_DATA)
    if daten is not None:
        daten.dashboards.pop(DASHBOARD_URL, None)
    frontend.async_remove_panel(hass, DASHBOARD_URL)
    _LOGGER.info("Dashboard %s entfernt", DASHBOARD_TITEL)
