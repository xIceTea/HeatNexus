"""Bedientasten an jeder bekannten Baureihe.

Die Anlagen sind aus Abzügen nachgebildet: welcher Funktionstyp welche Adresse
führt, wie HeatNexus sie benennt und welche Werte `9/75` am Gerät anbietet.
Geprüft wird, dass jede Taste ihren Zustand aus dem Teil ihres Auslösers liest.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


def _e(entity_id, name, adresse=None, schluessel=None, optionen=None):
    return {
        "entity_id": entity_id,
        "name": name,
        "kategorie": None,
        "bereich": entity_id.split(".")[0],
        "hat_wert": True,
        "wert": None,
        "state_class": None,
        "adresse": adresse,
        "schluessel": schluessel,
        "optionen": optionen or {},
    }


def _teil(name, fct_type, entitaeten):
    return {
        "name": name,
        "id": f"geraet_{name}",
        "anlage_id": "steuerung",
        "fct_type": fct_type,
        "rang": 0,
        "symbol": "mdi:fire",
        "entitaeten": entitaeten,
    }


BETRIEBSART = {
    3: "WW-Ladung",
    4: "Eco / Comfort",
    17: "Warmwasser Hygiene-Programm",
    18: "Warmwasser Einmalladung",
}
NEIN_JA = {0: "Nein", 1: "Ja"}


def _ww_heizkreis(p):
    """Heizkreis fctType 14 mit Warmwasser, wie UML und BioWIN ihn melden."""
    return _teil(
        f"{p} Heizkreis",
        14,
        [
            _e(f"sensor.{p}_betriebsart", "Betriebsart", "2/9", "operating_mode", BETRIEBSART),
            _e(f"switch.{p}_ww_einmalladung", "WW Einmalladung", "2/16"),
            _e(f"number.{p}_ww_ladetemperatur", "WW Einmalladung Temperatur", "5/51"),
            _e(f"binary_sensor.{p}_ww_ladepumpe", "WW-Ladepumpe", "1/66", "dhw_charge_pump"),
            _e(f"sensor.{p}_ww_ist", "Warmwasser Ist-Temperatur", "0/4", "dhw_temperature"),
            _e(
                f"select.{p}_betriebswahl",
                "Betriebswahl",
                "3/50",
                "mode_selection",
                {0: "Standby", 1: "Programm 1", 6: "WW-Betrieb"},
            ),
        ],
    )


def _puffer(p):
    """Puffer fctType 16 mit eigener Betriebsart; sie darf die Taste nie speisen."""
    return _teil(
        f"{p} Puffer",
        16,
        [_e(f"sensor.{p}_puffer_betriebsart", "Betriebsart", "2/9", "operating_mode", BETRIEBSART)],
    )


def _kessel(p, fct_type):
    """Kessel mit „Betriebsart" `2/59`: gleicher Name, anderer Datenpunkt."""
    return _teil(
        f"{p} Kessel", fct_type, [_e(f"sensor.{p}_kessel_betriebsart", "Betriebsart", "2/59")]
    )


BAUREIHEN = {
    "purowin": [_kessel("pw", 25), _puffer("pw"), _ww_heizkreis("pw")],
    "uml": [_puffer("uml"), _ww_heizkreis("uml")],
    "biowin": [_kessel("bw", 9), _puffer("bw"), _ww_heizkreis("bw")],
    # DuoWIN: Warmwasser als eigene Funktion fctType 2 ohne Betriebsart; `2/16`
    # ist dort eine Auswahl Nein/Ja, `58/113` startet das Hygiene-Programm.
    "duowin": [
        _kessel("dwb", 9),
        _kessel("dwl", 10),
        _teil(
            "Combiboiler",
            2,
            [
                _e("select.dw_freigabe_2_16", "Freigabe starten (2/16)", "2/16", optionen=NEIN_JA),
                _e(
                    "select.dw_freigabe_58_113",
                    "Freigabe starten (58/113)",
                    "58/113",
                    optionen=NEIN_JA,
                ),
                _e("number.dw_temperatur", "Temperatur", "5/51"),
                _e("binary_sensor.dw_ladepumpe", "WW-Ladepumpe (1/66)", "1/66", "dhw_charge_pump"),
                _e("sensor.dw_ww_ist", "WW-Temperatur Aktueller Wert", "0/4", "dhw_temperature"),
            ],
        ),
    ],
}

# `9/75` am Gerät, je Baureihe und Funktionstyp, aus den Abzügen.
BETRIEBSWAHL_KESSEL = {
    ("purowin", 25): {0, 1, 2, 3, 4, 5, 6, 7},
    ("biowin", 9): {0, 1, 2, 3, 4, 5, 8},
    ("duowin", 9): {0, 1, 3, 4, 5, 8},
    ("duowin", 10): {0, 1, 3, 4, 8},
}


@pytest.fixture(scope="module")
def daten():
    from custom_components.heatnexus.panel.daten import _anlage_daten

    return {name: _anlage_daten({"name": name, "teile": t}) for name, t in BAUREIHEN.items()}


@pytest.mark.parametrize("baureihe", sorted(BAUREIHEN))
def test_warmwasser_taste_liest_den_teil_ihres_ausloesers(daten, baureihe):
    teil = next(t for t in BAUREIHEN[baureihe] if t["fct_type"] in (2, 14))
    eigene = {e["entity_id"]: e for e in teil["entitaeten"]}
    schnell = [z for z in daten[baureihe]["schnellzugriff"] if z["titel"] == "Warmwasser laden"]
    assert len(schnell) == 1, schnell
    for taste in (daten[baureihe]["steuerung"]["warmwasser"]["taste"], schnell[0]):
        assert eigene[taste["entity"]]["adresse"] == "2/16"
        for quelle in ("zustand_an", "zustand_pumpe", "betriebswahl", "ist", "soll"):
            wert = taste.get(quelle)
            assert wert is None or wert in eigene, (quelle, wert)


def test_eine_auswahl_nein_ja_wird_zur_taste(daten):
    ww = daten["duowin"]["steuerung"]["warmwasser"]
    assert ww["taste"]["entity"] == "select.dw_freigabe_2_16"
    assert (ww["taste"]["ein_option"], ww["taste"]["aus_option"]) == ("Ja", "Nein")
    assert ww["laden_temperatur"] == "number.dw_temperatur"


def test_eingriffe_auf_der_kesselbetriebswahl_passen_zu_jedem_geraet():
    """Jeder Wert, den ein Schalter oder eine Taste auf `9/75` schreibt, muss die Baureihe anbieten."""
    from custom_components.heatnexus import device_db, geraete

    texte = device_db.get_enum("9/75")
    geprueft = 0
    for modul in geraete.MODULE:
        for d in modul.ENTITAETEN:
            if d.get("oid") != "/9/75/0" or d.get("platform") not in ("switch", "button"):
                continue
            if d["platform"] == "button":
                werte = [d["press_value"]]
            else:
                werte = [d.get("ein_wert") or "1", d.get("aus_wert") or "0"]
            for (baureihe, fct_type), angeboten in BETRIEBSWAHL_KESSEL.items():
                if fct_type == modul.FCT_TYPE:
                    geprueft += 1
                    assert {int(w) for w in werte} <= angeboten, (baureihe, d["name"], werte)
            # Name und Herstellertext des geschriebenen Werts meinen dasselbe.
            wort = texte[int(werte[0])].lower().split()[0][:8]
            assert wort in d["name"].lower() or d.get("key_suffix") == "ein_aus", (d["name"], wort)
    assert geprueft, "kein Eingriff auf 9/75 geprüft"
