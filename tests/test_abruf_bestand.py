"""Gezielt gelesene Werte und der Bestand des Abrufs."""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def client_module():
    from custom_components.heatnexus import client

    return client


@pytest.fixture
def client(client_module):
    c = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    c.neuron_by_node = {"60": "0000ABCD1234"}

    async def ohne_anlage(url, semaphore=None):
        return None, 599

    c._get = ohne_anlage
    c.oids = set()
    return c


def _anlage(client, monkeypatch, antworten: dict):
    """Jede Adresse liefert ihren Wert aus `antworten`; fehlt sie, scheitert sie."""
    from custom_components.heatnexus.client.gemeinsam import FEHLGESCHLAGEN

    gefragt: list[str] = []

    async def fetch_oid(oid):
        gefragt.append(oid)
        return oid, antworten.get(oid, FEHLGESCHLAGEN)

    monkeypatch.setattr(client, "_fetch_oid", fetch_oid)
    return gefragt


# ---------------------------------------------------------------------------
# Gezielt gelesene Werte gehören in den Bestand
# ---------------------------------------------------------------------------
async def test_ein_gezielt_gelesener_wert_ueberdauert_den_naechsten_durchlauf(client, monkeypatch):
    client.poll_oids = {"/1/60/0/9/1/0", "/1/60/0/0/7/0"}
    client.poll_class = {"/1/60/0/9/1/0": "slow", "/1/60/0/0/7/0": "fast"}
    client._letzte_werte = {"/1/60/0/9/1/0": "100", "/1/60/0/0/7/0": "60"}
    client._tick = 1
    _anlage(client, monkeypatch, {"/1/60/0/9/1/0": "101", "/1/60/0/0/7/0": "61"})

    assert await client.fetch_oids(["/1/60/0/9/1/0"]) == {"/1/60/0/9/1/0": "101"}
    daten = await client.fetch_all()

    assert daten["oids"]["/1/60/0/9/1/0"] == "101"


async def test_ein_gezielt_gelesener_wert_ist_nicht_mehr_offen(client, monkeypatch):
    client.poll_oids = set()
    _anlage(client, monkeypatch, {"/1/60/0/9/1/0": "101"})
    client.register_poll_oid("/1/60/0/9/1/0")
    assert "/1/60/0/9/1/0" in client._rest

    await client.fetch_oids(["/1/60/0/9/1/0"])

    assert "/1/60/0/9/1/0" not in client._rest


async def test_eine_adresse_ausserhalb_des_plans_bleibt_draussen(client, monkeypatch):
    client.poll_oids = set()
    _anlage(client, monkeypatch, {"/1/60/0/9/1/0": "101"})

    await client.fetch_oids(["/1/60/0/9/1/0"])

    assert "/1/60/0/9/1/0" not in client._letzte_werte
