"""Die Längenprüfung für neu hinzugekommene Kommentare.

Geprüft wird, dass nur neue Zeilen anschlagen und bestehender Text in Ruhe
gelassen wird.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

WURZEL = Path(__file__).resolve().parents[1]


def _regel():
    if (vorhanden := sys.modules.get("kommentarregel")) is not None:
        return vorhanden
    pfad = WURZEL / "tools" / "kommentarregel.py"
    spezifikation = importlib.util.spec_from_file_location("kommentarregel", pfad)
    modul = importlib.util.module_from_spec(spezifikation)
    # Vor dem Ausführen eintragen: `dataclass` schlägt sonst das eigene Modul
    # in `sys.modules` nach und findet nichts.
    sys.modules["kommentarregel"] = modul
    spezifikation.loader.exec_module(modul)
    return modul


LANGER_BLOCK = '''"""Kurz."""

# eins
# zwei
# drei
# vier
wert = 1
'''


def test_langer_kommentarblock_faellt_auf():
    regel = _regel()
    befunde = regel.pruefe("a.py", LANGER_BLOCK, neue_zeilen={3, 4, 5, 6})
    assert len(befunde) == 1
    assert "Kommentarblock mit 4 Zeilen" in befunde[0].art


def test_bestehender_block_bleibt_unangetastet():
    """Ohne neue Zeile im Block gibt es nichts zu melden."""
    regel = _regel()
    assert regel.pruefe("a.py", LANGER_BLOCK, neue_zeilen={7}) == []


def test_drei_zeilen_sind_erlaubt():
    regel = _regel()
    quelle = "# eins\n# zwei\n# drei\nwert = 1\n"
    assert regel.pruefe("a.py", quelle, neue_zeilen={1, 2, 3}) == []


def test_langer_docstring_faellt_auf():
    regel = _regel()
    quelle = '''def f():
    """Zusammenfassung.

    eins
    zwei
    drei
    vier
    """
'''
    befunde = regel.pruefe("a.py", quelle, neue_zeilen={4, 5, 6, 7})
    assert len(befunde) == 1
    assert "Docstring mit 4 Zeilen" in befunde[0].art


def test_leerzeilen_zaehlen_nicht_mit():
    """Sie gliedern einen Docstring, sie erzählen nicht."""
    regel = _regel()
    quelle = '''def f():
    """Zusammenfassung.

    eins

    zwei

    drei
    """
'''
    assert regel.pruefe("a.py", quelle, neue_zeilen=set(range(1, 10))) == []


def test_diff_liefert_die_nummern_der_neuen_zeilen():
    regel = _regel()
    diff = "\n".join(
        [
            "diff --git a/x.py b/x.py",
            "--- a/x.py",
            "+++ b/x.py",
            "@@ -3,0 +4,2 @@",
            "+# eins",
            "+# zwei",
        ]
    )
    assert regel.neue_zeilen(diff) == {"x.py": {4, 5}}


def test_die_eigenen_werkzeuge_halten_die_regel_ein():
    """Was die Regel prüft, muss sie selbst erfüllen."""
    regel = _regel()
    quelle = (WURZEL / "tools" / "kommentarregel.py").read_text(encoding="utf-8")
    alle = set(range(1, len(quelle.splitlines()) + 1))
    assert regel.pruefe("kommentarregel.py", quelle, alle) == []
