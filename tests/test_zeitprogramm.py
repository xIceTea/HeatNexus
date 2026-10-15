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

SEITE = MODUL.with_name("zeitprogrammseite.js")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")


@pytest.fixture(scope="module")
def rechnung(tmp_path_factory) -> dict:
    """Die reinen Funktionen des Moduls einmal in Node ausführen."""
    skript = tmp_path_factory.mktemp("zeitprogramm") / "pruefung.mjs"
    adresse = MODUL.resolve().as_uri()
    seite = SEITE.resolve().as_uri()
    skript.write_text(
        f"""
import {{
  abschnitte,
  blockraster,
  bloeckeLesen,
  gleich,
  istSchaltprogramm,
  farbe,
  jetztStelle,
  nachDienst,
  naechsterWechsel,
  ortszeit,
  pruefen,
  skala,
  tagesbereich,
  wertJetzt,
  wertText,
  wochenraster,
}} from "{adresse}";
import {{ gruppieren, heuteText, nachTeilen }} from "{seite}";

const kreis = [
  {{ entity: "sensor.p1", teil: "hk", anlagenteil: "HK", gruppe: "heizen", art: "raum", nummer: 1 }},
  {{ entity: "sensor.ww", teil: "hk", anlagenteil: "HK", gruppe: "warmwasser", art: "wasser" }},
  {{ entity: "sensor.v1", teil: "hk", anlagenteil: "HK", gruppe: "heizen", art: "vorlauf", nummer: 1 }},
  {{ entity: "sensor.v3", teil: "hk", anlagenteil: "HK", gruppe: "heizen", art: "vorlauf", nummer: 3 }},
  {{ entity: "sensor.p2", teil: "hk", anlagenteil: "HK", gruppe: "heizen", art: "raum", nummer: 2 }},
  {{ entity: "sensor.frei", teil: "hk", anlagenteil: "HK" }},
  {{ entity: "sensor.puffer", teil: "pu", anlagenteil: "Puffer", gruppe: "puffer", art: "wasser" }},
];

const nur21 = bloeckeLesen([{{ weekdays: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"], switchPoints: [{{ time: "00:00", value: 21 }}] }}]);
const warmUndKalt = bloeckeLesen([
  {{ weekdays: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"], switchPoints: [{{ time: "06:00", value: 21 }}, {{ time: "22:00", value: 14 }}] }},
]);
const vorlauf = bloeckeLesen([{{ weekdays: ["Mo"], switchPoints: [{{ time: "05:00", value: 55 }}, {{ time: "22:00", value: 10 }}] }}]);

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
    bereich_taeglich: tagesbereich(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]),
    bereich_spanne: tagesbereich(["Mo", "Tu", "We", "Th", "Fr"]),
    bereich_paar: tagesbereich(["Sa", "Su"]),
    bereich_luecke: tagesbereich(["Mo", "Tu", "We", "Fr"]),
    bereich_leer: tagesbereich([]),
    bloecke_als_zeilen: blockraster(heizen).map((zeile) => [zeile.text, zeile.punkte.length]),
    zeile_ohne_programm: blockraster(schalten).map((zeile) => [
      zeile.text,
      zeile.abschnitte.length,
    ]),
    schalt_erkannt: istSchaltprogramm(schalten),
    heizen_ist_kein_schaltprogramm: istSchaltprogramm(heizen),
    skala_heizen: skala(heizen, "raum"),
    skala_schalten: skala(schalten),
    skala_vorlauf: skala(vorlauf, "vorlauf"),
    skala_geraten: [skala(heizen).art, skala(vorlauf).art],
    farbe_gleich: farbe(21, skala(nur21, "raum")) === farbe(21, skala(warmUndKalt, "raum")),
    farbe_raender: [farbe(5, skala(heizen, "raum")) === farbe(14, skala(heizen, "raum")),
      farbe(30, skala(heizen, "raum")) === farbe(24, skala(heizen, "raum"))],
    schalttext: [1, 0].map((wert) => wertText(wert, skala(schalten))),
    schalttext_englisch: [1, 0].map((wert) =>
      wertText(wert, skala(schalten), (text) => ({{ Ein: "On", Aus: "Off" }})[text])
    ),
    temperaturtext: wertText(20.55, skala(heizen), () => "falsch"),
    wert_jetzt: wertJetzt(heizen, {{ tag: "Mo", minute: 10 * 60 }}),
    wechsel_heute: naechsterWechsel(heizen, {{ tag: "Mo", minute: 10 * 60 }}),
    wechsel_nach_mitternacht: naechsterWechsel(heizen, {{ tag: "Mo", minute: 23 * 60 }}),
    wechsel_wochenende: naechsterWechsel(heizen, {{ tag: "Fr", minute: 23 * 60 }}),
    wechsel_spaeter_tag: naechsterWechsel(vorlauf, {{ tag: "Mo", minute: 23 * 60 }}),
    wechsel_keiner: naechsterWechsel(nur21, {{ tag: "We", minute: 600 }}),
    wechsel_ohne_block: naechsterWechsel(vorlauf, {{ tag: "Tu", minute: 600 }}),
    dienst: nachDienst(heizen),
    fehler_zuviele: pruefen(zuviele),
    fehler_doppelter_tag: pruefen(doppelterTag),
    fehler_ohne_tag: pruefen(ohneTag),
    fehler_doppelte_zeit: pruefen(doppelteZeit),
    fehler_leer: pruefen([]),
    sauber: pruefen(heizen),
    gleich_trotz_reihenfolge: gleich(heizen, zurueckgemeldet),
    gleich_bei_abweichung: gleich(heizen, schalten),
    jetzt_mittag: jetztStelle(heizen, {{ tag: "Mo", minute: 10 * 60 }}),
    jetzt_spaet: jetztStelle(heizen, {{ tag: "Fr", minute: 23 * 60 + 45 }}),
    jetzt_frueh: jetztStelle(heizen, {{ tag: "Tu", minute: 15 }}),
    jetzt_ohne_block: jetztStelle(deutsch, {{ tag: "Mo", minute: 600 }}),
    ortszeit_utc: ortszeit(new Date("2026-09-21T21:45:00Z"), "UTC"),
    ortszeit_wien: ortszeit(new Date("2026-09-21T22:30:00Z"), "Europe/Vienna"),
    teile: nachTeilen(kreis).map((teil) => [teil.teil, teil.programme.length]),
    gruppen: gruppieren(kreis.filter((p) => p.teil === "hk")).map((gruppe) => [
      gruppe.schluessel,
      gruppe.eintraege.map((e) => [e.programm.entity, e.vorlauf ? e.vorlauf.entity : null]),
    ]),
    heute_text: heuteText(heizen, {{ tag: "Mo", minute: 600 }}, skala(heizen, "raum")),
    heute_text_spaeter: heuteText(vorlauf, {{ tag: "Mo", minute: 1400 }}, skala(vorlauf, "vorlauf")),
    heute_ohne_block: heuteText(vorlauf, {{ tag: "Tu", minute: 600 }}, skala(vorlauf, "vorlauf")),
    ortszeit_falsche_zone: ortszeit(new Date("2026-09-21T10:00:00Z"), "Nirgendwo/Stadt").tag !== null,
  }})
);
""",
        encoding="utf-8",
    )
    # Ohne `encoding` liest Windows die Ausgabe in der Codepage der Konsole,
    # und aus dem Gedankenstrich in „Mo–Fr" wird Zeichensalat.
    ausgabe = subprocess.run(
        ["node", str(skript)], capture_output=True, text=True, encoding="utf-8", check=True
    )
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


