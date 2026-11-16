"""Zeitprogramme lesen: Klartext und Stufen einer Tageszeile.

Je Block steht eine Spur in einer Farbe und darunter der Klartext. Beides wird
aus den Abschnitten gerechnet; geprüft wird diese Rechnung in Node.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "custom_components" / "heatnexus" / "frontend"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")

GESCHUETZT = " "


@pytest.fixture(scope="module")
def ansicht(tmp_path_factory) -> dict:
    """Klartext und Stufen für typische Tage in Node rechnen."""
    skript = tmp_path_factory.mktemp("ansicht") / "ansicht.mjs"
    modul = (FRONTEND / "zeitprogramm.js").resolve().as_uri()
    seite = (FRONTEND / "zeitprogrammseite.js").resolve().as_uri()
    skript.write_text(
        f"""
import {{ abschnitte, skala }} from "{modul}";
import {{ blockEinsetzen, klartext, stufen }} from "{seite}";

const p = (paare) => paare.map(([zeit, wert]) => ({{ zeit, wert }}));
const tag = (paare) => abschnitte(p(paare));
const raum = (paare) => skala([{{ tage: ["Mo"], punkte: p(paare) }}], "raum");
const schalt = skala([{{ tage: ["Mo"], punkte: p([[360, 1], [450, 0]]) }}]);

const werktag = [[330, 21], [480, 18], [960, 21.5], [1320, 18]];
const nacht = [[360, 18], [1320, 22]];
const woche = [
  {{ tage: ["Mo", "Tu", "We", "Th", "Fr"], punkte: p([[360, 21], [1320, 16]]) }},
  {{ tage: ["Sa", "Su"], punkte: p([[450, 21]]) }},
];
const vorher = JSON.stringify(woche);
const mitSamstag = blockEinsetzen(woche, 0, {{ tage: ["Mo", "Tu", "We", "Th", "Fr", "Sa"], punkte: p([[360, 21], [1320, 16]]) }});
const ganzeWoche = blockEinsetzen(woche, 0, {{ tage: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"], punkte: p([[360, 21]]) }});
const neuerBlock = blockEinsetzen([woche[0]], -1, {{ tage: ["Sa", "Su"], punkte: p([[480, 20]]) }});
const ohneTage = blockEinsetzen(woche, 1, {{ tage: [], punkte: p([[450, 21]]) }});
const englisch = (text) => ({{ "sonst {{wert}}": "otherwise {{wert}}" }})[text] || text;

console.log(JSON.stringify({{
  werktag: klartext(tag(werktag), raum(werktag), {{ sprache: "de" }}),
  werktag_englisch: klartext(tag(werktag), raum(werktag), {{ sprache: "en", t: englisch }}),
  ganztags: klartext(tag([[0, 20]]), raum([[0, 20]]), {{ sprache: "de" }}),
  ueber_mitternacht: klartext(tag(nacht), raum(nacht), {{ sprache: "de" }}),
  zirkulation: klartext(tag([[360, 1], [450, 0], [1080, 1], [1140, 0]]), schalt, {{ sprache: "de" }}),
  nie_an: klartext(tag([[360, 0]]), schalt, {{ sprache: "de" }}),
  leer: klartext([], raum(werktag), {{ sprache: "de" }}),
  stufen_werktag: stufen(tag(werktag), raum(werktag)),
  stufen_zwei_werte: stufen(tag([[360, 21], [1320, 17]]), raum([[360, 21], [1320, 17]])),
  stufen_schalt: stufen(tag([[360, 1], [450, 0]]), schalt),
  mit_samstag: mitSamstag.map((b) => b.tage),
  ganze_woche: ganzeWoche.map((b) => b.tage),
  neuer_block: neuerBlock.map((b) => [b.tage, b.punkte]),
  ohne_tage: ohneTage.map((b) => b.tage),
  unveraendert: JSON.stringify(woche) === vorher,
}}));
""",
        encoding="utf-8",
    )
    ausgabe = subprocess.run(
        ["node", str(skript)], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return json.loads(ausgabe.stdout)


def test_klartext_nennt_jedes_fenster_und_den_grundwert(ansicht):
    assert ansicht["werktag"] == [
        f"05:30–08:00 · 21,0{GESCHUETZT}°C",
        f"16:00–22:00 · 21,5{GESCHUETZT}°C",
        f"sonst 18,0{GESCHUETZT}°C",
    ]


def test_klartext_folgt_sprache_und_zahlformat(ansicht):
    assert ansicht["werktag_englisch"][0] == f"05:30–08:00 · 21.0{GESCHUETZT}°C"
    assert ansicht["werktag_englisch"][-1] == f"otherwise 18.0{GESCHUETZT}°C"


def test_ein_einziger_wert_gilt_ganztags(ansicht):
    assert ansicht["ganztags"] == [f"ganztags 20,0{GESCHUETZT}°C"]


def test_ein_fenster_ueber_mitternacht_steht_als_eines(ansicht):
    assert ansicht["ueber_mitternacht"] == [
        f"22:00–06:00 · 22,0{GESCHUETZT}°C",
        f"sonst 18,0{GESCHUETZT}°C",
    ]


def test_schaltprogramm_nennt_nur_die_zeiten_mit_an(ansicht):
    assert ansicht["zirkulation"] == ["an 06:00–07:30", "18:00–19:00"]
    assert ansicht["nie_an"] == ["immer aus"]


def test_ein_tag_ohne_abschnitte_hat_keinen_plan(ansicht):
    assert ansicht["leer"] == ["kein Zeitplan"]


def test_hoechster_wert_voll_zwischenwerte_halb_grundwert_leer(ansicht):
    # Umlauf 18, 21, 18, 21,5, 18: nur 21,5 ist der höchste Wert.
    assert ansicht["stufen_werktag"] == [None, "halb", None, "voll", None]
    assert ansicht["stufen_zwei_werte"] == [None, "voll", None]
    assert ansicht["stufen_schalt"] == [None, "voll", None]


def test_ein_tag_wandert_aus_dem_anderen_block(ansicht):
    assert ansicht["mit_samstag"] == [["Mo", "Tu", "We", "Th", "Fr", "Sa"], ["Su"]]


def test_ein_block_ohne_tage_faellt_weg(ansicht):
    assert ansicht["ganze_woche"] == [["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]]
    assert ansicht["ohne_tage"] == [["Mo", "Tu", "We", "Th", "Fr"]]


def test_tage_ohne_block_bekommen_einen_neuen(ansicht):
    assert ansicht["neuer_block"] == [
        [["Mo", "Tu", "We", "Th", "Fr"], [{"zeit": 360, "wert": 21}, {"zeit": 1320, "wert": 16}]],
        [["Sa", "Su"], [{"zeit": 480, "wert": 20}]],
    ]


def test_das_programm_der_anlage_bleibt_unberuehrt(ansicht):
    assert ansicht["unveraendert"] is True
