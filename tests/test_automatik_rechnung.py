"""Rechnungen der Automatik ohne Home Assistant: Stundenwerte und Nachrechnen.

Geprüft werden die Stundenabfrage per Bisektion gegen die lineare Fassung, Zeitzonen und
Zeitumstellung beim Nachrechnen.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
import random
from zoneinfo import ZoneInfo

import pytest

from .conftest import load_standalone

BERLIN = ZoneInfo("Europe/Berlin")


@pytest.fixture(scope="module")
def eingaben():
    load_standalone("automatik")
    return load_standalone("automatik.eingaben")


@pytest.fixture(scope="module")
def n():
    load_standalone("automatik")
    return load_standalone("automatik.nachrechnen")


def zufallsreihe(zufall: random.Random, anfang: datetime, stunden: int) -> list:
    """Werte in unregelmäßigen Abständen, mit Lücken, doppelten Zeiten und `None`."""
    reihe, zeit = [], anfang - timedelta(minutes=zufall.randint(0, 90))
    ende = anfang + timedelta(hours=stunden)
    while zeit < ende:
        wert = None if zufall.random() < 0.1 else round(zufall.uniform(15, 25), 2)
        reihe.append((zeit, wert))
        if zufall.random() < 0.05:
            reihe.append((zeit, round(zufall.uniform(15, 25), 2)))
        sprung = zufall.choice([1, 5, 17, 30, 59, 60, 61, 120, 400])
        zeit += timedelta(minutes=sprung, seconds=zufall.randint(0, 59))
    return reihe


@pytest.mark.parametrize("saat", range(8))
def test_stundenreihe_gleicht_der_linearen_rechnung(eingaben, saat):
    zufall = random.Random(saat)
    anfang = datetime(2026, 10, 1, tzinfo=UTC)
    reihe = zufallsreihe(zufall, anfang, 72)
    schnell = eingaben.Stundenreihe(reihe)

    for h in range(-2, 75):
        stunde = anfang + timedelta(hours=h)
        assert schnell.mittel(stunde) == eingaben.mittel_der_stunde(reihe, stunde)
        assert schnell.zur_stunde(stunde) == eingaben.wert_zur_stunde(reihe, stunde)


def test_stundenreihe_ohne_werte(eingaben):
    leer = eingaben.Stundenreihe([])
    stunde = datetime(2026, 10, 1, tzinfo=UTC)
    assert leer.mittel(stunde) is None
    assert leer.zur_stunde(stunde) is None


def _leere_reihen(n, **felder):
    werte = {"at": [], "soll": [], "vl": [], "ba": [], "restzeit": [], "raeume": []}
    return n.Reihen(**{**werte, **felder}, raum_art="mittel")


def test_nur_die_behaglichkeit_mit_zone_ergibt_keinen_tag(n):
    tag = date(2026, 10, 5)
    behaglichkeit = [(datetime.combine(tag, time(0), BERLIN), 0.5)]

    assert n.stunden_je_tag(_leere_reihen(n, behaglichkeit=behaglichkeit), [tag]) == {}


def test_die_zone_des_aufrufers_gilt_ohne_reihen(n):
    tag = date(2026, 3, 29)
    behaglichkeit = [(datetime.combine(tag, time(0), BERLIN), 0.5)]
    reihen = _leere_reihen(n, behaglichkeit=behaglichkeit)

    assert n.stunden_je_tag(reihen, [tag], zone=BERLIN) == {}


def _ortszeit(utc: datetime) -> datetime:
    return utc.astimezone(BERLIN)


def _umstellungsreihen(n, tag: date):
    """Zu jeder halben Stunde in UTC ein Wert: AT steigt je halbe Stunde um 1."""
    anfang = datetime.combine(tag, time(0), BERLIN).astimezone(UTC) - timedelta(hours=1)
    zeiten = [anfang + timedelta(minutes=30 * i) for i in range(56)]
    at = [(_ortszeit(z), float(i)) for i, z in enumerate(zeiten)]
    return _leere_reihen(n, at=at)


def test_herbst_fuehrt_die_doppelte_stunde_einmal(n):
    tag = date(2026, 10, 25)
    stunden = n.stunden_je_tag(_umstellungsreihen(n, tag), [tag])[tag.isoformat()]

    assert sorted(stunden, key=int) == [str(h) for h in range(24)]
    # Die Reihe beginnt 21:00 UTC des Vortags mit 0; 02:00 Sommerzeit ist 00:00 UTC.
    assert stunden["2"]["at"] == 6.0
    # 03:00 Winterzeit ist 02:00 UTC: Die Stunde 2 umfasst beide Durchläufe.
    assert stunden["3"]["at"] == 10.0


def test_fruehling_laesst_die_fehlende_stunde_aus(n):
    tag = date(2026, 3, 29)
    stunden = n.stunden_je_tag(_umstellungsreihen(n, tag), [tag])[tag.isoformat()]

    assert "2" not in stunden
    assert len(stunden) == 23
    assert stunden["3"]["at"] == stunden["1"]["at"] + 2.0
