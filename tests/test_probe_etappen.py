"""Die Sonde misst die Dauer jedes Schritts und nennt sie im Bericht."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

WERKZEUG = Path(__file__).parent.parent / "tools" / "heatnexus_probe.py"


@pytest.fixture(scope="module")
def probe_modul():
    spec = importlib.util.spec_from_file_location("heatnexus_probe", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_jeder_schritt_haelt_seine_dauer_fest(probe_modul, monkeypatch):
    uhr = iter([10.0, 70.0, 100.0, 103.5])
    monkeypatch.setattr(probe_modul, "time", SimpleNamespace(monotonic=lambda: next(uhr)))
    dauern: dict[str, float] = {}
    token = probe_modul.ETAPPEN.set(dauern)
    try:
        with probe_modul.etappe("Endpunktsuche"):
            pass
        with probe_modul.etappe("Stapelabruf"), pytest.raises(ValueError):
            raise ValueError("abgebrochen")
    finally:
        probe_modul.ETAPPEN.reset(token)

    assert dauern == {"Endpunktsuche": 60.0, "Stapelabruf": 3.5}


def test_ohne_sammlung_misst_ein_schritt_nichts(probe_modul):
    with probe_modul.etappe("Endpunktsuche"):
        pass
    assert probe_modul.ETAPPEN.get() is None


def test_der_bericht_nennt_die_dauer_je_schritt(probe_modul, tmp_path):
    menus = {"host": "192.0.2.10", "probed": "2026-11-12T17:00:00", "functions": []}
    stats = {
        "requests": 10,
        "seconds": 120.0,
        "etappen": {"Datenpunkte lesen": 100.4, "Endpunktsuche": 19.6},
    }
    pfad = tmp_path / "bericht.md"

    probe_modul.write_report(pfad, menus, {}, stats)

    text = pfad.read_text(encoding="utf-8")
    assert "  - Datenpunkte lesen: 100 s" in text
    assert "  - Endpunktsuche: 20 s" in text
