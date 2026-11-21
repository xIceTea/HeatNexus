"""Freigabe einer Bedienung nach dem Zustand der Anlage.

Eine Taste ist nur bedienbar, wenn jede ihrer Bedingungen erfüllt ist. Fehlt ein
Wert, gilt die Bedienung als gesperrt: Ohne Zustand darf nichts geschrieben werden.
"""

from __future__ import annotations

import pytest

from .conftest import load_standalone

PRAEFIX = "/1/65/0"


@pytest.fixture(scope="module")
def freigabe():
    return load_standalone("freigabe")


@pytest.fixture(scope="module")
def zuendung():
    # Über das Paket laden: Das Modul bindet beim Import Nachbarn aus `geraete` ein.
    return load_standalone("geraete").automatikkessel


def _werte(**adressen: str) -> dict[str, str]:
    return {f"{PRAEFIX}/{a.replace('_', '/')}/0": w for a, w in adressen.items()}


def test_alle_bedingungen_erfuellt(freigabe):
    regeln = {"12/105": ("1",), "2/1": ("3", "6", "13")}
    werte = _werte(**{"12_105": "1", "2_1": "13"})
    assert freigabe.freigegeben(regeln, PRAEFIX, werte)


def test_eine_bedingung_verfehlt_sperrt(freigabe):
    regeln = {"12/105": ("1",), "2/1": ("3", "6", "13")}
    assert not freigabe.freigegeben(regeln, PRAEFIX, _werte(**{"12_105": "1", "2_1": "8"}))
    assert not freigabe.freigegeben(regeln, PRAEFIX, _werte(**{"12_105": "0", "2_1": "3"}))


def test_fehlender_wert_sperrt(freigabe):
    assert not freigabe.freigegeben({"12/105": ("1",)}, PRAEFIX, {})


def test_kommazahl_zaehlt_wie_ganzzahl(freigabe):
    assert freigabe.freigegeben({"2/1": ("3",)}, PRAEFIX, _werte(**{"2_1": "3.0"}))


def test_ohne_regeln_frei(freigabe):
    assert freigabe.freigegeben(None, PRAEFIX, {})
    assert freigabe.freigegeben({}, PRAEFIX, {})


def test_adressen_der_regeln(freigabe):
    assert freigabe.adressen({"12/105": ("1",)}, PRAEFIX) == [f"{PRAEFIX}/12/105/0"]


def _taste(modul, wert: str) -> dict:
    return next(e for e in modul.ENTITAETEN if e.get("press_value") == wert)


@pytest.mark.parametrize("wert", ["2", "4", "3", "0"])
def test_zuendtasten_nur_am_logwin_2025(zuendung, wert):
    taste = _taste(zuendung, wert)
    assert taste["oid"] == "/46/100/0"
    assert taste["klassen"] == ("2009",)


@pytest.mark.parametrize("wert", ["2", "4", "3", "0"])
def test_zuendtasten_brauchen_eingeschaltete_zuendung(freigabe, zuendung, wert):
    regeln = _taste(zuendung, wert)["freigabe"]
    aus = _werte(**{"12_105": "0", "2_1": "3", "46_104": "1"})
    assert not freigabe.freigegeben(regeln, PRAEFIX, aus)


@pytest.mark.parametrize("phase", ["3", "6", "13"])
def test_zuenden_in_standby_und_zuendphasen(freigabe, zuendung, phase):
    regeln = _taste(zuendung, "2")["freigabe"]
    assert freigabe.freigegeben(regeln, PRAEFIX, _werte(**{"12_105": "1", "2_1": phase}))


@pytest.mark.parametrize("phase", ["8", "17", "4"])
def test_kein_zuenden_waehrend_der_kessel_brennt(freigabe, zuendung, phase):
    regeln = _taste(zuendung, "2")["freigabe"]
    assert not freigabe.freigegeben(regeln, PRAEFIX, _werte(**{"12_105": "1", "2_1": phase}))


def test_abbrechen_nur_bei_laufender_zuendung(freigabe, zuendung):
    regeln = _taste(zuendung, "0")["freigabe"]
    laeuft = _werte(**{"12_105": "1", "2_1": "6", "46_104": "1"})
    keine = _werte(**{"12_105": "1", "2_1": "6", "46_104": "0"})
    assert freigabe.freigegeben(regeln, PRAEFIX, laeuft)
    assert not freigabe.freigegeben(regeln, PRAEFIX, keine)


def test_jede_freigabeadresse_wird_nachgelesen(zuendung):
    for taste in (e for e in zuendung.ENTITAETEN if e.get("platform") == "button"):
        assert set(taste["freigabe"]) <= set(taste["nachlesen"]) | {"12/105"}, taste["name"]
