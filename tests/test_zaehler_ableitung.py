"""Abgeleitete Zähler: Zuwachs heute und seit dem letzten Brennerstart.

Die Anlage führt nur Gesamtstände. Geprüft wird, wann der Bezugspunkt
weiterrückt und wann er stehen bleibt – daran hängt, ob die Zahl stimmt.
"""

from __future__ import annotations

from datetime import date

import pytest

from .conftest import requires_ha
from .test_plattformen import _entitaet

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def sensoren():
    from custom_components.heatnexus import sensor

    return sensor


ZAEHLER = "/1/60/0/2/81/0"
STARTS = "/1/60/0/2/80/0"


def _ableitung(sensoren, werte, **felder):
    entity, koordinator = _entitaet(
        sensoren.WindhagerAbleitungSensor,
        werte,
        oid=ZAEHLER,
        name="Betriebsstunden heute",
        unit="h",
        **felder,
    )
    return entity, koordinator


def _fortschreiben(entity, koordinator, wert, starts=None):
    koordinator.data["oids"][ZAEHLER] = wert
    if starts is not None:
        koordinator.data["oids"][STARTS] = starts
    entity._bezugspunkt_pruefen()


# ---------------------------------------------------------------------------
# Tagesbezug
# ---------------------------------------------------------------------------
def test_der_erste_wert_setzt_den_bezugspunkt(sensoren):
    """Vor dem ersten Abruf gibt es keinen Zuwachs, nur einen Anfang."""
    entity, _ = _ableitung(sensoren, {ZAEHLER: "1200"}, type="zaehler_heute")
    entity._bezugspunkt_pruefen()
    assert entity.native_value == 0
    assert entity._marke == date.today().isoformat()


def test_der_zuwachs_zaehlt_ab_dem_bezugspunkt(sensoren):
    entity, koordinator = _ableitung(sensoren, {ZAEHLER: "1200"}, type="zaehler_heute")
    entity._bezugspunkt_pruefen()
    _fortschreiben(entity, koordinator, "1207.5")
    assert entity.native_value == 7.5


def test_ein_neuer_tag_setzt_den_bezugspunkt_neu(sensoren):
    entity, koordinator = _ableitung(sensoren, {ZAEHLER: "1200"}, type="zaehler_heute")
    entity._bezugspunkt_pruefen()
    _fortschreiben(entity, koordinator, "1210")
    entity._marke = "2020-01-01"
    _fortschreiben(entity, koordinator, "1210")
    assert entity.native_value == 0


def test_ein_kleinerer_stand_gilt_als_neuanfang(sensoren):
    """Tauscht jemand die Steuerung, beginnt ihr Zählwerk von vorn."""
    entity, koordinator = _ableitung(sensoren, {ZAEHLER: "1200"}, type="zaehler_heute")
    entity._bezugspunkt_pruefen()
    _fortschreiben(entity, koordinator, "5")
    assert entity.native_value == 0


def test_ohne_wert_bleibt_die_ableitung_leer(sensoren):
    entity, _ = _ableitung(sensoren, {}, type="zaehler_heute")
    entity._bezugspunkt_pruefen()
    assert entity.native_value is None


# ---------------------------------------------------------------------------
# Brennerstart als Bezugspunkt
# ---------------------------------------------------------------------------
def test_ohne_gelesenen_ausloeser_entsteht_kein_bezugspunkt(sensoren):
    """Erst wenn der Stand der Brennerstarts vorliegt, beginnt die Zählung."""
    entity, _ = _ableitung(sensoren, {ZAEHLER: "1200"}, type="zaehler_start", ausloeser_oid=STARTS)
    entity._bezugspunkt_pruefen()
    assert entity.native_value is None


def test_ein_neuer_brennerstart_setzt_den_bezugspunkt_neu(sensoren):
    entity, koordinator = _ableitung(
        sensoren, {ZAEHLER: "1200", STARTS: "40"}, type="zaehler_start", ausloeser_oid=STARTS
    )
    entity._bezugspunkt_pruefen()
    _fortschreiben(entity, koordinator, "1203", starts="40")
    assert entity.native_value == 3

    _fortschreiben(entity, koordinator, "1203", starts="41")
    assert entity.native_value == 0


def test_der_bezugspunkt_steht_im_zustand(sensoren):
    """Nur so übersteht er einen Neustart von Home Assistant."""
    entity, _ = _ableitung(sensoren, {ZAEHLER: "1200"}, type="zaehler_heute")
    entity._bezugspunkt_pruefen()
    attribute = entity.extra_state_attributes
    assert attribute["basis"] == 1200
    assert attribute["marke"] == date.today().isoformat()
    assert attribute["last_reset"]


# ---------------------------------------------------------------------------
# Was der Client daraus anlegt
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    from custom_components.heatnexus import client as modul

    c = modul.WindhagerHttpClient("192.0.2.10", "geheim")
    c.devices = [
        {
            "id": "SN1-stunden",
            "oid": ZAEHLER,
            "name": "Betriebsstunden",
            "state_class": "total_increasing",
            "unit": "h",
            "device_id": "SN1-3-0",
        },
        {
            "id": "SN1-starts",
            "oid": STARTS,
            "name": "Brennerstarts",
            "state_class": "total_increasing",
            "device_id": "SN1-3-0",
        },
        {"id": "SN1-kessel", "oid": "/1/60/0/0/7/0", "name": "Kesseltemperatur", "unit": "°C"},
    ]
    return c


