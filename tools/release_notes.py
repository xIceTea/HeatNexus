#!/usr/bin/env python3
"""Release-Text aus dem Changelog erzeugen.

Der Changelog folgt Keep a Changelog und bleibt schmucklos – dort gehören
Symbole nicht hin. Die Release-Seite auf GitHub liest sich mit ihnen besser,
also entstehen sie hier, beim Übertragen, und nicht in der Quelle.

Aufruf:

    python tools/release_notes.py 1.8.0-beta.1
    python tools/release_notes.py 1.8.0-beta.1 --out probe/notes.md

Ohne ``--out`` steht der Text auf der Standardausgabe und lässt sich direkt
weiterreichen:

    gh release create v1.8.0 --notes-file <(python tools/release_notes.py 1.8.0)
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"

# Symbol je Abschnitt. Die Schlüssel sind die Überschriften, die der Changelog
# tatsächlich benutzt; unbekannte Abschnitte bleiben unverändert, statt ein
# beliebiges Zeichen zu bekommen.
SYMBOLE = {
    "Beim Aktualisieren": "⚠️",
    "Neu": "✨",
    "Geändert": "🔧",
    "Behoben": "🐛",
    "Entfernt": "🗑️",
    "Veraltet": "⚠️",
    "Sicherheit": "🔒",
}

DANK = "Dank an {namen} für die beigesteuerten Anlagendaten."


def abschnitt(text: str, version: str) -> str:
    """Den Block einer Fassung aus dem Changelog schneiden."""
    beginn = re.search(rf"^## \[{re.escape(version)}\][^\n]*$", text, re.M)
    if not beginn:
        raise SystemExit(f"Fassung {version} steht nicht im Changelog")
    rest = text[beginn.end() :]
    naechste = re.search(r"^## \[", rest, re.M)
    return (rest[: naechste.start()] if naechste else rest).strip()


def mit_symbolen(block: str) -> str:
    """Die Abschnittsüberschriften mit ihrem Symbol versehen."""

    def ersetzen(treffer: re.Match) -> str:
        titel = treffer.group(1).strip()
        symbol = SYMBOLE.get(titel)
        return f"### {symbol} {titel}" if symbol else treffer.group(0)

    return re.sub(r"^### ([^\n]+)$", ersetzen, block, flags=re.M)


def main() -> int:
    parser = argparse.ArgumentParser(description="Release-Text aus dem Changelog")
    parser.add_argument("version", help="Fassung ohne führendes v, z. B. 1.8.0")
    parser.add_argument("--out", help="Zieldatei (sonst Standardausgabe)")
    parser.add_argument(
        "--dank",
        nargs="*",
        metavar="NAME",
        help="Beitragende, die unter dem Text genannt werden (ohne @)",
    )
    args = parser.parse_args()

    block = mit_symbolen(abschnitt(CHANGELOG.read_text(encoding="utf-8"), args.version))
    if args.dank:
        namen = ", ".join(f"@{n.lstrip('@')}" for n in args.dank)
        block += "\n\n---\n\n" + DANK.format(namen=namen)

    if args.out:
        Path(args.out).write_text(block + "\n", encoding="utf-8")
        print(f"-> {args.out}", file=sys.stderr)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(block)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
