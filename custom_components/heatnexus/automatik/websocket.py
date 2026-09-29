"""WebSocket-Befehle des Reiters „Automatik".

Lesen darf, wer die Klima-Entität des Heizkreises lesen darf. Ändern dürfen
nur Administratoren; jedes Schema ist nach oben begrenzt.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .. import texte
from ..const import DOMAIN, SUBEINTRAG_QUELLE
from ..rechte import darf_lesen
from ..registrierung import geraet_suchen
from . import eingaben, kennzahlen, korrektur, nachladen, profile, regel, tagesansicht
from .konfig import (
    EIGENE_FELDER,
    LISTEN_MAX,
    MODI,
    RAUM_ARTEN,
    RAUM_ZIEL,
    pv_ist_passt,
    pv_passt,
    raumfuehler_passt,
)
from .laufzeit import Laufzeit
from .verwaltung import DOMAENE_JE_ART, Verwaltung, unique_id, verwaltung_holen

PROTOKOLL_ANZEIGE = 20
PV_PLATTFORMEN = frozenset({"forecast_solar", "solcast_solar", "open_meteo_solar_forecast"})
FENSTER_KLASSEN = frozenset({"window", "door", "opening"})
KENNUNG = vol.All(str, vol.Length(min=1, max=120))
ENTITAET = vol.All(str, vol.Length(max=255))


def _liste(grenze: int) -> vol.All:
    return vol.All([ENTITAET], vol.Length(max=grenze))


def _korrektur(laufzeit: Laufzeit, jetzt: datetime) -> dict[str, Any]:
    fenster, heute = laufzeit.werte.lernfenster, jetzt.date()
    return {
        "an": laufzeit.werte.anpassen,
        "fenster": fenster,
        "noetig": korrektur.noetige_tage(fenster),
        "temperatur": {
            "versatz": laufzeit.temperatur.tagesversatz(fenster, heute),
            "versatz_bisher": laufzeit.temperatur.tagesversatz(fenster, heute, vorlaeufig=True),
            "tage": laufzeit.temperatur.lerntage(fenster, heute),
        },
        "sonne": {
            "aktiv": bool(laufzeit.konfig.get("pv_ist")),
            "faktor": laufzeit.pv.faktor(fenster, heute),
            "faktor_bisher": laufzeit.pv.faktor(fenster, heute, vorlaeufig=True),
            "tage": laufzeit.pv.lerntage(fenster, heute),
        },
    }


def _entitaeten(hass: HomeAssistant, device_id: str) -> dict[str, str | None]:
    register = er.async_get(hass)
    return {
        art: register.async_get_entity_id(domaene, DOMAIN, unique_id(device_id, art))
        for art, domaene in DOMAENE_JE_ART.items()
    }


def _eintrag(
    hass: HomeAssistant, verwaltung: Verwaltung, entry_id: str, coordinator: Any, b: dict
) -> dict:
    device_id = b["device_id"]
    geraet = geraet_suchen(dr.async_get(hass), device_id, entry_id)
    ergebnis: dict[str, Any] = {
        "heizkreis": device_id,
        "name": b.get("device_name") or device_id,
        "anlage": getattr(coordinator, "label", "") or "",
        # Dieselbe Kennung wie die Anlage im Panel: das Gerät der Steuerung.
        "anlage_id": geraet.via_device_id if geraet else None,
        "eingerichtet": False,
    }
    laufzeit = verwaltung.laufzeiten.get(device_id)
    if laufzeit is None:
        return ergebnis
    jetzt = dt_util.now()
    werte = laufzeit.werte
    lage = laufzeit.lage
    g = laufzeit.gedaechtnis
    soll = g.absenkung_basis or g.saison_soll or (lage.soll if lage else None)
    thermostate = eingaben.hat_thermostat(laufzeit.konfig["raeume"])
    abweichung = (
        regel.abweichung(lage, soll)
        if lage is not None and lage.raum is not None and soll is not None
        else None
    )
    ergebnis.update(
        eingerichtet=True,
        konfig=laufzeit.konfig,
        werte=asdict(werte),
        # Die Vorgabe, gegen die „Erweitert“ eigene Werte zeigt: Profil samt Ausrichtung.
        vorgabe=asdict(profile.vorgabe(laufzeit.konfig["profil"], laufzeit.konfig["ausrichtung"])),
        zustand=laufzeit.zustand.value,
        begruendung=laufzeit.begruendung,
        kennwerte={
            "sonnenquote": lage.sonnenquote if lage else None,
            "raum": lage.raum if lage else None,
            "soll": soll,
            "abweichung": abweichung,
            "eigene_ziele": thermostate or laufzeit.konfig.get("raum_ziel") is not None,
            # Gemeinsamer Bezug der Raumwerte im Stundenraster; Thermostate haben je Raum eigene.
            "raum_bezug": None if thermostate else laufzeit.konfig.get("raum_ziel") or soll,
            "at": lage.at if lage else None,
            "at_gedaempft": lage.at_gedaempft if lage else None,
            "raeume": tagesansicht.raumwerte(laufzeit),
            "raum_art": laufzeit.konfig["raum_art"],
            "heizgrenze": regel.grenze(lage, werte) if lage else None,
            "grenze_steuerung": lage.grenze_steuerung if lage else None,
            "grenze_absenk": laufzeit.wert("/3/2/0"),
            "versatz": werte.grenze_versatz,
            "hysterese": werte.hysterese,
            "sonne_schwelle": werte.sonnenquote,
            "stark_quote": regel.STARK_QUOTE if werte.stark else None,
            "stark_k": werte.stark_k if werte.stark else None,
            "rueckkehr_k": werte.rueckkehr_k,
            "sonne_raum_k": regel.SONNE_RAUM_K,
            "eingriffe": laufzeit.steller.stand.eingriffe,
            "budget": werte.budget,
            "naechste_pruefung": (
                n.isoformat() if (n := kennzahlen.naechste_entscheidung(laufzeit)) else None
            ),
            "modus_seit": (s.isoformat() if (s := kennzahlen.modus_seit(laufzeit)) else None),
            "vorrang": (
                {"laeuft": lage.vorrang_laeuft, "minuten": round(lage.vorrang_minuten or 0)}
                if lage is not None and laufzeit.konfig["vorrang"]
                else None
            ),
        },
        tag=tagesansicht.heute(laufzeit, jetzt),
        vorschau=tagesansicht.vorschau(laufzeit, jetzt),
        korrektur=_korrektur(laufzeit, jetzt),
        protokoll=list(laufzeit.steller.stand.protokoll[:PROTOKOLL_ANZEIGE]),
        beobachtet_seit=laufzeit.beobachtet_seit.isoformat(),
        pausiert_bis=laufzeit.pausiert_bis.isoformat() if laufzeit.pausiert_bis else None,
        entitaeten=_entitaeten(hass, device_id),
    )
    return ergebnis


def _geladene(hass: HomeAssistant) -> list[ConfigEntry]:
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED and getattr(entry, "runtime_data", None)
    ]


def _eintrag_zum_heizkreis(hass: HomeAssistant, device_id: str) -> ConfigEntry | None:
    for entry in _geladene(hass):
        if any(b["device_id"] == device_id for _, b in Verwaltung.heizkreise(entry)):
            return entry
    return None


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/automatik"})
@websocket_api.async_response
async def _ws_lesen(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Alle Heizkreise mit ihrer Automatik, soweit der Benutzer sie sehen darf."""
    verwaltung = verwaltung_holen(hass)
    await verwaltung.laden()
    register = er.async_get(hass)
    woerterbuch = texte.woerterbuch(hass)
    heizkreise = []
    for entry in _geladene(hass):
        for coordinator, beschreibung in Verwaltung.heizkreise(entry):
            klima = register.async_get_entity_id("climate", DOMAIN, beschreibung.get("id", ""))
            # Ohne Klima-Entität gibt es nichts zu prüfen und nichts zu bedienen.
            if not klima or not darf_lesen(connection.user, klima):
                continue
            heizkreise.append(
                _uebersetzt(
                    _eintrag(hass, verwaltung, entry.entry_id, coordinator, beschreibung),
                    woerterbuch,
                )
            )
    connection.send_result(
        msg["id"],
        {
            "heizkreise": heizkreise,
            "darf_aendern": bool(connection.user and connection.user.is_admin),
            "profile": {name: asdict(werte) for name, werte in profile.VORGABEN.items()},
            "grenzen": profile.GRENZEN,
        },
    )


