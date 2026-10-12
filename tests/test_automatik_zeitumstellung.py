"""Automatik über die Zeitumstellung: Dauern zählen in echten Minuten wie der Timer `2/10`."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from .conftest import load_standalone
from .test_automatik_regel import MILD, lage

BERLIN = ZoneInfo("Europe/Berlin")
# Mitternacht vor der Umstellung: im Herbst kommt eine Stunde dazu, im Frühjahr fehlt eine.
HERBST = datetime(2026, 10, 25, 0, 0, tzinfo=BERLIN)
FRUEHJAHR = datetime(2026, 3, 29, 0, 0, tzinfo=BERLIN)
UMSTELLUNGEN = pytest.mark.parametrize("start", [HERBST, FRUEHJAHR], ids=["herbst", "fruehjahr"])


@pytest.fixture(scope="module")
def m():
    load_standalone("automatik")
    load_standalone("automatik.profile")
    return load_standalone("automatik.regel")


@pytest.fixture(scope="module")
def w():
    return load_standalone("automatik.profile").werte("standard")


@pytest.fixture(scope="module")
def s(m):
    return load_standalone("automatik.steller")


@pytest.fixture(scope="module")
def vh():
    return load_standalone("automatik.vorhersage")


def _echt(start: datetime, minuten: float) -> datetime:
    """`minuten` echte Minuten nach `start`, in Ortszeit."""
    return (start.astimezone(UTC) + timedelta(minutes=minuten)).astimezone(BERLIN)


def _minuten(von: datetime, bis: datetime) -> float:
    return (bis.timestamp() - von.timestamp()) / 60


@UMSTELLUNGEN
def test_heizpause_endet_nach_echten_minuten(m, w, start):
    e = m.entscheiden(lage(m, **MILD, jetzt=start), m.Gedaechtnis(), w)

    assert [(a.art, a.minuten) for a in e.aktionen] == [("pause", 400)]
    assert _minuten(start, e.gedaechtnis.absenkung_bis) == 400


@UMSTELLUNGEN
def test_abwesenheit_endet_nach_echten_minuten(m, w, start):
    e = m.entscheiden(lage(m, jetzt=start, abwesend=True), m.Gedaechtnis(), w)

    assert [(a.art, a.minuten) for a in e.aktionen] == [("absenken", 400)]
    assert _minuten(start, e.gedaechtnis.absenkung_bis) == 400


@UMSTELLUNGEN
def test_vorausschau_rechnet_die_dauer_bis_zum_horizont_echt(m, w, vh, start):
    horizont = start.replace(hour=5)
    v = vh.Vorhersage("pause", horizont, 20.9, horizont, (), 20.8, 0.2, False)
    stand = lage(m, **MILD, jetzt=start, vorhersage=v, modell_freigegeben=True)

    e = m.entscheiden(stand, m.Gedaechtnis(), w)

    echt = _minuten(start, horizont)
    assert [(a.art, a.minuten) for a in e.aktionen] == [("pause", echt)]
    assert _minuten(start, e.gedaechtnis.absenkung_bis) == echt


@UMSTELLUNGEN
def test_verlaengerter_sonnentag_zaehlt_echte_minuten(m, w, start):
    ziel = start.replace(hour=5)
    g = m.Gedaechtnis(
        absenkung_art=m.SONNE,
        absenkung_von=start - timedelta(hours=1),
        absenkung_bis=start,
        absenkung_ziel=ziel,
        absenkung_basis=21.0,
        absenkung_soll=19.0,
    )
    e = m.entscheiden(lage(m, jetzt=start), g, w)

    echt = _minuten(start, ziel)
    assert [(a.art, a.minuten) for a in e.aktionen] == [("absenken", echt)]
    assert _minuten(start, e.gedaechtnis.absenkung_bis) == echt


@UMSTELLUNGEN
def test_restzeit_der_steuerung_gilt_ueber_die_umstellung(m, w, s, start):
    """Der Timer zählt echte Minuten; eine laufende Pause ist kein Handeingriff."""
    e = m.entscheiden(lage(m, **MILD, jetzt=start), m.Gedaechtnis(), w)
    steller = s.Steller("/1/15/0", [0, 1, 2, 3, 4, 5, 6, 7], None)

    for vergangen in (60, 200, 390):
        jetzt = _echt(start, vergangen)
        grund = steller.handeingriff(
            e.gedaechtnis,
            jetzt=jetzt,
            betriebswahl=None,
            rest_min=400 - vergangen,
            betriebsart=1,
            raumsoll=e.gedaechtnis.absenkung_soll,
        )
        assert grund is None, (vergangen, grund)


@UMSTELLUNGEN
def test_absenkung_laeuft_bis_zum_echten_ende(m, start):
    ende = _echt(start, 240)
    g = m.Gedaechtnis(absenkung_art=m.PAUSE, absenkung_von=start, absenkung_bis=ende)

    assert m.absenkung_laeuft(g, _echt(start, 239)) is True
    assert m.absenkung_laeuft(g, _echt(start, 240)) is False


def test_eine_gespeicherte_absenkung_gilt_gegen_die_ortszeit(m, s):
    """Aus dem Store kommt eine feste Verschiebung, `jetzt` trägt die Zone."""
    g = m.gedaechtnis_aus_dict(
        m.gedaechtnis_als_dict(
            replace(
                m.Gedaechtnis(),
                absenkung_art=m.PAUSE,
                absenkung_von=HERBST,
                absenkung_bis=_echt(HERBST, 400),
                absenkung_soll=17.0,
            )
        )
    )
    steller = s.Steller("/1/15/0", [0, 1, 2, 3, 4, 5, 6, 7], None)
    jetzt = _echt(HERBST, 60)

    assert (
        steller.handeingriff(
            g, jetzt=jetzt, betriebswahl=None, rest_min=340, betriebsart=1, raumsoll=17.0
        )
        is None
    )
