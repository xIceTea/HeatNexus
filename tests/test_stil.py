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


def test_verborgene_elemente_bleiben_verborgen():
    """Eine Klasse mit eigenem `display` schlägt sonst die Browserregel für `hidden`."""
    treffer = re.search(r"(?m)^\s*\[hidden\]\s*\{([^}]*)\}", STIL)
    assert treffer, "Regel [hidden] fehlt"
    assert "display: none !important" in treffer.group(1)


def test_stehende_pumpe_folgt_dem_farbsatz():
    """Ein fester dunkler Grund wirkt im hellen Farbsatz wie ein Loch."""
    assert "var(--hn-karte" in _regel(".schaubild .pumpe")
