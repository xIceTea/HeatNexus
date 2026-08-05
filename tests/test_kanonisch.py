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


# ---------------------------------------------------------------------------
# Schlüssel
# ---------------------------------------------------------------------------
def test_bekannte_datenpunkte_bekommen_ihren_schluessel(kanonisch):
    assert kanonisch.schluessel("0000ABCD1234-0-0-7-0") == "boiler_temperature"
    assert kanonisch.schluessel("0000ABCD1234-0-3-50-0") == "mode_selection"
    assert kanonisch.schluessel("0000ABCD1234-0-0-0-0") == "outdoor_temperature"


def test_ein_datenpunkt_ohne_entsprechung_bleibt_ohne_schluessel(kanonisch):
    """Er behält den Herstellernamen; deshalb verschwinden die Muster nicht."""
    assert kanonisch.schluessel("0000ABCD1234-0-9-31-0") is None


def test_kein_schluessel_wird_zweimal_vergeben(kanonisch):
    """Sonst suchte die Oberfläche einen Namen und fände zwei Datenpunkte."""
    werte = list(kanonisch.KANONISCH.values())
    assert len(werte) == len(set(werte))


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
