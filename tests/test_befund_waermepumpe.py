"""Wärmepumpe: Carnot-Zahl, Gütegrad je Luftband, gültige Tage, Vergleich gegen den Bezug."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from .conftest import load_standalone

HEUTE = date(2026, 12, 20)


@pytest.fixture(scope="module")
def wp():
    load_standalone("befund")
    return load_standalone("befund.waermepumpe")


def tag(wp, cop: float, vl: float = 35.0, luft: float = 2.0, waerme: float = 80.0):
    return wp.Tag(waerme, waerme / cop, wp.carnot(vl, luft), luft)


def test_carnot_nach_temperaturen(wp):
    # A7/W35: 308,15 K / 28 K = 11,0, wie in den Datenblatttabellen.
    assert wp.carnot(35.0, 7.0) == pytest.approx(11.005, abs=1e-3)
    assert wp.carnot(35.0, 2.0) == pytest.approx(9.338, abs=1e-3)
    assert wp.carnot(30.0, 25.0) is None


def test_baender_der_lufttemperatur(wp):
    assert wp.band(2.0) == "0"
    assert wp.band(-0.1) == "-5"
    assert wp.band(-12.0) == "-15"
    assert wp.band(15.0) is None
    assert wp.band(-21.0) is None


def test_guetegrad_rechnet_den_vorlauf_heraus(wp):
    # Gleiche Maschine, 10 K mehr Vorlauf: die Arbeitszahl fällt, der Gütegrad bleibt.
    kalt, warm = tag(wp, 4.0, vl=35.0), tag(wp, 4.0 * wp.carnot(45, 2) / wp.carnot(35, 2), vl=45.0)
    assert warm.waerme / warm.strom < 3.2
    assert warm.guete == pytest.approx(kalt.guete)
    assert kalt.guete == pytest.approx(0.4284, abs=1e-4)


def test_takt_zaehlt_nur_im_heizbetrieb(wp):
    heizen = wp.Probe(38.0, 3.0, 60.0, 4)
    assert wp.zaehlt(7, heizen, None)
    assert not wp.zaehlt(7, wp.Probe(38.0, 3.0, 60.0, 6), None)  # Abtauen
    assert not wp.zaehlt(7, wp.Probe(38.0, 3.0, 0.0, 4), None)  # Verdichter steht
    assert not wp.zaehlt(7, wp.Probe(50.0, 3.0, 60.0, 4, ww_h=12.1), 12.0)  # Warmwasser
    assert wp.zaehlt(27, heizen, None)
    assert not wp.zaehlt(27, wp.Probe(38.0, 3.0, 60.0, 7), None)


def test_tageszaehler_nach_mitternacht_zum_vortag(wp):
    tage = {}
    abend = datetime(2026, 12, 1, 23, 55)
    tage = wp.sammeln(
        tage, abend, 7, wp.Probe(None, None, 0, 3), False, {"q": 60.0, "cop": 3.9, "bh": 9.0}
    )
    # Die Steuerung setzt ihren Tag erst ein paar Minuten nach Mitternacht zurück.
    nacht = datetime(2026, 12, 2, 0, 3)
    tage = wp.sammeln(
        tage, nacht, 7, wp.Probe(None, None, 0, 3), False, {"q": 61.0, "cop": 3.9, "bh": 9.1}
    )
    assert tage["2026-12-01"]["q"] == 61.0
    assert "q" not in tage["2026-12-02"]
    danach = datetime(2026, 12, 2, 0, 8)
    tage = wp.sammeln(
        tage, danach, 7, wp.Probe(None, None, 0, 3), False, {"q": 0.2, "cop": 3.0, "bh": 0.1}
    )
    assert tage["2026-12-02"]["q"] == 0.2
    assert tage["2026-12-01"]["q"] == 61.0


def test_tagewerte_aus_tageszaehlern(wp):
    eintrag = {"n": 100, "vl": 3500.0, "luft": 200.0, "q": 80.0, "cop": 4.0, "bh": 10.0}
    werte = wp.tagewerte({"2026-12-01": eintrag, "2026-12-02": eintrag | {"bh": 2.0}}, 7)
    assert list(werte) == ["2026-12-01"]
    assert werte["2026-12-01"].strom == pytest.approx(20.0)
    assert werte["2026-12-01"].guete == pytest.approx(0.4284, abs=1e-4)


def test_tagewerte_aus_gesamtzaehlern(wp):
    temp = {"n": 100, "vl": 3500.0, "luft": 200.0}
    tage = {
        "2026-12-01": temp | {"wz": 1000.0, "sz": 300.0, "bhz": 500.0, "kz": 0.0},
        "2026-12-02": temp | {"wz": 1080.0, "sz": 320.0, "bhz": 510.0, "kz": 0.0},
        "2026-12-03": temp | {"wz": 1160.0, "sz": 340.0, "bhz": 520.0, "kz": 1.0},
        "2026-12-05": temp | {"wz": 1300.0, "sz": 380.0, "bhz": 540.0, "kz": 1.0},
    }
    werte = wp.tagewerte(tage, 27)
    # Der 3. kühlte, der 5. folgt auf eine Lücke.
    assert list(werte) == ["2026-12-02"]
    assert werte["2026-12-02"].waerme == 80.0


def test_unplausibler_tag_faellt_heraus(wp):
    eintrag = {"n": 100, "vl": 3500.0, "luft": 200.0, "q": 80.0, "cop": 9.5, "bh": 10.0}
    assert wp.tagewerte({"2026-12-01": eintrag}, 7) == {}
    assert wp.tagewerte({"2026-12-01": eintrag | {"cop": 4.0, "eheiz": True}}, 7) == {}


def _reihe(wp, cop_bezug: float, cop_jetzt: float, baender=(2.0, -3.0)) -> dict:
    tage = {}
    start = HEUTE - timedelta(days=80)
    for i in range(80):
        d = start + timedelta(days=i)
        luft = baender[i % len(baender)]
        cop = cop_jetzt if d >= HEUTE - timedelta(days=28) else cop_bezug
        tage[d.isoformat()] = tag(wp, cop * wp.carnot(35, luft) / wp.carnot(35, 2), luft=luft)
    return tage


def test_vergleich_ohne_aenderung(wp):
    b = wp.vergleich(_reihe(wp, 4.0, 4.0), None, HEUTE)
    assert b.art == "arbeitszahl"
    assert b.wert == pytest.approx(0.0, abs=0.05)
    assert b.status == "unauffaellig"
    assert b.stufe == "belastbar"
    assert set(b.angaben["baender"]) == {"0", "-5"}


def test_verdampfer_belegt_gibt_hinweis(wp):
    b = wp.vergleich(_reihe(wp, 4.0, 3.5), None, HEUTE)
    assert b.wert == pytest.approx(-12.5, abs=0.05)
    assert b.status == "hinweis"
    assert b.angaben["guete_jetzt"] == pytest.approx(0.375, abs=1e-3)


def test_ein_band_ist_vorlaeufig(wp):
    b = wp.vergleich(_reihe(wp, 4.0, 3.5, baender=(2.0,)), None, HEUTE)
    assert b.stufe == "vorlaeufig"
    assert b.status == "hinweis"


def test_reinigung_setzt_den_bezug_neu(wp):
    tage = _reihe(wp, 4.0, 3.5)
    gereinigt = (HEUTE - timedelta(days=10)).isoformat()
    b = wp.vergleich(tage, gereinigt, HEUTE)
    assert b.status == "sammelt"
    assert b.angaben["ohne_reinigungsdatum"] is False


def test_ohne_tage_sammelt(wp):
    b = wp.vergleich({}, None, HEUTE, inkl_warmwasser=True)
    assert b.status == "sammelt"
    assert b.angaben["inkl_warmwasser"] is True


def test_einheiten_der_zaehler(wp):
    assert wp.faktor("MWh") == 1000.0
    assert wp.faktor("kWh") == 1.0
    assert wp.faktor(None) == 1.0
