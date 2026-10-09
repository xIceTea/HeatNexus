"""Vorhersage: tiefste Stufe, die die Räume bis zum Horizont hält."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from .conftest import load_standalone

TZ = timezone(timedelta(hours=2))
START = datetime(2026, 10, 8, 8, 0, tzinfo=TZ)


@pytest.fixture(scope="module")
def v():
    load_standalone("automatik")
    load_standalone("automatik.hausmodell")
    return load_standalone("automatik.vorhersage")


@pytest.fixture(scope="module")
def modell():
    h = load_standalone("automatik.hausmodell")
    return h.Modell(40.0, 0.0, 0.6, 0.03, "vorlauf", 10, (0.2,))


def _tag(v, at, sonne, ziel=21.0, stunden=12):
    return [
        v.Stundeneingang(START + timedelta(hours=n), at, sonne, None, ziel) for n in range(stunden)
    ]


def test_sonniger_milder_tag_ergibt_heizpause(v, modell):
    e = v.waehlen(modell, 21.5, 40.0, _tag(v, 16.0, 0.6), 2.0, 0.2, START + timedelta(hours=12))
    assert e.stufe == v.PAUSE
    assert e.tiefst >= e.ziel_min


def test_kalter_trueber_tag_bleibt_im_programm(v, modell):
    e = v.waehlen(modell, 21.0, 40.0, _tag(v, 2.0, 0.0), 2.0, 0.2, START + timedelta(hours=12))
    assert e.stufe == v.PROGRAMM


@pytest.mark.parametrize(("spielraum", "stufe"), [(0.0, "programm"), (0.5, "pause")])
def test_spielraum_entscheidet_im_grenzfall(v, modell, spielraum, stufe):
    # Ohne Heizen fällt der Raum bis zum Horizont auf etwa 20,8 °C; bei Vorlauf 22 °C
    # heizt auch die Absenkung nicht mehr, so dass nur Pause oder Programm bleiben.
    e = v.waehlen(
        modell, 21.0, 22.0, _tag(v, 16.6, 0.15), 2.0, spielraum, START + timedelta(hours=12)
    )
    assert e.stufe == stufe


def test_modellfehler_macht_vorsichtiger(v):
    h = load_standalone("automatik.hausmodell")
    ungenau = h.Modell(40.0, 0.0, 0.6, 0.03, "vorlauf", 10, (0.45,))
    e = v.waehlen(ungenau, 21.0, 40.0, _tag(v, 12.0, 0.15), 2.0, 0.5, START + timedelta(hours=12))
    assert e.ziel_min == pytest.approx(21.0 - 0.5 + 0.45)


@pytest.mark.parametrize(
    ("gemessen", "erwartet", "zurueck"),
    [(21.0, 21.1, False), (20.5, 21.1, True), (20.7, None, True), (21.4, None, False)],
)
def test_rueckkehr(v, gemessen, erwartet, zurueck):
    assert v.rueckkehr_noetig(gemessen, erwartet, 21.0, 0.2, 0.2) is zurueck
