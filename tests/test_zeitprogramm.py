"""Zeitprogramme: rechnen, prüfen, schreiben.

Die Oberfläche zeichnet ein Wochenraster und schreibt das ganze Programm
zurück – dazwischen liegt Rechnung, keine Darstellung: Aus Schaltpunkten
werden Abschnitte, aus Abschnitten Balken, aus dem bearbeiteten Stand die
Nutzlast für ``heatnexus.set_time_program``.

Geprüft wird genau diese Rechnung, in Node, weil sie im Browser läuft. Zwei
Fälle tragen den Rest: Der **Umlauf über Mitternacht** – vor dem ersten
Schaltpunkt gilt der letzte des Tages weiter, sonst stünde jeder Morgen leer
da – und die **Ablehnung**, was die Anlage nicht annimmt (mehr als sechs
Schaltzeiten, ein Wochentag in zwei Blöcken). Beides kommentarlos ans Gerät zu
schicken hieße: gekürzt, überschrieben, und niemand merkt es.
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
    / "zeitprogramm.js"
)

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")


@pytest.fixture(scope="module")
def rechnung(tmp_path_factory) -> dict:
    """Die reinen Funktionen des Moduls einmal in Node ausführen."""
    skript = tmp_path_factory.mktemp("zeitprogramm") / "pruefung.mjs"
    adresse = MODUL.resolve().as_uri()
    skript.write_text(
        f"""
import {{
  abschnitte,
  bereich,
  bloeckeLesen,
  gleich,
  istSchaltprogramm,
  nachDienst,
  pruefen,
  wochenraster,
}} from "{adresse}";

const heizen = bloeckeLesen([
  {{
    weekdays: ["Mo", "Tu", "We", "Th", "Fr"],
    switchPoints: [
      {{ time: "22:00", value: 16 }},
      {{ time: "06:00", value: 21 }},
    ],
  }},
  {{ weekdays: ["Sa", "So"], switchPoints: [{{ time: "00:00", value: 21 }}] }},
]);

const deutsch = bloeckeLesen([
  {{ weekdays: ["Di", "So"], switchPoints: [{{ time: "6:30", value: "20.5" }}] }},
]);

const schmutz = bloeckeLesen([
  {{
    weekdays: ["Mo", "Mo", "Xx"],
    switchPoints: [
      {{ time: "25:00", value: 21 }},
      {{ time: "07:00", value: "keine Zahl" }},
      {{ time: "05:00", value: 19 }},
    ],
  }},
]);

const schalten = bloeckeLesen([
  {{
    weekdays: ["Mo"],
    switchPoints: [
      {{ time: "05:00", value: 1 }},
      {{ time: "08:00", value: 0 }},
    ],
  }},
]);

const zuviele = [
  {{
    tage: ["Mo"],
    punkte: [0, 1, 2, 3, 4, 5, 6].map((n) => ({{ zeit: n * 60, wert: 20 }})),
  }},
];

const doppelterTag = [
  {{ tage: ["Mo", "Tu"], punkte: [{{ zeit: 360, wert: 21 }}] }},
  {{ tage: ["Tu"], punkte: [{{ zeit: 420, wert: 19 }}] }},
];

const ohneTag = [{{ tage: [], punkte: [{{ zeit: 360, wert: 21 }}] }}];
const doppelteZeit = [
  {{ tage: ["Mo"], punkte: [{{ zeit: 360, wert: 21 }}, {{ zeit: 360, wert: 19 }}] }},
];

// Dieselben Blöcke, andere Reihenfolge und andere Schreibweise der Werte:
// So meldet die Anlage zurück, was gerade geschrieben wurde.
const zurueckgemeldet = bloeckeLesen([
  {{ weekdays: ["Sa", "Su"], switchPoints: [{{ time: "00:00", value: 21.0 }}] }},
  {{
    weekdays: ["Fr", "Mo", "Tu", "We", "Th"],
    switchPoints: [
      {{ time: "06:00", value: 21 }},
      {{ time: "22:00", value: 16.0 }},
    ],
  }},
]);

