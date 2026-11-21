"""Zeitprogramme lesen: Klartext und Farben einer Tageszeile.

Je Block steht eine Spur in den Farben der Temperaturen und darunter der Klartext.
Beides wird aus den Abschnitten gerechnet; geprüft wird diese Rechnung in Node.
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
    """Klartext und Farben für typische Tage in Node rechnen."""
    skript = tmp_path_factory.mktemp("ansicht") / "ansicht.mjs"
    modul = (FRONTEND / "zeitprogramm.js").resolve().as_uri()
    seite = (FRONTEND / "zeitprogrammseite.js").resolve().as_uri()
    skript.write_text(
        f"""
import {{ abschnitte, farbe, skala }} from "{modul}";
import {{ blockEinsetzen, farben, ohneFenster, spurteile, tabelle }} from "{seite}";

const p = (paare) => paare.map(([zeit, wert]) => ({{ zeit, wert }}));
const tag = (paare) => abschnitte(p(paare));
const raum = (paare) => skala([{{ tage: ["Mo"], punkte: p(paare) }}], "raum");
const schalt = skala([{{ tage: ["Mo"], punkte: p([[360, 1], [450, 0]]) }}]);
const wasser = skala([{{ tage: ["Mo"], punkte: p([[300, 52], [420, 40]]) }}], "wasser");

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
const englisch = (text) => ({{ "Übrige Zeit": "Rest of the day" }})[text] || text;

