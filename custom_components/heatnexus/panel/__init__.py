"""Eigene Oberfläche für die Heizung.

Meldet einen eigenen Eintrag in der Seitenleiste an, hinter dem eine
Anlagenübersicht steht: Kennwerte, Schaubild, Heizkreise, Warmwasser,
Störungen, Verlauf und Schnellzugriff – in einer Anordnung, die sich mit
Lovelace-Karten nicht bauen lässt.

**Die Aufteilung entsteht hier, nicht im Browser.** Python sucht die
Entitäten zusammen und legt sie als fertige Struktur ab; die Datei im Browser
stellt sie nur dar und holt sich die aktuellen Werte aus ``hass.states``.
Damit bleibt die gesamte Gerätekenntnis an einer Stelle, und im Browser liegt
nichts, was bei einer neuen Anlage angepasst werden müsste.

Die Struktur wird **beim Öffnen** über ``heatnexus/panel_daten`` geholt, nicht
nur beim Einrichten mitgegeben. Beim Einrichten ist die Anlage erst zur Hälfte
eingelesen: Der Vollabzug läuft im Hintergrund weiter, und die Werte der
zuerst angelegten Entitäten stehen teils noch aus. Eine damals berechnete
Aufteilung bliebe für immer halb leer – genau daran fehlten Kennwerte,
Systemstatus, Warmwasser, Schaubild und Verlauf. Die Konfiguration des Panels
enthält weiterhin einen Stand, damit die Ansicht sofort etwas zeigt.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from homeassistant.components import frontend, websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
import voluptuous as vol

from ..anordnung import async_register_anordnung
from ..auslieferung import async_dateien_ausliefern
from ..const import (
    COMFORT_TEMP_STANDARD,
    CONF_AUSSENTEMPERATUR,
    CONF_COMFORT_DAUER,
    CONF_COMFORT_TEMP,
    CONF_ECO_DAUER,
    CONF_ECO_TEMP,
    CONF_HILFE,
    CONF_MARKEN,
    CONF_MARKEN_STATUS,
    DOMAIN,
    ECO_TEMP_STANDARD,
    PANEL_TITEL,
    PANEL_URL,
    UEBERSTEUERUNG_DAUER_STANDARD,
    panel_element,
    panel_js_pfad,
)
from ..dashboard.anlagen import anlagen_lesen
from ..entity import steuerung_kennung
from ..registrierung import geraet_suchen
from ..texte import uebersetze_baum, woerterbuch
from . import marken as markenmodul
from .daten import _anlage_daten, _erster
from .hilfe import hilfe

# Was von außen benutzt wird. `_anlage_daten` und `_erster` stehen mit in der
# Liste, weil die Tests die Aufteilung direkt prüfen – sie ist der Vertrag
# zwischen Integration und Browser und gehört geprüft, nicht bloß benutzt.
__all__ = [
    "_anlage_daten",
    "_erster",
    "async_remove_panel",
    "async_setup_panel",
    "hilfe",
    "panel_daten",
]

_LOGGER = logging.getLogger(__name__)


def _uebersteuerung(hass: HomeAssistant) -> dict[str, dict[str, float]]:
    """Die eingestellten Werte für Eco und Comfort.

    Sie gelten für alle Heizkreise: Die Anlage kennt je Kreis nur *einen*
    Übersteuerungswert, zwei getrennte Vorgaben je Kreis hätten dort nichts,
    worin sie stehen könnten.
    """
    optionen: dict[str, Any] = {}
    for eigene in _optionen(hass):
        optionen = {**eigene, **optionen}
    return {
        "eco": {
            "temperatur": float(optionen.get(CONF_ECO_TEMP, ECO_TEMP_STANDARD)),
            "dauer": float(optionen.get(CONF_ECO_DAUER, UEBERSTEUERUNG_DAUER_STANDARD)),
        },
        "comfort": {
            "temperatur": float(optionen.get(CONF_COMFORT_TEMP, COMFORT_TEMP_STANDARD)),
            "dauer": float(optionen.get(CONF_COMFORT_DAUER, UEBERSTEUERUNG_DAUER_STANDARD)),
        },
    }


def _optionen(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Die Optionen jedes Eintrags dieser Integration, in ihrer Reihenfolge."""
    return [dict(eintrag.options or {}) for eintrag in hass.config_entries.async_entries(DOMAIN)]


