"""Mitgeliefertes Dashboard.

Das Dashboard wird **in Home Assistant** aus der Geräte- und Entitätsliste
gebaut und als fertige Lovelace-Konfiguration ausgeliefert. Es gibt weder
eine Strategie-Datei im Browser noch feste Entitäts-IDs: Was die Anlage
liefert, erscheint; was fehlt, entfällt.

Der frühere Weg über eine JavaScript-Strategie hing daran, dass der Browser
das Modul rechtzeitig geladen hatte. Nach einem Neustart oder einer
Aktualisierung war das nicht der Fall und die Ansicht meldete nur noch
"Timeout waiting for strategy element". Serverseitig gebaut entfällt diese
ganze Fehlerquelle.
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

# Werte, die in der Übersicht zuerst stehen sollen.
UEBERSICHT_VORRANG: tuple[re.Pattern, ...] = tuple(
    re.compile(muster, re.IGNORECASE)
    for muster in (
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

# Plattformen, die der Nutzer bedient statt nur abliest.
BEDIENBAR = frozenset({"climate", "select", "number", "switch", "button", "time", "date"})

# Höchstzahl der Kacheln, die ein Anlagenteil in der Übersicht bekommt.
UEBERSICHT_MAX = 8


def _kurzname(name: str | None) -> str:
    """Gerätenamen ohne das vorangestellte Steuerungskürzel."""
    return (name or "").split(" · ")[-1].strip()


def _rang(fct_type: Any) -> int:
    """Platz eines Anlagenteils in der fachlichen Reihenfolge."""
    try:
        return FCT_RANG.get(int(fct_type), RANG_UNBEKANNT)
    except (TypeError, ValueError):
        return RANG_UNBEKANNT


def _vorrang(name: str) -> int:
    """Position eines Werts in der Übersicht; kleiner heißt weiter oben."""
    for platz, muster in enumerate(UEBERSICHT_VORRANG):
        if muster.search(name):
            return platz
    return len(UEBERSICHT_VORRANG)


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


def _anlagenteile(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Alle Anlagenteile mit ihren sichtbaren Entitäten, fachlich sortiert."""
    geraete_registry = dr.async_get(hass)
    entitaeten_registry = er.async_get(hass)
    fct_je_geraet = _fct_je_geraet(hass)

    teile: dict[str, dict[str, Any]] = {}
    for geraet in geraete_registry.devices.values():
        kennung = next(
            (wert for bereich, wert in geraet.identifiers if bereich == DOMAIN),
            None,
        )
        if kennung is None:
            continue
        teile[geraet.id] = {
            "name": _kurzname(geraet.name_by_user or geraet.name),
            "id": geraet.id,
            "rang": _rang(fct_je_geraet.get(kennung)),
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
        teil["entitaeten"].append(
            {
                "entity_id": eintrag.entity_id,
                "name": _kurzname(eintrag.name or eintrag.original_name or eintrag.entity_id),
                "kategorie": eintrag.entity_category,
                "bereich": eintrag.entity_id.split(".")[0],
            }
        )

    mit_werten = [teil for teil in teile.values() if teil["entitaeten"]]
    mit_werten.sort(key=lambda teil: (teil["rang"], teil["name"]))
    for teil in mit_werten:
        teil["entitaeten"].sort(key=lambda e: e["name"])
    return mit_werten


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
    return {"type": "tile", "entity": eintrag["entity_id"], "name": eintrag["name"]}


def _abschnitt(titel: str, karten: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ein Abschnitt mit Überschrift – oder gar keiner, wenn nichts drin ist."""
    if not karten:
        return []
    return [
        {
            "type": "grid",
            "cards": [
                {"type": "heading", "heading": titel, "heading_style": "title"},
                *karten,
            ],
        }
    ]


def _uebersicht(teile: list[dict[str, Any]]) -> dict[str, Any]:
    """Erste Ansicht: je Anlagenteil die wichtigsten Werte."""
    abschnitte: list[dict[str, Any]] = []
    for teil in teile:
        messwerte = [
            e
            for e in teil["entitaeten"]
            if e["kategorie"] is None and e["bereich"] not in ("button", "time", "date")
        ]
        messwerte.sort(key=lambda e: (_vorrang(e["name"]), e["name"]))
        abschnitte += _abschnitt(
            teil["name"],
            [_karte(e, rundinstrument=True) for e in messwerte[:UEBERSICHT_MAX]],
        )

    meldungen = [
        e
        for teil in teile
        for e in teil["entitaeten"]
        if e["kategorie"] == "diagnostic" and "meldung" in e["name"].lower()
    ]
    abschnitte += _abschnitt("Meldungen", [_karte(e) for e in meldungen])

    return {
        "title": "Übersicht",
        "path": "uebersicht",
        "icon": "mdi:fire",
        "type": "sections",
        "max_columns": 3,
        "sections": abschnitte,
    }


def _geraeteansicht(teil: dict[str, Any]) -> dict[str, Any]:
    """Eine Ansicht je Anlagenteil, nach Verwendungszweck gegliedert."""
    entitaeten = teil["entitaeten"]
    bedienbar = [e for e in entitaeten if e["bereich"] in BEDIENBAR]
    messwerte = [e for e in entitaeten if e not in bedienbar and e["kategorie"] is None]
    einstellungen = [e for e in entitaeten if e not in bedienbar and e["kategorie"] == "config"]
    diagnose = [e for e in entitaeten if e["kategorie"] == "diagnostic"]

    return {
        "title": teil["name"],
        "path": f"teil-{teil['id'][:8]}",
        "type": "sections",
        "max_columns": 3,
        "sections": [
            *_abschnitt("Bedienung", [_karte(e) for e in bedienbar]),
            *_abschnitt("Messwerte", [_karte(e) for e in messwerte]),
            *_abschnitt("Einstellungen", [_karte(e) for e in einstellungen]),
            *_abschnitt("Diagnose", [_karte(e) for e in diagnose]),
        ],
    }


def dashboard_konfiguration(hass: HomeAssistant) -> dict[str, Any]:
    """Die vollständige Lovelace-Konfiguration des Dashboards."""
    teile = _anlagenteile(hass)
    if not teile:
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

    return {
        "title": DASHBOARD_TITEL,
        "views": [_uebersicht(teile), *(_geraeteansicht(teil) for teil in teile)],
    }


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
