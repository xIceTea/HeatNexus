"""Profile der Automatik: Vorgaben, Grenzen, eigene Werte."""

from __future__ import annotations

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def profile():
    load_standalone("automatik")
    return load_standalone("automatik.profile")


def test_heizflaechen_waehlen_das_profil(profile):
    assert profile.profil_fuer("heizkoerper") == profile.SCHNELL
    assert profile.profil_fuer("gemischt") == profile.STANDARD
    assert profile.profil_fuer("flaeche") == profile.TRAEGE
    assert profile.profil_fuer("unbekannt") == profile.STANDARD


def test_vorgaben_unterscheiden_sich_in_der_traegheit(profile):
    schnell = profile.werte(profile.SCHNELL)
    traege = profile.werte(profile.TRAEGE)
    assert schnell.tau_h < profile.werte(profile.STANDARD).tau_h < traege.tau_h
    assert schnell.nachpruefung == "11:00"
    assert traege.entscheidung == "05:00"
    assert schnell.heizgrenze == traege.heizgrenze == 17.0


def test_eigene_werte_ueberschreiben_und_werden_begrenzt(profile):
    w = profile.werte(profile.STANDARD, {"absenkung_k": "2,5", "heizgrenze": 99, "budget": 2.6})
    assert w.absenkung_k == 1.5  # "2,5" ist keine Zahl im Python-Sinn
    assert w.heizgrenze == 22.0
    assert w.budget == 3


def test_ungueltige_uhrzeit_bleibt_bei_der_vorgabe(profile):
    assert profile.werte(profile.STANDARD, {"entscheidung": "25:00"}).entscheidung == "07:00"
    assert profile.werte(profile.STANDARD, {"entscheidung": "6:5"}).entscheidung == "06:05"
    assert profile.werte(profile.SCHNELL, {"nachpruefung": ""}).nachpruefung == ""


def test_unbekannte_felder_werden_ignoriert(profile):
    assert profile.werte(profile.STANDARD, {"gibt_es_nicht": 1}) == profile.VORGABEN["standard"]


def test_wahrheitswert_ist_keine_zahl(profile):
    assert profile.werte(profile.STANDARD, {"budget": True}).budget == 4


def test_abweichungen_nennen_nur_geaenderte_felder(profile):
    assert profile.abweichungen(profile.STANDARD, {"absenkung_k": 2.0, "hysterese": 1.0}) == {
        "absenkung_k": 2.0
    }


def test_lernfenster_nur_drei_sieben_oder_vierzehn_tage(profile):
    assert profile.werte(profile.STANDARD).lernfenster == 14
    assert profile.werte(profile.STANDARD, {"lernfenster": 3}).lernfenster == 3
    assert profile.werte(profile.STANDARD, {"lernfenster": "7"}).lernfenster == 7
    assert profile.werte(profile.STANDARD, {"lernfenster": 5}).lernfenster == 14