def _gewaehlte_aussentemperatur(hass: HomeAssistant) -> str | None:
    """In den Optionen festgelegte Außentemperatur, falls vorhanden."""
    for optionen in _optionen(hass):
        if gewaehlt := optionen.get(CONF_AUSSENTEMPERATUR):
            return str(gewaehlt)
    return None


def _hilfe_gewuenscht(hass: HomeAssistant) -> bool:
    """Ob die Erklärungen angezeigt werden sollen (Standard: ja)."""
    for optionen in _optionen(hass):
        if CONF_HILFE in optionen:
            return bool(optionen[CONF_HILFE])
    return True


def _marken_je_anlage(
    hass: HomeAssistant, benutzer: Any = None
) -> dict[str, tuple[list[dict], list[dict]]]:
    """Karten und Statuszeilen aus den Labels, je Anlage.

    Die Auswahl steht in den Optionen der Anlage; ein Label, das dem
    Systemstatus zugeordnet ist, wird keine eigene Karte.
    """
    geraete = dr.async_get(hass)
    je_anlage: dict[str, tuple[list[dict], list[dict]]] = {}
    for eintrag in hass.config_entries.async_entries(DOMAIN):
        daten = getattr(eintrag, "runtime_data", None) or {}
        for host, coordinator in (daten.get("coordinators") or {}).items():
            optionen = (eintrag.options or {}).get(host) or {}
            gewaehlt = optionen.get(CONF_MARKEN) or []
            if not gewaehlt:
                continue
            geraet = geraet_suchen(geraete, steuerung_kennung(coordinator), eintrag.entry_id)
            if geraet is None:
                continue
            im_status = set(optionen.get(CONF_MARKEN_STATUS) or [])
            je_anlage[geraet.id] = (
                markenmodul.karten(hass, [k for k in gewaehlt if k not in im_status], benutzer),
                markenmodul.zeilen(hass, [k for k in gewaehlt if k in im_status], benutzer),
            )
    return je_anlage


