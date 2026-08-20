"""Die Wortlautprüfung für neu hinzugekommene Changelog-Zeilen.

Geprüft wird, was anschlägt, was in Ruhe gelassen wird und dass nur neue
Zeilen zählen.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

WURZEL = Path(__file__).resolve().parents[1]


def _regel():
    if (vorhanden := sys.modules.get("changelogregel")) is not None:
        return vorhanden
    pfad = WURZEL / "tools" / "changelogregel.py"
    spezifikation = importlib.util.spec_from_file_location("changelogregel", pfad)
    modul = importlib.util.module_from_spec(spezifikation)
    # Vor dem Ausführen eintragen: `dataclass` schlägt sonst das eigene Modul
    # in `sys.modules` nach und findet nichts.
    sys.modules["changelogregel"] = modul
    spezifikation.loader.exec_module(modul)
    return modul


def _arten(text: str) -> list[str]:
    befunde = _regel().pruefe("CHANGELOG.md", f"- {text}")
    return [befund.art for befund in befunde]


def test_possessiv_vor_einem_hauptwort_schlaegt_an():
    assert "Possessivpronomen" in _arten("Der Kaminkehrer zeigt seine Restlaufzeit in Minuten.")
    assert "Possessivpronomen" in _arten("Wartungszähler behalten ihre Tageswerte.")


def test_sein_als_verb_bleibt_unbeanstandet():
    assert _arten("Einstellbar, wie alt übernommene Startwerte höchstens sein dürfen.") == []


def test_personifizierendes_verb_schlaegt_an():
    assert "personifizierendes Verb" in _arten("Brennstoffart kennt zusätzlich Hackgut trocken.")
    assert "personifizierendes Verb" in _arten("Zählerstände bekommen einen Langzeitverlauf.")


def test_anrede_schlaegt_an():
    assert "Anrede" in _arten("Nach dem Start finden Sie die Werte im Panel.")


def test_fettdruck_am_anfang_schlaegt_an():
    assert "Fettdruck am Zeilenanfang" in _arten("**Neu:** Die Karte zeigt mehr.")


def test_zu_lange_zeile_schlaegt_an():
    lang = "Die Karte zeigt nun auch dann noch alle Werte an, wenn das Fenster sehr schmal wird."
    assert any(art.endswith(f"(erlaubt {_regel().MAX_WOERTER})") for art in _arten(lang))


def test_ein_verweis_zaehlt_nicht_zur_laenge():
    kurz = (
        "Anlagen mit vielen Datenpunkten lasen keine Werte mehr ([#2](https://example.invalid/2))."
    )
    assert _arten(kurz) == []


def test_wortwiederholung_schlaegt_an():
    assert "Wortwiederholung" in _arten(
        "Eigene Sensoren in der Werteliste, in einem eigenen Abschnitt."
    )


def test_zusammensetzungen_mit_gleichem_anfang_bleiben_unbeanstandet():
    assert _arten("Systemuhr und Systemdatum erscheinen nicht mehr ungefragt.") == []
    assert _arten("Der Betriebszustand zeigt wieder die Betriebsphase.") == []


def test_ein_zitierter_name_darf_sich_wiederholen():
    umbenannt = '„Laufzeit aktuell" heißt „Laufzeit Zyklus" und zeigt den letzten Lauf.'
    assert _arten(umbenannt) == []


def test_funktionswoerter_zaehlen_nicht_als_wiederholung():
    assert _arten("Ein Anlagenteil, das nicht antwortet, hält die Einrichtung nicht auf.") == []


def test_ueberschriften_und_fliesstext_bleiben_aussen_vor():
    regel = _regel()
    quelle = "### Neu\n\nEin Absatz mit ihrer Formulierung und seinem Possessiv.\n"
    assert regel.pruefe("CHANGELOG.md", quelle) == []


def test_nur_die_genannten_zeilen_werden_geprueft():
    regel = _regel()
    quelle = (
        "- Wartungszähler behalten ihre Tageswerte.\n- Die Meldungsliste ist wieder verfügbar.\n"
    )
    assert regel.pruefe("CHANGELOG.md", quelle, zeilen={2}) == []
    assert len(regel.pruefe("CHANGELOG.md", quelle, zeilen={1})) == 1


def test_der_abschnitt_der_laufenden_fassung_ist_sauber():
    """Was diese Fassung veröffentlicht, muss die eigene Regel bestehen."""
    regel = _regel()
    text = (WURZEL / "CHANGELOG.md").read_text(encoding="utf-8")
    beginn = text.index("## [1.10.0] - ")
    ende = text.index("## [1.10.0-beta.3]")
    assert regel.pruefe("CHANGELOG.md", text[beginn:ende]) == []
