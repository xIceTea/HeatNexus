"""Zeitprogramme bedienen: Reiter, Zeilen, Tipp, Editor, Tastatur und Vorleser.

Gefahren wird der Reiter in Node gegen die DOM-Attrappe (`js/dom-attrappe.mjs`).
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")

KOMPONENTE = Path(__file__).resolve().parents[1] / "custom_components" / "heatnexus"
LAUF = Path(__file__).parent / "js" / "zeitprogramme-bedienung.mjs"


@pytest.fixture(scope="module")
def befund() -> dict:
    lauf = subprocess.run(
        ["node", str(LAUF), str(KOMPONENTE / "frontend"), str(KOMPONENTE / "sprachen")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr or lauf.stdout
    return json.loads(lauf.stdout)


def _abschnitt(befund: dict, name: str) -> dict:
    teil = befund[name]
    assert "fehler" not in teil, teil.get("fehler")
    return teil


def test_reiter_lassen_den_gemeinsamen_anfang_weg(befund):
    reiter = _abschnitt(befund, "reiter")
    assert reiter["zirkulation"] == {
        "vorsatz": "WW-Zirkulationsprogramm",
        "namen": ["Temperatursteuerung", "Zeitsteuerung"],
    }
    assert reiter["heizen"] == {"vorsatz": "Heizprogramm", "namen": ["1", "2"]}


def test_der_vorsatz_endet_an_einer_wortgrenze(befund):
    assert _abschnitt(befund, "reiter")["englisch"] == {
        "vorsatz": "DHW circulation program",
        "namen": ["Temperature control", "Time control"],
    }


def test_ohne_eigenen_rest_bleiben_die_namen_ganz(befund):
    reiter = _abschnitt(befund, "reiter")
    assert reiter["gleich"] == {"vorsatz": "", "namen": ["Programm", "Programm"]}
    assert reiter["teil"] == {"vorsatz": "", "namen": ["Programm", "Programm 2"]}
    assert reiter["ohne"] == {"vorsatz": "", "namen": ["Heizprogramm 1", "Warmwasserprogramm"]}
    assert reiter["bezeichnung"] == {
        "vorsatz": "Heizprogramm",
        "namen": ["1", "2 – Übergangszeit"],
    }


def test_gleiche_nachbartage_stehen_in_einer_zeile(befund):
    assert _abschnitt(befund, "zusammen")["werktage"] == ["Mo–Fr", "Sa, So"]


def test_gleiche_tage_ohne_gemeinsame_grenze_bleiben_getrennt(befund):
    assert _abschnitt(befund, "zusammen")["getrennt"] == ["Mo", "Di", "Mi", "Do–So"]


def test_eine_unveraenderte_sammelzeile_schreibt_nichts(befund):
    assert _abschnitt(befund, "zusammen")["unveraendert"] == []


def test_eine_geaenderte_sammelzeile_schreibt_einen_block_fuer_alle_ihre_tage(befund):
    (bloecke,) = _abschnitt(befund, "zusammen")["geaendert"]
    assert bloecke == [
        {
            "weekdays": ["Mo", "Tu", "We", "Th", "Fr"],
            "switch_points": [{"time": "06:00", "value": 22}, {"time": "22:00", "value": 16}],
        },
        {
            "weekdays": ["Sa"],
            "switch_points": [{"time": "07:30", "value": 21}, {"time": "23:00", "value": 16}],
        },
        {
            "weekdays": ["Su"],
            "switch_points": [{"time": "07:30", "value": 21}, {"time": "23:00", "value": 16}],
        },
    ]


def test_der_tipp_bleibt_innerhalb_der_spur(befund):
    """Die Spur ist 330 px breit, der Tipp 120 px; am Rand rückt er nach innen."""
    assert _abschnitt(befund, "tipp")["lagen"] == [60, 159, 270]


def test_der_tipp_schliesst_mit_escape_und_antippen_daneben(befund):
    tipp = _abschnitt(befund, "tipp")
    assert (tipp["offen"], tipp["nachTaste"], tipp["nachEscape"]) == (True, True, False)
    assert tipp["nachKlick"] is False


def test_es_ist_hoechstens_ein_tipp_offen(befund):
    assert _abschnitt(befund, "tipp")["zweiOffen"] == 1


def test_nach_enter_bleibt_der_fokus_auf_der_geoeffneten_zeile(befund):
    assert _abschnitt(befund, "editor")["nachEnter"] == {"lage": "zeile true", "offen": True}


def test_im_editor_bleibt_der_fokus_an_seiner_taste(befund):
    editor = _abschnitt(befund, "editor")
    assert (editor["nachMehr"], editor["nachTag"]) == ("mehr", "tag:Sa")


def test_nach_dem_entfernen_rueckt_der_fokus_zur_vorigen_schaltzeit(befund):
    assert _abschnitt(befund, "editor")["nachWeg"] == "weg:1"


def test_escape_schliesst_den_editor_und_kehrt_zur_zeile_zurueck(befund):
    editor = _abschnitt(befund, "editor")
    assert editor["nachEscape"] == {"lage": "zeile false", "offen": False}
    assert editor["nachAbbrechen"] == {"lage": "zeile false", "offen": False}


TEMPERATUR = "WW-Zirkulationsprogramm Temperatursteuerung"
ZEIT = "WW-Zirkulationsprogramm Zeitsteuerung, gilt"


def test_nur_der_gewaehlte_reiter_ist_tabulatorziel(befund):
    tabulator = dict(_abschnitt(befund, "pfeile")["tabulator"])
    assert sorted(tabulator.values()) == ["-1", "0"]


def test_pfeiltasten_wandern_durch_die_reiter(befund):
    pfeile = _abschnitt(befund, "pfeile")
    assert [pfeile[k] for k in ("rechts", "nochmal", "ende", "anfang")] == [
        TEMPERATUR,
        ZEIT,
        ZEIT,
        TEMPERATUR,
    ]


def test_ein_gewaehlter_reiter_behaelt_den_fokus(befund):
    gewaehlt = _abschnitt(befund, "pfeile")["gewaehlt"]
    assert gewaehlt["name"].startswith(TEMPERATUR)
    assert gewaehlt["ausgewaehlt"] == "true"


def test_pfeiltasten_wandern_durch_die_zeilen(befund):
    assert _abschnitt(befund, "pfeile")["zeilen"] == [
        "Sa, So",
        "Mo–Fr",
        "Sa, So",
        "Mo–Fr",
        "Sa, So",
    ]


def test_vorleser_ueberspringen_die_achse(befund):
    achsen = _abschnitt(befund, "vorleser")["achsen"]
    assert achsen
    assert set(achsen) == {"true"}


@pytest.mark.parametrize(
    ("sprache", "erwartet"),
    [
        ("de", ["Heizprogramm 1, gilt", "Heizprogramm 2"]),
        ("en", ["Heating program 1, in effect", "Heating program 2"]),
        ("nl", ["Verwarmingsprogramma 1, actief", "Verwarmingsprogramma 2"]),
    ],
)
def test_der_geltende_reiter_nennt_gilt_als_eigenes_wort(befund, sprache, erwartet):
    assert _abschnitt(befund, "vorleser")[sprache] == erwartet


def test_im_balken_sagt_ein_satz_dass_antippen_details_zeigt(befund):
    hinweis = _abschnitt(befund, "hinweis")
    assert hinweis["spur"] == ["Antippen zeigt Zeit und Wert."]
    assert hinweis["en"] == ["Tap to show time and value."]
    assert hinweis["nl"] == ["Tik om tijd en waarde te tonen."]


def test_unter_der_tabelle_braucht_es_keinen_hinweis(befund):
    assert _abschnitt(befund, "hinweis")["tabelle"] == []


def test_mit_maus_bleibt_der_hinweis_verborgen():
    """Wer überfahren kann, sieht Zeit und Wert schon im Titel des Abschnitts."""
    stil = (KOMPONENTE / "frontend" / "stil" / "zeitprogramme.js").read_text(encoding="utf-8")
    regel = re.search(r"@media \(hover: hover\) \{([^}]*)\}", stil)
    assert regel and ".zp-tipphinweis" in regel.group(1) and "display: none" in regel.group(1)
