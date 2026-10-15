"""Befunde zum Kessel: Starts und Laufzeit je Start, Energie je Heizgradtag."""

from __future__ import annotations

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def k():
    load_standalone("befund")
    return load_standalone("befund.kessel")


def reihe(n, monat=10, kwh=95.0, at=12.0, heiztag=True):
    """Je Tag ein Start und zwei Betriebsstunden."""
    return [
        {
            "datum": f"2026-{monat:02d}-{i + 1:02d}",
            "starts": 1001.0 + i,
            "bh": 5002.0 + 2 * i,
            "kwh": kwh,
            "at": at,
            "heiztag": heiztag,
        }
        for i in range(n)
    ]


def test_laufzeit_aus_zaehlerdeltas(k):
    befund = k.laufzeit(reihe(10), zaehler=(6585.0, 18201.0))
    assert befund.wert == pytest.approx(2.0)
    assert befund.angaben["starts_tag"] == pytest.approx(1.0)
    assert befund.angaben["gesamt_h_je_start"] == pytest.approx(2.76, abs=0.01)
    assert befund.status == "unauffaellig"


def test_laufzeit_uebergeht_zaehlersprung(k):
    tage = reihe(10)
    tage[5]["starts"] = 5.0
    befund = k.laufzeit(tage, zaehler=None)
    assert befund.wert == pytest.approx(2.0)
    assert befund.angaben["starts"] == 7


def test_laufzeit_ohne_zaehler(k):
    assert k.laufzeit([], zaehler=None).status == "braucht_daten"


def test_energie_zieht_den_sockel_ab(k):
    sommer = reihe(20, monat=8, kwh=20.0, at=22.0, heiztag=False)
    winter = reihe(10, monat=11, kwh=120.0, at=10.0)
    befund = k.energie(sommer + winter, grenze=15.0, heizgrenze=17.0)
    assert befund.wert == pytest.approx(10.0)
    assert befund.angaben["sockel"] == pytest.approx(20.0)
    assert befund.stufe == "vorlaeufig"


def test_energie_ohne_sockel_sammelt(k):
    befund = k.energie(reihe(10, kwh=120.0, at=10.0), grenze=15.0, heizgrenze=17.0)
    assert befund.status == "sammelt"


def test_energie_ohne_kwh_braucht_daten(k):
    tage = [t | {"kwh": None} for t in reihe(5)]
    assert k.energie(tage, grenze=15.0, heizgrenze=None).status == "braucht_daten"


def test_energie_gerade_je_kelvin(k):
    tage = []
    for i in range(30):
        at = 15.0 - i * 0.4
        tage.append(
            {"datum": f"2026-11-{i + 1:02d}", "at": at, "kwh": 200 - 10 * at, "heiztag": True}
        )
    punkte = k.energie(tage, grenze=15.0, heizgrenze=17.0).angaben
    assert punkte["gerade"] == pytest.approx(10.0)


def test_wochenpunkte_ueberspringen_luecken(k):
    tage = reihe(20, monat=11, kwh=120.0, at=10.0)
    del tage[8:12]
    punkte = k.energie(tage, grenze=15.0, heizgrenze=17.0).angaben["punkte"]
    assert len(punkte) == 2


def vergleichsreihe(ohne: int, mit: int, offen: int = 0):
    """Ohne Eingriff zwei Starts am Tag, mit Eingriff einer; jeweils 10 Gradtage."""
    tage, starts, bh = [], 1000.0, 5000.0
    arten = [False] * ohne + [True] * mit + [None] * offen
    for i, eingriff in enumerate(arten):
        starts += 1 if eingriff else 2
        bh += 3
        tage.append(
            {
                "datum": f"2026-10-{i + 1:02d}",
                "starts": starts,
                "bh": bh,
                "at": 10.0,
                "heiztag": True,
                "eingriff": eingriff,
            }
        )
    return tage


def test_starts_je_gradtag_mit_und_ohne_automatik(k):
    befund = k.starts(vergleichsreihe(10, 10))
    assert befund.art == "starts"
    assert befund.wert == -50
    assert befund.einheit == "%"
    assert befund.status == "unauffaellig"
    assert befund.stufe == "vorlaeufig"
    assert befund.angaben["mit"]["tage"] == 10
    assert befund.angaben["ohne"]["starts_je_gt"] == pytest.approx(0.2)


def test_starts_ohne_tage_mit_eingriff_sammelt(k):
    befund = k.starts(vergleichsreihe(12, 0))
    assert befund.status == "sammelt"
    assert befund.wert is None


def test_starts_tage_ohne_angabe_zaehlen_nicht(k):
    befund = k.starts(vergleichsreihe(6, 6, offen=5))
    assert befund.angaben["mit"]["tage"] + befund.angaben["ohne"]["tage"] == 11
