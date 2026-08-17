"""Aufbau der eigenen Oberfläche.

Die Aufteilung entsteht aus Geräte- und Entitätsliste, also aus reinen
Funktionen – prüfbar ohne Anlage und ohne laufende Home-Assistant-Instanz.

Der Anlass für diese Tests: In 1.0.0 blieb die Oberfläche halb leer, weil die
Aufteilung berechnet wurde, während die Anlage noch eingelesen wurde. Die
Entitäten waren da, ihre Werte noch nicht – und ein fehlender Wert schloss die
Zeile aus. Genau das prüft `test_zeilen_entstehen_auch_ohne_werte`.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def panel():
    from custom_components.heatnexus import panel as modul

    return modul


def entitaet(entity_id: str, name: str, **rest):
    """Ein Registry-Eintrag in der Form, die `dashboard._anlagen` liefert."""
    eintrag = {
        "entity_id": entity_id,
        "name": name,
        "kategorie": None,
        "bereich": entity_id.split(".")[0],
        "hat_wert": True,
        "wert": None,
        "state_class": None,
    }
    eintrag.update(rest)
    return eintrag


def anlage(*teile):
    return {"name": "Heizhaus", "teile": list(teile)}


def teil(name: str, fct_type: int, entitaeten: list):
    return {
        "name": name,
        "id": f"geraet_{name}",
        "anlage_id": "steuerung",
        "fct_type": fct_type,
        "rang": 0,
        "symbol": "mdi:fire",
        "entitaeten": entitaeten,
    }


@pytest.fixture
def kessel_und_heizkreis():
    kessel = teil(
        "PuroWIN",
        25,
        [
            entitaet("sensor.kesseltemperatur_ist", "Kesseltemperatur Ist"),
            entitaet("sensor.betriebsphase", "Betriebsphase"),
            entitaet("sensor.kesselleistung", "Kesselleistung"),
            entitaet("button.serviceausbrand", "Serviceausbrand"),
            entitaet("switch.ww_einmalladung", "WW Einmalladung"),
            entitaet("sensor.meldung_klartext", "Meldung Klartext", kategorie="diagnostic"),
        ],
    )
    heizkreis = teil(
        "UMLZ HEIZKREIS",
        14,
        [
            entitaet("climate.umlz_heizkreis", "UMLZ HEIZKREIS"),
            entitaet("sensor.aussentemperatur", "Außentemperatur"),
            entitaet("sensor.vorlauftemperatur_ist", "Vorlauftemperatur Ist"),
            entitaet("sensor.warmwasser_ist", "Warmwasser Ist-Temperatur"),
            entitaet("sensor.warmwasser_soll", "Warmwasser Soll-Temperatur"),
            entitaet("binary_sensor.ww_zirkulationspumpe", "WW-Zirkulationspumpe"),
        ],
    )
    return anlage(kessel, heizkreis)


# ---------------------------------------------------------------------------
# Der Fehler aus 1.0.0
# ---------------------------------------------------------------------------
def test_zeilen_entstehen_auch_ohne_werte(panel, kessel_und_heizkreis):
    """Ohne Wert darf keine Zeile wegfallen – sonst bleibt die Seite leer.

    Beim ersten Aufbau läuft der Vollabzug noch; die Entitäten stehen schon in
    der Registry, ihre Werte kommen erst mit dem nächsten Abruf.
    """
    for anlagenteil in kessel_und_heizkreis["teile"]:
        for e in anlagenteil["entitaeten"]:
            e["hat_wert"] = False

    daten = panel._anlage_daten(kessel_und_heizkreis)

    assert daten["kennwerte"], "Kennwerte fehlen, obwohl die Entitäten existieren"
    assert daten["status"], "Systemstatus fehlt, obwohl die Entitäten existieren"
    assert daten["warmwasser"], "Warmwasser fehlt, obwohl die Entitäten existieren"
    assert daten["heizkreise"], "Heizkreis fehlt, obwohl das Thermostat existiert"
    assert daten["schnellzugriff"], "Schnellzugriff fehlt"


def test_die_oberflaeche_findet_auch_ohne_deutsche_namen(panel):
    """Der eigentliche Zweck der kanonischen Schlüssel.

    Liefert die Anlage ihre Namen in einer anderen Sprache, greift kein
    einziges Muster mehr. Die Adresse bleibt dieselbe – also muss die
    Aufteilung allein daraus entstehen können. Ohne diesen Nachweis fiele die
    Umstellung erst auf, wenn jemand die zweite Sprache einschaltet, und dann
    nur als leere Karte ohne Fehlermeldung.
    """
    kessel = teil(
        "PuroWIN",
        25,
        [
            entitaet(
                "sensor.boiler_temperature",
                "Boiler temperature",
                schluessel="boiler_temperature",
            ),
            entitaet("sensor.operating_phase", "Operating phase", schluessel="operating_phase"),
            entitaet("sensor.boiler_power", "Boiler output", schluessel="boiler_power"),
            entitaet(
                "sensor.outdoor_temperature",
                "Outdoor temperature",
                schluessel="outdoor_temperature",
            ),
        ],
    )

    daten = panel._anlage_daten(anlage(kessel))

    assert [k["untertitel"] for k in daten["kennwerte"]] == ["Kesseltemperatur"]
    assert [z["titel"] for z in daten["status"]] == [
        "Betriebszustand",
        "Außentemperatur",
        "Kesselleistung",
    ]
    assert daten["aussentemperatur"] == "sensor.outdoor_temperature"
    assert "sensor.boiler_temperature" in daten["verlauf"]


def test_die_laufzeit_verdraengt_den_betriebszustand_nicht(panel):
    """Beide sitzen auf derselben Adresse, gesucht ist die Betriebsphase.

    Die Ableitung stand alphabetisch vor ihrer Quelle und hatte einen Wert –
    damit gewann sie die Zeile, und der Betriebszustand zeigte Minuten.
    """
    kessel = teil(
        "PuroWIN",
        25,
        [
            entitaet(
                "sensor.aktuelle_laufzeit",
                "Aktuelle Laufzeit",
                schluessel="operating_phase_runtime",
            ),
            entitaet("sensor.betriebsphase", "Betriebsphase", schluessel="operating_phase"),
        ],
    )

    zeilen = {z["titel"]: z["entity"] for z in panel._anlage_daten(anlage(kessel))["status"]}

    assert zeilen["Betriebszustand"] == "sensor.betriebsphase"


def test_die_stoerung_nennt_ihren_melder(panel):
    """Der Klartext sagt was, der Ja/Nein-Sensor daneben sagt ob."""
    kessel = teil(
        "PuroWIN",
        25,
        [
            entitaet("sensor.meldung_klartext", "Meldung Klartext", kategorie="diagnostic"),
            entitaet(
                "binary_sensor.stoerung_gemeldet",
                "Störung gemeldet",
                kategorie="diagnostic",
            ),
        ],
    )

    stoerungen = panel._anlage_daten(anlage(kessel))["stoerungen"]

    assert stoerungen == [
        {
            "entity": "sensor.meldung_klartext",
            "titel": "Meldung Klartext",
            "melder": "binary_sensor.stoerung_gemeldet",
        }
    ]


def test_ohne_melder_bleibt_die_stoerung_bestehen(panel):
    """Ein Erkennungsstand von vor dem Ja/Nein-Sensor führt ihn nicht."""
    kessel = teil(
        "PuroWIN",
        25,
        [entitaet("sensor.meldung_klartext", "Meldung Klartext", kategorie="diagnostic")],
    )

    stoerungen = panel._anlage_daten(anlage(kessel))["stoerungen"]

    assert stoerungen[0]["melder"] is None


def test_wert_hat_vorrang_vor_wertloser_entitaet(panel):
    """Gibt es beide, gewinnt die Entität mit Wert."""
    anlagenteil = teil(
        "PuroWIN",
        25,
        [
            entitaet("sensor.alt", "Kesseltemperatur Ist", hat_wert=False),
            entitaet("sensor.neu", "Kesseltemperatur Ist", hat_wert=True),
        ],
    )
    treffer = panel._erster(anlagenteil["entitaeten"], r"kesseltemperatur ist")
    assert treffer["entity_id"] == "sensor.neu"


# ---------------------------------------------------------------------------
# Warmwasser hängt am Heizkreis, nicht an einem eigenen Anlagenteil
# ---------------------------------------------------------------------------
def test_warmwasser_wird_am_heizkreis_gefunden(panel, kessel_und_heizkreis):
    daten = panel._anlage_daten(kessel_und_heizkreis)
    namen = [w["titel"] for w in daten["warmwasser"]]
    assert "Warmwasser Ist-Temperatur" in namen
    assert "WW-Zirkulationspumpe" in namen


def test_ohne_warmwasser_bleibt_die_karte_leer(panel):
    """Ein Heizkreis ohne Warmwasserbereitung darf nichts vortäuschen."""
    ohne = anlage(
        teil(
            "Südbau",
            14,
            [
                entitaet("climate.hebebuehne", "Südbau"),
                entitaet("sensor.vorlauftemperatur_ist", "Vorlauftemperatur Ist"),
            ],
        )
    )
    assert panel._anlage_daten(ohne)["warmwasser"] == []


def test_reine_parameter_beweisen_kein_warmwasser(panel):
    """Der Fehler aus 1.1.0-beta.1: Das Heizhaus zeigte eine Warmwasserkarte.

    Ein Heizkreis führt die Warmwasser-*Parameter* auch dann, wenn kein
    Speicher daran hängt – gemessen wird dort aber nichts, und „WW-Kreis"
    steht auf 0. Genau so meldet es die Anlage im Heizhaus.
    """
    ohne = anlage(
        teil(
            "Südbau",
            14,
            [
                entitaet("climate.hebebuehne", "Südbau"),
                entitaet("number.ww_ueberhoehung", "WW-Überhöhung"),
                entitaet("binary_sensor.ww_ladepumpe", "WW-Ladepumpe"),
                entitaet("number.ww_ladevorrang", "WW-Ladung max. Ladevorrang"),
                entitaet("sensor.ww_kreis", "WW-Kreis", wert=0.0),
            ],
        )
    )
    assert panel._anlage_daten(ohne)["warmwasser"] == []


def test_gemeldeter_warmwasserkreis_genuegt(panel):
    """Meldet die Anlage den Kreis, gibt es ihn – auch ohne eigenen Istwert."""
    mit = anlage(
        teil(
            "UMLZ HEIZKREIS",
            14,
            [
                entitaet("climate.umlz", "UMLZ HEIZKREIS"),
                entitaet("sensor.ww_kreis", "WW-Kreis", wert=1.0),
                entitaet("binary_sensor.ww_ladepumpe", "WW-Ladepumpe"),
            ],
        )
    )
    assert panel._anlage_daten(mit)["warmwasser"]


def test_abgas_rezirkulation_ist_kein_warmwasser(panel):
    """„Rezirkulation" enthält „Zirkulation" – ohne Wortgrenze zählte sie mit."""
    kessel = anlage(
        teil(
            "PuroWIN",
            25,
            [
                entitaet("sensor.warmwasser_ist", "Warmwasser Ist-Temperatur"),
                entitaet("sensor.abgas_rezirkulation", "Abgas-Rezirkulation"),
            ],
        )
    )
    namen = [w["titel"] for w in panel._anlage_daten(kessel)["warmwasser"]]
    assert "Abgas-Rezirkulation" not in namen


def test_thermostat_zaehlt_nicht_als_warmwasser(panel):
    """Ein Heizkreis namens „Warmwasser" ist trotzdem ein Heizkreis."""
    seltsam = anlage(teil("Warmwasser Nord", 14, [entitaet("climate.ww_nord", "Warmwasser Nord")]))
    daten = panel._anlage_daten(seltsam)
    assert daten["warmwasser"] == []
    assert daten["heizkreise"][0]["entity"] == "climate.ww_nord"


