"""Die Oberfläche einmal wirklich aufbauen, nicht nur laden.

**Der Anlass steht in `ordnung.js`.** Beim Schnitt der Panel-Datei in
ES-Module blieben zwei Zeitkonstanten ohne `export` zurück, während die
Oberfläche sie weiter benutzte. Laden ließ sich alles; erst beim Aufräumen
einer Rückmeldung flog ein `ReferenceError`, und „wird ausgeführt …" blieb am
Gerät für immer stehen. Ein Ladetest fängt so etwas nicht – nur ein Durchlauf.

Gefahren wird der Durchlauf in Node gegen eine schmale DOM-Attrappe
(`js/dom-attrappe.mjs`). Die Aufteilung kommt aus der echten Serverseite
(`panel/daten.py`), damit beide Seiten gegeneinander geprüft sind: Was Python
liefert, muss der Browser auch verarbeiten.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from .conftest import requires_ha

pytestmark = [
    requires_ha(),
    pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden"),
]

WURZEL = Path(__file__).resolve().parents[1]
PANEL_JS = WURZEL / "custom_components" / "heatnexus" / "frontend" / "heatnexus-panel.js"
DURCHLAUF = Path(__file__).parent / "js" / "oberflaeche-durchlauf.mjs"


def _entitaet(entity_id: str, name: str, **rest):
    eintrag = {
        "entity_id": entity_id,
        "name": name,
        "kategorie": None,
        "bereich": entity_id.split(".")[0],
        "hat_wert": True,
        "wert": 21.5,
        "text": "21.5",
        "state_class": None,
    }
    eintrag.update(rest)
    return eintrag


def _teil(name: str, fct_type: int, entitaeten: list):
    return {
        "name": name,
        "id": f"geraet_{name}",
        "anlage_id": "steuerung",
        "fct_type": fct_type,
        "rang": 0,
        "symbol": "mdi:fire",
        "entitaeten": entitaeten,
    }


@pytest.fixture(scope="module")
def aufteilung() -> dict:
    """Eine Anlage mit allem, was die Oberfläche zeichnen kann."""
    from custom_components.heatnexus import panel as modul

    kessel = _teil(
        "PuroWIN",
        25,
        [
            _entitaet("sensor.kesseltemperatur_ist", "Kesseltemperatur Ist"),
            _entitaet("sensor.betriebsphase", "Betriebsphase"),
            _entitaet("sensor.kesselleistung", "Kesselleistung"),
            _entitaet("sensor.vorratsbehaelter", "Vorratsbehälter"),
            _entitaet("sensor.laufzeit_asche", "Laufzeit bis Ascheentleerung"),
            _entitaet("sensor.betriebsstunden", "Betriebsstunden", state_class="total_increasing"),
            _entitaet("button.serviceausbrand", "Serviceausbrand"),
            _entitaet("button.lagerraumbefuellung", "Lagerraumbefüllung anfordern"),
            _entitaet("select.gewaehlter_brennstoff", "Gewählter Brennstoff"),
            _entitaet("switch.kaminkehrer", "Kaminkehrer"),
            _entitaet("sensor.meldung_klartext", "Meldung Klartext", kategorie="diagnostic"),
        ],
    )
    heizkreis = _teil(
        "UMLZ HEIZKREIS",
        14,
        [
            _entitaet("climate.umlz_heizkreis", "UMLZ HEIZKREIS"),
            _entitaet("sensor.aussentemperatur", "Außentemperatur"),
            _entitaet("sensor.raumtemperatur_ist", "Raumtemperatur Ist"),
            _entitaet("sensor.vorlauftemperatur_ist", "Vorlauftemperatur Ist"),
            _entitaet("sensor.warmwasser_ist", "Warmwasser Ist-Temperatur"),
            _entitaet("sensor.programm_1", "Programm 1"),
            _entitaet("sensor.ww_programm", "WW-Programm"),
            _entitaet("select.betriebswahl", "Betriebswahl"),
            _entitaet("number.behaglichkeitskorrektur", "Behaglichkeitskorrektur"),
            _entitaet("number.dauer", "Dauer"),
            _entitaet("number.temperatur", "Temperatur"),
            # Die Einschalthysterese steht als Zahlenfeld neben der Ladetaste –
            # der einzige Wert der Oberfläche, den man dort direkt verstellt.
            _entitaet("number.hysterese_ein", "Hysterese Ein", wert=5.0, text="5"),
            _entitaet("switch.ww_einmalladung", "WW Einmalladung"),
        ],
    )
    puffer = _teil(
        "B-PLMi PUFFER",
        16,
        [
            _entitaet("sensor.puffer_oben", "Puffer oben"),
            _entitaet("sensor.puffer_unten", "Puffer unten"),
            _entitaet("select.betriebswahl_puffer", "Betriebswahl"),
        ],
    )
    # Das Pumpen-/Relaismodul: Sein Leitwert ist die Wärmeanforderung, und die
    # gibt es an einer Anlage, die das Modul nur als Relais benutzt, nie.
    zsp = _teil(
        "ZSP-2",
        20,
        [
            _entitaet("sensor.analog_sollwert", "Analog-Sollwert", wert=0.0, text="0"),
            _entitaet("sensor.pumpendrehzahl", "Pumpendrehzahl"),
        ],
    )
    return {
        "anlagen": [
            modul._anlage_daten({"name": "Heizhaus", "teile": [kessel, heizkreis, puffer, zsp]})
        ],
        "uebersteuerung": {
            "eco": {"temperatur": 18, "dauer": 120},
            "comfort": {"temperatur": 22, "dauer": 180},
        },
        "aussentemperatur": "sensor.aussentemperatur",
    }


@pytest.fixture(scope="module")
def durchlauf(aufteilung, tmp_path_factory) -> dict:
    datei = tmp_path_factory.mktemp("oberflaeche") / "daten.json"
    datei.write_text(json.dumps(aufteilung), encoding="utf-8")
    ergebnis = subprocess.run(
        ["node", str(DURCHLAUF), str(PANEL_JS), str(datei)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert ergebnis.returncode == 0, (
        f"Die Oberfläche ist beim Aufbau gescheitert:\n{ergebnis.stderr[:2000]}"
    )
    return json.loads(ergebnis.stdout)


# ---------------------------------------------------------------------------
# Jeder Reiter muss sich aufbauen lassen
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "reiter", ["uebersicht", "steuerung", "wartung", "verlauf", "zeitprogramme"]
)
def test_jeder_reiter_baut_karten(durchlauf, reiter):
    """Ein leerer Reiter hieße: Die Aufteilung kommt im Browser nicht an."""
    assert durchlauf[reiter]["karten"] > 0, f"Reiter {reiter} bleibt leer"


def test_karten_haengen_am_zustand(durchlauf):
    """Ohne Bindungen stünden die Karten still, sobald sich ein Wert ändert."""
    assert durchlauf["uebersicht"]["bindungen"] > 0


def test_anordnen_gibt_jeder_karte_einen_griff(durchlauf):
    assert durchlauf["anordnen"]["griffe"] > 0


def test_ohne_waermeanforderung_steht_ein_strich(durchlauf):
    """Liegt keine Wärmeanforderung an, steht in der Zeile ein Strich.

    Bis 1.5.0-beta.9 verschwand die Zeile ganz und mit ihr das Anlagenteil aus
    der Liste; danach stand dort „keine Anforderung" – und direkt darunter
    noch einmal „Anforderung". Ein „0,0 °C" wiederum behauptete eine
    Anforderung mit null Grad.
    """
    assert durchlauf["uebersicht"]["ohneAnforderung"] > 0


def test_zwischen_schaltzeit_und_wert_steht_ein_strich(durchlauf):
    """Sonst standen „06:00" und „21,0 °C" nur durch ein Leerzeichen getrennt da."""
    schaltzeiten = durchlauf["zeitprogramme"]["schaltzeiten"]
    assert schaltzeiten, "Das Wochenraster zeigt keine Schaltzeiten"
    assert all(" – " in text for text in schaltzeiten), schaltzeiten


def test_der_zeitprogramm_dialog_zeigt_erst_die_spannen(durchlauf):
    """Wie im Bediengerät: „06:00 – 19:00", nicht zwei Startpunkte.

    Wer wissen will, wann geheizt wird, soll die Spanne lesen und nicht zwei
    Zeilen im Kopf zusammenrechnen.
    """
    lesen = durchlauf["zeitprogrammDialog"]["lesen"]
    assert lesen["spannen"], "Die Leseansicht zeigt keine Spannen"
    assert all(" – " in text for text in lesen["spannen"]), lesen["spannen"]
    assert lesen["editoren"] == 0, "Der Editor steht schon vor dem Bearbeiten da"
    assert lesen["tasten"] == ["Schließen", "Bearbeiten"]


def test_erst_bearbeiten_holt_die_startpunkte(durchlauf):
    """Eingestellt wird der Startpunkt – ein Punkt gilt, bis der nächste kommt.

    Ohne diese Überschrift liest man die Zeilen wie die Spannen der
    Leseansicht und verstellt die falsche Zeit.
    """
    bearbeiten = durchlauf["zeitprogrammDialog"]["bearbeiten"]
    assert bearbeiten["editoren"] == 1
    assert bearbeiten["spannen"] == 0, "Spannen und Startpunkte stehen gemischt da"
    assert bearbeiten["startpunkte"], "Die Punktetabelle sagt nicht, was sie einstellt"
    assert set(bearbeiten["startpunkte"]) == {"Startpunkt"}
    # Und die Leiste sagt, dass jetzt etwas zu übernehmen ist.
    assert bearbeiten["tasten"] == ["Verwerfen", "Übernehmen"]


def test_das_zahlenfeld_hat_eigene_pfeile(durchlauf):
    """Die des Browsers sind abgeschaltet – ganz ohne blieb nur noch Tippen.

    Am Telefon ist ein 22 px breiter Pfeil der Unterschied zwischen „geht" und
    „geht nicht".
    """
    assert durchlauf["steuerung"]["zahlPfeile"] >= 2


def test_die_ladeschwelle_heisst_nach_dem_was_sie_tut(durchlauf):
    """„Nachladen ab" las sich wie eine Temperatur; gemeint ist der Abstand."""
    assert "Freigabe ab Abweichung" in durchlauf["steuerung"]["zahlFelder"]


