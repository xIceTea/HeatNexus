"""Prüft, ob jeder paketinterne Import auflösbar ist.

`ruff` prüft Namen, nicht Importziele: `from .const import Tippfehler` fällt
erst zur Laufzeit auf. Aufruf: `python tools/importpruefung.py [wurzel]`
"""

from __future__ import annotations

import ast
from pathlib import Path
import sys

PAKET = Path("custom_components/heatnexus")


def oeffentliche_namen(modul: Path) -> set[str] | None:
    """Was ein Modul auf oberster Ebene bereitstellt."""
    if not modul.is_file():
        return None
    baum = ast.parse(modul.read_text(encoding="utf-8"))
    namen: set[str] = set()
    for knoten in baum.body:
        if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            namen.add(knoten.name)
        elif isinstance(knoten, ast.Assign):
            namen |= {z.id for z in knoten.targets if isinstance(z, ast.Name)}
        elif isinstance(knoten, ast.AnnAssign) and isinstance(knoten.target, ast.Name):
            namen.add(knoten.target.id)
        elif isinstance(knoten, (ast.Import, ast.ImportFrom)):
            namen |= {a.asname or a.name.split(".")[0] for a in knoten.names}
    return namen


def ziel(datei: Path, knoten: ast.ImportFrom, wurzel: Path) -> Path | None:
    """Die Datei, auf die ein relativer Import zeigt."""
    ordner = datei.parent
    for _ in range(knoten.level - 1):
        ordner = ordner.parent
    if not knoten.module:
        return None
    pfad = ordner / Path(*knoten.module.split("."))
    if (pfad / "__init__.py").is_file():
        return pfad / "__init__.py"
    return pfad.with_suffix(".py")


def pruefe(wurzel: Path) -> list[str]:
    befunde = []
    for datei in sorted((wurzel / PAKET).rglob("*.py")):
        if "__pycache__" in datei.parts:
            continue
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.ImportFrom) or not knoten.level:
                continue
            quelle = ziel(datei, knoten, wurzel)
            if quelle is None:
                continue
            vorhanden = oeffentliche_namen(quelle)
            if vorhanden is None:
                befunde.append(f"{datei.relative_to(wurzel)}:{knoten.lineno} — {quelle.name} fehlt")
                continue
            for eintrag in knoten.names:
                if eintrag.name != "*" and eintrag.name not in vorhanden:
                    befunde.append(
                        f"{datei.relative_to(wurzel)}:{knoten.lineno} — "
                        f"{quelle.stem} führt kein {eintrag.name}"
                    )
    return befunde


if __name__ == "__main__":
    wurzel = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    befunde = pruefe(wurzel)
    for b in befunde:
        print(b)
    print(f"{len(befunde)} Befunde")
    raise SystemExit(1 if befunde else 0)