# ---------------------------------------------------------------------------
# Reiter „Steuerung" und „Wartung"
# ---------------------------------------------------------------------------
def test_steuerung_findet_heizkreis_und_warmwasser(panel, kessel_und_heizkreis):
    steuerung = panel._anlage_daten(kessel_und_heizkreis)["steuerung"]
    assert steuerung["heizkreise"][0]["entity"] == "climate.umlz_heizkreis"
    assert steuerung["warmwasser"]["ist"] == "sensor.warmwasser_ist"
    assert steuerung["warmwasser"]["laden"] == "switch.ww_einmalladung"


def test_steuerung_ohne_warmwasser_bleibt_leer(panel):
    ohne = anlage(teil("Südbau", 14, [entitaet("climate.hebebuehne", "Südbau")]))
    assert panel._anlage_daten(ohne)["steuerung"]["warmwasser"] is None


def test_steuerung_nimmt_die_betriebswahl_des_kreises(panel):
    mit = anlage(
        teil(
            "UMLZ HEIZKREIS",
            14,
            [
                entitaet("climate.umlz", "UMLZ HEIZKREIS"),
                entitaet("select.betriebswahl", "Betriebswahl"),
                entitaet("sensor.heizprogramm", "Heizprogramm 1"),
            ],
        )
    )
    kreis = panel._anlage_daten(mit)["steuerung"]["heizkreise"][0]
    assert kreis["betriebswahl"] == "select.betriebswahl"
    assert kreis["programm"] == "sensor.heizprogramm"


