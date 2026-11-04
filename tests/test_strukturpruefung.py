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


async def _zweimal_pruefen(client, antwort: list[dict]) -> None:
    """Dieselbe Abweichung in zwei langsamen Takten: Erst das zählt als Änderung."""
    client.antworten = [antwort, antwort]
    await client._struktur_pruefen()
    await client._struktur_pruefen()


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
    c._systemzeit_lesen = nichts
    return c


# ---------------------------------------------------------------------------
# Vergleich im Client
# ---------------------------------------------------------------------------
async def test_bei_gleicher_struktur_bleibt_es_ruhig(client):
    await client._struktur_pruefen()

    assert client.strukturaenderung_abholen() is False


async def test_eine_neue_funktion_wird_einmal_gemeldet(client):
    await _zweimal_pruefen(client, _mit_funktion(NEUER_HEIZKREIS))

    assert client.strukturaenderung_abholen() is True
    assert client.strukturaenderung_abholen() is False


async def test_eine_weggefallene_funktion_wird_gemeldet(client):
    weniger = copy.deepcopy(STRUKTUR)
    weniger[0]["functions"].pop()
    await _zweimal_pruefen(client, weniger)

    assert client.strukturaenderung_abholen() is True


async def test_ein_kurzer_aussetzer_bleibt_ohne_meldung(client):
    """Ein Busteilnehmer fehlt für einen Takt; ein Vollabzug wäre umsonst."""
    weniger = copy.deepcopy(STRUKTUR)
    weniger[0]["functions"].pop()
    client.antworten = [weniger, STRUKTUR, weniger]

    for _ in range(3):
        await client._struktur_pruefen()

    assert client.strukturaenderung_abholen() is False


async def test_erst_die_gleiche_abweichung_zaehlt(client):
    client.antworten = [_mit_funktion(NEUER_HEIZKREIS), _mit_funktion({"fctId": 3, "fctType": 14})]

    await client._struktur_pruefen()
    await client._struktur_pruefen()

    assert client.strukturaenderung_abholen() is False


async def test_eine_gesperrte_funktion_zaehlt_nicht(client):
    client.antworten = [_mit_funktion({**NEUER_HEIZKREIS, "lock": True})]

    await client._struktur_pruefen()

    assert client.strukturaenderung_abholen() is False


async def test_eine_unbekannte_funktionsart_zaehlt_nicht(client):
    client.antworten = [_mit_funktion({"fctId": 7, "fctType": 9999, "name": "Unbekannt"})]

    await client._struktur_pruefen()

    assert client.strukturaenderung_abholen() is False


async def test_ein_neuer_knoten_wird_gemeldet(client):
    await _zweimal_pruefen(client, [*STRUKTUR, {"nodeId": 15, "functions": []}])

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

    await _zweimal_pruefen(client, neu)
    client.strukturaenderung_abholen()
    await _zweimal_pruefen(client, neu)

    assert client.strukturaenderung_abholen() is False


async def test_eine_zurueckgestellte_meldung_kommt_im_naechsten_takt(client):
    """Lief gerade ein Einlesen, ging die Meldung ins Leere; die Abweichung gilt weiter."""
    neu = _mit_funktion(NEUER_HEIZKREIS)
    await _zweimal_pruefen(client, neu)
    client.strukturaenderung_abholen()

    client.strukturaenderung_zurueckstellen()
    client.antworten = [neu]
    await client._struktur_pruefen()

    assert client.strukturaenderung_abholen() is True


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


async def _takte_bis_zur_meldung(client, neu: list[dict]) -> int:
    for takt in range(1, 40):
        client.antworten = [neu]
        await client._struktur_pruefen()
        if client.strukturaenderung_abholen():
            return takt
    raise AssertionError("Keine Meldung")


