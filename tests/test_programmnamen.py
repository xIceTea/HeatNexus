"""Namen der Zeitprogramme an beiden Heizkreis-Baureihen.

Der Infinity-Heizkreis (fctType 1) führt drei Programme für die Raumtemperatur
(`3/61`–`3/63`) und drei für die Vorlauftemperatur (`58/78`–`58/80`). Die
Herstellertabelle nennt beide Sätze gleich „Programm 1“ bis „Programm 3“.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import load_standalone, requires_ha

KOMPONENTE = Path(__file__).parent.parent / "custom_components" / "heatnexus"
RAUM = ("3/61", "3/62", "3/63")
VORLAUF = ("58/78", "58/79", "58/80")
KNOTEN = 15
SERIE = "0000INFINI01"


@pytest.fixture(scope="module")
def geraete():
    return load_standalone("geraete")


@pytest.fixture(scope="module")
def db():
    return json.loads((KOMPONENTE / "device_db.json").read_text(encoding="utf-8"))


def _name(geraete, db, fct_type: int, gnmn: str) -> str | None:
    """Der Name, den die Erkennung einer Adresse gibt: Baureihe vor Herstellertabelle."""
    return geraete.NAMEN.get(fct_type, {}).get(gnmn) or db["names"].get(gnmn)


def test_die_herstellertabelle_nennt_beide_saetze_gleich(db):
    """Die Voraussetzung: Ohne eigene Namen hängt die Erkennung die Adresse an."""
    assert [db["names"][a] for a in RAUM] == [db["names"][a] for a in VORLAUF]


def test_jedes_zeitprogramm_des_infinity_heizkreises_heisst_anders(geraete, db):
    programme = [a for a in db["layers"]["1"]["objekte"] if a in RAUM + VORLAUF]
    namen = [_name(geraete, db, 1, a).casefold() for a in programme]
    assert len(programme) == 6
    assert len(set(namen)) == len(namen)


def test_die_raumprogramme_heissen_an_beiden_baureihen_gleich(geraete, db):
    assert [_name(geraete, db, 1, a) for a in RAUM] == [_name(geraete, db, 14, a) for a in RAUM]


def test_die_vorlaufprogramme_nennen_ihre_bezugsgroesse(geraete, db):
    assert [_name(geraete, db, 1, a) for a in VORLAUF] == [
        "Programm 1 Vorlauftemperatur",
        "Programm 2 Vorlauftemperatur",
        "Programm 3 Vorlauftemperatur",
    ]


def test_die_sollwerte_fuer_raum_und_vorlauf_heissen_verschieden(geraete, db):
    sollwerte = ("3/51", "3/53", "58/81", "58/82")
    assert set(db["layers"]["1"]["groups"]["Vorlauftemperatur Sollwerte"]) == {"58/81", "58/82"}
    namen = [_name(geraete, db, 1, a).casefold() for a in sollwerte]
    assert len(set(namen)) == len(namen)


async def _keine_geraetetexte():
    from custom_components.heatnexus import geraetetexte

    return geraetetexte.Texte()


async def _erkennen(monkeypatch):
    from custom_components.heatnexus import client

    c = client.WindhagerHttpClient("192.0.2.10", "geheim", levels=["info", "operate"])
    c.geraeteinfo = {"device": "MB66xx", "version": "1.0"}
    c.werksbezeichnung = {str(KNOTEN): "Infinity"}

    async def fetch(url, semaphore=None):
        return [
            {
                "nodeId": KNOTEN,
                "neuronId": SERIE,
                "name": "Heizkreise",
                "functions": [{"fctId": 0, "fctType": 1, "lock": False, "name": "Heizkreis 1"}],
            }
        ]

    async def leer(*_args):
        return {}

    async def keine_adressen():
        return set()

    monkeypatch.setattr(c, "fetch", fetch)
    monkeypatch.setattr(c, "_read_function_menus", leer)
    monkeypatch.setattr(c, "_statische_adressen", keine_adressen)
    monkeypatch.setattr(c, "_lade_geraetetexte", _keine_geraetetexte)
    await c._discover()
    c._namen_vereindeutigen()
    return c


@requires_ha()
async def test_die_erkennung_haengt_keine_adresse_an(monkeypatch):
    c = await _erkennen(monkeypatch)
    namen = {d["oid"].split("/1/15/0/", 1)[1][:-2]: d["name"] for d in c.devices if d.get("oid")}
    assert [namen[a] for a in RAUM] == ["Programm 1", "Programm 2", "Programm 3"]
    assert namen["58/78"] == "Programm 1 Vorlauftemperatur"
    assert not [n for n in namen.values() if "(" in n]


@requires_ha()
async def test_der_name_aendert_die_kennung_nicht(monkeypatch):
    c = await _erkennen(monkeypatch)
    kennungen = {d["oid"]: d["id"] for d in c.devices if d.get("oid")}
    assert kennungen["/1/15/0/58/78/0"] == f"{SERIE}-0-58-78-0"
    assert kennungen["/1/15/0/3/61/0"] == f"{SERIE}-0-3-61-0"