def test_wartung_trennt_restlaufzeit_von_zaehler(panel):
    anlagenteil = teil(
        "PuroWIN",
        25,
        [
            entitaet("sensor.laufzeit_asche", "Laufzeit bis Ascheentleerung"),
            entitaet("sensor.betriebsstunden", "Betriebsstunden", state_class="total_increasing"),
            entitaet("sensor.vorratsbehaelter", "Vorratsbehälter"),
        ],
    )
    wartung = panel._anlage_daten(anlage(anlagenteil))["wartung"]
    assert [z["titel"] for z in wartung["restlaufzeiten"]] == ["Laufzeit bis Ascheentleerung"]
    assert [z["titel"] for z in wartung["zaehler"]] == ["Betriebsstunden"]
    assert [z["titel"] for z in wartung["brennstoff"]] == ["Vorratsbehälter"]


# ---------------------------------------------------------------------------
# Zeitprogramme
# ---------------------------------------------------------------------------
def test_zeitprogramme_tragen_ihren_anlagenteil(panel):
    """Zwei Anlagen melden gleich benannte Programme.

    „Programm 1" gibt es an jedem Heizkreis. Ohne den Anlagenteil daneben
    stünden im Reiter mehrere gleich beschriftete Karten, und niemand wüsste,
    welche zu welchem Kreis gehört.
    """
    kreis = teil(
        "UMLZ HEIZKREIS",
        14,
        [
            entitaet("sensor.programm_1", "Programm 1"),
            entitaet("sensor.ww_programm", "WW-Programm"),
            entitaet("sensor.vorlauftemperatur_ist", "Vorlauftemperatur Ist"),
        ],
    )
    programme = panel._anlage_daten(anlage(kreis))["zeitprogramme"]
    assert [p["titel"] for p in programme] == ["Programm 1", "WW-Programm"]
    assert {p["anlagenteil"] for p in programme} == {"UMLZ HEIZKREIS"}
    assert programme[0]["entity"] == "sensor.programm_1"