console.log(
  JSON.stringify({{
    umlauf: abschnitte(heizen[0].punkte),
    ab_mitternacht: abschnitte(heizen[1].punkte),
    ohne_punkte: abschnitte([]),
    deutsche_tage: deutsch[0].tage,
    deutscher_wert: deutsch[0].punkte,
    schmutz: schmutz[0],
    raster_tage: wochenraster(heizen).map((zeile) => [zeile.tag, zeile.abschnitte.length]),
    schalt_erkannt: istSchaltprogramm(schalten),
    heizen_ist_kein_schaltprogramm: istSchaltprogramm(heizen),
    bereich_heizen: bereich(heizen),
    bereich_schalten: bereich(schalten),
    dienst: nachDienst(heizen),
    fehler_zuviele: pruefen(zuviele),
    fehler_doppelter_tag: pruefen(doppelterTag),
    fehler_ohne_tag: pruefen(ohneTag),
    fehler_doppelte_zeit: pruefen(doppelteZeit),
    fehler_leer: pruefen([]),
    sauber: pruefen(heizen),
    gleich_trotz_reihenfolge: gleich(heizen, zurueckgemeldet),
    gleich_bei_abweichung: gleich(heizen, schalten),
  }})
);
""",
        encoding="utf-8",
    )
    ausgabe = subprocess.run(["node", str(skript)], capture_output=True, text=True, check=True)
    return json.loads(ausgabe.stdout)


# ---------------------------------------------------------------------------
# Aus Schaltpunkten werden Abschnitte
# ---------------------------------------------------------------------------
def test_vor_dem_ersten_schaltpunkt_gilt_der_letzte_des_tages(rechnung):
    """Der Umlauf über Mitternacht.

    Die Anlage schaltet um 00:00 nicht ab, sie behält den Wert von 22:00 bis
    zur ersten Schaltzeit am Morgen. Ohne diesen Abschnitt stünde jeder Tag
    bis 6 Uhr leer da, obwohl abgesenkt geheizt wird.
    """
    assert rechnung["umlauf"] == [
        {"von": 0, "bis": 360, "wert": 16},
        {"von": 360, "bis": 1320, "wert": 21},
        {"von": 1320, "bis": 1440, "wert": 16},
    ]


def test_ein_schaltpunkt_um_mitternacht_deckt_den_ganzen_tag(rechnung):
    assert rechnung["ab_mitternacht"] == [{"von": 0, "bis": 1440, "wert": 21}]


def test_ohne_schaltpunkte_gibt_es_keine_abschnitte(rechnung):
    assert rechnung["ohne_punkte"] == []


def test_jeder_wochentag_bekommt_seine_zeile(rechnung):
    """Auch Tage ohne Block – sonst verschiebt sich das Raster."""
    assert [tag for tag, _ in rechnung["raster_tage"]] == [
        "Mo",
        "Tu",
        "We",
        "Th",
        "Fr",
        "Sa",
        "Su",
    ]
    assert all(anzahl > 0 for _, anzahl in rechnung["raster_tage"])


# ---------------------------------------------------------------------------
# Lesen, was die Anlage liefert
# ---------------------------------------------------------------------------
def test_deutsche_wochentage_werden_angenommen(rechnung):
    """Die Anlage schreibt englische Kürzel, die Dokumentation deutsche."""
    assert rechnung["deutsche_tage"] == ["Tu", "Su"]
    assert rechnung["deutscher_wert"] == [{"zeit": 390, "wert": 20.5}]


def test_unlesbares_faellt_weg_statt_das_programm_zu_kippen(rechnung):
    """Eine kaputte Schaltzeit darf nicht das ganze Programm leeren.

    Sonst stünde die Karte leer da und der Nutzer hielte sein Programm für
    verloren – dabei fehlt nur ein Eintrag.
    """
    assert rechnung["schmutz"]["tage"] == ["Mo"]
    assert rechnung["schmutz"]["punkte"] == [{"zeit": 300, "wert": 19}]


def test_schaltprogramm_wird_am_wertebereich_erkannt(rechnung):
    """0/1 ist Ein und Aus, alles andere sind Temperaturen.

    Die Anlage führt beides unter derselben Typkennung; eine Solltemperatur
    von 1 °C gibt es nicht.
    """
    assert rechnung["schalt_erkannt"] is True
    assert rechnung["heizen_ist_kein_schaltprogramm"] is False
    assert rechnung["bereich_schalten"] == {"min": 0, "max": 1, "schalt": True}
    assert rechnung["bereich_heizen"]["schalt"] is False
    assert rechnung["bereich_heizen"]["min"] == 16


# ---------------------------------------------------------------------------
# Schreiben
# ---------------------------------------------------------------------------
def test_die_nutzlast_hat_die_form_des_dienstes(rechnung):
    """Genau das, was `set_time_program` als `blocks` erwartet."""
    assert rechnung["dienst"] == [
        {
            "weekdays": ["Mo", "Tu", "We", "Th", "Fr"],
            "switch_points": [
                {"time": "06:00", "value": 21},
                {"time": "22:00", "value": 16},
            ],
        },
        {"weekdays": ["Sa", "Su"], "switch_points": [{"time": "00:00", "value": 21}]},
    ]


def test_zurueckgemeldetes_programm_gilt_als_dasselbe(rechnung):
    """Sonst bliebe die Rückmeldung ewig auf „wird ausgeführt".

    Die Anlage meldet dieselben Blöcke in eigener Reihenfolge und mit „21"
    statt „21.0" zurück.
    """
    assert rechnung["gleich_trotz_reihenfolge"] is True
    assert rechnung["gleich_bei_abweichung"] is False


# ---------------------------------------------------------------------------
# Was die Anlage nicht annimmt, wird vorher abgelehnt
# ---------------------------------------------------------------------------
def test_mehr_als_sechs_schaltzeiten_werden_abgelehnt(rechnung):
    """Das Gerät kürzt sonst kommentarlos."""
    assert any("sechs" in text or "6" in text for text in rechnung["fehler_zuviele"])


def test_ein_wochentag_gehoert_nur_einem_block(rechnung):
    assert any("Di" in text for text in rechnung["fehler_doppelter_tag"])


def test_block_ohne_wochentag_und_doppelte_zeit_werden_abgelehnt(rechnung):
    assert rechnung["fehler_ohne_tag"]
    assert rechnung["fehler_doppelte_zeit"]
    assert rechnung["fehler_leer"]


def test_ein_gueltiges_programm_geht_durch(rechnung):
    assert rechnung["sauber"] == []
