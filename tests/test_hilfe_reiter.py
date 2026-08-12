"""Die Suche im Hilfe-Reiter.

Gefiltert wird im Browser, geprüft wird deshalb in Node — dieselbe Rechnung,
dieselbe Datei. Zwei Fälle tragen den Rest: Die Suche muss auch im Text
greifen, nicht nur im Titel (wer einen Begriff sucht, kennt die Überschrift
meist nicht), und Groß- und Kleinschreibung darf keine Rolle spielen.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

MODUL = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "heatnexus"
    / "frontend"
    / "teile"
    / "hilfe.js"
)

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")


@pytest.fixture(scope="module")
def rechnung(tmp_path_factory) -> dict:
    """Die reine Filterfunktion einmal in Node ausführen."""
    skript = tmp_path_factory.mktemp("hilfe") / "pruefung.mjs"
    adresse = MODUL.resolve().as_uri()
    skript.write_text(
        f"""
import {{ filtern }} from "{adresse}";

const eintraege = [
  {{ titel: "Serviceausbrand", text: "Brennt den Kessel gezielt aus." }},
  {{ titel: "Warmwasser", text: "Der eingestellte Wert ist der Ausschaltpunkt." }},
];

console.log(
  JSON.stringify({{
    leer: filtern(eintraege, "").length,
    nur_leerzeichen: filtern(eintraege, "   ").length,
    im_titel: filtern(eintraege, "service").map((e) => e.titel),
    im_text: filtern(eintraege, "ausschaltpunkt").map((e) => e.titel),
    gross_klein: filtern(eintraege, "SERVICE").map((e) => e.titel),
    ohne_treffer: filtern(eintraege, "Dampfmaschine").length,
    leere_liste: filtern([], "service").length,
  }})
);
""",
        encoding="utf-8",
    )
    ausgabe = subprocess.run(
        ["node", str(skript)], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return json.loads(ausgabe.stdout)


def test_ohne_suche_bleibt_alles_stehen(rechnung):
    assert rechnung["leer"] == 2
    assert rechnung["nur_leerzeichen"] == 2


def test_die_suche_greift_im_titel(rechnung):
    assert rechnung["im_titel"] == ["Serviceausbrand"]


def test_die_suche_greift_auch_im_text(rechnung):
    """Wer nach einem Begriff sucht, kennt die Überschrift nicht."""
    assert rechnung["im_text"] == ["Warmwasser"]


def test_gross_und_kleinschreibung_spielt_keine_rolle(rechnung):
    assert rechnung["gross_klein"] == ["Serviceausbrand"]


def test_ohne_treffer_bleibt_die_liste_leer(rechnung):
    assert rechnung["ohne_treffer"] == 0
    assert rechnung["leere_liste"] == 0
