"""Die Strukturprüfung: Ein neues Anlagenteil löst im laufenden Betrieb den Vollabzug aus."""

from __future__ import annotations

import asyncio
import copy
from types import SimpleNamespace

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

STRUKTUR = [
    {
        "nodeId": 60,
        "neuronId": "0000ABCD1234",
        "FE01msg": "PUR 09  OK",
        "functions": [
            {"fctId": 0, "fctType": 25, "name": "Kessel"},
            {"fctId": 1, "fctType": 14, "name": "Heizkreis 1"},
        ],
    }
]


def _mit_funktion(funktion: dict) -> list[dict]:
    struktur = copy.deepcopy(STRUKTUR)
    struktur[0]["functions"].append(funktion)
    return struktur


NEUER_HEIZKREIS = {"fctId": 2, "fctType": 14, "name": "Heizkreis 2"}


@pytest.fixture
def client():
    from custom_components.heatnexus.client import WindhagerHttpClient

    c = WindhagerHttpClient("192.0.2.10", "geheim")
    c.oids = set()
    c.devices = [{"id": "SN1-fe01text", "type": "message_text", "node_id": "60"}]
    c._struktur = c._strukturabdruck(STRUKTUR)
    c.antworten = []
    c.gefragt = []

    async def fetch(url, semaphore=None):
        c.gefragt.append(url)
        antwort = c.antworten.pop(0) if c.antworten else STRUKTUR
        if isinstance(antwort, Exception):
            raise antwort
        return antwort

    async def nichts(*_args, **_kwargs):
        return None

    c.fetch = fetch
    c._fetch_stoerspeicher = nichts
    return c


# ---------------------------------------------------------------------------
# Vergleich im Client
# ---------------------------------------------------------------------------
async def test_bei_gleicher_struktur_bleibt_es_ruhig(client):
    await client._struktur_pruefen()

    assert client.strukturaenderung_abholen() is False


async def test_eine_neue_funktion_wird_einmal_gemeldet(client):
    client.antworten = [_mit_funktion(NEUER_HEIZKREIS)]

    await client._struktur_pruefen()

    assert client.strukturaenderung_abholen() is True
    assert client.strukturaenderung_abholen() is False


async def test_eine_weggefallene_funktion_wird_gemeldet(client):
    weniger = copy.deepcopy(STRUKTUR)
    weniger[0]["functions"].pop()
    client.antworten = [weniger]

    await client._struktur_pruefen()

    assert client.strukturaenderung_abholen() is True


async def test_eine_gesperrte_funktion_zaehlt_nicht(client):
    client.antworten = [_mit_funktion({**NEUER_HEIZKREIS, "lock": True})]

    await client._struktur_pruefen()

    assert client.strukturaenderung_abholen() is False


async def test_eine_unbekannte_funktionsart_zaehlt_nicht(client):
    client.antworten = [_mit_funktion({"fctId": 7, "fctType": 9999, "name": "Unbekannt"})]

    await client._struktur_pruefen()

    assert client.strukturaenderung_abholen() is False


async def test_ein_neuer_knoten_wird_gemeldet(client):
    client.antworten = [[*STRUKTUR, {"nodeId": 15, "functions": []}]]

    await client._struktur_pruefen()

    assert client.strukturaenderung_abholen() is True


@pytest.mark.parametrize(
    "antwort",
    [
        {"code": 504, "reason": "No response from Device"},
        None,
        [],
        OSError("Leitung weg"),
    ],
)
async def test_ein_fehlgeschlagener_strukturabruf_aendert_nichts(client, antwort):
    vorher = list(client._struktur)
    client.antworten = [antwort]

    await client._struktur_pruefen()

    assert client.strukturaenderung_abholen() is False
    assert client._struktur == vorher


