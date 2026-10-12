"""Metadaten ohne Antwort: Ein Verbindungsfehler ist keine Auskunft der Anlage."""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

OID = "/1/60/0/2/1/0"
META = {"OID": OID, "value": "3", "unit": "°C", "writeProt": True}


@pytest.fixture
def client():
    from custom_components.heatnexus.client import WindhagerHttpClient

    c = WindhagerHttpClient("192.0.2.10", "geheim")
    c.neuron_by_node = {"60": "0000ABCD1234"}
    c.oids = {OID}
    c.devices = [c._deskriptor(id="SN1-0-2-1-0", oid=OID, name="Kesseltemperatur", fct_type=25)]
    return c


def _antworten(client, monkeypatch, folge: list):
    """Je Anfrage die nächste Antwort aus `folge`: ein Status oder ein Fehler."""
    anfragen: list[str] = []

    async def get(url, semaphore=None):
        anfragen.append(url)
        antwort = folge.pop(0) if len(folge) > 1 else folge[0]
        if isinstance(antwort, Exception):
            raise antwort
        return (META, 200) if antwort == 200 else ({"reason": "x"}, antwort)

    monkeypatch.setattr(client, "_get", get)
    return anfragen


async def test_ein_einzelner_aussetzer_wird_wiederholt(client, monkeypatch):
    _antworten(client, monkeypatch, [OSError("weg"), 200])

    await client._apply_metadata()

    assert [d["type"] for d in client.devices] == ["temperature"]
    assert not client.erkennung_unvollstaendig


async def test_ohne_antwort_bleibt_der_bekannte_deskriptor(client, monkeypatch):
    _antworten(client, monkeypatch, [OSError("weg")])
    bekannt = {**client.devices[0], "type": "temperature", "unit": "°C"}
    client._geraete_waehrend_einlesen = [bekannt]

    await client._apply_metadata()

    assert client.devices == [bekannt]
    assert client.erkennung_unvollstaendig


async def test_ohne_antwort_und_ohne_vorstand_fehlt_der_deskriptor(client, monkeypatch):
    _antworten(client, monkeypatch, [OSError("weg")])

    await client._apply_metadata()

    assert client.devices == []
    assert client._metadaten_luecken == {OID}


async def test_eine_absage_der_anlage_ist_keine_luecke(client, monkeypatch):
    _antworten(client, monkeypatch, [404])

    await client._apply_metadata()

    assert client.devices == []
    assert not client.erkennung_unvollstaendig
