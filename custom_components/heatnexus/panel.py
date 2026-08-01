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
from pathlib import Path
import re
from typing import Any

from homeassistant.components import frontend, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback
import voluptuous as vol

from .const import (
    DOMAIN,
    PANEL_ELEMENT,
    PANEL_JS_PFAD,
    PANEL_TITEL,
    PANEL_URL,
)
from .dashboard import (
    WARTUNG_RESTLAUFZEIT,
    WARTUNG_WEITERE,
    _anlagen,
    _muster,
    _passt,
    rueckfrage,
)
from .schema import anlagenschema

_LOGGER = logging.getLogger(__name__)

_JS_DATEI = Path(__file__).parent / "frontend" / "heatnexus-panel.js"

# Der wichtigste Wert eines Anlagenteils, für die Liste links.
KENNWERT = (
    (r"kesseltemperatur ist", "Kesseltemperatur", "mdi:fire"),
    (r"puffer oben", "Puffer oben", "mdi:storage-tank"),
    (r"warmwassertemperatur", "Warmwasser", "mdi:water-boiler"),
    (r"raumtemperatur ist", "Raumtemperatur", "mdi:home-thermometer"),
    (r"vorlauftemperatur ist", "Vorlauf", "mdi:radiator"),
    (r"^temperatur ist$", "Temperatur", "mdi:thermometer"),
    (r"r(ü|ue)cklauf temperatur", "Rücklauf", "mdi:pipe"),
)

# Systemstatus rechts: Zeile für Zeile, in dieser Reihenfolge.
STATUS = (
    (r"betriebsphase", "Betriebszustand", "mdi:state-machine"),
    (r"au(ß|ss)entemperatur", "Außentemperatur", "mdi:thermometer"),
    (r"kesselleistung", "Kesselleistung", "mdi:fire"),
    (r"aktueller brennstoff", "Brennstoff", "mdi:sack"),
    (r"vorratsbeh", "Vorratsbehälter", "mdi:battery-70"),
    (r"laufzeit bis ascheentleerung", "Bis Ascheentleerung", "mdi:delete-clock-outline"),
)

# Warmwasser hat keine eigene Funktion: Die Datenpunkte hängen am Heizkreis.
# Die Wortgrenze ist nötig – ohne sie zählte auch die Abgas-Re*zirkulation* des
# Kessels als Warmwasserwert.
WARMWASSER = _muster(
    r"\bwarmwasser",
    r"\bww[- ]",
    r"\bzirkulation",
)

# Ob überhaupt Warmwasser bereitet wird, verraten diese beiden: eine gemessene
# Warmwassertemperatur (0/4) oder der ausdrücklich gemeldete Kreis (5/76).
#
# Die Parameter allein beweisen nichts: „WW-Überhöhung", „WW-Ladepumpe" und
# „WW-Ladung max. Ladevorrang" stehen auch an einem Heizkreis ohne
# Warmwasserspeicher in der Liste. Genau daran zeigte die Oberfläche im
# Heizhaus eine Warmwasserkarte, die es dort nie gab.
# Kuratiert heißt der Datenpunkt „Warmwasser Ist-Temperatur", aus der
# Menü-Erkennung „WW-Temperatur Aktueller Wert" – beide Schreibweisen zählen.
WARMWASSER_IST = _muster(
    r"\bww[- ]temperatur",
    r"\bwarmwasser[- ]?(ist|soll)?[- ]?temperatur",
)
WARMWASSER_KREIS = _muster(r"\bww-kreis\b")

VERLAUF = _muster(
    r"kesseltemperatur ist",
    r"au(ß|ss)entemperatur",
)

# Schnellzugriff: bedienbare Datenpunkte, die man wirklich anfasst.
# Ob vor dem Auslösen nachgefragt wird, entscheidet `dashboard.rueckfrage` –
# dieselbe Tabelle gilt für die Kacheln im Dashboard.
SCHNELLZUGRIFF = (
    (r"ww einmalladung", "Warmwasser laden", "mdi:water-boiler"),
    (r"serviceausbrand", "Serviceausbrand", "mdi:fire-off"),
    (r"reinigung best", "Reinigung bestätigen", "mdi:broom"),
    (r"betriebswahl", "Betriebswahl", "mdi:tune"),
    (r"gew(ä|ae)hlter brennstoff", "Brennstoff wählen", "mdi:sack"),
)

