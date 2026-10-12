"""Befunde zum Heizkreis: Räume am Ziel, Übergangszeit nachts, Vorlauf erreicht Soll."""

from __future__ import annotations

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def hk():
    load_standalone("befund")
    return load_standalone("befund.heizkreis")


def stunde(zeit, at=10.0, vl=45.0, vi=45.0, raeume=None, eingriff=False, soll=21.0):
    return {
        "zeit": zeit,
        "at": at,
        "vl": vl,
        "vi": vi,
        "soll": soll,
        "eingriff": eingriff,
        "raeume": raeume or {},
    }


def tagesstunden(datum, raum_ist, ziel=21.0, at=10.0):
    raum = {"climate.a": [raum_ist, ziel]}
    return [stunde(f"{datum} {h:02d}", at=at, raeume=raum) for h in range(6, 22)]


def test_raeume_anteile_je_raum(hk):
    stunden = []
    for d in range(1, 8):
        stunden += tagesstunden(f"2026-10-{d:02d}", 21.2)
        stunden += [stunde(f"2026-10-{d:02d} 22", raeume={"climate.a": [22.5, 21.0]})]
    befund = hk.raeume(stunden, grenze=17.0)[0]
    werte = befund.angaben["je_raum"]["climate.a"]
    assert werte["am"] + werte["ueber"] == 100
    assert werte["ueber"] == 6  # 7 von 119 Stunden
    assert befund.status == "unauffaellig"
    assert befund.stufe == "belastbar"


def test_raeume_hinweis_ab_15_prozent_darueber(hk):
    stunden = []
    for d in range(1, 8):
        stunden += tagesstunden(f"2026-10-{d:02d}", 21.0)[:12]
        stunden += tagesstunden(f"2026-10-{d:02d}", 22.3)[12:]
    assert hk.raeume(stunden, grenze=17.0)[0].status == "hinweis"


def test_raeume_ohne_heizen_und_nach_eingriff_zaehlen_nicht(hk):
    kalt = {"climate.a": [18.0, 21.0]}
    stunden = [
        stunde("2026-10-01 10", vl=0.0, raeume=kalt),
        stunde("2026-10-01 11", eingriff=True, raeume=kalt),
        stunde("2026-10-01 12", raeume=kalt),
        stunde("2026-10-01 14", raeume={"climate.a": [21.0, 21.0]}),
    ]
    werte = hk.raeume(stunden, grenze=17.0)[0].angaben["je_raum"]["climate.a"]
    assert werte["stunden"] == 1
    assert werte["am"] == 100


def test_raeume_ohne_ziel_nimmt_das_raumsoll(hk):
    stunden = [stunde("2026-10-01 10", raeume={"sensor.a": [21.2, None]}, soll=21.0)]
    werte = hk.raeume(stunden, grenze=17.0)[0].angaben["je_raum"]["sensor.a"]
    assert werte["am"] == 100


def test_raeume_ohne_raum_braucht_daten(hk):
    assert hk.raeume([stunde("2026-10-01 10")], grenze=17.0)[0].status == "braucht_daten"


def test_naechte_vor_dem_anstieg(hk):
    stunden = []
    for d in range(1, 9):
        datum = f"2026-10-{d:02d}"
        nacht = {"climate.a": [20.3, 20.0]}
        stunden += [stunde(f"{datum} {h:02d}", at=11.0, raeume=nacht) for h in range(5)]
        stunden += [stunde(f"{datum} 05", at=11.0, raeume={"climate.a": [20.4, 22.5]})]
    befund = hk.naechte(stunden)
    assert befund.wert == pytest.approx(0.3)
    assert befund.status == "unauffaellig"
    assert len(befund.angaben["naechte"]) == 8


def test_naechte_ausserhalb_des_bands_sammeln(hk):
    raum = {"climate.a": [20.3, 20.0]}
    stunden = [stunde(f"2026-10-01 {h:02d}", at=-2.0, raeume=raum) for h in range(6)]
    assert hk.naechte(stunden).status == "sammelt"


def test_vorlauf_anteil_und_folge(hk):
    tage = [
        {"datum": f"2026-10-{d:02d}", "at": 12.0, "heizh": 20, "unter": int(d < 4), "folge": 1}
        for d in range(1, 11)
    ]
    befund = hk.vorlauf(tage)
    assert befund.wert == pytest.approx(1.5)
    assert befund.status == "unauffaellig"
    for t in tage[:3]:
        t |= {"unter": 4, "folge": 4}
    assert hk.vorlauf(tage).status == "hinweis"
