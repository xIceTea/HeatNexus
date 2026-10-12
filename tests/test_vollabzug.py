"""Der Vollabzug: Ein gescheiterter Lauf lässt den bekannten Stand stehen."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

KERN = [{"id": "SN1-0-0-7-0", "oid": "/1/60/0/0/7/0", "type": "temperature"}]


@pytest.fixture
def client():
    from custom_components.heatnexus.client import WindhagerHttpClient

    c = WindhagerHttpClient("192.0.2.10", "geheim")
    c.devices = list(KERN)
    c.oids = {"/1/60/0/0/7/0"}
    c.poll_oids = {"/1/60/0/0/7/0"}
    return c


async def test_ein_abgebrochener_lauf_stellt_den_stand_wieder_her(client, monkeypatch):
    async def discover(nur_kern=False):
        client.devices = [{"id": "halb", "oid": "/1/60/0/2/1/0"}]
        client.oids = {"/1/60/0/2/1/0"}
        raise OSError("Leitung weg")

    monkeypatch.setattr(client, "_discover", discover)

    with pytest.raises(OSError):
        await client.async_init()

    assert client.devices == KERN
    assert client.oids == {"/1/60/0/0/7/0"}
    assert client._vollstaendig is False


async def test_waehrend_des_laufs_liefert_der_abruf_den_bekannten_stand(client, monkeypatch):
    gesehen: list = []

    async def discover(nur_kern=False):
        client.devices = []
        gesehen.append(await client.fetch_all())

    async def nichts():
        return None

    monkeypatch.setattr(client, "_discover", discover)
    monkeypatch.setattr(client, "_apply_metadata", nichts)
    monkeypatch.setattr(client, "_fetch_oid", _wert)

    await client.async_init()

    assert gesehen[0]["devices"] == KERN


async def _wert(oid):
    return oid, "1"


# ---------------------------------------------------------------------------
# Wiederholung und Meldung
# ---------------------------------------------------------------------------
class _Client:
    def __init__(self, fehler: list):
        self.fehler = fehler
        self.laeufe = 0
        self.erkennung_unvollstaendig = False

    async def async_init(self, erzwingen=False):
        self.laeufe += 1
        if self.fehler:
            raise self.fehler.pop(0)


@pytest.fixture
def ohne_pause(monkeypatch):
    from custom_components.heatnexus import einlesen

    monkeypatch.setattr(einlesen, "VOLLABZUG_PAUSEN", (0, 0))
    return einlesen


async def test_ein_gescheiterter_lauf_wird_wiederholt(ohne_pause):
    client = _Client([OSError("weg")])

    ergebnis = await ohne_pause._einlesen_mit_wiederholung(client, "192.0.2.10", False)
    assert ergebnis == ohne_pause.EINLESEN_VOLL
    assert client.laeufe == 2


async def test_nach_dem_letzten_versuch_gibt_er_auf(ohne_pause):
    client = _Client([OSError("weg")] * 5)

    ergebnis = await ohne_pause._einlesen_mit_wiederholung(client, "192.0.2.10", False)
    assert ergebnis == ohne_pause.EINLESEN_FEHLER
    assert client.laeufe == 3


async def test_ein_unvollstaendiger_lauf_wird_wiederholt(ohne_pause):
    client = _Client([])
    client.erkennung_unvollstaendig = True

    ergebnis = await ohne_pause._einlesen_mit_wiederholung(client, "192.0.2.10", False)
    assert ergebnis == ohne_pause.EINLESEN_LUECKEN
    assert client.laeufe == 3


def test_ohne_vollstaendigen_lauf_keine_fertigmeldung(ohne_pause, monkeypatch):
    erstellt: list = []
    entfernt: list = []
    monkeypatch.setattr(
        ohne_pause.persistent_notification, "async_create", lambda *a, **k: erstellt.append(a)
    )
    monkeypatch.setattr(
        ohne_pause.persistent_notification, "async_dismiss", lambda *a, **k: entfernt.append(a)
    )
    eintrag = SimpleNamespace(
        entry_id="e1",
        title="Heizhaus",
        options={"meldung_einlesen": True},
        runtime_data={"einlesen_offen": {"192.0.2.10"}},
    )

    ohne_pause._einlesen_abgeschlossen(None, eintrag, "192.0.2.10", erfolgreich=False)

    assert not erstellt
    assert entfernt
