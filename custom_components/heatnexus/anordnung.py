"""Selbst gewählte Anordnung der Karten in der Oberfläche.

Die Oberfläche baut ihre Karten aus dem, was die Anlage meldet. Welche
Reihenfolge, welche Spaltenzahl und welche Breite dem Nutzer davon gefällt,
steht hier – **je Benutzer und je Reiter**, gespeichert über den ``Store`` von
Home Assistant.

**Neue Anlagenteile dürfen die Anordnung nicht zerreißen.** Deshalb wird nicht
die Reihenfolge als solche gespeichert, sondern die Reihenfolge *bekannter
Kennungen*. Beim Anzeigen mischt ``ordnung_anwenden`` beides zusammen: Was der
Nutzer sortiert hat, behält seinen Platz; was neu dazukommt, rutscht an die
Stelle, an der es von Haus aus stünde – hinter seinen Vorgänger aus der
Standardreihenfolge. Kennungen, die es nicht mehr gibt, fallen still weg,
bleiben aber gespeichert: Ein zeitweise fehlendes Anlagenteil soll seinen
Platz nicht dadurch verlieren, dass es einmal nicht geantwortet hat.

Die Kennung einer Karte ist deshalb nie eine laufende Nummer, sondern ihre
Art (``kessel``, ``status``, ``verlauf``) bzw. bei Karten, die es je
Anlagenteil gibt, die Gerätekennung (``heizkreis:<device_id>``). Beides
überlebt eine erneute Erkennung.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
import voluptuous as vol

from .const import DOMAIN
from .helpers import ordnung_anwenden  # noqa: F401  (Teil der Schnittstelle dieses Moduls)
from .schema import FARBSAETZE

# Fassung des Speicherformats. Wird sie erhöht, muss `_async_migrate_func`
# eines Stores die alten Daten übersetzen – bis dahin gibt es nur die 1.
ANORDNUNG_STORE_VERSION = 1
ANORDNUNG_STORE_KEY = f"{DOMAIN}.anordnung"

# Reiter, die eine eigene Anordnung haben.
#
# **Muss zu `frontend/ordnung.js` passen.** Die Liste ist nicht nur Aufzählung,
# sondern Prüfung: `vol.In(REITER)` weist eine Anordnung für einen unbekannten
# Reiter ab. Steht dort einer, den die Oberfläche anbietet, der hier aber
# fehlt, lässt sich seine Karte zwar verschieben und verbreitern – gespeichert
# wird nichts, und beim nächsten Öffnen steht wieder der Standard.
REITER = ("uebersicht", "steuerung", "wartung", "verlauf", "zeitprogramme", "hilfe")

# Neben den Reitern steht je Benutzer ein Satz Einstellungen, die für die
# ganze Oberfläche gelten. Der Schlüssel darf keinem Reiter gleichen.
EINSTELLUNGEN = "einstellungen"

# 0 heißt „automatisch": so viele Spalten, wie nebeneinander passen.
SPALTEN_AUTO = 0
SPALTEN_MAX = 4

# Wie breit eine Karte höchstens werden darf, in Spalten.
BREITE_MAX = 4

# Obergrenzen. Der Speicher gehört Home Assistant, nicht der Oberfläche: Eine
# fehlerhafte oder böswillige Gegenstelle soll ihn nicht vollschreiben können.
KENNUNG_MAX_LAENGE = 160
KARTEN_MAX = 300


def _kennung(wert: Any) -> str:
    """Eine Kartenkennung prüfen."""
    text = str(wert)
    if not text or len(text) > KENNUNG_MAX_LAENGE:
        raise vol.Invalid("Kartenkennung fehlt oder ist zu lang")
    return text


REITER_SCHEMA = vol.Schema(
    {
        vol.Optional("spalten"): vol.All(int, vol.Range(min=SPALTEN_AUTO, max=SPALTEN_MAX)),
        vol.Optional("ordnung"): vol.All([_kennung], vol.Length(max=KARTEN_MAX)),
        vol.Optional("versteckt"): vol.All([_kennung], vol.Length(max=KARTEN_MAX)),
        vol.Optional("breite"): vol.All(
            {_kennung: vol.All(int, vol.Range(min=1, max=BREITE_MAX))},
            vol.Length(max=KARTEN_MAX),
        ),
    }
)


EINSTELLUNGEN_SCHEMA = vol.Schema({vol.Optional("farbsatz"): vol.In(FARBSAETZE)})


def _store(hass: HomeAssistant) -> Store:
    """Der Speicher – einer für die ganze Integration, Benutzer darin getrennt."""
    speicher = hass.data.get(f"{DOMAIN}_anordnung_store")
    if speicher is None:
        speicher = Store(hass, ANORDNUNG_STORE_VERSION, ANORDNUNG_STORE_KEY)
        hass.data[f"{DOMAIN}_anordnung_store"] = speicher
    return speicher


async def _laden(hass: HomeAssistant) -> dict[str, Any]:
    """Der gesamte gespeicherte Stand, nach Benutzern getrennt."""
    zwischenspeicher = hass.data.get(f"{DOMAIN}_anordnung")
    if zwischenspeicher is None:
        gespeichert = await _store(hass).async_load() or {}
        zwischenspeicher = gespeichert.get("benutzer") or {}
        hass.data[f"{DOMAIN}_anordnung"] = zwischenspeicher
    return zwischenspeicher


async def _sichern(hass: HomeAssistant, benutzer: dict[str, Any]) -> None:
    """Den Stand auf die Platte schreiben."""
    hass.data[f"{DOMAIN}_anordnung"] = benutzer
    await _store(hass).async_save({"benutzer": benutzer})


async def anordnung_lesen(hass: HomeAssistant, benutzer_id: str) -> dict[str, Any]:
    """Die Anordnung eines Benutzers – leer, solange er nichts verstellt hat."""
    return dict((await _laden(hass)).get(benutzer_id) or {})


async def anordnung_setzen(
    hass: HomeAssistant, benutzer_id: str, reiter: str, anordnung: dict[str, Any]
) -> None:
    """Die Anordnung eines Reiters für einen Benutzer festhalten."""
    alle = dict(await _laden(hass))
    eigene = dict(alle.get(benutzer_id) or {})
    eigene[reiter] = anordnung
    alle[benutzer_id] = eigene
    await _sichern(hass, alle)


async def einstellungen_setzen(
    hass: HomeAssistant, benutzer_id: str, einstellungen: dict[str, Any]
) -> None:
    """Die Einstellungen eines Benutzers ergänzen – Reiter bleiben unberührt."""
    alle = dict(await _laden(hass))
    eigene = dict(alle.get(benutzer_id) or {})
    eigene[EINSTELLUNGEN] = {**(eigene.get(EINSTELLUNGEN) or {}), **einstellungen}
    alle[benutzer_id] = eigene
    await _sichern(hass, alle)


async def anordnung_zuruecksetzen(
    hass: HomeAssistant, benutzer_id: str, reiter: str | None = None
) -> None:
    """Auf die Standardanordnung zurückgehen – ein Reiter oder alle."""
    alle = dict(await _laden(hass))
    if reiter is None:
        alle.pop(benutzer_id, None)
    else:
        eigene = dict(alle.get(benutzer_id) or {})
        eigene.pop(reiter, None)
        if eigene:
            alle[benutzer_id] = eigene
        else:
            alle.pop(benutzer_id, None)
    await _sichern(hass, alle)


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/anordnung"})
@websocket_api.async_response
async def _ws_lesen(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Die Anordnung des angemeldeten Benutzers zurückgeben."""
    connection.send_result(msg["id"], await anordnung_lesen(hass, connection.user.id))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/anordnung/setzen",
        vol.Required("reiter"): vol.In(REITER),
        vol.Required("anordnung"): REITER_SCHEMA,
    }
)
@websocket_api.async_response
async def _ws_setzen(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Eine geänderte Anordnung übernehmen."""
    await anordnung_setzen(hass, connection.user.id, msg["reiter"], msg["anordnung"])
    connection.send_result(msg["id"], {"gespeichert": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/anordnung/einstellungen",
        vol.Required("einstellungen"): EINSTELLUNGEN_SCHEMA,
    }
)
@websocket_api.async_response
async def _ws_einstellungen(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Eine Einstellung der Oberfläche übernehmen."""
    await einstellungen_setzen(hass, connection.user.id, msg["einstellungen"])
    connection.send_result(msg["id"], {"gespeichert": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/anordnung/zuruecksetzen",
        vol.Optional("reiter"): vol.In(REITER),
    }
)
@websocket_api.async_response
async def _ws_zuruecksetzen(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Auf die Standardanordnung zurückgehen."""
    await anordnung_zuruecksetzen(hass, connection.user.id, msg.get("reiter"))
    connection.send_result(msg["id"], {"zurueckgesetzt": True})


@callback
def async_register_anordnung(hass: HomeAssistant) -> None:
    """Die Befehle anmelden – einmal je Start."""
    if hass.data.get(f"{DOMAIN}_anordnung_ws"):
        return
    websocket_api.async_register_command(hass, _ws_lesen)
    websocket_api.async_register_command(hass, _ws_setzen)
    websocket_api.async_register_command(hass, _ws_einstellungen)
    websocket_api.async_register_command(hass, _ws_zuruecksetzen)
    hass.data[f"{DOMAIN}_anordnung_ws"] = True
