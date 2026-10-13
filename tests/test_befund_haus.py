"""Befunde zum Haus: Heizgrenze im Betrieb gegen TA Heizbetrieb, Wärmespeicher."""

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
    klassen = haus._klassen(kippt_bei_17())
    assert klassen[16] == [3, 2]
    assert klassen[17] == [3, 1]


@pytest.mark.parametrize(("eingestellt", "status"), [(18.0, "unauffaellig"), (20.0, "hinweis")])
def test_heizgrenze_prueft_gegen_die_einstellung(haus, eingestellt, status):
    befund = haus.heizgrenze(kippt_bei_17(), eingestellt)
    assert befund.status == status
    assert befund.angaben["abweichung"] == pytest.approx(17.0 - eingestellt, abs=0.05)


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
