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


MORGEN = datetime(2026, 10, 16, 9, 0, tzinfo=TZ)


@pytest.fixture(scope="module")
def r(p):
    return load_standalone("automatik.regel")


@pytest.fixture(scope="module")
def w(p):
    return p.werte(p.STANDARD)


def sonnentag(r, jetzt=MORGEN):
    g = r.Gedaechtnis(
        absenkung_art=r.SONNE,
        absenkung_von=jetzt,
        absenkung_bis=jetzt + timedelta(hours=5),
        absenkung_basis=21.0,
        absenkung_soll=19.5,
    )
    aktion = r.Aktion("absenken", soll=19.5, minuten=300)
    return r.Entscheidung(r.Zustand.SONNENTAG, (aktion,), "Sonne", g)


def programm(r, aktionen=()):
    return r.Entscheidung(r.Zustand.PROGRAMM, aktionen, "Programm", r.Gedaechtnis())


def lage(r, jetzt=MORGEN, **felder):
    return r.Lage(jetzt=jetzt, soll=21.0, **{"raeume": ((21.4, None),), **felder})


def test_beginn_braucht_drei_takte(d, r, w):
    verlauf = d.Verlauf()
    for n in (1, 2):
        e = d.stabilisieren(sonnentag(r), r.Gedaechtnis(), verlauf, lage(r), w, takt=True)
        assert e.entscheidung.aktionen == ()
        assert e.entscheidung.zustand == r.Zustand.PROGRAMM
        a = e.anstehend
        assert (a.zustand, a.zaehler, a.noetig) == (r.Zustand.SONNENTAG, n, 3)
        verlauf = e.verlauf
    e = d.stabilisieren(sonnentag(r), r.Gedaechtnis(), verlauf, lage(r), w, takt=True)
    assert e.entscheidung.zustand == r.Zustand.SONNENTAG
    assert e.anstehend is None
    assert e.verlauf.halten_bis == MORGEN + timedelta(minutes=60)


def test_laeufe_ausserhalb_des_takts_zaehlen_nicht(d, r, w):
    verlauf = d.Verlauf(kandidat=r.Zustand.SONNENTAG, zaehler=2)
    e = d.stabilisieren(sonnentag(r), r.Gedaechtnis(), verlauf, lage(r), w, takt=False)
    assert e.entscheidung.aktionen == ()
    assert e.verlauf == verlauf
    assert e.anstehend.zaehler == 2


def test_anderer_kandidat_beginnt_von_vorn(d, r, w):
    verlauf = d.Verlauf(kandidat=r.Zustand.HEIZPAUSE, zaehler=2)
    e = d.stabilisieren(sonnentag(r), r.Gedaechtnis(), verlauf, lage(r), w, takt=True)
    assert e.anstehend.zaehler == 1


def test_ende_braucht_sechs_takte_und_wartet_das_halten_ab(d, r, w):
    alt = sonnentag(r).gedaechtnis
    ende = programm(r, (r.Aktion("absenkung_ende"),))
    gehalten = d.Verlauf(halten_bis=MORGEN + timedelta(minutes=30))
    e = d.stabilisieren(ende, alt, gehalten, lage(r), w, takt=True)
    assert e.entscheidung.zustand == r.Zustand.SONNENTAG
    assert e.anstehend.halten_bis == MORGEN + timedelta(minutes=30)
    verlauf = d.Verlauf()
    for _ in range(5):
        e = d.stabilisieren(ende, alt, verlauf, lage(r), w, takt=True)
        verlauf = e.verlauf
    assert e.anstehend.zaehler == 5
    e = d.stabilisieren(ende, alt, verlauf, lage(r), w, takt=True)
    assert e.entscheidung.aktionen == ende.aktionen


@pytest.mark.parametrize("felder", [{"raeume": ((19.9, None),)}, {"ruhig": False}])
def test_kalte_raeume_und_fordernde_thermostate_beenden_sofort(d, r, w, felder):
    alt = sonnentag(r).gedaechtnis
    ende = programm(r, (r.Aktion("absenkung_ende"),))
    gehalten = d.Verlauf(halten_bis=MORGEN + timedelta(minutes=30))
    e = d.stabilisieren(ende, alt, gehalten, lage(r, **felder), w, takt=False)
    assert e.entscheidung.aktionen == ende.aktionen


def test_rueckkehr_aus_nur_warmwasser_bei_kuehlen_raeumen_gilt_sofort(d, r, w):
    alt = r.Gedaechtnis(saison=r.NUR_WW, saison_soll=21.0)
    zurueck = programm(r, (r.Aktion("zurueck"),))
    e = d.stabilisieren(zurueck, alt, d.Verlauf(), lage(r, raeume=((20.4, None),)), w, takt=False)
    assert e.entscheidung.aktionen == zurueck.aktionen


def test_sicherheit_wirkt_sofort(d, r, w):
    alt = sonnentag(r).gedaechtnis
    aktion = r.Aktion("absenkung_ende", sicherheit=True)
    sicher = r.Entscheidung(r.Zustand.SICHERHEIT, (aktion,), "kalt", r.Gedaechtnis())
    gehalten = d.Verlauf(halten_bis=MORGEN + timedelta(hours=1))
    e = d.stabilisieren(sicher, alt, gehalten, lage(r), w, takt=False)
    assert e.entscheidung is sicher


def test_verlaengern_geht_sofort(d, r, w):
    # Abgelaufen, aber das Gedächtnis kennt den Sonnentag noch: Verlängern ist kein neuer Beginn.
    alt = sonnentag(r, MORGEN - timedelta(hours=6)).gedaechtnis
    e = d.stabilisieren(sonnentag(r), alt, d.Verlauf(), lage(r), w, takt=False)
    assert e.entscheidung.zustand == r.Zustand.SONNENTAG
    assert e.entscheidung.aktionen


def test_bestaetigung_uebergeht_zaehler_und_halten(d, r, w):
    gehalten = d.Verlauf(halten_bis=MORGEN + timedelta(minutes=30))
    e = d.stabilisieren(
        sonnentag(r), r.Gedaechtnis(), gehalten, lage(r), w, takt=False, erzwingen=True
    )
    assert e.entscheidung.zustand == r.Zustand.SONNENTAG


def test_ohne_aktion_zaehlt_nichts(d, r, w):
    e = d.stabilisieren(programm(r), r.Gedaechtnis(), d.Verlauf(), lage(r), w, takt=True)
    assert e.anstehend is None
    assert e.entscheidung.begruendung == "Programm"


def test_anstehender_beginn_nennt_sich_in_der_begruendung(d, r, w):
    e = d.stabilisieren(sonnentag(r), r.Gedaechtnis(), d.Verlauf(), lage(r), w, takt=True)
    assert e.entscheidung.begruendung == "Sonnentag in Sicht (1 von 3): Sonne"


def test_ende_einer_stufe_des_hausmodells_gilt_sofort(d, r, w):
    from dataclasses import replace

    alt = replace(sonnentag(r).gedaechtnis, absenkung_anlass=r.ANLASS_MODELL)
    ende = programm(r, (r.Aktion("absenkung_ende"),))
    e = d.stabilisieren(ende, alt, d.Verlauf(), lage(r), w, takt=False)
    assert e.entscheidung.aktionen == ende.aktionen