# ---------------------------------------------------------------------------
# Bedienen: übertragen, bestätigen, aufräumen
# ---------------------------------------------------------------------------
def test_der_dienst_wird_wirklich_gerufen(durchlauf):
    assert "climate.set_temperature" in durchlauf["bedienen"]["dienste"]


def test_die_rueckmeldung_durchlaeuft_ihre_drei_stufen(durchlauf):
    """Und räumt am Ende auf.

    Der letzte Schritt ist der, der am Gerät gefehlt hat: Ohne ihn bleibt
    „übernommen ✓" stehen, und die Karte zeigt nie wieder ihren Zustand.
    """
    bedienen = durchlauf["bedienen"]
    assert bedienen["waehrend"] == "wird ausgeführt …"
    assert bedienen["bestaetigt"] == "übernommen ✓"
    assert bedienen["aufgeraeumt"] == ""


# ---------------------------------------------------------------------------
# Farbsatz des Schaubilds
# ---------------------------------------------------------------------------
def test_das_schaubild_folgt_dem_erscheinungsbild(durchlauf, aufteilung):
    """Hell und Dunkel kommen beide mit, gewählt wird im Browser.

    Serverseitig ist beim Zeichnen nicht bekannt, welches Erscheinungsbild
    gilt, und beim Umschalten berechnet niemand die Aufteilung neu – deshalb
    hängt die Auswahl an einer Bindung und nicht am Aufbau.
    """
    anlage = aufteilung["anlagen"][0]
    schaubild = durchlauf["schaubild"]
    assert schaubild["dunkel"] == anlage["schema"]
    assert schaubild["hell"] == anlage["schema_hell"]
    assert schaubild["hell"] != schaubild["dunkel"]


