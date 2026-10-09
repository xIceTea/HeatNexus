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


def _erzeugt(h, tau=40.0, sonne=0.6, heiz=0.03, wind=0.0, tage=10, rauschen=0.02, heizt=True):
    zufall = random.Random(4)
    stunden, raum = [], 21.0
    for n in range(24 * tage):
        stunde = n % 24
        at = 10 + 6 * math.sin((stunde - 9) / 24 * 2 * math.pi)
        einstrahlung = max(0.0, math.sin((stunde - 7) / 12 * math.pi)) if 7 < stunde < 19 else 0.0
        w = 2 + 3 * zufall.random()
        vl = 40.0 if heizt and raum < 21.0 else 0.0
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


def _modell(h, fehler=(), bleibt=()):
    return h.Modell(40.0, 0.0, 0.6, 0.03, "vorlauf", 20, tuple(fehler), 0.0, tuple(bleibt))


@pytest.mark.parametrize(
    ("modell_fehler", "bleibt", "erwartet"),
    [
        (0.3, 0.5, True),
        (0.45, 0.5, False),
        (0.6, 1.0, False),
    ],
)
def test_freigabe_braucht_vergleichstage_und_klaren_vorsprung(h, modell_fehler, bleibt, erwartet):
    m = _modell(h, [modell_fehler] * 14, [bleibt] * 14)
    assert h.freigegeben(m) is erwartet


def test_freigabe_braucht_vierzehn_gleich_lange_reihen(h):
    assert not h.freigegeben(_modell(h, [0.3] * 13, [0.5] * 13))
    assert not h.freigegeben(_modell(h, [0.3] * 14, [0.5] * 13))
    assert not h.freigegeben(_modell(h, [0.3] * 13, [0.5] * 14))
    assert not h.freigegeben(None)


def test_speichern_und_laden(h):
    m = h.Modell(40.0, 0.05, 0.6, 0.03, "pumpe", 7, (0.2,))
    assert h.aus_dict(h.als_dict(m)) == m
    assert h.aus_dict({"auskuehlzeit_h": "x"}) is None


def test_tagesfehler_klein_beim_wahren_modell_gross_beim_falschen(h):
    stunden = _erzeugt(h, wind=0.08)
    m = h.lernen(stunden, "vorlauf", 10)
    tag = stunden[-24:]
    falsch = h.Modell(10.0, m.wind_je_ms, m.sonne_k_h, m.heizwirkung, "vorlauf", 10)
    assert h.tagesfehler(m, tag) < 0.3
    assert h.tagesfehler(falsch, tag) > 0.5


def test_tagesfehler_ueberbrueckt_luecken(h):
    stunden = _erzeugt(h)
    m = h.lernen(stunden, "vorlauf", 10)
    tag = stunden[-24:]
    s = tag[12]
    tag[12] = h.Stunde(s.raum, None, s.at, s.sonne, s.wind, s.heizen)
    assert h.tagesfehler(m, tag) < 0.3
    assert h.tagesfehler(m, tag[:8]) is None


def test_wind_kuehlt_schneller_aus(h):
    m = h.Modell(40.0, 0.08, 0.0, 0.0, "vorlauf", 10)
    windig = h.vorhersagen(m, 21.0, [(5.0, 0.0, 8.0, 0.0)] * 3)
    still = h.vorhersagen(m, 21.0, [(5.0, 0.0, 0.0, 0.0)] * 3)
    assert windig[-1] < still[-1]


def test_fehlender_wind_gilt_als_mittlerer_wind(h):
    m = h.Modell(40.0, 0.08, 0.0, 0.0, "vorlauf", 10, (), 4.0)
    ohne_angabe = h.schritt(m, 21.0, 5.0, 0.0, None, 0.0)
    assert ohne_angabe == pytest.approx(h.schritt(m, 21.0, 5.0, 0.0, 4.0, 0.0))
    assert ohne_angabe < h.schritt(m, 21.0, 5.0, 0.0, 0.0, 0.0)


def test_gelernter_mittelwind_stammt_aus_den_daten(h):
    m = h.lernen(_erzeugt(h, wind=0.08), "vorlauf", 10)
    assert m.wind_mittel == pytest.approx(3.5, rel=0.1)
    assert h.lernen(_erzeugt(h), "vorlauf", 10).wind_mittel == 0.0


def test_ohne_heizstunden_bleiben_auskuehlzeit_und_sonne_lernbar(h):
    m = h.lernen(_erzeugt(h, heizt=False), "vorlauf", 10)
    assert m is not None
    assert m.auskuehlzeit_h == pytest.approx(40.0, rel=0.15)
    assert m.sonne_k_h == pytest.approx(0.6, rel=0.15)
    assert m.heizwirkung == 0.0


