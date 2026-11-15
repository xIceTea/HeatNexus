"""Der Abruf, wenn die Anlage ganz oder teilweise nicht antwortet."""

from __future__ import annotations

import logging

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


def _warnungen(caplog) -> list:
    """Warnungen der Integration; asyncio meldet unter Last langsame Tasks."""
    return [
        z
        for z in caplog.records
        if z.levelno >= logging.WARNING and z.name.startswith("custom_components")
    ]


# ---------------------------------------------------------------------------
# Totalausfall: Scheitert jede Lesung, ist der Durchlauf gescheitert
# ---------------------------------------------------------------------------


async def test_scheitert_jede_lesung_scheitert_der_durchlauf(client, monkeypatch):
    client.poll_oids = {"/1/60/0/0/7/0", "/1/60/0/0/8/0"}
    client.poll_class = dict.fromkeys(client.poll_oids, "fast")
    client._letzte_werte = {"/1/60/0/0/7/0": "60"}
    _anlage(client, monkeypatch, {})
    client._letzter_lesefehler = OSError("Verbindung abgelehnt")

    with pytest.raises(OSError, match="Verbindung"):
        await client.fetch_all()

    # Der Zähler der Poll-Klassen bleibt stehen, die Adressen bleiben offen.
    assert client._tick == 0
    assert client._rest == client.poll_oids


async def test_ein_teilausfall_liefert_weiter_daten(client, monkeypatch):
    client.poll_oids = {"/1/60/0/0/7/0", "/1/60/0/0/8/0"}
    client.poll_class = dict.fromkeys(client.poll_oids, "fast")
    _anlage(client, monkeypatch, {"/1/60/0/0/7/0": "61"})

    daten = await client.fetch_all()

    assert daten["oids"]["/1/60/0/0/7/0"] == "61"
    assert client._rest == {"/1/60/0/0/8/0"}


async def test_eine_einzelne_unerreichbare_adresse_schreibt_nur_debug(client, caplog):
    """Je Adresse eine Warnung füllte bei einem Ausfall das Protokoll."""

    async def scheitern(url, semaphore=None):
        raise OSError("Verbindung abgelehnt")

    client._get = scheitern
    with caplog.at_level(logging.DEBUG):
        await client._fetch_oid("/1/60/0/0/7/0")

    assert not _warnungen(caplog)
    assert "Verbindung abgelehnt" in str(client._letzter_lesefehler)


async def test_ein_teilausfall_meldet_sich_einmal(client, monkeypatch, caplog):
    client.poll_oids = {"/1/60/0/0/7/0", "/1/60/0/0/8/0"}
    client.poll_class = dict.fromkeys(client.poll_oids, "fast")
    _anlage(client, monkeypatch, {"/1/60/0/0/7/0": "61"})

    with caplog.at_level(logging.DEBUG):
        await client.fetch_all()
        await client.fetch_all()

    warnungen = _warnungen(caplog)
    assert len(warnungen) == 1
