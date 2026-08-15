"""Die Lovelace-Karte mit dem Anlagenschaubild.

Serverseite: ein WebSocket-Befehl, der je Anlage die Zeichnung und die
Farbtabellen liefert. Gezeichnet wird im Browser – aus denselben Teilen wie
die eigene Oberfläche.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
import voluptuous as vol

from .auslieferung import async_dateien_ausliefern, karte_anmelden
from .const import DOMAIN
from .dashboard import _anlagen
from .schema import schaubild_daten

_LOGGER = logging.getLogger(__name__)


def kartendaten(
    hass: HomeAssistant,
    auswahl: dict[str, list[str]] | None = None,
    teile_aus: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Alle Anlagen mit ihrem Schaubild, frisch aus der Registrierung."""
    return schaubild_daten(_anlagen(hass), auswahl, teile_aus or [])


# Obergrenzen, damit eine fehlerhafte Gegenstelle den Aufbau nicht sprengt.
AUSWAHL_MAX = 60
WERTE_MAX = 30


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/schaubild",
        vol.Optional("auswahl"): vol.All(
            {str: vol.All([str], vol.Length(max=WERTE_MAX))}, vol.Length(max=AUSWAHL_MAX)
        ),
        vol.Optional("teile_aus"): vol.All([str], vol.Length(max=AUSWAHL_MAX)),
    }
)
@callback
def _ws_schaubild(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Die Schaubilder aller Anlagen zurückgeben, nach eigener Auswahl."""
    connection.send_result(
        msg["id"], kartendaten(hass, msg.get("auswahl"), msg.get("teile_aus"))
    )


async def async_setup_karte(hass: HomeAssistant, version: str = "") -> None:
    """Karte bereitstellen.

    Schlägt das fehl, bleibt alles andere nutzbar – die Karte ist Beiwerk.
    """
    try:
        await async_dateien_ausliefern(hass, version)
        if not hass.data.get(f"{DOMAIN}_karte_ws"):
            websocket_api.async_register_command(hass, _ws_schaubild)
            hass.data[f"{DOMAIN}_karte_ws"] = True
        karte_anmelden(hass, version)
    except Exception as err:
        _LOGGER.warning("Kartenmodul konnte nicht angemeldet werden: %s", err)
