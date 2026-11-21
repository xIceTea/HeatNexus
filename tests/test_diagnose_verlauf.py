"""Tagesverlauf im Diagnoseexport: welche Datenpunkte hineingehören und wie er ausgedünnt wird."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from .conftest import load_standalone

BERLIN = ZoneInfo("Europe/Berlin")


@pytest.fixture(scope="module")
def verlauf():
    return load_standalone("diagnose_verlauf")


def _zeit(stunde: int, minute: int, sekunde: int = 0) -> datetime:
    return datetime(2026, 11, 15, stunde, minute, sekunde, tzinfo=UTC)


@pytest.mark.parametrize(
    ("typ", "einheit", "erwartet"),
    [
        ("binary_sensor", None, "wechsel"),
        ("select", None, "wechsel"),
        ("enum_sensor", None, "wechsel"),
        ("switch", None, "wechsel"),
        ("temperature", None, "raster"),
        ("temperature", "°C", "raster"),
        ("sensor", "%", "wechsel"),
        ("sensor", "min", None),
        ("sensor", "kWh", None),
        ("string_sensor", None, None),
        ("time", None, None),
        ("date", None, None),
        ("number", "°C", None),
    ],
)
def test_art_je_typ(verlauf, typ, einheit, erwartet):
    assert verlauf.art(typ, einheit) == erwartet


def test_die_auswahl_kommt_aus_den_beschreibungen(verlauf):
    beschreibungen = [
        {"id": "a", "type": "binary_sensor", "name": "Pufferladepumpe"},
        {"id": "b", "type": "temperature", "unit": None, "name": "Kesseltemperatur"},
        {"id": "c", "type": "string_sensor", "name": "Uhrzeit"},
        {"type": "select", "name": "ohne Kennung"},
    ]
    gewaehlt = verlauf.auswahl(beschreibungen)
    assert set(gewaehlt) == {"a", "b"}
    assert gewaehlt["a"]["bereich"] == "binary_sensor"
    assert gewaehlt["b"] == {
        "art": "raster",
        "bereich": "sensor",
        "einheit": "°C",
        "name": "Kesseltemperatur",
    }


def test_ein_wechsel_bleibt_auf_die_sekunde_genau(verlauf):
    reihe = [(_zeit(5, 0), "off"), (_zeit(5, 41, 7), "on"), (_zeit(5, 44, 30), "off")]
    assert verlauf.ausduennen(reihe, "wechsel", BERLIN) == [
        ["2026-11-15T06:00:00+01:00", "off"],
        ["2026-11-15T06:41:07+01:00", "on"],
        ["2026-11-15T06:44:30+01:00", "off"],
    ]


def test_wiederholte_werte_fallen_weg(verlauf):
    reihe = [(_zeit(6, 0), "0"), (_zeit(6, 1), "0"), (_zeit(6, 2), "30"), (_zeit(6, 3), "30")]
    assert [wert for _, wert in verlauf.ausduennen(reihe, "wechsel", UTC)] == ["0", "30"]


def test_im_raster_zaehlt_der_hoechste_wert_je_abschnitt(verlauf):
    reihe = [(_zeit(6, 1), "31.5"), (_zeit(6, 8), "31.0"), (_zeit(6, 12), "32.0")]
    assert verlauf.ausduennen(reihe, "raster", UTC) == [
        ["2026-11-15T06:00+00:00", "31.5"],
        ["2026-11-15T06:10+00:00", "32.0"],
    ]


def test_ein_kurzer_pumpenlauf_bleibt_im_raster_sichtbar(verlauf):
    reihe = [(_zeit(6, 0), "0"), (_zeit(6, 3), "40"), (_zeit(6, 6), "0")]
    assert verlauf.ausduennen(reihe, "raster", UTC) == [["2026-11-15T06:00+00:00", "40"]]


def test_ein_springender_wert_geht_ins_raster_und_behaelt_den_ganzen_tag(verlauf):
    beginn = _zeit(0, 0)
    reihe = [(beginn + timedelta(seconds=30 * i), str(i % 2)) for i in range(2880)]
    ergebnis = verlauf.ausduennen(reihe, "wechsel", UTC)
    assert len(ergebnis) <= verlauf.HOECHSTENS
    assert ergebnis[0][0] == "2026-11-15T00:00+00:00"


def test_die_doppelte_stunde_der_zeitumstellung_bleibt_getrennt(verlauf):
    # 25.10.2026: 02:05 MESZ und 02:05 MEZ liegen eine Stunde auseinander.
    erste = datetime(2026, 10, 25, 0, 5, tzinfo=UTC)
    reihe = [(erste, "40.0"), (erste + timedelta(hours=1), "50.0")]
    ergebnis = verlauf.ausduennen(reihe, "raster", BERLIN)
    assert ergebnis == [
        ["2026-10-25T02:00+02:00", "40.0"],
        ["2026-10-25T02:00+01:00", "50.0"],
    ]
