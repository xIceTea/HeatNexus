"""Eine Menüwurzel ohne Antwort ist eine Lücke, keine Absage."""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

PRAEFIX = "/1/60/0"


@pytest.fixture
def anlage():
    from custom_components.heatnexus import client

    c = client.WindhagerHttpClient("192.0.2.10", "geheim", levels=["info", "operate"])
    c._wurzel_luecken = set()
    return c


def _antwort(c, monkeypatch, status=None, fehler=None):
    async def menue_abruf(url):
        if fehler:
            raise fehler
        return None, status

    monkeypatch.setattr(c, "_menue_abruf", menue_abruf)


@pytest.mark.parametrize("status", [0, 502, 504])
async def test_eine_wurzel_ohne_antwort_bleibt_als_luecke(anlage, monkeypatch, status):
    _antwort(anlage, monkeypatch, status=status)
    assert await anlage._menue_ebenen(PRAEFIX) is None
    assert PRAEFIX in anlage._wurzel_luecken
    assert anlage.erkennung_unvollstaendig


async def test_eine_zeitueberschreitung_ist_ebenfalls_eine_luecke(anlage, monkeypatch):
    _antwort(anlage, monkeypatch, fehler=TimeoutError())
    assert await anlage._menue_ebenen(PRAEFIX) is None
    assert PRAEFIX in anlage._wurzel_luecken


async def test_eine_wurzel_ohne_menueliste_ist_keine_luecke(anlage, monkeypatch):
    _antwort(anlage, monkeypatch, status=404)
    assert await anlage._menue_ebenen(PRAEFIX) is None
    assert not anlage._wurzel_luecken


async def test_eine_gemeldete_funktion_liest_einzeln_weiter(anlage, monkeypatch):
    _antwort(anlage, monkeypatch, status=504)
    assert await anlage._read_function_menus(PRAEFIX, 9) == {}
    assert not anlage._wurzel_luecken


def test_die_bekannten_beschreibungen_des_teils_bleiben(anlage):
    kennung = anlage._geraetekennung(PRAEFIX)
    bekannt = [
        {"id": "a", "oid": f"{PRAEFIX}/0/7/0", "device_id": kennung},
        {"id": "b", "type": "sensor", "device_id": kennung},
        {"id": "c", "oid": "/1/60/1/0/7/0", "device_id": "anderes"},
    ]
    anlage._geraete_waehrend_einlesen = bekannt
    anlage._wurzel_luecken = {PRAEFIX}
    anlage.devices, anlage.oids = [], set()
    anlage._wurzel_luecken_ueberbruecken()
    assert {d["id"] for d in anlage.devices} == {"a", "b"}
    assert anlage.oids == {f"{PRAEFIX}/0/7/0"}
