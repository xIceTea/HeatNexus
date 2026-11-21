"""Die Sonde meldet sich, wenn sie längere Zeit nichts ausgegeben hat."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import time

import pytest

WERKZEUG = Path(__file__).parent.parent / "tools" / "heatnexus_probe.py"


@pytest.fixture
def probe_modul(monkeypatch):
    spec = importlib.util.spec_from_file_location("heatnexus_probe", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    monkeypatch.setattr(modul, "LEBENSZEICHEN_S", 0.2)
    monkeypatch.setattr(modul, "LEBENSZEICHEN_TAKT_S", 0.05)
    return modul


def test_stille_bringt_ein_lebenszeichen(probe_modul, capsys):
    with probe_modul.lebenszeichen():
        time.sleep(0.5)

    assert "läuft noch" in capsys.readouterr().out


def test_laufende_ausgabe_braucht_kein_lebenszeichen(probe_modul, capsys):
    with probe_modul.lebenszeichen():
        for _ in range(10):
            print("Zeile")
            time.sleep(0.05)

    assert "läuft noch" not in capsys.readouterr().out


def test_ausgabe_ist_danach_wieder_die_alte(probe_modul):
    vorher = sys.stdout
    with probe_modul.lebenszeichen():
        pass

    assert sys.stdout is vorher
