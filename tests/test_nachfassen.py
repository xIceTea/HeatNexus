"""Gezieltes Nachlesen nach einer Bedienung, und was nach dem Entladen geschieht."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from .conftest import ha_fehlt, requires_ha

pytestmark = requires_ha()

if not ha_fehlt():
    from custom_components.heatnexus import coordinator as coordinator_modul
    from custom_components.heatnexus.coordinator import WindhagerDataUpdateCoordinator

OID = "/1/60/0/9/75/0"


@pytest.fixture
def coordinator(hass, monkeypatch):
    eintrag = MagicMock()
    eintrag.data = {"name": "Heizhaus"}
    eintrag.title = "Heizhaus"
    eintrag.entry_id = "abc123"
    eintrag.async_create_background_task = lambda h, coro, name: h.async_create_task(coro)
    client = MagicMock()
    client.auth_errors = 0
    client.fetch_oids = AsyncMock(return_value={OID: "1"})
    k = WindhagerDataUpdateCoordinator(hass, client, eintrag, "192.0.2.1", "Heizhaus")
    k.data = {"oids": {OID: "0"}, "devices": []}
    monkeypatch.setattr(coordinator_modul.asyncio, "sleep", AsyncMock())
    return k


async def test_nachlesen_legt_den_wert_in_den_bestand(coordinator):
    assert await coordinator.werte_nachlesen([OID]) == {OID: "1"}
    assert coordinator.data["oids"][OID] == "1"


async def test_ein_fehlschlag_beim_nachlesen_bleibt_still(coordinator):
    coordinator.client.fetch_oids.side_effect = OSError("weg")

    assert await coordinator.werte_nachlesen([OID]) is None
    assert coordinator.data["oids"][OID] == "0"


async def test_das_nachfassen_endet_mit_dem_erwarteten_wert(coordinator, hass):
    coordinator.nachfassen([OID], {OID: "1"}, anzahl=6, abstand=3)
    await hass.async_block_till_done()

    assert coordinator.client.fetch_oids.await_count == 1


async def test_ohne_erwartung_liest_es_jedes_mal(coordinator, hass):
    coordinator.nachfassen([OID], anzahl=4, abstand=3)
    await hass.async_block_till_done()

    assert coordinator.client.fetch_oids.await_count == 4


async def test_die_meldungsliste_wird_sofort_nachgelesen(coordinator, hass):
    neu = [{"id": 154, "status": "receipted"}]
    coordinator.client.meldungsliste_nachlesen = AsyncMock(return_value=({"60": "PUR 09  OK"}, neu))
    coordinator.data["stoerspeicher"] = [{"id": 154, "status": "new"}]

    coordinator.meldungen_nachfassen(anzahl=6, abstand=3)
    await hass.async_block_till_done()

    assert coordinator.client.meldungsliste_nachlesen.await_count == 1
    assert coordinator.data["stoerspeicher"] == neu
    assert coordinator.data["status"] == {"60": "PUR 09  OK"}


async def test_ohne_aenderung_liest_es_die_meldungsliste_mehrmals(coordinator, hass):
    gleich = [{"id": 154, "status": "new"}]
    coordinator.client.meldungsliste_nachlesen = AsyncMock(return_value=({}, gleich))
    coordinator.data["stoerspeicher"] = gleich

    coordinator.meldungen_nachfassen(anzahl=3, abstand=3)
    await hass.async_block_till_done()

    assert coordinator.client.meldungsliste_nachlesen.await_count == 3


# ---------------------------------------------------------------------------
# Nach dem Schließen öffnet der Client keine neue Sitzung
# ---------------------------------------------------------------------------
async def test_ein_geschlossener_client_fragt_nicht_mehr():
    from custom_components.heatnexus.client import WindhagerHttpClient
    from custom_components.heatnexus.client.gemeinsam import FEHLGESCHLAGEN

    client = WindhagerHttpClient("192.0.2.10", "geheim")
    await client.close()

    assert await client._fetch_oid(OID) == (OID, FEHLGESCHLAGEN)
    assert client._session is None


# ---------------------------------------------------------------------------
# Schreiben wartet nicht auf einen vollen Durchlauf
# ---------------------------------------------------------------------------
async def test_schreiben_wartet_nicht_auf_den_abruf(hass):
    from custom_components.heatnexus.switch import WindhagerSwitch

    from .test_plattformen import FakeCoordinator

    koordinator = FakeCoordinator()
    koordinator.async_update_listeners = MagicMock()
    koordinator.async_request_refresh = AsyncMock()
    koordinator.nachfassen = MagicMock()
    entitaet = WindhagerSwitch(
        koordinator, {"id": "SN1-0-9-75-0", "oid": OID, "name": "Prüfwert", "type": "switch"}
    )
    entitaet.hass = hass

    await entitaet.async_turn_on()

    koordinator.async_request_refresh.assert_not_awaited()
    koordinator.nachfassen.assert_called_once()
    assert koordinator.nachfassen.call_args.args[0] == [OID]


async def test_behaglichkeit_liest_raum_und_vorlaufsoll_gezielt_nach(hass):
    from custom_components.heatnexus.climate import WindhagerThermostatClimate

    from .test_plattformen import FakeCoordinator

    koordinator = FakeCoordinator({"/1/15/0/1/1/0": "22.0"})
    koordinator.client.update = AsyncMock()
    koordinator.async_update_listeners = MagicMock()
    koordinator.async_request_refresh = AsyncMock()
    koordinator.nachfassen = MagicMock()
    klima = WindhagerThermostatClimate(
        koordinator, {"id": "SN1-15-0", "name": "Heizkreis", "prefix": "/1/15/0"}
    )
    klima.hass = hass

    await klima.set_current_temp_compensation(1.0)

    koordinator.async_request_refresh.assert_not_awaited()
    assert koordinator.data["oids"]["/1/15/0/3/58/0"] == "1.0"
    assert koordinator.nachfassen.call_args.args[0] == [
        "/1/15/0/3/58/0",
        "/1/15/0/1/1/0",
        "/1/15/0/1/2/0",
    ]
