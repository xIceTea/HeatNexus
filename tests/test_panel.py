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
            "Hebebühne",
            14,
            [
                entitaet("climate.hebebuehne", "Hebebühne"),
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
            "Hebebühne",
            14,
            [
                entitaet("climate.hebebuehne", "Hebebühne"),
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
    ohne = anlage(teil("Hebebühne", 14, [entitaet("climate.hebebuehne", "Hebebühne")]))
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


def test_je_anlagenteil_nur_ein_kennwert(panel, kessel_und_heizkreis):
    """Die linke Spalte zeigt je Anlagenteil den wichtigsten Wert, nicht alle."""
    daten = panel._anlage_daten(kessel_und_heizkreis)
    assert len(daten["kennwerte"]) == len(kessel_und_heizkreis["teile"])
    assert daten["kennwerte"][0]["entity"] == "sensor.kesseltemperatur_ist"


def test_leere_anlage_ergibt_leere_aufteilung(panel):
    daten = panel._anlage_daten(anlage())
    assert daten["kennwerte"] == []
    assert daten["heizkreise"] == []
    assert daten["schema"] is None
