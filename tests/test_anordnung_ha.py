"""Einstellungen der Oberfläche je Benutzer über WebSocket: Reiterfolge, Kopfzeile, Menütaste."""

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


async def test_kopfzeile_und_menuetaste_werden_gespeichert_unbekannte_abgewiesen(
    hass, hass_ws_client
):
    from custom_components.heatnexus.anordnung import async_register_anordnung

    async_register_anordnung(hass)
    client = await hass_ws_client(hass)

    antwort = await _senden(
        client,
        type="heatnexus/anordnung/einstellungen",
        einstellungen={
            "kopf": "farbig",
            "menue": "taste",
            "alle": "zusammen",
            "strang": "verkleinern",
            "strang_groesse": "gross",
        },
    )
    assert antwort["success"], antwort
    gelesen = (await _senden(client, type="heatnexus/anordnung"))["result"]
    assert gelesen["einstellungen"]["kopf"] == "farbig"
    assert gelesen["einstellungen"]["menue"] == "taste"
    assert gelesen["einstellungen"]["alle"] == "zusammen"
    assert gelesen["einstellungen"]["strang"] == "verkleinern"
    assert gelesen["einstellungen"]["strang_groesse"] == "gross"

    for fremd in ({"kopf": "bunt"}, {"strang": "falten"}, {"strang_groesse": "riesig"}):
        antwort = await _senden(
            client, type="heatnexus/anordnung/einstellungen", einstellungen=fremd
        )
        assert not antwort["success"], fremd


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


async def test_offene_erzeuger_werden_je_ansicht_gespeichert(hass, hass_ws_client):
    from custom_components.heatnexus.anordnung import async_register_anordnung

    async_register_anordnung(hass)
    client = await hass_ws_client(hass)
    wahl = {"anlage:9c1a2a075f23a07f3d5257079f2c028a": False, "alle:b1861b10": True}

    antwort = await _senden(
        client, type="heatnexus/anordnung/einstellungen", einstellungen={"erzeuger": wahl}
    )
    assert antwort["success"], antwort
    gelesen = (await _senden(client, type="heatnexus/anordnung"))["result"]
    assert gelesen["einstellungen"]["erzeuger"] == wahl


async def test_erzeugerwahl_ohne_ansicht_oder_ueber_der_grenze_wird_abgewiesen(
    hass, hass_ws_client
):
    from custom_components.heatnexus.anordnung import ERZEUGER_MAX, async_register_anordnung

    async_register_anordnung(hass)
    client = await hass_ws_client(hass)
    zu_viele = {f"anlage:teil{nummer}": True for nummer in range(ERZEUGER_MAX + 1)}

    for wahl in ({"teil": True}, {"anlage:teil": "offen"}, zu_viele):
        antwort = await _senden(
            client, type="heatnexus/anordnung/einstellungen", einstellungen={"erzeuger": wahl}
        )
        assert not antwort["success"], wahl
