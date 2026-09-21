"""Die Ebenen, wie der Hersteller sie auswertet.

`overview` ist die Titelseite einer Funktion und damit sichtbar. Geprüft an
einer erfundenen Wärmepumpe (fctType 27), deren Leistung nur dort steht.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

PRAEFIX = "/1/70/0"
LEISTUNG = f"{PRAEFIX}/50/26/0"


async def keine_geraetetexte():
    from custom_components.heatnexus import geraetetexte

    return geraetetexte.Texte()


@pytest.fixture(scope="module")
def client_module():
    from custom_components.heatnexus import client

    return client


async def _erkennen(client_module, monkeypatch, menue):
    c = client_module.WindhagerHttpClient("192.0.2.10", "geheim", levels=["info", "operate"])
    c.geraeteinfo = {"device": "MB66xx", "version": "1.0"}
    c.werksbezeichnung = {"70": "Wärmepumpe"}

    async def fetch(url, semaphore=None):
        return [
            {
                "nodeId": 70,
                "neuronId": "0000WAERME01",
                "name": "Wärmepumpe",
                "functions": [{"fctId": 0, "fctType": 27, "lock": False, "name": "Wärmepumpe"}],
            }
        ]

    async def read_function_menus(prefix, fct_type):
        return dict(menue)

    async def statische_adressen():
        return set()

    monkeypatch.setattr(c, "fetch", fetch)
    monkeypatch.setattr(c, "_read_function_menus", read_function_menus)
    monkeypatch.setattr(c, "_statische_adressen", statische_adressen)
    monkeypatch.setattr(c, "_lade_geraetetexte", keine_geraetetexte)
    await c._discover()
    return c


async def test_ein_wert_der_titelseite_erscheint_als_infoebene(client_module, monkeypatch):
    menue = {LEISTUNG: {"writeProt": True, "unit": "kW", "value": "4.2"}}
    c = await _erkennen(client_module, monkeypatch, menue)
    leistung = next((d for d in c.devices if d.get("oid") == LEISTUNG), None)
    assert leistung is not None, "die Leistung der Titelseite fehlt"
    assert leistung["level"] == "info"
    assert leistung["enabled_default"] is True


async def test_ein_zeitprogramm_der_herstellerliste_wird_gesucht(client_module, monkeypatch):
    """Weder Menü noch Navigation nennen es; die Objektliste des Herstellers schon."""
    menue = {LEISTUNG: {"writeProt": True, "unit": "kW", "value": "4.2"}}
    c = await _erkennen(client_module, monkeypatch, menue)
    assert f"{PRAEFIX}/50/14/0" in {d.get("oid") for d in c.devices}


async def test_versionen_der_herstellerliste_werden_nicht_gesucht(client_module, monkeypatch):
    """Nur Programme: Software- und Hardwarestand laufen über die Geräteinfo."""
    menue = {LEISTUNG: {"writeProt": True, "unit": "kW", "value": "4.2"}}
    c = await _erkennen(client_module, monkeypatch, menue)
    assert f"{PRAEFIX}/4/92/0" not in {d.get("oid") for d in c.devices}


ZAEHLER = "/1/60/0/23/100/0"


def _mit_zaehler(client_module):
    c = client_module.WindhagerHttpClient("192.0.2.10", "geheim", levels=["info"])
    c.devices = [
        c._deskriptor(
            id="0000BIOWIN01-0-23-100-0",
            oid=ZAEHLER,
            name="Brennstoffverbrauch seit Befüllung",
            type="sensor",
            fct_type=9,
        )
    ]
    return c


def test_ein_ruecksetzbarer_zaehler_bekommt_eine_taste(client_module):
    c = _mit_zaehler(client_module)
    c._ruecksetztasten({ZAEHLER: {"writeProt": False}})
    taste = next(d for d in c.devices if d["type"] == "button")
    assert taste["press_value"] == "0.00"
    assert taste["id"].endswith("-zuruecksetzen")
    assert taste["enabled_default"] is False


def test_ein_schreibgeschuetzter_zaehler_bekommt_keine_taste(client_module):
    c = _mit_zaehler(client_module)
    c._ruecksetztasten({ZAEHLER: {"writeProt": True}})
    assert all(d["type"] != "button" for d in c.devices)


def test_die_taste_verdraengt_ihren_zaehler_nicht(client_module):
    """Beide teilen die Adresse; die Oberfläche braucht den Zähler, nicht die Taste."""
    from custom_components.heatnexus.kanonisch import ist_ableitung

    assert ist_ableitung("0000BIOWIN01-0-23-100-0-zuruecksetzen")


def test_eine_einstellung_mit_neustart_wird_markiert(client_module):
    c = client_module.WindhagerHttpClient("192.0.2.10", "geheim", levels=["info"])
    c.devices = [
        c._deskriptor(id="x-0-42-18-0", oid="/1/60/0/42/18/0", type="select", fct_type=9),
        c._deskriptor(id="x-0-0-7-0", oid="/1/60/0/0/7/0", type="temperature", fct_type=9),
    ]
    c._neustart_markieren()
    assert [d.get("neustart") for d in c.devices] == [True, None]


async def test_die_menuelesung_behaelt_werte_der_titelseite(client_module, monkeypatch):
    """Der Filter der Sammellesung muss die Titelseite mitnehmen, sonst fehlt sie."""
    c = client_module.WindhagerHttpClient("192.0.2.10", "geheim", levels=["info"])
    geprueft: dict[str, bool] = {}

    async def menue_ebenen(prefix):
        return {"1": 1}

    async def read_menu(prefix, menu_id, count, pruefer):
        geprueft["50/26"] = pruefer("50/26") if pruefer else True
        return []

    monkeypatch.setattr(c, "_menue_ebenen", menue_ebenen)
    monkeypatch.setattr(c, "_read_menu", read_menu)
    await c._read_function_menus(PRAEFIX, 27)
    assert geprueft["50/26"] is True