def test_wochentage_werden_zu_spannen_zusammengefasst(rechnung):
    """Sieben gleiche Zeilen sagen nichts, was „täglich" nicht auch sagt."""
    assert rechnung["bereich_taeglich"] == "täglich"
    assert rechnung["bereich_spanne"] == "Mo–Fr"
    # Bei zwei Tagen wäre „Sa–So" länger als die Aufzählung.
    assert rechnung["bereich_paar"] == "Sa, So"
    assert rechnung["bereich_luecke"] == "Mo–Mi, Fr"
    assert rechnung["bereich_leer"] == "kein Tag"


def test_raster_zeigt_bloecke_statt_sieben_gleicher_zeilen(rechnung):
    """Ein Block je Zeile – so führt die Anlage das Programm auch."""
    assert rechnung["bloecke_als_zeilen"] == [["Mo–Fr", 2], ["Sa, So", 1]]


def test_tage_ohne_block_bekommen_eine_leere_zeile(rechnung):
    """Sonst fiele nicht auf, dass für sechs Tage nichts hinterlegt ist."""
    # Mo hat drei Abschnitte: Ein ab 05:00, Aus ab 08:00, davor der Umlauf.
    assert rechnung["zeile_ohne_programm"] == [["Mo", 3], ["Di–So", 0]]


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
    assert rechnung["skala_schalten"] == {"min": 0, "max": 1, "schalt": True, "art": "schalt"}
    assert rechnung["skala_heizen"]["schalt"] is False


def test_die_farbskala_ist_fest(rechnung):
    """Gleiche Temperatur, gleiche Farbe – unabhängig von den übrigen Werten des Programms."""
    assert rechnung["skala_heizen"] == {"min": 14, "max": 24, "schalt": False, "art": "raum"}
    assert rechnung["farbe_gleich"] is True
    # Außerhalb der Skala gilt die Endfarbe.
    assert rechnung["farbe_raender"] == [True, True]


def test_vorlauf_liegt_auf_der_wasserskala(rechnung):
    assert rechnung["skala_vorlauf"] == {"min": 40, "max": 65, "schalt": False, "art": "wasser"}


def test_ohne_art_entscheidet_der_wert_ueber_die_skala(rechnung):
    """Eine Raumtemperatur über 30 °C gibt es nicht."""
    assert rechnung["skala_geraten"] == ["raum", "wasser"]


