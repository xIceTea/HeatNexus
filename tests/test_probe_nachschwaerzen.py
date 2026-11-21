"""Ein vorhandener Abzug lässt sich nachträglich schwärzen, ohne die Anlage zu fragen."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

WERKZEUG = Path(__file__).parent.parent / "tools" / "heatnexus_probe.py"

STRUKTUR = [{"nodeId": 15, "neuronId": "0702bb00a1b2", "functions": []}]
MENUS = {
    "host": "192.0.2.10",
    "structure": STRUKTUR,
    "functions": [
        {
            "prefix": "/1/15/0",
            "datapoints": {
                "/1/15/0/39/112/0": {"value": "00:11:22:AA:BB:CC"},
                "/1/15/0/39/115/0": {"value": "W123456789"},
            },
        }
    ],
}
KENNUNGEN = ("0702bb00a1b2", "aa:bb:cc", "aabbcc", "w123456789")


@pytest.fixture(scope="module")
def probe_modul():
    spec = importlib.util.spec_from_file_location("heatnexus_probe", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _abzug(ordner: Path, mit_struktur: bool = True) -> list[Path]:
    dateien = [ordner / "192.0.2.10_menus.json", ordner / "192.0.2.10_bericht.md"]
    dateien[0].write_text(json.dumps(MENUS), encoding="utf-8")
    dateien[1].write_text("Knoten 0702BB00A1B2, MAC 001122aabbcc, SN W123456789\n", "utf-8")
    if mit_struktur:
        struktur = ordner / "192.0.2.10_structure.json"
        struktur.write_text(json.dumps(STRUKTUR), encoding="utf-8")
        dateien.append(struktur)
    return dateien


def _sauber(datei: Path) -> bool:
    text = datei.read_text(encoding="utf-8").lower()
    return not any(k in text for k in KENNUNGEN)


def test_alle_dateien_einer_anlage_werden_geschwaerzt(probe_modul, tmp_path):
    dateien = _abzug(tmp_path)

    geschwaerzt = probe_modul.schwaerzen_ordner(tmp_path)

    assert sorted(geschwaerzt) == sorted(dateien)
    assert all(_sauber(d) for d in dateien)


def test_knoten_kommen_auch_aus_den_menues(probe_modul, tmp_path):
    dateien = _abzug(tmp_path, mit_struktur=False)

    probe_modul.schwaerzen_ordner(tmp_path)

    assert all(_sauber(d) for d in dateien)


def test_zweiter_durchlauf_aendert_nichts_mehr(probe_modul, tmp_path):
    _abzug(tmp_path)
    probe_modul.schwaerzen_ordner(tmp_path)

    assert probe_modul.schwaerzen_ordner(tmp_path) == []


def test_ordner_ohne_abzug_meldet_nichts(probe_modul, tmp_path):
    (tmp_path / "hosts.txt").write_text("192.0.2.10\n", encoding="utf-8")

    assert probe_modul.schwaerzen_ordner(tmp_path) == []