def test_der_farbsatz_faerbt_auch_die_oberflaeche(durchlauf):
    """Nicht nur das Bild: Die Karten, Reiter und Linien folgen mit.

    Gesetzt werden die Variablen am Wirtselement; „Automatisch" räumt sie ab
    und überlässt das Feld wieder Home Assistant.
    """
    assert durchlauf["palette"]["terrakotta"] == "#d98e46"
    assert durchlauf["palette"]["auto"] == ""


def test_die_eigene_wahl_schlaegt_das_erscheinungsbild(durchlauf, aufteilung):
    """Wer einen Farbsatz wählt, bekommt ihn – auch gegen das helle Thema."""
    anlage = aufteilung["anlagen"][0]
    schaubild = durchlauf["schaubild"]
    assert schaubild["terrakotta"] == anlage["schema_terrakotta"]
    assert schaubild["wahlDunkel"] == anlage["schema"]


# ---------------------------------------------------------------------------
# Warmwasserladung abbrechen
#
# Der Fehler, den es hier zu halten gilt: Bis 1.5.0 hing der Abbruchzweig
# zusätzlich an der Betriebswahl und ihrem Rückkehrmuster. Fehlte eines von
# beiden, fiel der Druck durch bis zum Auslöser und startete die Ladung noch
# einmal. Am Gerät sah das aus, als passierte gar nichts – „lädt gerade" stand
# sofort wieder da, ohne Meldung.
# ---------------------------------------------------------------------------
ABBRUCH = Path(__file__).parent / "js" / "ladung-abbrechen.mjs"


