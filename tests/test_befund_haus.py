"""Befunde zum Haus: tatsächliche Heizgrenze, Heizstunden je Gradtag, Wärmespeicher."""

from __future__ import annotations

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def haus():
    load_standalone("befund")
    return load_standalone("befund.haus")


def tag(at, heizh, datum="2026-10-01"):
    return {"datum": datum, "at": at, "heizh": heizh, "unter": 0, "folge": 0}


def kippt_bei_17():
    """Unter 16 °C heizt jeder Tag, bei 16 zwei von drei, bei 17 einer von drei, darüber keiner."""
    tage = [tag(12.4, 20), tag(13.3, 21), tag(14.2, 18), tag(15.5, 16), tag(15.1, 14)]
    tage += [tag(16.2, 12), tag(16.5, 10), tag(16.8, 0)]
    tage += [tag(17.2, 6), tag(17.5, 0), tag(17.8, 0)]
    tage += [tag(18.4, 0), tag(19.1, 0), tag(20.5, 0), tag(21.3, 0)]
    return tage


def test_heizgrenze_zwischen_den_klassenmitten(haus):
    befund = haus.heizgrenze(kippt_bei_17())
    assert befund.wert == pytest.approx(17.0, abs=0.05)
    assert befund.stufe == "belastbar"


def test_heizgrenze_sammelt_ohne_heizfreie_tage(haus):
    befund = haus.heizgrenze([tag(12.0 + i * 0.3, 20) for i in range(10)])
    assert befund.status == "sammelt"
    assert befund.wert is None


def test_heizgrenze_zaehlt_klassen(haus):
    klassen = {k: (n, h) for k, n, h in haus.heizgrenze(kippt_bei_17()).angaben["klassen"]}
    assert klassen[16] == (3, 2)
    assert klassen[17] == (3, 1)


def test_heizstunden_je_gradtag(haus):
    tage = [tag(10.0, 20), tag(12.0, 16), tag(16.0, 10)]
    # Gradtage 10 + 8 = 18 (16 °C zählt nicht), Heizstunden an diesen Tagen 36
    assert haus.heizstunden_je_gradtag(tage, 15.0) == pytest.approx(2.0)
    assert haus.heizstunden_je_gradtag([tag(16.0, 10)], 15.0) is None


def test_waermespeicher_rechnet_die_nacht(haus):
    modell = {
        "auskuehlzeit_h": 36.0,
        "sonne_k_h": 0.09,
        "fehler": 0.49,
        "fehler_bleibt": 0.56,
        "vergleiche": 9,
        "tage": 13,
        "status": "beobachtet",
    }
    befund = haus.waermespeicher(modell, raum=21.9, aussen=6.8)
    assert befund.wert == 36.0
    assert befund.stufe == "vorlaeufig"
    assert befund.angaben["nacht"]["nach"] == pytest.approx(18.9, abs=0.05)
    assert befund.angaben["ziel"] == pytest.approx(0.45, abs=0.005)


def test_waermespeicher_ohne_modell(haus):
    assert haus.waermespeicher({"status": "lernt"}, 21.0, 5.0).status == "sammelt"
    assert haus.waermespeicher(None, 21.0, 5.0).status == "braucht_daten"
