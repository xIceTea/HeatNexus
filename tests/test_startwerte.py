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


def _uhr_deskriptoren():
    return [
        {"name": "Datum", "oid": "/1/15/0/2/70/0", "type": "string_sensor"},
        {"name": "Uhrzeit", "oid": "/1/15/0/2/72/0", "type": "string_sensor"},
    ]


async def test_die_uhr_der_steuerung_wird_zusammengesetzt(client):
    client.devices = _uhr_deskriptoren()
    werte = {"/1/15/0/2/70/0": "18.08.2026", "/1/15/0/2/72/0": "12:30:00"}

    async def lesen(oid):
        return oid, werte[oid]

    client._fetch_oid = lesen

    assert await client._steuerungszeit() == datetime(2026, 8, 18, 12, 30, 0)


async def test_ohne_uhr_gibt_es_keine_bezugszeit(client):
    client.devices = []

    assert await client._steuerungszeit() is None


async def test_eine_unlesbare_uhr_gibt_keine_bezugszeit(client):
    client.devices = _uhr_deskriptoren()

    async def lesen(oid):
        return oid, "kaputt"

    client._fetch_oid = lesen

    assert await client._steuerungszeit() is None


async def test_die_steuerungsuhr_schlaegt_die_serverzeit(client):
    """Zeitstempel und Bezugszeit stammen aus derselben Uhr."""
    client.devices = _uhr_deskriptoren()
    # Die Steuerung geht zwei Stunden vor. Ihr Zeitstempel ist zwei Minuten
    # alt – gegen die Serverzeit sähe er zwei Stunden alt aus.
    steuerung = JETZT + timedelta(hours=2)
    werte = {
        "/1/15/0/2/70/0": steuerung.strftime("%d.%m.%Y"),
        "/1/15/0/2/72/0": steuerung.strftime("%H:%M:%S"),
    }

    async def lesen(oid):
        return oid, werte[oid]

    client._fetch_oid = lesen
    stempel = steuerung - timedelta(minutes=2)
    _speicher(
        client,
        [
            {
                "OID": "/1/60/0/0/7/0",
                "value": "62.4",
                "timestamp": stempel.strftime("%Y-%m-%d %H:%M:%S"),
            }
        ],
    )

    bezug = await client._steuerungszeit()

    assert await client._startwerte_lesen(15, bezug) == 1

    # Gegenprobe gegen die Serverzeit, mit leerem Speicher: Sonst bestünde
    # die Zusicherung, weil die Adresse schon gelesen ist.
    client._letzte_werte.clear()
    assert await client._startwerte_lesen(15, JETZT) == 0
