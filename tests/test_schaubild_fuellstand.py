"""Werte und Füllstand im Schaubild: feste Stellen an der Wärmepumpe, Behälter und Lagerraum."""

from __future__ import annotations

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def schema():
    return load_standalone("schema")


def _teil(name: str, fct: int, werte: list[tuple[str, str, str | None]], **optionen) -> dict:
    return {
        "name": name,
        "fct_type": fct,
        "entitaeten": [
            {
                "entity_id": eid,
                "name": n,
                "hat_wert": True,
                "bereich": eid.split(".")[0],
                "adresse": adresse,
                "optionen": optionen.get(eid, {}),
            }
            for eid, n, adresse in werte
        ],
    }


BEHAELTER = {0: "Fehler Vorratsbehälter ", 1: "Vorratsbehälter leer", 3: "Vorratsbehälter voll"}


def _purowin(brennstoff: str = "Pellets") -> dict:
    teil = _teil(
        "PuroWIN",
        25,
        [
            ("sensor.kessel", "Kesseltemperatur Ist", "0/7"),
            ("sensor.brennstoff", "Aktueller Brennstoff", "38/127"),
            ("sensor.behaelter", "Vorratsbehälter Status", "39/76"),
        ],
        **{"sensor.behaelter": BEHAELTER, "sensor.brennstoff": {0: "Hackgut normal", 2: "Pellets"}},
    )
    teil["entitaeten"][1]["text"] = brennstoff
    return teil


def test_die_waermepumpe_traegt_ihre_werte_an_festen_stellen(schema):
    modul = {
        "art": "kessel",
        "kesselart": "waermepumpe",
        "werte": [
            {"entity_id": "sensor.vl", "beschriftung": "Vorlauf"},
            {"entity_id": "sensor.cop", "beschriftung": "COP"},
        ],
    }
    vorlauf, cop = schema.zeichnung.beschriftungen(0, modul, 400)
    assert (vorlauf["style"]["left"], vorlauf["style"]["top"]) == ("25.0%", "35.7%")
    assert (cop["style"]["left"], cop["style"]["top"]) == ("29.5%", "67.9%")
    assert [vorlauf["name"], cop["name"]] == ["Vorlauf", "COP"]


def test_die_waermepumpe_hat_kein_glutbett(schema):
    """Sie zeigt den Betrieb über Lüfter und Lampe; eine Glut läge über der Lampe."""
    rahmen = schema.ebenen.Rahmen(400, (), ())
    module = [
        {"art": "kessel", "kesselart": art, "leistung": f"sensor.{art}", "titel": art}
        for art in ("waermepumpe", "pellets")
    ]
    assert [e["entity"] for e in schema.ebenen.brenner(module, rahmen)] == ["sensor.pellets"]


@pytest.mark.parametrize("kesselart", ["pellets", "hackgut"])
def test_die_kessel_mit_behaelter_markieren_seine_innenflaeche(schema, kesselart):
    assert schema.bauteile.vorratsflaeche(kesselart) is not None


@pytest.mark.parametrize(("kesselart", "farbe"), [("pellets", "#c9a26b"), ("hackgut", "#a87c4f")])
def test_ohne_gemeldeten_fuellstand_zeigt_die_zeichnung_den_brennstoff_in_holzfarbe(
    schema, kesselart, farbe
):
    """Der BioWIN meldet keinen Behälter; die Körner stehen trotzdem bis zur festen Höhe."""
    zeichnung = schema.bauteile.aus_datei("kessel", kesselart, "t0-")
    assert '<g opacity="1" clip-path="url(#t0-fest)">' in zeichnung
    assert farbe in zeichnung


def test_ohne_behaelter_in_der_zeichnung_keine_flaeche(schema):
    assert schema.bauteile.vorratsflaeche("waermepumpe") is None


@pytest.mark.parametrize(
    ("brennstoff", "kesselart", "farbe"),
    [("Pellets", "pellets", "#c9a26b"), ("Hackgut normal", "hackgut", "#a87c4f")],
)
def test_der_purowin_fuellt_seinen_behaelter_in_stufen(schema, brennstoff, kesselart, farbe):
    [modul] = schema.werte.zeichenbare_module([_purowin(brennstoff)])
    assert modul["kesselart"] == kesselart
    bild = schema.karte.anlagenschema([_purowin(brennstoff)])
    [behaelter] = [e for e in bild["vorrat"] if e["art"] == "behaelter"]
    assert behaelter["entity"] == "sensor.behaelter"
    # Die Füllung trägt dieselbe Körnung wie die Zeichnung, samt Umriss für den Fehler.
    assert 'class="koerner-flaeche"' in behaelter["bild"]
    assert farbe in behaelter["bild"]
    assert 'class="umriss-linie"' in behaelter["bild"]
    assert behaelter["stufen"] == {
        "Fehler Vorratsbehälter ": "fehler",
        "Vorratsbehälter leer": "leer",
        "Vorratsbehälter voll": "voll",
    }
    # Der gezeichnete Brennstoff weicht der gemeldeten Füllung.
    assert '<g opacity="0" ' in bild["svg"]


def test_ohne_gemeldeten_fuellstand_bleibt_die_zeichnung(schema):
    teil = _teil("PuroWIN", 25, [("sensor.kessel", "Kesseltemperatur Ist", "0/7")])
    bild = schema.karte.anlagenschema([teil])
    assert bild["vorrat"] == []
    assert '<g opacity="0" ' not in bild["svg"]


def test_der_biowin_zeigt_den_lagerraum_und_fuellt_den_behaelter_nicht(schema):
    teil = _teil(
        "BioWIN",
        9,
        [
            ("sensor.kessel", "Kesseltemperatur Ist", "0/7"),
            ("sensor.behaelter", "Vorratsbehälter Status", "39/76"),
            ("sensor.vorratsbehaelter", "Befüllgrad Vorratsbehälter", "43/42"),
            ("sensor.lager", "Befüllgrad Lagerraum", "43/78"),
        ],
    )
    vorrat = schema.karte.anlagenschema([teil])["vorrat"]
    assert [(e["art"], e["entity"]) for e in vorrat] == [("lagerraum", "sensor.lager")]
