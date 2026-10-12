"""Archiv des Befunds: 5-Minuten-Werte zu Stunden, Stunden zu Tagen, Kürzen und Nachtragen."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def a():
    load_standalone("befund")
    return load_standalone("befund.archiv")


def werte(at=10.0, vl=45.0, vi=44.0, raum=21.0, ziel=21.0, eingriff=False):
    return {
        "at": at,
        "vl": vl,
        "vi": vi,
        "soll": 21.0,
        "eingriff": eingriff,
        "raeume": {"climate.a": [raum, ziel]},
    }


def test_stunde_entsteht_mit_der_naechsten(a):
    archiv = a.Archiv()
    t = datetime(2026, 10, 1, 10, 0)
    for m in range(0, 60, 5):
        archiv.messen("hk", t + timedelta(minutes=m), werte(at=10.0 + m / 60))
    assert archiv.stunden("hk") == []
    archiv.messen("hk", t + timedelta(hours=1), werte(eingriff=True))
    stunde = archiv.stunden("hk")[0]
    assert stunde["zeit"] == "2026-10-01 10"
    assert stunde["at"] == pytest.approx(10.46, abs=0.01)
    assert stunde["raeume"]["climate.a"] == [21.0, 21.0]
    assert stunde["eingriff"] is False


def test_tag_entsteht_mit_dem_naechsten(a):
    archiv = a.Archiv()
    t = datetime(2026, 10, 1, 0, 0)
    for h in range(25):
        heizt = 6 <= h < 22
        vi = 40.0 if h in (6, 7, 8, 12) else 45.0
        archiv.messen("hk", t + timedelta(hours=h), werte(vl=45.0 if heizt else 0.0, vi=vi))
    tag = archiv.tage_heizkreis("hk")[0]
    assert tag["datum"] == "2026-10-01"
    assert tag["heizh"] == 16
    assert tag["unter"] == 4
    assert tag["folge"] == 3


def test_kessel_zaehler_und_energie(a):
    archiv = a.Archiv()
    t = datetime(2026, 10, 1, 0, 0)
    for h in range(25):
        kw = 20.0 if 12 <= h < 14 else 0.0
        archiv.messen_kessel(
            "k", t + timedelta(hours=h), {"starts": 100.0 + (h >= 12), "bh": 50.0, "kw": kw}
        )
    tag = archiv.tage_kessel("k", {"2026-10-01": 11.0})[0]
    assert tag["starts"] == 101.0
    assert tag["kwh"] == pytest.approx(40.0)
    assert tag["at"] == 11.0


def test_speichern_und_laden(a):
    archiv = a.Archiv()
    archiv.messen("hk", datetime(2026, 10, 1, 10, 0), werte())
    archiv.messen("hk", datetime(2026, 10, 1, 11, 0), werte())
    archiv.nachgerechnet = 1
    wieder = a.Archiv.aus_dict(archiv.als_dict())
    assert wieder.stunden("hk") == archiv.stunden("hk")
    assert wieder.nachgerechnet == 1


def test_kuerzen_behaelt_tage(a):
    archiv = a.Archiv()
    t = datetime(2026, 1, 1, 0, 0)
    for h in range(25):
        archiv.messen("hk", t + timedelta(hours=h), werte())
    archiv.kuerzen(date(2026, 6, 1))
    assert archiv.stunden("hk") == []
    assert len(archiv.tage_heizkreis("hk")) == 1


def test_nachtragen_ueberschreibt_nicht(a):
    archiv = a.Archiv()
    archiv.messen("hk", datetime(2026, 10, 1, 10, 0), werte(at=5.0))
    archiv.messen("hk", datetime(2026, 10, 1, 11, 0), werte(at=5.0))
    neu = archiv.nachtragen("hk", {"2026-10-01 10": {"at": 9.0}, "2026-10-01 09": {"at": 8.0}})
    assert neu == 1
    assert [s["at"] for s in archiv.stunden("hk")] == [8.0, 5.0]


def test_nachtragen_bildet_vergangene_tage(a):
    archiv = a.Archiv()
    stunden = {f"2026-09-30 {h:02d}": {"at": 12.0, "vl": 40.0 if h > 5 else 0.0} for h in range(24)}
    archiv.nachtragen("hk", stunden)
    assert archiv.tage_heizkreis("hk")[0]["heizh"] == 18


@pytest.mark.parametrize("roh", [None, "x", {"stunden_hk": "x"}, {"stunden_hk": {"hk": [1]}}])
def test_kaputter_speicher_ergibt_leeres_archiv(a, roh):
    archiv = a.Archiv.aus_dict(roh)
    assert archiv.stunden("hk") == []
    assert archiv.nachgerechnet == 0
