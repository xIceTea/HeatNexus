"""Einstellungen der Oberfläche je Benutzer über WebSocket: Reiterfolge."""

from __future__ import annotations

from .conftest import requires_ha

pytestmark = requires_ha()


async def _senden(client, **nachricht) -> dict:
    await client.send_json_auto_id(nachricht)
    return await client.receive_json()


async def test_reiterfolge_und_ausgeblendete_reiter_bleiben_gespeichert(hass, hass_ws_client):
    from custom_components.heatnexus.anordnung import async_register_anordnung

    async_register_anordnung(hass)
    client = await hass_ws_client(hass)

    antwort = await _senden(
        client,
        type="heatnexus/anordnung/einstellungen",
        einstellungen={"reiter": ["uebersicht", "zeitprogramme"], "reiter_versteckt": ["hilfe"]},
    )
    assert antwort["success"], antwort

    gelesen = (await _senden(client, type="heatnexus/anordnung"))["result"]
    assert gelesen["einstellungen"]["reiter"] == ["uebersicht", "zeitprogramme"]
    assert gelesen["einstellungen"]["reiter_versteckt"] == ["hilfe"]


async def test_unbekannter_reiter_wird_abgewiesen(hass, hass_ws_client):
    from custom_components.heatnexus.anordnung import async_register_anordnung

    async_register_anordnung(hass)
    client = await hass_ws_client(hass)

    antwort = await _senden(
        client,
        type="heatnexus/anordnung/einstellungen",
        einstellungen={"reiter": ["gibt_es_nicht"]},
    )
    assert not antwort["success"]
