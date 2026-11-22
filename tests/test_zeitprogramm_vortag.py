"""Vor dem ersten Schaltpunkt eines Tages gilt der letzte Wert des Vortags.

Geprüft in Node, weil die Rechnung im Browser läuft. Ein Tag ohne Block
behält den Wert davor; erst ein Schaltpunkt ändert ihn.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "custom_components" / "heatnexus" / "frontend"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")


@pytest.fixture(scope="module")
def rechnung(tmp_path_factory) -> dict:
    skript = tmp_path_factory.mktemp("vortag") / "vortag.mjs"
    modul = (FRONTEND / "zeitprogramm.js").as_uri()
    seite = (FRONTEND / "zeitprogrammseite.js").as_uri()
    pumpe = (FRONTEND / "teile" / "waermepumpe.js").as_uri()
    skript.write_text(
        f"""
import {{
  blockraster, bloeckeLesen, jetztStelle, naechsterWechsel, tagesabschnitte, vortagswert,
  wertJetzt, wochenraster, zeilenvortag,
}} from "{modul}";
import {{ nachbarnZusammenfassen, spurteile, tabelle }} from "{seite}";
import {{ zeitfensterText }} from "{pumpe}";

const woche = bloeckeLesen([
  {{ weekdays: ["Su"], switchPoints: [{{ time: "22:00", value: 18 }}] }},
  {{ weekdays: ["Mo"], switchPoints: [{{ time: "06:00", value: 20 }}, {{ time: "22:00", value: 14 }}] }},
]);
const werktage = bloeckeLesen([
  {{ weekdays: ["Mo", "Tu", "We", "Th", "Fr"],
    switchPoints: [{{ time: "05:30", value: 51 }}, {{ time: "23:00", value: 20 }}] }},
  {{ weekdays: ["Sa", "Su"], switchPoints: [{{ time: "21:00", value: 43 }}] }},
]);
const gleicheTage = bloeckeLesen([
  {{ weekdays: ["Fr"], switchPoints: [{{ time: "12:00", value: 15 }}] }},
  {{ weekdays: ["Sa"], switchPoints: [{{ time: "06:00", value: 21 }}, {{ time: "22:00", value: 16 }}] }},
  {{ weekdays: ["Su"], switchPoints: [{{ time: "06:00", value: 21 }}, {{ time: "22:00", value: 16 }}] }},
]);
const schalten = bloeckeLesen([
  {{ weekdays: ["Su"], switchPoints: [{{ time: "08:00", value: 0 }}, {{ time: "20:00", value: 1 }}] }},
  {{ weekdays: ["Mo"],
    switchPoints: [{{ time: "06:00", value: 0 }}, {{ time: "20:00", value: 1 }}, {{ time: "23:00", value: 0 }}] }},
]);
const schaltenWerktage = bloeckeLesen([
  {{ weekdays: ["Mo", "Tu", "We", "Th", "Fr"],
    switchPoints: [{{ time: "06:00", value: 0 }}, {{ time: "20:00", value: 1 }}, {{ time: "23:00", value: 0 }}] }},
  {{ weekdays: ["Sa", "Su"], switchPoints: [{{ time: "08:00", value: 0 }}, {{ time: "22:00", value: 1 }}] }},
]);
const ohneSonntag = bloeckeLesen([
  {{ weekdays: ["Mo", "Tu", "We", "Th", "Fr", "Sa"],
    switchPoints: [{{ time: "06:00", value: 21 }}, {{ time: "22:00", value: 17 }}] }},
]);
const nurSamstag = bloeckeLesen([
  {{ weekdays: ["Mo"], switchPoints: [{{ time: "06:00", value: 20 }}, {{ time: "22:00", value: 14 }}] }},
  {{ weekdays: ["Sa"], switchPoints: [{{ time: "22:00", value: 18 }}] }},
]);
const zeile = (bloecke, tage) => blockraster(bloecke).find((z) => z.tage.join() === tage).abschnitte;

