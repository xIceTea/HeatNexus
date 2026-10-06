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


def test_thermostat_liefert_ist_ziel_und_anforderung(eingaben):
    attribute = {"current_temperature": 20.8, "temperature": 21.0, "hvac_action": "heating"}
    assert eingaben.raum_messung("climate.bad", "heat", attribute) == eingaben.Messung(
        20.8, 21.0, True
    )


def test_thermostat_im_leerlauf_fordert_nichts_an(eingaben):
    attribute = {"current_temperature": 19.8, "temperature": 18.0, "hvac_action": "idle"}
    assert eingaben.raum_messung("climate.schlafzimmer", "auto", attribute) == eingaben.Messung(
        19.8, 18.0, False
    )


@pytest.mark.parametrize("zustand", ["unavailable", "unknown"])
def test_nicht_erreichbares_thermostat_zaehlt_nicht(eingaben, zustand):
    attribute = {"current_temperature": 19.0, "temperature": 5.0}
    assert eingaben.raum_messung("climate.bad", zustand, attribute) is None


def test_ausgeschaltetes_thermostat_misst_weiter_ohne_ziel_und_bedarf(eingaben):
    attribute = {"current_temperature": 19.0, "temperature": 5.0, "hvac_action": "off"}
    messung = eingaben.raum_messung("climate.bad", "off", attribute)
    assert messung == eingaben.Messung(19.0, None, False, aus=True)


def test_temperatursensor_kennt_kein_ziel(eingaben):
    assert eingaben.raum_messung("sensor.kueche_temperatur", "18.9", {}) == eingaben.Messung(
        18.9, None, None
    )
    assert eingaben.raum_messung("sensor.kueche_temperatur", "unavailable", {}) is None


def _uhr(tag: int, stunde: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, tag, stunde, minute, tzinfo=UTC)


def test_lauf_zaehlt_die_minuten_des_tages(eingaben):
    lauf = eingaben.lauf_fortschreiben(eingaben.Lauf(), _uhr(28, 9), laeuft=True)
    assert eingaben.lauf_minuten(lauf, _uhr(28, 10)) == 60
    lauf = eingaben.lauf_fortschreiben(lauf, _uhr(28, 10, 30), laeuft=False)
    assert eingaben.lauf_minuten(lauf, _uhr(28, 12)) == 90


def test_neuer_tag_beginnt_bei_null(eingaben):
    lauf = eingaben.lauf_fortschreiben(eingaben.Lauf(), _uhr(28, 9), laeuft=True)
    lauf = eingaben.lauf_fortschreiben(lauf, _uhr(28, 11), laeuft=False)
    lauf = eingaben.lauf_fortschreiben(lauf, _uhr(29, 6), laeuft=False)
    assert eingaben.lauf_minuten(lauf, _uhr(29, 7)) == 0


def test_lauf_ueber_mitternacht_zaehlt_ab_mitternacht(eingaben):
    lauf = eingaben.lauf_fortschreiben(eingaben.Lauf(), _uhr(28, 23), laeuft=True)
    lauf = eingaben.lauf_fortschreiben(lauf, _uhr(29, 1), laeuft=True)
    assert eingaben.lauf_minuten(lauf, _uhr(29, 1)) == 60


def test_lauf_uebersteht_den_store(eingaben):
    lauf = eingaben.lauf_fortschreiben(eingaben.Lauf(), _uhr(28, 9), laeuft=True)
    assert eingaben.lauf_aus_dict(eingaben.lauf_als_dict(lauf)) == lauf
    assert eingaben.lauf_aus_dict({"seit": "kaputt"}) == eingaben.Lauf()


@pytest.mark.parametrize(
    ("at", "vorher", "erwartet"),
    [
        (19.1, None, True),
        (16.9, True, False),
        (18.0, True, True),
        (18.0, False, False),
        (18.0, None, None),
    ],
)
def test_heizgrenze_der_steuerung_mit_hysterese(eingaben, at, vorher, erwartet):
    assert eingaben.heizgrenze_halten(at, 18.0, vorher) is erwartet


def test_minimum_bis_morgen_reicht_bis_neun_uhr(eingaben):
    abend = datetime(2026, 10, 2, 17, 0, tzinfo=UTC)
    stunden = [
        (abend - timedelta(hours=2), 5.0),
        (abend, 18.0),
        (datetime(2026, 10, 3, 5, 0, tzinfo=UTC), 13.7),
        (datetime(2026, 10, 3, 10, 0, tzinfo=UTC), 2.0),
    ]
    assert eingaben.minimum_bis_morgen(stunden, abend) == 13.7


def test_minimum_bis_morgen_ohne_werte(eingaben):
    jetzt = datetime(2026, 10, 3, 2, 0, tzinfo=UTC)
    assert eingaben.minimum_bis_morgen([(jetzt, None)], jetzt) is None


def test_vorrangtage_zaehlen_die_letzten_drei_tage(eingaben):
    heute = date(2026, 10, 6)
    minuten = {
        "2026-10-05": 40.0,
        "2026-10-04": 5.0,
        "2026-10-03": 90.0,
        "2026-10-02": 300.0,  # liegt außerhalb der drei Tage
        "2026-10-06": 500.0,  # heute zählt nicht
    }
    assert eingaben.vorrang_tage(minuten, heute, 15.0) == 2
    assert eingaben.vorrang_tage({}, heute, 15.0) == 0