@pytest.mark.parametrize("tau", [1000.0, 1.0])
def test_unplausible_auskuehlzeit_ergibt_kein_modell(h, tau):
    stunden = []
    for n in range(100):
        raum, at, sonne = 20.0 + (n % 5) * 0.3, 5.0 + (n % 7), (n % 3) * 0.5
        stunden.append(h.Stunde(raum, raum + (at - raum) / tau + 0.3 * sonne, at, sonne, None, 0.0))
    assert h.lernen(stunden, "vorlauf", 5) is None


@pytest.mark.parametrize(
    "aenderung",
    [
        {"auskuehlzeit_h": 0.0},
        {"auskuehlzeit_h": float("nan")},
        {"sonne_k_h": float("inf")},
        {"heiz_art": "kamin"},
        {"fehler": [float("nan")]},
    ],
)
def test_unsinnige_gespeicherte_werte_werden_verworfen(h, aenderung):
    roh = h.als_dict(h.Modell(40.0, 0.05, 0.6, 0.03, "pumpe", 7, (0.2,)))
    assert h.aus_dict({**roh, **aenderung}) is None


def test_alter_speicherstand_ohne_mittelwind_wird_gelesen(h):
    roh = h.als_dict(h.Modell(40.0, 0.05, 0.6, 0.03, "pumpe", 7))
    del roh["wind_mittel"]
    assert h.aus_dict(roh).wind_mittel == 0.0


def test_speichern_kappt_die_fehlerliste(h):
    m = h.Modell(40.0, 0.0, 0.6, 0.03, "vorlauf", 40, tuple(range(40)), 0.0, tuple(range(40)))
    d = h.als_dict(m)
    assert len(d["fehler"]) == 28
    assert len(d["fehler_bleibt"]) == 28
    assert len(h.aus_dict(d).fehler_bleibt) == 28


def test_fehler_bleibt_laeuft_rund_und_fehlt_in_altem_stand(h):
    m = h.Modell(40.0, 0.05, 0.6, 0.03, "pumpe", 7, (0.2,), 1.5, (0.4,))
    assert h.aus_dict(h.als_dict(m)) == m
    roh = h.als_dict(m)
    del roh["fehler_bleibt"]
    assert h.aus_dict(roh).fehler_bleibt == ()


@pytest.mark.parametrize("wert", [float("nan"), float("inf")])
def test_nicht_endliche_werte_in_fehler_bleibt_werden_verworfen(h, wert):
    roh = h.als_dict(h.Modell(40.0, 0.05, 0.6, 0.03, "pumpe", 7, (0.2,), 0.0, (0.4,)))
    assert h.aus_dict({**roh, "fehler_bleibt": [wert]}) is None


def test_ueberlaufende_zahl_im_speicherstand_ergibt_kein_modell(h):
    roh = h.als_dict(h.Modell(40.0, 0.05, 0.6, 0.03, "pumpe", 7))
    assert h.aus_dict({**roh, "tage": float("inf")}) is None


def test_negativer_sonnenanteil_entfaellt_statt_das_modell_zu_verwerfen(h):
    m = h.lernen(_erzeugt(h, sonne=-0.3), "vorlauf", 10)
    assert m is not None
    assert m.sonne_k_h == 0.0
    assert m.auskuehlzeit_h == pytest.approx(40.0, rel=0.15)
    assert m.heizwirkung == pytest.approx(0.03, rel=0.3)


def test_negative_heizwirkung_entfaellt_statt_das_modell_zu_verwerfen(h):
    m = h.lernen(_erzeugt(h, heiz=-0.001), "vorlauf", 10)
    assert m is not None
    assert m.heizwirkung == 0.0
    assert m.auskuehlzeit_h == pytest.approx(40.0, rel=0.15)
    assert m.sonne_k_h == pytest.approx(0.6, rel=0.15)


def test_tagesfehler_bleibt_misst_die_abweichung_vom_startwert(h):
    tag = [h.Stunde(20.0, 20.5, 10.0, 0.0, None, 0.0)] * 12
    assert h.tagesfehler_bleibt(tag) == pytest.approx(0.5)


def test_tagesfehler_bleibt_startet_nach_einer_luecke_neu(h):
    tag = [h.Stunde(20.0, 21.0, 10.0, 0.0, None, 0.0)] * 6
    tag.append(h.Stunde(21.0, None, 10.0, 0.0, None, 0.0))
    tag += [h.Stunde(30.0, 31.0, 10.0, 0.0, None, 0.0)] * 6
    # Ohne Neustart bliebe der Startwert 20 und der Fehler nach der Lücke wäre 11
    assert h.tagesfehler_bleibt(tag) == pytest.approx(1.0)


def test_tagesfehler_bleibt_braucht_zwoelf_stunden(h):
    tag = [h.Stunde(20.0, 20.5, 10.0, 0.0, None, 0.0)] * 11
    assert h.tagesfehler_bleibt(tag) is None
