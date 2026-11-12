"""Geführter Modus der Sonde: stille Ausgabe mit Protokoll, Sprache, fertiges ZIP."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import zipfile

import pytest

WERKZEUG = Path(__file__).parent.parent / "tools" / "heatnexus_probe.py"


@pytest.fixture
def probe_modul(monkeypatch):
    spec = importlib.util.spec_from_file_location("heatnexus_probe", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    monkeypatch.setattr(modul, "SPRACHE", "de")
    monkeypatch.setattr(modul, "_im_explorer_zeigen", lambda datei: None)
    return modul


def test_stiller_modus_zeigt_nur_nutzerzeilen(probe_modul, tmp_path, capsys):
    log = tmp_path / "sonde.log"

    with probe_modul.ausgabe(log, still=True):
        print("technische Zeile")
        probe_modul.sage("für den Nutzer")

    sichtbar = capsys.readouterr().out
    assert "für den Nutzer" in sichtbar
    assert "technische Zeile" not in sichtbar
    protokoll = log.read_text(encoding="utf-8")
    assert "technische Zeile" in protokoll and "für den Nutzer" in protokoll


def test_etappe_zeigt_haken_und_fortschritt(probe_modul, capsys):
    with probe_modul.ausgabe(still=True), probe_modul.etappe("Bericht"):
        probe_modul.fortschritt("Funktion 2 von 3")

    sichtbar = capsys.readouterr().out
    assert "✓ Bericht · Funktion 2 von 3" in sichtbar


def test_geschuetzte_etappe_laesst_den_lauf_weiterlaufen(probe_modul, capsys):
    with probe_modul.ausgabe(still=True), probe_modul.etappe("Bericht"):
        raise ValueError("kaputt")

    assert "✗ Bericht" in capsys.readouterr().out


def test_englisch_uebersetzt_nutzertexte(probe_modul, monkeypatch):
    monkeypatch.setattr(probe_modul, "SPRACHE", "en")

    assert probe_modul._t("{} Datenpunkte", 5) == "5 datapoints"
    assert probe_modul._t("unbekannter Text") == "unbekannter Text"


def test_sprache_aus_der_umgebung(probe_modul, monkeypatch):
    monkeypatch.setenv("HEATNEXUS_SPRACHE", "en")

    assert probe_modul._sprache_erkennen() == "en"


def test_abschluss_packt_die_dateien_des_laufs(probe_modul, tmp_path):
    ordner = tmp_path / "probe"
    ordner.mkdir()
    datei = ordner / "192.0.2.10_menus.json"
    datei.write_text("{}", encoding="utf-8")
    alt = ordner / "192.0.2.99_menus.json"
    alt.write_text("{}", encoding="utf-8")
    log = ordner / "sonde.log"
    log.write_text("Protokoll", encoding="utf-8")
    ergebnis = {"host": "192.0.2.10", "ok": True, "datapoints": 3, "seconds": 75.0}

    rueckgabe = probe_modul._abschluss([{**ergebnis, "files": [str(datei)]}], ordner, log)

    zip_datei = next(tmp_path.glob("heatnexus-abzug-*.zip"))
    assert rueckgabe == 0
    with zipfile.ZipFile(zip_datei) as inhalt:
        assert sorted(inhalt.namelist()) == ["probe/192.0.2.10_menus.json", "probe/sonde.log"]


def test_abschluss_ohne_erfolg_packt_nichts(probe_modul, tmp_path):
    ordner = tmp_path / "probe"
    ordner.mkdir()

    rueckgabe = probe_modul._abschluss([{"host": "192.0.2.10", "ok": False}], ordner, ordner / "x")

    assert rueckgabe == 1
    assert not list(tmp_path.glob("*.zip"))