def test_zirkulationsprogramm_sagt_wann_es_wirkt(panel):
    """`5/6` entscheidet, ob die Pumpe dem Programm überhaupt folgt.

    Steht sie auf Temperatur- oder Impulssteuerung, läuft das schönste
    Zirkulationsprogramm ins Leere. Versteckt wird die Karte trotzdem nicht –
    vorbereiten können muss man es.
    """
    kreis = teil(
        "UMLZ HEIZKREIS",
        14,
        [
            entitaet("sensor.ww_zirkulationsprogramm", "WW-Zirkulationsprogramm"),
            entitaet("select.ww_zirkulationspumpe", "WW-Zirkulationspumpe"),
            entitaet("sensor.programm_1", "Programm 1"),
        ],
    )
    programme = {p["titel"]: p for p in panel._anlage_daten(anlage(kreis))["zeitprogramme"]}
    wirkung = programme["WW-Zirkulationsprogramm"]["wirkung"]
    assert wirkung["entity"] == "select.ww_zirkulationspumpe"
    assert wirkung["muster"] == "zeitsteuerung"
    # Das Heizprogramm hängt an nichts – es wirkt immer.
    assert "wirkung" not in programme["Programm 1"]


def test_von_zwei_zirkulationsprogrammen_bleibt_das_wirksame(panel):
    """Die Anlage führt zwei – wortgleich benannt, nur die Adresse trennt sie.

    `5/65` gilt bei Zeitsteuerung, `5/64` bei Temperatursteuerung. Ohne die
    Unterscheidung standen zwei gleichnamige Karten nebeneinander, und keine
    sagte, welche gerade wirkt. Versteckt wird jeweils die der **anderen**
    Art – bei „Aus" oder Impulssteuerung bleiben beide stehen.
    """
    kreis = teil(
        "UMLZ HEIZKREIS",
        14,
        [
            entitaet(
                "sensor.zirkulationsprogramm_zeit",
                "WW-Zirkulationsprogramm",
                schluessel="dhw_circulation_program_time",
            ),
            entitaet(
                "sensor.zirkulationsprogramm_temperatur",
                "WW-Zirkulationsprogramm",
                schluessel="dhw_circulation_program_temperature",
            ),
            entitaet(
                "select.ww_zirkulationspumpe",
                "WW-Zirkulationspumpe",
                schluessel="dhw_circulation_mode",
            ),
        ],
    )
    programme = {p["entity"]: p for p in panel._anlage_daten(anlage(kreis))["zeitprogramme"]}
    nach_zeit = programme["sensor.zirkulationsprogramm_zeit"]["wirkung"]
    nach_temperatur = programme["sensor.zirkulationsprogramm_temperatur"]["wirkung"]

    # Jedes verschwindet, sobald die Pumpe der anderen Art folgt.
    assert nach_zeit["verbergen_bei"] == "temperatursteuerung"
    assert nach_temperatur["verbergen_bei"] == "zeitsteuerung"
    # Und jedes nennt die Steuerungsart, bei der es selbst greift.
    assert nach_zeit["muster"] == "zeitsteuerung"
    assert nach_temperatur["muster"] == "temperatursteuerung"
    assert "Temperatursteuerung" in nach_temperatur["hinweis"]


