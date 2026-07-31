"""Mitgelieferte Automations-Vorlagen.

Die Vorlagen enthalten den Home-Assistant-Tag ``!input`` und lassen sich
darum nicht mit ``yaml.safe_load`` prüfen. Ein eigener Lader bildet den Tag
auf einen Platzhalter ab; damit ist die Datei trotzdem vollständig gegen
Syntaxfehler abgesichert.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

VORLAGEN = (
    Path(__file__).parent.parent
    / "custom_components"
    / "heatnexus"
    / "blueprints"
    / "automation"
    / "heatnexus"
)


class _Lader(yaml.SafeLoader):
    """SafeLoader, der ``!input`` kennt."""


_Lader.add_constructor("!input", lambda loader, node: {"__input__": node.value})


def _dateien() -> list[Path]:
    return sorted(VORLAGEN.glob("*.yaml"))


def test_vorlagen_vorhanden():
    assert _dateien(), "Es wird keine einzige Automations-Vorlage mitgeliefert"


@pytest.mark.parametrize("datei", _dateien(), ids=lambda p: p.name)
def test_vorlage_ist_gueltig(datei: Path):
    inhalt = yaml.load(datei.read_text(encoding="utf-8"), Loader=_Lader)
    blueprint = inhalt["blueprint"]
    assert blueprint["domain"] == "automation"
    assert blueprint["name"].startswith("HeatNexus")
    assert blueprint["description"].strip()
    assert blueprint["input"], "Vorlage ohne Eingabefelder"
    # Ein Auslöser ist Pflicht, sonst löst die Automation nie aus.
    assert inhalt.get("triggers") or inhalt.get("trigger")


@pytest.mark.parametrize("datei", _dateien(), ids=lambda p: p.name)
def test_eingaben_werden_benutzt(datei: Path):
    text = datei.read_text(encoding="utf-8")
    inhalt = yaml.load(text, Loader=_Lader)
    for name in inhalt["blueprint"]["input"]:
        assert f"!input {name}" in text, f"Eingabefeld {name} wird nirgends verwendet"