console.log(JSON.stringify({{
  montag: tagesabschnitte(woche, "Mo"),
  raster_montag: wochenraster(woche).find((z) => z.tag === "Mo").abschnitte,
  wert_montag_frueh: wertJetzt(woche, {{ tag: "Mo", minute: 120 }}),
  jetzt_montag_frueh: jetztStelle(woche, {{ tag: "Mo", minute: 120 }}),
  wechsel_sonntag_nacht: naechsterWechsel(woche, {{ tag: "Su", minute: 23 * 60 }}),
  vortag_ohne_block: vortagswert(woche, "Su"),
  sonntag_ohne_vortag: tagesabschnitte(woche, "Su"),
  zeile_montag: zeile(woche, "Mo"),
  vortag_mehrdeutig: zeilenvortag(werktage, ["Mo", "Tu", "We", "Th", "Fr"]),
  zeilen_werktage: nachbarnZusammenfassen(blockraster(werktage)).map((z) => [z.text, z.stelle]),
  spur_werktage: spurteile(zeile(werktage, "Mo,Tu,We,Th,Fr"), {{ min: 40, max: 65, art: "wasser" }})[0],
  tabelle_werktage: tabelle(zeile(werktage, "Mo,Tu,We,Th,Fr"), {{ min: 40, max: 65, art: "wasser" }}),
  zeile_wochenende: zeile(werktage, "Sa,Su")[0],
  zeile_werktage: zeile(werktage, "Mo,Tu,We,Th,Fr"),
  montag_werktage: tagesabschnitte(werktage, "Mo"),
  zusammengefasst: nachbarnZusammenfassen(blockraster(gleicheTage)).filter((z) => z.stelle >= 0).map((z) => [z.tage, z.abschnitte[0].wert]),
  fenster: zeitfensterText(schalten),
  fenster_werktage: zeitfensterText(schaltenWerktage),
  sonntag_ohne_block: wertJetzt(ohneSonntag, {{ tag: "Su", minute: 600 }}),
  raster_sonntag: wochenraster(ohneSonntag).find((z) => z.tag === "Su").abschnitte,
  wechsel_ohne_block: naechsterWechsel(ohneSonntag, {{ tag: "Su", minute: 600 }}),
  jetzt_ohne_block: jetztStelle(ohneSonntag, {{ tag: "Su", minute: 600 }}),
  montag_nach_leerem_sonntag: wertJetzt(nurSamstag, {{ tag: "Mo", minute: 120 }}),
  mittwoch_ohne_block: wertJetzt(nurSamstag, {{ tag: "We", minute: 600 }}),
}}));
""",
        encoding="utf-8",
    )
    ausgabe = subprocess.run(
        ["node", str(skript)], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return json.loads(ausgabe.stdout)


def test_montag_beginnt_mit_dem_letzten_wert_des_sonntags(rechnung):
    erwartet = [
        {"von": 0, "bis": 360, "wert": 18},
        {"von": 360, "bis": 1320, "wert": 20},
        {"von": 1320, "bis": 1440, "wert": 14},
    ]
    assert rechnung["montag"] == erwartet
    assert rechnung["raster_montag"] == erwartet
    assert rechnung["zeile_montag"] == erwartet


def test_gilt_jetzt_folgt_dem_vortag(rechnung):
    assert rechnung["wert_montag_frueh"] == 18
    assert rechnung["jetzt_montag_frueh"] == {"block": 1, "von": 0}
    # Sonntag 23:00 gilt 18, und das bleibt bis Montag 06:00.
    assert rechnung["wechsel_sonntag_nacht"] == {"tag": "Mo", "tage": 1, "minute": 360, "wert": 20}


def test_ohne_block_am_vortag_gilt_der_letzte_wert_davor(rechnung):
    """Samstag hat keinen Block: Von Montag 22:00 an gilt 14 bis Sonntag 22:00."""
    assert rechnung["vortag_ohne_block"] == 14
    assert rechnung["sonntag_ohne_vortag"][0] == {"von": 0, "bis": 1320, "wert": 14}


def test_ein_tag_ohne_block_behaelt_den_wert_davor(rechnung):
    assert rechnung["sonntag_ohne_block"] == 17
    assert rechnung["raster_sonntag"] == [{"von": 0, "bis": 1440, "wert": 17}]
    assert rechnung["wechsel_ohne_block"] == {"tag": "Mo", "tage": 1, "minute": 360, "wert": 21}
    # Ohne Block gibt es keine Zeile, die als „jetzt“ hervortritt.
    assert rechnung["jetzt_ohne_block"] is None


def test_ueber_mehrere_tage_ohne_block_gilt_der_letzte_schaltpunkt(rechnung):
    assert rechnung["montag_nach_leerem_sonntag"] == 18
    assert rechnung["mittwoch_ohne_block"] == 14


VERSCHIEDEN = [{"tage": ["Mo"], "wert": 43}, {"tage": ["Tu", "We", "Th", "Fr"], "wert": 20}]


def test_zeile_mit_verschiedenen_vortagen_zeigt_keinen_einzelnen_wert(rechnung):
    """Mo–Fr: Montag erbt 43 vom Sonntag, Di–Fr 20 vom eigenen Block."""
    assert rechnung["vortag_mehrdeutig"] == {"verschieden": VERSCHIEDEN}
    assert rechnung["zeile_werktage"][0] == {
        "von": 0,
        "bis": 330,
        "wert": 20,
        "jeNachVortag": VERSCHIEDEN,
    }
    assert rechnung["montag_werktage"][0] == {"von": 0, "bis": 330, "wert": 43}
    assert rechnung["zeile_wochenende"]["jeNachVortag"] == [
        {"tage": ["Sa"], "wert": 20},
        {"tage": ["Su"], "wert": 43},
    ]


def test_der_abschnitt_je_nach_vortag_nennt_die_werte_je_tag(rechnung):
    spur = rechnung["spur_werktage"]
    assert spur["farbe"] is None
    assert spur["tipp"] == "00:00–05:30 · je nach Vortag: Mo 43 °C, Di–Fr 20 °C"
    assert rechnung["tabelle_werktage"][0] == {
        "stufe": None,
        "farbe": None,
        "zeit": "00:00 – 05:30",
        "wert": "je nach Vortag",
    }


def test_die_zeilen_folgen_weiter_den_bloecken_der_steuerung(rechnung):
    """Bearbeiten schreibt den Block Mo–Fr; die Anzeige teilt ihn nicht in Mo und Di–Fr."""
    assert rechnung["zeilen_werktage"] == [["Mo–Fr", 0], ["Sa, So", 1]]


def test_zeilen_mit_verschiedenem_morgen_bleiben_getrennt(rechnung):
    assert rechnung["zusammengefasst"] == [[["Fr"], 16], [["Sa"], 15], [["Su"], 16]]


def test_zeitfenster_der_waermepumpe_folgt_dem_vortag(rechnung):
    # Montag 23:00 schaltet aus; das gilt über die Tage ohne Block bis Sonntag 20:00.
    assert rechnung["fenster"] == "So 20:00–00:00; Mo 00:00–06:00, 20:00–23:00"


def test_zeitfenster_mit_verschiedenen_vortagen_nennt_den_wert_je_tag(rechnung):
    assert rechnung["fenster_werktage"] == (
        "Mo–Fr 00:00–06:00 (je nach Vortag: Mo Ein, Di–Fr Aus), 20:00–23:00; "
        "Sa, So 00:00–08:00 (je nach Vortag: Sa Aus, So Ein), 22:00–00:00"
    )