async def test_dieselbe_abweichung_wird_nicht_zweimal_gemeldet(client):
    """Bleibt der Vollabzug erfolglos, startet derselbe Aufbau ihn nicht alle Viertelstunde."""
    neu = _mit_funktion(NEUER_HEIZKREIS)
    client.antworten = [neu, neu]

    await client._struktur_pruefen()
    client.strukturaenderung_abholen()
    await client._struktur_pruefen()

    assert client.strukturaenderung_abholen() is False


async def test_vor_der_erkennung_wird_nicht_verglichen(client):
    client.oids = None
    client.antworten = [_mit_funktion(NEUER_HEIZKREIS)]

    await client._struktur_pruefen()

    assert client.gefragt == []
    assert client.strukturaenderung_abholen() is False


async def test_waehrend_eines_einlesens_wird_nicht_verglichen(client):
    client._geraete_waehrend_einlesen = []
    client.antworten = [_mit_funktion(NEUER_HEIZKREIS)]

    await client._struktur_pruefen()

    assert client.gefragt == []
    assert client.strukturaenderung_abholen() is False


# ---------------------------------------------------------------------------
# Wiederhergestellter Stand
# ---------------------------------------------------------------------------
async def test_ein_wiederhergestellter_stand_ist_vergleichbar(client):
    from custom_components.heatnexus.client import WindhagerHttpClient

    neu = WindhagerHttpClient("192.0.2.10", "geheim")
    neu.restore_discovery(client.export_discovery())
    neu.fetch = client.fetch

    await neu._struktur_pruefen()

    assert neu._struktur == client._struktur
    assert neu.strukturaenderung_abholen() is False


async def test_ein_stand_ohne_abdruck_uebernimmt_die_erste_antwort(client):
    from custom_components.heatnexus.client import WindhagerHttpClient

    gespeichert = client.export_discovery()
    del gespeichert["struktur"]
    neu = WindhagerHttpClient("192.0.2.10", "geheim")
    neu.restore_discovery(gespeichert)
    neu.fetch = client.fetch
    client.antworten = [_mit_funktion(NEUER_HEIZKREIS)]

    await neu._struktur_pruefen()

    assert neu.strukturaenderung_abholen() is False
    assert neu._struktur == client._strukturabdruck(_mit_funktion(NEUER_HEIZKREIS))


async def test_ein_gescheiterter_lauf_behaelt_den_abdruck(client, monkeypatch):
    vorher = list(client._struktur)

    async def discover(nur_kern=False):
        client._struktur = ["anders"]
        raise OSError("Leitung weg")

    monkeypatch.setattr(client, "_discover", discover)

    with pytest.raises(OSError):
        await client.async_init()

    assert client._struktur == vorher


async def test_nach_gescheitertem_lauf_meldet_die_pruefung_erneut(client, monkeypatch):
    client.antworten = [_mit_funktion(NEUER_HEIZKREIS)]
    await client._struktur_pruefen()
    assert client.strukturaenderung_abholen() is True

    async def discover(nur_kern=False):
        raise OSError("Leitung weg")

    monkeypatch.setattr(client, "_discover", discover)
    with pytest.raises(OSError):
        await client.async_init(erzwingen=True)

    client.antworten = [_mit_funktion(NEUER_HEIZKREIS)]
    await client._struktur_pruefen()
    assert client.strukturaenderung_abholen() is True


# ---------------------------------------------------------------------------
# Takt
# ---------------------------------------------------------------------------
async def test_die_pruefung_nutzt_die_antwort_der_meldungen(client):
    client.antworten = [_mit_funktion(NEUER_HEIZKREIS)]

    await client.fetch_all()

    assert client.gefragt == ["/1"]
    assert client.strukturaenderung_abholen() is True


async def test_zwischen_den_langsamen_takten_wird_nicht_verglichen(client):
    client._tick = 1
    client.antworten = [_mit_funktion(NEUER_HEIZKREIS)]

    await client.fetch_all()

    assert client.strukturaenderung_abholen() is False


