"""Kanonische Schlüssel: die Adresse statt des deutschen Namens.

Der Grund für dieses Modul steht in seinem Kopf: Solange Schaubild, Dashboard
und Oberfläche einen Datenpunkt an seinem deutschen Namen erkennen, kann keine
zweite Sprache eingeschaltet werden – mit englischen Namen liefe kein Muster
mehr an, und die Karten blieben still leer.

Geprüft wird deshalb vor allem das, was still schiefgehen würde: eine falsch
zerlegte Kennung, ein geratener Schlüssel, eine Adresse, die es in der
Geräte-Datenbank gar nicht gibt.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import load_standalone

DB = Path(__file__).parent.parent / "custom_components" / "heatnexus" / "device_db.json"


@pytest.fixture(scope="module")
def kanonisch():
    """Das Modul kommt ohne Home Assistant aus."""
    return load_standalone("kanonisch")


# ---------------------------------------------------------------------------
# Adresse aus der Kennung
# ---------------------------------------------------------------------------
def test_die_adresse_kommt_aus_der_kennung(kanonisch):
    """`<neuronId>-<fctId>-<gn>-<mn>-<idx>` – gesucht sind gn und mn."""
    assert kanonisch.gnmn("0000ABCD1234-0-0-7-0") == "0/7"
    assert kanonisch.gnmn("0000ABCD1234-0-21-65-0") == "21/65"


def test_ein_namenszusatz_stoert_die_zerlegung_nicht(kanonisch):
    """Zwei Entitäten auf derselben Adresse tragen hinten einen Zusatz."""
    assert kanonisch.gnmn("0000ABCD1234-0-2-1-0-text") == "2/1"


def test_eine_seriennummer_mit_ziffern_verschiebt_nichts(kanonisch):
    """Gezählt wird von hinten, nicht von vorn – sonst zerfiele sie mit."""
    assert kanonisch.gnmn("12345678-0-0-7-0") == "0/7"


def test_die_alte_adressgebundene_kennung_liefert_auch_eine_adresse(kanonisch):
    """`192-168-178-100-1-60-0-0-7-0` – die letzten vier zählen, nicht die IP."""
    assert kanonisch.gnmn("192-168-178-100-1-60-0-0-7-0") == "0/7"


@pytest.mark.parametrize("kaputt", [None, "", "ohne-zahlen", "0000ABCD1234-7-0"])
def test_eine_unbrauchbare_kennung_ergibt_keine_adresse(kanonisch, kaputt):
    """Kein Schlüssel ist besser als ein geratener – dann greift das Muster."""
    assert kanonisch.gnmn(kaputt) is None


@pytest.mark.parametrize(
    "kennung",
    [
        "10-0-1-20-0-thermostat",
        "192-168-1-20-fe01",
        "192-168-1-4-fe01text",
    ],
)
def test_ohne_seriennummer_wird_nicht_geraten(kanonisch, kennung):
    """Meldet ein Knoten keine `neuronId`, steht die Adresse in der Kennung.

    Dann beginnt sie selbst mit Zahlen, und zusammen mit einem Wortzusatz
    hinten verschiebt sich der Zahlenlauf: `10-0-1-20-0-thermostat` ergäbe
    sonst `1/20` und damit „Heizkreispumpe" für ein Thermostat. Solche
    Kennungen bleiben ohne Adresse – das Muster greift weiter.
    """
    assert kanonisch.gnmn(kennung) is None
    assert kanonisch.schluessel(kennung) is None


def test_die_alte_kennung_ohne_zusatz_bleibt_lesbar(kanonisch):
    """Sie beginnt zwar auch mit Zahlen, hat aber keinen Zusatz – sie trägt."""
    assert kanonisch.gnmn("192-168-178-100-1-60-0-0-7-0") == "0/7"


# ---------------------------------------------------------------------------
# Schlüssel
# ---------------------------------------------------------------------------
def test_bekannte_datenpunkte_bekommen_ihren_schluessel(kanonisch):
    assert kanonisch.schluessel("0000ABCD1234-0-0-7-0") == "boiler_temperature"
    assert kanonisch.schluessel("0000ABCD1234-0-3-50-0") == "mode_selection"
    assert kanonisch.schluessel("0000ABCD1234-0-0-0-0") == "outdoor_temperature"


def test_auch_die_nachgereichten_datenpunkte_tragen_ihren_schluessel(kanonisch):
    """Die Adressen, die die Muster der Oberfläche brauchen."""
    assert kanonisch.schluessel("0000ABCD1234-0-0-8-0") == "return_temperature"
    assert kanonisch.schluessel("0000ABCD1234-0-0-95-0") == "analog_setpoint"
    assert kanonisch.schluessel("0000ABCD1234-0-1-21-0") == "mixer_position"
    assert kanonisch.schluessel("0000ABCD1234-0-39-76-0") == "fuel_storage_status"


def test_ein_datenpunkt_ohne_entsprechung_bleibt_ohne_schluessel(kanonisch):
    """Er behält den Herstellernamen; deshalb verschwinden die Muster nicht."""
    assert kanonisch.schluessel("0000ABCD1234-0-9-31-0") is None


def test_ein_schluessel_gilt_nur_dort_mehrfach_wo_es_begruendet_ist(kanonisch):
    """Sonst suchte die Oberfläche einen Begriff und fände zwei Datenpunkte.

    Zwei Adressen dürfen denselben Schlüssel tragen, wenn zwei Baureihen
    denselben Messwert an verschiedenen Stellen führen – der Puffer etwa. Wer
    einen weiteren Schlüssel doppelt vergibt, muss ihn hier eintragen und
    begründen; genau das soll auffallen.
    """
    mehrfach = {"buffer_top", "buffer_bottom"}
    werte = [w for w in kanonisch.KANONISCH.values() if w not in mehrfach]
    doppelt = sorted({w for w in werte if werte.count(w) > 1})
    assert doppelt == [], f"doppelt vergeben: {doppelt}"


def test_jede_adresse_steht_auch_in_der_geraete_datenbank(kanonisch):
    """Belegt statt abgeschrieben: Eine erfundene Adresse fiele hier auf."""
    namen = json.loads(DB.read_text(encoding="utf-8"))["names"]
    fehlend = [adresse for adresse in kanonisch.KANONISCH if adresse not in namen]
    assert fehlend == [], f"nicht in device_db.json: {fehlend}"


def test_die_schluessel_sind_englisch_und_kleingeschrieben(kanonisch):
    """Sie sind der herstellerübergreifende Name, nicht der deutsche."""
    for schluessel in kanonisch.KANONISCH.values():
        assert schluessel == schluessel.lower()
        assert " " not in schluessel
