"""Der Automatik-/Zusatzkessel (fctType 10) ohne kuratierte Tabelle.

Diese Baureihe führt ihre Kesseltemperatur in keiner Bedienebene, wohl aber
auf der Übersichtsseite des Herstellers. Die Tests halten fest, dass sie von
dort als Infoebene ankommt – eingeschaltet, mit derselben Art wie am PuroWIN.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import load_standalone, requires_ha

KOMPONENTE = Path(__file__).parent.parent / "custom_components" / "heatnexus"
FCT_AUTOMATIKKESSEL = "10"
PRAEFIX = "/1/65/0"
KESSEL = f"{PRAEFIX}/0/7/0"
BETRIEBSART = f"{PRAEFIX}/2/59/0"

# Metadaten in der Form, die die Steuerung für beide Adressen meldet.
MENUE = {
    KESSEL: {"writeProt": True, "typeId": 13, "unit": "°C", "value": "64.2"},
    BETRIEBSART: {"writeProt": True, "typeId": 9, "enum": "[0,1,2,5]", "value": "5"},
}


@pytest.fixture(scope="module")
def db():
    return json.loads((KOMPONENTE / "device_db.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ebenenfolge():
    return load_standalone("client.gemeinsam").EBENENFOLGE


def _ebene(db, ebenenfolge, gnmn: str) -> str | None:
    """Die Ebene, die die Erkennung einer Adresse gibt."""
    ebenen = db["layers"][FCT_AUTOMATIKKESSEL]
    return next((ziel for liste, ziel in ebenenfolge if gnmn in ebenen.get(liste, [])), None)


def test_kesseltemperatur_und_betriebsart_stehen_in_keiner_bedienebene(db):
    """Die Voraussetzung: Ohne Übersichtsseite blieben beide Werksebene."""
    ebenen = db["layers"][FCT_AUTOMATIKKESSEL]
    bedienbar = set(ebenen["info"]) | set(ebenen["operate"])
    assert {"0/7", "2/59"} <= set(ebenen["overview"])
    assert not {"0/7", "2/59"} & bedienbar


def test_die_uebersichtsseite_hebt_sie_auf_die_infoebene(db, ebenenfolge):
    assert _ebene(db, ebenenfolge, "0/7") == "info"
    assert _ebene(db, ebenenfolge, "2/59") == "info"


@pytest.fixture(scope="module")
def client_module():
    from custom_components.heatnexus import client

    return client


async def _erkennen(client_module, monkeypatch):
    from custom_components.heatnexus import geraetetexte

    c = client_module.WindhagerHttpClient("192.0.2.10", "geheim", levels=["info", "operate"])
    c.geraeteinfo = {"device": "MB66xx", "version": "1.0"}
    c.werksbezeichnung = {"65": "LogWIN"}

    async def fetch(url, semaphore=None):
        return [
            {
                "nodeId": 65,
                "neuronId": "0000LOGWIN01",
                "name": "LogWIN",
                "functions": [{"fctId": 0, "fctType": 10, "lock": False, "name": "LogWIN"}],
            }
        ]

    async def read_function_menus(prefix, fct_type):
        return dict(MENUE)

    async def statische_adressen():
        return set()

    async def keine_geraetetexte():
        return geraetetexte.Texte()

    monkeypatch.setattr(c, "fetch", fetch)
    monkeypatch.setattr(c, "_read_function_menus", read_function_menus)
    monkeypatch.setattr(c, "_statische_adressen", statische_adressen)
    monkeypatch.setattr(c, "_lade_geraetetexte", keine_geraetetexte)
    await c._discover()
    return {d.get("oid"): d for d in c.devices}, c


@requires_ha()
async def test_der_kessel_entsteht_eingeschaltet_auf_der_infoebene(client_module, monkeypatch):
    beschreibungen, _ = await _erkennen(client_module, monkeypatch)
    for oid in (KESSEL, BETRIEBSART):
        assert beschreibungen[oid]["level"] == "info", oid
        assert beschreibungen[oid]["enabled_default"] is True, oid
    assert beschreibungen[KESSEL]["name"] == "Kesseltemperatur Ist"


@requires_ha()
async def test_die_arten_gleichen_denen_der_anderen_kessel(client_module, monkeypatch):
    beschreibungen, c = await _erkennen(client_module, monkeypatch)
    assert c._resolve_auto_type(beschreibungen[KESSEL], MENUE[KESSEL]) == "temperature"
    art = c._resolve_auto_type(beschreibungen[BETRIEBSART], MENUE[BETRIEBSART])
    assert art == "enum_sensor"
    assert beschreibungen[BETRIEBSART]["enum"] == "2/59"
