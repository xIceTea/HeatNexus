"""Pflege: Termine aus Restzählern, Stunden seit Service oder Kalender."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from .conftest import load_standalone

HEUTE = date(2026, 11, 20)


@pytest.fixture(scope="module")
def p():
    load_standalone("befund")
    return load_standalone("befund.pflege")


def verlauf(start: float, je_tag: float, tage: int, ende: date = HEUTE) -> dict[str, float]:
    """Je Tag ein Restwert, der um `je_tag` sinkt, endend an `ende`."""
    return {
        (ende - timedelta(days=tage - 1 - i)).isoformat(): start - je_tag * i for i in range(tage)
    }


def zaehler(p, art="hauptreinigung"):
    return next(x for x in p.PFLEGE[25] if x.art == art)


def test_tabelle_deckt_biowin_purowin_gas_und_logwin(p):
    assert [x.adresse for x in p.PFLEGE[9]] == ["/20/61/0", "/20/62/0", "/20/63/0"]
    assert [x.adresse for x in p.PFLEGE[25]] == ["/39/91/0", "/39/92/0", "/39/93/0"]
    assert p.PFLEGE[6][0].weise == p.SEIT_SERVICE
    assert {x.art for x in p.LOGWIN} == {"asche", "jahresreinigung"}
    assert all(x.weise == p.KALENDER for x in p.LOGWIN)


def test_hoechst_nimmt_echtes_maximum_sonst_gesehenes(p):
    assert p.hoechst(4216, 700.0) == 4216.0
    assert p.hoechst(65534, 700.0) == 700.0
    assert p.hoechst(None, None) is None


def test_sprung_nur_ueber_zehn_prozent(p):
    assert p.sprung(10.0, 757.0, 757.0) is True
    assert p.sprung(100.0, 101.0, 757.0) is False
    assert p.sprung(None, 757.0, 757.0) is False


def test_kleiner_gelernter_hoechstwert_macht_kein_rauschen_zum_sprung(p):
    assert p.sprung(5.0, 6.0, 5.0) is False
    assert p.sprung(5.0, 757.0, 5.0) is True


def test_zuruecksetzen_seit_service(p):
    assert p.zurueckgesetzt(1500.0, 3.0) is True
    assert p.zurueckgesetzt(1500.0, 1501.0) is False


def test_abnahme_zaehlt_tage_ohne_betrieb_und_keine_spruenge(p):
    v = verlauf(500.0, 4.0, 15)
    assert p.abnahme_je_tag(v, HEUTE) == (4.0, 14)
    # Am 12.11. erledigt: der Zähler beginnt neu bei 757 und sinkt wieder um 4 h je Tag.
    neu = {d: 757.0 - 4.0 * i for i, d in enumerate(sorted(x for x in v if x >= "2026-11-12"))}
    rate, tage = p.abnahme_je_tag(v | neu, HEUTE)
    assert tage == 14
    assert rate == pytest.approx(52 / 14, abs=0.01)


def test_faelligkeit_aus_eigenem_verlauf(p):
    eintrag = {"rest": 140.0, "verlauf": verlauf(196.0, 4.0, 15)}
    b = p.befund(zaehler(p), eintrag, HEUTE)
    assert b.art == "pflege_hauptreinigung"
    assert b.wert == 35.0
    assert b.angaben["datum"] == "2026-12-25"
    assert b.status == "unauffaellig"
    assert b.stufe == "belastbar"


def test_bald_faellig_ist_hinweis(p):
    eintrag = {"rest": 20.0, "verlauf": verlauf(76.0, 4.0, 15)}
    b = p.befund(zaehler(p), eintrag, HEUTE)
    assert b.wert == 5.0
    assert b.status == "hinweis"


def test_sommer_ruht(p):
    eintrag = {"rest": 140.0, "verlauf": verlauf(143.0, 0.2, 15)}
    b = p.befund(zaehler(p), eintrag, HEUTE)
    assert b.wert is None
    assert b.angaben["ruht"] is True


def test_zu_kurzer_verlauf_sammelt(p):
    eintrag = {"rest": 140.0, "verlauf": verlauf(148.0, 4.0, 3)}
    assert p.befund(zaehler(p), eintrag, HEUTE).status == "sammelt"


def test_ohne_restwert_braucht_daten(p):
    assert p.befund(zaehler(p), {}, HEUTE).status == "braucht_daten"


def test_fortschreiben_erkennt_sprung_und_kuerzt_verlauf(p):
    alt = {"rest": 2.0, "hoechst": 757.0, "verlauf": verlauf(80.0, 2.0, 40, date(2026, 11, 19))}
    neu = p.fortschreiben(alt, 757.0, HEUTE, None, zaehler(p))
    assert neu["zuletzt"] == "2026-11-20"
    assert neu["rest"] == 757.0
    assert min(neu["verlauf"]) >= "2026-10-21"
    assert alt["rest"] == 2.0


def test_fortschreiben_rauschen_ist_kein_sprung(p):
    alt = {"rest": 100.0, "hoechst": 757.0, "zuletzt": "2026-10-01"}
    neu = p.fortschreiben(alt, 101.0, HEUTE, None, zaehler(p))
    assert neu["zuletzt"] == "2026-10-01"


def test_fortschreiben_ohne_wert_aendert_nichts(p):
    alt = {"rest": 100.0}
    assert p.fortschreiben(alt, None, HEUTE, None, zaehler(p)) == alt


def test_wartung_gemeldet_gibt_drei_monate_frist(p):
    wartung = zaehler(p, "wartung")
    alt = {"rest": 1.0, "hoechst": 4216.0}
    neu = p.fortschreiben(alt, 0.0, HEUTE, 4216, wartung)
    assert neu["gemeldet"] == "2026-11-20"
    b = p.befund(wartung, neu, date(2026, 12, 1))
    assert b.angaben["datum"] == "2027-02-20"
    assert b.status == "hinweis"


def test_frist_am_monatsende(p):
    assert p._monate(date(2026, 11, 30), 3) == date(2027, 2, 28)
    assert p._monate(date(2026, 10, 15), 3) == date(2027, 1, 15)


def test_seit_service_jaehrlich(p):
    gas = p.PFLEGE[6][0]
    neu = p.fortschreiben({"rest": 1800.0}, 2.0, HEUTE, None, gas)
    assert neu["zuletzt"] == "2026-11-20"
    b = p.befund(gas, neu, HEUTE)
    assert b.angaben["datum"] == "2027-11-20"
    assert b.status == "unauffaellig"


def test_kalender_ohne_zuletzt_braucht_datum(p):
    asche = next(x for x in p.LOGWIN if x.art == "asche")
    assert p.befund(asche, {}, HEUTE).grund == "zuletzt"


def test_kalender_woechentlich_hinweis_erst_am_tag(p):
    asche = next(x for x in p.LOGWIN if x.art == "asche")
    assert p.befund(asche, {"zuletzt": "2026-11-15"}, HEUTE).status == "unauffaellig"
    assert p.befund(asche, {"zuletzt": "2026-11-13"}, HEUTE).status == "hinweis"


def test_letzte_erledigung_aus_statistik(p):
    reihe = [
        ("2026-09-01 10", 30.0),
        ("2026-09-01 11", 757.0),
        ("2026-10-02 08", 5.0),
        ("2026-10-02 09", 750.0),
        ("2026-10-03 09", 745.0),
    ]
    assert p.letzte_erledigung(reihe, zaehler(p), None) == "2026-10-02"
    assert p.letzte_erledigung([("2026-10-02 09", 750.0)], zaehler(p), None) is None


def test_kennung_des_terminsensors(p):
    assert p.befund_kennung("dev", "pflege_hauptreinigung") == "dev-befund-pflege-hauptreinigung"
    assert p.befund_kennung("dev", "laufzeit") is None
