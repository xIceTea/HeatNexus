"""WebSocket-Befehle des Reiters „Automatik".

Lesen darf, wer die Klima-Entität des Heizkreises lesen darf. Ändern dürfen
nur Administratoren; jedes Schema ist nach oben begrenzt.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import math
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import voluptuous as vol

from ..const import DOMAIN
from ..rechte import darf_lesen
from . import profile
from .konfig import LISTEN_MAX, MODI, RAUM_ARTEN, pv_passt, raumfuehler_passt
from .laufzeit import Laufzeit, ortszeit
from .verwaltung import DOMAENE_JE_ART, Verwaltung, unique_id, verwaltung_holen

PROTOKOLL_ANZEIGE = 20
PV_PLATTFORMEN = frozenset({"forecast_solar", "solcast_solar", "open_meteo_solar_forecast"})
FENSTER_KLASSEN = frozenset({"window", "door", "opening"})
KENNUNG = vol.All(str, vol.Length(min=1, max=120))
ENTITAET = vol.All(str, vol.Length(max=255))


def _liste(grenze: int) -> vol.All:
    return vol.All([ENTITAET], vol.Length(max=grenze))


def _stunde(zeit: datetime | None, heute: Any) -> float | None:
    if zeit is None:
        return None
    lokal = dt_util.as_local(zeit)
    if lokal.date() != heute:
        return 24.0 if lokal.date() > heute else 0.0
    return lokal.hour + lokal.minute / 60


def _sonne(laufzeit: Laufzeit, jetzt: datetime) -> list[float]:
    """Relative Einstrahlung je Stunde: Tagbogen mal (1 − Bewölkung)."""
    aufgang, untergang = laufzeit.sonne(jetzt.date())
    if not aufgang or not untergang or not laufzeit.stunden:
        return []
    wolken: dict[int, float] = {}
    for eintrag in laufzeit.stunden:
        zeit = ortszeit(eintrag.get("datetime"))
        if zeit and zeit.date() == jetzt.date() and eintrag.get("cloud_coverage") is not None:
            wolken[zeit.hour] = float(eintrag["cloud_coverage"])
    auf = aufgang.hour + aufgang.minute / 60
    unter = untergang.hour + untergang.minute / 60
    werte = []
    for stunde in range(25):
        if not auf < stunde < unter:
            werte.append(0.0)
            continue
        bogen = math.sin(math.pi * (stunde - auf) / (unter - auf))
        anteil = 1 - wolken.get(stunde, 50.0) / 100
        werte.append(round(max(0.0, bogen * anteil), 3))
    return werte


def _entitaeten(hass: HomeAssistant, device_id: str) -> dict[str, str | None]:
    register = er.async_get(hass)
    return {
        art: register.async_get_entity_id(domaene, DOMAIN, unique_id(device_id, art))
        for art, domaene in DOMAENE_JE_ART.items()
    }


def _eintrag(hass: HomeAssistant, verwaltung: Verwaltung, coordinator: Any, b: dict) -> dict:
    device_id = b["device_id"]
    geraet = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, device_id)})
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
    heute = jetzt.date()
    ergebnis.update(
        eingerichtet=True,
        konfig=laufzeit.konfig,
        werte=asdict(werte),
        zustand=laufzeit.zustand.value,
        begruendung=laufzeit.begruendung,
        kennwerte={
            "sonnenquote": lage.sonnenquote if lage else None,
            "raum": lage.raum if lage else None,
            "soll": g.absenkung_basis or g.saison_soll or (lage.soll if lage else None),
            "at_gedaempft": lage.at_gedaempft if lage else None,
            "heizgrenze": werte.heizgrenze,
            "eingriffe": laufzeit.steller.stand.eingriffe,
            "budget": werte.budget,
        },
        tag={
            "sonne": _sonne(laufzeit, jetzt),
            "absenkung_von": _stunde(g.absenkung_von, heute),
            "absenkung_bis": _stunde(g.absenkung_bis, heute),
            "absenkung_ziel": _stunde(g.absenkung_ziel, heute),
            "entscheidungen": [
                int(z[:2]) + int(z[3:]) / 60 for z in (werte.entscheidung, werte.nachpruefung) if z
            ],
            "jetzt": jetzt.hour + jetzt.minute / 60,
        },
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
    heizkreise = []
    for entry in _geladene(hass):
        for coordinator, beschreibung in Verwaltung.heizkreise(entry):
            klima = register.async_get_entity_id("climate", DOMAIN, beschreibung.get("id", ""))
            # Ohne Klima-Entität gibt es nichts zu prüfen und nichts zu bedienen.
            if not klima or not darf_lesen(connection.user, klima):
                continue
            heizkreise.append(_eintrag(hass, verwaltung, coordinator, beschreibung))
    connection.send_result(
        msg["id"],
        {
            "heizkreise": heizkreise,
            "darf_aendern": bool(connection.user and connection.user.is_admin),
            "profile": {name: asdict(werte) for name, werte in profile.VORGABEN.items()},
            "grenzen": profile.GRENZEN,
        },
    )


def _bereich(hass: HomeAssistant, eintrag: er.RegistryEntry | None) -> str:
    if eintrag is None:
        return ""
    area_id = eintrag.area_id
    if area_id is None and eintrag.device_id:
        geraet = dr.async_get(hass).async_get(eintrag.device_id)
        area_id = geraet.area_id if geraet else None
    bereich = ar.async_get(hass).async_get_area(area_id) if area_id else None
    return bereich.name if bereich else ""


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/automatik/kandidaten"})
@callback
def _ws_kandidaten(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Auswahllisten für den Einrichtungsdialog."""
    register = er.async_get(hass)
    listen: dict[str, list[dict[str, str]]] = {
        "temperatur": [],
        "wetter": [],
        "pv": [],
        "personen": [],
        "fenster": [],
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
        if domaene == "sensor" and klasse == "temperature" and raumfuehler_passt(entity_id):
            ziel = "temperatur"
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
        elif domaene == "person":
            ziel = "personen"
        elif domaene == "binary_sensor" and klasse in FENSTER_KLASSEN:
            ziel = "fenster"
        else:
            continue
        listen[ziel].append(
            {
                "entity_id": entity_id,
                "name": str(zustand.attributes.get("friendly_name") or entity_id),
                "bereich": _bereich(hass, eintrag),
            }
        )
    for liste in listen.values():
        liste.sort(key=lambda e: (e["bereich"] or "~", e["name"]))
    connection.send_result(msg["id"], listen)


EINSTELLUNGEN = {
    vol.Optional("heizflaechen"): vol.In(tuple(profile.HEIZFLAECHEN)),
    vol.Optional("profil"): vol.In(profile.PROFILE),
    vol.Optional("raeume"): _liste(LISTEN_MAX["raeume"]),
    vol.Optional("raum_art"): vol.In(RAUM_ARTEN),
    vol.Optional("wetter"): ENTITAET,
    vol.Optional("pv"): vol.Any(None, ENTITAET),
    vol.Optional("aussen"): vol.Any(None, ENTITAET),
    vol.Optional("personen"): _liste(LISTEN_MAX["personen"]),
    vol.Optional("fenster"): _liste(LISTEN_MAX["fenster"]),
    vol.Optional("fenster_erkennung"): bool,
}


async def _ausfuehren(connection, msg: dict[str, Any], aufgabe) -> None:
    try:
        ergebnis = await aufgabe
    except ValueError as fehler:
        connection.send_error(msg["id"], "ungueltig", str(fehler))
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
        connection.send_error(msg["id"], "ungueltig", "Diesen Heizkreis kennt keine Anlage.")
        return
    roh = {k: v for k, v in msg.items() if k not in ("id", "type")}
    await _ausfuehren(connection, msg, verwaltung_holen(hass).einrichten(entry, roh))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/automatik/einstellen",
        vol.Required("heizkreis"): KENNUNG,
        vol.Optional("aktiv"): bool,
        vol.Optional("modus"): vol.In(MODI),
        vol.Optional("eigene"): vol.All(
            {
                vol.In(tuple(profile.GRENZEN) + profile.UHRZEITEN + ("stark",)): vol.Any(
                    int, float, str, bool
                )
            },
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
        connection, msg, verwaltung_holen(hass).einstellen(msg["heizkreis"], aenderung)
    )


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/automatik/uebernehmen", vol.Required("heizkreis"): KENNUNG}
)
@websocket_api.require_admin
@websocket_api.async_response
async def _ws_uebernehmen(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Eine Pause nach Handeingriff aufheben."""
    await _ausfuehren(connection, msg, verwaltung_holen(hass).uebernehmen(msg["heizkreis"]))


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/automatik/entfernen", vol.Required("heizkreis"): KENNUNG}
)
@websocket_api.require_admin
@websocket_api.async_response
async def _ws_entfernen(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Eine Automatik löschen."""
    await _ausfuehren(connection, msg, verwaltung_holen(hass).entfernen(msg["heizkreis"]))


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
        _ws_entfernen,
    ):
        websocket_api.async_register_command(hass, befehl)
    hass.data[f"{DOMAIN}_automatik_ws"] = True
