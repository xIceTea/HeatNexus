"""Geräte-Datenbank: Namen, Enums und Ebenen-Listen je Funktionstyp."""

from __future__ import annotations

import pytest

# Funktionstypen, die mindestens abgedeckt sein müssen
FCT_HEIZKREIS = 14
FCT_PUFFER = 16
FCT_PUROWIN = 25
FCT_BIOWIN = 9


def test_names_resolve(device_db):
    assert device_db.get_name("0/0") == "Aussentemperatur"


def test_unknown_name_is_none(device_db):
    assert device_db.get_name("999/999") is None


def test_enum_keys_are_ints(device_db):
    enum = device_db.get_enum("3/50")
    assert enum
    assert all(isinstance(k, int) for k in enum)


@pytest.mark.parametrize("fct", [FCT_HEIZKREIS, FCT_PUFFER, FCT_PUROWIN, FCT_BIOWIN])
def test_layers_present(device_db, fct):
    layers = device_db.get_layers(fct)
    assert layers, f"Funktionstyp {fct} fehlt in der Geräte-DB"
    assert layers.get("info"), f"Funktionstyp {fct} ohne Infoebene"


def test_layer_entries_are_gn_mn(device_db):
    for gnmn in device_db.get_layers(FCT_PUROWIN)["operate"]:
        gn, _, mn = gnmn.partition("/")
        assert gn.isdigit() and mn.isdigit(), gnmn