@pytest.fixture(scope="module")
def abbruch() -> dict:
    """Den Tastendruck in Node fahren – ohne Browser, ohne Anlage."""
    lauf = subprocess.run(
        ["node", str(ABBRUCH), str(PANEL_JS)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr or lauf.stdout
    # Eine Warnung auf der Fehlerausgabe wäre hier ein Produktfehler: Der
    # Durchlauf meldet dort, wenn eine Bestätigung nicht prüfbar war.
    assert not lauf.stderr.strip(), lauf.stderr
    return json.loads(lauf.stdout)


def test_eine_laufende_ladung_wird_beendet_statt_neu_gestartet(abbruch):
    """Derselbe Druck, entgegengesetzte Wirkung – daran hing der Fehler."""
    assert "laufende Ladung: zurück auf den Zustand von vorher" in abbruch["faelle"]


def test_ohne_rueckkehrpunkt_bleibt_der_ausloeser_nicht_stehen(abbruch):
    """Kein zweiter Start – aber auch kein stummes Nichts.

    Ein stummer Neustart ist das Schlimmste: Er sieht aus wie eine kaputte
    Oberfläche und heizt trotzdem weiter. Gar nichts zu tun war die zweite
    Stufe desselben Fehlers.
    """
    assert "ohne Betriebswahl: Auslöser zurück, kein zweiter Start" in abbruch["faelle"]
    assert "Betriebswahl ohne Zustand: nur der Auslöser, kein zweiter Start" in abbruch["faelle"]


def test_ohne_laufende_ladung_loest_die_taste_aus(abbruch):
    """Die Gegenprobe – sonst ließe sich gar nicht mehr laden."""
    assert "ruhende Anlage: Ladung wird ausgelöst" in abbruch["faelle"]


def test_der_zweite_druck_raet_kein_programm(abbruch):
    """Der zweite gemeldete Fehler – und der gefährlichere.

    Nach dem ersten Abbruch ist der gemerkte Zustand verbraucht, die Ladung
    aber bis zum nächsten Abruf noch als laufend gemeldet. Wer dann noch
    einmal drückt, bekam die Anlage kommentarlos auf „Heizprogramm 1"
    gestellt – ein Programm, das nie jemand gewählt hatte.
    """
    assert "zweiter Druck: kein geratenes Programm" in abbruch["faelle"]


def test_der_erste_druck_wirkt_auch_ohne_gemerkten_zustand(abbruch):
    """Der gemeldete Fehler „geht erst beim zweiten Klick".

    Ist der Zustand von vor der Ladung unbekannt – Seite neu geladen oder am
    Gerät gestartet –, schrieb der Abbruch die Betriebswahl auf den Wert, der
    dort schon stand. Ein Schreibvorgang ohne Wirkung: Die Ladung lief weiter,
    „wird ausgeführt …" blieb daneben stehen.
    """
    assert "unbekannter Rückkehrpunkt: Auslöser zurückgenommen" in abbruch["faelle"]


def test_der_druck_wirkt_sofort_und_sperrt_die_taste(abbruch):
    """Die Anlage wird alle 30 s abgefragt – so lange sah es aus wie nichts.

    Bis dahin stand unverändert „läuft" und dieselbe Beschriftung da. Also
    drückte man noch einmal, und der zweite Druck traf auf den alten Zustand.
    """
    assert "Druck wirkt sofort, zweiter Druck ist gesperrt" in abbruch["faelle"]


def test_die_bestaetigung_gibt_die_taste_wieder_frei(abbruch):
    """Sonst bliebe sie nach jeder Bedienung eine dreiviertel Minute tot."""
    assert "bestaetigte Bedienung gibt die Taste sofort wieder frei" in abbruch["faelle"]


def test_die_nachlaufende_ladepumpe_ist_keine_ladung(abbruch):
    """`5/5` „Modus Ladepumpennachlauf" – die Pumpe dreht nach dem Auftrag weiter.

    Stand sie vor der Betriebsart, meldete die Taste nach einem Abbruch wieder
    „läuft" und bot ein zweites Mal Abbrechen an – für eine Ladung, die es
    nicht mehr gab. Genau so war es gemeldet.
    """
    assert "nachlaufende Pumpe gilt nicht als laufende Ladung" in abbruch["faelle"]


def test_ohne_betriebsart_zaehlt_weiter_die_pumpe(abbruch):
    """Die Gegenprobe: An manchen Kreisen meldet die Betriebsart gar nichts."""
    assert "ohne lesbare Betriebsart bleibt die Pumpe der Beleg" in abbruch["faelle"]
