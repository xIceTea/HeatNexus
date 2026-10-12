"""Das Zeitfenster eines Abrufdurchlaufs."""

from __future__ import annotations

import time

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
# Zeitfenster: ein Block, der nicht mehr passt, wird nicht begonnen
# ---------------------------------------------------------------------------
@pytest.fixture
def uhr(monkeypatch):
    stand = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: stand[0])
    return stand


async def test_ein_block_wird_nach_der_gemessenen_dauer_bemessen(client, monkeypatch, uhr):
    """Bekannt ist eine Sekunde je Wert; nach zwölf Sekunden passen noch drei."""
    from custom_components.heatnexus.const import POLL_BLOCK

    gelesen: list[str] = []

    async def fetch_oid(oid):
        uhr[0] += 1.0
        gelesen.append(oid)
        return oid, "1"

    monkeypatch.setattr(client, "_fetch_oid", fetch_oid)
    client.poll_oids = {f"/oid/{nummer:02d}" for nummer in range(40)}
    client.poll_class = dict.fromkeys(client.poll_oids, "fast")

    await client.fetch_all(budget=POLL_BLOCK + 3)

    assert len(gelesen) == POLL_BLOCK + 3
    assert uhr[0] <= 1000.0 + POLL_BLOCK + 3


async def test_gelesene_werte_bleiben_auch_bei_abbruch(client, monkeypatch):
    """Bricht der Coordinator den Durchlauf ab, ist das Gelesene schon im Bestand."""
    import asyncio

    from custom_components.heatnexus.const import POLL_BLOCK

    zaehler = [0]

    async def fetch_oid(oid):
        zaehler[0] += 1
        if zaehler[0] > POLL_BLOCK:
            raise asyncio.CancelledError
        return oid, "1"

    monkeypatch.setattr(client, "_fetch_oid", fetch_oid)
    client.poll_oids = {f"/oid/{nummer:02d}" for nummer in range(40)}
    client.poll_class = dict.fromkeys(client.poll_oids, "fast")

    with pytest.raises(asyncio.CancelledError):
        await client.fetch_all()

    assert len(client._letzte_werte) == POLL_BLOCK
    assert len(client._rest) == 40 - POLL_BLOCK
