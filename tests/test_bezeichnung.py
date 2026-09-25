"""Die eigene Bezeichnung eines Zeitprogramms in den Registry-Optionen."""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

ZEITPROGRAMM_JS = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "heatnexus"
    / "frontend"
    / "zeitprogramm.js"
)


@pytest.fixture
async def programm(hass):
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.bezeichnung import async_register_bezeichnung
    from custom_components.heatnexus.const import DOMAIN

    eintrag = MockConfigEntry(domain=DOMAIN)
    eintrag.add_to_hass(hass)
    async_register_bezeichnung(hass)
    return er.async_get(hass).async_get_or_create(
        "sensor", DOMAIN, "SN1-0-3-62-0", config_entry=eintrag, original_name="Heizprogramm 2"
    )


async def _senden(client, entity_id: str, bezeichnung: str) -> dict:
    await client.send_json_auto_id(
        {"type": "heatnexus/bezeichnung", "entity_id": entity_id, "bezeichnung": bezeichnung}
    )
    return await client.receive_json()


def _optionen(hass, entity_id: str) -> dict:
    from homeassistant.helpers import entity_registry as er

    return dict(er.async_get(hass).async_get(entity_id).options.get("heatnexus") or {})


async def test_die_bezeichnung_wird_gespeichert(hass, hass_ws_client, programm):
    antwort = await _senden(await hass_ws_client(hass), programm.entity_id, " Übergangszeit ")

    assert antwort["success"], antwort
    assert _optionen(hass, programm.entity_id) == {"bezeichnung": "Übergangszeit"}


async def test_der_name_der_entitaet_bleibt(hass, hass_ws_client, programm):
    from homeassistant.helpers import entity_registry as er

    await _senden(await hass_ws_client(hass), programm.entity_id, "Übergangszeit")

    eintrag = er.async_get(hass).async_get(programm.entity_id)
    assert eintrag.name is None
    assert eintrag.original_name == "Heizprogramm 2"


async def test_eine_leere_bezeichnung_entfernt_sie(hass, hass_ws_client, programm):
    client = await hass_ws_client(hass)
    await _senden(client, programm.entity_id, "Übergangszeit")

    antwort = await _senden(client, programm.entity_id, "   ")

    assert antwort["success"], antwort
    assert "bezeichnung" not in _optionen(hass, programm.entity_id)


async def test_eine_zu_lange_bezeichnung_wird_abgewiesen(hass, hass_ws_client, programm):
    antwort = await _senden(await hass_ws_client(hass), programm.entity_id, "x" * 41)

    assert not antwort["success"]
    assert antwort["error"]["code"] == "invalid_format"


async def test_eine_fremde_entitaet_wird_abgewiesen(hass, hass_ws_client, programm):
    from homeassistant.helpers import entity_registry as er

    fremd = er.async_get(hass).async_get_or_create("sensor", "demo", "irgendwas")

    antwort = await _senden(await hass_ws_client(hass), fremd.entity_id, "Winter")

    assert not antwort["success"]
    assert antwort["error"]["code"] == "not_found"


async def test_ohne_steuerrecht_wird_nichts_gespeichert(
    hass, hass_ws_client, hass_read_only_access_token, programm
):
    client = await hass_ws_client(hass, hass_read_only_access_token)

    antwort = await _senden(client, programm.entity_id, "Winter")

    assert not antwort["success"]
    assert antwort["error"]["code"] == "unauthorized"
    assert _optionen(hass, programm.entity_id) == {}


def test_die_laengengrenze_gilt_auf_beiden_seiten():
    from custom_components.heatnexus.bezeichnung import BEZEICHNUNG_MAX

    treffer = re.search(r"BEZEICHNUNG_MAX = (\d+)", ZEITPROGRAMM_JS.read_text(encoding="utf-8"))
    assert treffer, "zeitprogramm.js führt keine BEZEICHNUNG_MAX"
    assert int(treffer.group(1)) == BEZEICHNUNG_MAX