def test_ein_einzelnes_zirkulationsprogramm_wird_nie_versteckt(panel):
    """Ohne Schlüssel keine Zuordnung – dann bleibt es bei Hinweis statt Verstecken."""
    kreis = teil(
        "UMLZ HEIZKREIS",
        14,
        [
            entitaet("sensor.ww_zirkulationsprogramm", "WW-Zirkulationsprogramm"),
            entitaet("select.ww_zirkulationspumpe", "WW-Zirkulationspumpe"),
        ],
    )
    programme = {p["titel"]: p for p in panel._anlage_daten(anlage(kreis))["zeitprogramme"]}
    assert "verbergen_bei" not in programme["WW-Zirkulationsprogramm"]["wirkung"]


def test_nur_sensoren_kommen_als_zeitprogramm_in_frage(panel):
    """Die Betriebswahl heißt „Programm 1", ist aber eine Auswahl.

    Was am Ende wirklich ein Zeitprogramm ist, entscheidet die Oberfläche am
    Attribut `blocks`; hier fällt schon einmal alles weg, was gar kein Sensor
    ist.
    """
    kreis = teil(
        "UMLZ HEIZKREIS",
        14,
        [
            entitaet("select.betriebswahl", "Betriebswahl"),
            entitaet("number.urlaubsprogramm", "Urlaubsprogramm"),
        ],
    )
    assert panel._anlage_daten(anlage(kreis))["zeitprogramme"] == []


