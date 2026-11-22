"""Bündelt die lokalen Prüfungen und merkt sich ihr Ergebnis je Baumstand.

Aufruf: `python tools/pruefen.py [--projekt P05 ...]`. Gleicher Baumstand heißt gleiches
Ergebnis: Jede Prüfung läuft je Stand einmal, eine rote bleibt rot bis zur nächsten Änderung.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parent.parent
ABLAGE = ".pruefung"
BEREICHE = ("custom_components", "tests", "tools")
AUSGABE_ZEILEN = 40


@dataclass(frozen=True)
class Lauf:
    """Ergebnis einer Prüfung; `gespeichert` heißt: aus der Ablage, nicht neu gelaufen."""

    name: str
    rc: int
    ausgabe: str
    sekunden: float
    gespeichert: bool


def _git(repo: Path, *argumente: str, umgebung: dict[str, str] | None = None) -> str:
    lauf = subprocess.run(
        ["git", "-c", "safe.directory=*", "-c", "core.quotePath=false", *argumente],
        cwd=repo,
        env=umgebung,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return lauf.stdout.strip()


def baumstand(repo: Path) -> str:
    """Tree-Hash über Index und Arbeitsbaum samt neuer Dateien; der echte Index bleibt unberührt."""
    index = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-path", "index"))
    with tempfile.TemporaryDirectory() as ordner:
        kopie = Path(ordner) / "index"
        if index.is_file():
            # copy2 behält die Zeit des Index; sonst gälte eine eben geänderte Datei als unverändert.
            shutil.copy2(index, kopie)
        umgebung = {**os.environ, "GIT_INDEX_FILE": str(kopie)}
        # Ein ausdrücklicher Ausschluss eines schon ignorierten Pfads lässt `git add` scheitern.
        ignoriert = subprocess.run(
            ["git", "-c", "safe.directory=*", "check-ignore", "-q", f"{ABLAGE}/x.json"],
            cwd=repo,
            capture_output=True,
            check=False,
        )
        ausschluss = [] if ignoriert.returncode == 0 else ["--", ".", f":(exclude){ABLAGE}"]
        _git(repo, "add", "-A", *ausschluss, umgebung=umgebung)
        return _git(repo, "write-tree", umgebung=umgebung)


def _datei(repo: Path, baum: str) -> Path:
    return repo / ABLAGE / f"{baum}.json"


def laden(repo: Path, baum: str) -> dict:
    try:
        return json.loads(_datei(repo, baum).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _speichern(repo: Path, baum: str, name: str, eintrag: dict) -> None:
    """Einen Lauf eintragen; ein paralleler Lauf am selben Stand verliert dabei nichts."""
    ziel = _datei(repo, baum)
    ziel.parent.mkdir(exist_ok=True)
    daten = laden(repo, baum) or {"baum": baum, "laeufe": {}}
    daten["laeufe"][name] = eintrag
    zwischen = ziel.with_name(f"{ziel.name}.{os.getpid()}.tmp")
    zwischen.write_text(json.dumps(daten, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(zwischen, ziel)


def pruefe(
    repo: Path,
    pruefungen: dict[str, list[str]],
    *,
    umgebung: dict[str, str] | None = None,
    neu: bool = False,
) -> list[Lauf]:
    """Jede Prüfung einmal je Baumstand; ein gleicher Befehl am gleichen Stand liest die Ablage."""
    baum = baumstand(repo)
    alt = {} if neu else laden(repo, baum).get("laeufe", {})
    ergebnis: dict[str, Lauf] = {}
    offen = {}
    with tempfile.TemporaryDirectory() as ordner:
        # Gleichzeitig: Auf einer Netzfreigabe warten die Läufe meist auf Dateizugriffe.
        for nummer, (name, befehl) in enumerate(pruefungen.items()):
            eintrag = alt.get(name)
            if eintrag and eintrag.get("befehl") == befehl:
                ergebnis[name] = Lauf(
                    name, eintrag["rc"], eintrag["ausgabe"], eintrag["sekunden"], True
                )
                continue
            aus = (Path(ordner) / f"{nummer}.out").open("w+", encoding="utf-8", errors="replace")
            prozess = subprocess.Popen(
                befehl, cwd=repo, env=umgebung, stdout=aus, stderr=subprocess.STDOUT, text=True
            )
            offen[name] = (befehl, prozess, aus, time.monotonic())
        while offen:
            fertig = [
                name for name, (_, prozess, _, _) in offen.items() if prozess.poll() is not None
            ]
            if not fertig:
                time.sleep(0.2)
                continue
            name = fertig[0]
            befehl, prozess, aus, start = offen.pop(name)
            rc = prozess.returncode
            sekunden = round(time.monotonic() - start, 1)
            aus.seek(0)
            ausgabe = "\n".join(aus.read().strip().splitlines()[-AUSGABE_ZEILEN:])
            aus.close()
            _speichern(
                repo,
                baum,
                name,
                {
                    "befehl": befehl,
                    "rc": rc,
                    "ausgabe": ausgabe,
                    "sekunden": sekunden,
                    "zeit": dt.datetime.now().isoformat(timespec="seconds"),
                },
            )
            ergebnis[name] = Lauf(name, rc, ausgabe, sekunden, False)
    return [ergebnis[name] for name in pruefungen]


def intern_ordner(repo: Path) -> Path | None:
    """Ordner mit der Projektzuordnung `projekte.py`; liegt außerhalb des Repos neben dem Hauptcheckout."""
    if wert := os.environ.get("HEATNEXUS_INTERN"):
        return Path(wert)
    gemeinsam = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    for ordner in sorted(gemeinsam.parent.parent.iterdir()):
        if (ordner / "projekte.py").is_file():
            return ordner
    return None


def testdateien(projekte: list[str], repo: Path, skript: Path) -> list[str]:
    """Die Testdateien der Projekte, aufgelöst gegen dieses Repo statt gegen den Hauptcheckout."""
    dateien: set[str] = set()
    for projekt in projekte:
        lauf = subprocess.run(
            [sys.executable, "-B", str(skript), "--tests", projekt.upper()],
            env={**os.environ, "HEATNEXUS_REPO": str(repo)},
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        dateien.update(lauf.stdout.split())
    return sorted(dateien)


def _befehle(repo: Path, basis: str, tests: list[str], projekte: list[str]) -> dict[str, list[str]]:
    py = sys.executable
    ruff = [gefunden] if (gefunden := shutil.which("ruff")) else [py, "-m", "ruff"]
    befehle = {
        "ruff check": [*ruff, "check", *BEREICHE],
        "ruff format": [*ruff, "format", "--check", *BEREICHE],
        "strukturregel": [py, "tools/strukturregel.py"],
        "importpruefung": [py, "tools/importpruefung.py", "."],
    }
    # Committetes prüft der Bereich seit der Basis, Offenes der Lauf ohne Bereich.
    # Ohne passende Änderung entfällt der Lauf; die Kommentarregel liest sonst den ganzen Bestand.
    bereiche = {"": "HEAD"}
    try:
        _git(repo, "rev-parse", "--verify", "-q", basis)
        bereiche[" seit " + basis] = f"{basis}...HEAD"
    except subprocess.CalledProcessError:
        pass
    for zusatz, bereich in bereiche.items():
        argumente = ["--bereich", bereich] if zusatz else []
        for regel, muster in (("kommentarregel", "*.py"), ("changelogregel", "CHANGELOG.md")):
            if _git(repo, "diff", "--name-only", bereich, "--", muster):
                befehle[regel + zusatz] = [py, f"tools/{regel}.py", *argumente]
    if tests:
        befehle["pytest " + " ".join(projekte)] = [
            py,
            "-m",
            "pytest",
            "--no-header",
            "-p",
            "no:cacheprovider",
            *tests,
        ]
    return befehle


def _umgebung(intern: Path | None) -> dict[str, str]:
    umgebung = {**os.environ, "PYTHONUTF8": "1"}
    stubs = intern / "windows-stubs" if intern else None
    # Unter Windows fehlen fcntl und resource; Ersatzmodule machen die HA-Tests lauffähig.
    if os.name == "nt" and stubs and stubs.is_dir():
        umgebung["PYTHONPATH"] = os.pathsep.join(
            filter(None, [str(stubs), os.environ.get("PYTHONPATH")])
        )
    return umgebung


def _bericht(baum: str, laeufe: list[Lauf]) -> None:
    print(f"pruefen: Baumstand {baum[:12]}, Ergebnis in {ABLAGE}/{baum}.json")
    for lauf in laeufe:
        herkunft = "gespeichert" if lauf.gespeichert else f"{lauf.sekunden:.0f} s"
        print(f"  {'grün' if lauf.rc == 0 else 'rot '}  {lauf.name} ({herkunft})")
        if lauf.rc != 0:
            print("\n".join("      " + zeile for zeile in lauf.ausgabe.splitlines()[-20:]))


def main(argv: list[str] | None = None) -> int:
    """0 alles grün, 1 etwas rot, 2 Aufruf fehlerhaft, 3 kein gespeichertes Ergebnis."""
    zerleger = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    zerleger.add_argument(
        "--projekt", action="append", default=[], help="Tests dieses Projekts (Pnn), mehrfach"
    )
    zerleger.add_argument(
        "--basis", default="origin/main", help="Vergleichsstand für Kommentar- und Changelogregel"
    )
    zerleger.add_argument("--neu", action="store_true", help="gespeicherte Ergebnisse übergehen")
    zerleger.add_argument(
        "--gespeichert", action="store_true", help="nur das gespeicherte Ergebnis als JSON"
    )
    zerleger.add_argument("--repo", default=str(REPO), help=argparse.SUPPRESS)
    argumente = zerleger.parse_args(argv)
    repo = Path(argumente.repo).resolve()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if argumente.gespeichert:
        daten = laden(repo, baumstand(repo))
        if not daten:
            return 3
        print(json.dumps(daten, ensure_ascii=False))
        return 0

    intern = intern_ordner(repo)
    tests: list[str] = []
    if argumente.projekt:
        if not intern:
            print(
                "pruefen: projekte.py nicht gefunden; HEATNEXUS_INTERN auf seinen Ordner setzen",
                file=sys.stderr,
            )
            return 2
        tests = testdateien(argumente.projekt, repo, intern / "projekte.py")
        if not tests:
            print(f"pruefen: keine Testdateien für {', '.join(argumente.projekt)}", file=sys.stderr)
            return 2
    befehle = _befehle(repo, argumente.basis, tests, [p.upper() for p in argumente.projekt])
    laeufe = pruefe(repo, befehle, umgebung=_umgebung(intern), neu=argumente.neu)
    _bericht(baumstand(repo), laeufe)
    return 1 if any(lauf.rc for lauf in laeufe) else 0


if __name__ == "__main__":
    sys.exit(main())
