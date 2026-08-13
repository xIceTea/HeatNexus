"""Die Erkennung des LON-Adressraums.

Ein Knoten meldet neben seiner Funktion einen zweiten Bereich `NV's` ohne
Funktionstyp. Er fiel bisher durch den Filter der Erkennung – mitsamt dem
Bedienteil, das *nur* diesen Bereich hat. Was hier steht, hält den Weg fest,
den eine fremde Baureihe nimmt, für die es keine Adresstabelle gibt.

Die Antworten haben die Form, die eine BioWIN geliefert hat; Adresse und
Seriennummer sind erfunden.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

PRAEFIX_NV = "/1/60/32"
PRAEFIX_FKT = "/1/60/0"

# Drei Einträge, die zusammen die drei Fälle abdecken: kuratiert und ohne
# Entsprechung im OID-Raum, kuratiert mit Entsprechung, unbekannt.
NV_EINTRAEGE = [
    {"nvIndex": 28, "nvName": "PMX_eeBetrStd", "unit": "Std", "value": "14203", "typeId": 13},
    {"nvIndex": 7, "nvName": "WET_nvoTist", "unit": "°C", "value": "78.27", "typeId": 13},
    {"nvIndex": 3, "nvName": "nvoFileDirectory", "unit": "", "value": "16744", "typeId": 13},
]

# Der Kessel führt die Kesseltemperatur als gewöhnlichen Datenpunkt.
MENUE_DATEN = {f"{PRAEFIX_FKT}/0/7/0": {"writeProt": True, "unit": "°C", "value": "76.4"}}


async def keine_geraetetexte():
    from custom_components.heatnexus import geraetetexte

    return geraetetexte.Texte()


@pytest.fixture(scope="module")
def client_module():
    from custom_components.heatnexus import client

    return client


async def _erkennen(client_module, monkeypatch, nv_eintraege=None):
    c = client_module.WindhagerHttpClient("192.0.2.10", "geheim", levels=["info", "operate"])
    c.geraeteinfo = {"device": "MB66xx", "version": "1.0"}
    c.werksbezeichnung = {"60": "BioWIN"}

    async def fetch(url, semaphore=None):
        return [
            {
                "nodeId": 60,
                "neuronId": "0000BIOWIN01",
                "name": "BioWIN",
                "functions": [
                    {"fctId": 0, "fctType": 9, "lock": False, "name": "BioWIN"},
                    {"fctId": 32, "fctType": -1, "lock": False, "name": "NV's"},
                ],
            }
        ]

    async def get(url, semaphore=None):
        if url.endswith(f"lookup{PRAEFIX_NV}"):
            return [{"id": 0, "count": 3}], 200
        if f"lookup{PRAEFIX_NV}/0" in url:
            return list(NV_EINTRAEGE if nv_eintraege is None else nv_eintraege), 200
        return None, 404

    async def read_function_menus(prefix, fct_type):
        return dict(MENUE_DATEN)

    async def statische_adressen():
        return set()

    monkeypatch.setattr(c, "fetch", fetch)
    monkeypatch.setattr(c, "_get", get)
    monkeypatch.setattr(c, "_read_function_menus", read_function_menus)
    monkeypatch.setattr(c, "_statische_adressen", statische_adressen)
    monkeypatch.setattr(c, "_lade_geraetetexte", keine_geraetetexte)
    await c._discover()
    # Erst danach steht fest, welche Datenpunkte die Anlage wirklich führt –
    # und damit, welcher LON-Wert eine Entsprechung hat.
    await c._apply_metadata()
    return c


def _nv(c, nv_name: str) -> dict:
    return next(d for d in c.devices if d.get("nv_name") == nv_name)


async def test_netzwerkvariablen_werden_ueberhaupt_erkannt(client_module, monkeypatch):
    """Ohne diesen Weg fehlt der ganze Adressraum – und Knoten 90 mit ihm."""
    c = await _erkennen(client_module, monkeypatch)

    assert len([d for d in c.devices if d.get("nv_name")]) == 3


async def test_kuratierter_name_ersetzt_den_rohnamen(client_module, monkeypatch):
    c = await _erkennen(client_module, monkeypatch)

    eintrag = _nv(c, "PMX_eeBetrStd")
    assert eintrag["name"] == "Betriebsstunden"
    assert eintrag["enabled_default"] is True
    assert eintrag["oid"] == f"{PRAEFIX_NV}/0/28/0"


async def test_unbekannter_name_kommt_deaktiviert_mit_rohnamen(client_module, monkeypatch):
    """Nichts geht verloren, aber die Liste bleibt sauber."""
    c = await _erkennen(client_module, monkeypatch)

    eintrag = _nv(c, "nvoFileDirectory")
    assert eintrag["name"] == "nvoFileDirectory"
    assert eintrag["enabled_default"] is False


async def test_doppelter_begriff_bleibt_deaktiviert(client_module, monkeypatch):
    """Die Kesseltemperatur gibt es schon als Datenpunkt – einmal reicht."""
    c = await _erkennen(client_module, monkeypatch)

    assert _nv(c, "WET_nvoTist")["enabled_default"] is False


async def test_netzwerkvariablen_werden_nie_geschrieben(client_module, monkeypatch):
    """`nvi`-Variablen sind Eingänge der Regelung zwischen den Knoten."""
    c = await _erkennen(client_module, monkeypatch)

    assert all(d["write_prot"] is True for d in c.devices if d.get("nv_name"))


async def test_kennung_wird_nicht_als_datenpunktadresse_gelesen(client_module, monkeypatch):
    """Aus `…-32-0-7-0` würde sonst `0/7`, die Kesseltemperatur."""
    from custom_components.heatnexus.kanonisch import schluessel

    c = await _erkennen(client_module, monkeypatch)

    assert schluessel(_nv(c, "WET_nvoTist")["id"]) is None


async def test_der_kurzdurchlauf_liest_keine_netzwerkvariablen(client_module, monkeypatch):
    """Die Einrichtung darf davon nicht länger werden."""
    c = client_module.WindhagerHttpClient("192.0.2.10", "geheim", levels=["info"])
    c.geraeteinfo = {"device": "MB66xx", "version": "1.0"}
    c.werksbezeichnung = {"60": "BioWIN"}
    gefragt = []

    async def fetch(url, semaphore=None):
        return [
            {
                "nodeId": 60,
                "neuronId": "0000BIOWIN01",
                "name": "BioWIN",
                "functions": [{"fctId": 32, "fctType": -1, "lock": False, "name": "NV's"}],
            }
        ]

    async def get(url, semaphore=None):
        gefragt.append(url)
        return None, 404

    monkeypatch.setattr(c, "fetch", fetch)
    monkeypatch.setattr(c, "_get", get)
    monkeypatch.setattr(c, "_lade_geraetetexte", keine_geraetetexte)
    await c._discover(nur_kern=True)

    assert not [u for u in gefragt if PRAEFIX_NV in u]