# ---------------------------------------------------------------------------
# Rückfragen
# ---------------------------------------------------------------------------
def test_serviceausbrand_fragt_nach(panel, kessel_und_heizkreis):
    daten = panel._anlage_daten(kessel_und_heizkreis)
    eintraege = {e["titel"]: e for e in daten["schnellzugriff"]}
    assert eintraege["Serviceausbrand"]["frage"], "Serviceausbrand muss nachfragen"


def test_warmwasserladung_fragt_nicht_nach(panel, kessel_und_heizkreis):
    """Was harmlos ist, darf nicht mit einer Rückfrage genervt werden."""
    daten = panel._anlage_daten(kessel_und_heizkreis)
    eintraege = {e["titel"]: e for e in daten["schnellzugriff"]}
    assert eintraege["Warmwasser laden"]["frage"] == ""


# ---------------------------------------------------------------------------
# Störungen und Kennwerte
# ---------------------------------------------------------------------------
def test_stoerungen_kommen_aus_der_diagnose(panel, kessel_und_heizkreis):
    daten = panel._anlage_daten(kessel_und_heizkreis)
    assert [s["entity"] for s in daten["stoerungen"]] == ["sensor.meldung_klartext"]


def test_je_anlagenteil_ein_leitwert(panel, kessel_und_heizkreis):
    """Die linke Spalte zeigt je Anlagenteil **einen** Leitwert, nicht alle.

    Ausnahme sind Warmwasser und Zirkulation: Sie hängen als Datenpunkte am
    Heizkreis, liest man aber täglich und einzeln – sie bekommen deshalb ihre
    eigene Zeile. Ohne die Ausnahme stünde am Heizkreis nur die Raumtemperatur
    und das Warmwasser gar nicht.
    """
    daten = panel._anlage_daten(kessel_und_heizkreis)
    leitwerte = [
        e for e in daten["kennwerte"] if e["untertitel"] not in ("Warmwasser", "Zirkulation")
    ]
    assert len(leitwerte) == len(kessel_und_heizkreis["teile"])
    assert daten["kennwerte"][0]["entity"] == "sensor.kesseltemperatur_ist"


def test_leere_anlage_ergibt_leere_aufteilung(panel):
    daten = panel._anlage_daten(anlage())
    assert daten["kennwerte"] == []
    assert daten["heizkreise"] == []
    assert daten["schema_svg"] is None


def test_das_pufferprogramm_nennt_seine_betriebswahl(panel):
    """`20/15` entscheidet, ob der Puffer seinem Zeitprogramm folgt.

    Es kennt Standby, Automatik-, Festbrennstoff-, Puffer-, Hand- und
    Kaminkehrerbetrieb – und „Auto mit Zeitprogramm". Nur dort greift das
    Programm. Versteckt wird die Karte trotzdem nicht: Anders als bei der
    Zirkulation gibt es kein zweites Programm, das stattdessen gälte.
    """
    puffer = teil(
        "B-PLMi PUFFER",
        16,
        [
            # So heißt `4/82` an der Anlage wirklich. „Programm Puffer" stand
            # hier bis 1.5.0-beta.10 und war erfunden.
            entitaet("sensor.pufferprogramm", "Zeitprogramm"),
            entitaet(
                "select.puffer_betriebswahl",
                "Betriebswahl",
                schluessel="buffer_mode_selection",
            ),
        ],
    )
    programme = {p["titel"]: p for p in panel._anlage_daten(anlage(puffer))["zeitprogramme"]}
    wirkung = programme["Zeitprogramm"]["wirkung"]
    assert wirkung["entity"] == "select.puffer_betriebswahl"
    assert wirkung["muster"] == "zeitprogramm"
    # Kein Verstecken – es gibt kein konkurrierendes zweites Programm.
    assert "verbergen_bei" not in wirkung


