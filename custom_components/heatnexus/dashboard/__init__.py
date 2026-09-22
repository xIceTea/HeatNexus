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
from typing import Any

from homeassistant.components import frontend, websocket_api
from homeassistant.core import HomeAssistant, callback
import voluptuous as vol
import yaml

from ..const import DASHBOARD_TITEL, DASHBOARD_URL, DOMAIN
from ..texte import LOVELACE_FELDER, uebersetze_baum, woerterbuch
from .anlagen import anlagen_lesen, mehrfach_vergebene_namen
from .ansichten import anlagenbild, auswertung, geraeteansicht, uebersicht, wartung

_LOGGER = logging.getLogger(__name__)


def dashboard_konfiguration(hass: HomeAssistant, als_karte: bool | None = None) -> dict[str, Any]:
    """Die vollständige Lovelace-Konfiguration des Dashboards.

    Ohne Angabe entscheidet der Merker aus `auslieferung.karte_anmelden`: Ist
    das Kartenmodul angemeldet, steht das Schaubild als eigene Karte da –
    beweglich und im Editor zu öffnen. Sonst bleibt es die feste Zeichnung.
    """
    if als_karte is None:
        als_karte = bool(hass.data.get(f"{DOMAIN}_karte_js"))
    return uebersetze_baum(_konfiguration(hass, als_karte), woerterbuch(hass), LOVELACE_FELDER)


def _konfiguration(hass: HomeAssistant, als_karte: bool) -> dict[str, Any]:
    """Die Ansichten, noch in der Quellsprache."""
    anlagen = anlagen_lesen(hass)
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

    mehrdeutig = mehrfach_vergebene_namen(anlagen)
    views: list[dict[str, Any]] = [uebersicht(anlagen)]
    for ansicht in (anlagenbild(anlagen, als_karte), wartung(anlagen), auswertung(anlagen)):
        if ansicht:
            views.append(ansicht)
    views += [
        geraeteansicht(anlage, teil, mehrdeutig) for anlage in anlagen for teil in anlage["teile"]
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
