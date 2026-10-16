"""Regellauf: Ringpuffer der Läufe, nur bei Änderung."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from .conftest import load_standalone

TZ = timezone(timedelta(hours=2))
JETZT = datetime(2026, 10, 16, 9, 0, tzinfo=TZ)


@pytest.fixture(scope="module")
def rl():
    load_standalone("automatik")
    return load_standalone("automatik.regellauf")


def eintrag(zeit, kandidat="sonnentag", zaehler=1, erfuellt=True):
    return {
        "zeit": zeit.isoformat(),
        "kandidat": kandidat,
        "zustand": "programm",
        "zaehler": zaehler,
        "noetig": 3,
        "halten_bis": None,
        "ergebnis": "zaehlt",
        "bewertungen": [{"name": "sonne", "erfuellt": erfuellt, "wert": 78.0}],
    }


def test_gleicher_lauf_erzeugt_keine_zeile(rl):
    lauf = rl.Regellauf()
    assert lauf.eintragen(eintrag(JETZT)) is True
    assert lauf.eintragen(eintrag(JETZT + timedelta(minutes=5))) is False
    assert lauf.eintragen(eintrag(JETZT + timedelta(minutes=10), zaehler=2)) is True
    assert [e["zaehler"] for e in lauf.liste(JETZT + timedelta(minutes=10))] == [2, 1]


def test_nur_ein_wechsel_eines_hakens_zaehlt(rl):
    lauf = rl.Regellauf()
    lauf.eintragen(eintrag(JETZT))
    assert lauf.eintragen(eintrag(JETZT, erfuellt=False)) is True


def test_aelter_als_ein_tag_faellt_weg(rl):
    lauf = rl.Regellauf()
    lauf.eintragen(eintrag(JETZT - timedelta(hours=25)))
    lauf.eintragen(eintrag(JETZT, zaehler=2))
    assert len(lauf.liste(JETZT)) == 1


def test_hoechstens_dreihundert(rl):
    lauf = rl.Regellauf()
    for n in range(320):
        lauf.eintragen(eintrag(JETZT, zaehler=n))
    assert len(lauf.liste(JETZT)) == 300