def test_das_estrichprogramm_ist_kein_zeitprogramm(panel):
    """`4/60` heißt schlicht „Programm" und ist das Estrich-Ausheizprogramm.

    Es kennt *beenden*, *Belegreifheizen* und *Funktionsheizen* – keine
    Schaltzeiten. Mit dem bloßen Teilwort „programm" stand es im Reiter
    Zeitprogramme und verdrängte als erster Treffer die echten Programme aus
    der Steuerungsübersicht, sobald jemand den Datenpunkt einschaltete.
    """
    kreis = teil(
        "UMLZ HEIZKREIS",
        14,
        [
            entitaet("climate.umlz_heizkreis", "UMLZ HEIZKREIS"),
            entitaet("sensor.programm", "Programm"),
            entitaet("sensor.programm_1", "Programm 1"),
        ],
    )
    daten = panel._anlage_daten(anlage(kreis))

    titel = [p["titel"] for p in daten["zeitprogramme"]]
    assert "Programm" not in titel
    assert "Programm 1" in titel
    # Und in der Steuerungsübersicht steht das echte Programm, nicht „beenden".
    assert daten["steuerung"]["heizkreise"][0]["programm"] == "sensor.programm_1"


def test_jedes_zeitprogramm_traegt_sein_eigenes_symbol(panel):
    """Warmwasser und Zirkulation hängen am Heizkreis – nicht sein Symbol.

    Mit dem Symbol des Anlagenteils trugen beide einen Heizkörper; im Reiter
    Zeitprogramme standen drei gleiche Bilder untereinander.
    """
    kreis = teil(
        "UMLZ HEIZKREIS",
        14,
        [
            entitaet("sensor.heizprogramm", "Heizprogramm 1"),
            entitaet("sensor.ww_programm", "WW-Programm"),
            entitaet("sensor.zirkulationsprogramm", "WW-Zirkulationsprogramm"),
        ],
    )
    kreis["symbol"] = "mdi:radiator"
    symbole = {p["titel"]: p["symbol"] for p in panel._anlage_daten(anlage(kreis))["zeitprogramme"]}
    assert symbole["WW-Zirkulationsprogramm"] == "mdi:reload"
    assert symbole["WW-Programm"] == "mdi:water-boiler"
    assert symbole["Heizprogramm 1"] == "mdi:radiator"


# ---------------------------------------------------------------------------
# Kennwert einer fremden Baureihe
# ---------------------------------------------------------------------------
def test_ein_unbekanntes_anlagenteil_bekommt_seinen_leitwert(panel):
    """Der Hersteller sagt selbst, was auf die Übersicht gehört.

    Für Baureihen ohne Namensmuster in `muster.py` bliebe die Zeile sonst leer.
    Die Übersichtsebene der Geräte-Datenbank ist der Rückfall: Was dort für
    diesen Funktionstyp steht, ist die Antwort des Herstellers auf dieselbe
    Frage.
    """
    daten = panel._anlage_daten(
        anlage(
            teil(
                "Fremdkessel",
                9,
                [
                    entitaet("sensor.irgendwas", "Ein Wert ohne Muster", adresse="12/38"),
                    # `2/59` steht in der Übersichtsebene des Funktionstyps 9.
                    entitaet("sensor.leitwert", "Kesselleistung Ist", adresse="2/59", wert=42.0),
                ],
            )
        )
    )
    kennwerte = [k for k in daten["kennwerte"] if k["titel"] == "Fremdkessel"]
    assert [k["entity"] for k in kennwerte] == ["sensor.leitwert"]


