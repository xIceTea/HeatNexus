"""Regeln der Bedienung je Baureihe: Sichtbarkeit, Bits, Zustandstexte, Nur-Anzeige.

Die Regeln stehen in den Gerätemodulen. Die Tests halten fest, was sie bedeuten,
und dass jede Regel nur Adressen nennt, die das Modul auch führt.
"""

from __future__ import annotations

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def geraete():
    return load_standalone("geraete")


def _erfuellt(geraete, saetze: list[dict], werte: dict[str, str]) -> bool:
    return any(geraete.satz_trifft(werte[s["oid"]], s) for s in saetze)


@pytest.mark.parametrize("fct", [2, 14])
def test_beide_zirkulationsprogramme_bleiben_bei_jeder_betriebsart(geraete, fct):
    """Unter „Zeitprogramme“ aktiviert man die andere Steuerungsart über ihr Programm."""
    regeln = geraete.BEDINGUNGEN.get(fct, {})
    assert "5/64" not in regeln
    assert "5/65" not in regeln


def test_ohne_zirkulation_entfallen_ihre_werte_am_warmwasser(geraete):
    regeln = geraete.BEDINGUNGEN[2]
    for adresse in ("0/118", "1/118", "59/18"):
        assert not _erfuellt(geraete, regeln[adresse], {"5/6": "0"}), adresse


@pytest.mark.parametrize(("art", "heizprogramme"), [("1", True), ("2", True), ("4", False)])
def test_infinity_programme_folgen_der_regelart(geraete, art, heizprogramme):
    regeln = geraete.BEDINGUNGEN[1]
    assert _erfuellt(geraete, regeln["3/61"], {"7/76": art}) is heizprogramme
    assert _erfuellt(geraete, regeln["58/78"], {"7/76": art}) is not heizprogramme


@pytest.mark.parametrize("art", ["0", "3", "5"])
def test_infinity_ohne_belegte_regelart_behaelt_beide_programmsaetze(geraete, art):
    regeln = geraete.BEDINGUNGEN[1]
    assert _erfuellt(geraete, regeln["3/61"], {"7/76": art})
    assert _erfuellt(geraete, regeln["58/78"], {"7/76": art})


def test_jede_bedingung_hat_saetze_mit_werten(geraete):
    for fct, regeln in geraete.BEDINGUNGEN.items():
        for adresse, saetze in regeln.items():
            assert saetze, (fct, adresse)
            assert all(s["oid"] and (s.get("values") or s.get("ausser")) for s in saetze), (
                fct,
                adresse,
            )


@pytest.mark.parametrize(
    ("fct", "bits"),
    [(4, {12, 13}), (15, {1, 2, 3, 6})],
)
def test_aktive_aktoren_werden_einzeln_gezeigt(geraete, fct, bits):
    eintraege = [e for e in geraete.ENTITAETEN[fct] if e["oid"] == "/2/2/0"]
    assert {e["bit"] for e in eintraege} == bits
    assert len({e["key_suffix"] for e in eintraege}) == len(eintraege)
    assert all(e["platform"] == "binary_sensor" for e in eintraege)


def test_eigene_tabellen_haben_texte(geraete):
    assert geraete.TABELLEN["58/112"] == {0: "Pufferspeicher", 1: "Warmwasserspeicher"}
    assert geraete.TABELLEN["58/55"][2] == "Automatisch"
    assert geraete.TABELLEN["46/104"][3] == "Sperrzeit"


def test_mischer_des_infinity_heizkreises_bleibt_anzeige(geraete):
    assert {"58/83", "58/84"} <= geraete.NUR_ANZEIGE[1]


def test_die_pufferladung_folgt_der_betriebsart_des_moduls(geraete):
    """Am Puffermodul fct 15 heißt „Automatikkessel“ oder „FB-Kessel“: Die Ladepumpe läuft."""
    [ladung] = [e for e in geraete.ENTITAETEN[15] if e.get("key_suffix") == "pufferladung"]
    assert ladung["oid"] == "/2/9/0"
    assert ladung["platform"] == "binary_sensor"
    assert set(ladung["an_bei"]) == {14, 15}


def test_das_schaubild_nimmt_am_puffer_die_ladung_vor_den_pumpenbits():
    from .conftest import load_standalone

    werte = load_standalone("schema.werte")
    entitaeten = [
        {"entity_id": "binary_sensor.pumpe", "name": "Pufferladepumpe", "bereich": "binary_sensor"},
        {"entity_id": "sensor.drehzahl", "name": "Pufferladepumpe Drehzahl", "bereich": "sensor"},
        {
            "entity_id": "binary_sensor.ladung",
            "name": "Pufferladung",
            "bereich": "binary_sensor",
            "schluessel": "buffer_charging",
        },
    ]
    for e in entitaeten:
        e["hat_wert"] = True
    assert werte._pumpe(entitaeten, "puffer") == "binary_sensor.ladung"