# ---------------------------------------------------------------------------
# Heute: jetzt und der nächste Wechsel
# ---------------------------------------------------------------------------
def test_der_wert_jetzt_kommt_aus_dem_heutigen_block(rechnung):
    assert rechnung["wert_jetzt"] == 21


def test_der_naechste_wechsel_am_selben_tag(rechnung):
    assert rechnung["wechsel_heute"] == {"tag": "Mo", "tage": 0, "minute": 1320, "wert": 16}


def test_der_naechste_wechsel_nach_mitternacht(rechnung):
    """Um 23 Uhr gilt 16 °C; der Umlauf bis 06:00 ist kein Wechsel, erst 06:00 ist einer."""
    assert rechnung["wechsel_nach_mitternacht"] == {
        "tag": "Tu",
        "tage": 1,
        "minute": 360,
        "wert": 21,
    }


def test_gleicher_wert_nach_mitternacht_zaehlt_nicht(rechnung):
    """Freitag 23 Uhr 16 °C, das Wochenende beginnt mit 21 °C ab 00:00 – das ist der Wechsel."""
    assert rechnung["wechsel_wochenende"] == {"tag": "Sa", "tage": 1, "minute": 0, "wert": 21}


def test_der_naechste_wechsel_an_einem_spaeteren_tag(rechnung):
    """Ein Block nur für Montag: Der nächste Wechsel ist eine Woche später."""
    assert rechnung["wechsel_spaeter_tag"] == {"tag": "Mo", "tage": 7, "minute": 300, "wert": 55}


def test_ohne_wechsel_oder_ohne_block_gibt_es_keinen(rechnung):
    assert rechnung["wechsel_keiner"] is None
    assert rechnung["wechsel_ohne_block"] is None


# ---------------------------------------------------------------------------
# Schreiben
# ---------------------------------------------------------------------------
def test_schaltwerte_folgen_der_sprache(rechnung):
    assert rechnung["schalttext"] == ["Ein", "Aus"]
    assert rechnung["schalttext_englisch"] == ["On", "Off"]
    assert rechnung["temperaturtext"] == "20.6 °C"


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


# ---------------------------------------------------------------------------
# Was jetzt gilt
# ---------------------------------------------------------------------------
def test_jetzt_liegt_im_abschnitt_der_uhrzeit(rechnung):
    assert rechnung["jetzt_mittag"] == {"block": 0, "von": 360}


def test_spaet_abends_gilt_der_letzte_abschnitt_bis_mitternacht(rechnung):
    assert rechnung["jetzt_spaet"] == {"block": 0, "von": 1320}


def test_nach_mitternacht_gilt_der_umlauf_des_vortags(rechnung):
    """Vor dem ersten Schaltpunkt gilt der letzte des Tages weiter."""
    assert rechnung["jetzt_frueh"] == {"block": 0, "von": 0}


def test_ein_tag_ohne_block_hat_kein_jetzt(rechnung):
    assert rechnung["jetzt_ohne_block"] is None


def test_die_ortszeit_folgt_der_zeitzone_von_home_assistant(rechnung):
    assert rechnung["ortszeit_utc"] == {"tag": "Mo", "minute": 21 * 60 + 45}
    # 22:30 UTC ist in Wien schon Dienstag, 00:30.
    assert rechnung["ortszeit_wien"] == {"tag": "Tu", "minute": 30}


def test_eine_unbekannte_zeitzone_faellt_auf_den_browser(rechnung):
    assert rechnung["ortszeit_falsche_zone"] is True


# ---------------------------------------------------------------------------
# Seite: Gruppen je Anlagenteil und der Text im Heute-Streifen
# ---------------------------------------------------------------------------
def test_programme_werden_je_anlagenteil_gesammelt(rechnung):
    assert rechnung["teile"] == [["hk", 6], ["pu", 1]]


def test_vorlauf_haengt_am_raumprogramm_gleicher_nummer(rechnung):
    """Ohne Raumprogramm gleicher Nummer steht das Vorlaufprogramm allein in der Gruppe."""
    assert rechnung["gruppen"] == [
        [
            "heizen",
            [["sensor.p1", "sensor.v1"], ["sensor.v3", None], ["sensor.p2", None]],
        ],
        ["warmwasser", [["sensor.ww", None]]],
        ["allein:sensor.frei", [["sensor.frei", None]]],
    ]


def test_der_heute_text_nennt_jetzt_und_den_wechsel(rechnung):
    assert rechnung["heute_text"] == "jetzt 21 °C · ab 22:00 16 °C"


def test_ein_wechsel_an_einem_anderen_tag_nennt_den_wochentag(rechnung):
    assert rechnung["heute_text_spaeter"] == "jetzt 10 °C · ab Mo 05:00 55 °C"


def test_ohne_block_fuer_heute_steht_kein_zeitplan(rechnung):
    assert rechnung["heute_ohne_block"] == "heute kein Zeitplan"