async def test_im_langsamen_takt_wird_verglichen(client):
    client._tick = client._takte()["slow"]
    client.antworten = [_mit_funktion(NEUER_HEIZKREIS)]

    await client.fetch_all()

    assert client.strukturaenderung_abholen() is True


async def test_ohne_meldungssensor_fragt_nur_der_langsame_takt_nach(client):
    client.devices = []

    client._tick = 1
    await client.fetch_all()
    assert client.gefragt == []

    client._tick = client._takte()["slow"]
    await client.fetch_all()
    assert client.gefragt == ["/1"]


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------
def _coordinator(client, empfaenger):
    from custom_components.heatnexus.coordinator import WindhagerDataUpdateCoordinator

    coordinator = WindhagerDataUpdateCoordinator.__new__(WindhagerDataUpdateCoordinator)
    coordinator.client = client
    coordinator.bei_strukturaenderung = empfaenger
    return coordinator


def test_ohne_empfaenger_bleibt_die_meldung_beim_client(client):
    client._struktur_geaendert = True

    _coordinator(client, None)._strukturaenderung_weitergeben()

    assert client._struktur_geaendert is True


def test_der_empfaenger_erhaelt_die_meldung(client):
    aufgerufen: list = []
    client._struktur_geaendert = True

    _coordinator(client, lambda: aufgerufen.append(True))._strukturaenderung_weitergeben()

    assert aufgerufen == [True]
    assert client._struktur_geaendert is False


# ---------------------------------------------------------------------------
# Start des Vollabzugs
# ---------------------------------------------------------------------------
class _Anlage(SimpleNamespace):
    def _replace(self, **felder):
        return _Anlage(**{**vars(self), **felder})


@pytest.fixture
def einlesen(monkeypatch):
    from custom_components.heatnexus import einlesen

    gestartet: list = []

    def starten(hass, entry, anlagen, mem_cache, version):
        gestartet.extend(anlagen)
        return ["aufgabe"]

    monkeypatch.setattr(einlesen, "vollabzuege_starten", starten)
    einlesen.gestartet = gestartet
    return einlesen


def _eintrag(offen: set, hintergrund: list):
    return SimpleNamespace(runtime_data={"einlesen_offen": offen, "hintergrund": hintergrund})


def test_eine_strukturaenderung_startet_den_vollabzug(einlesen):
    offen: set = set()
    hintergrund: list = []
    anlage = _Anlage(host="192.0.2.10", restored=False)

    einlesen._nach_strukturaenderung(None, _eintrag(offen, hintergrund), anlage, {}, "1.0")

    assert [a.restored for a in einlesen.gestartet] == [True]
    assert offen == {"192.0.2.10"}
    assert hintergrund == ["aufgabe"]


def test_ein_laufender_vollabzug_verhindert_einen_zweiten(einlesen):
    anlage = _Anlage(host="192.0.2.10", restored=True)

    einlesen._nach_strukturaenderung(None, _eintrag({"192.0.2.10"}, []), anlage, {}, "1.0")

    assert einlesen.gestartet == []


async def test_eine_laufende_aufgabe_verhindert_einen_zweiten(einlesen):
    anlage = _Anlage(host="192.0.2.10", restored=True)
    sperre = asyncio.Event()
    aufgabe = asyncio.create_task(sperre.wait(), name="heatnexus_vollabzug_192.0.2.10")
    try:
        einlesen._nach_strukturaenderung(None, _eintrag(set(), [aufgabe]), anlage, {}, "1.0")
    finally:
        sperre.set()
        await aufgabe

    assert einlesen.gestartet == []


def test_eine_andere_anlage_startet_trotz_laufendem_vollabzug(einlesen):
    anlage = _Anlage(host="192.0.2.11", restored=True)

    einlesen._nach_strukturaenderung(None, _eintrag({"192.0.2.10"}, []), anlage, {}, "1.0")

    assert [a.host for a in einlesen.gestartet] == ["192.0.2.11"]
