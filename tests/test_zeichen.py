"""Das Zeichen im Panel entsteht aus der Vorlage und trägt keine festen Kennungen."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

WURZEL = Path(__file__).resolve().parent.parent
WERKZEUG = WURZEL / "tools" / "build_zeichen.py"


def _werkzeug():
    sys.path.insert(0, str(WERKZEUG.parent))
    spec = importlib.util.spec_from_file_location("build_zeichen", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_das_zeichen_im_panel_traegt_keine_feste_kennung():
    # Mehrere Zeichen im selben Schattenbaum dürfen keine `id` doppelt führen.
    assert 'id="zeichen-' not in _werkzeug().zeichen_js()


def test_zeichen_js_entspricht_der_vorlage():
    werkzeug = _werkzeug()
    assert werkzeug.ZEICHEN_JS.read_text(encoding="utf-8") == werkzeug.zeichen_js()
