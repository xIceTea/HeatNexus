"""Die Sonde schwärzt Seriennummer, MAC-Adresse und Knotenkennungen im fertigen Abzug."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

WERKZEUG = Path(__file__).parent.parent / "tools" / "heatnexus_probe.py"

STRUKTUR = [
    {"nodeId": 15, "neuronId": "0702bb00a1b2", "functions": []},
    {"nodeId": 16, "neuronId": "0702bb00c3d4", "functions": []},
]
MENUS = {
    "functions": [
        {
            "prefix": "/1/15/0",
            "datapoints": {
                "/1/15/0/39/112/0": {"value": "00:11:22:AA:BB:CC"},
                "/1/15/0/39/115/0": {"value": "W123456789"},
                "/1/15/0/3/50/0": {"value": "1"},
            },
        }
    ]
}


@pytest.fixture(scope="module")
def probe_modul():
    spec = importlib.util.spec_from_file_location("heatnexus_probe", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_kennungen_verschwinden_aus_allen_dateien(probe_modul, tmp_path):
    json_datei = tmp_path / "anlage_menus.json"
    json_datei.write_text(json.dumps({"structure": STRUKTUR, **MENUS}), encoding="utf-8")
    bericht = tmp_path / "anlage_bericht.md"
    bericht.write_text(
        "Knoten 0702BB00A1B2, MAC 001122aabbcc, Seriennummer W123456789\n", encoding="utf-8"
    )

    probe_modul.schwaerzen([json_datei, bericht], STRUKTUR, MENUS)

    for datei in (json_datei, bericht):
        text = datei.read_text(encoding="utf-8").lower()
        for kennung in ("0702bb00a1b2", "0702bb00c3d4", "aa:bb:cc", "aabbcc", "w123456789"):
            assert kennung not in text, (datei.name, kennung)
    assert "SN1-1" in bericht.read_text(encoding="utf-8")


def test_gleiche_kennung_bekommt_gleichen_platzhalter(probe_modul, tmp_path):
    datei = tmp_path / "anlage_structure.json"
    datei.write_text(json.dumps(STRUKTUR), encoding="utf-8")

    probe_modul.schwaerzen([datei], STRUKTUR, MENUS)

    knoten = json.loads(datei.read_text(encoding="utf-8"))
    assert [k["neuronId"] for k in knoten] == ["SN1-1", "SN1-2"]


def test_geraeteauskunft_und_netz_werden_geschwaerzt(probe_modul, tmp_path):
    """`info/deviceinfo` und `config/network` nennen Seriennummer, Prüfnummer und MAC-Adresse."""
    endpunkte = {
        "vorhanden": [
            {
                "pfad": "/api/1.0/info/deviceinfo",
                "inhalt": {"serialnumber": "00100900000099999", "checknumber": "a1b2c3"},
            },
            {
                "pfad": "/api/1.0/config/network",
                "inhalt": {"MAC": "00:23:43:0a:bc:de", "IP": "192.0.2.10"},
            },
        ]
    }
    datei = tmp_path / "anlage_endpunkte.json"
    datei.write_text(json.dumps(endpunkte), encoding="utf-8")
    bericht = tmp_path / "anlage_bericht.md"
    bericht.write_text("Seriennummer 00100900000099999, MAC 0023430ABCDE\n", encoding="utf-8")

    probe_modul.schwaerzen([datei, bericht], [], None)

    for pfad in (datei, bericht):
        text = pfad.read_text(encoding="utf-8").lower()
        for kennung in ("00100900000099999", "a1b2c3", "0a:bc:de", "0abcde"):
            assert kennung not in text, (pfad.name, kennung)
    inhalt = json.loads(datei.read_text(encoding="utf-8"))["vorhanden"]
    assert inhalt[0]["inhalt"] == {"serialnumber": "<seriennummer>", "checknumber": "<pruefnummer>"}
    assert inhalt[1]["inhalt"]["IP"] == "192.0.2.10"


def test_kurze_werte_bleiben_stehen(probe_modul, tmp_path):
    menus = {"functions": [{"datapoints": {"/1/15/0/39/115/0": {"value": "0"}}}]}
    datei = tmp_path / "anlage_datenpunkte.csv"
    datei.write_text("oid;wert\n/1/15/0/3/50/0;0\n", encoding="utf-8")

    probe_modul.schwaerzen([datei], [], menus)

    assert datei.read_text(encoding="utf-8") == "oid;wert\n/1/15/0/3/50/0;0\n"


def test_eine_kurze_kennung_trifft_keine_laengere_zahl(probe_modul, tmp_path):
    endpunkte = tmp_path / "anlage_endpunkte.json"
    endpunkte.write_text(json.dumps({"inhalt": {"checknumber": "123456"}}), encoding="utf-8")
    werte = tmp_path / "anlage_datenpunkte.csv"
    werte.write_text("oid;wert\n/1/60/0/20/112/0;1234567\n/1/60/0/9/1/0;123456\n", encoding="utf-8")

    probe_modul.schwaerzen([endpunkte, werte], [], None)

    assert werte.read_text(encoding="utf-8") == (
        "oid;wert\n/1/60/0/20/112/0;1234567\n/1/60/0/9/1/0;<pruefnummer>\n"
    )


def test_das_protokoll_wird_vor_dem_packen_geschwaerzt(probe_modul, tmp_path, monkeypatch):
    import zipfile

    monkeypatch.setattr(probe_modul, "_im_explorer_zeigen", lambda _datei: None)
    ziel = tmp_path / "probe"
    ziel.mkdir()
    menus = ziel / "anlage_menus.json"
    menus.write_text(json.dumps(MENUS), encoding="utf-8")
    log = ziel / "sonde.log"
    log.write_text("Knoten 0702bb00a1b2, Seriennummer W123456789\n", encoding="utf-8")
    ergebnis = {
        "host": "192.0.2.10",
        "ok": True,
        "datapoints": 3,
        "seconds": 1.0,
        "files": [str(menus)],
        "ersatz": probe_modul._ersatzpaare([], STRUKTUR, MENUS),
    }

    assert probe_modul._abschluss([ergebnis], ziel, log) == 0

    with zipfile.ZipFile(next(tmp_path.glob("heatnexus-abzug-*.zip"))) as abzug:
        text = abzug.read("probe/sonde.log").decode("utf-8").lower()
    assert "0702bb00a1b2" not in text and "w123456789" not in text