# Höchstzahl der Warmwasserzeilen; mehr sprengt die Karte.
WARMWASSER_MAX = 6

# ---------------------------------------------------------------------------
# Reiter „Steuerung": die Anlage bedienen statt nur ablesen
# ---------------------------------------------------------------------------
# Betriebswahl eines Heizkreises bzw. des Kessels.
BETRIEBSWAHL = _muster(r"\bbetriebswahl\b")
# Zeitprogramm eines Kreises.
ZEITPROGRAMM = _muster(r"programm")
# Die Einmalladung: der einzige Warmwasser-Eingriff, den man täglich anfasst.
EINMALLADUNG = _muster(r"einmalladung")
# Die Anlage kennt zur Einmalladung zwei Einstellungen: auslösen und die
# Temperatur, auf die dabei geladen wird.
EINMALLADUNG_TEMPERATUR = _muster(r"einmalladung temperatur", r"ww-ladefreigabe temperatur")
WARMWASSER_SOLL = _muster(r"\bww[- ]temperatur sollwert", r"\bwarmwasser soll")

# Die Außentemperatur gehört an der Anlage in die Kopfzeile und nicht in eine
# Kachel – sie gilt für die ganze Anlage, nicht für einen Anlagenteil.
AUSSENTEMPERATUR = _muster(r"au(ß|ss)entemperatur")

# Bedienbares am Kessel, in dieser Reihenfolge.
KESSEL_BEDIENUNG = (
    (r"gew(ä|ae)hlter brennstoff", "Brennstoff", "mdi:sack"),
    (r"serviceausbrand", "Serviceausbrand", "mdi:fire-off"),
    (r"reinigung best", "Reinigung bestätigen", "mdi:broom"),
    (r"lagerraum bef(ü|ue)llen", "Lagerraum befüllen", "mdi:warehouse"),
)

# ---------------------------------------------------------------------------
# Reiter „Wartung"
# ---------------------------------------------------------------------------
WARTUNG_BRENNSTOFF = _muster(r"vorratsbeh", r"aktueller brennstoff", r"brennstoff")


def _erster(entitaeten: list[dict[str, Any]], muster: str) -> dict[str, Any] | None:
    """Erste passende Entität; eine mit Wert hat Vorrang.

    Ein vorhandener Wert darf keine Bedingung sein: Beim ersten Aufbau ist die
    Anlage noch nicht fertig eingelesen. Was jetzt noch leer ist, bekommt
    trotzdem seine Zeile und füllt sich mit dem nächsten Abruf.
    """
    regex = re.compile(muster, re.IGNORECASE)
    treffer = [e for e in entitaeten if regex.search(e["name"])]
    if not treffer:
        return None
    return next((e for e in treffer if e.get("hat_wert")), treffer[0])


def _zeilen(
    entitaeten: list[dict[str, Any]], vorlage: tuple[tuple[str, str, str], ...]
) -> list[dict[str, str]]:
    """Aus einer Mustervorlage die vorhandenen Entitäten als Zeilen."""
    zeilen = []
    for muster, beschriftung, symbol in vorlage:
        if (treffer := _erster(entitaeten, muster)) is not None:
            zeilen.append(
                {
                    "entity": treffer["entity_id"],
                    "titel": beschriftung,
                    "symbol": symbol,
                }
            )
    return zeilen


def _bereitet_warmwasser(entitaeten: list[dict[str, Any]]) -> bool:
    """Prüfen, ob diese Anlage überhaupt Warmwasser bereitet.

    Zwei Belege lässt die Anlage zu: eine gemessene Warmwassertemperatur oder
    einen gemeldeten Warmwasserkreis ungleich null. Solange der Vollabzug noch
    läuft, hat der Istwert womöglich noch keinen Wert – vorhanden sein reicht
    deshalb, ein Wert ist nicht nötig.
    """
    for eintrag in entitaeten:
        if _passt(eintrag["name"], WARMWASSER_IST):
            return True
        if _passt(eintrag["name"], WARMWASSER_KREIS) and (eintrag.get("wert") or 0) != 0:
            return True
    return False


