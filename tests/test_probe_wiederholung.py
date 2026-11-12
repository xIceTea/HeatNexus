"""Die Sonde wiederholt nur vorübergehende Fehlerantworten, endgültige gehen sofort zurück."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import urllib.error

import pytest

WERKZEUG = Path(__file__).parent.parent / "tools" / "heatnexus_probe.py"
URL = "http://192.0.2.10/api/1.0/recorder"


@pytest.fixture(scope="module")
def probe_modul():
    spec = importlib.util.spec_from_file_location("heatnexus_probe", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class Opener:
    """Antwortet auf jede Anfrage mit demselben HTTP-Fehler."""

    def __init__(self, status: int, rumpf: str) -> None:  # noqa: D107
        self.status = status
        self.rumpf = rumpf.encode()
        self.aufrufe = 0

    def open(self, url, timeout=None):
        self.aufrufe += 1
        raise urllib.error.HTTPError(url, self.status, "", {}, io.BytesIO(self.rumpf))


def _abrufen(probe_modul, monkeypatch, status: int, rumpf: str):
    pausen: list[float] = []
    monkeypatch.setattr(probe_modul.time, "sleep", pausen.append)
    probe = probe_modul.Probe("192.0.2.10", "geheim")
    opener = Opener(status, rumpf)
    probe._local.opener = opener
    data, antwort = probe.get(URL)
    return opener.aufrufe, pausen, data, antwort


@pytest.mark.parametrize(
    ("status", "rumpf"),
    [
        (503, '{"reason": "endpoint <recorder> does not exist."}'),
        (500, '{"reason": "Wrong formatted OID"}'),
        (501, '{"reason": "Not Implemented"}'),
    ],
)
def test_eine_endgueltige_fehlerantwort_wird_nicht_wiederholt(
    probe_modul, monkeypatch, status, rumpf
):
    aufrufe, pausen, data, antwort = _abrufen(probe_modul, monkeypatch, status, rumpf)

    assert aufrufe == 1
    assert pausen == []
    assert antwort == status
    assert "reason" in data


@pytest.mark.parametrize(
    ("status", "rumpf"),
    [(502, "Bad Gateway"), (504, "Gateway Timeout"), (503, '{"reason": "busy"}')],
)
def test_eine_ueberlastung_wird_mit_pause_wiederholt(probe_modul, monkeypatch, status, rumpf):
    aufrufe, pausen, _, antwort = _abrufen(probe_modul, monkeypatch, status, rumpf)

    assert aufrufe == probe_modul.GATEWAY_RETRIES + 1
    assert len(pausen) == probe_modul.GATEWAY_RETRIES
    assert antwort == status
