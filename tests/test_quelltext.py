r"""Steuerzeichen im Quelltext.

Ein `\b`, das beim Schreiben zum Rückschritt-Zeichen wird, macht einen regulären
Ausdruck blind, ohne dass ein Test fehlschlägt.
"""

from __future__ import annotations

from pathlib import Path

WURZEL = Path(__file__).parent.parent
ENDUNGEN = {".py", ".js", ".mjs", ".json", ".yaml", ".md"}


def test_kein_rueckschritt_zeichen_im_quelltext():
    ordner = ("custom_components", "tests", "tools", "docs")
    dateien = [
        p
        for name in ordner
        for p in (WURZEL / name).rglob("*")
        if p.suffix in ENDUNGEN and "__pycache__" not in p.parts
    ]
    betroffen = [str(p.relative_to(WURZEL)) for p in dateien if b"\x08" in p.read_bytes()]
    assert betroffen == []
