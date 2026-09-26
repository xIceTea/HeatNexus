"""Heizkreise der Baureihe Infinity PLUS (fctType 1).

Sie führen dieselben Klima-Adressen wie ein Heizkreis UML/UMLZ und bekommen
deshalb ebenfalls ein Thermostat.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

KNOTEN = 15
SERIE = "0000INFINI01"
PRAEFIXE = ("/1/15/0", "/1/15/1")
KLIMA_ENDUNGEN = ("/0/1/0", "/1/1/0", "/3/50/0", "/2/10/0", "/3/58/0")


async def _keine_geraetetexte():
    from custom_components.heatnexus import geraetetexte

    return geraetetexte.Texte()


async def _erkennen(monkeypatch):
    from custom_components.heatnexus import client

    c = client.WindhagerHttpClient("192.0.2.10", "geheim", levels=["info", "operate"])
    c.geraeteinfo = {"device": "MB66xx", "version": "1.0"}
    c.werksbezeichnung = {str(KNOTEN): "InfinityPlusWall"}

    async def fetch(url, semaphore=None):
        return [
            {
                "nodeId": KNOTEN,
                "neuronId": SERIE,
                "name": "Heizkreise",
                "functions": [
                    {"fctId": 0, "fctType": 1, "lock": False, "name": "Heizkreis 1"},
                    {"fctId": 1, "fctType": 1, "lock": False, "name": "Heizkreis 2"},
                ],
            }
        ]

    async def read_function_menus(prefix, fct_type):
        return {}

    async def statische_adressen():
        return set()

    monkeypatch.setattr(c, "fetch", fetch)
    monkeypatch.setattr(c, "_read_function_menus", read_function_menus)
    monkeypatch.setattr(c, "_statische_adressen", statische_adressen)
    monkeypatch.setattr(c, "_lade_geraetetexte", _keine_geraetetexte)
    await c._discover()
    return c


async def test_jeder_infinity_heizkreis_bekommt_ein_thermostat(monkeypatch):
    c = await _erkennen(monkeypatch)
    thermostate = {d["prefix"]: d for d in c.devices if d["type"] == "climate"}
    assert set(thermostate) == set(PRAEFIXE)
    assert thermostate["/1/15/0"]["id"] == f"{SERIE}-0-thermostat"
    assert thermostate["/1/15/1"]["id"] == f"{SERIE}-1-thermostat"
    assert {d["fct_type"] for d in thermostate.values()} == {1}


async def test_die_klima_adressen_der_infinity_heizkreise_stehen_im_abruf(monkeypatch):
    c = await _erkennen(monkeypatch)
    c._compute_poll_oids()
    erwartet = {f"{p}{e}" for p in PRAEFIXE for e in KLIMA_ENDUNGEN}
    assert erwartet <= c.poll_oids


@pytest.fixture
def thermostat():
    from custom_components.heatnexus import climate

    from .test_plattformen import _entitaet

    def bauen(werte):
        entitaet, _ = _entitaet(
            climate.WindhagerThermostatClimate,
            werte,
            type="climate",
            prefix="/1/15/0",
            id=f"{SERIE}-0-thermostat",
        )
        return entitaet

    return bauen


@pytest.mark.parametrize("roh", ["-.-", None])
def test_ohne_raumfuehler_bleibt_die_isttemperatur_leer(thermostat, roh):
    werte = {"/1/15/0/1/1/0": "20.0", "/1/15/0/3/50/0": "1"}
    if roh is not None:
        werte["/1/15/0/0/1/0"] = roh
    entitaet = thermostat(werte)
    assert entitaet.current_temperature is None
    assert entitaet.target_temperature == 20.0
    assert entitaet.hvac_mode == "heat"


def test_mit_raumfuehler_zeigt_das_thermostat_die_isttemperatur(thermostat):
    entitaet = thermostat({"/1/15/0/0/1/0": "21.1"})
    assert entitaet.current_temperature == 21.1
