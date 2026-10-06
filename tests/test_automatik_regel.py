"""Entscheidungsregel der Automatik.

Geprüft wird vor allem, wann sie nicht eingreift: Ein falscher Eingriff heizt
zu wenig oder überschreibt eine Bedienung.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import random
import re

import pytest

from .conftest import load_standalone

TZ = timezone(timedelta(hours=2))
MORGEN = datetime(2026, 9, 27, 7, 0, tzinfo=TZ)
UNTERGANG = datetime(2026, 9, 27, 18, 55, tzinfo=TZ)


@pytest.fixture(scope="module")
def m():
    load_standalone("automatik")
    load_standalone("automatik.profile")
    return load_standalone("automatik.regel")


@pytest.fixture(scope="module")
def w():
    return load_standalone("automatik.profile").werte("standard")


def lage(m, **felder):
    basis = {
        "jetzt": MORGEN,
        "at": 12.0,
        "at_gedaempft": 11.8,
        "raum": 21.4,
        "soll": 21.0,
        "sonnenquote": 78.0,
        "mittel_heute": 12.0,
        "mittel_morgen": 10.0,
        "sonnenuntergang": UNTERGANG,
        "betriebswahl": 1,
        "grenze_steuerung": 17.0,
    }
    basis.update(felder)
    # Ein einzelner Raumwert steht für einen Raum ohne eigenes Ziel.
    raum = basis.pop("raum")
    basis.setdefault("raeume", () if raum is None else ((raum, None),))
    return m.Lage(**basis)


def sonnentag(m, **felder):
    return m.Gedaechtnis(
        absenkung_art=m.SONNE,
        absenkung_von=MORGEN,
        absenkung_bis=MORGEN + timedelta(hours=3),
        absenkung_basis=21.0,
        **felder,
    )


def nur_ww(m, seit: timedelta):
    return m.Gedaechtnis(saison=m.NUR_WW, saison_seit=MORGEN - seit, saison_soll=21.0)


# --- Sicherheit, Pause, Fenster, Daten -------------------------------------
def test_frost_holt_nur_ww_zurueck(m, w):
    e = m.entscheiden(lage(m, at=2.0, betriebswahl=6), nur_ww(m, timedelta(hours=1)), w)
    assert e.zustand == m.Zustand.SICHERHEIT
    assert [a.art for a in e.aktionen] == ["zurueck"]
    assert e.aktionen[0].sicherheit is True
    assert e.gedaechtnis.saison == m.HEIZEN


def test_kalter_raum_beendet_eine_laufende_absenkung(m, w):
    e = m.entscheiden(lage(m, jetzt=MORGEN + timedelta(hours=1), raum=15.5), sonnentag(m), w)
    assert [a.art for a in e.aktionen] == ["absenkung_ende"]
    assert e.aktionen[0].sicherheit is True


def test_frost_blockiert_keinen_sonnentag(m, w):
    """Eine befristete Absenkung um wenige Kelvin birgt kein Frostrisiko."""
    e = m.entscheiden(lage(m, at=1.0, entscheidungszeit=True), m.Gedaechtnis(), w)
    assert e.zustand == m.Zustand.SONNENTAG
    assert [a.art for a in e.aktionen] == ["absenken"]


def test_zwei_stunden_ohne_daten_in_nur_ww_fuehren_zurueck(m, w):
    stand = lage(m, daten_ok=False, raum=None, daten_fehlen_seit=MORGEN - timedelta(hours=2))
    e = m.entscheiden(stand, nur_ww(m, timedelta(days=1)), w)
    assert [a.art for a in e.aktionen] == ["zurueck"]


def test_pause_hat_vorrang_vor_allem_ausser_sicherheit(m, w):
    stand = lage(m, entscheidungszeit=True, pausiert_bis=MORGEN + timedelta(hours=22))
    e = m.entscheiden(stand, m.Gedaechtnis(), w)
    assert e.zustand == m.Zustand.PAUSIERT
    assert e.aktionen == ()
    assert "05:00" in e.begruendung


def test_offenes_fenster_friert_ein(m, w):
    alt = sonnentag(m)
    stand = lage(m, jetzt=MORGEN + timedelta(hours=1), raum=18.0, fenster_offen=True)
    e = m.entscheiden(stand, alt, w)
    assert e.zustand == m.Zustand.FENSTER
    assert e.aktionen == ()
    assert e.gedaechtnis == alt


def test_ohne_raumwert_keine_entscheidung(m, w):
    e = m.entscheiden(lage(m, raum=None, entscheidungszeit=True), m.Gedaechtnis(), w)
    assert e.zustand == m.Zustand.KEINE_DATEN
    assert e.aktionen == ()


# --- Saison ------------------------------------------------------------------
def test_warme_gedaempfte_at_schaltet_nur_ww(m, w):
    e = m.entscheiden(lage(m, at=17.5, at_gedaempft=18.2, mittel_heute=None), m.Gedaechtnis(), w)
    assert e.zustand == m.Zustand.NUR_WW
    assert [a.art for a in e.aktionen] == ["nur_ww"]
    assert e.gedaechtnis.saison_soll == 21.0


def test_milde_prognose_schaltet_nur_ww(m, w):
    e = m.entscheiden(lage(m, at=17.5, mittel_heute=17.5, mittel_morgen=17.0), m.Gedaechtnis(), w)
    assert [a.art for a in e.aktionen] == ["nur_ww"]


def test_kalte_nacht_in_der_prognose_verhindert_nur_ww(m, w):
    stand = lage(m, at=17.5, mittel_heute=17.5, mittel_morgen=17.0, minimum_bis_morgen=13.7)
    assert m.entscheiden(stand, m.Gedaechtnis(), w).aktionen == ()


def test_warme_nacht_in_der_prognose_erlaubt_nur_ww(m, w):
    stand = lage(m, at=17.5, mittel_heute=17.5, mittel_morgen=17.0, minimum_bis_morgen=16.2)
    assert [a.art for a in m.entscheiden(stand, m.Gedaechtnis(), w).aktionen] == ["nur_ww"]


def test_kalte_luft_jetzt_verhindert_nur_ww_trotz_gedaempfter_at(m, w):
    stand = lage(m, at=14.0, at_gedaempft=18.2, mittel_heute=None)
    assert m.entscheiden(stand, m.Gedaechtnis(), w).aktionen == ()


def test_nur_ww_merkt_seinen_grund(m, w):
    warm = m.entscheiden(lage(m, at=17.5, at_gedaempft=18.2, mittel_heute=None), m.Gedaechtnis(), w)
    mild = m.entscheiden(
        lage(m, at=17.5, mittel_heute=17.5, mittel_morgen=17.0), m.Gedaechtnis(), w
    )
    assert (warm.gedaechtnis.saison_grund, mild.gedaechtnis.saison_grund) == (
        "gedaempft",
        "prognose",
    )


def test_nur_ww_nach_prognose_nennt_die_prognose(m, w):
    g = replace(nur_ww(m, timedelta(hours=1)), saison_grund="prognose")
    e = m.entscheiden(
        lage(m, at_gedaempft=12.8, mittel_heute=17.5, mittel_morgen=17.0, betriebswahl=6), g, w
    )
    assert e.zustand == m.Zustand.NUR_WW
    assert "Prognose" in e.begruendung and "12,8" not in e.begruendung


def test_kuehler_raum_verhindert_nur_ww(m, w):
    e = m.entscheiden(lage(m, at_gedaempft=18.5, raum=20.3), m.Gedaechtnis(), w)
    assert e.aktionen == ()


def test_von_hand_gewaehlter_standby_bleibt(m, w):
    e = m.entscheiden(lage(m, at_gedaempft=18.5, betriebswahl=0), m.Gedaechtnis(), w)
    assert e.aktionen == ()


def test_hysterese_haelt_nur_ww_zwischen_den_schwellen(m, w):
    stand = lage(m, at_gedaempft=16.5, raum=20.2, betriebswahl=6)
    e = m.entscheiden(stand, nur_ww(m, timedelta(days=2)), w)
    assert e.zustand == m.Zustand.NUR_WW
    assert e.aktionen == ()


def test_kuehle_at_und_kuehler_raum_fuehren_zurueck(m, w):
    stand = lage(m, at_gedaempft=15.8, raum=20.4, betriebswahl=6)
    e = m.entscheiden(stand, nur_ww(m, timedelta(days=2)), w)
    assert [a.art for a in e.aktionen] == ["zurueck"]
    assert e.gedaechtnis.saison == m.HEIZEN


def test_mindestdauer_blockiert_die_rueckkehr(m, w):
    stand = lage(m, at_gedaempft=15.8, raum=20.4, betriebswahl=6)
    assert m.entscheiden(stand, nur_ww(m, timedelta(hours=3)), w).aktionen == ()


def test_zu_kalter_raum_kehrt_trotz_mindestdauer_zurueck(m, w):
    stand = lage(m, at_gedaempft=17.0, raum=19.9, betriebswahl=6)
    e = m.entscheiden(stand, nur_ww(m, timedelta(hours=3)), w)
    assert [a.art for a in e.aktionen] == ["zurueck"]


def _heizbedarf(m, **felder):
    basis = {
        "at": 16.7,
        "at_gedaempft": 16.4,
        "raeume": ((18.4, 19.0), (21.1, 21.5)),
        "ruhig": False,
        "betriebswahl": 6,
        "grenze_steuerung": 18.0,
    }
    basis.update(felder)
    return lage(m, raum=None, **basis)


def test_heizbedarf_unter_der_einschaltschwelle_holt_nur_ww_zurueck(m, w):
    e = m.entscheiden(_heizbedarf(m), nur_ww(m, timedelta(hours=3)), w)
    assert [a.art for a in e.aktionen] == ["zurueck"]
    assert "16,7" in e.begruendung and "17,0" in e.begruendung


def test_heizbedarf_ueber_der_einschaltschwelle_haelt_nur_ww(m, w):
    e = m.entscheiden(_heizbedarf(m, at=17.2), nur_ww(m, timedelta(hours=3)), w)
    assert e.aktionen == ()


def test_ruhige_thermostate_unter_der_einschaltschwelle_halten_nur_ww(m, w):
    e = m.entscheiden(_heizbedarf(m, ruhig=True), nur_ww(m, timedelta(hours=3)), w)
    assert e.aktionen == ()


def test_anforderung_bei_raeumen_ueber_ziel_haelt_nur_ww(m, w):
    stand = _heizbedarf(m, raeume=((19.2, 19.0), (21.6, 21.5)))
    assert m.entscheiden(stand, nur_ww(m, timedelta(hours=3)), w).aktionen == ()


def test_nur_ww_misst_gegen_den_gemerkten_sollwert(m, w):
    stand = lage(m, soll=5.0, raum=19.9, betriebswahl=6)
    e = m.entscheiden(stand, nur_ww(m, timedelta(hours=3)), w)
    assert [a.art for a in e.aktionen] == ["zurueck"]


# --- Sonnentag ---------------------------------------------------------------
def test_sonnentag_senkt_zur_entscheidungszeit_ab(m, w):
    e = m.entscheiden(lage(m, entscheidungszeit=True), m.Gedaechtnis(), w)
    assert e.zustand == m.Zustand.SONNENTAG
    (aktion,) = e.aktionen
    assert aktion.art == "absenken"
    assert aktion.soll == 19.5
    assert aktion.minuten == 400
    assert e.gedaechtnis.absenkung_ziel == UNTERGANG - timedelta(hours=2)
    assert "16:55" in e.begruendung


def test_ausserhalb_der_entscheidungszeit_keine_neue_absenkung(m, w):
    e = m.entscheiden(lage(m), m.Gedaechtnis(), w)
    assert e.zustand == m.Zustand.PROGRAMM
    assert e.aktionen == ()


def test_kurzer_resttag_gibt_kurze_absenkung(m, w):
    stand = lage(m, jetzt=datetime(2026, 9, 27, 15, 0, tzinfo=TZ), entscheidungszeit=True)
    (aktion,) = m.entscheiden(stand, m.Gedaechtnis(), w).aktionen
    assert aktion.minuten == 115


def test_zu_spaet_am_tag_keine_absenkung(m, w):
    stand = lage(m, jetzt=datetime(2026, 9, 27, 16, 30, tzinfo=TZ), entscheidungszeit=True)
    assert m.entscheiden(stand, m.Gedaechtnis(), w).aktionen == ()


def test_zu_wenig_sonne_keine_absenkung(m, w):
    e = m.entscheiden(lage(m, sonnenquote=45.0, entscheidungszeit=True), m.Gedaechtnis(), w)
    assert e.aktionen == ()
    assert "45 %" in e.begruendung


def test_kuehler_raum_keine_absenkung(m, w):
    e = m.entscheiden(lage(m, raum=20.6, entscheidungszeit=True), m.Gedaechtnis(), w)
    assert e.aktionen == ()


def test_absenkung_wird_einmal_verlaengert(m, w):
    start = m.entscheiden(lage(m, entscheidungszeit=True), m.Gedaechtnis(), w).gedaechtnis
    spaeter = MORGEN + timedelta(minutes=401)
    e = m.entscheiden(lage(m, jetzt=spaeter, raum=21.2, soll=19.5), start, w)
    (aktion,) = e.aktionen
    assert aktion.art == "absenken"
    assert aktion.soll == 19.5
    assert aktion.minuten == int((UNTERGANG - timedelta(hours=2) - spaeter).total_seconds() // 60)
    assert e.gedaechtnis.verlaengert is True
    noch_spaeter = spaeter + timedelta(minutes=aktion.minuten + 1)
    ende = m.entscheiden(lage(m, jetzt=noch_spaeter), e.gedaechtnis, w)
    assert ende.aktionen == ()
    assert ende.gedaechtnis.absenkung_art is None


def test_laufende_absenkung_nennt_das_geschriebene_ziel(m, w):
    start = m.entscheiden(lage(m, entscheidungszeit=True), m.Gedaechtnis(), w)
    (aktion,) = start.aktionen
    staerker = replace(w, absenkung_k=w.absenkung_k + 0.5)
    e = m.entscheiden(lage(m, jetzt=MORGEN + timedelta(hours=1)), start.gedaechtnis, staerker)
    assert e.aktionen == ()
    assert f"{aktion.soll:.1f}".replace(".", ",") in e.begruendung


def test_verlaengerung_merkt_das_neue_ziel(m, w):
    start = m.entscheiden(lage(m, entscheidungszeit=True), m.Gedaechtnis(), w).gedaechtnis
    spaeter = MORGEN + timedelta(minutes=401)
    e = m.entscheiden(lage(m, jetzt=spaeter, raum=21.2, soll=19.5), start, w)
    (aktion,) = e.aktionen
    assert e.gedaechtnis.absenkung_soll == aktion.soll


def test_gedaechtnis_ohne_geschriebenes_ziel_bleibt_lesbar(m):
    g = m.gedaechtnis_aus_dict({"absenkung_art": m.SONNE, "absenkung_basis": 21.0})
    assert g.absenkung_soll is None
    assert m.gedaechtnis_aus_dict(
        m.gedaechtnis_als_dict(replace(g, absenkung_soll=19.5))
    ) == replace(g, absenkung_soll=19.5)


def test_kuehler_raum_beendet_den_sonnentag(m, w):
    start = m.entscheiden(lage(m, entscheidungszeit=True), m.Gedaechtnis(), w).gedaechtnis
    stand = lage(m, jetzt=MORGEN + timedelta(hours=2), raum=20.1, soll=19.5)
    e = m.entscheiden(stand, start, w)
    assert [a.art for a in e.aktionen] == ["absenkung_ende"]
    assert e.gedaechtnis.absenkung_art is None


def test_starke_stufe_schaltet_nur_ww_bis_sonnenuntergang(m, w):
    stark = replace(w, stark=True)
    stand = lage(m, raum=22.2, sonnenquote=85.0, entscheidungszeit=True)
    e = m.entscheiden(stand, m.Gedaechtnis(), stark)
    assert [a.art for a in e.aktionen] == ["nur_ww"]
    assert e.gedaechtnis.stark_bis == UNTERGANG
    abend = m.entscheiden(lage(m, jetzt=UNTERGANG, raum=21.5, betriebswahl=6), e.gedaechtnis, stark)
    assert [a.art for a in abend.aktionen] == ["zurueck"]


# --- Abwesenheit -------------------------------------------------------------
def test_abwesenheit_senkt_ab_und_endet_bei_rueckkehr(m, w):
    weg = m.entscheiden(lage(m, abwesend=True), m.Gedaechtnis(), w)
    (aktion,) = weg.aktionen
    assert (aktion.art, aktion.soll, aktion.minuten) == ("absenken", 18.0, 400)
    stand = lage(m, jetzt=MORGEN + timedelta(hours=1), soll=18.0)
    zurueck = m.entscheiden(stand, weg.gedaechtnis, w)
    assert [a.art for a in zurueck.aktionen] == ["absenkung_ende"]


def test_laufende_abwesenheit_schreibt_nicht_erneut(m, w):
    weg = m.entscheiden(lage(m, abwesend=True), m.Gedaechtnis(), w).gedaechtnis
    stand = lage(m, jetzt=MORGEN + timedelta(hours=1), abwesend=True, soll=18.0)
    e = m.entscheiden(stand, weg, w)
    assert e.zustand == m.Zustand.ABWESEND
    assert e.aktionen == ()


# --- Speichern ---------------------------------------------------------------
def test_gedaechtnis_uebersteht_den_store(m, w):
    g = m.entscheiden(lage(m, entscheidungszeit=True), m.Gedaechtnis(), w).gedaechtnis
    assert m.gedaechtnis_aus_dict(m.gedaechtnis_als_dict(g)) == g


def test_kaputtes_gedaechtnis_wird_leer(m):
    assert m.gedaechtnis_aus_dict({"saison_seit": "kein datum", "unbekannt": 1}) == m.Gedaechtnis()
    assert m.gedaechtnis_aus_dict(None) == m.Gedaechtnis()


def test_wechsel_auf_nur_ww_beendet_laufende_absenkung(m, w):
    warm = lage(m, at=17.5, jetzt=MORGEN + timedelta(hours=1), at_gedaempft=18.5, betriebswahl=3)
    e = m.entscheiden(warm, sonnentag(m), w)
    assert e.zustand == m.Zustand.NUR_WW
    assert [a.art for a in e.aktionen] == ["absenkung_ende", "nur_ww"]


# --- Räume gegen ihr eigenes Ziel --------------------------------------------
def test_raeume_am_eigenen_ziel_erlauben_den_sonnentag(m, w):
    """Ohne Raumfühler am Heizkreis ist der Sollwert nur eine Verschiebung der Heizkurve."""
    stand = lage(
        m, raum=20.7, soll=22.0, raeume=((20.4, 20.5), (21.0, 21.0)), entscheidungszeit=True
    )
    e = m.entscheiden(stand, m.Gedaechtnis(), w)
    assert e.zustand == m.Zustand.SONNENTAG
    assert e.aktionen[0].soll == 20.5


def test_kaeltester_raum_zaehlt_gegen_sein_ziel(m, w):
    stand = lage(
        m,
        raum=20.0,
        soll=22.0,
        raeume=((22.0, 20.0), (19.0, 20.0)),
        raum_art="minimum",
        entscheidungszeit=True,
    )
    e = m.entscheiden(stand, m.Gedaechtnis(), w)
    assert e.aktionen == ()
    assert "−1,0 K" in e.begruendung


def test_raum_ohne_eigenes_ziel_misst_gegen_den_sollwert(m, w):
    stand = lage(m, raum=20.6, soll=21.0, raeume=((20.6, None),), entscheidungszeit=True)
    assert m.entscheiden(stand, m.Gedaechtnis(), w).aktionen == ()


def test_nur_ww_endet_wenn_ein_raum_unter_sein_ziel_faellt(m, w):
    stand = lage(m, raum=21.5, soll=22.0, raeume=((19.2, 20.5),), betriebswahl=6)
    e = m.entscheiden(stand, nur_ww(m, timedelta(hours=3)), w)
    assert [a.art for a in e.aktionen] == ["zurueck"]


def test_nur_ww_bleibt_wenn_die_raeume_ihr_ziel_halten(m, w):
    stand = lage(m, raum=20.4, soll=22.0, raeume=((20.4, 20.5),), betriebswahl=6)
    e = m.entscheiden(stand, nur_ww(m, timedelta(hours=3)), w)
    assert e.zustand == m.Zustand.NUR_WW
    assert e.aktionen == ()


def test_waermeanforderung_verhindert_nur_ww(m, w):
    stand = lage(m, at_gedaempft=18.5, ruhig=False)
    e = m.entscheiden(stand, m.Gedaechtnis(), w)
    assert e.aktionen == ()
    assert "fordern Wärme an" in e.begruendung


def test_ruhige_raeume_erlauben_nur_ww(m, w):
    e = m.entscheiden(lage(m, at=17.5, at_gedaempft=18.5, ruhig=True), m.Gedaechtnis(), w)
    assert [a.art for a in e.aktionen] == ["nur_ww"]


def test_ausgeschalteter_sonnentag_senkt_nicht_ab(m, w):
    e = m.entscheiden(lage(m, entscheidungszeit=True), m.Gedaechtnis(), replace(w, sonnentag=False))
    assert e.zustand == m.Zustand.PROGRAMM
    assert e.aktionen == ()


def test_ausschalten_beendet_einen_laufenden_sonnentag(m, w):
    stand = lage(m, jetzt=MORGEN + timedelta(hours=1), soll=19.5)
    e = m.entscheiden(stand, sonnentag(m), replace(w, sonnentag=False))
    assert [a.art for a in e.aktionen] == ["absenkung_ende"]
    assert e.gedaechtnis.absenkung_art is None


def test_waermeanforderung_verhindert_nur_ww_am_sehr_sonnigen_tag(m, w):
    stand = lage(m, raum=22.2, sonnenquote=85.0, entscheidungszeit=True, ruhig=False)
    e = m.entscheiden(stand, m.Gedaechtnis(), replace(w, stark=True))
    assert [a.art for a in e.aktionen] == ["absenken"]


def test_waermeanforderung_beendet_nur_ww_des_sonnentags(m, w):
    stark = replace(w, stark=True)
    start = m.entscheiden(
        lage(m, raum=22.2, sonnenquote=85.0, entscheidungszeit=True), m.Gedaechtnis(), stark
    )
    stand = lage(m, jetzt=MORGEN + timedelta(hours=2), raum=22.0, betriebswahl=6, ruhig=False)
    e = m.entscheiden(stand, start.gedaechtnis, stark)
    assert [a.art for a in e.aktionen] == ["zurueck"]


@pytest.mark.parametrize("betriebsart", [5, 6, 9, 10, 11])
def test_sonderbetrieb_der_steuerung_setzt_die_automatik_aus(m, w, betriebsart):
    """Estrich, Urlaub, Hand-, Test- und Kaminkehrerbetrieb laufen über `3/50` weiter im Programm."""
    stand = lage(m, entscheidungszeit=True, at_gedaempft=18.5, betriebsart=betriebsart)
    e = m.entscheiden(stand, m.Gedaechtnis(), w)
    assert e.zustand == m.Zustand.PAUSIERT
    assert e.aktionen == ()


def test_warmwasserladung_ist_kein_sonderbetrieb(m, w):
    e = m.entscheiden(lage(m, entscheidungszeit=True, betriebsart=3), m.Gedaechtnis(), w)
    assert e.zustand == m.Zustand.SONNENTAG


# --- Wärmequellen mit Vorrang vor dem Kessel -----------------------------------
def lange_absenkung(m):
    return replace(sonnentag(m), absenkung_bis=MORGEN + timedelta(hours=6))


def test_liefernde_vorrangquelle_bestaetigt_den_sonnentag(m, w):
    stand = lage(
        m, sonnenquote=40.0, entscheidungszeit=True, vorrang_laeuft=True, vorrang_name="Solaranlage"
    )
    e = m.entscheiden(stand, m.Gedaechtnis(), w)
    assert e.zustand == m.Zustand.SONNENTAG
    assert e.begruendung.startswith("Solaranlage liefert")


# --- Heizpause ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("at", "erwartet"),
    [
        (25.0, 17.0),  # Deckel: unten (16) + 1
        (17.9, 16.0),  # AT − 1,5 = 16,4, auf 0,5 abgerundet
        (16.9, 15.0),
        (6.0, 6.0),  # Untergrenze der Vorgabe
        (None, None),
    ],
)
def test_pause_soll_liegt_knapp_unter_der_at_der_steuerung(m, w, at, erwartet):
    # Grenze 17 (Steuerung), Hysterese 1 → Rückkehr unter 16.
    assert m.pause_soll(lage(m, at_steuerung=at), w) == erwartet


def pause(m, **felder):
    werte = {
        "absenkung_art": m.PAUSE,
        "absenkung_von": MORGEN,
        "absenkung_bis": MORGEN + timedelta(minutes=400),
        "absenkung_basis": 21.0,
        "absenkung_soll": 17.0,
    }
    werte.update(felder)
    return m.Gedaechtnis(**werte)


MILD = {"at": 18.5, "at_steuerung": 18.5, "mittel_heute": 17.5, "ruhig": True}


def test_milder_tag_beginnt_die_heizpause(m, w):
    e = m.entscheiden(lage(m, **MILD), m.Gedaechtnis(), w)
    assert e.zustand == m.Zustand.HEIZPAUSE
    assert [(a.art, a.soll, a.minuten) for a in e.aktionen] == [("pause", 17.0, 400)]
    assert e.gedaechtnis.absenkung_art == m.PAUSE
    assert e.gedaechtnis.saison == m.HEIZEN


@pytest.mark.parametrize(
    "abweichung",
    [
        {"at_steuerung": 17.0},  # unter unten + 1,5
        {"ruhig": False},
        {"raum": 20.4},  # 0,6 K unter Ziel
        {"betriebswahl": 0},
        {"absenkung_moeglich": False},
        {"mittel_heute": 12.0, "at_gedaempft": 11.8, "sonnenquote": 30.0},
    ],
)
def test_ohne_bedingung_keine_heizpause(m, w, abweichung):
    e = m.entscheiden(lage(m, **{**MILD, **abweichung}), m.Gedaechtnis(), w)
    assert all(a.art != "pause" for a in e.aktionen)


def test_nach_einer_beendeten_pause_heute_keine_neue(m, w):
    g = m.Gedaechtnis(pause_sperre=MORGEN.date().isoformat())
    e = m.entscheiden(lage(m, **MILD), g, w)
    assert all(a.art != "pause" for a in e.aktionen)


def test_laufende_pause_wartet(m, w):
    e = m.entscheiden(lage(m, **MILD, jetzt=MORGEN + timedelta(hours=1), vl_soll=0.0), pause(m), w)
    assert e.zustand == m.Zustand.HEIZPAUSE
    assert e.aktionen == ()


def test_pause_wird_kurz_vor_ablauf_erneuert(m, w):
    jetzt = MORGEN + timedelta(minutes=380)
    e = m.entscheiden(lage(m, **MILD, jetzt=jetzt, vl_soll=0.0), pause(m), w)
    assert [(a.art, a.minuten, a.erneuern) for a in e.aktionen] == [("pause", 400, True)]
    assert e.gedaechtnis.absenkung_bis == jetzt + timedelta(minutes=400)


def test_erneuern_senkt_den_sollwert_nie(m, w):
    jetzt = MORGEN + timedelta(minutes=380)
    felder = {**MILD, "at": 14.0, "at_steuerung": 14.0, "jetzt": jetzt}
    e = m.entscheiden(lage(m, **felder), pause(m), w)
    assert [(a.art, a.soll, a.erneuern) for a in e.aktionen] == [("pause", 17.0, True)]
    assert e.gedaechtnis.absenkung_soll == 17.0


def test_pause_rueckt_bei_steigender_at_nach(m, w):
    g = pause(m, absenkung_soll=12.0)
    e = m.entscheiden(lage(m, **MILD, jetzt=MORGEN + timedelta(hours=1)), g, w)
    assert [(a.art, a.soll, a.erneuern) for a in e.aktionen] == [("pause", 17.0, True)]


@pytest.mark.parametrize(
    "abweichung",
    [
        {"raum": 20.0},  # 1 K unter Ziel, rueckkehr_k 0,8
        {"ruhig": False},
        {"vl_soll": 35.0},  # Steuerung heizt wieder
    ],
)
def test_pause_endet(m, w, abweichung):
    jetzt = MORGEN + timedelta(hours=1)
    e = m.entscheiden(lage(m, **{**MILD, "jetzt": jetzt, **abweichung}), pause(m), w)
    assert [a.art for a in e.aktionen] == ["absenkung_ende"]
    assert e.gedaechtnis.absenkung_art is None
    assert e.gedaechtnis.pause_sperre == jetzt.date().isoformat()


def test_vorlauf_im_nachlauf_beendet_die_pause_nicht(m, w):
    jetzt = MORGEN + timedelta(minutes=5)
    e = m.entscheiden(lage(m, **MILD, jetzt=jetzt, vl_soll=42.0), pause(m), w)
    assert e.aktionen == ()


def test_kurzfassung_der_heizpause(m):
    assert m.kurz(m.Zustand.HEIZPAUSE, m.Gedaechtnis(absenkung_soll=16.5)) == "Heizpause · 16,5 °C"


def test_ende_des_starken_sonnentags_geht_in_die_heizpause(m, w):
    g = replace(nur_ww(m, timedelta(hours=1)), stark_bis=MORGEN + timedelta(hours=8))
    jetzt = MORGEN + timedelta(hours=9)
    e = m.entscheiden(lage(m, **MILD, jetzt=jetzt, betriebswahl=6), g, w)
    assert [a.art for a in e.aktionen] == ["zurueck", "pause"]
    assert e.zustand == m.Zustand.HEIZPAUSE
    assert e.gedaechtnis.saison == m.HEIZEN
    assert e.gedaechtnis.absenkung_art == m.PAUSE


def test_kalte_raeume_gehen_ohne_heizpause_ins_programm(m, w):
    e = m.entscheiden(
        lage(m, **{**MILD, "raum": 19.5}, betriebswahl=6), nur_ww(m, timedelta(hours=1)), w
    )
    assert [a.art for a in e.aktionen] == ["zurueck"]


def test_sicherheit_geht_nie_in_die_heizpause(m, w):
    e = m.entscheiden(
        lage(m, **{**MILD, "at": 2.0}, betriebswahl=6), nur_ww(m, timedelta(hours=1)), w
    )
    assert [a.art for a in e.aktionen] == ["zurueck"]


def test_vorrangtage_machen_einen_knapp_kuehlen_tag_mild(m, w):
    felder = {
        "at": 18.0,
        "at_steuerung": 18.0,
        "mittel_heute": 16.5,
        "mittel_morgen": 16.5,
        "minimum_bis_morgen": 16.5,
        "at_gedaempft": 15.0,
        "ruhig": True,
    }
    ohne = m.entscheiden(lage(m, **felder), m.Gedaechtnis(), w)
    mit = m.entscheiden(lage(m, **felder, vorrang_tage=2), m.Gedaechtnis(), w)
    assert "nur_ww" not in [a.art for a in ohne.aktionen]
    assert "nur_ww" in [a.art for a in mit.aktionen]


def test_vorrangquelle_ersetzt_eine_fehlende_sonnenquote(m, w):
    stand = lage(m, sonnenquote=None, entscheidungszeit=True, vorrang_laeuft=True)
    assert [a.art for a in m.entscheiden(stand, m.Gedaechtnis(), w).aktionen] == ["absenken"]


def test_ohne_waerme_der_vorrangquellen_endet_der_sonnentag_nach_vier_stunden(m, w):
    spaeter = MORGEN + timedelta(hours=4)
    stand = lage(m, jetzt=spaeter, soll=19.5, vorrang_laeuft=False, vorrang_minuten=5.0)
    e = m.entscheiden(stand, lange_absenkung(m), w)
    assert [a.art for a in e.aktionen] == ["absenkung_ende"]
    assert e.gedaechtnis.absenkung_art is None


def test_mit_waerme_der_vorrangquellen_laeuft_der_sonnentag_weiter(m, w):
    spaeter = MORGEN + timedelta(hours=4)
    stand = lage(m, jetzt=spaeter, soll=19.5, vorrang_laeuft=True, vorrang_minuten=60.0)
    assert m.entscheiden(stand, lange_absenkung(m), w).aktionen == ()


def test_vor_vier_stunden_zaehlt_fehlende_waerme_nicht(m, w):
    stand = lage(m, jetzt=MORGEN + timedelta(hours=2), soll=19.5, vorrang_minuten=0.0)
    assert m.entscheiden(stand, lange_absenkung(m), w).aktionen == ()


# --- Ausgeschaltete Thermostate -----------------------------------------------
def test_ausgeschaltete_raeume_sind_kein_fehlender_messwert(m, w):
    stand = lage(m, at=17.5, at_gedaempft=18.5, raeume=(), aus=(19.0, 18.5))
    e = m.entscheiden(stand, m.Gedaechtnis(), w)
    assert e.zustand == m.Zustand.NUR_WW
    assert stand.raum == 18.75


def test_ausgeschaltete_raeume_holen_nur_ww_nicht_zurueck(m, w):
    stand = lage(m, raeume=(), aus=(19.0,), betriebswahl=6)
    e = m.entscheiden(stand, nur_ww(m, timedelta(hours=3)), w)
    assert e.zustand == m.Zustand.NUR_WW
    assert e.aktionen == ()


def test_ausgeschalteter_raum_zaehlt_nicht_gegen_die_anderen(m, w):
    stand = lage(m, raeume=((21.0, 21.0),), aus=(15.0,), entscheidungszeit=True)
    assert m.abweichung(stand, 22.0) == 0.0


# --- Heizgrenze der Steuerung --------------------------------------------------
def test_hohe_heizgrenze_der_steuerung_haelt_den_heizkreis_im_programm(m, w):
    stand = lage(m, mittel_heute=19.0, mittel_morgen=19.0, grenze_steuerung=20.0)
    assert m.entscheiden(stand, m.Gedaechtnis(), w).aktionen == ()


def test_niedrige_heizgrenze_der_steuerung_erlaubt_nur_ww(m, w):
    stand = lage(m, at=17.5, mittel_heute=19.0, mittel_morgen=19.0, grenze_steuerung=18.0)
    e = m.entscheiden(stand, m.Gedaechtnis(), w)
    assert [a.art for a in e.aktionen] == ["nur_ww"]
    assert "18,0 °C" in e.begruendung


def test_ohne_heizgrenze_der_steuerung_gilt_der_rueckfall(m, w):
    stand = lage(m, grenze_steuerung=None)
    assert m.grenze(stand, w) == m.HEIZGRENZE_RUECKFALL == 17.0


@pytest.mark.parametrize("wert", [-5.0, 45.0])
def test_unplausible_heizgrenze_gilt_als_fehlend(m, w, wert):
    assert m.grenze(lage(m, grenze_steuerung=wert), w) == m.HEIZGRENZE_RUECKFALL


def test_versatz_der_ausrichtung_verschiebt_die_heizgrenze(m, w):
    eco = replace(w, grenze_versatz=-2.0)
    stand = lage(m, at=17.5, mittel_heute=16.5, mittel_morgen=16.5, grenze_steuerung=18.0)
    assert m.grenze(stand, eco) == 16.0
    assert [a.art for a in m.entscheiden(stand, m.Gedaechtnis(), eco).aktionen] == ["nur_ww"]


# Merkmale deutscher Sätze: Umlaute und häufige kurze Wörter.
DEUTSCH = re.compile(
    r"[äöüÄÖÜß]|\b(und|der|die|das|nicht|bis|von|mit|keine|seit|oder|für|zum|zur|Uhr|heute|"
    r"Raum|Räume|Außen|Absenkung|Programm|Warmwasser|Sonnentag|Prognose|Heizpause)\b"
)


def test_jede_begruendung_kommt_auf_englisch_an(m, w):
    """Ein festes Zufallsraster über Lage und Gedächtnis; kein Satz bleibt deutsch."""
    texte = load_standalone("texte")
    englisch = texte.Woerterbuch("en")
    zufall = random.Random(7)
    gedaechtnisse = [
        m.Gedaechtnis(),
        nur_ww(m, timedelta(hours=1)),
        nur_ww(m, timedelta(hours=30)),
        replace(nur_ww(m, timedelta(hours=1)), stark_bis=UNTERGANG),
        replace(nur_ww(m, timedelta(hours=1)), stark_bis=MORGEN),
        sonnentag(m),
        replace(sonnentag(m), absenkung_bis=MORGEN - timedelta(minutes=1)),
        m.Gedaechtnis(
            absenkung_art=m.ABWESEND,
            absenkung_von=MORGEN,
            absenkung_bis=MORGEN + timedelta(hours=6),
        ),
        pause(m),
        pause(m, absenkung_soll=12.0),
    ]
    reste = set()
    for _ in range(4000):
        felder = {
            "jetzt": MORGEN + timedelta(hours=zufall.choice([0, 3, 7, 11.5, 13])),
            "at": zufall.choice([None, 2.0, 12.0, 15.5, 16.5, 20.0]),
            "at_gedaempft": zufall.choice([None, 11.8, 16.0, 20.0]),
            "raum": zufall.choice([None, 15.0, 19.5, 20.6, 21.4, 22.2, 23.5]),
            "ruhig": zufall.choice([None, True, False]),
            "sonnenquote": zufall.choice([None, 30.0, 78.0, 95.0]),
            "mittel_heute": zufall.choice([None, 12.0, 19.0]),
            "betriebswahl": zufall.choice([None, 0, 1, 6]),
            "betriebsart": zufall.choice([None, 5]),
            "daten_ok": zufall.random() > 0.1,
            "daten_fehlen_seit": zufall.choice([None, MORGEN - timedelta(hours=3)]),
            "fenster_offen": zufall.random() < 0.1,
            "abwesend": zufall.random() < 0.1,
            "pausiert_bis": zufall.choice([None, None, MORGEN + timedelta(hours=2)]),
            "entscheidungszeit": zufall.random() < 0.5,
            "vorrang_laeuft": zufall.choice([None, True, False]),
            "vorrang_minuten": zufall.choice([None, 0.0, 120.0]),
            "vorrang_name": zufall.choice([None, "Solar"]),
            "at_steuerung": zufall.choice([None, 12.0, 17.0, 18.5, 22.0]),
            "vl_soll": zufall.choice([None, 0.0, 35.0]),
            "vorrang_tage": zufall.choice([None, 0, 2]),
        }
        e = m.entscheiden(lage(m, **felder), zufall.choice(gedaechtnisse), w)
        uebersetzt = englisch.satz(e.begruendung).replace("Solar", "")
        if DEUTSCH.search(uebersetzt):
            reste.add(e.begruendung)
    assert not reste, sorted(reste)


@pytest.mark.parametrize(
    ("zustand", "felder", "erwartet"),
    [
        ("SONNENTAG", {"absenkung_soll": 19.5}, "Sonnentag · 19,5 °C"),
        ("SONNENTAG", {}, "Sonnentag"),
        ("ABWESEND", {"absenkung_soll": 18.0}, "Abwesend · 18,0 °C"),
        ("NUR_WW", {}, "Nur Warmwasser"),
        ("PROGRAMM", {"absenkung_soll": 19.5}, None),
        ("AUS", {}, None),
    ],
)
def test_die_kurzfassung_nennt_zustand_und_geschriebenen_sollwert(m, zustand, felder, erwartet):
    assert m.kurz(m.Zustand[zustand], m.Gedaechtnis(**felder)) == erwartet


def test_die_kurzfassung_nennt_das_ende_der_pause(m):
    assert m.kurz(m.Zustand.PAUSIERT, m.Gedaechtnis(), MORGEN) == f"Pausiert bis {MORGEN:%H:%M}"


def test_jede_kurzfassung_kommt_auf_englisch_an(m):
    englisch = load_standalone("texte").Woerterbuch("en")
    gedaechtnis = m.Gedaechtnis(absenkung_soll=19.5)
    reste = {
        text
        for zustand in m.Zustand
        if (text := m.kurz(zustand, gedaechtnis, MORGEN)) and DEUTSCH.search(englisch.satz(text))
    }
    assert not reste, sorted(reste)


def test_programm_nennt_den_von_der_steuerung_ausgeschalteten_heizkreis(m, w):
    """Ohne Vorlauf-Soll heizt die Steuerung nicht; „heizt nach Programm“ wäre falsch."""
    felder = {"at": 17.6, "at_steuerung": 17.6, "vl_soll": 0.0, "ruhig": False}
    e = m.entscheiden(lage(m, **felder), m.Gedaechtnis(), w)
    assert e.zustand == m.Zustand.PROGRAMM
    assert e.begruendung == (
        "Kein Eingriff – die Steuerung hält den Heizkreis aus, AT 17,6 °C. "
        "Die Räume fordern Wärme an."
    )


def test_programm_mit_vorlauf_heizt(m, w):
    e = m.entscheiden(lage(m, vl_soll=42.0), m.Gedaechtnis(), w)
    assert e.begruendung.startswith("Heizt nach Programm")