def panel_daten(hass: HomeAssistant, benutzer: Any = None) -> dict[str, Any]:
    """Die vollständige Struktur für die Oberfläche.

    `benutzer` ist der Anfragende; seine Rechte entscheiden über die Zeilen
    der Markenkarten. Ohne ihn gilt keine Einschränkung.
    """
    aussen = _gewaehlte_aussentemperatur(hass)
    marken = _marken_je_anlage(hass, benutzer)
    daten = {
        "anlagen": [
            _anlage_daten(anlage, aussen, *marken.get(anlage.get("id"), ((), ())))
            for anlage in anlagen_lesen(hass, benutzer)
        ],
        # Eco und Comfort gelten für alle Anlagen gemeinsam.
        "uebersteuerung": _uebersteuerung(hass),
        # Die Außentemperatur der Ansicht „Alle". Dort steht keine einzelne
        # Anlage im Vordergrund, also gilt die gewählte Entität – und nur dort.
        "aussentemperatur": aussen,
    }
    if not _hilfe_gewuenscht(hass):
        # Abgewählt: Die Texte gar nicht erst mitschicken.
        for anlage in daten["anlagen"]:
            anlage["hilfe"] = {}
            for bereich in ("schnellzugriff", "zeitprogramme"):
                for eintrag in anlage.get(bereich) or []:
                    eintrag.pop("hilfe", None)
            steuerung = anlage.get("steuerung") or {}
            for eintrag in steuerung.get("kessel") or []:
                eintrag.pop("hilfe", None)
            for kreis in steuerung.get("heizkreise") or []:
                kreis.pop("betriebswahl_hilfe", None)
            if steuerung.get("lagerraum"):
                steuerung["lagerraum"].pop("hilfe", None)
            if (wasser := steuerung.get("warmwasser")) and wasser.get("taste"):
                wasser["taste"].pop("hilfe", None)
    # Übersetzt wird hier, damit die Daten und die Anzeige übereinstimmen –
    # die Hilfesuche durchsucht die Titel der Nutzlast. Was der Browser
    # selbst beschriftet, steht nicht im Baum und braucht das Wörterbuch.
    buch = woerterbuch(hass)
    daten = uebersetze_baum(daten, buch)
    daten["texte"] = buch.fuer_frontend
    return daten


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/panel_daten"})
@callback
def _ws_panel_daten(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Die Aufteilung frisch berechnen, so wie sie gerade gilt."""
    connection.send_result(msg["id"], panel_daten(hass, connection.user))


async def async_setup_panel(hass: HomeAssistant, version: str = "") -> None:
    """Die Oberfläche in der Seitenleiste anmelden.

    Fehler bleiben folgenlos – das Dashboard und die Entitäten funktionieren
    auch ohne sie.
    """
    try:
        await _async_setup_panel(hass, version)
    except Exception as err:
        _LOGGER.warning("Oberfläche konnte nicht angemeldet werden: %s", err)


async def _async_setup_panel(hass: HomeAssistant, version: str = "") -> None:
    """Eigentliche Anmeldung.

    Die Fassungsnummer steckt im *Pfad* der Oberflächendatei, nicht als
    Fragezeichen-Anhang dahinter. Home Assistant legt seine Oberfläche über
    einen Service-Worker im Browser ab, und der vergleicht Adressen ohne
    Suchteil – ein Anhang wie ``?v=1.1.0`` wird dabei schlicht übergangen und
    die alte Datei weiter ausgeliefert. Ein neuer Pfad ist für den
    Zwischenspeicher dagegen eine neue Datei; die Oberfläche erscheint nach
    einer Aktualisierung von selbst, ohne dass jemand neu laden muss.
    """
    # **Der Ordner, nicht die Datei.** Die Oberfläche besteht aus mehreren
    # ES-Modulen, die einander relativ laden (`./stil.js`); ein einzeln
    # angemeldeter Pfad ließe die Nachbardateien ins Leere laufen.
    await async_dateien_ausliefern(hass, version)
    if not hass.data.get(f"{DOMAIN}_panel_datei"):
        websocket_api.async_register_command(hass, _ws_panel_daten)
        hass.data[f"{DOMAIN}_panel_datei"] = True
    # Die selbst gewählte Anordnung hängt am Panel, nicht an einer Anlage.
    async_register_anordnung(hass)

    daten = panel_daten(hass)
    if not daten["anlagen"]:
        return

    # update=True ersetzt eine bestehende Anmeldung – nötig, weil sich mit dem
    # Umfang auch die Aufteilung ändert.
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=PANEL_TITEL,
        sidebar_icon="mdi:radiator",
        frontend_url_path=PANEL_URL,
        config={
            "_panel_custom": {
                "name": panel_element(version),
                "module_url": panel_js_pfad(version),
                "embed_iframe": False,
                "trust_external": False,
            },
            "daten": daten,
        },
        require_admin=False,
        update=True,
    )
    hass.data[f"{DOMAIN}_panel"] = True
    _LOGGER.info("Oberfläche %s in der Seitenleiste angemeldet", PANEL_TITEL)


async def async_remove_panel(hass: HomeAssistant) -> None:
    """Die Oberfläche wieder aus der Seitenleiste nehmen."""
    if not hass.data.pop(f"{DOMAIN}_panel", None):
        return
    with contextlib.suppress(Exception):
        frontend.async_remove_panel(hass, PANEL_URL)
    _LOGGER.info("Oberfläche %s entfernt", PANEL_TITEL)