def _warmwasser(entitaeten: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Zeilen der Warmwasserkarte – leer, wo es kein Warmwasser gibt."""
    if not _bereitet_warmwasser(entitaeten):
        return []
    return [
        {"entity": e["entity_id"], "titel": e["name"]}
        for e in entitaeten
        if e["kategorie"] is None and e["bereich"] != "climate" and _passt(e["name"], WARMWASSER)
    ][:WARMWASSER_MAX]


def _kennung(entitaeten: list[dict[str, Any]], muster: tuple, bereiche: tuple = ()) -> str | None:
    """Entity-ID der ersten passenden Entität, optional auf Plattformen begrenzt."""
    for eintrag in entitaeten:
        if bereiche and eintrag["bereich"] not in bereiche:
            continue
        if _passt(eintrag["name"], muster):
            return eintrag["entity_id"]
    return None


def _steuerung(anlage: dict[str, Any]) -> dict[str, Any]:
    """Der Reiter „Steuerung": alles, was man an der Anlage wirklich verstellt.

    Vorbild ist die Bedienung der Anlage selbst – Heizkreis, Warmwasser,
    Kessel. Was nur abgelesen wird, gehört in die Übersicht.
    """
    alle = [e for teil in anlage["teile"] for e in teil["entitaeten"]]

    heizkreise = []
    for teil in anlage["teile"]:
        thermostat = next((e for e in teil["entitaeten"] if e["bereich"] == "climate"), None)
        if thermostat is None:
            continue
        heizkreise.append(
            {
                "entity": thermostat["entity_id"],
                "titel": teil["name"],
                "betriebswahl": _kennung(teil["entitaeten"], BETRIEBSWAHL, ("select",)),
                "programm": _kennung(teil["entitaeten"], ZEITPROGRAMM, ("sensor",)),
                "vorlauf": (
                    v["entity_id"]
                    if (v := _erster(teil["entitaeten"], r"vorlauftemperatur ist"))
                    else None
                ),
            }
        )

    warmwasser = None
    if _bereitet_warmwasser(alle):
        ist = _erster(alle, r"\bww[- ]temperatur aktueller|\bwarmwasser ist")
        warmwasser = {
            "ist": ist["entity_id"] if ist else None,
            "soll": _kennung(alle, WARMWASSER_SOLL),
            "laden": _kennung(alle, EINMALLADUNG, ("switch", "button")),
            # Die Temperatur der Einmalladung ist an der Anlage Teil derselben
            # Bedienung; ohne sie lädt man auf einen Wert, den man nicht sieht.
            "laden_temperatur": _kennung(alle, EINMALLADUNG_TEMPERATUR, ("number",)),
            "programm": _kennung(alle, _muster(r"ww[- ].*programm"), ("sensor",)),
        }

    kessel = []
    for teil in anlage["teile"]:
        for muster, beschriftung, symbol in KESSEL_BEDIENUNG:
            treffer = next(
                (
                    e
                    for e in teil["entitaeten"]
                    if e["bereich"] in ("switch", "button", "select")
                    and re.search(muster, e["name"], re.IGNORECASE)
                ),
                None,
            )
            if treffer is not None:
                kessel.append(
                    {
                        "entity": treffer["entity_id"],
                        "titel": beschriftung,
                        "symbol": symbol,
                        "frage": rueckfrage(treffer["name"]),
                    }
                )

    return {"heizkreise": heizkreise, "warmwasser": warmwasser, "kessel": kessel}


def _wartung(anlage: dict[str, Any]) -> dict[str, Any]:
    """Der Reiter „Wartung": Restlaufzeiten, Brennstoff, Zählerstände."""
    alle = [e for teil in anlage["teile"] for e in teil["entitaeten"]]

    def zeilen(bedingung) -> list[dict[str, str]]:
        return [
            {"entity": e["entity_id"], "titel": e["name"]}
            for e in alle
            if e["kategorie"] is None and bedingung(e)
        ]

    return {
        "restlaufzeiten": zeilen(lambda e: _passt(e["name"], WARTUNG_RESTLAUFZEIT)),
        "brennstoff": zeilen(
            lambda e: (
                _passt(e["name"], WARTUNG_BRENNSTOFF)
                and not _passt(e["name"], WARTUNG_RESTLAUFZEIT)
            )
        ),
        # Zählerstände erkennt man an der Statistikklasse, nicht am Namen.
        "zaehler": zeilen(lambda e: e.get("state_class") == "total_increasing"),
        "weitere": zeilen(
            lambda e: (
                _passt(e["name"], WARTUNG_WEITERE)
                and not _passt(e["name"], WARTUNG_RESTLAUFZEIT)
                and not _passt(e["name"], WARTUNG_BRENNSTOFF)
                and e.get("state_class") != "total_increasing"
            )
        ),
    }


def _anlage_daten(anlage: dict[str, Any]) -> dict[str, Any]:
    """Alles, was die Oberfläche für eine Anlage braucht."""
    alle = [e for teil in anlage["teile"] for e in teil["entitaeten"]]

    kennwerte = []
    for teil in anlage["teile"]:
        for muster, beschriftung, symbol in KENNWERT:
            if (treffer := _erster(teil["entitaeten"], muster)) is not None:
                kennwerte.append(
                    {
                        "entity": treffer["entity_id"],
                        "titel": teil["name"],
                        "untertitel": beschriftung,
                        "symbol": symbol,
                    }
                )
                break

    heizkreise = []
    for teil in anlage["teile"]:
        thermostat = next(
            (e for e in teil["entitaeten"] if e["bereich"] == "climate"),
            None,
        )
        if thermostat is None:
            continue
        heizkreise.append(
            {
                "entity": thermostat["entity_id"],
                "titel": teil["name"],
                "vorlauf": (
                    v["entity_id"]
                    if (v := _erster(teil["entitaeten"], r"vorlauftemperatur ist"))
                    else None
                ),
            }
        )

    warmwasser = _warmwasser(alle)

    stoerungen = [
        {"entity": e["entity_id"], "titel": e["name"]}
        for e in alle
        if e["kategorie"] == "diagnostic" and "klartext" in e["name"].lower()
    ]

    schnellzugriff = []
    for teil in anlage["teile"]:
        for muster, beschriftung, symbol in SCHNELLZUGRIFF:
            treffer = next(
                (
                    e
                    for e in teil["entitaeten"]
                    if e["bereich"] in ("switch", "button", "select")
                    and re.search(muster, e["name"], re.IGNORECASE)
                ),
                None,
            )
            if treffer is not None:
                schnellzugriff.append(
                    {
                        "entity": treffer["entity_id"],
                        "titel": beschriftung,
                        "symbol": symbol,
                        "frage": rueckfrage(treffer["name"]),
                    }
                )

    bild = anlagenschema(anlage["teile"])
    aussen = _kennung(alle, AUSSENTEMPERATUR)
    return {
        "name": anlage["name"],
        # Die Außentemperatur gilt für die ganze Anlage und steht deshalb oben,
        # nicht in der Liste der Anlagenteile.
        "aussentemperatur": aussen,
        "steuerung": _steuerung(anlage),
        "wartung": _wartung(anlage),
        "kennwerte": kennwerte,
        "status": _zeilen(alle, STATUS),
        "heizkreise": heizkreise,
        "warmwasser": warmwasser,
        "stoerungen": stoerungen,
        "schnellzugriff": schnellzugriff[:6],
        "verlauf": [e["entity_id"] for e in alle if _passt(e["name"], VERLAUF)][:2],
        "schema": bild["image"] if bild else None,
        "schema_werte": (
            [
                {
                    "entity": el["entity"],
                    "left": el["style"]["left"],
                    "top": el["style"]["top"],
                }
                for el in bild["elements"]
            ]
            if bild
            else []
        ),
    }


def panel_daten(hass: HomeAssistant) -> dict[str, Any]:
    """Die vollständige Struktur für die Oberfläche."""
    return {"anlagen": [_anlage_daten(anlage) for anlage in _anlagen(hass)]}


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/panel_daten"})
@callback
def _ws_panel_daten(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Die Aufteilung frisch berechnen, so wie sie gerade gilt."""
    connection.send_result(msg["id"], panel_daten(hass))


async def async_setup_panel(hass: HomeAssistant) -> None:
    """Die Oberfläche in der Seitenleiste anmelden.

    Fehler bleiben folgenlos – das Dashboard und die Entitäten funktionieren
    auch ohne sie.
    """
    try:
        await _async_setup_panel(hass)
    except Exception as err:
        _LOGGER.warning("Oberfläche konnte nicht angemeldet werden: %s", err)


async def _async_setup_panel(hass: HomeAssistant) -> None:
    """Eigentliche Anmeldung."""
    if not hass.data.get(f"{DOMAIN}_panel_datei"):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(PANEL_JS_PFAD, str(_JS_DATEI), cache_headers=False)]
        )
        websocket_api.async_register_command(hass, _ws_panel_daten)
        hass.data[f"{DOMAIN}_panel_datei"] = True

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
                "name": PANEL_ELEMENT,
                "module_url": PANEL_JS_PFAD,
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