def _uebersetzt(eintrag: dict[str, Any], woerterbuch: texte.Woerterbuch) -> dict[str, Any]:
    """Begründung, Vorschau und Protokoll in der Sprache der Oberfläche; gespeichert bleibt Deutsch."""
    if not woerterbuch:
        return eintrag

    def feld(daten: dict[str, Any], name: str) -> dict[str, Any]:
        # Nur vorhandenen Text ersetzen; die Form der Nutzlast hängt nicht an der Sprache.
        text = daten.get(name)
        return {**daten, name: woerterbuch.satz(text)} if isinstance(text, str) and text else daten

    neu = feld(eintrag, "begruendung")
    if "vorschau" in eintrag:
        neu["vorschau"] = [feld(tag, "begruendung") for tag in eintrag["vorschau"]]
    if "protokoll" in eintrag:
        neu["protokoll"] = [feld(e, "text") for e in eintrag["protokoll"]]
    return neu


def _bereich(hass: HomeAssistant, eintrag: er.RegistryEntry | None) -> str:
    if eintrag is None:
        return ""
    area_id = eintrag.area_id
    if area_id is None and eintrag.device_id:
        geraet = dr.async_get(hass).async_get(eintrag.device_id)
        area_id = geraet.area_id if geraet else None
    bereich = ar.async_get(hass).async_get_area(area_id) if area_id else None
    return bereich.name if bereich else ""


