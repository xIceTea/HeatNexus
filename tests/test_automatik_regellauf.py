"""Regellauf: Ringpuffer der Läufe, nur bei Änderung."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from .conftest import load_standalone

TZ = timezone(timedelta(hours=2))
JETZT = datetime(2026, 10, 16, 9, 0, tzinfo=TZ)


@pytest.fixture(scope="module")
def rl():
    load_standalone("automatik")
    return load_standalone("automatik.regellauf")


def eintrag(zeit, kandidat="sonnentag", zaehler=1, erfuellt=True):
    return {
        "zeit": zeit.isoformat(),
        "kandidat": kandidat,
        "zustand": "programm",
        "zaehler": zaehler,
        "noetig": 3,
        "halten_bis": None,
        "ergebnis": "zaehlt",
        "bewertungen": [{"name": "sonne", "erfuellt": erfuellt, "wert": 78.0}],
    }


def test_gleicher_lauf_erzeugt_keine_zeile(rl):
    lauf = rl.Regellauf()
    assert lauf.eintragen(eintrag(JETZT)) is True
    assert lauf.eintragen(eintrag(JETZT + timedelta(minutes=5))) is False
    assert lauf.eintragen(eintrag(JETZT + timedelta(minutes=10), zaehler=2)) is True
    assert [e["zaehler"] for e in lauf.liste(JETZT + timedelta(minutes=10))] == [2, 1]


def test_nur_ein_wechsel_eines_hakens_zaehlt(rl):
    lauf = rl.Regellauf()
    lauf.eintragen(eintrag(JETZT))
    assert lauf.eintragen(eintrag(JETZT, erfuellt=False)) is True


def test_zeile_behaelt_nur_entscheidende_und_gekippte_bewertungen(rl):
    lauf = rl.Regellauf()
    erste = eintrag(JETZT)
    erste["bewertungen"] = [
        {"name": "sonne", "erfuellt": True, "entscheidend": True},
        {"name": "raeume", "erfuellt": True, "entscheidend": False},
        {"name": "fenster", "erfuellt": True, "entscheidend": False},
    ]
    zweite = eintrag(JETZT + timedelta(minutes=5), zaehler=2)
    zweite["bewertungen"] = [
        {"name": "sonne", "erfuellt": True, "entscheidend": True},
        {"name": "raeume", "erfuellt": False, "entscheidend": False},
        {"name": "fenster", "erfuellt": True, "entscheidend": False},
    ]
    lauf.eintragen(erste)
    lauf.eintragen(zweite)
    neu, alt = lauf.liste(JETZT + timedelta(minutes=5))
    assert [b["name"] for b in neu["bewertungen"]] == ["sonne", "raeume"]
    assert [b["name"] for b in alt["bewertungen"]] == ["sonne"]


def test_liste_haelt_die_anzahl_ein(rl):
    lauf = rl.Regellauf()
    for n in range(5):
        lauf.eintragen(eintrag(JETZT, zaehler=n))
    assert [e["zaehler"] for e in lauf.liste(JETZT, 2)] == [4, 3]


def test_aelter_als_ein_tag_faellt_weg(rl):
    lauf = rl.Regellauf()
    lauf.eintragen(eintrag(JETZT - timedelta(hours=25)))
    lauf.eintragen(eintrag(JETZT, zaehler=2))
    assert len(lauf.liste(JETZT)) == 1


def test_hoechstens_dreihundert(rl):
    lauf = rl.Regellauf()
    for n in range(320):
        lauf.eintragen(eintrag(JETZT, zaehler=n))
    assert len(lauf.liste(JETZT)) == 300


def lauf_ohne_aktion(zeit, zustand, bewertungen, ergebnis="bleibt"):
    return {
        "zeit": zeit.isoformat(),
        "kandidat": zustand,
        "zustand": zustand,
        "zaehler": None,
        "noetig": None,
        "halten_bis": None,
        "ergebnis": ergebnis,
        "bewertungen": bewertungen,
    }


def test_zustandswechsel_ohne_aktion_heisst_wechselt(rl):
    lauf = rl.Regellauf()
    haken = [{"name": "beginn", "erfuellt": True, "entscheidend": True}]
    lauf.eintragen(lauf_ohne_aktion(JETZT, "sonnentag", haken, ergebnis="schreibt"))
    lauf.eintragen(lauf_ohne_aktion(JETZT + timedelta(minutes=5), "programm", haken))
    neu = lauf.liste(JETZT + timedelta(minutes=5))[0]
    assert (neu["ergebnis"], neu["vorher"]) == ("wechselt", "sonnentag")
    assert [b["name"] for b in neu["bewertungen"]] == ["beginn"]


def test_ohne_vorigen_lauf_oder_bei_fehlenden_daten_kein_wechsel(rl):
    lauf = rl.Regellauf()
    lauf.eintragen(lauf_ohne_aktion(JETZT, "keine_daten", []))
    lauf.eintragen(lauf_ohne_aktion(JETZT, "programm", [{"name": "x", "erfuellt": True}]))
    assert [e["ergebnis"] for e in lauf.liste(JETZT)] == ["bleibt", "bleibt"]


def test_ruhiger_lauf_zeigt_nur_gekippte_bewertungen(rl):
    lauf = rl.Regellauf()
    vorher = [
        {"name": "beginn", "erfuellt": True, "entscheidend": True},
        {"name": "vorrang", "erfuellt": True, "entscheidend": True},
    ]
    nachher = [dict(vorher[0]), {**vorher[1], "erfuellt": False}]
    lauf.eintragen(lauf_ohne_aktion(JETZT, "sonnentag", vorher, ergebnis="schreibt"))
    lauf.eintragen(lauf_ohne_aktion(JETZT + timedelta(minutes=5), "sonnentag", nachher))
    neu = lauf.liste(JETZT + timedelta(minutes=5))[0]
    assert [b["name"] for b in neu["bewertungen"]] == ["vorrang"]


def test_ruhiger_lauf_ohne_gekippte_bewertung_erzeugt_keine_zeile(rl):
    lauf = rl.Regellauf()
    haken = [{"name": "beginn", "erfuellt": True, "entscheidend": True}]
    lauf.eintragen(lauf_ohne_aktion(JETZT, "sonnentag", haken, ergebnis="schreibt"))
    assert (
        lauf.eintragen(lauf_ohne_aktion(JETZT + timedelta(minutes=5), "sonnentag", haken)) is False
    )
    assert len(lauf.liste(JETZT + timedelta(minutes=5))) == 1


def test_erster_ruhiger_lauf_nach_neustart_zeigt_die_entscheidenden(rl):
    lauf = rl.Regellauf()
    haken = [
        {"name": "beginn", "erfuellt": False, "entscheidend": True},
        {"name": "raeume", "erfuellt": True, "entscheidend": False},
    ]
    lauf.eintragen(lauf_ohne_aktion(JETZT, "programm", haken))
    assert [b["name"] for b in lauf.liste(JETZT)[0]["bewertungen"]] == ["beginn"]
