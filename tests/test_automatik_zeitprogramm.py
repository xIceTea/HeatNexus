"""Zeitprogramme der Heizkreise lesen: Sollwert zur Zeit und Ende der Komfortzeit."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from .conftest import load_standalone

TZ = timezone(timedelta(hours=2))
P1 = [
    {
        "weekdays": ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"],
        "switchPoints": [
            {"time": "02:00", "value": 21},
            {"time": "05:00", "value": 22},
            {"time": "23:30", "value": 20.5},
        ],
    }
]
P3 = [
    {
        "weekdays": ["Mo", "Tu", "We", "Th", "Fr"],
        "switchPoints": [
            {"time": "06:00", "value": 20},
            {"time": "10:00", "value": 18},
            {"time": "19:00", "value": 20},
            {"time": "22:00", "value": 18},
        ],
    }
]


@pytest.fixture(scope="module")
def z():
    load_standalone("automatik")
    return load_standalone("automatik.zeitprogramm")


def test_sollwert_zur_zeit(z):
    donnerstag = datetime(2026, 10, 8, 3, 0, tzinfo=TZ)
    assert z.soll_um(P1, donnerstag) == 21
    assert z.soll_um(P1, donnerstag.replace(hour=1)) == 20.5  # Vortag gilt weiter
    assert z.soll_um(P1, donnerstag.replace(hour=12)) == 22


def test_horizont_ist_der_naechste_abfall(z):
    d = datetime(2026, 10, 8, 8, 0, tzinfo=TZ)
    assert z.horizont(P1, d) == d.replace(hour=23, minute=30)
    assert z.horizont(P3, d) == d.replace(hour=10, minute=0)


def test_ohne_programm_gilt_der_rueckfall(z):
    d = datetime(2026, 10, 8, 8, 0, tzinfo=TZ)
    assert z.horizont(None, d) == d.replace(hour=22, minute=0)
    assert z.horizont([{"weekdays": ["Sa"], "switchPoints": []}], d) == d.replace(hour=22)
