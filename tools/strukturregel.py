"""Hält Komplexität und Länge der Funktionen unter einer Grenze.

Neue Funktionen bleiben unter `GRENZEN`. Was schon darüber liegt, steht mit
seinem Stand in `strukturregel.json` und darf nicht wachsen. `--aktualisieren`
schreibt den aktuellen Stand fest; ein Rückgang zieht die Grenze mit.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import subprocess
import sys

REPO = Path(__file__).resolve().parent.parent
QUELLE = REPO / "custom_components" / "heatnexus"
STAND = Path(__file__).with_suffix(".json")
GRENZEN = {"komplexitaet": 15, "zeilen": 80}


def komplexitaeten() -> dict[tuple[str, int], int]:
    """McCabe-Zahl je Funktion aus ruff, geschlüsselt nach Datei und Zeile."""
    ausgabe = subprocess.run(
        [
            *("ruff", "check", str(QUELLE), "--select", "C901", "--output-format", "json"),
            *("--config", "lint.mccabe.max-complexity=0", "--exit-zero", "-q"),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    ergebnis: dict[tuple[str, int], int] = {}
    for fund in json.loads(ausgabe or "[]"):
        if m := re.search(r"\((\d+) > 0\)", fund["message"]):
            datei = Path(fund["filename"]).resolve().relative_to(REPO).as_posix()
            ergebnis[(datei, fund["location"]["row"])] = int(m.group(1))
    return ergebnis


def funktionen() -> dict[str, dict[str, int]]:
    """Komplexität und Zeilen je Funktion, Schlüssel `datei::Klasse.funktion`."""
    mccabe = komplexitaeten()
    werte: dict[str, dict[str, int]] = {}

    def besuchen(knoten: ast.AST, datei: str, praefix: str) -> None:
        for kind in ast.iter_child_nodes(knoten):
            if isinstance(kind, ast.ClassDef):
                besuchen(kind, datei, f"{praefix}{kind.name}.")
            elif isinstance(kind, ast.FunctionDef | ast.AsyncFunctionDef):
                name = f"{datei}::{praefix}{kind.name}"
                neu = {
                    "komplexitaet": mccabe.get((datei, kind.lineno), 1),
                    "zeilen": (kind.end_lineno or kind.lineno) - kind.lineno + 1,
                }
                alt = werte.get(name, {})
                werte[name] = {k: max(v, alt.get(k, 0)) for k, v in neu.items()}
                besuchen(kind, datei, f"{praefix}{kind.name}.")

    for pfad in sorted(QUELLE.rglob("*.py")):
        datei = pfad.relative_to(REPO).as_posix()
        besuchen(ast.parse(pfad.read_text(encoding="utf-8")), datei, "")
    return werte


def ueber_grenze(werte: dict[str, int]) -> dict[str, int]:
    """Nur die Größen, die eine Grenze überschreiten."""
    return {k: v for k, v in werte.items() if v > GRENZEN[k]}


def pruefen(aktuell: dict[str, dict[str, int]], stand: dict[str, dict[str, int]]) -> list[str]:
    """Befunde: neu über der Grenze oder über dem festgeschriebenen Stand."""
    befunde = []
    for name, werte in sorted(aktuell.items()):
        erlaubt = stand.get(name, {})
        for groesse, wert in ueber_grenze(werte).items():
            if wert > erlaubt.get(groesse, GRENZEN[groesse]):
                bis = erlaubt.get(groesse, GRENZEN[groesse])
                befunde.append(f"{name} – {groesse} {wert}, erlaubt {bis}")
    return befunde


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--aktualisieren", action="store_true", help="Stand festschreiben")
    args = parser.parse_args()

    aktuell = funktionen()
    stand = json.loads(STAND.read_text(encoding="utf-8")) if STAND.exists() else {}
    neu = {name: g for name, werte in aktuell.items() if (g := ueber_grenze(werte))}

    if args.aktualisieren:
        STAND.write_text(
            json.dumps(neu, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"{len(neu)} Funktionen über der Grenze festgeschrieben: {STAND.name}")
        return 0

    befunde = pruefen(aktuell, stand)
    for befund in befunde:
        print(befund)
    gesunken = [n for n in stand if neu.get(n) != stand[n]] if not befunde else []
    if gesunken:
        print(f"Gesunken oder entfallen: {', '.join(gesunken)} – `--aktualisieren` zieht nach.")
    print(f"{len(befunde)} Befunde")
    return 1 if befunde else 0


if __name__ == "__main__":
    sys.exit(main())
