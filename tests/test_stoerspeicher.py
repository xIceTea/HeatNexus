"""Störspeicher des Bediengeräts: Regeln je Eintrag, Abruf, Aktionen, Sensor.

Die Regeln folgen der Oberfläche des Bediengeräts: Zurücksetzen nur bei
anliegender Störung des eigenen Kessels, Quittieren nur bei neuem Eintrag,
Löschen nur, wenn nichts mehr anliegt.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from .conftest import requires_ha
from .test_plattformen import FakeClient, FakeCoordinator

pytestmark = requires_ha()

JETZT = datetime(2026, 10, 14, 21, 33, 30)
PARTNER = {"peerId": 60, "subnet": 1}


def _roh(**felder) -> dict:
    grund = {
        "FE01Msg": "PUR 09E346",
        "active": True,
        "code": 346,
        "id": 154,
        "lastRxTime": "2026-10-14 21:33:25",
        "nodeId": 60,
        "nodeName": "PuroWIN",
        "status": "new",
        "subnet": 1,
        "symbol": "E",
        "timestamp": "2026-10-14 21:33:00",
    }
    grund.update(felder)
    return grund


@pytest.fixture(scope="module")
def speicher():
    from custom_components.heatnexus.client import stoerspeicher

    return stoerspeicher


# ---------------------------------------------------------------------------
# Regeln je Eintrag
# ---------------------------------------------------------------------------
def test_anliegende_stoerung_des_eigenen_kessels_ist_zuruecksetzbar(speicher):
    eintrag = speicher.eintrag_aufbereiten(_roh(), PARTNER, JETZT)
    assert eintrag["aktiv"] and eintrag["zuruecksetzbar"] and eintrag["quittierbar"]
    assert not eintrag["loeschbar"]


def test_kessel_eines_anderen_bediengeraets_ist_nicht_zuruecksetzbar(speicher):
    eintrag = speicher.eintrag_aufbereiten(_roh(nodeId=61), PARTNER, JETZT)
    assert eintrag["aktiv"] and not eintrag["zuruecksetzbar"]


def test_ohne_kopplung_bleiben_andere_module_bearbeitbar(speicher):
    eintrag = speicher.eintrag_aufbereiten(_roh(nodeId=90, FE01Msg="MB1 00A187"), None, JETZT)
    assert eintrag["zuruecksetzbar"]


def test_eintrag_ohne_neue_meldung_gilt_nach_sieben_minuten_als_erledigt(speicher):
    alt = (JETZT - timedelta(minutes=8)).strftime("%Y-%m-%d %H:%M:%S")
    eintrag = speicher.eintrag_aufbereiten(_roh(lastRxTime=alt), PARTNER, JETZT)
    assert not eintrag["aktiv"] and eintrag["loeschbar"] and not eintrag["zuruecksetzbar"]


def test_quittierter_eintrag_ist_nicht_erneut_quittierbar(speicher):
    eintrag = speicher.eintrag_aufbereiten(_roh(status="receipted"), PARTNER, JETZT)
    assert not eintrag["quittierbar"]


def test_eintrag_ist_erledigt_sobald_das_geraet_ok_meldet(speicher):
    eintrag = speicher.eintrag_aufbereiten(_roh(), PARTNER, JETZT, "PUR 09  OK")
    assert not eintrag["aktiv"] and eintrag["loeschbar"]


def test_eintrag_liegt_an_solange_das_geraet_seinen_code_meldet(speicher):
    alt = (JETZT - timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
    eintrag = speicher.eintrag_aufbereiten(_roh(lastRxTime=alt), PARTNER, JETZT, "PUR 09E346")
    assert eintrag["aktiv"] and not eintrag["loeschbar"]


def test_eintrag_ohne_kennung_faellt_weg(speicher):
    assert speicher.eintrag_aufbereiten({"nodeId": 60}, PARTNER, JETZT) is None


# ---------------------------------------------------------------------------
# Abruf
# ---------------------------------------------------------------------------
def _client(antworten):
    from custom_components.heatnexus.client import WindhagerHttpClient

    client = WindhagerHttpClient("192.0.2.10", "geheim")
    gefragt = []

    async def _get(url, semaphore=None):
        gefragt.append(url)
        for teil, antwort in antworten.items():
            if url.endswith(teil):
                return antwort
        return None, 404

    client._get = _get
    return client, gefragt


def test_abruf_liest_eintraege_und_kopplung(speicher):
    client, gefragt = _client(
        {
            "/fehlerlog": ([_roh(id=153, active=False), _roh()], 200),
            "/heartbeat": (PARTNER, 200),
        }
    )
    eintraege = asyncio.run(client._fetch_stoerspeicher())
    assert client.stoerspeicher_vorhanden is True
    assert [e["id"] for e in eintraege] == [154, 153]
    assert any(url.endswith("/heartbeat") for url in gefragt)


def test_ohne_stoerspeicher_fragt_der_abruf_erst_spaeter_wieder(speicher):
    client, gefragt = _client({"/fehlerlog": (None, 503)})
    assert asyncio.run(client._fetch_stoerspeicher()) is None
    assert client.stoerspeicher_vorhanden is False
    for _ in range(5):
        asyncio.run(client._fetch_stoerspeicher())
    assert len(gefragt) == 1


def test_fehlschlag_laesst_den_letzten_stand_stehen(speicher):
    client, _ = _client({"/fehlerlog": ([_roh()], 200), "/heartbeat": (PARTNER, 200)})
    erster = asyncio.run(client._fetch_stoerspeicher())

    async def _kaputt(url, semaphore=None):
        raise TimeoutError

    client._get = _kaputt
    assert asyncio.run(client._fetch_stoerspeicher()) == erster


def test_aussetzer_nach_erster_antwort_schaltet_den_stoerspeicher_nicht_ab(speicher):
    client, _ = _client({"/fehlerlog": ([_roh()], 200), "/heartbeat": (PARTNER, 200)})
    erster = asyncio.run(client._fetch_stoerspeicher())
    client._get = _client({"/fehlerlog": (None, 503)})[0]._get
    assert asyncio.run(client._fetch_stoerspeicher()) == erster
    assert client.stoerspeicher_vorhanden is True


def test_nachlesen_koppelt_die_eintraege_an_die_geraetemeldung(speicher):
    client, _ = _client({"/fehlerlog": ([_roh()], 200), "/heartbeat": (PARTNER, 200)})

    async def _status():
        return {"60": "PUR 09  OK"}

    client._fetch_status = _status
    status, eintraege = asyncio.run(client.meldungsliste_nachlesen())
    assert status == {"60": "PUR 09  OK"}
    assert eintraege[0]["aktiv"] is False


def test_kopplung_ohne_antwort_wird_nicht_bei_jedem_abruf_erneut_gefragt(speicher):
    client, gefragt = _client({"/fehlerlog": ([_roh()], 200)})
    for _ in range(3):
        asyncio.run(client._fetch_stoerspeicher())
    assert sum(url.endswith("/heartbeat") for url in gefragt) == 1


# ---------------------------------------------------------------------------
# Aktionen an der Steuerung
# ---------------------------------------------------------------------------
class _Antwort:
    def __init__(self, status):
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def text(self):
        return "abgelehnt"


class _Sitzung:
    def __init__(self, status=200):
        self.anfragen = []
        self.status = status

    def request(self, methode, url, data=None):
        self.anfragen.append((methode, url.split("/fehlerlog", 1)[1]))
        return _Antwort(self.status)


def _schreibclient(status=200):
    from custom_components.heatnexus.client import WindhagerHttpClient

    client = WindhagerHttpClient("192.0.2.10", "geheim")
    client._session = _Sitzung(status)

    async def _bereit():
        return None

    client._ensure_session = _bereit
    return client


def test_zuruecksetzen_folgt_der_taste_am_bediengeraet():
    client = _schreibclient()
    asyncio.run(client.stoerung_zuruecksetzen(154))
    assert client._session.anfragen == [("PUT", "/reset/154"), ("PUT", "/154?status=receipted")]


def test_quittieren_und_loeschen_aendern_nur_die_liste():
    client = _schreibclient()
    asyncio.run(client.stoerung_quittieren(155))
    asyncio.run(client.stoerung_loeschen(155))
    assert client._session.anfragen == [("PUT", "/155?status=receipted"), ("DELETE", "/155")]


def test_abgelehnte_aktion_meldet_einen_fehler():
    from custom_components.heatnexus.exceptions import WindhagerWriteError

    client = _schreibclient(status=404)
    with pytest.raises(WindhagerWriteError):
        asyncio.run(client.stoerung_loeschen(1))


def test_zuruecksetzen_gilt_auch_wenn_das_quittieren_danach_scheitert():
    client = _schreibclient()
    sitzung = client._session

    def _nur_reset(methode, url, data=None):
        sitzung.anfragen.append((methode, url.split("/fehlerlog", 1)[1]))
        return _Antwort(200 if "/reset/" in url else 502)

    sitzung.request = _nur_reset
    asyncio.run(client.stoerung_zuruecksetzen(154))
    assert sitzung.anfragen[0] == ("PUT", "/reset/154")


# ---------------------------------------------------------------------------
# Sensor
# ---------------------------------------------------------------------------
class _Client(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.aktionen: list[tuple[str, int]] = []
        self.sprache = "de"
        self.devices: list[dict] = []

    async def stoerung_quittieren(self, kennung):
        self.aktionen.append(("quittieren", kennung))

    async def stoerung_zuruecksetzen(self, kennung):
        self.aktionen.append(("zuruecksetzen", kennung))

    async def stoerung_loeschen(self, kennung):
        self.aktionen.append(("loeschen", kennung))


def _koordinator(speicher, *roh, zuruecksetzen=False):
    koordinator = FakeCoordinator()
    koordinator.client = _Client()
    koordinator.last_update_success = True
    koordinator.config_entry = SimpleNamespace(
        options={"stoerung_zuruecksetzen": zuruecksetzen}, entry_id="e1"
    )
    koordinator.data["stoerspeicher"] = [
        speicher.eintrag_aufbereiten(r, PARTNER, datetime.now()) for r in roh
    ]
    return koordinator


def _sensor(koordinator):
    from custom_components.heatnexus.sensor.stoerspeicher import StoerspeicherSensor

    return StoerspeicherSensor(koordinator)


def _jetzt(**felder):
    zeit = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return _roh(lastRxTime=zeit, **felder)


def test_sensor_zeigt_klartext_und_zahl_der_eintraege(speicher):
    sensor = _sensor(_koordinator(speicher, _jetzt(), _roh(id=153, active=False)))
    assert sensor.native_value == 2
    eintraege = sensor.extra_state_attributes["eintraege"]
    assert eintraege[0]["text"] == "Verkleidungstür offen"
    assert eintraege[0]["zuerst"].startswith("2026-10-14T21:33:00")


def test_ohne_option_bietet_der_sensor_kein_zuruecksetzen_an(speicher):
    from custom_components.heatnexus.exceptions import WindhagerValueError

    koordinator = _koordinator(speicher, _jetzt())
    sensor = _sensor(koordinator)
    assert sensor.extra_state_attributes["eintraege"][0]["zuruecksetzbar"] is False
    with pytest.raises(WindhagerValueError):
        asyncio.run(sensor.async_zuruecksetzen(154))
    assert koordinator.client.aktionen == []


def test_mit_option_setzt_der_sensor_zurueck(speicher):
    koordinator = _koordinator(speicher, _jetzt(), zuruecksetzen=True)
    asyncio.run(_sensor(koordinator).async_zuruecksetzen(154))
    assert koordinator.client.aktionen == [("zuruecksetzen", 154)]


def test_nach_einer_aktion_liest_der_sensor_die_liste_sofort_nach(speicher):
    koordinator = _koordinator(speicher, _jetzt())
    asyncio.run(_sensor(koordinator).async_quittieren(154))
    assert koordinator.nachgefasst == [["meldungsliste"]]


def test_anliegende_stoerung_laesst_sich_nicht_loeschen(speicher):
    from custom_components.heatnexus.exceptions import WindhagerValueError

    koordinator = _koordinator(speicher, _jetzt())
    with pytest.raises(WindhagerValueError):
        asyncio.run(_sensor(koordinator).async_loeschen(154))


def test_unbekannter_eintrag_wird_gemeldet(speicher):
    from custom_components.heatnexus.exceptions import WindhagerValueError

    with pytest.raises(WindhagerValueError):
        asyncio.run(_sensor(_koordinator(speicher, _jetzt())).async_quittieren(999))


def test_meldungsliste_spiegelt_die_eintraege_ihres_geraets(speicher):
    from custom_components.heatnexus.sensor import WindhagerMessageListSensor

    from .test_plattformen import _beschreibung

    koordinator = _koordinator(speicher, _jetzt(), _roh(id=7, nodeId=90, FE01Msg="MB1 00A187"))
    liste = WindhagerMessageListSensor(
        koordinator, _beschreibung(type="message_list", node_id="60", oid=None)
    )
    assert liste.native_value == 1
    attribute = liste.extra_state_attributes
    assert attribute["eigene_liste"] is False
    assert attribute["meldungen"][0]["code"] == 346


def test_steuerung_mit_eigener_entitaet_bleibt_gruppe():
    from custom_components.heatnexus.dashboard.anlagen import _gruppieren

    def teil(kennung, anlage, entitaeten):
        return {
            "id": kennung,
            "anlage_id": anlage,
            "name": kennung,
            "eintrag": "e1",
            "kennung": kennung,
            "rang": 0,
            "entitaeten": entitaeten,
        }

    teile = {
        "st": teil("st", "heizung", [{"entity_id": "sensor.st_stoerspeicher", "name": "S"}]),
        "kessel": teil("kessel", "st", [{"entity_id": "sensor.k", "name": "K"}]),
    }
    anlagen = _gruppieren(teile)
    assert [a["id"] for a in anlagen] == ["st"]
    assert [t["id"] for t in anlagen[0]["teile"]] == ["kessel"]
    assert anlagen[0]["steuerung_entitaeten"][0]["entity_id"] == "sensor.st_stoerspeicher"
