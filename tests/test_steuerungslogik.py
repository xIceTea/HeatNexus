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


def _erfuellt(saetze: list[dict], werte: dict[str, str]) -> bool:
    return any(werte.get(s["oid"]) in s["values"] for s in saetze)


@pytest.mark.parametrize(
    ("modus", "sichtbar"),
    [("0", set()), ("1", {"5/65"}), ("2", {"5/64"}), ("3", {"5/65"})],
)
def test_zirkulationsprogramm_folgt_der_betriebsart(geraete, modus, sichtbar):
    regeln = geraete.BEDINGUNGEN[14]
    gezeigt = {a for a in ("5/64", "5/65") if _erfuellt(regeln[a], {"5/6": modus})}
    assert gezeigt == sichtbar


def test_ohne_zirkulation_entfallen_ihre_werte_am_warmwasser(geraete):
    regeln = geraete.BEDINGUNGEN[2]
    for adresse in ("0/118", "1/118", "59/18", "5/64", "5/65"):
        assert not _erfuellt(regeln[adresse], {"5/6": "0"}), adresse


@pytest.mark.parametrize(("art", "heizprogramme"), [("1", True), ("2", True), ("4", False)])
def test_infinity_programme_folgen_der_regelart(geraete, art, heizprogramme):
    regeln = geraete.BEDINGUNGEN[1]
    assert _erfuellt(regeln["3/61"], {"7/76": art}) is heizprogramme
    assert _erfuellt(regeln["58/78"], {"7/76": art}) is not heizprogramme


def test_jede_bedingung_hat_saetze_mit_werten(geraete):
    for fct, regeln in geraete.BEDINGUNGEN.items():
        for adresse, saetze in regeln.items():
            assert saetze, (fct, adresse)
            assert all(s["oid"] and s["values"] for s in saetze), (fct, adresse)


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
