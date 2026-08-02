"""Anlagenschaubild: Aufbau der Grafik und Lage der Beschriftungen."""

from __future__ import annotations

import base64

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def schema():
    """Das Modul kommt ohne Home Assistant aus und wird direkt geladen."""
    return load_standalone("schema")


def _teil(name: str, fct: int, werte: list[tuple[str, str]]) -> dict:
    return {
        "name": name,
        "fct_type": fct,
        "entitaeten": [
            {
                "entity_id": eid,
                "name": n,
                "hat_wert": True,
                "bereich": eid.split(".")[0],
            }
            for eid, n in werte
        ],
    }


@pytest.fixture
def anlage():
    return [
        _teil(
            "PuroWIN",
            25,
            [("sensor.kessel_ist", "Kesseltemperatur Ist"), ("sensor.leistung", "Kesselleistung")],
        ),
        _teil(
            "B-PLMi PUFFER",
            16,
            [
                ("sensor.tpe", "Puffer oben Temperatur (TPE)"),
                ("sensor.tpa", "Puffer unten Temperatur (TPA)"),
            ],
        ),
    ]


def test_karte_ist_ein_bild_mit_beschriftungen(schema, anlage):
    karte = schema.anlagenschema(anlage)
    assert karte["type"] == "picture-elements"
    assert karte["image"].startswith("data:image/svg+xml;base64,")
    # Je Anlagenteil zwei Werte.
    assert len(karte["elements"]) == 4
    assert {e["entity"] for e in karte["elements"]} == {
        "sensor.kessel_ist",
        "sensor.leistung",
        "sensor.tpe",
        "sensor.tpa",
    }


def test_bild_enthaelt_die_namen(schema, anlage):
    karte = schema.anlagenschema(anlage)
    svg = base64.b64decode(karte["image"].split(",", 1)[1]).decode("utf-8")
    assert svg.startswith("<svg")
    assert "PuroWIN" in svg
    assert "B-PLMi PUFFER" in svg
    assert "</svg>" in svg


def test_beschriftungen_liegen_im_bild(schema, anlage):
    for element in schema.anlagenschema(anlage)["elements"]:
        for achse in ("top", "left"):
            anteil = float(element["style"][achse].rstrip("%"))
            assert 0 < anteil < 100


def test_ohne_messwerte_kein_schaubild(schema):
    assert schema.anlagenschema([]) is None
    ohne = [_teil("ZSP-PTS", 20, [("sensor.x", "Pumpendrehzahl")])]
    assert schema.anlagenschema(ohne) is None


def test_spitze_klammern_im_namen_zerlegen_das_bild_nicht(schema):
    teil = _teil("Kessel <b>", 25, [("sensor.k", "Kesseltemperatur Ist")])
    svg = base64.b64decode(schema.anlagenschema([teil])["image"].split(",", 1)[1]).decode("utf-8")
    assert "<b>" not in svg
    assert "&lt;b&gt;" in svg


def test_schaubild_entsteht_auch_ohne_werte(schema, anlage):
    """Beim ersten Aufbau ist die Anlage noch nicht eingelesen.

    Verlangte das Schaubild einen vorhandenen Wert, bliebe der Reiter „Anlage"
    dauerhaft leer – der Fehler aus 1.0.0.
    """
    for teil in anlage:
        for eintrag in teil["entitaeten"]:
            eintrag["hat_wert"] = False

    bild = schema.anlagenschema(anlage)
    assert bild is not None
    assert len(bild["elements"]) == 4


def test_anlagenteil_ohne_passenden_messwert_faellt_weg(schema):
    """Ein leerer Kasten hilft niemandem."""
    ohne = [{"name": "Rätsel", "fct_type": 99, "entitaeten": []}]
    assert schema.anlagenschema(ohne) is None


# ---------------------------------------------------------------------------
# Warmwasser als eigener Anlagenteil
#
# In 1.1.0-beta.6/7 fehlte der Warmwasserbehälter im Schaubild, obwohl die
# Anlage ihn liefert. Grund war ein Steuerzeichen im Suchmuster: Beim Erzeugen
# der Datei war aus der Wortgrenze `\b` ein echtes Backspace-Zeichen geworden.
# Im Quelltext war das nicht zu sehen – nur im Verhalten.
# ---------------------------------------------------------------------------
def test_muster_enthalten_keine_steuerzeichen(schema):
    """Ein Suchmuster darf nie ein Steuerzeichen enthalten."""
    muster = [schema.WARMWASSER_IST]
    muster += [m for eintraege in schema.WERTE_JE_ART.values() for m, _ in eintraege]
    muster += list(schema.PUMPE_JE_ART.values())
    for einzeln in muster:
        assert not any(ord(z) < 32 for z in einzeln), f"Steuerzeichen in {einzeln!r}"


def test_warmwasser_wird_eigener_anlagenteil(schema):
    heizkreis = _teil(
        "UMLZ HEIZKREIS",
        14,
        [
            ("sensor.vorlauf", "Vorlauftemperatur Ist"),
            ("sensor.raum", "Raumtemperatur Ist"),
            ("sensor.ww_ist", "Warmwasser Ist-Temperatur"),
            ("sensor.ww_soll", "Warmwasser Soll-Temperatur"),
            ("binary_sensor.ww_ladepumpe", "WW-Ladepumpe"),
        ],
    )
    arten = [m["art"] for m in schema._module([heizkreis])]
    assert "wasser" in arten, "Warmwasser fehlt im Schaubild"


def test_ohne_warmwasser_kein_eigener_anlagenteil(schema):
    heizkreis = _teil(
        "Hebebuehne",
        14,
        [("sensor.vorlauf", "Vorlauftemperatur Ist"), ("sensor.raum", "Raumtemperatur Ist")],
    )
    arten = [m["art"] for m in schema._module([heizkreis])]
    assert "wasser" not in arten


def test_pumpe_je_anlagenteil(schema):
    heizkreis = _teil(
        "UMLZ HEIZKREIS",
        14,
        [
            ("sensor.raum", "Raumtemperatur Ist"),
            ("sensor.vorlauf", "Vorlauftemperatur Ist"),
            ("binary_sensor.hkp", "Heizkreispumpe"),
        ],
    )
    module = schema._module([heizkreis])
    assert module[0]["pumpe"] == "binary_sensor.hkp"
