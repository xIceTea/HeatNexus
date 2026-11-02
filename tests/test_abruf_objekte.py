"""Zeitprogramme und Textobjekte im Abruf."""

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
# Zeitprogramme: Ein Verbindungsfehler ist keine Auskunft der Anlage
# ---------------------------------------------------------------------------
def _programme(client, monkeypatch, antwort):
    client.time_programs = [
        {"oid": "/1/60/0/3/61/0", "type": "time_program"},
        {"oid": "/1/60/0/3/62/0", "type": "time_program"},
    ]
    client.devices = list(client.time_programs)

    async def fetch_object(oid):
        return antwort(oid)

    monkeypatch.setattr(client, "fetch_object", fetch_object)


BLOECKE = [{"weekdays": ["Mo"], "switchPoints": []}]


async def test_ohne_verbindung_bleiben_die_zeitprogramme(client, monkeypatch):
    _programme(client, monkeypatch, lambda _oid: (None, 0))

    assert await client._fetch_time_programs() == {}

    assert client._objects_supported is None
    assert len(client.devices) == 2
    assert len(client.time_programs) == 2


async def test_ohne_endpunkt_entfallen_die_zeitprogramme(client, monkeypatch):
    _programme(client, monkeypatch, lambda _oid: ({"reason": "unknown endpoint"}, 404))

    await client._fetch_time_programs()

    assert client._objects_supported is False
    assert client.devices == []


async def test_ein_teilausfall_behaelt_den_vorigen_stand(client, monkeypatch):
    _programme(
        client,
        monkeypatch,
        lambda oid: ({"value": BLOECKE}, 200) if oid.endswith("61/0") else (None, 0),
    )
    client._letzte_objekte = {"/1/60/0/3/62/0": BLOECKE}

    objekte = await client._fetch_time_programs()

    assert set(objekte) == {"/1/60/0/3/61/0", "/1/60/0/3/62/0"}


# ---------------------------------------------------------------------------
# object-Endpunkt: Eine Absage entscheidet erst nach einem vollen Durchlauf
# ---------------------------------------------------------------------------
def _stapelweise(client, monkeypatch, antwort):
    """Sechs Zeitprogramme, je Aufruf mit knappem Fenster genau ein Stapel."""
    import asyncio

    client.time_programs = [
        {"oid": f"/1/60/0/3/{60 + n}/0", "type": "time_program"} for n in range(6)
    ]
    client.devices = list(client.time_programs)

    async def fetch_object(oid):
        await asyncio.sleep(0.05)
        return antwort(oid)

    monkeypatch.setattr(client, "fetch_object", fetch_object)


async def _ein_stapel(client):
    import time

    await client._fetch_time_programs(time.monotonic() + 0.01)


async def test_absage_im_ersten_stapel_entscheidet_noch_nicht(client, monkeypatch):
    erster = {f"/1/60/0/3/{60 + n}/0" for n in range(3)}
    _stapelweise(
        client,
        monkeypatch,
        lambda oid: ({"reason": "gesperrt"}, 404) if oid in erster else ({"value": BLOECKE}, 200),
    )

    await _ein_stapel(client)

    assert client._objects_supported is None
    assert len(client.time_programs) == 6
    assert len(client.devices) == 6

    await _ein_stapel(client)

    assert client._objects_supported is True
    assert len(client.time_programs) == 6


async def test_absage_in_allen_stapeln_entscheidet_nach_dem_durchlauf(client, monkeypatch):
    _stapelweise(client, monkeypatch, lambda _oid: ({"reason": "unknown endpoint"}, 404))

    await _ein_stapel(client)

    assert client._objects_supported is None

    await _ein_stapel(client)

    assert client._objects_supported is False
    assert client.devices == []
