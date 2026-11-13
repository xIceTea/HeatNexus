"""Eine Fehlerantwort, deren Rumpf nicht ankommt, beendet keinen Schritt der Sonde."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import urllib.error

import pytest

WERKZEUG = Path(__file__).parent.parent / "tools" / "heatnexus_probe.py"
URL = "http://192.0.2.10/api/1.0/object?OID=/1/90/0/2/90/0"


@pytest.fixture(scope="module")
def probe_modul():
    spec = importlib.util.spec_from_file_location("heatnexus_probe", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class HaengenderRumpf:
    """Der Kopf ist da, das Lesen des Rumpfs läuft in die Zeitgrenze."""

    def read(self, *_):
        raise TimeoutError("timed out")

    def close(self):
        pass


class Opener:
    def __init__(self, status: int) -> None:  # noqa: D107
        self.status = status

    def open(self, url, timeout=None):
        raise urllib.error.HTTPError(str(url), self.status, "", {}, HaengenderRumpf())


def _probe(probe_modul, monkeypatch, status: int):
    monkeypatch.setattr(probe_modul.time, "sleep", lambda _s: None)
    probe = probe_modul.Probe("192.0.2.10", "geheim")
    probe._local.opener = Opener(status)
    return probe


@pytest.mark.parametrize("status", [500, 503])
def test_get_meldet_den_status_wenn_der_rumpf_nicht_ankommt(probe_modul, monkeypatch, status):
    probe = _probe(probe_modul, monkeypatch, status)

    data, antwort = probe.get(URL)

    assert antwort == status
    assert "error" in data


def test_post_meldet_den_status_wenn_der_rumpf_nicht_ankommt(probe_modul, monkeypatch):
    probe = _probe(probe_modul, monkeypatch, 500)

    text, antwort = probe.post("http://192.0.2.10/ws", b"<x/>")

    assert antwort == 500
    assert "timed out" in text


class Anlage:
    """Ein Ziel scheitert hart, die übrigen antworten."""

    workers = 1

    def obj(self, oid):
        if "/1/90/" in oid:
            raise TimeoutError("timed out")
        return {"value": "1"}, 200

    def lookup(self, pfad):
        return {}, 409

    def map(self, func, items):
        return [func(i) for i in items]


def test_ein_scheiterndes_objekt_beendet_den_schritt_nicht(probe_modul, monkeypatch):
    monkeypatch.setattr(probe_modul, "statische_navigation", lambda _p: {"2/90/0": "Zeitprogramm"})
    monkeypatch.setattr(probe_modul, "DEVICE_DB", None)
    menus = {
        "functions": [
            {"prefix": "/1/15/0", "datapoints": {}},
            {"prefix": "/1/90/32", "datapoints": {}},
        ]
    }

    objekte = probe_modul.fetch_objects(Anlage(), menus)

    assert objekte["/1/15/0/2/90/0"]["status"] == 200
    assert objekte["/1/90/32/2/90/0"]["status"] == 0
    assert "timed out" in objekte["/1/90/32/2/90/0"]["data"]["error"]
