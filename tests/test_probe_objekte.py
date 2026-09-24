"""Das Probe-Werkzeug an den strukturierten Objekten.

Nicht jede Steuerung nennt ihre Zeitprogramme in der statischen Navigation.
Die Adressen, die der Hersteller je Funktionstyp über den object-Endpunkt
liest, prüft der Abzug deshalb zusätzlich – über beide Endpunkte.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

WERKZEUG = Path(__file__).parent.parent / "tools" / "heatnexus_probe.py"
PROGRAMM = "/1/60/5/5/61/0"


@pytest.fixture(scope="module")
def probe_modul():
    spec = importlib.util.spec_from_file_location("heatnexus_probe", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class SteuerungAttrappe:
    """Kennt das Zeitprogramm nur am object-Endpunkt."""

    def obj(self, oid):
        if oid == PROGRAMM:
            return {"value": [{"weekdays": ["Mo"], "switchPoints": []}], "typeId": 30}, 200
        return {"code": 404}, 404

    def lookup(self, pfad):
        return {"code": 404}, 404

    def map(self, ruf, eintraege):
        return [ruf(eintrag) for eintrag in eintraege]


def test_zeitprogramme_des_herstellers_werden_geprueft(probe_modul, monkeypatch):
    monkeypatch.setattr(probe_modul, "statische_navigation", lambda probe: {})
    menus = {"functions": [{"prefix": "/1/60/5", "fct_type": 14, "datapoints": {}}]}

    objekte = probe_modul.fetch_objects(SteuerungAttrappe(), menus)

    assert objekte[PROGRAMM]["status"] == 200
    assert objekte[PROGRAMM]["antworten"] == {"object": 200, "lookup": 404}
