"""Eingänge der Automatik: Filter, Raumwert, Sonnenquote, Fenster."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def eingaben():
    load_standalone("automatik")
    return load_standalone("automatik.eingaben")


def test_filter_startet_beim_messwert(eingaben):
    assert eingaben.daempfen(None, 12.0, 0, 15) == (12.0, 12.0)


def test_filter_folgt_einem_sprung_traege(eingaben):
    stufen = (10.0, 10.0)
    for _ in range(12):  # 12 × 5 min = 1 h
        stufen = eingaben.daempfen(stufen, 20.0, 300, 15)
    assert 10.0 < stufen[1] < stufen[0] < 11.0


def test_filter_nach_vielen_zeitkonstanten_beim_messwert(eingaben):
    stufen = (10.0, 10.0)
    for _ in range(40):
        stufen = eingaben.daempfen(stufen, 20.0, 3600 * 5, 5)
    assert stufen[1] == pytest.approx(20.0, abs=0.01)


def test_raumwert_mittel_und_minimum(eingaben):
    assert eingaben.raumwert([21.0, None, 20.0], "mittel") == 20.5
    assert eingaben.raumwert([21.0, 20.0], "minimum") == 20.0
    assert eingaben.raumwert([None], "mittel") is None


def test_sonnenquote_aus_bewoelkung_nur_helle_stunden(eingaben):
    tag = datetime(2026, 9, 27, tzinfo=UTC)
    stunden = [(tag + timedelta(hours=h), 100.0 if h < 7 else 20.0) for h in range(24)]
    quote = eingaben.sonnenquote_aus_bewoelkung(
        stunden, tag + timedelta(hours=7), tag + timedelta(hours=19)
    )
    assert quote == 80.0


def test_sonnenquote_ohne_prognose_ist_unbekannt(eingaben):
    tag = datetime(2026, 9, 27, tzinfo=UTC)
    assert eingaben.sonnenquote_aus_bewoelkung([(tag, None)], tag, tag + timedelta(hours=1)) is None


def test_pv_quote_braucht_eine_woche_vergleich(eingaben):
    assert eingaben.sonnenquote_aus_pv(5.0, [8.0] * 6) is None
    assert eingaben.sonnenquote_aus_pv(4.0, [8.0] * 7) == 50.0
    assert eingaben.sonnenquote_aus_pv(10.0, [8.0] * 7) == 100.0
    assert eingaben.sonnenquote_aus_pv(None, [8.0] * 7) is None


def test_tagesmittel_aus_hoch_und_tief(eingaben):
    tage = [(date(2026, 9, 27), 18.0, 8.0), (date(2026, 9, 28), 14.0, None)]
    assert eingaben.tagesmittel(tage, date(2026, 9, 27)) == 13.0
    assert eingaben.tagesmittel(tage, date(2026, 9, 28)) == 14.0
    assert eingaben.tagesmittel(tage, date(2026, 9, 29)) is None


def test_temperatursturz_erkennt_schnelles_fallen(eingaben):
    verlauf = [(0.0, 21.0), (300.0, 20.8), (600.0, 20.4)]  # 0,6 K in 10 min
    assert eingaben.temperatursturz(verlauf, 3.0) is True
    langsam = [(0.0, 21.0), (600.0, 20.9)]
    assert eingaben.temperatursturz(langsam, 3.0) is False
    assert eingaben.temperatursturz([(0.0, 21.0)], 3.0) is False


def test_wert_zur_stunde_nimmt_den_geltenden_stand(eingaben):
    t = datetime(2026, 9, 27, tzinfo=UTC)
    reihe = [(t + timedelta(hours=7, minutes=40), 9.0), (t + timedelta(hours=8, minutes=20), 11.0)]
    assert eingaben.wert_zur_stunde(reihe, t + timedelta(hours=8)) == 9.0
    assert eingaben.wert_zur_stunde(reihe, t + timedelta(hours=9)) == 11.0
    # Vor dem ersten Stand zählt der erste Wert innerhalb der Stunde.
    assert eingaben.wert_zur_stunde(reihe, t + timedelta(hours=7)) == 9.0
    assert eingaben.wert_zur_stunde(reihe, t + timedelta(hours=5)) is None
    assert eingaben.wert_zur_stunde([], t) is None
