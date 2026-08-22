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

from homeassistant.components import frontend, websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
import voluptuous as vol
import yaml

from .const import (
    CONF_KESSELART,
    CONF_KESSELWERT,
    CONF_MODULPUMPE,
    DASHBOARD_TITEL,
    DASHBOARD_URL,
    DOMAIN,
    KARTE_ELEMENT,
    KESSELART_AUTO,
    KESSELWERT_LEISTUNG,
)
from .kanonisch import gnmn, ist_ableitung
from .kanonisch import schluessel as kanonischer_schluessel
from .schema import anlagenschema, kesselart_erkennen
from .schema import passt as _passt
from .schema import traegt as _traegt
from .symbole import symbol_je_fct

_LOGGER = logging.getLogger(__name__)

# Fachliche Reihenfolge der Anlagenteile. Alphabetisch sortiert stünde der
# Puffer vor dem Kessel und ein von Hand benannter Heizkreis irgendwo
# dazwischen – hier bestimmt der Funktionstyp die Reihenfolge.
#
# Welche Zahl welche Funktion ist, steht belegt in `schema.ART_JE_FCT` und in
# `docs/_includes/DATAPOINTS.md`. **Nicht nach Namen raten** – die Zuordnung stammt aus
# der Parameterliste des Herstellers. Typen ohne Beleg stehen nicht in der
# Liste und landen hinten.
FCT_RANG: dict[int, int] = {
    25: 10,  # PuroWIN Hackgutkessel
    9: 10,  # BioWIN Pelletskessel
    7: 10,  # Wärmepumpe
    26: 10,  # Wärmepumpe (Energiemanagement)
    27: 10,  # Wärmepumpe
    6: 12,  # Gas-/Ölkessel
    8: 12,  # E-Heizung / Zusatzheizung
    10: 14,  # Automatik-/Zusatzkessel
    4: 16,  # Kaskade ("KAS")
    15: 18,  # Umschaltung Automatikkessel / Festbrennstoff / Puffer
    16: 20,  # Puffer (B-PLMi)
    21: 22,  # Puffer
    24: 24,  # Pumpe Wärmeerzeuger / Schichtladung
    1: 30,  # Heizkreis (Infinity PLUS)
    14: 30,  # Heizkreis (UML / UMLZ)
    2: 42,  # Warmwasser
    5: 44,  # Solar
    20: 50,  # ZSP Pumpen-/Relaismodul
}
RANG_UNBEKANNT = 80


def _muster(*ausdruecke: str) -> tuple[re.Pattern, ...]:
    return tuple(re.compile(a, re.IGNORECASE) for a in ausdruecke)


# Werte, die in der Übersicht zuerst stehen sollen.
# Je Zeile: Muster und die kanonischen Schlüssel, die dasselbe meinen.
UEBERSICHT_VORRANG: tuple[tuple[re.Pattern, tuple[str, ...]], ...] = (
    (re.compile(r"betriebsphase", re.IGNORECASE), ("operating_phase",)),
    (re.compile(r"betriebsart", re.IGNORECASE), ("operating_mode",)),
    (re.compile(r"betriebswahl", re.IGNORECASE), ("mode_selection",)),
    (re.compile(r"kesseltemperatur ist", re.IGNORECASE), ("boiler_temperature",)),
    (re.compile(r"kesselleistung", re.IGNORECASE), ("boiler_power",)),
    (re.compile(r"aktueller brennstoff", re.IGNORECASE), ("fuel_current",)),
    (re.compile(r"vorratsbeh", re.IGNORECASE), ("fuel_storage_status",)),
    (re.compile(r"puffer oben", re.IGNORECASE), ("buffer_top",)),
    (re.compile(r"puffer unten", re.IGNORECASE), ("buffer_bottom",)),
    (re.compile(r"au(ß|ss)entemperatur", re.IGNORECASE), ("outdoor_temperature",)),
    (re.compile(r"raumtemperatur ist", re.IGNORECASE), ("room_temperature",)),
    (re.compile(r"raumtemperatur soll", re.IGNORECASE), ("room_temperature_target",)),
    (re.compile(r"vorlauftemperatur ist", re.IGNORECASE), ("flow_temperature",)),
    (re.compile(r"warmwasser", re.IGNORECASE), ("dhw_temperature",)),
    (re.compile(r"heizkreispumpe", re.IGNORECASE), ("circuit_pump",)),
    (re.compile(r"pumpe", re.IGNORECASE), ()),
    (re.compile(r"temperatur ist", re.IGNORECASE), ()),
)

