"""Hausmodell: lernt bekannte Hauswerte zurück und rechnet den Tag vor."""

from __future__ import annotations

import math
import random

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def h():
    load_standalone("automatik")
    return load_standalone("automatik.hausmodell")


def _erzeugt(h, tau=40.0, sonne=0.6, heiz=0.03, wind=0.0, tage=10, rauschen=0.02):
    zufall = random.Random(4)
    stunden, raum = [], 21.0
    for n in range(24 * tage):
        stunde = n % 24
        at = 10 + 6 * math.sin((stunde - 9) / 24 * 2 * math.pi)
        einstrahlung = max(0.0, math.sin((stunde - 7) / 12 * math.pi)) if 7 < stunde < 19 else 0.0
        w = 2 + 3 * zufall.random()
        vl = 40.0 if raum < 21.0 else 0.0
        heizen = max(0.0, vl - raum)
        neu = raum + (-(raum - at) * (1 + wind * w) / tau + sonne * einstrahlung + heiz * heizen)
        neu += zufall.gauss(0, rauschen)
        stunden.append(h.Stunde(raum, neu, at, einstrahlung, w, heizen))
        raum = neu
    return stunden


def test_lernen_findet_bekannte_hauswerte(h):
    m = h.lernen(_erzeugt(h), "vorlauf", 10)
    assert m.auskuehlzeit_h == pytest.approx(40.0, rel=0.15)
    assert m.sonne_k_h == pytest.approx(0.6, rel=0.15)
    assert m.heizwirkung == pytest.approx(0.03, rel=0.15)
    assert m.wind_je_ms == 0.0


def test_wind_bleibt_nur_wenn_er_erklaert(h):
    m = h.lernen(_erzeugt(h, wind=0.08), "vorlauf", 10)
    assert m.wind_je_ms == pytest.approx(0.08, rel=0.3)


def test_unsinnige_daten_ergeben_kein_modell(h):
    stunden = [h.Stunde(21.0, 21.0, 21.0, 0.0, None, 0.0)] * 50
    assert h.lernen(stunden, "vorlauf", 3) is None


def test_vorhersage_kuehlt_ohne_heizen_aus_und_waermt_mit_sonne(h):
    m = h.Modell(40.0, 0.0, 0.6, 0.03, "vorlauf", 10)
    kalt = h.vorhersagen(m, 21.0, [(5.0, 0.0, None, 0.0)] * 5)
    sonnig = h.vorhersagen(m, 21.0, [(5.0, 1.0, None, 0.0)] * 5)
    assert kalt[-1] < 21.0 < sonnig[-1]
    assert len(kalt) == 5


def test_freigabe_braucht_fuenf_tage_und_kleinen_fehler(h):
    gut = h.Modell(40.0, 0.0, 0.6, 0.03, "vorlauf", 5, (0.3, 0.4))
    assert h.freigegeben(gut)
    assert not h.freigegeben(h.Modell(40.0, 0.0, 0.6, 0.03, "vorlauf", 4, (0.3,)))
    assert not h.freigegeben(h.Modell(40.0, 0.0, 0.6, 0.03, "vorlauf", 9, (0.9, 0.8)))
    assert not h.freigegeben(None)


def test_speichern_und_laden(h):
    m = h.Modell(40.0, 0.05, 0.6, 0.03, "pumpe", 7, (0.2,))
    assert h.aus_dict(h.als_dict(m)) == m
    assert h.aus_dict({"auskuehlzeit_h": "x"}) is None