async def test_nach_gescheitertem_lauf_meldet_die_pruefung_mit_wachsender_pause(
    client, monkeypatch
):
    from custom_components.heatnexus.const import STRUKTUR_WARTETAKTE_MAX

    neu = _mit_funktion(NEUER_HEIZKREIS)
    await _zweimal_pruefen(client, neu)
    assert client.strukturaenderung_abholen() is True

    async def discover(nur_kern=False):
        raise OSError("Leitung weg")

    monkeypatch.setattr(client, "_discover", discover)
    pausen = []
    for _ in range(7):
        with pytest.raises(OSError):
            await client.async_init(erzwingen=True)
        pausen.append(await _takte_bis_zur_meldung(client, neu) - 1)

    assert pausen == [1, 2, 4, 8, 16, 16, 16]
    assert max(pausen) == STRUKTUR_WARTETAKTE_MAX


async def test_eine_gelungene_aenderung_setzt_die_pause_zurueck(client, monkeypatch):
    neu = _mit_funktion(NEUER_HEIZKREIS)
    client._strukturlauf_gescheitert()
    client._strukturlauf_gescheitert()

    client._struktur = client._strukturabdruck(neu)
    client.antworten = [neu]
    await client._struktur_pruefen()

    assert (client._struktur_pause, client._struktur_wartetakte) == (0, 0)


def _viele(praefix: str, anzahl: int = 40) -> list[str]:
    return [f"{praefix}/3/{nummer}/0" for nummer in range(anzahl)]


def test_der_magerschutz_nimmt_nur_entfallene_funktionen_heraus(client):
    """Ein Kessel, den `/1` nie nennt, zählt weiter: Fehlt er, ist der Lauf zu mager."""
    alt = client._strukturabdruck(STRUKTUR)
    gesucht, kreis = _viele("/1/60/9"), _viele("/1/60/1", 5)
    client._struktur = client._strukturabdruck(
        [{**STRUKTUR[0], "functions": STRUKTUR[0]["functions"][:1]}]
    )
    client.oids = set(kreis[:0])

    assert client._noch_vorhanden([*gesucht, *kreis], alt) == gesucht
    assert client._erkennung_zu_mager({"oids": [*gesucht, *kreis], "struktur": alt}) is True


def test_mit_einem_knoten_entfallen_auch_seine_gesuchten_funktionen(client):
    alt = [*client._strukturabdruck(STRUKTUR), "15"]
    client._struktur = client._strukturabdruck(STRUKTUR)
    bleibt = _viele("/1/60/0", 2)

    assert client._noch_vorhanden([*bleibt, *_viele("/1/15/9", 2)], alt) == bleibt


# ---------------------------------------------------------------------------
# Takt
# ---------------------------------------------------------------------------
async def test_die_pruefung_nutzt_die_antwort_der_meldungen(client):
    client.antworten = [_mit_funktion(NEUER_HEIZKREIS)]
    await client._struktur_pruefen()
    client.gefragt.clear()
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

    assert client._struktur_kandidat == client._strukturabdruck(_mit_funktion(NEUER_HEIZKREIS))


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
    def __init__(self, **felder):
        zurueckgestellt: list = []
        super().__init__(
            client=SimpleNamespace(
                zurueckgestellt=zurueckgestellt,
                strukturaenderung_zurueckstellen=lambda: zurueckgestellt.append(True),
            ),
            **felder,
        )

    def _replace(self, **felder):
        return _Anlage(**{k: v for k, v in {**vars(self), **felder}.items() if k != "client"})


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
    assert anlage.client.zurueckgestellt == [True]


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
    assert anlage.client.zurueckgestellt == [True]


def test_eine_andere_anlage_startet_trotz_laufendem_vollabzug(einlesen):
    anlage = _Anlage(host="192.0.2.11", restored=True)

    einlesen._nach_strukturaenderung(None, _eintrag({"192.0.2.10"}, []), anlage, {}, "1.0")

    assert [a.host for a in einlesen.gestartet] == ["192.0.2.11"]
