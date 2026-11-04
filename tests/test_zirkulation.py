"""Die Zirkulationspumpe, die nach ihren Schaltzeiten nie läuft."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

DATEI = Path(__file__).parents[1] / "custom_components" / "heatnexus" / "zirkulation.py"
PROGRAMM = "/1/15/0/5/65/0"
MODUS = "/1/15/0/5/6/0"


@pytest.fixture(scope="module")
def zirkulation():
    spec = importlib.util.spec_from_file_location("zirkulation", DATEI)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def daten(modus, *werte):
    bloecke = [
        {
            "weekdays": ["Mo"],
            "switchPoints": [{"time": f"{i:02d}:00", "value": w} for i, w in enumerate(werte)],
        }
    ]
    return {"oids": {MODUS: modus}, "objects": {PROGRAMM: bloecke}}


@pytest.mark.parametrize("modus", ["1", "3"])
def test_nur_aus_laesst_die_pumpe_stehen(zirkulation, modus):
    """Zeit- und Impulssteuerung folgen den Schaltzeiten."""
    assert zirkulation.steht_still(daten(modus, 0, 0, 0)) is True


def test_ein_einziges_ein_genuegt(zirkulation):
    assert zirkulation.steht_still(daten("1", 0, 1)) is False


@pytest.mark.parametrize("modus", ["0", "2"])
def test_andere_steuerungsarten_brauchen_keine_schaltzeiten(zirkulation, modus):
    assert zirkulation.steht_still(daten(modus, 0, 0)) is False


def test_ohne_schaltzeit_gibt_es_keine_aussage_ueber_aus(zirkulation):
    assert zirkulation.steht_still(daten("1")) is False


def test_ohne_modus_oder_programm_bleibt_es_offen(zirkulation):
    assert zirkulation.steht_still({"oids": {}, "objects": {}}) is None
    assert zirkulation.steht_still({"oids": {}, "objects": daten("1", 0)["objects"]}) is None
    assert zirkulation.steht_still(daten("-.-", 0)) is None


def test_zwei_kreise_zaehlen_einzeln(zirkulation):
    """Ein Kreis mit Einschaltpunkt deckt den anderen nicht zu."""
    laeuft = daten("1", 1)
    laeuft["oids"]["/1/15/1/5/6/0"] = "1"
    laeuft["objects"]["/1/15/1/5/65/0"] = daten("1", 0)["objects"][PROGRAMM]
    assert zirkulation.steht_still(laeuft) is True