# Werte, die als Rundinstrument mehr sagen als eine Kachel.
RUNDINSTRUMENT: tuple[tuple[re.Pattern, tuple[str, ...], dict], ...] = (
    (
        re.compile(r"kesseltemperatur ist", re.IGNORECASE),
        ("boiler_temperature",),
        {"min": 0, "max": 95, "severity": {"green": 55, "yellow": 80, "red": 88}},
    ),
    (re.compile(r"kesselleistung", re.IGNORECASE), ("boiler_power",), {"min": 0, "max": 100}),
    (
        re.compile(r"puffer oben", re.IGNORECASE),
        ("buffer_top",),
        {"min": 0, "max": 95, "severity": {"green": 60, "yellow": 80, "red": 90}},
    ),
    (
        re.compile(r"puffer unten", re.IGNORECASE),
        ("buffer_bottom",),
        {"min": 0, "max": 95, "severity": {"green": 40, "yellow": 70, "red": 85}},
    ),
)

# Wartungsansicht: Restlaufzeiten, Zähler, Brennstoff.
#
# Zu jeder Musterliste gehört eine Liste kanonischer Schlüssel. Sie steht
# daneben statt darin, weil die Muster hier als Liste ausgewertet werden und
# nicht Zeile für Zeile: Getroffen wird, was **eines** von beiden erfüllt.
WARTUNG_RESTLAUFZEIT = _muster(r"laufzeit bis")
WARTUNG_RESTLAUFZEIT_SCHLUESSEL = (
    "maintenance_ash_hours",
    "maintenance_cleaning_hours",
    "maintenance_main_cleaning_hours",
    "maintenance_service_hours",
)
WARTUNG_WEITERE = _muster(
    r"vorratsbeh",
    r"aktueller brennstoff",
    r"gew(ä|ae)hlter brennstoff",
    r"reinigung best",
    r"betriebsstunden",
    r"brennerstarts",
    r"serviceausbrand",
)
WARTUNG_WEITERE_SCHLUESSEL = (
    "fuel_storage_status",
    "fuel_current",
    "fuel_selected",
    "cleaning_confirm",
    "operating_hours",
    "burner_starts",
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
# „Meldung Klartext" hat keine Adresse: Der Text entsteht aus `FE01msg` und
# steht in keiner Datenpunkttabelle. Dort bleibt es beim Namen.
ZUSTAND_SCHLUESSEL = (
    "operating_phase",
    "outdoor_temperature",
    "boiler_power",
    "fuel_current",
    "fuel_storage_status",
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
VERLAUF_SCHLUESSEL = (
    "boiler_temperature",
    "flue_gas_temperature",
    "buffer_top",
    "buffer_bottom",
    "flow_temperature",
    "room_temperature",
    "outdoor_temperature",
    "boiler_power",
    "return_temperature",
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
        re.compile(r"kaminkehrer starten", re.IGNORECASE),
        "Der Kessel fährt auf die eingestellte Kaminkehrer-Leistung und hält "
        "sie für die Abgasmessung. Die Restzeit steht danach unter "
        "„Kaminkehrer”. Wirklich starten?",
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
    return symbol_je_fct(fct_type)


def _vorrang(eintrag: dict) -> int:
    """Position eines Werts in der Übersicht; kleiner heißt weiter oben.

    Auch hier gewinnt die Adresse: „Heizkreispumpe Nachlauf" träfe sonst die
    Zeile der Pumpe, bevor die Pumpe selbst an ihre kommt.
    """
    for platz, zeile in enumerate(UEBERSICHT_VORRANG):
        if _traegt(eintrag, zeile[1]):
            return platz
    for platz, zeile in enumerate(UEBERSICHT_VORRANG):
        if _passt(eintrag.get("name") or "", (zeile[0],)):
            return platz
    return len(UEBERSICHT_VORRANG)


def _trifft(eintrag: dict, muster: tuple[re.Pattern, ...], *schluessel: str) -> bool:
    """Erst am kanonischen Schlüssel, sonst am Namen.

    Der fehlende Schlüssel darf nicht als „passt nicht" gelten: Auf der
    Serviceebene gibt es Datenpunkte, die dieselbe Adresse an einer anderen
    Funktion tragen, und die Muster sind dort bisher die einzige Auskunft.
    """
    return _traegt(eintrag, schluessel) or _passt(eintrag.get("name") or "", muster)


def _skala(wert: float | None) -> int:
    """Obere Grenze einer Restlaufzeit-Skala, auf 100 aufgerundet."""
    if not wert or wert <= 0:
        return 100
    return max(100, -(-int(wert) // 100) * 100)


def _fct_je_geraet(hass: HomeAssistant) -> dict[str, Any]:
    """Funktionstyp je Gerätekennung aus den Beschreibungen der Anlagen."""
    zuordnung: dict[str, Any] = {}
    for entry in hass.config_entries.async_entries(DOMAIN):
        eintrag = getattr(entry, "runtime_data", None)
        if not isinstance(eintrag, dict):
            continue
        for coordinator in (eintrag.get("coordinators") or {}).values():
            for beschreibung in (coordinator.data or {}).get("devices", []):
                kennung = beschreibung.get("device_id")
                if kennung and beschreibung.get("fct_type") is not None:
                    zuordnung.setdefault(kennung, beschreibung["fct_type"])
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
    schaubildwahl_je_geraet = _schaubildwahl_je_geraet(hass)

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
                # Der sprachunabhängige Schlüssel, sofern der Datenpunkt einen
                # hat. Er kommt aus der Adresse in der Kennung und nicht aus
                # dem Namen – siehe `kanonisch.py`. Wo er fehlt, bleibt es beim
                # Namensmuster.
                "schluessel": kanonischer_schluessel(eintrag.unique_id),
                # Die rohe Datenpunktadresse. Sie erlaubt den Abgleich mit den
                # Ebenenlisten der Geräte-Datenbank – dort steht auch für
                # Baureihen etwas, für die es hier kein Namensmuster gibt.
                "adresse": gnmn(eintrag.unique_id),
                # Dazugewählte Ableitung statt eines Messwerts der Anlage. Die
                # festen Listen der Oberfläche übergehen sie.
                "abgeleitet": ist_ableitung(eintrag.unique_id),
                "kategorie": eintrag.entity_category,
                "bereich": eintrag.entity_id.split(".")[0],
                "hat_wert": hat_wert,
                "wert": zahl,
                # Der Zustand als Text: Zahlen stehen in "wert", aber die
                # Kesselart wird am gemeldeten Brennstoff erkannt, und der ist
                # ein Wort.
                "text": zustand.state if hat_wert else None,
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
            {
                # Die Kennung der Steuerung. Sie überlebt eine erneute
                # Erkennung und unterscheidet zwei gleich aufgebaute Anlagen –
                # der Name täte das auch, bis ihn jemand ändert.
                "id": anlage_id,
                "name": _kurzname((teile.get(anlage_id) or {}).get("name")),
                "teile": [],
            },
        )
        gruppe["teile"].append(teil)
        teil["entitaeten"].sort(key=lambda e: e["name"])

    for gruppe in anlagen.values():
        gruppe["teile"].sort(key=lambda t: (t["rang"], t["name"]))
        # Die ausdrückliche Auswahl schlägt die Erkennung; steht überall
        # "automatisch", entscheidet der gemeldete Brennstoff bzw. der Name.
        gewaehlt = next(
            (
                t["kesselart_wahl"]
                for t in gruppe["teile"]
                if t.get("kesselart_wahl") not in (None, KESSELART_AUTO)
            ),
            None,
        )
        gruppe["kesselart"] = gewaehlt or kesselart_erkennen(gruppe["teile"])
        # Welcher zweite Wert am Kessel steht. Die erste ausdrückliche Angabe
        # gilt; ohne Angabe bleibt es bei der Leistung.
        gruppe["kesselwert"] = next(
            (t["kesselwert_wahl"] for t in gruppe["teile"] if t.get("kesselwert_wahl")),
            KESSELWERT_LEISTUNG,
        )
        # Erst wenn eine Anlage eine Pumpe am Modul bestätigt, steht sie im Bild.
        gruppe["modulpumpe"] = any(t.get("modulpumpe_wahl") for t in gruppe["teile"])

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
        # Die Adresse zuerst, der Name als Rückfall – wie überall sonst.
        zeilen = [z for z in RUNDINSTRUMENT if _traegt(eintrag, z[1])] or [
            z for z in RUNDINSTRUMENT if _passt(eintrag.get("name") or "", (z[0],))
        ]
        if zeilen:
            return {
                "type": "gauge",
                "entity": eintrag["entity_id"],
                "name": eintrag["name"],
                "needle": True,
                **zeilen[0][2],
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
    titel: str,
    karten: list[dict[str, Any]],
    symbol: str | None = None,
    stil: str = "title",
    spanne: int = 0,
) -> list[dict[str, Any]]:
    """Ein Abschnitt mit Überschrift – oder gar keiner, wenn nichts drin ist.

    ``spanne`` gibt dem Abschnitt mehrere Spalten der Ansicht. Das Schaubild
    braucht sie: Neben dem Bild steht die Werteliste.
    """
    if not karten:
        return []
    grid: dict[str, Any] = {"type": "grid", "cards": [_ueberschrift(titel, symbol, stil), *karten]}
    if spanne > 1:
        grid["column_span"] = spanne
    return [grid]


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
            messwerte.sort(key=lambda e: (_vorrang(e), e["name"]))
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


def _zustandswerte(anlage: dict[str, Any]) -> list[dict[str, Any]]:
    """Der Zustand einer Anlage in Kurzform – Meldung, Betriebsphase, Außentemperatur."""
    return [
        e
        for teil in anlage["teile"]
        for e in teil["entitaeten"]
        # Einsteller bleiben draußen: Ein Grenzwert der Serviceebene heißt
        # mitunter wie der Messwert, den er begrenzt.
        if e["hat_wert"] and e.get("kategorie") is None and _trifft(e, ZUSTAND, *ZUSTAND_SCHLUESSEL)
    ]


def _anlagenbild(anlagen: list[dict[str, Any]], als_karte: bool = False) -> dict[str, Any] | None:
    """Ansicht „Anlage": das Schaubild mit den Werten darauf.

    ``als_karte`` setzt die eigene Lovelace-Karte ein statt der fertigen
    Zeichnung: Sie lässt sich im Editor bearbeiten. Das mitgelieferte
    Dashboard bleibt bei der Zeichnung, die kein Modul im Browser braucht.
    """
    abschnitte: list[dict[str, Any]] = []
    for anlage in anlagen:
        zustand = _zustandswerte(anlage)
        if als_karte:
            karte: dict[str, Any] = {
                "type": f"custom:{KARTE_ELEMENT}",
                "anlage": anlage["id"],
                "farbsatz": "auto",
                "schrift": "normal",
                "animation": True,
                "liste": "rechts",
                "titel_bild": "",
                "titel_liste": "Zustand",
                # Volle Breite: Bild und Werteliste stehen nebeneinander.
                "grid_options": {"columns": 24, "rows": "auto"},
            }
            if zustand:
                karte["zusatzwerte"] = [e["entity_id"] for e in zustand]
            abschnitte += _abschnitt(
                anlage["name"] or "Anlage", [karte], "mdi:sitemap-outline", spanne=2
            )
            continue

        bild = anlagenschema(
            anlage["teile"],
            anlage.get("kesselart"),
            modulpumpe=anlage.get("modulpumpe", False),
        )
        if bild is None:
            continue
        abschnitte += _abschnitt(anlage["name"] or "Anlage", [bild], "mdi:sitemap-outline")
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
                if e["hat_wert"]
                and _trifft(e, WARTUNG_RESTLAUFZEIT, *WARTUNG_RESTLAUFZEIT_SCHLUESSEL)
            ]
            weitere = [
                e
                for e in teil["entitaeten"]
                if e["hat_wert"] and _trifft(e, WARTUNG_WEITERE, *WARTUNG_WEITERE_SCHLUESSEL)
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
                if e["hat_wert"]
                and e["bereich"] == "sensor"
                and _trifft(e, VERLAUF, *VERLAUF_SCHLUESSEL)
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


def dashboard_konfiguration(hass: HomeAssistant, als_karte: bool = False) -> dict[str, Any]:
    """Die vollständige Lovelace-Konfiguration des Dashboards.

    ``als_karte`` ist für den Text zum Kopieren: Dort steht das Schaubild als
    eigene Karte statt als fertige Zeichnung.
    """
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
    for ansicht in (_anlagenbild(anlagen, als_karte), _wartung(anlagen), _auswertung(anlagen)):
        if ansicht:
            views.append(ansicht)
    views += [
        _geraeteansicht(anlage, teil, mehrdeutig) for anlage in anlagen for teil in anlage["teile"]
    ]
    return {"title": DASHBOARD_TITEL, "views": views}


def als_yaml(konfiguration: dict[str, Any]) -> str:
    """Eine Lovelace-Konfiguration als YAML zum Einfügen.

    Ohne Sortierung und ohne entwichene Zeichen: Der Text landet im
    Rohkonfigurations-Editor und wird dort gelesen.
    """
    return yaml.safe_dump(
        konfiguration, allow_unicode=True, sort_keys=False, default_flow_style=False
    )


def dashboard_als_yaml(hass: HomeAssistant) -> str:
    """Das erzeugte Dashboard als YAML – Grundlage für ein eigenes.

    Das Schaubild steht hier als eigene Karte: Sie lässt sich im Editor
    bearbeiten, und der Text bleibt lesbar statt eine eingebettete Zeichnung
    über Zehntausende Zeichen zu führen.
    """
    return als_yaml(dashboard_konfiguration(hass, als_karte=True))


# Das mitgelieferte Dashboard entsteht bei jedem Öffnen neu; Home Assistant
# sperrt Editor und Rohkonfiguration deshalb. Wer es abwandeln will, holt sich
# hier den Text und legt damit ein eigenes Dashboard an.
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/dashboard_yaml"})
@callback
def _ws_dashboard_yaml(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Das erzeugte Dashboard als Text zum Kopieren."""
    connection.send_result(msg["id"], {"yaml": dashboard_als_yaml(hass)})


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

    if not hass.data.get(f"{DOMAIN}_dashboard_ws"):
        websocket_api.async_register_command(hass, _ws_dashboard_yaml)
        hass.data[f"{DOMAIN}_dashboard_ws"] = True

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
