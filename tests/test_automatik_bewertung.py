"""Bewertungen der Automatik: was gemessen wird und was entscheidet."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from .conftest import load_standalone

TZ = timezone(timedelta(hours=2))
MORGEN = datetime(2026, 9, 27, 9, 0, tzinfo=TZ)


@pytest.fixture(scope="module")
def mods():
    load_standalone("automatik")
    p = load_standalone("automatik.profile")
    return p, load_standalone("automatik.regel"), load_standalone("automatik.bewertung")


def lage(r, **felder):
    basis = {
        "jetzt": MORGEN,
        "at": 12.0,
        "at_gedaempft": 11.8,
        "soll": 21.0,
        "raeume": ((21.4, None),),
        "sonnenquote": 78.0,
        "mittel_heute": 12.0,
        "sonnenuntergang": MORGEN.replace(hour=18, minute=55),
        "fruehester_beginn": MORGEN.replace(hour=7, minute=12),
        "betriebswahl": 1,
        "grenze_steuerung": 17.0,
    }
    basis.update(felder)
    return r.Lage(**basis)


def test_sonnentag_traegt_beginn_sonne_und_raeume(mods):
    p, r, b = mods
    liste = b.bewerten(lage(r), r.Gedaechtnis(), p.werte(p.STANDARD), r.Zustand.SONNENTAG)
    kern = {x.name for x in liste if x.entscheidend}
    assert {"beginn", "sonne", "raeume", "programmwahl"} <= kern
    sonne = next(x for x in liste if x.name == "sonne")
    assert (sonne.wert, sonne.schwelle, sonne.einheit, sonne.erfuellt) == (78.0, 60.0, "%", True)


def test_heizpause_misst_mit_den_schwellen_der_regel(mods):
    p, r, b = mods
    w = p.werte(p.STANDARD)
    stand = lage(r, sonnenquote=70.0, raeume=((20.6, None),))
    liste = {x.name: x for x in b.bewerten(stand, r.Gedaechtnis(), w, r.Zustand.HEIZPAUSE)}
    assert (liste["sonne"].schwelle, liste["sonne"].erfuellt) == (w.sonnenquote + 20.0, False)
    assert (liste["raeume"].schwelle, liste["raeume"].erfuellt) == (-0.5, True)


def test_im_programm_entscheidet_die_erste_unerfuellte(mods):
    p, r, b = mods
    stand = lage(r, jetzt=MORGEN.replace(hour=5))
    liste = b.bewerten(stand, r.Gedaechtnis(), p.werte(p.STANDARD), r.Zustand.PROGRAMM)
    assert [x.name for x in liste if x.entscheidend] == ["beginn"]


def test_kern_liefert_nur_entscheidende_als_dict(mods):
    p, r, b = mods
    liste = b.bewerten(lage(r), r.Gedaechtnis(), p.werte(p.STANDARD), r.Zustand.SONNENTAG)
    kern = b.kern(liste)
    assert kern
    assert all(e["entscheidend"] for e in kern)


def test_ohne_programm_bewerten_die_raeume_keinen_frostschutz(mods):
    p, r, b = mods
    stand = lage(r, soll=4.9, betriebswahl=6)
    raeume = next(
        x
        for x in b.bewerten(stand, r.Gedaechtnis(), p.werte(p.STANDARD), r.Zustand.PROGRAMM)
        if x.name == "raeume"
    )
    assert (raeume.wert, raeume.erfuellt) == (None, False)


def test_im_nur_warmwasser_der_automatik_gilt_der_gemerkte_sollwert(mods):
    p, r, b = mods
    g = r.Gedaechtnis(saison=r.NUR_WW, saison_soll=21.0)
    stand = lage(r, soll=4.9, betriebswahl=6)
    raeume = next(
        x for x in b.bewerten(stand, g, p.werte(p.STANDARD), r.Zustand.NUR_WW) if x.name == "raeume"
    )
    assert raeume.wert == 0.4
