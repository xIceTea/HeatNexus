"""Prognosekorrektur: gelernter Versatz der Temperatur, Faktor der Sonne."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from .conftest import load_standalone

TZ = timezone(timedelta(hours=2))
START = datetime(2026, 9, 1, 0, 5, tzinfo=TZ)


@pytest.fixture(scope="module")
def k():
    load_standalone("automatik")
    return load_standalone("automatik.korrektur")


def lernen(k, tage: int, fehler_je_stunde, korrektur=None):
    """Täglich jede Stunde vormerken und messen; Fehler als Funktion der Stunde."""
    korrektur = korrektur or k.Temperaturkorrektur()
    for tag in range(tage):
        for stunde in range(24):
            zeit = START + timedelta(days=tag, hours=stunde)
            korrektur.vormerken([(zeit.replace(minute=0), 15.0)], zeit - timedelta(hours=1))
            korrektur.messen(zeit, 15.0 + fehler_je_stunde(stunde))
    return korrektur


def test_ohne_genug_tage_kein_versatz(k):
    korrektur = lernen(k, 6, lambda h: -2.0)
    heute = (START + timedelta(days=6)).date()
    assert korrektur.lerntage(14, heute) == 6
    assert korrektur.versatz(8, 14, heute) is None


def test_versatz_je_tageszeit(k):
    korrektur = lernen(k, 7, lambda h: -3.0 if h < 12 else 1.0)
    heute = (START + timedelta(days=7)).date()
    assert korrektur.versatz(8, 14, heute) == pytest.approx(-3.0)
    assert korrektur.versatz(15, 14, heute) == pytest.approx(1.0)
    assert korrektur.tagesversatz(14, heute) == pytest.approx(-1.0)


def test_fenster_von_drei_tagen(k):
    korrektur = k.Temperaturkorrektur()
    for tag in range(10):
        fehler = -4.0 if tag < 7 else 2.0
        for stunde in range(24):
            zeit = START + timedelta(days=tag, hours=stunde)
            korrektur.vormerken([(zeit.replace(minute=0), 15.0)], zeit - timedelta(hours=1))
            korrektur.messen(zeit, 15.0 + fehler)
    heute = (START + timedelta(days=10)).date()
    assert korrektur.versatz(8, 3, heute) == pytest.approx(2.0)
    assert korrektur.versatz(8, 14, heute) == pytest.approx((7 * -4.0 + 3 * 2.0) / 10)


def test_versatz_ist_begrenzt(k):
    korrektur = lernen(k, 7, lambda h: -12.0)
    heute = (START + timedelta(days=7)).date()
    assert korrektur.versatz(3, 14, heute) == -k.VERSATZ_MAX


def test_eine_stunde_wird_nur_einmal_gemessen(k):
    korrektur = k.Temperaturkorrektur()
    zeit = START.replace(hour=10)
    korrektur.vormerken([(zeit.replace(minute=0), 15.0)], zeit - timedelta(hours=1))
    korrektur.messen(zeit, 13.0)
    korrektur.messen(zeit + timedelta(minutes=5), 20.0)
    assert korrektur.als_dict()["fehler"] == [[zeit.date().isoformat(), 10, -2.0]]


def test_alte_fehler_fallen_heraus(k):
    korrektur = lernen(k, 20, lambda h: -1.0)
    heute = (START + timedelta(days=20)).date()
    daten = {eintrag[0] for eintrag in korrektur.als_dict()["fehler"]}
    assert len(daten) == k.FENSTER_MAX
    assert min(daten) > (heute - timedelta(days=k.FENSTER_MAX + 1)).isoformat()


def test_temperaturkorrektur_uebersteht_den_store(k):
    korrektur = lernen(k, 3, lambda h: -1.5)
    kopie = k.Temperaturkorrektur(korrektur.als_dict())
    assert kopie.als_dict() == korrektur.als_dict()
    assert k.Temperaturkorrektur("kaputt").als_dict() == {"vorgemerkt": {}, "fehler": []}


# --- Sonne -------------------------------------------------------------------
def pv_tage(k, anzahl: int, prognose: float, ist: float, korrektur=None):
    korrektur = korrektur or k.Pvkorrektur()
    for tag in range(anzahl):
        morgen = START + timedelta(days=tag, hours=6)
        korrektur.prognose_merken(morgen, prognose)
        korrektur.prognose_merken(
            morgen + timedelta(hours=3), prognose * 2
        )  # späterer Wert zählt nicht
        korrektur.ist_merken(morgen + timedelta(hours=12), ist / 2)
        korrektur.ist_merken(morgen + timedelta(hours=14), ist)
    return korrektur


def test_pv_faktor_aus_ist_und_prognose(k):
    korrektur = pv_tage(k, 7, 10.0, 8.8)
    heute = (START + timedelta(days=7)).date()
    assert korrektur.faktor(14, heute) == pytest.approx(0.88)
    assert korrektur.bester_ist(heute) == pytest.approx(8.8)


def test_pv_faktor_braucht_tage_und_zaehlt_heute_nicht(k):
    korrektur = pv_tage(k, 7, 10.0, 8.8)
    assert korrektur.faktor(14, (START + timedelta(days=6)).date()) is None


def test_pv_faktor_ist_begrenzt(k):
    korrektur = pv_tage(k, 7, 10.0, 30.0)
    assert korrektur.faktor(14, (START + timedelta(days=7)).date()) == k.FAKTOR_MAX


def test_prognose_vor_fuenf_uhr_zaehlt_nicht(k):
    korrektur = k.Pvkorrektur()
    korrektur.prognose_merken(START.replace(hour=4), 99.0)
    korrektur.prognose_merken(START.replace(hour=5), 10.0)
    assert korrektur.als_dict()["tage"][START.date().isoformat()]["prognose"] == 10.0


def test_pvkorrektur_uebersteht_den_store(k):
    korrektur = pv_tage(k, 3, 10.0, 8.0)
    assert k.Pvkorrektur(korrektur.als_dict()).als_dict() == korrektur.als_dict()
    assert k.Pvkorrektur(None).als_dict() == {"tage": {}}


def test_sonnenquote_mit_faktor(k):
    assert k.sonnenquote_korrigiert(10.0, 0.88, 11.0) == pytest.approx(80.0)
    assert k.sonnenquote_korrigiert(20.0, 1.0, 11.0) == 100.0
    assert k.sonnenquote_korrigiert(10.0, None, 11.0) is None
    assert k.sonnenquote_korrigiert(10.0, 0.9, None) is None
