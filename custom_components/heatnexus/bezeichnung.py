"""Eigene Bezeichnung eines Zeitprogramms, etwa „Übergangszeit".

Die Anlage kennt keine Programmnamen. Die Bezeichnung liegt in den Optionen des
Registry-Eintrags unter dem eigenen Namensraum; der Name der Entität bleibt.
"""

from __future__ import annotations

from typing import Any

from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import entity_registry as er
import voluptuous as vol

from .const import DOMAIN

# Muss zu `BEZEICHNUNG_MAX` in `frontend/zeitprogramm.js` passen.
BEZEICHNUNG_MAX = 40
SCHLUESSEL = "bezeichnung"


def bezeichnung_lesen(eintrag: er.RegistryEntry) -> str | None:
    """Die Bezeichnung aus den Registry-Optionen, sofern eine gesetzt ist."""
    return (eintrag.options.get(DOMAIN) or {}).get(SCHLUESSEL) or None


@callback
def bezeichnung_setzen(hass: HomeAssistant, entity_id: str, bezeichnung: str) -> None:
    """Setzen oder bei leerem Text entfernen; andere Optionen bleiben erhalten."""
    register = er.async_get(hass)
    eintrag = register.async_get(entity_id)
    if eintrag is None or eintrag.platform != DOMAIN or eintrag.domain != "sensor":
        raise ValueError(f"{entity_id} ist kein Zeitprogramm von HeatNexus")
    optionen = {
        schluessel: wert
        for schluessel, wert in (eintrag.options.get(DOMAIN) or {}).items()
        if schluessel != SCHLUESSEL
    }
    if bezeichnung:
        optionen[SCHLUESSEL] = bezeichnung
    register.async_update_entity_options(entity_id, DOMAIN, optionen)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/bezeichnung",
        vol.Required("entity_id"): str,
        vol.Required("bezeichnung"): vol.All(str, vol.Strip, vol.Length(max=BEZEICHNUNG_MAX)),
    }
)
@callback
def _ws_setzen(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Die Bezeichnung übernehmen; nötig ist das Recht, die Entität zu steuern."""
    if not connection.user.permissions.check_entity(msg["entity_id"], POLICY_CONTROL):
        raise Unauthorized(entity_id=msg["entity_id"])
    try:
        bezeichnung_setzen(hass, msg["entity_id"], msg["bezeichnung"])
    except ValueError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, str(err))
        return
    connection.send_result(msg["id"], {"gespeichert": True})


@callback
def async_register_bezeichnung(hass: HomeAssistant) -> None:
    """Den Befehl anmelden – einmal je Start."""
    if hass.data.get(f"{DOMAIN}_bezeichnung_ws"):
        return
    websocket_api.async_register_command(hass, _ws_setzen)
    hass.data[f"{DOMAIN}_bezeichnung_ws"] = True
