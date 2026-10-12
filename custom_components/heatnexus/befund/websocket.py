"""WebSocket-Befehl des Reiters „Befund“: der Stand je Anlage, die der Benutzer sehen darf."""

from __future__ import annotations

from statistics import mean
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
import voluptuous as vol

from ..automatik.verwaltung import verwaltung_holen
from ..const import DOMAIN
from ..rechte import darf_lesen
from . import haus
from .laufzeit import Sammler, befund_holen

NACHT_EINTRAEGE = 8


async def _aussen_nacht(hass: HomeAssistant, wetter: str | None) -> float | None:
    """Mittel der Vorhersage über die nächsten acht Stunden; ohne Wetter nichts."""
    if not wetter:
        return None
    vorhersage = await verwaltung_holen(hass).prognose(wetter, "hourly") or []
    werte = [
        e["temperature"] for e in vorhersage[:NACHT_EINTRAEGE] if e.get("temperature") is not None
    ]
    return round(mean(werte), 1) if werte else None


def _darf(hass: HomeAssistant, user: Any, sammler: Sammler) -> bool:
    """Wer die Klima-Entität eines Heizkreises der Anlage lesen darf, sieht ihren Befund."""
    if user is None or user.is_admin:
        return True
    register = er.async_get(hass)
    for b in sammler.kreise():
        klima = register.async_get_entity_id("climate", DOMAIN, b.get("id", ""))
        if klima and darf_lesen(user, klima):
            return True
    return False


async def _nacht_einsetzen(
    hass: HomeAssistant, stand: dict[str, Any], vorhersagen: dict[str | None, float | None]
) -> None:
    """Die Nacht ohne Heizung braucht die Wettervorhersage; je Wetter-Entität einmal gelesen."""
    for abschnitt in stand["abschnitte"]:
        if abschnitt["art"] != "haus":
            continue
        wetter = (verwaltung_holen(hass).konfig(abschnitt["kennung"]) or {}).get("wetter")
        if wetter not in vorhersagen:
            vorhersagen[wetter] = await _aussen_nacht(hass, wetter)
        aussen = vorhersagen[wetter]
        for befund in abschnitt["befunde"]:
            if befund["art"] == "waermespeicher" and befund["wert"]:
                raum = befund["angaben"].get("raum")
                befund["angaben"]["nacht"] = haus.nacht(befund["wert"], raum, aussen)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/befund"})
@websocket_api.async_response
async def _ws_befund(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    anlagen = {}
    vorhersagen: dict[str | None, float | None] = {}
    for anlage_id, sammler in befund_holen(hass).sammler.items():
        if not _darf(hass, connection.user, sammler):
            continue
        stand = sammler.stand()
        await _nacht_einsetzen(hass, stand, vorhersagen)
        anlagen[anlage_id] = stand
    connection.send_result(msg["id"], {"anlagen": anlagen})


@callback
def async_register_befund(hass: HomeAssistant) -> None:
    """Den Befehl anmelden – einmal je Start."""
    if hass.data.get(f"{DOMAIN}_befund_ws"):
        return
    websocket_api.async_register_command(hass, _ws_befund)
    hass.data[f"{DOMAIN}_befund_ws"] = True
