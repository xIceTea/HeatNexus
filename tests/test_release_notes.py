"""Der Release-Text bekommt die Symbole seiner Abschnitte."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PFAD = Path(__file__).resolve().parents[1] / "tools" / "release_notes.py"
_SPEC = importlib.util.spec_from_file_location("release_notes", _PFAD)
release_notes = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(release_notes)


def test_das_highlight_bekommt_seinen_stern():
    text = release_notes.mit_symbolen("### Highlight: Meldungsliste\n\n### Neu")
    assert text == "### 🌟 Highlight: Meldungsliste\n\n### ✨ Neu"


def test_ein_unbekannter_abschnitt_bleibt_unveraendert():
    assert release_notes.mit_symbolen("### Sonstiges") == "### Sonstiges"
