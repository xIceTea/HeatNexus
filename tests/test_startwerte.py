"""Der kalte Start: Werte aus dem Lesespeicher der Anlage.

Der Speicher hält, was zuletzt gelesen wurde, und füllt sich nicht selbst.
Übernommen wird deshalb nur, was jung genug ist – sonst stünde ein alter
Messwert als aktueller da und liefe so in den Verlauf.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

JETZT = datetime(2026, 8, 18, 12, 0, 0)


@pytest.fixture(scope="module")
def client_module():
    from custom_components.heatnexus import client

    return client


@pytest.fixture
def client(client_module):
    c = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    c.poll_oids = {"/1/60/0/0/7/0", "/1/60/0/0/11/0"}
    return c


def _speicher(client, eintraege):
    """Antwort des Lesespeichers vorgeben."""

    async def antwort(url, semaphore=None):
        return eintraege, 200

    client._get = antwort


def _eintrag(oid, wert, alter_min):
    zeit = JETZT - timedelta(minutes=alter_min)
    return {"OID": oid, "value": wert, "timestamp": zeit.strftime("%Y-%m-%d %H:%M:%S")}


async def test_ein_junger_wert_wird_uebernommen(client):
    _speicher(client, [_eintrag("/1/60/0/0/7/0", "62.4", 3)])

    assert await client._startwerte_lesen(15, JETZT) == 1
    assert client._letzte_werte["/1/60/0/0/7/0"] == "62.4"


async def test_ein_zu_alter_wert_bleibt_liegen(client):
    _speicher(client, [_eintrag("/1/60/0/0/7/0", "62.4", 40)])

    assert await client._startwerte_lesen(15, JETZT) == 0
    assert "/1/60/0/0/7/0" not in client._letzte_werte


async def test_ein_zeitstempel_aus_der_zukunft_wird_abgelehnt(client):
    """Eine vorgehende Uhr macht alte Werte nicht frisch."""
    _speicher(client, [_eintrag("/1/60/0/0/7/0", "62.4", -30)])

    assert await client._startwerte_lesen(15, JETZT) == 0


async def test_ein_unlesbarer_zeitstempel_wird_uebergangen(client):
    _speicher(client, [{"OID": "/1/60/0/0/7/0", "value": "62.4", "timestamp": "gestern"}])

    assert await client._startwerte_lesen(15, JETZT) == 0


async def test_nur_adressen_aus_dem_abrufplan(client):
    _speicher(client, [_eintrag("/1/60/0/9/99/0", "1", 1)])

    assert await client._startwerte_lesen(15, JETZT) == 0


async def test_die_leermarke_wird_zu_none(client):
    """`-.-` heißt: kein Messwert. Eine 0 daraus wäre eine Falschaussage."""
    _speicher(client, [_eintrag("/1/60/0/0/7/0", "-.-", 1)])

    assert await client._startwerte_lesen(15, JETZT) == 1
    assert client._letzte_werte["/1/60/0/0/7/0"] is None


async def test_abgeschaltet_fragt_den_speicher_nicht(client):
    async def darf_nicht(url, semaphore=None):
        raise AssertionError("Der Lesespeicher wurde trotz Abschaltung abgefragt")

    client._get = darf_nicht

    assert await client._startwerte_lesen(0, JETZT) == 0