console.log(JSON.stringify({{
  werktag: tabelle(tag(werktag), raum(werktag), {{ sprache: "de" }}),
  werktag_englisch: tabelle(tag(werktag), raum(werktag), {{ sprache: "en", t: englisch }}),
  ganztags: tabelle(tag([[0, 20]]), raum([[0, 20]]), {{ sprache: "de" }}),
  ueber_mitternacht: tabelle(tag(nacht), raum(nacht), {{ sprache: "de" }}),
  zirkulation: tabelle(tag([[360, 1], [450, 0], [1080, 1], [1140, 0]]), schalt, {{ sprache: "de" }}),
  nie_an: tabelle(tag([[360, 0]]), schalt, {{ sprache: "de" }}),
  leer: tabelle([], raum(werktag), {{ sprache: "de" }}),
  ohne_fenster: ohneFenster(tabelle(tag([[0, 20]]), raum([[0, 20]]), {{ sprache: "de" }})),
  mit_fenster: ohneFenster(tabelle(tag(werktag), raum(werktag), {{ sprache: "de" }})),
  ohne_plan: ohneFenster(tabelle([], raum(werktag), {{ sprache: "de" }})),
  kalt: farbe(14, raum(werktag)),
  warm: farbe(24, raum(werktag)),
  mitte: farbe(18, raum(werktag)),
  wasser_kalt: farbe(40, wasser),
  wasser_warm: farbe(60, wasser),
  spur_ohne: spurteile(tag(werktag), raum(werktag), {{ sprache: "de" }}),
  spur_mit: spurteile(tag(werktag), raum(werktag), {{ beschriften: true, sprache: "de" }}),
  spur_schalt: spurteile(tag([[360, 1], [450, 0], [1080, 1], [1260, 0]]), schalt, {{ beschriften: true, sprache: "de" }}),
  farben_werktag: farben(tag(werktag), raum(werktag)),
  farben_erwartet: [18, 21, 18, 21.5, 18].map((wert) => farbe(wert, raum(werktag))),
  farben_schalt: farben(tag([[360, 1], [450, 0]]), schalt),
  ein_farbe: farbe(1, schalt),
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
        ("halb", "05:30 – 08:00", f"21{GESCHUETZT}°C"),
        ("voll", "16:00 – 22:00", f"21,5{GESCHUETZT}°C"),
        (None, "Übrige Zeit", f"18{GESCHUETZT}°C"),
    ]


def test_die_tabelle_folgt_sprache_und_zahlformat(ansicht):
    assert _zeilen(ansicht["werktag_englisch"])[-1] == (
        None,
        "Rest of the day",
        f"18{GESCHUETZT}°C",
    )


def test_ein_einziger_wert_gilt_ganztags(ansicht):
    assert _zeilen(ansicht["ganztags"]) == [("voll", "ganztags", f"20{GESCHUETZT}°C")]


def test_ein_fenster_ueber_mitternacht_steht_als_eines(ansicht):
    assert _zeilen(ansicht["ueber_mitternacht"]) == [
        ("voll", "22:00 – 06:00", f"22{GESCHUETZT}°C"),
        (None, "Übrige Zeit", f"18{GESCHUETZT}°C"),
    ]


def test_schaltprogramm_nennt_ein_und_aus(ansicht):
    assert _zeilen(ansicht["zirkulation"]) == [
        ("voll", "06:00 – 07:30", "Ein"),
        ("voll", "18:00 – 19:00", "Ein"),
        (None, "Übrige Zeit", "Aus"),
    ]
    assert _zeilen(ansicht["nie_an"]) == [(None, "ganztags", "Aus")]


def test_ein_tag_ohne_abschnitte_hat_keinen_plan(ansicht):
    assert _zeilen(ansicht["leer"]) == [(None, "Kein Zeitplan", "")]


def test_ein_tag_mit_einem_wert_hat_kein_zeitfenster(ansicht):
    assert (ansicht["ohne_fenster"], ansicht["mit_fenster"]) == (True, False)


def test_ein_tag_ohne_zeitplan_zeigt_keine_leere_spur(ansicht):
    assert ansicht["ohne_plan"] is True


def test_die_farben_reichen_von_schiefer_bis_orange(ansicht):
    """Feste Stufen statt einer Mischung aus Blau und Rot; dazwischen gemischt in oklab."""
    assert ansicht["kalt"] == "var(--zp-t14)"
    assert ansicht["warm"] == "var(--zp-t23)"
    assert ansicht["mitte"].startswith("color-mix(in oklab,")
    assert "rgb(" not in ansicht["mitte"]


def test_warmwasser_nutzt_dieselbe_farbfamilie(ansicht):
    assert (ansicht["wasser_kalt"], ansicht["wasser_warm"]) == ("var(--zp-t17)", "var(--zp-t23)")


def test_die_spur_traegt_ohne_wunsch_keine_zahlen(ansicht):
    assert [teil["text"] for teil in ansicht["spur_ohne"]] == ["", "", "", "", ""]
    assert [teil["ruhe"] for teil in ansicht["spur_ohne"]] == [True, False, True, False, True]


def test_abschnitte_ab_zwei_stunden_tragen_ihren_wert(ansicht):
    texte = [teil["text"] for teil in ansicht["spur_mit"]]
    assert texte == ["18°", "21°", "18°", "21,5°", "18°"]
    assert ansicht["spur_mit"][1]["tipp"] == f"05:30–08:00 · 21{GESCHUETZT}°C"


def test_ein_schaltprogramm_beschriftet_nur_breite_ein_fenster(ansicht):
    """06:00–07:30 ist zu schmal für eine Beschriftung; der Tipp nennt es."""
    teile = ansicht["spur_schalt"]
    assert [teil["text"] for teil in teile] == ["", "", "", "Ein", ""]
    assert [teil["farbe"] is None for teil in teile] == [True, False, True, False, True]
    assert teile[1]["tipp"] == "06:00–07:30 · Ein"


def test_jeder_abschnitt_traegt_die_farbe_seiner_temperatur(ansicht):
    """Auch die übrige Zeit ist eingefärbt, auf der festen Skala des Programms."""
    assert ansicht["farben_werktag"] == ansicht["farben_erwartet"]
    assert len(set(ansicht["farben_werktag"])) == 3


def test_ein_schaltprogramm_faerbt_nur_ein(ansicht):
    assert ansicht["farben_schalt"] == [None, ansicht["ein_farbe"], None]


def test_die_tabelle_nennt_die_farbe_jeder_zeile(ansicht):
    zeilen = ansicht["werktag"]
    assert zeilen[-1]["farbe"] == ansicht["farben_erwartet"][0]
    assert zeilen[1]["farbe"] == ansicht["farben_erwartet"][3]


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


# ---------------------------------------------------------------------------
# Stromtarifprogramm `54/7`: Werte 0–4 heißen Tarif 1–5, es lässt sich nur ansehen
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def tarif(tmp_path_factory) -> dict:
    """Skala, Klartext und Farben des Tarifprogramms in Node rechnen."""
    skript = tmp_path_factory.mktemp("tarif") / "tarif.mjs"
    modul = (FRONTEND / "zeitprogramm.js").resolve().as_uri()
    seite = (FRONTEND / "zeitprogrammseite.js").resolve().as_uri()
    skript.write_text(
        f"""
import {{ abschnitte, farbe, skala, wertText }} from "{modul}";
import {{ nurLesen, spurteile, tabelle }} from "{seite}";

const p = (paare) => paare.map(([zeit, wert]) => ({{ zeit, wert }}));
const paare = [[360, 0], [1320, 1]];
const grenzen = skala([{{ tage: ["Mo"], punkte: p(paare) }}], "tarif");
const englisch = (text) => ({{ Tarif: "Tariff" }})[text] || text;

console.log(JSON.stringify({{
  grenzen,
  tabelle: tabelle(abschnitte(p(paare)), grenzen, {{ sprache: "de" }}),
  englisch: tabelle(abschnitte(p(paare)), grenzen, {{ sprache: "en", t: englisch }}),
  spur: spurteile(abschnitte(p(paare)), grenzen, {{ beschriften: true, sprache: "de" }}),
  wert: wertText(4, grenzen),
  farben: [0, 1, 2, 3, 4].map((wert) => farbe(wert, grenzen)),
  schalt_leer: skala([{{ tage: ["Mo"], punkte: [] }}], "schalt"),
  wasser_null: skala([{{ tage: ["Mo"], punkte: p([[360, 0]]) }}], "wasser"),
  wasser_null_text: tabelle(abschnitte(p([[360, 0]])), skala([{{ tage: ["Mo"], punkte: p([[360, 0]]) }}], "wasser"), {{ sprache: "de" }}),
  ohne_art_null: skala([{{ tage: ["Mo"], punkte: p([[360, 0]]) }}]),
  nur_lesen: nurLesen({{ art: "tarif" }}),
  raum_bearbeitbar: nurLesen({{ art: "raum" }}),
}}));
""",
        encoding="utf-8",
    )
    ausgabe = subprocess.run(
        ["node", str(skript)], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return json.loads(ausgabe.stdout)


def test_das_tarifprogramm_ist_kein_schaltprogramm(tarif):
    """Nur aus 0 und 1 sieht es aus wie Aus und Ein; die Art „tarif“ entscheidet."""
    assert tarif["grenzen"]["schalt"] is False
    assert tarif["grenzen"]["art"] == "tarif"


def test_das_tarifprogramm_nennt_tarife_ohne_grad(tarif):
    assert _zeilen(tarif["tabelle"]) == [
        ("voll", "22:00 – 06:00", "Tarif 2"),
        (None, "Übrige Zeit", "Tarif 1"),
    ]
    assert _zeilen(tarif["englisch"])[-1] == (None, "Übrige Zeit", "Tariff 1")
    assert tarif["wert"] == "Tarif 5"
    assert all("°" not in teil["text"] and "°" not in teil["tipp"] for teil in tarif["spur"])
    assert [teil["text"] for teil in tarif["spur"]] == ["Tarif 2", "Tarif 1", "Tarif 2"]


def test_jeder_tarif_hat_seine_farbe(tarif):
    assert len(set(tarif["farben"])) == 5


def test_nur_das_tarifprogramm_ist_nur_lesbar(tarif):
    assert tarif["nur_lesen"] is True
    assert tarif["raum_bearbeitbar"] is False


@pytest.fixture(scope="module")
def tarifzeilen() -> dict:
    """Die Tageszeilen eines Tarif- und eines Raumprogramms im Panel aufbauen und antippen."""
    skript = Path(__file__).parent / "js" / "zeitprogramm-tarif.mjs"
    ausgabe = subprocess.run(
        ["node", str(skript), str(FRONTEND / "heatnexus-panel.js")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(ausgabe.stdout)


def test_die_zeile_des_tarifprogramms_oeffnet_keinen_editor(tarifzeilen):
    tarif = tarifzeilen["tarif"]
    assert tarif["zeilen"] == 1
    assert tarif["rollen"] == [None]
    assert tarif["getippt"] is False
    assert tarif["taste"] is False
    assert "Tarif 5" in tarif["text"][0]
    assert "°" not in tarif["text"][0]


def test_die_zeile_eines_raumprogramms_bleibt_bedienbar(tarifzeilen):
    raum = tarifzeilen["raum"]
    assert raum["rollen"] == ["button"]
    assert raum["getippt"] is True
    assert raum["taste"] is True


def test_die_art_vom_server_geht_vor_den_werten(tarif):
    """Ein Schaltprogramm ohne Schaltzeit bleibt eines; ein Wasserprogramm mit 0 zeigt 0 °C."""
    assert tarif["schalt_leer"]["schalt"] is True
    assert tarif["wasser_null"]["schalt"] is False
    assert _zeilen(tarif["wasser_null_text"]) == [("voll", "ganztags", f"0{GESCHUETZT}°C")]


def test_ohne_art_entscheiden_weiter_die_werte(tarif):
    assert tarif["ohne_art_null"]["schalt"] is True
