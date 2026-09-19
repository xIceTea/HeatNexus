"""Regeln im Stil der Oberfläche, die sich ohne Browser prüfen lassen."""

from __future__ import annotations

from pathlib import Path
import re

WURZEL = Path(__file__).resolve().parents[1]
STIL = (WURZEL / "custom_components" / "heatnexus" / "frontend" / "stil.js").read_text(
    encoding="utf-8"
)


def _regel(auswahl: str) -> str:
    """Der Rumpf einer CSS-Regel."""
    treffer = re.search(re.escape(auswahl) + r"\s*\{([^}]*)\}", STIL)
    assert treffer, f"Regel {auswahl} fehlt"
    return treffer.group(1)


def test_laufendes_rad_bekommt_eigene_ebene():
    """Ohne eigene Ebene rastert WebKit das Rad im skalierten Elternkasten neu."""
    assert "will-change: transform" in _regel(".schaubild .pumpe.laeuft .rad")


def test_laufende_pumpe_bleibt_zentriert():
    """Die Vergrößerung darf die Marke nicht von ihrem Punkt schieben."""
    assert "translate(-50%, -50%)" in _regel(".schaubild .pumpe.laeuft")
