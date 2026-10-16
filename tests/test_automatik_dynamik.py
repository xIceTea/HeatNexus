"""Ruhe der Automatik: frühester Beginn, Zähler, Halten, sofortige Fälle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from .conftest import load_standalone

TZ = timezone(timedelta(hours=2))
NACHT = datetime(2026, 10, 16, 2, 0, tzinfo=TZ)
AUFGANG = datetime(2026, 10, 16, 7, 12, tzinfo=TZ)


@pytest.fixture(scope="module")
def p():
    load_standalone("automatik")
    return load_standalone("automatik.profile")


@pytest.fixture(scope="module")
def d(p):
    return load_standalone("automatik.dynamik")


@pytest.mark.parametrize(
    ("art", "erwartet"),
    [("aufgang", AUFGANG), ("uhrzeit", NACHT.replace(hour=7, minute=30)), ("aus", None)],
)
def test_fruehester_beginn_folgt_der_einstellung(d, p, art, erwartet):
    w = p.werte(p.STANDARD, {"beginn_art": art, "beginn_uhrzeit": "07:30"})
    assert d.fruehester_beginn(w, NACHT, AUFGANG) == erwartet


def test_ohne_sonnenaufgang_gilt_die_uhrzeit(d, p):
    assert d.fruehester_beginn(p.werte(p.STANDARD), NACHT, None) == NACHT.replace(hour=7, minute=0)
