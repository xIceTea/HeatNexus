"""Entscheidungsregel der Automatik.

Geprüft wird vor allem, wann sie nicht eingreift: Ein falscher Eingriff heizt
zu wenig oder überschreibt eine Bedienung.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

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
    e = m.entscheiden(lage(m, at_gedaempft=18.2, mittel_heute=None), m.Gedaechtnis(), w)
    assert e.zustand == m.Zustand.NUR_WW
    assert [a.art for a in e.aktionen] == ["nur_ww"]
    assert e.gedaechtnis.saison_soll == 21.0


def test_milde_prognose_schaltet_nur_ww(m, w):
    e = m.entscheiden(lage(m, mittel_heute=17.5, mittel_morgen=17.0), m.Gedaechtnis(), w)
    assert [a.art for a in e.aktionen] == ["nur_ww"]


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
    warm = lage(m, jetzt=MORGEN + timedelta(hours=1), at_gedaempft=18.5, betriebswahl=3)
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
    e = m.entscheiden(lage(m, at_gedaempft=18.5, ruhig=True), m.Gedaechtnis(), w)
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
    stand = lage(m, at_gedaempft=18.5, raeume=(), aus=(19.0, 18.5))
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
