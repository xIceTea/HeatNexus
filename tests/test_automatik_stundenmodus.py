"""Modus je vergangener Stunde aus Vermerken und geschriebenen Eingriffen."""

from __future__ import annotations

from datetime import date, timedelta, timezone

import pytest

from .conftest import load_standalone

TZ = timezone(timedelta(hours=2))
TAG = date(2026, 9, 28)


@pytest.fixture(scope="module")
def m():
    load_standalone("automatik")
    return load_standalone("automatik.stundenmodus")


def eintrag(zeit: str, *werte: tuple[str, str], art: str = "geschrieben") -> dict:
    return {
        "zeit": f"2026-09-28T{zeit}:00+02:00",
        "art": art,
        "text": "",
        "werte": [list(w) for w in werte],
    }


PROTOKOLL = [
    eintrag("11:32", ("/2/10/0", "0"), ("/3/50/0", "6")),
    eintrag("07:30", ("/3/4/0", "21.0"), ("/2/10/0", "400")),
]


def test_luecke_uebernimmt_den_vorigen_vermerk(m):
    assert m.ergaenzen({12: "nur_ww"}, [], TAG, 15, 6, TZ) == {
        **{h: "programm" for h in range(12)},
        12: "nur_ww",
        13: "nur_ww",
        14: "nur_ww",
    }


def test_vor_dem_ersten_vermerk_zaehlt_das_protokoll(m):
    ergebnis = m.ergaenzen({12: "nur_ww"}, PROTOKOLL, TAG, 13, 6, TZ)
    assert [ergebnis[h] for h in range(6, 13)] == [
        "programm",
        "absenkung",
        "absenkung",
        "absenkung",
        "absenkung",
        "nur_ww",
        "nur_ww",
    ]


def test_beobachtete_eintraege_zaehlen_nicht(m):
    haette = [eintrag("07:30", ("/3/4/0", "21.0"), ("/2/10/0", "400"), art="haette")]
    assert m.ergaenzen({}, haette, TAG, 9, 6, TZ)[8] == "programm"


def test_absenkung_endet_mit_ihrer_dauer(m):
    kurz = [eintrag("07:30", ("/3/4/0", "21.0"), ("/2/10/0", "60"))]
    ergebnis = m.ergaenzen({}, kurz, TAG, 10, 6, TZ)
    assert (ergebnis[7], ergebnis[8], ergebnis[9]) == ("absenkung", "programm", "programm")


def test_betriebswahl_zurueck_ist_programm(m):
    zurueck = [*PROTOKOLL, eintrag("14:10", ("/3/50/0", "1"))]
    assert m.ergaenzen({}, zurueck, TAG, 15, 6, TZ)[14] == "programm"


def eintrag_am(datum: str, zeit: str, *werte: tuple[str, str], art: str = "geschrieben") -> dict:
    return {
        "zeit": f"{datum}T{zeit}:00+02:00",
        "art": art,
        "text": "",
        "werte": [list(w) for w in werte],
    }


def test_nur_ww_von_gestern_gilt_ueber_mitternacht(m):
    gestern = [eintrag_am("2026-09-27", "16:00", ("/3/50/0", "6"))]
    ergebnis = m.ergaenzen({}, gestern, TAG, 3, 6, TZ)
    assert [ergebnis[h] for h in range(3)] == ["nur_ww", "nur_ww", "nur_ww"]


def test_absenkung_von_gestern_endet_nach_mitternacht(m):
    gestern = [eintrag_am("2026-09-27", "23:50", ("/3/4/0", "21.0"), ("/2/10/0", "400"))]
    ergebnis = m.ergaenzen({}, gestern, TAG, 7, 6, TZ)
    assert [ergebnis[h] for h in range(7)] == [
        "absenkung",
        "absenkung",
        "absenkung",
        "absenkung",
        "absenkung",
        "absenkung",
        "programm",
    ]
