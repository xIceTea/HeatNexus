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
    assert schnell.grenze_versatz == traege.grenze_versatz == 0.0


def test_eigene_werte_ueberschreiben_und_werden_begrenzt(profile):
    w = profile.werte(profile.STANDARD, {"absenkung_k": "2,5", "grenze_versatz": 99, "budget": 2.6})
    assert w.absenkung_k == 1.5  # "2,5" ist keine Zahl im Python-Sinn
    assert w.grenze_versatz == 5.0
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


def test_prognose_anpassen_ist_abschaltbar(profile):
    assert profile.werte(profile.STANDARD).anpassen is True
    assert profile.werte(profile.STANDARD, {"anpassen": False}).anpassen is False


def test_nicht_endliche_eigene_werte_gelten_nicht(profile):
    w = profile.werte(profile.STANDARD, {"sonnenquote": "nan", "grenze_versatz": "inf"})
    assert w.sonnenquote == profile.VORGABEN[profile.STANDARD].sonnenquote
    assert w.grenze_versatz == profile.VORGABEN[profile.STANDARD].grenze_versatz


def test_eco_greift_frueher_ein(profile):
    basis = profile.werte(profile.SCHNELL)
    eco = profile.werte(profile.SCHNELL, ausrichtung=profile.ECO)
    assert eco.grenze_versatz == basis.grenze_versatz - 2
    assert eco.sonnenquote == basis.sonnenquote - 15
    assert eco.absenkung_k == basis.absenkung_k + 0.5
    assert eco.ruhe_h < basis.ruhe_h
    assert eco.stark is True
    assert eco.stark_k < basis.stark_k


def test_komfort_greift_spaeter_und_sanfter_ein(profile):
    basis = profile.werte(profile.STANDARD)
    komfort = profile.werte(profile.STANDARD, ausrichtung=profile.KOMFORT)
    assert komfort.grenze_versatz == basis.grenze_versatz + 1
    assert komfort.sonnenquote == basis.sonnenquote + 10
    assert komfort.absenkung_k == basis.absenkung_k - 0.5
    assert komfort.stark is False
    assert komfort.ruhe_h > basis.ruhe_h


def test_spielraum_folgt_der_ausrichtung(profile):
    assert profile.werte("schnell", {}, "eco").spielraum_k == 0.5
    assert profile.werte("schnell", {}, "komfort").spielraum_k == 0.0
    assert profile.werte("schnell", {}, "ausgewogen").spielraum_k == 0.2


def test_ausrichtung_bleibt_in_den_grenzen(profile):
    assert profile.werte(profile.SCHNELL, ausrichtung=profile.KOMFORT).absenkung_k == 0.5


def test_eigene_werte_gehen_der_ausrichtung_vor(profile):
    w = profile.werte(profile.SCHNELL, {"grenze_versatz": 0.5}, ausrichtung=profile.ECO)
    assert w.grenze_versatz == 0.5


def test_abweichungen_messen_gegen_die_ausrichtung(profile):
    eco = profile.werte(profile.SCHNELL, ausrichtung=profile.ECO)
    eigene = {"grenze_versatz": eco.grenze_versatz}
    assert profile.abweichungen(profile.SCHNELL, eigene, profile.ECO) == {}


def test_unbekannte_ausrichtung_gilt_als_ausgewogen(profile):
    assert profile.werte(profile.STANDARD, ausrichtung="gibt_es_nicht") == profile.werte(
        profile.STANDARD
    )
