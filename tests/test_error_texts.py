"""Dekodierung der Geräte-Meldungen (FE01msg)."""

from __future__ import annotations

import pytest


def test_ok_message_has_no_faults(error_texts):
    assert error_texts.parse_messages("PUR 09  OK") == []


def test_single_fault_is_decoded(error_texts):
    msgs = error_texts.parse_messages("PUR 09E346")
    assert len(msgs) == 1
    assert msgs[0]["code"] == 346
    assert msgs[0]["kind"] == "Fehler"
    assert msgs[0]["text"]


def test_multiple_faults_are_collected(error_texts):
    msgs = error_texts.parse_messages("PUR 09E346  PUR 09E322")
    assert [m["code"] for m in msgs] == [346, 322]


def test_duplicate_codes_appear_once(error_texts):
    msgs = error_texts.parse_messages("PUR 09E346  PCM 00E346")
    assert [m["code"] for m in msgs] == [346]


@pytest.mark.parametrize(
    ("letter", "kind"),
    [("E", "Fehler"), ("A", "Alarm"), ("I", "Info")],
)
def test_message_kinds(error_texts, letter, kind):
    msgs = error_texts.parse_messages(f"PUR 09{letter}322")
    assert msgs[0]["kind"] == kind


def test_unknown_code_falls_back(error_texts):
    msgs = error_texts.parse_messages("PUR 09E9999")
    assert msgs == [] or msgs[0]["text"]


def test_none_input(error_texts):
    assert error_texts.parse_messages(None) == []


def test_zusatztabelle_schlaegt_die_mitgelieferte(error_texts):
    """Die Steuerung benennt ihre Störungen selbst und in ihrer Sprache."""
    meldungen = error_texts.parse_messages("XXX 01E346", zusatz={346: "Casing door open"})

    assert meldungen[0]["text"] == "Casing door open"


def test_zusatztabelle_aus_dem_erkennungsstand_hat_textschluessel(error_texts):
    """Nach dem Ablegen als JSON sind die Schlüssel Text, nicht Zahl."""
    meldungen = error_texts.parse_messages("XXX 01E346", zusatz={"346": "Casing door open"})

    assert meldungen[0]["text"] == "Casing door open"


def test_zusatztabelle_ohne_treffer_aendert_nichts(error_texts):
    ohne = error_texts.parse_messages("XXX 01E346")
    mit = error_texts.parse_messages("XXX 01E346", zusatz={999: "irgendwas"})

    assert ohne == mit
