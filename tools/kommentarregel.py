"""Prüft neu hinzugekommene Kommentare und Docstrings auf ihre Länge.

Erlaubt sind höchstens drei Zeilen je Block; geprüft wird nur, was eine
Änderung hinzufügt. `--datei`, `--gestaged` und `--bereich` wählen die Quelle.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import io
from pathlib import Path
import re
import subprocess
import sys
import tokenize

MAX_ZEILEN = 3


@dataclass(frozen=True)
class Befund:
    """Eine Fundstelle: Datei, Zeile, Art, Anfang des Textes."""

    datei: str
    zeile: int
    art: str
    text: str

    def __str__(self) -> str:
        """Eine Zeile für Hook, CI und Kommandozeile."""
        return f"{self.datei}:{self.zeile} – {self.art}: „{self.text}“"


def kommentarbloecke(quelle: str) -> list[tuple[int, int, str]]:
    """Zusammenhängende Kommentarzeilen als (erste Zeile, Anzahl, Anfang)."""
    bloecke: list[tuple[int, int, str]] = []
    start = letzte = 0
    anfang = ""
    try:
        marken = list(tokenize.generate_tokens(io.StringIO(quelle).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return bloecke
    for marke in marken:
        # Nur Kommentare, die eine Zeile für sich haben. Was hinter Code steht,
        # gehört zu dieser Zeile und bildet keinen Block.
        if marke.type != tokenize.COMMENT or marke.line[: marke.start[1]].strip():
            continue
        zeile = marke.start[0]
        if start and zeile == letzte + 1:
            letzte = zeile
            continue
        if start:
            bloecke.append((start, letzte - start + 1, anfang))
        start = letzte = zeile
        anfang = marke.string.lstrip("# ").strip()
    if start:
        bloecke.append((start, letzte - start + 1, anfang))
    return bloecke


def docstrings(quelle: str) -> list[tuple[int, int, str]]:
    """Docstrings als (erste Zeile, Zeilen nach der Zusammenfassung, Anfang).

    Leerzeilen zählen nicht mit: Sie gliedern, sie erzählen nicht.
    """
    try:
        baum = ast.parse(quelle)
    except SyntaxError:
        return []
    gefunden: list[tuple[int, int, str]] = []
    traeger = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for knoten in ast.walk(baum):
        if not isinstance(knoten, traeger):
            continue
        text = ast.get_docstring(knoten, clean=False)
        if text is None:
            continue
        zeilen = text.splitlines()
        koerper = [z for z in zeilen[1:] if z.strip()]
        gefunden.append((knoten.body[0].lineno, len(koerper), zeilen[0].strip() or "(Docstring)"))
    return gefunden


def pruefe(datei: str, quelle: str, neue_zeilen: set[int]) -> list[Befund]:
    """Befunde einer Datei – nur Blöcke, die neue Zeilen enthalten."""
    befunde: list[Befund] = []
    for art, stellen, zugabe in (
        ("Kommentarblock", kommentarbloecke(quelle), 0),
        # Die beiden Zeilen mit den Anführungszeichen zählen zum Bereich.
        ("Docstring", docstrings(quelle), 2),
    ):
        for erste, laenge, anfang in stellen:
            bereich = set(range(erste, erste + max(laenge + zugabe, 1)))
            if laenge > MAX_ZEILEN and neue_zeilen & bereich:
                befunde.append(
                    Befund(
                        datei,
                        erste,
                        f"{art} mit {laenge} Zeilen (erlaubt {MAX_ZEILEN})",
                        anfang,
                    )
                )
    return befunde


def neue_zeilen(diff: str) -> dict[str, set[int]]:
    """Aus einem Diff je Datei die Nummern der hinzugefügten Zeilen lesen."""
    je_datei: dict[str, set[int]] = {}
    datei = ""
    zeile = 0
    for text in diff.splitlines():
        if text.startswith("+++ b/"):
            datei = text[6:]
            continue
        if kopf := re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", text):
            zeile = int(kopf.group(1))
            continue
        if text.startswith("+++") or text.startswith("---"):
            continue
        if text.startswith("+"):
            je_datei.setdefault(datei, set()).add(zeile)
            zeile += 1
        elif not text.startswith("-"):
            zeile += 1
    return je_datei


def pruefe_diff(diff: str, wurzel: Path, nur: str | None = None) -> list[Befund]:
    """Alle Python-Dateien eines Diffs prüfen, wahlweise nur eine davon."""
    befunde: list[Befund] = []
    for datei, zeilen in sorted(neue_zeilen(diff).items()):
        pfad = wurzel / datei
        if not datei.endswith(".py") or not pfad.is_file():
            continue
        if nur and datei != nur:
            continue
        befunde += pruefe(datei, pfad.read_text(encoding="utf-8"), zeilen)
    return befunde


def _git(*argumente: str, wurzel: Path) -> str:
    ergebnis = subprocess.run(
        ["git", *argumente], cwd=wurzel, capture_output=True, text=True, encoding="utf-8"
    )
    return ergebnis.stdout or ""


def main(argv: list[str] | None = None) -> int:
    """Befunde ausgeben; 1 heißt: es gibt welche."""
    zerleger = argparse.ArgumentParser(description="Kommentarlänge neuer Zeilen prüfen")
    zerleger.add_argument("--datei", help="nur diese Datei prüfen, repo-relativ")
    zerleger.add_argument("--gestaged", action="store_true", help="den vorgemerkten Stand prüfen")
    zerleger.add_argument("--bereich", help="einen Commit-Bereich prüfen, z.B. origin/main...HEAD")
    zerleger.add_argument("--wurzel", default=".", help="Wurzel des Repos")
    argumente = zerleger.parse_args(argv)

    wurzel = Path(argumente.wurzel).resolve()
    # `-M` erkennt Umbenennungen; ohne das gilt eine verschobene Datei als neu
    # und ihr ganzer Bestand schlüge an. Gefiltert wird erst danach, denn die
    # Erkennung braucht beide Seiten im Diff.
    auswahl = "--cached" if argumente.gestaged else (argumente.bereich or "HEAD")
    diff = _git("diff", auswahl, "--unified=0", "-M", "--", "*.py", wurzel=wurzel)
    nur = Path(argumente.datei).as_posix() if argumente.datei else None
    befunde = pruefe_diff(diff, wurzel, nur=nur)
    for befund in befunde:
        print(befund)
    return 1 if befunde else 0


if __name__ == "__main__":
    sys.exit(main())
