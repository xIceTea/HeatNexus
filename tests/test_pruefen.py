"""Das Prüfwerkzeug: Baumstand, Ablage je Stand und Wiederverwendung des Ergebnisses."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

WURZEL = Path(__file__).resolve().parents[1]


def _werkzeug():
    if (vorhanden := sys.modules.get("pruefen")) is not None:
        return vorhanden
    pfad = WURZEL / "tools" / "pruefen.py"
    spezifikation = importlib.util.spec_from_file_location("pruefen", pfad)
    modul = importlib.util.module_from_spec(spezifikation)
    sys.modules["pruefen"] = modul
    spezifikation.loader.exec_module(modul)
    return modul


def _git(repo: Path, *argumente: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *argumente],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    ziel = tmp_path / "repo"
    ziel.mkdir()
    _git(ziel, "init", "-q")
    (ziel / "a.py").write_text("x = 1\n", encoding="utf-8")
    (ziel / ".gitignore").write_text("ignoriert.txt\n", encoding="utf-8")
    _git(ziel, "add", "-A")
    _git(ziel, "commit", "-q", "-m", "a")
    return ziel


def _zaehler(datei: Path, rc: int = 0) -> list[str]:
    """Ein Befehl, der bei jedem Lauf eine Zeile an `datei` hängt."""
    code = f"open({str(datei)!r}, 'a').write('x\\n'); raise SystemExit({rc})"
    return [sys.executable, "-c", code]


def _laeufe(datei: Path) -> int:
    return len(datei.read_text().splitlines()) if datei.exists() else 0


def test_baumstand_bleibt_ohne_aenderung_gleich(repo):
    pruefen = _werkzeug()
    assert pruefen.baumstand(repo) == pruefen.baumstand(repo)


def test_baumstand_folgt_geaenderter_und_neuer_datei(repo):
    pruefen = _werkzeug()
    vorher = pruefen.baumstand(repo)
    (repo / "a.py").write_text("x = 2\n", encoding="utf-8")
    geaendert = pruefen.baumstand(repo)
    (repo / "neu.py").write_text("y = 1\n", encoding="utf-8")
    assert len({vorher, geaendert, pruefen.baumstand(repo)}) == 3


def test_baumstand_uebergeht_ablage_und_ignorierte_dateien(repo):
    pruefen = _werkzeug()
    vorher = pruefen.baumstand(repo)
    (repo / "ignoriert.txt").write_text("egal", encoding="utf-8")
    (repo / ".pruefung").mkdir()
    (repo / ".pruefung" / "alt.json").write_text("{}", encoding="utf-8")
    assert pruefen.baumstand(repo) == vorher


def test_baumstand_bei_ablage_in_gitignore(repo):
    pruefen = _werkzeug()
    (repo / ".gitignore").write_text(".pruefung/\n", encoding="utf-8")
    vorher = pruefen.baumstand(repo)
    (repo / ".pruefung").mkdir()
    (repo / ".pruefung" / "alt.json").write_text("{}", encoding="utf-8")
    assert pruefen.baumstand(repo) == vorher


def test_baumstand_laesst_den_index_unberuehrt(repo):
    pruefen = _werkzeug()
    (repo / "neu.py").write_text("y = 1\n", encoding="utf-8")
    pruefen.baumstand(repo)
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True
    )
    assert status.stdout.strip() == "?? neu.py"


def test_gruener_lauf_wird_beim_gleichen_stand_nicht_wiederholt(repo, tmp_path):
    pruefen = _werkzeug()
    zaehler = tmp_path / "zaehler"
    erster = pruefen.pruefe(repo, {"probe": _zaehler(zaehler)})
    zweiter = pruefen.pruefe(repo, {"probe": _zaehler(zaehler)})
    assert _laeufe(zaehler) == 1
    assert [lauf.rc for lauf in erster + zweiter] == [0, 0]
    assert zweiter[0].gespeichert is True


def test_roter_lauf_bleibt_beim_gleichen_stand_rot(repo, tmp_path):
    pruefen = _werkzeug()
    zaehler = tmp_path / "zaehler"
    pruefen.pruefe(repo, {"probe": _zaehler(zaehler, rc=1)})
    zweiter = pruefen.pruefe(repo, {"probe": _zaehler(zaehler, rc=1)})
    assert _laeufe(zaehler) == 1
    assert zweiter[0].rc == 1


def test_geaenderter_stand_loest_einen_neuen_lauf_aus(repo, tmp_path):
    pruefen = _werkzeug()
    zaehler = tmp_path / "zaehler"
    pruefen.pruefe(repo, {"probe": _zaehler(zaehler)})
    (repo / "a.py").write_text("x = 3\n", encoding="utf-8")
    pruefen.pruefe(repo, {"probe": _zaehler(zaehler)})
    assert _laeufe(zaehler) == 2


def test_neu_erzwingt_den_lauf_trotz_ergebnis(repo, tmp_path):
    pruefen = _werkzeug()
    zaehler = tmp_path / "zaehler"
    pruefen.pruefe(repo, {"probe": _zaehler(zaehler)})
    pruefen.pruefe(repo, {"probe": _zaehler(zaehler)}, neu=True)
    assert _laeufe(zaehler) == 2


def test_ergebnis_liegt_je_baumstand_in_der_ablage(repo, tmp_path):
    pruefen = _werkzeug()
    pruefen.pruefe(repo, {"probe": _zaehler(tmp_path / "zaehler", rc=1)})
    datei = repo / ".pruefung" / f"{pruefen.baumstand(repo)}.json"
    daten = json.loads(datei.read_text(encoding="utf-8"))
    assert daten["laeufe"]["probe"]["rc"] == 1


def test_gespeichert_meldet_fehlendes_ergebnis(repo, capsys):
    pruefen = _werkzeug()
    assert pruefen.main(["--gespeichert", "--repo", str(repo)]) == 3


def test_gespeichert_gibt_das_ergebnis_als_json_aus(repo, tmp_path, capsys):
    pruefen = _werkzeug()
    pruefen.pruefe(repo, {"probe": _zaehler(tmp_path / "zaehler", rc=1)})
    capsys.readouterr()
    assert pruefen.main(["--gespeichert", "--repo", str(repo)]) == 0
    assert json.loads(capsys.readouterr().out)["laeufe"]["probe"]["rc"] == 1


def test_testdateien_vereinen_die_projekte(tmp_path):
    pruefen = _werkzeug()
    skript = tmp_path / "projekte.py"
    skript.write_text(
        "import os, sys\n"
        "assert os.environ['HEATNEXUS_REPO'] == sys.argv[0].rsplit('projekte.py', 1)[0] + 'repo'\n"
        "print({'P01': 'tests/test_b.py tests/test_a.py', 'P02': 'tests/test_a.py'}[sys.argv[2]])\n",
        encoding="utf-8",
    )
    dateien = pruefen.testdateien(["P01", "p02"], tmp_path / "repo", skript)
    assert dateien == ["tests/test_a.py", "tests/test_b.py"]


def test_ablage_steht_in_gitignore():
    zeilen = (WURZEL / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".pruefung/" in zeilen
