"""Die Sonde fragt die Master-Position des Netzwerkmoduls nicht nach Objekten."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

WERKZEUG = Path(__file__).parent.parent / "tools" / "heatnexus_probe.py"


@pytest.fixture(scope="module")
def probe_modul():
    spec = importlib.util.spec_from_file_location("heatnexus_probe", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class Steuerung:
    """Merkt sich jede gefragte Adresse."""

    def __init__(self) -> None:  # noqa: D107
        self.gefragt: list[str] = []

    def obj(self, oid):
        self.gefragt.append(oid)
        return {"code": 409}, 409

    def lookup(self, pfad):
        self.gefragt.append(pfad)
        return {"code": 409}, 409

    def map(self, ruf, eintraege):
        return [ruf(eintrag) for eintrag in eintraege]


@pytest.mark.parametrize("knoten", [85, 90, 95, 96, 97, 100])
def test_objektsuche_laesst_die_master_position_aus(probe_modul, monkeypatch, knoten):
    monkeypatch.setattr(
        probe_modul, "statische_navigation", lambda _p: {"3/61/0": "Zeitprogramm 1"}
    )
    monkeypatch.setattr(probe_modul, "DEVICE_DB", None)
    menus = {
        "functions": [
            {"prefix": "/1/15/0", "datapoints": {}},
            {"prefix": f"/1/{knoten}/32", "datapoints": {}},
        ]
    }
    steuerung = Steuerung()

    objekte = probe_modul.fetch_objects(steuerung, menus)

    assert "/1/15/0/3/61/0" in objekte
    assert not any(f"/1/{knoten}/" in oid for oid in steuerung.gefragt)


def test_statische_suche_laesst_die_master_position_aus(probe_modul, monkeypatch):
    monkeypatch.setattr(
        probe_modul, "statische_navigation", lambda _p: {"3/61/0": "Zeitprogramm 1"}
    )
    struktur = [
        {"nodeId": 15, "functions": [{"fctId": 0}]},
        {"nodeId": 60, "functions": [{"fctId": 0}, {"fctId": 32}]},
        {"nodeId": 90, "functions": [{"fctId": 32}]},
    ]
    steuerung = Steuerung()

    ergebnis = probe_modul.suche_statisch(steuerung, struktur)

    praefixe = {zeile["prefix"] for zeile in ergebnis["alle"]}
    assert praefixe == {"/1/15/0", "/1/60/0", "/1/60/32"}
    assert not any("/1/90/" in oid for oid in steuerung.gefragt)
