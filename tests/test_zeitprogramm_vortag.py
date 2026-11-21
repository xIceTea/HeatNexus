"""Vor dem ersten Schaltpunkt eines Tages gilt der letzte Wert des Vortags.

Geprüft in Node, weil die Rechnung im Browser läuft. Fehlt der Block des
Vortags, gilt der letzte Wert desselben Tags weiter.
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
import {{ nachbarnZusammenfassen }} from "{seite}";
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
  zeile_werktage: zeile(werktage, "Mo,Tu,We,Th,Fr"),
  montag_werktage: tagesabschnitte(werktage, "Mo"),
  zusammengefasst: nachbarnZusammenfassen(blockraster(gleicheTage)).filter((z) => z.stelle >= 0).map((z) => [z.tage, z.abschnitte[0].wert]),
  fenster: zeitfensterText(schalten),
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


def test_ohne_block_am_vortag_gilt_der_eigene_letzte_wert(rechnung):
    assert rechnung["vortag_ohne_block"] is None
    assert rechnung["sonntag_ohne_vortag"][0] == {"von": 0, "bis": 1320, "wert": 18}


def test_zeile_mit_verschiedenen_vortagen_behaelt_den_eigenen_wert(rechnung):
    """Mo–Fr: Montag erbt 43 vom Sonntag, Di–Fr 20 vom eigenen Block."""
    assert rechnung["vortag_mehrdeutig"] is None
    assert rechnung["zeile_werktage"][0] == {"von": 0, "bis": 330, "wert": 20}
    assert rechnung["montag_werktage"][0] == {"von": 0, "bis": 330, "wert": 43}


def test_zeilen_mit_verschiedenem_morgen_bleiben_getrennt(rechnung):
    assert rechnung["zusammengefasst"] == [[["Fr"], 15], [["Sa"], 15], [["Su"], 16]]


def test_zeitfenster_der_waermepumpe_folgt_dem_vortag(rechnung):
    assert rechnung["fenster"] == "So 20:00–08:00; Mo 00:00–06:00, 20:00–23:00"
