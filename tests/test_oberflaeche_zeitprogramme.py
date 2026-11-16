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
import {{ blockEinsetzen, tabelle, stufen, zeitmarken }} from "{seite}";

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
const englisch = (text) => ({{ "übrige Zeit": "rest of the day" }})[text] || text;

console.log(JSON.stringify({{
  werktag: tabelle(tag(werktag), raum(werktag), {{ sprache: "de" }}),
  werktag_englisch: tabelle(tag(werktag), raum(werktag), {{ sprache: "en", t: englisch }}),
  ganztags: tabelle(tag([[0, 20]]), raum([[0, 20]]), {{ sprache: "de" }}),
  ueber_mitternacht: tabelle(tag(nacht), raum(nacht), {{ sprache: "de" }}),
  zirkulation: tabelle(tag([[360, 1], [450, 0], [1080, 1], [1140, 0]]), schalt, {{ sprache: "de" }}),
  nie_an: tabelle(tag([[360, 0]]), schalt, {{ sprache: "de" }}),
  leer: tabelle([], raum(werktag), {{ sprache: "de" }}),
  marken_werktag: zeitmarken(tag(werktag), raum(werktag)),
  marken_dicht: zeitmarken(tag([[360, 21], [420, 18], [960, 21], [1320, 18]]), raum([[360, 21], [420, 18]])),
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


def _zeilen(liste):
    return [(z["stufe"], z["zeit"], z["wert"]) for z in liste]


def test_die_tabelle_nennt_jedes_fenster_und_die_uebrige_zeit(ansicht):
    assert _zeilen(ansicht["werktag"]) == [
        ("halb", "05:30 – 08:00", f"21,0{GESCHUETZT}°C"),
        ("voll", "16:00 – 22:00", f"21,5{GESCHUETZT}°C"),
        (None, "übrige Zeit", f"18,0{GESCHUETZT}°C"),
    ]


def test_die_tabelle_folgt_sprache_und_zahlformat(ansicht):
    assert _zeilen(ansicht["werktag_englisch"])[-1] == (
        None,
        "rest of the day",
        f"18.0{GESCHUETZT}°C",
    )


def test_ein_einziger_wert_gilt_ganztags(ansicht):
    assert _zeilen(ansicht["ganztags"]) == [("voll", "ganztags", f"20,0{GESCHUETZT}°C")]


def test_ein_fenster_ueber_mitternacht_steht_als_eines(ansicht):
    assert _zeilen(ansicht["ueber_mitternacht"]) == [
        ("voll", "22:00 – 06:00", f"22,0{GESCHUETZT}°C"),
        (None, "übrige Zeit", f"18,0{GESCHUETZT}°C"),
    ]


def test_schaltprogramm_nennt_ein_und_aus(ansicht):
    assert _zeilen(ansicht["zirkulation"]) == [
        ("voll", "06:00 – 07:30", "Ein"),
        ("voll", "18:00 – 19:00", "Ein"),
        (None, "übrige Zeit", "Aus"),
    ]
    assert _zeilen(ansicht["nie_an"]) == [(None, "ganztags", "Aus")]


def test_ein_tag_ohne_abschnitte_hat_keinen_plan(ansicht):
    assert _zeilen(ansicht["leer"]) == [(None, "kein Zeitplan", "")]


def test_zeitmarken_stehen_an_den_grenzen(ansicht):
    assert ansicht["marken_werktag"] == [330, 480, 960, 1320]


def test_eine_zu_dichte_zeitmarke_faellt_weg(ansicht):
    """06:00 und 07:00 lägen auf dem Handy übereinander; die Tabelle nennt beide."""
    assert ansicht["marken_dicht"] == [360, 960, 1320]


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
