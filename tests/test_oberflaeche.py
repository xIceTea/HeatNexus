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
import re
import shutil
import subprocess
from urllib.parse import unquote

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
            _entitaet("switch.lagerraumbefuellung", "Lagerraumbefüllung anfordern"),
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
            _entitaet("sensor.programm_1", "Programm 1", adresse="3/61"),
            _entitaet(
                "sensor.programm_2", "Programm 2", adresse="3/62", bezeichnung="Übergangszeit"
            ),
            _entitaet("sensor.ww_programm", "WW-Programm", adresse="5/61"),
            _entitaet(
                "select.betriebswahl",
                "Betriebswahl",
                adresse="3/50",
                optionen={0: "Standby", 1: "Programm 1", 2: "Programm 2", 3: "Programm 3"},
            ),
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
    labelkarte = [
        {
            "id": "marke:solar",
            "titel": "Solarthermie",
            "zeilen": [
                {
                    "entity": "sensor.kollektor",
                    "titel": "Kollektor",
                    "symbol": "mdi:solar-power-variant",
                }
            ],
        }
    ]
    return {
        "anlagen": [
            modul._anlage_daten(
                {"name": "Heizhaus", "teile": [kessel, heizkreis, puffer, zsp]}, None, labelkarte
            )
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


def test_nach_der_betriebswahl_werden_die_verwandten_werte_gelesen(durchlauf):
    """Die Anlage setzt mit der Betriebswahl auch den Sollwert neu.

    Ohne Nachfassen stünde er bis zum nächsten Abruf auf dem alten Stand.
    """
    aufrufe = durchlauf["betriebswahl"]["aufrufe"]
    assert aufrufe and aufrufe[0]["dienst"] == "select.select_option"
    nachgefasst = [a for a in aufrufe if a["dienst"] == "homeassistant.update_entity"]
    assert nachgefasst, "Nach der Auswahl wird nichts nachgelesen"
    assert "climate.heizkreis" in nachgefasst[0]["entitaeten"]


def test_das_aktive_zeitprogramm_hebt_sich_ab(durchlauf):
    """Vier gleich aussehende Karten sagen sonst nicht, welche gerade gilt."""
    aktiv = durchlauf["zeitprogramme"]["aktiveKarten"]
    # Betriebswahl „Programm 1": das Heizprogramm gilt, Warmwasser gilt immer
    # außer auf Standby, Programm 2 gilt nicht.
    assert aktiv == ["Programm 1", "WW-Programm"], aktiv


def test_das_aktive_zeitprogramm_traegt_eine_textmarke(durchlauf):
    """Farbe allein trägt keine Aussage; die Marke steht bei jeder aktiven Karte."""
    assert durchlauf["zeitprogramme"]["aktivMarken"] == ["· aktiv", "· aktiv"]


def test_ausserhalb_der_zeitprogramme_hebt_sich_keine_karte_ab(durchlauf):
    """Die Hervorhebung gilt dem Programm, nicht jeder Karte mit einem Hinweis."""
    assert durchlauf["uebersicht"]["aktiveKarten"] == []


def test_das_nachfassen_reicht_ueber_eine_minute(durchlauf):
    """Die Steuerung rechnet den Sollwert auch mal erst nach über zwölf Sekunden."""
    assert durchlauf["betriebswahl"]["geplant"] >= 7


def test_das_nachfassen_endet_sobald_der_wert_nachgezogen_ist(durchlauf):
    """Sonst kostete jede Bedienung acht Runden Anfragen an die Anlage."""
    nachgefasst = [
        a
        for a in durchlauf["betriebswahl"]["aufrufe"]
        if a["dienst"] == "homeassistant.update_entity"
    ]
    assert len(nachgefasst) == 1


def test_nach_der_betriebswahl_laedt_der_sollwert(durchlauf):
    """Der alte Sollwert stünde sonst neben „übernommen ✓", bis die Steuerung nachrechnet."""
    sollwert = durchlauf["betriebswahl"]["sollwert"]
    assert sollwert["wartet"] == "lädt …"
    assert sollwert["nachgezogen"] == "21.5 °C"
    assert sollwert["danach"] == "20 °C"


def test_der_sollwert_im_regler_oeffnet_den_heizkreis(durchlauf):
    """Ohne Raumfühler ist der Sollwert die einzige große Zahl der Karte."""
    assert durchlauf["betriebswahl"]["sollwertOeffnet"] == ["climate.heizkreis"]


def test_eine_abgelehnte_betriebswahl_laesst_den_sollwert_stehen(durchlauf):
    """Nach einer Ablehnung kommt kein neuer Sollwert, auf den zu warten wäre."""
    assert durchlauf["betriebswahl"]["sollwert"]["abgelehnt"] == "20 °C"


def test_die_eigene_auswahl_beendet_das_nachfassen_nicht(durchlauf):
    """Ihre Anzeige kann nach dem Aufruf eintreffen; der Sollwert steht dann noch."""
    assert durchlauf["betriebswahl"]["spaeteAnzeige"] > 1


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
    assert schaubild["dunkel"] != schaubild["hell"]
    # Ein Wert, den der helle Satz wirklich austauscht. Vor- und Rücklauf
    # stehen in jedem Satz gleich und taugen dafür nicht.
    tabelle = anlage["schema_farben"]["hell"]
    dunkler_wert = next(alt for alt, neu in tabelle.items() if alt != neu)
    assert unquote(schaubild["dunkel"]).count(dunkler_wert) > 0
    assert unquote(schaubild["hell"]).count(dunkler_wert) == 0


def test_die_werkzeuge_liegen_hinter_einem_knopf(durchlauf):
    """Einzelne Symbole wachsen mit jedem Werkzeug in die Kopfzeile hinein."""
    assert durchlauf["werkzeugmenueDa"] is True
    assert durchlauf["werkzeugeZu"] is True
    assert durchlauf["werkzeugeOffen"] is True
    assert durchlauf["werkzeuge"] == ["Ansicht bearbeiten", "Dashboard-Vorlage"]
    assert durchlauf["werkzeugeNachKlickZu"] is True


def test_die_dashboard_vorlage_steht_zum_kopieren_bereit(durchlauf):
    """Das mitgelieferte Dashboard ist nicht zu bearbeiten – sein Text schon."""
    assert durchlauf["vorlageFuerVerwalter"] is True
    assert durchlauf["yamlImFenster"] is True


def test_die_dashboard_vorlage_nennt_die_feste_adresse(durchlauf):
    """Links und Zurück-Pfeile der Kopie führen weiter ins mitgelieferte Dashboard."""
    assert "/heatnexus/" in durchlauf["yamlHinweis"]


def test_ohne_verwalterrecht_keine_dashboard_vorlage(durchlauf):
    """Wer keine Dashboards anlegen darf, kann mit der Vorlage nichts anfangen."""
    assert durchlauf["werkzeugeOhneRecht"] == ["Ansicht bearbeiten"]


def test_ein_misslungenes_speichern_wird_gemeldet(durchlauf):
    """Sonst bleibt der Fehlschlag in der Entwicklerkonsole stehen."""
    assert durchlauf["meldungBeimSpeichern"] == ["Die Farbwahl konnte nicht gespeichert werden."]


def test_der_farbsatz_faerbt_auch_die_oberflaeche(durchlauf):
    """Nicht nur das Bild: Die Karten, Reiter und Linien folgen mit.

    Gesetzt werden die Variablen am Wirtselement; „Automatisch" räumt sie ab
    und überlässt das Feld wieder Home Assistant.
    """
    assert durchlauf["palette"]["terrakotta"] == "#d98e46"
    assert durchlauf["palette"]["auto"] == ""


def test_der_farbsatz_steht_vor_den_einstellungen_bereit(durchlauf):
    """Sonst zeigt der erste Aufbau den Standardanstrich und springt dann um."""
    assert durchlauf["gemerkt"]["gesetzt"] == "petrol"
    assert durchlauf["gemerkt"]["beimAufbau"] == "petrol"


def test_der_abzug_der_anmeldung_ueberschreibt_nichts_frisches(durchlauf):
    """Nach einem Verbindungsabriss käme sonst der Stand der Einrichtung zurück."""
    assert durchlauf["wiederverbunden"]["name"] == "frisch"


def test_die_eigene_wahl_schlaegt_das_erscheinungsbild(durchlauf, aufteilung):
    """Wer einen Farbsatz wählt, bekommt ihn – auch gegen das helle Thema."""
    anlage = aufteilung["anlagen"][0]
    schaubild = durchlauf["schaubild"]
    # Trotz hellem Erscheinungsbild: der gewählte Satz gilt.
    assert schaubild["terrakotta"] not in (schaubild["hell"], schaubild["dunkel"])
    assert schaubild["wahlDunkel"] == schaubild["dunkel"]
    terrakotta = anlage["schema_farben"]["terrakotta"]
    assert unquote(schaubild["terrakotta"]).count(next(iter(terrakotta.values()))) > 0


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


def test_eine_vorgabe_auf_zeit_verdeckt_die_ladung_nicht(abbruch):
    """Die Betriebsart zeigt „Eco / Comfort“; die Freigabe belegt die Ladung."""
    assert "Freigabe auf Ja bei Eco / Comfort: Taste bricht ab" in abbruch["faelle"]
    assert "nachlaufende Pumpe ohne Freigabe: keine Ladung" in abbruch["faelle"]


def test_eine_auswahl_nein_ja_startet_und_beendet_die_ladung(abbruch):
    assert "Auswahl Nein/Ja: Ja startet, Nein beendet" in abbruch["faelle"]


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


def test_die_labelkarte_steht_in_der_uebersicht(durchlauf):
    """Sie hängt an der Anlage; global geführt erschiene sie an jeder."""
    assert "Solarthermie" in durchlauf["uebersicht"]["titel"]


# Der Rückfragedialog mit mehreren Zahlenfeldern: Leistung und Laufzeit gelten
# beide für die ganze Abgasmessung.
DIALOG = Path(__file__).parent / "js" / "kaminkehrer-dialog.mjs"


@pytest.fixture(scope="module")
def dialog() -> dict:
    """Den Dialog in Node fahren – ohne Browser, ohne Anlage."""
    lauf = subprocess.run(
        ["node", str(DIALOG), str(PANEL_JS)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr or lauf.stdout
    return json.loads(lauf.stdout)


def test_beide_werte_werden_vor_dem_ausloesen_geschrieben(dialog):
    """Ein Feld allein hieße: messen mit einer Vorgabe, die nicht gilt."""
    assert "zwei Felder: beide Werte geschrieben, dann ausgelöst" in dialog["faelle"]


def test_ein_abgebrochener_dialog_schreibt_nichts(dialog):
    assert "Abbruch: kein Schreibvorgang" in dialog["faelle"]


def test_ohne_schreibbare_laufzeit_bleibt_ein_feld(dialog):
    """Meldet die Anlage Schreibschutz, fehlt das zweite Feld."""
    assert "ohne Laufzeit: nur die Leistung" in dialog["faelle"]


def test_unter_der_stoerung_steht_die_abhilfe(durchlauf):
    """Der Text sagt, was ansteht; die Abhilfe, was zu tun ist."""
    assert durchlauf["uebersicht"]["abhilfe"] == ["schließen"]


# ---------------------------------------------------------------------------
# Zeitprogramm aktivieren
# ---------------------------------------------------------------------------
def test_die_bezeichnung_steht_im_kartentitel(durchlauf):
    assert any("Programm 2 – Übergangszeit" in t for t in durchlauf["zeitprogramme"]["titel"])


def test_aktivieren_steht_nur_an_programmen_die_nicht_gelten(durchlauf):
    """Programm 1 gilt schon; nur Programm 2 bietet die Taste an."""
    assert durchlauf["aktivieren"]["vorher"] == 1


def test_waehrend_der_umstellung_ist_keine_taste_zu_sehen(durchlauf):
    assert durchlauf["aktivieren"]["waehrendUmstellung"] == 0


def test_nach_der_umstellung_wechselt_die_taste_zum_alten_programm(durchlauf):
    assert durchlauf["aktivieren"]["danach"] == ["Programm 1"]


def test_ohne_verfuegbare_auswahl_fehlt_die_taste(durchlauf):
    assert durchlauf["aktivieren"]["nichtVerfuegbar"] == []


def test_aktivieren_fragt_vorher_nach(durchlauf):
    aktivieren = durchlauf["aktivieren"]
    assert aktivieren["frage"] == (
        "Betriebswahl von „Programm 1“ auf „Programm 2 – Übergangszeit“ umstellen?"
    )
    assert aktivieren["nachNein"] == 0


def test_aktivieren_stellt_die_betriebswahl_um(durchlauf):
    assert durchlauf["aktivieren"]["gesetzt"] == "Programm 2"


# ---------------------------------------------------------------------------
# Bezeichnung
# ---------------------------------------------------------------------------
def test_der_dialog_traegt_die_bezeichnung_im_titel(durchlauf):
    assert durchlauf["bezeichnung"]["titel"] == "Programm 2 – Übergangszeit"


def test_das_bezeichnungsfeld_erscheint_erst_beim_bearbeiten(durchlauf):
    bezeichnung = durchlauf["bezeichnung"]
    assert bezeichnung["imLesen"] == 0
    assert bezeichnung["vorbelegt"] == "Übergangszeit"


def test_eine_geaenderte_bezeichnung_schreibt_nur_die_bezeichnung(durchlauf):
    """Die Zeiten sind unverändert; das Programm der Anlage bleibt unberührt."""
    bezeichnung = durchlauf["bezeichnung"]
    assert [a["bezeichnung"] for a in bezeichnung["gesendet"]] == ["Winter"]
    assert bezeichnung["gesendet"][0]["entity_id"] == "sensor.programm_2"
    assert not bezeichnung["programmGeschrieben"]
    assert bezeichnung["neuGeholt"]
    assert bezeichnung["dialogZu"]


def test_uebernehmen_ist_waehrend_des_speicherns_gesperrt(durchlauf):
    assert durchlauf["bezeichnung"]["gesperrt"]


def test_bezeichnung_und_zeiten_zugleich_behalten_die_rueckmeldung(durchlauf):
    """Der Neuaufbau ersetzt die Karte; die Rückmeldung steht an der neuen."""
    fall = durchlauf["bezeichnungUndZeiten"]
    assert fall["geschrieben"]
    assert fall["waehrend"] == ["wird ausgeführt …"]
    assert fall["bestaetigt"] == ["übernommen ✓"]
    assert any("Programm 2 – Sommer" in t for t in fall["titel"])


def test_die_betriebswahl_zeigt_die_bezeichnung(durchlauf):
    optionen = {o["wert"]: o["text"] for o in durchlauf["optionen"]}
    assert optionen["Programm 2"] == "Programm 2 – Übergangszeit"
    assert optionen["Programm 1"] == "Programm 1"


def test_der_dialog_hebt_die_spanne_von_jetzt_hervor(durchlauf):
    """Montag 10:00 liegt im Abschnitt 06:00 – 22:00 des Wochentagsblocks."""
    assert durchlauf["zeitprogrammDialog"]["lesen"]["jetzt"] == ["06:00 – 22:00"]


def test_die_marke_jetzt_steht_vor_dem_wert(durchlauf):
    """Der Wert bleibt am rechten Rand, damit die Werte untereinander stehen."""
    assert durchlauf["zeitprogrammDialog"]["lesen"]["jetztFolge"] == [
        ["zp-spannezeit", "zp-jetzt", "zp-spannewert"]
    ]


def test_der_reiter_automatik_folgt_dem_entwurf(durchlauf):
    """Eingerichtet: Karte mit Marke, Feldern und Protokoll; sonst die Einladung."""
    automatik = durchlauf["automatik"]
    assert automatik["marken"] == ["Sonnentag · beobachtet"]
    assert automatik["felder"] == 22  # Profil, zwei Heizgrenzen und neunzehn Werte
    assert automatik["geaendert"] == 1
    assert automatik["protokoll"] == 1
    assert automatik["einladungen"] == 1
    assert automatik["tagesleiste"] == 1
    assert "Einrichtung bearbeiten" in automatik["knoepfe"]
    assert "Automatik entfernen" in automatik["knoepfe"]
    assert automatik["kacheln"] == ["aussentemperatur", "sonne", "raum"]
    assert automatik["skalen"] == 3
    assert "1 von 4 Eingriffen heute" in automatik["meta"]
    assert "Gemischt" in automatik["meta"]
    assert f"Nächste Prüfung {automatik['naechstePruefungUhrzeit']}" in automatik["meta"]
    assert (automatik["alteEingriffe"], automatik["alteProfilzeile"]) == (0, 0)
    assert automatik["raumZonen"] == 4
    # Innerhalb von ±2 K steht der Wert nur in der Kachel, nicht noch einmal am Punkt.
    assert automatik["raumWert"] == ""
    assert automatik["grenzenEingaben"] == 2
    assert automatik["gruppen"] == [
        "Heizgrenze",
        "Sonnentag",
        "Zeitplan",
        "Schutz und Prognose",
        "Manuell mit Empfehlung",
    ]
    assert automatik["ausrichtung"] == [
        ["Eco", "false"],
        ["Ausgewogen", "true"],
        ["Komfort", "false"],
    ]
    (hinweis,) = automatik["hinweise"]
    assert "Nichts davon ging an die Steuerung" in hinweis


def test_reiter_lassen_sich_umordnen_und_ausblenden(durchlauf):
    reiter = durchlauf["reiter"]
    standard = ["uebersicht", "steuerung", "automatik", "wartung", "verlauf", "zeitprogramme"]
    assert reiter["ohneHilfe"] == standard
    umgestellt = ["uebersicht", "zeitprogramme", "steuerung", "automatik", "wartung", "verlauf"]
    assert reiter["verschoben"] == umgestellt
    assert reiter["ausgeblendet"] == [r for r in umgestellt if r != "verlauf"]
    assert reiter["gesendet"] == {
        "reiter": [*umgestellt, "hilfe"],
        "reiter_versteckt": ["verlauf", "hilfe"],
    }


def test_die_werte_der_automatik_oeffnen_ihre_entitaet(durchlauf):
    """Zustand, Eingriffe, nächste Prüfung und die Kachelwerte öffnen den Mehr-Info-Dialog."""
    assert sorted(durchlauf["automatik"]["klickbar"]) == sorted(
        ["automatik-marke", "klickbar", "klickbar", "neben", "zahl", "zahl"]
    )


def test_prognose_anpassen_zeigt_seine_wirkung(durchlauf):
    """Neben dem Schalter steht, um wie viel die Anpassung die Prognose verschiebt."""
    automatik = durchlauf["automatik"]
    assert automatik["korrekturSchalter"] == ["true"]
    assert automatik["korrektur"] == [["Außen −1,4 K", True], ["Sonne +12 %", True]]


def test_eine_offene_eingabe_uebersteht_den_neuaufbau(durchlauf):
    """Ein Klick im Tagesverlauf baut neu; die Heizgrenze 19 bleibt eingetragen und speicherbar."""
    assert durchlauf["automatik"]["entwurfNachAufbau"] == ["19", False, True]


def test_heizgrenze_und_eigener_wert_laden_einmal_nach(durchlauf):
    """Beide Aufrufe gehen nacheinander hinaus, danach folgt genau ein Abruf; der Entwurf ist weg."""
    automatik = durchlauf["automatik"]
    assert automatik["gemeinsamGespeichert"] == [
        "heatnexus/automatik/heizgrenzen",
        "heatnexus/automatik/einstellen",
        "heatnexus/automatik",
    ]
    assert automatik["entwurfNachSpeichern"] is False


def test_speichern_ist_nur_mit_einer_abweichung_aktiv(durchlauf):
    """Grau ohne Änderung, aktiv nach einer Eingabe, grau nach der Rückkehr zum gespeicherten Wert."""
    automatik = durchlauf["automatik"]
    assert automatik["speichernGrau"] is True
    assert automatik["speichernFolge"] == [False, True]


def test_der_reiter_automatik_laedt_nach_ohne_zu_stoeren(durchlauf):
    """Ein offener Dialog bleibt; die Sperre fürs Nachladen hält nicht über den Aufbau hinaus."""
    automatik = durchlauf["automatik"]
    assert automatik["dialogBleibt"] is True
    assert automatik["sperreNachAufbau"] is False
    assert automatik["sperreNachZuklappen"] is False
    assert automatik["erweitertBleibtOffen"] is True
    assert automatik["gespeichert"] == ["übernommen ✓"]
    # Die Metazeile steht als eigene Zeile unter dem Kopf, nicht mehr darin.
    assert automatik["kopf"] == [
        "h2",
        "automatik-marke",
        "automatik-knopf",
        "fragezeichen",
    ]
    assert automatik["dialogKopf"] is True
    assert automatik["kreuzSchliesst"] is True
    assert automatik["raumliste"] == [["Bad", "20,8 → 21,0 °C · heizt"]]
    assert automatik["raumSkalaMitListe"] == 4
    assert automatik["raumKachel"] == ["−0,2 K", "Ø 21,4 °C"]
    assert automatik["vorrangWahl"] is True
    assert automatik["vorrangZeile"] == ["Vorrangquellen 1,5 h"]
    assert automatik["modusStunden"] > 0
    assert automatik["stundenLegende"] == 1
    # Die Erklärung der Farben ist auch am Handy erreichbar, nicht nur als Tooltip.
    assert automatik["legendeHilfe"] == [1]
    assert automatik["stundenKasten"] == ["10:00 Uhr"]
    assert automatik["stundeOffen"] == 1
    # Die Auswahl gehört dem Kreis, in dem geklickt wurde, nicht dem ganzen Reiter.
    assert automatik["stundeJeKreis"] == [["SN1-2-0", 10]]


def test_eine_offene_empfehlung_hat_einen_uebernehmen_knopf(durchlauf):
    """Im Modus „Manuell mit Empfehlung“ zeigt der Hinweis die Begründung und übernimmt per Knopf."""
    empfehlung = durchlauf["automatikEmpfehlung"]
    assert empfehlung["modus"] == [
        ["Beobachten", "false"],
        ["Manuell mit Empfehlung", "true"],
        ["Automatisch", "false"],
    ]
    (hinweis,) = empfehlung["hinweise"]
    assert "Heizpause empfohlen: 22 °C Außentemperatur." in hinweis
    assert empfehlung["knopf"] == "Übernehmen"
    assert empfehlung["knoepfe"] == ["Übernehmen", "Verwerfen"]
    # Der Kasten hebt sich als Empfehlung ab, nicht nur durch seine Knöpfe.
    assert empfehlung["markiert"] is True
    assert empfehlung["titel"] == ["Empfehlung"]
    assert empfehlung["aufrufe"][0] == ["heatnexus/automatik/empfehlung_uebernehmen", "SN1-2-0"]
    assert empfehlung["punkt"] == [True, False]


def test_die_automatik_steht_bei_allen_anlagen_in_einem_raster(durchlauf):
    """Eingerichtete Kreise zuerst, über Anlagen hinweg; die Anlage steht im Titel."""
    alle = durchlauf["automatikAlle"]
    assert alle["raster"] == 1
    assert alle["trenner"] == 0
    assert alle["titel"][0] == "Anlage B · Heizkreis"
    assert alle["titel"][-1] == "Anlage A · Heizkreis 2"


ENGLISCH = Path(__file__).parent / "js" / "englisch-durchlauf.mjs"
WOERTERBUCH = WURZEL / "custom_components" / "heatnexus" / "sprachen" / "en.json"


def test_auf_englisch_bleibt_kein_uebersetzbarer_text_deutsch(aufteilung, tmp_path):
    """Jeder angezeigte Text mit englischer Fassung erscheint auch englisch.

    Geprüft wird nach Aufbau und Aktualisierung: Texte, die eine Bindung später
    setzt, laufen nicht durch den Übersetzungsdurchlauf und brauchen `_t`.
    """
    from custom_components.heatnexus.texte import Woerterbuch, uebersetze_baum

    englisch = json.loads(WOERTERBUCH.read_text(encoding="utf-8"))
    nutzlast = uebersetze_baum(aufteilung, Woerterbuch("en"))
    datei = tmp_path / "daten.json"
    datei.write_text(json.dumps({**nutzlast, "texte": englisch}), encoding="utf-8")
    ergebnis = subprocess.run(
        ["node", str(ENGLISCH), str(PANEL_JS), str(datei)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert ergebnis.returncode == 0, ergebnis.stderr[:2000]

    reste = sorted(
        {
            teil
            for text in json.loads(ergebnis.stdout)
            for teil in [text, *text.split(" – ")]
            if englisch.get(teil, teil) != teil
        }
    )

    assert not reste, f"auf Englisch noch deutsch: {reste}"


# Merkmale deutscher Sätze: Umlaute und häufige kurze Wörter.
DEUTSCH = re.compile(
    r"[äöüÄÖÜß]|(und|der|die|das|nicht|bis|von|mit|keine|seit|oder|für|zum|zur|Uhr|heute|Wert)"
)


def _texte_der_nutzlast(wert) -> set[str]:
    """Namen aus den Daten: Sie dürfen deutsch sein, die Oberfläche übersetzt sie nicht."""
    if isinstance(wert, dict):
        return set().union(*(_texte_der_nutzlast(v) for v in wert.values()))
    if isinstance(wert, list):
        return set().union(*(_texte_der_nutzlast(v) for v in wert)) if wert else set()
    return {wert} if isinstance(wert, str) and len(wert) > 2 else set()


def test_auf_englisch_bleibt_kein_deutscher_text_ohne_eintrag(aufteilung, tmp_path):
    """Findet auch Texte, die ganz ohne Eintrag im Wörterbuch stehen, etwa zusammengesetzte Titel."""
    from custom_components.heatnexus.texte import Woerterbuch, uebersetze_baum

    englisch = json.loads(WOERTERBUCH.read_text(encoding="utf-8"))
    nutzlast = uebersetze_baum(aufteilung, Woerterbuch("en"))
    datei = tmp_path / "daten.json"
    datei.write_text(json.dumps({**nutzlast, "texte": englisch}), encoding="utf-8")
    ergebnis = subprocess.run(
        ["node", str(ENGLISCH), str(PANEL_JS), str(datei)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert ergebnis.returncode == 0, ergebnis.stderr[:2000]
    namen = sorted(_texte_der_nutzlast(nutzlast), key=len, reverse=True)

    def ohne_namen(text: str) -> str:
        for name in namen:
            text = text.replace(name, "")
        return text

    reste = sorted(t for t in json.loads(ergebnis.stdout) if DEUTSCH.search(ohne_namen(t)))
    assert not reste, f"auf Englisch noch deutsch: {reste}"
