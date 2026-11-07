"""Abgaswächter: Abgasüberhöhung gegen den Bezug nach der Reinigung, Abgasverlust nach Siegert."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from .conftest import load_standalone

T0 = datetime(2026, 11, 20, 10, 0)


@pytest.fixture(scope="module")
def ab():
    load_standalone("befund")
    return load_standalone("befund.abgas")


def m(ab, abgas=120.0, kessel=70.0, leistung=60.0, phase=8, o2=7.0):
    return ab.Messung(abgas, kessel, leistung, phase, o2)


def test_gueltig_erst_nach_15_minuten_modulation(ab):
    zustand, stufe = ab.bewerten({}, m(ab), T0, logwin=False)
    assert stufe is None
    zustand, stufe = ab.bewerten(zustand, m(ab), T0 + timedelta(minutes=10), logwin=False)
    assert stufe is None
    _, stufe = ab.bewerten(zustand, m(ab), T0 + timedelta(minutes=15), logwin=False)
    assert stufe == "50"


def test_phasenwechsel_beginnt_von_vorn(ab):
    zustand, _ = ab.bewerten({}, m(ab), T0, logwin=False)
    zustand, _ = ab.bewerten(zustand, m(ab, phase=17), T0 + timedelta(minutes=5), logwin=False)
    _, stufe = ab.bewerten(zustand, m(ab), T0 + timedelta(minutes=20), logwin=False)
    assert stufe is None


def test_leistungssprung_und_teillast_ungueltig(ab):
    zustand, _ = ab.bewerten({}, m(ab, leistung=60.0), T0, logwin=False)
    zustand, stufe = ab.bewerten(
        zustand, m(ab, leistung=80.0), T0 + timedelta(minutes=20), logwin=False
    )
    assert stufe is None
    zustand, stufe = ab.bewerten(
        zustand, m(ab, leistung=25.0), T0 + timedelta(minutes=25), logwin=False
    )
    assert stufe is None


def test_logwin_ohne_leistung_nach_30_minuten(ab):
    zustand, _ = ab.bewerten({}, m(ab, leistung=None), T0, logwin=True)
    zustand, stufe = ab.bewerten(
        zustand, m(ab, leistung=None), T0 + timedelta(minutes=20), logwin=True
    )
    assert stufe is None
    _, stufe = ab.bewerten(zustand, m(ab, leistung=None), T0 + timedelta(minutes=30), logwin=True)
    assert stufe == "m"


def test_fehlender_wert_ist_ungueltig(ab):
    zustand, _ = ab.bewerten({}, m(ab), T0, logwin=False)
    _, stufe = ab.bewerten(zustand, m(ab, abgas=None), T0 + timedelta(minutes=20), logwin=False)
    assert stufe is None


def test_stufen(ab):
    assert [ab.stufe(x) for x in (30, 49, 50, 70, 100)] == ["30", "30", "50", "70", "90"]


def test_sammeln_ist_unveraenderlich(ab):
    alt = {}
    neu = ab.sammeln(alt, "2026-11-20", "50", 50.0, 7.0, 120.0)
    neu = ab.sammeln(neu, "2026-11-20", "50", 52.0, None, 122.0)
    assert alt == {}
    assert neu["2026-11-20"]["50"] == [102.0, 2, 7.0, 1, 242.0, 0.0, 0]


def test_konstanten_je_brennstoff(ab):
    assert ab.brennstoff(9, None) == "pellets"
    assert ab.brennstoff(25, 2) == "pellets"
    assert ab.brennstoff(25, 0) == "hackgut"
    assert ab.brennstoff(25, 1) == "hackgut_feucht"
    assert ab.brennstoff(25, 5) == "hackgut_trocken"
    assert ab.brennstoff(10, None) == "scheitholz"
    assert ab.konstanten("pellets") == (0.68, 0.0085)


def test_abgasverlust_nach_siegert(ab):
    k = ab.konstanten("pellets")
    assert ab.abgasverlust(140.0, 20.0, 7.0, k) == pytest.approx(6.85, abs=0.01)
    assert ab.abgasverlust(140.0, 20.0, None, k) is None
    assert ab.abgasverlust(140.0, 20.0, 21.0, k) is None


def tage(ab, start: date, anzahl: int, dt: float, n: int = 6, stufe="50", o2=7.0, tl=None):
    """Je Tag `n` Messungen mit Überhöhung `dt` und Abgas `70 + dt`."""
    ergebnis: dict = {}
    for i in range(anzahl):
        tag = (start + timedelta(days=i)).isoformat()
        for _ in range(n):
            ergebnis = ab.sammeln(ergebnis, tag, stufe, dt, o2, 70.0 + dt, tl)
    return ergebnis


def test_raumluft_gemessen_geht_in_den_verlust(ab):
    """Im Winter 12 °C, im Bezug 22 °C Raumluft: 10 K mehr Abstand zur Luft heben den Verlust."""
    heute = date(2026, 11, 30)
    bezug = tage(ab, date(2026, 10, 1), 14, 40.0, tl=22.0)
    jetzt = tage(ab, date(2026, 11, 23), 7, 40.0, tl=12.0)
    _, verlust = ab.vergleich(bezug | jetzt, "2026-10-01", heute, False, "pellets")
    assert verlust.wert == pytest.approx(10.0 * (0.68 / 14 + 0.0085), abs=0.01)
    assert verlust.angaben["luft_geschaetzt"] is False
    assert verlust.angaben["verlust_jetzt"] == pytest.approx(
        (110 - 12) * (0.68 / 14 + 0.0085), abs=0.01
    )


def test_raumluft_nur_in_einem_zeitraum_bleibt_geschaetzt(ab):
    heute = date(2026, 11, 30)
    bezug = tage(ab, date(2026, 10, 1), 14, 40.0)
    jetzt = tage(ab, date(2026, 11, 23), 7, 40.0, tl=12.0)
    _, verlust = ab.vergleich(bezug | jetzt, "2026-10-01", heute, False, "pellets")
    assert verlust.wert == pytest.approx(0.0, abs=0.01)
    assert verlust.angaben["luft_geschaetzt"] is True


def test_raumluft_fehlt_in_einer_stufe_gilt_fuer_alle_geschaetzt(ab):
    """Eine Grundlage für alle Stufen: fehlt der Fühler in einer, rechnen alle mit 20 °C."""
    heute = date(2026, 11, 30)
    tage_ = tage(ab, date(2026, 10, 1), 14, 40.0, tl=22.0)
    tage_ |= tage(ab, date(2026, 11, 23), 7, 40.0, tl=12.0)
    for i in range(14):
        tag = (date(2026, 10, 1) + timedelta(days=i)).isoformat()
        for _ in range(6):
            tage_ = ab.sammeln(tage_, tag, "100", 40.0, 7.0, 110.0)
    for i in range(7):
        tag = (date(2026, 11, 23) + timedelta(days=i)).isoformat()
        for _ in range(6):
            tage_ = ab.sammeln(tage_, tag, "100", 40.0, 7.0, 110.0, 12.0)
    _, verlust = ab.vergleich(tage_, "2026-10-01", heute, False, "pellets")
    assert verlust.angaben["luft_geschaetzt"] is True
    assert verlust.wert == pytest.approx(0.0, abs=0.01)


def test_unplausible_raumluft_zaehlt_nicht(ab):
    neu = ab.sammeln({}, "2026-11-20", "50", 50.0, 7.0, 120.0, 85.0)
    assert neu["2026-11-20"]["50"][5:] == [0.0, 0]


def test_alte_tage_ohne_raumluft_lesbar(ab):
    alt = {"2026-11-20": {"50": [50.0, 1, 7.0, 1, 120.0]}}
    neu = ab.sammeln(alt, "2026-11-20", "50", 50.0, 7.0, 120.0, 20.0)
    assert neu["2026-11-20"]["50"] == [100.0, 2, 14.0, 2, 240.0, 20.0, 1]


def test_vergleich_zeigt_anstieg_seit_reinigung(ab):
    heute = date(2026, 11, 30)
    bezug = tage(ab, date(2026, 10, 1), 14, 40.0)
    jetzt = tage(ab, date(2026, 11, 23), 7, 62.0)
    dt, verlust = ab.vergleich(
        bezug | jetzt, "2026-10-01", heute, logwin=False, brennstoff_="pellets"
    )
    assert dt.wert == pytest.approx(22.0)
    assert dt.status == "hinweis"
    assert dt.stufe == "vorlaeufig"
    assert verlust.wert == pytest.approx(22.0 * (0.68 / 14 + 0.0085), abs=0.01)


def test_vergleich_unauffaellig_und_belastbar_mit_zwei_stufen(ab):
    heute = date(2026, 11, 30)
    daten = tage(ab, date(2026, 10, 1), 14, 40.0) | {}
    for stufe in ("50", "70"):
        bezug = tage(ab, date(2026, 10, 1), 14, 40.0, stufe=stufe)
        jetzt = tage(ab, date(2026, 11, 23), 7, 45.0, stufe=stufe)
        for quelle in (bezug, jetzt):
            for tag, je_stufe in quelle.items():
                daten.setdefault(tag, {}).update(je_stufe)
    dt, _ = ab.vergleich(daten, "2026-10-01", heute, logwin=False, brennstoff_="pellets")
    assert dt.wert == pytest.approx(5.0)
    assert dt.status == "unauffaellig"
    assert dt.stufe == "belastbar"


def test_ohne_gemeinsame_stufe_sammelt(ab):
    heute = date(2026, 11, 30)
    bezug = tage(ab, date(2026, 10, 1), 14, 40.0, stufe="50")
    jetzt = tage(ab, date(2026, 11, 23), 7, 62.0, stufe="90")
    dt, verlust = ab.vergleich(
        bezug | jetzt, "2026-10-01", heute, logwin=False, brennstoff_="pellets"
    )
    assert dt.status == "sammelt"
    assert verlust.status == "sammelt"


def test_bezug_ohne_reinigungsdatum_vermerkt(ab):
    heute = date(2026, 11, 30)
    bezug = tage(ab, date(2026, 10, 1), 14, 40.0)
    jetzt = tage(ab, date(2026, 11, 23), 7, 42.0)
    dt, _ = ab.vergleich(bezug | jetzt, None, heute, logwin=False, brennstoff_="pellets")
    assert dt.angaben["ohne_reinigungsdatum"] is True
    assert dt.angaben["bezug_seit"] == "2026-10-01"


def test_neuer_bezug_nach_reinigung(ab):
    heute = date(2026, 11, 30)
    alt = tage(ab, date(2026, 9, 1), 14, 70.0)
    bezug = tage(ab, date(2026, 10, 1), 14, 40.0)
    jetzt = tage(ab, date(2026, 11, 23), 7, 41.0)
    dt, _ = ab.vergleich(
        alt | bezug | jetzt, "2026-10-01", heute, logwin=False, brennstoff_="pellets"
    )
    assert dt.wert == pytest.approx(1.0)


def test_ohne_o2_kein_verlust(ab):
    heute = date(2026, 11, 30)
    bezug = tage(ab, date(2026, 10, 1), 14, 40.0, o2=None)
    jetzt = tage(ab, date(2026, 11, 23), 7, 62.0, o2=None)
    dt, verlust = ab.vergleich(
        bezug | jetzt, "2026-10-01", heute, logwin=False, brennstoff_="pellets"
    )
    assert dt.wert == pytest.approx(22.0)
    assert verlust.status == "braucht_daten"


def test_o2_null_gilt_als_fehlendes_signal(ab):
    """Eine Sonde, die im Betrieb 0 % meldet, ergibt keinen Verlust statt eines falschen."""
    k = ab.konstanten("pellets")
    assert ab.abgasverlust(140.0, 20.0, 0.0, k) is None
    assert ab.abgasverlust(140.0, 20.0, 1.9, k) is None
    assert ab.abgasverlust(140.0, 20.0, 2.0, k) is not None
    heute = date(2026, 11, 30)
    bezug = tage(ab, date(2026, 10, 1), 14, 40.0, o2=0.0)
    jetzt = tage(ab, date(2026, 11, 23), 7, 62.0, o2=0.0)
    dt, verlust = ab.vergleich(
        bezug | jetzt, "2026-10-01", heute, logwin=False, brennstoff_="pellets"
    )
    assert dt.wert == pytest.approx(22.0)
    assert verlust.status == "braucht_daten"


def test_einzelne_o2_null_verfaelscht_das_mittel_nicht(ab):
    """Ein Takt ohne Signal fällt aus der O2-Summe; die übrigen Takte zählen weiter."""
    summe = ab.sammeln({}, "2026-11-01", "50", 40.0, 7.0, 110.0)
    summe = ab.sammeln(summe, "2026-11-01", "50", 40.0, 0.0, 110.0)
    werte = summe["2026-11-01"]["50"]
    assert werte[1] == 2
    assert werte[2] / werte[3] == pytest.approx(7.0)


def test_logwin_belastbar_ab_36_messungen(ab):
    heute = date(2026, 11, 30)
    bezug = tage(ab, date(2026, 10, 1), 14, 40.0, n=3, stufe="m")
    jetzt = tage(ab, date(2026, 11, 23), 7, 45.0, n=6, stufe="m")
    dt, _ = ab.vergleich(bezug | jetzt, "2026-10-01", heute, logwin=True, brennstoff_="scheitholz")
    assert dt.stufe == "belastbar"


def test_stunde_aus_statistik_nur_bei_ruhiger_modulation(ab):
    leistung = {"mean": 55.0, "min": 50.0, "max": 59.0}
    abgas_, kessel = {"mean": 120.0}, {"mean": 70.0}
    assert ab.stunde_aus_statistik(leistung, abgas_, kessel, {"mean": 7.5}) == (
        "50",
        50.0,
        7.5,
        120.0,
    )
    # Der Brenner stand zwischendurch: das Minimum liegt bei null.
    assert ab.stunde_aus_statistik(leistung | {"min": 0.0}, abgas_, kessel, {}) is None
    # Die Leistung sprang um mehr als 10 Prozentpunkte.
    assert ab.stunde_aus_statistik(leistung | {"max": 75.0}, abgas_, kessel, {}) is None
    assert ab.stunde_aus_statistik(leistung, {}, kessel, {}) is None


def test_nachgerechnete_stunde_zaehlt_zwoelf_takte(ab):
    neu = ab.sammeln({}, "2026-10-01", "50", 50.0, 7.5, 120.0, None, 12)
    assert neu["2026-10-01"]["50"] == [600.0, 12, 90.0, 12, 1440.0, 0.0, 0]


def test_bezug_aus_nachgerechneten_tagen_vermerkt(ab):
    heute = date(2026, 11, 30)
    bezug = tage(ab, date(2026, 10, 1), 14, 40.0)
    jetzt = tage(ab, date(2026, 11, 23), 7, 40.0)
    dt, _ = ab.vergleich(bezug | jetzt, "2026-10-01", heute, False, "pellets", "2026-10-20")
    assert dt.angaben["nachgerechnet"] is True
    dt, _ = ab.vergleich(bezug | jetzt, "2026-10-01", heute, False, "pellets")
    assert dt.angaben["nachgerechnet"] is False