def _anzeigewert(zustand: Any, art: str) -> str:
    if art != "thermostat":
        einheit = zustand.attributes.get("unit_of_measurement") or ""
        return f"{zustand.state} {einheit}".strip()
    ist = zustand.attributes.get("current_temperature")
    ziel = zustand.attributes.get("temperature")
    return f"{ist} °C → {ziel} °C" if ziel is not None else f"{ist} °C"


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/automatik/kandidaten"})
@websocket_api.async_response
async def _ws_kandidaten(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Auswahllisten für den Einrichtungsdialog."""
    register = er.async_get(hass)
    listen: dict[str, list[dict[str, str]]] = {
        "temperatur": [],
        "wetter": [],
        "pv": [],
        "pv_ist": [],
        "personen": [],
        "fenster": [],
        "vorrang": [],
    }
    for zustand in hass.states.async_all():
        entity_id = zustand.entity_id
        if not darf_lesen(connection.user, entity_id):
            continue
        domaene = entity_id.split(".", 1)[0]
        klasse = zustand.attributes.get("device_class")
        eintrag = register.async_get(entity_id)
        if eintrag is not None and eintrag.entity_category is not None:
            continue
        art = ""
        if domaene == "sensor" and klasse == "temperature" and raumfuehler_passt(entity_id):
            ziel = "temperatur"
        elif (
            domaene == "climate"
            and "current_temperature" in zustand.attributes
            and not (eintrag and eintrag.platform == DOMAIN)
        ):
            ziel, art = "temperatur", "thermostat"
        elif domaene == "weather":
            ziel = "wetter"
        elif (
            domaene == "sensor"
            and klasse == "energy"
            and eintrag
            and eintrag.platform in PV_PLATTFORMEN
            and pv_passt(entity_id)
        ):
            ziel = "pv"
        elif (
            domaene == "sensor"
            and klasse == "energy"
            and not (eintrag and eintrag.platform in PV_PLATTFORMEN)
            and pv_ist_passt(entity_id)
        ):
            ziel = "pv_ist"
        elif domaene == "person":
            ziel = "personen"
        elif domaene == "binary_sensor" and klasse in FENSTER_KLASSEN:
            ziel = "fenster"
        elif (
            domaene == "binary_sensor"
            and eintrag is not None
            and eintrag.platform == DOMAIN
            and f"-{SUBEINTRAG_QUELLE}-" in eintrag.unique_id
        ):
            ziel = "vorrang"
        else:
            continue
        listen[ziel].append(
            {
                "entity_id": entity_id,
                "name": str(zustand.attributes.get("friendly_name") or entity_id),
                "bereich": _bereich(hass, eintrag),
                "wert": _anzeigewert(zustand, art),
                "seit": (zustand.last_updated if art else zustand.last_changed).isoformat(),
                **({"art": art} if art else {}),
            }
        )
    # Ein ausgefallener Fühler zeigt seit Tagen denselben Wert; der Verlauf verrät es.
    kalt = await nachladen.eingefrorene_fuehler(
        hass, [e["entity_id"] for e in listen["temperatur"]]
    )
    for eintrag in listen["temperatur"]:
        if (seit := kalt.get(eintrag["entity_id"])) is not None:
            eintrag["seit"] = seit.isoformat()
    for liste in listen.values():
        liste.sort(key=lambda e: (e["bereich"] or "~", e["name"]))
    connection.send_result(msg["id"], listen)


EINSTELLUNGEN = {
    vol.Optional("heizflaechen"): vol.In(tuple(profile.HEIZFLAECHEN)),
    vol.Optional("profil"): vol.In(profile.PROFILE),
    vol.Optional("ausrichtung"): vol.In(profile.AUSRICHTUNGEN),
    vol.Optional("raeume"): _liste(LISTEN_MAX["raeume"]),
    vol.Optional("raum_art"): vol.In(RAUM_ARTEN),
    vol.Optional("raum_ziel"): vol.Any(
        None, vol.All(vol.Coerce(float), vol.Range(min=RAUM_ZIEL[0], max=RAUM_ZIEL[1]))
    ),
    vol.Optional("wetter"): ENTITAET,
    vol.Optional("pv"): vol.Any(None, ENTITAET),
    vol.Optional("pv_ist"): vol.Any(None, ENTITAET),
    vol.Optional("aussen"): vol.Any(None, ENTITAET),
    vol.Optional("personen"): _liste(LISTEN_MAX["personen"]),
    vol.Optional("fenster"): _liste(LISTEN_MAX["fenster"]),
    vol.Optional("fenster_erkennung"): bool,
    vol.Optional("vorrang"): _liste(LISTEN_MAX["vorrang"]),
}


def _ablehnen(hass: HomeAssistant, connection, msg: dict[str, Any], text: str) -> None:
    connection.send_error(msg["id"], "ungueltig", texte.woerterbuch(hass).satz(text))


async def _ausfuehren(hass: HomeAssistant, connection, msg: dict[str, Any], aufgabe) -> None:
    try:
        ergebnis = await aufgabe
    except ValueError as fehler:
        _ablehnen(hass, connection, msg, str(fehler))
        return
    connection.send_result(msg["id"], ergebnis if ergebnis is not None else {"ok": True})


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/automatik/einrichten", vol.Required("heizkreis"): KENNUNG}
    | EINSTELLUNGEN
)
@websocket_api.require_admin
@websocket_api.async_response
async def _ws_einrichten(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Eine Automatik für einen Heizkreis anlegen."""
    entry = _eintrag_zum_heizkreis(hass, msg["heizkreis"])
    if entry is None:
        _ablehnen(hass, connection, msg, "Diesen Heizkreis kennt keine Anlage.")
        return
    roh = {k: v for k, v in msg.items() if k not in ("id", "type")}
    await _ausfuehren(hass, connection, msg, verwaltung_holen(hass).einrichten(entry, roh))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/automatik/einstellen",
        vol.Required("heizkreis"): KENNUNG,
        vol.Optional("aktiv"): bool,
        vol.Optional("modus"): vol.In(MODI),
        vol.Optional("eigene"): vol.All(
            {vol.In(EIGENE_FELDER): vol.Any(int, float, str, bool)},
            vol.Length(max=20),
        ),
    }
    | EINSTELLUNGEN
)
@websocket_api.require_admin
@websocket_api.async_response
async def _ws_einstellen(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Einstellungen einer Automatik ändern."""
    aenderung = {k: v for k, v in msg.items() if k not in ("id", "type", "heizkreis")}
    await _ausfuehren(
        hass, connection, msg, verwaltung_holen(hass).einstellen(msg["heizkreis"], aenderung)
    )


# Dieselben Bereiche wie an der Steuerung (TA Heizbetrieb, TA Absenkbetrieb).
HEIZBETRIEB = vol.All(vol.Coerce(float), vol.Range(min=0.0, max=30.0))
ABSENKBETRIEB = vol.All(vol.Coerce(float), vol.Range(min=-10.0, max=20.0))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/automatik/heizgrenzen",
        vol.Required("heizkreis"): KENNUNG,
        vol.Optional("heizbetrieb"): HEIZBETRIEB,
        vol.Optional("absenkbetrieb"): ABSENKBETRIEB,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def _ws_heizgrenzen(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Heizgrenzen der Steuerung schreiben; die Automatik liest sie beim nächsten Abruf."""
    werte = {name: msg[name] for name in ("heizbetrieb", "absenkbetrieb") if name in msg}
    if not werte:
        _ablehnen(hass, connection, msg, "Keine Heizgrenze angegeben.")
        return
    await _ausfuehren(
        hass, connection, msg, verwaltung_holen(hass).heizgrenzen(msg["heizkreis"], werte)
    )


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/automatik/uebernehmen", vol.Required("heizkreis"): KENNUNG}
)
@websocket_api.require_admin
@websocket_api.async_response
async def _ws_uebernehmen(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Eine Pause nach Handeingriff aufheben."""
    await _ausfuehren(hass, connection, msg, verwaltung_holen(hass).uebernehmen(msg["heizkreis"]))


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/automatik/entfernen", vol.Required("heizkreis"): KENNUNG}
)
@websocket_api.require_admin
@websocket_api.async_response
async def _ws_entfernen(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Eine Automatik löschen."""
    await _ausfuehren(hass, connection, msg, verwaltung_holen(hass).entfernen(msg["heizkreis"]))


@callback
def async_register_automatik(hass: HomeAssistant) -> None:
    """Die Befehle anmelden – einmal je Start."""
    if hass.data.get(f"{DOMAIN}_automatik_ws"):
        return
    for befehl in (
        _ws_lesen,
        _ws_kandidaten,
        _ws_einrichten,
        _ws_einstellen,
        _ws_uebernehmen,
        _ws_heizgrenzen,
        _ws_entfernen,
    ):
        websocket_api.async_register_command(hass, befehl)
    hass.data[f"{DOMAIN}_automatik_ws"] = True
