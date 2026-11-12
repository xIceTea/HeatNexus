"""Bewertung der Verbindung: Fenster, Regeln, Hysterese, Stunden und Bezug."""

from __future__ import annotations

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def vb():
    return load_standalone("verbindung")


def reihe(dauern, fehler=0, zeit=1000.0):
    """Einträge im Fenster: Dauern in ms, danach Fehlantworten."""
    return [(zeit, d) for d in dauern] + [(zeit, None)] * fehler


def test_fenster_ignoriert_alte_eintraege(vb):
    eintraege = [(0.0, 9999.0), *reihe([100.0] * 20, zeit=950.0)]
    f = vb.fenster(eintraege, jetzt=1000.0)
    assert f.antworten == 20
    assert f.median_ms == 100.0


def test_fenster_ohne_genug_antworten_hat_keinen_median(vb):
    f = vb.fenster(reihe([100.0] * 19, fehler=5), jetzt=1000.0)
    assert f.median_ms is None
    assert f.anfragen == 24
    assert f.fehlerquote == pytest.approx(5 / 24)


def test_zu_wenige_anfragen_ergeben_kein_urteil(vb):
    assert vb.regel(vb.Fenster(None, 10, 9), 100.0, 0) is None


def test_fehlerquote_ab_zwanzig_prozent_ist_gestoert(vb):
    f = vb.fenster(reihe([100.0] * 16, fehler=4), jetzt=1000.0)
    assert vb.regel(f, None, 0) == vb.GESTOERT


def test_gestoert_geht_vor_ueberlastet(vb):
    f = vb.fenster(reihe([100.0] * 16, fehler=4), jetzt=1000.0)
    assert vb.regel(f, 100.0, 9) == vb.GESTOERT


def test_liegengebliebene_werte_ueber_fuenf_abrufe_sind_ueberlastet(vb):
    f = vb.fenster(reihe([100.0] * 30), jetzt=1000.0)
    assert vb.regel(f, 100.0, 4) == vb.STABIL
    assert vb.regel(f, 100.0, 5) == vb.UEBERLASTET


def test_ohne_bezug_sammelt(vb):
    f = vb.fenster(reihe([900.0] * 30), jetzt=1000.0)
    assert vb.regel(f, None, 0) == vb.SAMMELT


def test_traege_braucht_faktor_und_abstand(vb):
    langsam = vb.fenster(reihe([400.0] * 30), jetzt=1000.0)
    assert vb.regel(langsam, 200.0, 0) == vb.TRAEGE
    # 80 ms Bezug: 1,5-fach, aber unter 150 ms Abstand bleibt stabil.
    klein = vb.fenster(reihe([200.0] * 30), jetzt=1000.0)
    assert vb.regel(klein, 80.0, 0) == vb.STABIL


def test_erster_zustand_gilt_sofort(vb):
    stand = vb.fortschreiben(vb.Stand(), vb.STABIL)
    assert stand.zustand == vb.STABIL
    assert not stand.erster


def test_wechsel_erst_nach_drei_bewertungen(vb):
    stand = vb.fortschreiben(vb.Stand(), vb.STABIL)
    for _ in range(2):
        stand = vb.fortschreiben(stand, vb.TRAEGE)
        assert stand.zustand == vb.STABIL
    stand = vb.fortschreiben(stand, vb.TRAEGE)
    assert stand.zustand == vb.TRAEGE


def test_unterbrochene_folge_beginnt_neu(vb):
    stand = vb.fortschreiben(vb.Stand(), vb.STABIL)
    stand = vb.fortschreiben(stand, vb.TRAEGE)
    stand = vb.fortschreiben(stand, vb.TRAEGE)
    stand = vb.fortschreiben(stand, vb.STABIL)
    stand = vb.fortschreiben(stand, vb.TRAEGE)
    assert stand.zustand == vb.STABIL
    assert stand.folge == 1


def test_kein_urteil_laesst_den_stand(vb):
    stand = vb.fortschreiben(vb.Stand(), vb.STABIL)
    assert vb.fortschreiben(stand, None) == stand


def test_stunde_gueltig_mit_genug_antworten_und_ruhigem_zustand(vb):
    gut = vb.stunde_abschliessen("2026-11-12T06", [100.0] * 60, ["stabil"] * 3)
    assert gut.gueltig and gut.median_ms == 100.0 and gut.antworten == 60
    zu_wenig = vb.stunde_abschliessen("2026-11-12T07", [100.0] * 59, ["stabil"])
    assert not zu_wenig.gueltig
    unruhig = vb.stunde_abschliessen("2026-11-12T08", [100.0] * 60, ["traege", "traege", "stabil"])
    assert not unruhig.gueltig


def test_leere_stunde_hat_keinen_median(vb):
    leer = vb.stunde_abschliessen("2026-11-12T06", [], [])
    assert leer.median_ms is None and not leer.gueltig


def test_bezug_ab_vierundzwanzig_gueltigen_stunden(vb):
    stunden = [vb.Stunde(f"k{i}", 100.0 + i, 60, True) for i in range(23)]
    assert vb.bezug(stunden) is None
    stunden.append(vb.Stunde("k23", 123.0, 60, True))
    stunden.append(vb.Stunde("k24", 9999.0, 60, False))
    assert vb.bezug(stunden) == pytest.approx(111.5)


def test_kuerzen_haelt_hundertachtundsechzig_stunden(vb):
    stunden = [vb.Stunde(f"k{i}", 100.0, 60, True) for i in range(168)]
    neu = vb.stunden_kuerzen(stunden, vb.Stunde("neu", 100.0, 60, True))
    assert len(neu) == 168
    assert neu[0].schluessel == "k1" and neu[-1].schluessel == "neu"
