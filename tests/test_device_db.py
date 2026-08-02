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


# ---------------------------------------------------------------------------
# Erzeugte Referenz
#
# `docs/DATAPOINTS.md` und `docs/ENUMS.md` werden aus `device_db.json` erzeugt.
# Ohne diesen Test fällt niemandem auf, dass sie nach einem neuen Datenbestand
# veraltet sind – und eine veraltete Referenz ist schlimmer als keine.
# ---------------------------------------------------------------------------
def test_datenpunkt_referenz_ist_aktuell():
    import importlib.util
    import json
    from pathlib import Path

    wurzel = Path(__file__).parent.parent
    pfad = wurzel / "tools" / "build_datenpunkte_doku.py"
    spec = importlib.util.spec_from_file_location("doku", pfad)
    doku = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(doku)

    db = json.loads(doku.DB.read_text(encoding="utf-8"))
    for ziel, erzeugt in (
        (doku.ZIEL_DATENPUNKTE, doku.datenpunkte(db)),
        (doku.ZIEL_ENUMS, doku.enums(db)),
    ):
        assert ziel.exists(), f"{ziel.name} fehlt"
        assert ziel.read_text(encoding="utf-8") == erzeugt, (
            f"{ziel.name} passt nicht zur Geräte-Datenbank. "
            "Abhilfe: python tools/build_datenpunkte_doku.py"
        )


def test_jeder_funktionstyp_hat_einen_namen():
    """Ein Funktionstyp ohne Namen steht als „unbekannt" in der Referenz."""
    import importlib.util
    import json
    from pathlib import Path

    pfad = Path(__file__).parent.parent / "tools" / "build_datenpunkte_doku.py"
    spec = importlib.util.spec_from_file_location("doku", pfad)
    doku = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(doku)

    db = json.loads(doku.DB.read_text(encoding="utf-8"))
    ohne = sorted(set(db["layers"]) - set(doku.FUNKTIONEN), key=int)
    assert not ohne, f"Funktionstypen ohne Namen: {ohne}"