def test_das_namensmuster_geht_der_uebersichtsebene_vor(panel):
    """Es ist an einer echten Anlage entstanden, die Ebene nur abgeleitet."""
    daten = panel._anlage_daten(
        anlage(
            teil(
                "PuroWIN",
                25,
                [
                    entitaet("sensor.leistung", "Kesselleistung Ist", adresse="2/59"),
                    entitaet("sensor.kessel", "Kesseltemperatur Ist", adresse="0/7"),
                ],
            )
        )
    )
    assert [k["entity"] for k in daten["kennwerte"]] == ["sensor.kessel"]


def test_der_leitwert_nimmt_lieber_einen_gefuellten_wert(panel):
    """Beim ersten Aufbau ist erst ein Teil der Anlage gelesen.

    Steht der leere Eintrag in der Herstellerliste vorn, zeigte die Zeile
    nichts, obwohl daneben schon ein Wert derselben Liste bereitstand.
    """
    daten = panel._anlage_daten(
        anlage(
            teil(
                "Fremdkessel",
                9,
                [
                    # `2/1` steht in der Übersichtsebene vor `0/7`.
                    entitaet("sensor.leer", "Betriebsphase", adresse="2/1", hat_wert=False),
                    entitaet("sensor.warm", "Kesseltemperatur", adresse="0/7", wert=64.0),
                ],
            )
        )
    )
    assert [k["entity"] for k in daten["kennwerte"]] == ["sensor.warm"]


def test_ohne_uebersichtsebene_bleibt_es_beim_bisherigen(panel):
    """Ein unbekannter Funktionstyp ohne Beleg erfindet nichts."""
    daten = panel._anlage_daten(
        anlage(teil("Unbekannt", 99, [entitaet("sensor.x", "Irgendwas", adresse="99/99")]))
    )
    assert daten["kennwerte"] == []


# ---------------------------------------------------------------------------
# Hilfe-Reiter
# ---------------------------------------------------------------------------
def test_hilfe_liste_zeigt_nur_was_die_anlage_fuehrt(panel):
    """Ein Reiter, der nicht verbaute Technik erklärt, schickt in die Irre."""
    daten = panel._anlage_daten(
        anlage(teil("PuroWIN", 25, [entitaet("button.serviceausbrand", "Serviceausbrand")]))
    )
    titel = [e["titel"] for e in daten["hilfe_liste"]]
    assert "Serviceausbrand" in titel
    # „Lagerraum befüllen" hat einen Kartentext, aber diese Anlage baut die
    # Karte nicht.
    assert "Lagerraum befüllen" not in titel


def test_hilfe_liste_ist_sortiert_und_ohne_dubletten(panel, kessel_und_heizkreis):
    daten = panel._anlage_daten(kessel_und_heizkreis)
    titel = [e["titel"] for e in daten["hilfe_liste"]]
    assert titel == sorted(titel)
    assert len(titel) == len(set(titel))
    assert all(set(e) == {"titel", "text"} for e in daten["hilfe_liste"])


def test_hilfe_liste_bleibt_leer_statt_zu_scheitern(panel):
    """Eine Anlage ohne passende Datenpunkte ist kein Fehlerfall."""
    daten = panel._anlage_daten(anlage(teil("Unbekannt", 99, [])))
    assert isinstance(daten["hilfe_liste"], list)


def test_die_karte_traegt_ihre_fassung_im_pfad():
    """Der Editor wird relativ nachgeladen und braucht denselben Ordner.

    Stünde die Fassung als Anhang, bliebe die Nachbardatei im Zwischenspeicher.
    """
    from custom_components.heatnexus.const import KARTE_VERZEICHNIS, karte_js_pfad

    alt = karte_js_pfad("1.9.0")
    neu = karte_js_pfad("1.10.0")
    assert alt != neu
    assert "?" not in neu
    assert neu.startswith(f"{KARTE_VERZEICHNIS}-1-10-0/")
