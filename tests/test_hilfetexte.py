r"""Die Erklärungen hinter den „?" der Oberfläche.

Warum eigene Tests dafür: Die Texte sind mehrzeilig, und beim Schreiben der
Datei ging schon einmal ein `\\n` als echtes Steuerzeichen in ein
Zeichenkettenliteral – die Datei war danach nicht mehr lesbar. Ein anderes Mal
stand statt `\\b` ein Rückschritt-Zeichen im Muster, unsichtbar in jeder
Suche, und ein ganzer Abschnitt der Oberfläche verschwand.

Die Prüfung liest die Dateien als Quelltext ein, statt sie zu importieren:
Das Paket zieht Home Assistant nach, die Texte hängen aber an nichts. So läuft
der Test auch auf einem Rechner ohne HA.
"""

from __future__ import annotations

import ast
from pathlib import Path
import re

import pytest

PANEL = Path(__file__).resolve().parents[1] / "custom_components" / "heatnexus" / "panel"

# Wo welche Konstante steht. Seit dem Schnitt von `panel.py` in ein Paket
# liegen die Erklärtexte in `hilfe.py` und die Mustertabellen in `muster.py`.
QUELLEN = (PANEL / "hilfe.py", PANEL / "muster.py", PANEL / "daten.py")


def _konstante(name: str):
    """Eine Konstante des Panel-Pakets, ohne das Modul zu laden."""
    for quelle in QUELLEN:
        if (wert := _aus_datei(quelle, name)) is not None:
            return wert
    raise AssertionError(f"{name} in keiner Quelle gefunden")


def _aus_datei(quelle: Path, name: str):
    """Eine Konstante aus einer Datei – oder None, wenn sie dort nicht steht."""
    baum = ast.parse(quelle.read_text(encoding="utf-8"))
    for knoten in baum.body:
        ziele = []
        if isinstance(knoten, ast.AnnAssign):
            ziele = [knoten.target]
        elif isinstance(knoten, ast.Assign):
            ziele = knoten.targets
        if any(getattr(z, "id", "") == name for z in ziele):
            return ast.literal_eval(knoten.value)
    return None


@pytest.fixture(scope="module")
def hilfe():
    return _konstante("HILFE")


@pytest.fixture(scope="module")
def karten():
    return _konstante("HILFE_KARTEN")


def test_muster_sind_uebersetzbar(hilfe):
    for muster, _text in hilfe:
        re.compile(muster)


def test_texte_ohne_steuerzeichen(hilfe, karten):
    """Nur Zeilenumbrüche sind erlaubt – alles andere ist ein Unfall."""
    for muster, text in hilfe:
        schlimm = {c for c in text if ord(c) < 32 and c != "\n"}
        assert not schlimm, f"{muster}: {[hex(ord(c)) for c in schlimm]}"
    for titel, text in karten.items():
        assert not any(ord(c) < 32 for c in text), titel


def test_muster_enthalten_keine_steuerzeichen(hilfe):
    r"""`\b` im Muster heißt Wortgrenze, nicht Rückschritt."""
    for muster, _text in hilfe:
        assert not any(ord(c) < 32 for c in muster), repr(muster)


def test_texte_sind_gehaltvoll(hilfe, karten):
    for muster, text in hilfe:
        assert len(text) > 40, muster
    for titel, text in karten.items():
        assert len(text) > 40, titel


def test_bedientasten_haben_eine_erklaerung():
    """Jede Taste der Kesselkarte findet ihren Text.

    Gesucht wird zweimal: über den Namen des Datenpunkts, den die Anlage
    meldet, und über die Beschriftung in der Oberfläche. Nur der zweite Weg
    lässt sich hier prüfen – er ist der Rückfall, wenn eine Anlage den
    Datenpunkt anders benennt.
    """
    hilfe = _konstante("HILFE")

    def text_zu(name: str) -> str:
        for muster, text in hilfe:
            if re.search(muster, name, re.IGNORECASE):
                return text
        return ""

    for _muster, beschriftung, _symbol in _konstante("KESSEL_BEDIENUNG"):
        assert text_zu(beschriftung), beschriftung


def test_brennstoff_nennt_die_grenzwerte():
    """Wann „normal", wann „feucht", wann „schlackend"? Das war die Frage.

    Ohne Zahlen ist der Text nutzlos – deshalb stehen sie hier fest.
    """
    hilfe = dict(_konstante("HILFE"))
    text = next(t for m, t in hilfe.items() if "brennstoff" in m)
    for zahl in ("15 bis 30", "35", "1,5"):
        assert zahl in text
    assert "Hauptschalter" in text, "Der Hinweis auf die Wirksamkeit fehlt"