def test_je_zaehler_entstehen_beide_ableitungen(client):
    """Nur der Bezugszähler selbst bekommt keinen Bezug auf sich."""
    client._abgeleitete_zaehler()
    neue = {d["id"]: d for d in client.devices if str(d.get("type", "")).startswith("zaehler_")}
    assert set(neue) == {"SN1-stunden-heute", "SN1-stunden-start", "SN1-starts-heute"}
    assert neue["SN1-stunden-heute"]["name"] == "Betriebsstunden heute"
    assert neue["SN1-stunden-start"]["name"] == "Betriebsstunden seit Start"
    assert neue["SN1-stunden-start"]["ausloeser_oid"] == STARTS


def test_ableitungen_entstehen_abgeschaltet(client):
    """Sie kosten keinen Abruf, bis jemand sie einschaltet."""
    client._abgeleitete_zaehler()
    client.oids = {ZAEHLER, STARTS}
    client._compute_poll_oids()
    abgeleitet = [d for d in client.devices if str(d.get("type", "")).startswith("zaehler_")]
    assert abgeleitet and all(d["enabled_default"] is False for d in abgeleitet)


def test_eine_ableitung_bremst_ihre_quelle_nicht_aus(client):
    """Teilen sich zwei Deskriptoren eine Adresse, gilt die schnellste Klasse.

    Die Ableitung entsteht abgeschaltet und damit träge; ihre Quelle wird alle
    30 s gelesen und muss das bleiben.
    """
    client.devices = [
        {
            "id": "SN1-phase",
            "oid": "/1/60/0/2/1/0",
            "name": "Betriebsphase",
            "device_id": "SN1-3-0",
        },
        {
            "id": "SN1-phase-betriebsdauer",
            "oid": "/1/60/0/2/1/0",
            "name": "Betriebsdauer",
            "type": "betriebsdauer",
            "enabled_default": False,
            "device_id": "SN1-3-0",
        },
    ]
    client.oids = {"/1/60/0/2/1/0"}
    client._compute_poll_oids()
    assert client.poll_class["/1/60/0/2/1/0"] == "fast"

    # Derselbe Stand aus dem Zwischenspeicher darf nichts anderes ergeben.
    client.restore_discovery({"devices": client.devices, "poll_oids": list(client.poll_oids)})
    assert client.poll_class["/1/60/0/2/1/0"] == "fast"


def test_ein_messwert_bekommt_keine_ableitung(client):
    client._abgeleitete_zaehler()
    assert not any(d["id"].startswith("SN1-kessel-") for d in client.devices)


def test_ohne_startzaehler_gibt_es_nur_den_tageswert(client):
    """An einem Gerät ohne Startzähler fehlt der Bezugspunkt."""
    client.devices = [d for d in client.devices if d["id"] != "SN1-starts"]
    client._abgeleitete_zaehler()
    neue = [d["id"] for d in client.devices if str(d.get("type", "")).startswith("zaehler_")]
    assert neue == ["SN1-stunden-heute"]


# ---------------------------------------------------------------------------
# Andere Aggregate: Der Bezug hängt an der Datenpunktkennung, nicht am Kessel
# ---------------------------------------------------------------------------
@pytest.fixture
def waermepumpe():
    from custom_components.heatnexus import client as modul

    c = modul.WindhagerHttpClient("192.0.2.10", "geheim")
    c.devices = [
        {
            "id": "SN1-heizen",
            "oid": "/1/70/0/52/50/0",
            "name": "Betriebsstunden Heizen",
            "state_class": "total_increasing",
            "unit": "h",
            "device_id": "SN1-70-0",
        },
        {
            "id": "SN1-heizen-tag",
            "oid": "/1/70/0/52/51/0",
            "name": "Betriebsstunden Heizen heute",
            "state_class": "total_increasing",
            "unit": "h",
            "device_id": "SN1-70-0",
        },
        {
            "id": "SN1-starts",
            "oid": "/1/70/0/52/56/0",
            "name": "Anzahl Starts",
            "state_class": "total_increasing",
            "device_id": "SN1-70-0",
        },
    ]
    return c


def test_der_startzaehler_der_waermepumpe_ist_der_bezug(waermepumpe):
    """`52/56` zählt dort die Läufe, nicht `2/80`."""
    waermepumpe._abgeleitete_zaehler()
    neue = {
        d["id"]: d for d in waermepumpe.devices if str(d.get("type", "")).startswith("zaehler_")
    }
    assert neue["SN1-heizen-start"]["ausloeser_oid"] == "/1/70/0/52/56/0"


def test_kein_zweiter_tageswert_neben_dem_der_anlage(waermepumpe):
    """Die Wärmepumpe führt „Betriebsstunden Heizen heute" selbst."""
    waermepumpe._abgeleitete_zaehler()
    neue = {d["id"] for d in waermepumpe.devices if str(d.get("type", "")).startswith("zaehler_")}
    assert "SN1-heizen-heute" not in neue
    assert "SN1-heizen-start" in neue


def test_ein_tageswert_der_anlage_bekommt_keine_ableitung(waermepumpe):
    """Er beginnt ohnehin jeden Tag von vorn."""
    waermepumpe._abgeleitete_zaehler()
    neue = {d["id"] for d in waermepumpe.devices if str(d.get("type", "")).startswith("zaehler_")}
    assert not any(kennung.startswith("SN1-heizen-tag") for kennung in neue)
