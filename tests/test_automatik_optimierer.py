"""Optimierungshinweise der Automatik.

Geprüft werden die Tageszusammenfassung und jede Regel, die aus ungestörten
Tagen einen Hinweis zu Heizkurve, Raumsollwert oder Vorhaltezeit ableitet.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest

from .conftest import load_standalone

HEUTE = "2027-03-01"
START = date(2026, 11, 1)


@pytest.fixture(scope="module")
def m():
    load_standalone("automatik")
    return load_standalone("automatik.optimierer")


def stunden_eines_tages(**abweichend):
    """Absenkung bis 5 Uhr, Heizbetrieb 6 bis 21 Uhr, ab 8 Uhr warm."""
    stunden = {}
    for h in range(24):
        heizen = 6 <= h <= 21
        stunden[str(h)] = {
            "aktion": "programm",
            "at": 2.0 if h % 2 else 4.0,
            "raum": 21.0,
            "ab": -1.0 if h < 8 else (-0.2 if h == 8 else 0.4),
            "soll": 22.0 if heizen else 18.0,
            "vl": 45.0,
            "ba": 1 if heizen else 2,
        }
    for h, felder in abweichend.items():
        stunden[h.lstrip("h")].update(felder)
    return stunden


def tag(m, i, at, ab, *, soll=21.0, morgen=None, ungestoert=True, stunden=24, sauber=None):
    datum = (START + timedelta(days=i)).isoformat()
    return m.Tag(datum, at, ab, soll, morgen, ungestoert, stunden, sauber=sauber)


def heiztag(gestoert, ab_gestoert=-2.0):
    """Heizbetrieb rund um die Uhr; `gestoert` sind Stunden mit Vorgabe."""
    stunden = {}
    for h in range(24):
        stunden[str(h)] = {"aktion": "programm", "at": 3.0, "ab": 0.5, "soll": 21.0, "ba": 1}
        if h in gestoert:
            stunden[str(h)].update(vorgabe=True, ab=ab_gestoert)
    return stunden


def reihe(m, anzahl, at, ab, *, ab_tag=0, **felder):
    return [tag(m, ab_tag + i, at, ab, **felder) for i in range(anzahl)]


def parameter(**werte):
    """Anfangsstand je Parameter; `p3_13=80` steht für `3/13`."""
    basis = {"p3_13": 80.0, "p3_1": 45.0, "p3_58": 0.0, "p3_6": 60.0, "p3_7": 0.0, "p3_101": None}
    basis.update(werte)
    return {k[1:].replace("_", "/"): [["2026-10-01", v]] for k, v in basis.items()}


def ohne_baender(**werte):
    """Parameterstand ohne Kurvenpunkte `3/1` und `3/13`, etwa bei einem DuoWIN."""
    p = parameter(**werte)
    del p["3/1"], p["3/13"]
    return p


def arten(liste):
    return [h.art for h in liste]


# --- Tageszusammenfassung -------------------------------------------------


def test_tag_fasst_heizbetrieb_zusammen(m):
    t = m.tag_aus_stunden("2026-11-03", stunden_eines_tages())
    assert t.datum == "2026-11-03"
    assert t.at == pytest.approx(3.0)
    # Heizbetrieb 6 bis 21 ohne die Aufheizstunden 6 und 7: eine −0,2, dreizehn +0,4.
    assert t.abweichung == pytest.approx((-0.2 + 13 * 0.4) / 14)
    assert t.soll == 22.0
    assert t.morgen_min == 120
    assert t.ungestoert is True
    assert t.stunden == 24


def test_soll_ist_median_der_heizstunden(m):
    stunden = stunden_eines_tages(h6={"soll": 30.0}, h7={"soll": 30.0}, h3={"soll": 30.0})
    assert m.tag_aus_stunden("2026-11-03", stunden).soll == 22.0


def test_abweichung_ohne_heizbetrieb_fehlt(m):
    stunden = stunden_eines_tages()
    for s in stunden.values():
        s["ba"] = 2
    t = m.tag_aus_stunden("2026-11-03", stunden)
    assert t.abweichung is None
    assert t.soll is None
    assert t.morgen_min is None
    assert t.stunden == 24


def test_andere_aktion_nimmt_die_stunde_und_die_erholung_heraus(m):
    for aktion in ("absenkung", "heizpause", "nur_ww"):
        stunden = stunden_eines_tages(
            h13={"aktion": aktion, "ab": 5.0}, h14={"ab": 5.0}, h15={"ab": 5.0}
        )
        t = m.tag_aus_stunden("2026-11-03", stunden)
        # Heizstunden 8 bis 21 ohne 13 und die zwei Erholungsstunden.
        assert t.sauber == 11
        assert t.abweichung == pytest.approx((-0.2 + 10 * 0.4) / 11)
        assert t.ungestoert is True


def test_vorgabe_des_nutzers_stoert_die_stunde(m):
    stunden = stunden_eines_tages(h19={"vorgabe": True})
    assert m.tag_aus_stunden("2026-11-03", stunden).sauber == 14 - 3


def test_vorgabe_am_tag_laesst_die_stunden_davor_und_danach_zaehlen(m):
    t = m.tag_aus_stunden("2026-11-03", heiztag(range(7, 17)))
    # 0 bis 6 und 19 bis 23; 17 und 18 sind Erholung.
    assert t.sauber == 12
    assert t.abweichung == pytest.approx(0.5)
    assert t.ungestoert is True
    assert t.stunden == 24


@pytest.mark.parametrize(("gestoert", "erwartet"), [(range(16), True), (range(17), False)])
def test_ungestoert_braucht_genug_saubere_stunden(m, gestoert, erwartet):
    t = m.tag_aus_stunden("2026-11-03", heiztag(gestoert))
    assert (t.sauber >= m.MIN_SAUBER) is erwartet
    assert t.ungestoert is erwartet


def test_ohne_saubere_stunde_keine_abweichung(m):
    t = m.tag_aus_stunden("2026-11-03", heiztag(range(24)))
    assert t.sauber == 0
    assert t.abweichung is None
    assert t.ungestoert is False


def test_saubere_stunde_braucht_eine_abweichung(m):
    stunden = heiztag(())
    for h in range(10):
        del stunden[str(h)]["ab"]
    assert m.tag_aus_stunden("2026-11-03", stunden).sauber == 14


@pytest.mark.parametrize("stunde", ["h5", "h6", "h7", "h8"])
def test_eingriff_im_aufheizen_verwirft_die_morgenzeit(m, stunde):
    stunden = stunden_eines_tages(**{stunde: {"aktion": "absenkung"}})
    assert m.tag_aus_stunden("2026-11-03", stunden).morgen_min is None


def test_eingriff_vor_dem_aufheizen_laesst_die_morgenzeit_stehen(m):
    stunden = stunden_eines_tages(h4={"vorgabe": True}, h9={"vorgabe": True})
    assert m.tag_aus_stunden("2026-11-03", stunden).morgen_min == 120


def test_im_beobachten_zaehlt_ein_geplanter_eingriff_nicht(m):
    stunden = stunden_eines_tages(h13={"aktion": "absenkung", "beobachtet": True})
    assert m.tag_aus_stunden("2026-11-03", stunden).ungestoert is True


def test_ohne_betriebsart_bestimmt_der_anstieg_des_sollwerts_den_morgen(m):
    stunden = stunden_eines_tages()
    for h in range(6):
        del stunden[str(h)]["ba"]
    assert m.tag_aus_stunden("2026-11-03", stunden).morgen_min == 120


def test_tag_ohne_aktion_bleibt_ungestoert(m):
    stunden = stunden_eines_tages()
    for s in stunden.values():
        del s["aktion"]
    assert m.tag_aus_stunden("2026-11-03", stunden).ungestoert is True


def test_morgen_sofort_warm_ergibt_null(m):
    stunden = stunden_eines_tages(h6={"ab": -0.3})
    assert m.tag_aus_stunden("2026-11-03", stunden).morgen_min == 0


def test_morgen_nie_warm_ergibt_keine_morgenzeit(m):
    stunden = stunden_eines_tages()
    for s in stunden.values():
        s["ab"] = -1.0
    assert m.tag_aus_stunden("2026-11-03", stunden).morgen_min is None


def test_morgen_zaehlt_nur_den_ersten_heizblock(m):
    # Erst im zweiten Heizblock warm; der erste endet um 10 Uhr.
    felder = {f"h{h}": {"ab": -1.0} for h in range(6, 22)}
    felder.update({"h11": {"ba": 2}, "h14": {"ab": 0.0}})
    stunden = stunden_eines_tages(**felder)
    assert m.tag_aus_stunden("2026-11-03", stunden).morgen_min is None


def test_heizbetrieb_ab_mitternacht_misst_ab_dem_anstieg_des_sollwerts(m):
    stunden = stunden_eines_tages()
    for s in stunden.values():
        s["ba"] = 1
    tag = m.tag_aus_stunden("2026-11-03", stunden)
    assert (tag.morgen_min, tag.morgen_quelle) == (120, "steuerung")


def test_ein_spaeterer_kleiner_anstieg_verdraengt_den_morgen_nicht(m):
    # Hauptanstieg um 6 Uhr, um 10 Uhr hebt ein Thermostat noch einmal um 0,5 K an.
    stunden = stunden_eines_tages()
    for h in range(10, 22):
        stunden[str(h)]["soll"] = 22.5
    assert m.tag_aus_stunden("2026-11-03", stunden).morgen_min == 120


def test_ohne_raumsoll_der_steuerung_gilt_sie_als_quelle(m):
    stunden = _thermostattag()
    del stunden["3"]["soll"]
    tag = m.tag_aus_stunden("2026-11-03", stunden)
    assert (tag.morgen_min, tag.morgen_quelle) == (120, "steuerung")


def test_warmwasserladung_am_morgen_unterbricht_die_messung_nicht(m):
    # Um 6 Uhr lädt der Kessel Warmwasser (Betriebsart 3); der Raum wird trotzdem um 8 Uhr warm.
    stunden = stunden_eines_tages(h6={"ba": 3})
    assert m.tag_aus_stunden("2026-11-03", stunden).morgen_min == 120


def test_absenkbetrieb_beendet_die_messung(m):
    stunden = stunden_eines_tages(h7={"ba": 2})
    assert m.tag_aus_stunden("2026-11-03", stunden).morgen_min is None


def test_ohne_anstieg_des_ziels_gibt_es_keinen_morgen(m):
    stunden = stunden_eines_tages()
    for s in stunden.values():
        s.update(ba=1, soll=22.0)
    assert m.tag_aus_stunden("2026-11-03", stunden).morgen_min is None


def _thermostattag(**abweichend):
    """Steuerung heizt durchgehend auf 22 °C; die Thermostate heben ihr Ziel um 4 Uhr auf 22,5 °C."""
    stunden = {}
    for h in range(24):
        stunden[str(h)] = {
            "aktion": "programm",
            "at": 3.0,
            "ba": 1,
            "soll": 21.0 if h < 1 or h >= 22 else 22.0,
            "ziel": 22.5 if 4 <= h < 22 else 21.0,
            "vl": 45.0,
            "ab": 0.2 if h < 4 else (-1.2 if h < 6 else 0.1),
        }
    for h, felder in abweichend.items():
        stunden[h.lstrip("h")].update(felder)
    return stunden


def test_morgen_beginnt_mit_dem_anstieg_des_ziels_der_thermostate(m):
    tag = m.tag_aus_stunden("2026-11-03", _thermostattag())
    assert (tag.morgen_min, tag.morgen_quelle) == (120, "raeume")


def test_hebt_die_steuerung_mit_an_gilt_ihr_programm(m):
    stunden = _thermostattag(h3={"soll": 20.0}, h4={"soll": 22.0})
    tag = m.tag_aus_stunden("2026-11-03", stunden)
    assert (tag.morgen_min, tag.morgen_quelle) == (120, "steuerung")


def test_der_morgen_ist_der_anstieg_auf_das_hoechste_ziel(m):
    # Kleine Stufe um 2 Uhr, das Tagesziel erst um 5 Uhr; warm um 6 Uhr.
    stunden = stunden_eines_tages()
    for h, s in stunden.items():
        s.update(ba=1, soll=20.5 if int(h) < 2 else (21.0 if int(h) < 5 else 22.0), ab=0.0)
    stunden["5"]["ab"] = -0.8
    assert m.tag_aus_stunden("2026-11-03", stunden).morgen_min == 60


def test_stunden_zaehlt_nur_stunden_mit_abweichung(m):
    stunden = {str(h): {"at": 5.0, "ab": 0.1, "ba": 1} for h in range(10)}
    stunden.update({str(h): {"at": 5.0, "ba": 1} for h in range(10, 24)})
    t = m.tag_aus_stunden("2026-11-03", stunden)
    assert t.stunden == 10
    assert t.at == 5.0


def test_tag_ohne_verwertbare_stunde_ist_none(m):
    assert m.tag_aus_stunden("2026-11-03", {}) is None
    assert m.tag_aus_stunden("2026-11-03", {"3": {"aktion": "programm"}, "4": None}) is None


# --- Grundlage ------------------------------------------------------------


def test_zu_wenige_tage_ergeben_keine_hinweise(m):
    tage = reihe(m, 6, -3.0, -1.4) + reihe(m, 6, 10.0, 1.0, ab_tag=6)
    assert m.hinweise(tage, parameter(), HEUTE) == []


def test_gestoerte_und_kurze_tage_zaehlen_nicht(m):
    tage = reihe(m, 6, -3.0, -1.4)
    tage.append(tag(m, 6, -3.0, -1.4, ungestoert=False))
    tage.append(tag(m, 7, -3.0, -1.4, stunden=m.MIN_STUNDEN - 1))
    assert m.hinweise(tage, parameter(), HEUTE) == []
    tage.append(tag(m, 8, -3.0, -1.4, stunden=m.MIN_STUNDEN))
    assert arten(m.hinweise(tage, parameter(), HEUTE)) == ["heizkurve_frost"]


def test_heute_und_spaeter_zaehlen_nicht(m):
    tage = reihe(m, 7, -3.0, -1.4)
    heute = tage[-1].datum
    assert m.hinweise(tage, parameter(), heute) == []
    assert m.hinweise(tage, parameter(), date.fromisoformat(heute) + timedelta(days=1))


def test_aenderung_setzt_grundlage_zurueck(m):
    p = parameter()
    p["3/13"].append(["2026-11-10", 84.0])
    vorher = reihe(m, 9, -3.0, -1.4)
    assert m.hinweise(vorher, p, HEUTE) == []
    # Der Tag der Änderung zählt nicht mit, erst die danach.
    nachher = reihe(m, 8, -3.0, -1.4, ab_tag=9)
    assert nachher[0].datum == "2026-11-10"
    (h,) = m.hinweise(vorher + nachher, p, HEUTE)
    assert h.art == "heizkurve_frost"
    assert h.seit == "2026-11-10"
    assert h.tage == 7
    assert h.von == 84.0


def test_seit_ist_juengste_aenderung_ueber_alle_parameter(m):
    p = parameter()
    p["3/13"].append(["2026-11-05", 84.0])
    p["3/1"].append(["2026-11-12", 43.0])
    p["3/1"].append(["2026-11-20", 44.0])
    tage = reihe(m, 7, -3.0, -1.4, ab_tag=20)
    (h,) = m.hinweise(tage, p, HEUTE)
    assert h.seit == "2026-11-20"
    assert h.tage == 7


def test_erster_eintrag_ist_keine_aenderung(m):
    p = parameter()
    p["3/13"] = [["2026-12-24", 80.0]]
    (h,) = m.hinweise(reihe(m, 7, -3.0, -1.4), p, HEUTE)
    assert h.seit is None


# --- Heizkurve ------------------------------------------------------------


def test_frost_zu_kalt_hebt_auslegung(m):
    # −1,4 K × 2,5 × 0,7 = −2,45 K, auf ganze Grad gerundet.
    (h,) = m.hinweise(reihe(m, 7, -3.0, -1.4), parameter(), HEUTE)
    assert h == m.Hinweis(
        art="heizkurve_frost",
        tage=7,
        seit=None,
        abweichung=-1.4,
        parameter="3/13",
        von=80.0,
        nach=82.0,
        einheit="°C",
    )


def test_frost_aenderung_hoechstens_zehn(m):
    (h,) = m.hinweise(reihe(m, 7, -3.0, -6.0), parameter(), HEUTE)
    assert h.nach == 90.0
    (h,) = m.hinweise(reihe(m, 7, -3.0, 8.0), parameter(), HEUTE)
    assert h.nach == 70.0


def test_frost_nur_unter_null(m):
    assert m.hinweise(reihe(m, 7, 0.0, -1.4), parameter(), HEUTE) == []


def test_uebergang_zu_warm_senkt_fusspunkt(m):
    (h,) = m.hinweise(reihe(m, 7, 10.0, 0.8), parameter(), HEUTE)
    assert (h.art, h.parameter, h.von, h.nach, h.einheit) == (
        "heizkurve_uebergang",
        "3/1",
        45.0,
        43.0,
        "°C",
    )


def test_uebergang_kleine_abweichung_aendert_ein_grad(m):
    # ±0,5 K × 3,5 × 0,7 = ±1,225 K.
    (h,) = m.hinweise(reihe(m, 7, 10.0, 0.5), parameter(), HEUTE)
    assert h.nach == 44.0
    (h,) = m.hinweise(reihe(m, 7, 10.0, -0.5), parameter(), HEUTE)
    assert h.nach == 46.0


@pytest.mark.parametrize(
    ("wert", "schritt", "erwartet"),
    [(1.5, 1.0, 2.0), (-1.5, 1.0, -2.0), (2.49, 1.0, 2.0), (0.25, 0.5, 0.5), (-0.75, 0.5, -1.0)],
)
def test_runden_halbe_weg_von_null(m, wert, schritt, erwartet):
    assert m._runden(wert, schritt) == erwartet


def test_uebergang_aenderung_hoechstens_zehn(m):
    (h,) = m.hinweise(reihe(m, 7, 10.0, 5.0), parameter(), HEUTE)
    assert h.nach == 35.0


def test_uebergang_grenzen_des_bands(m):
    assert arten(m.hinweise(reihe(m, 7, 5.0, 0.8), parameter(), HEUTE)) == ["heizkurve_uebergang"]
    assert arten(m.hinweise(reihe(m, 7, 15.0, 0.8), parameter(), HEUTE)) == ["heizkurve_uebergang"]
    assert m.hinweise(reihe(m, 7, 4.9, 0.8), parameter(), HEUTE) == []
    assert m.hinweise(reihe(m, 7, 15.1, 0.8), parameter(), HEUTE) == []


def test_kleine_abweichung_ergibt_keinen_hinweis(m):
    tage = reihe(m, 7, -3.0, -0.4) + reihe(m, 7, 10.0, 0.4, ab_tag=7)
    assert m.hinweise(tage, parameter(), HEUTE) == []


def test_tage_ohne_abweichung_oder_aussentemperatur_zaehlen_nicht(m):
    tage = reihe(m, 6, -3.0, -1.4)
    tage += [tag(m, 6, -3.0, None), tag(m, 7, None, -1.4)]
    assert m.hinweise(tage, parameter(), HEUTE) == []


def test_beide_baender_gleich_verschieben_behaglichkeit(m):
    tage = reihe(m, 7, -3.0, -1.0) + reihe(m, 7, 10.0, -0.8, ab_tag=7)
    (h,) = m.hinweise(tage, parameter(), HEUTE)
    assert (h.art, h.parameter, h.von, h.nach, h.einheit, h.tage) == (
        "heizkurve_parallel",
        "3/58",
        0.0,
        1.0,
        "K",
        14,
    )
    assert h.abweichung == pytest.approx(-0.9)


def test_parallel_rundet_auf_halbe_kelvin(m):
    tage = reihe(m, 7, -3.0, -0.8) + reihe(m, 7, 10.0, -0.6, ab_tag=7)
    (h,) = m.hinweise(tage, parameter(), HEUTE)
    assert h.nach == 0.5


def test_parallel_hoechstens_drei_kelvin(m):
    tage = reihe(m, 7, -3.0, -1.0) + reihe(m, 7, 10.0, -1.0, ab_tag=7)
    (h,) = m.hinweise(tage, parameter(p3_58=2.5), HEUTE)
    assert h.nach == 3.0
    tage = reihe(m, 7, -3.0, 2.0) + reihe(m, 7, 10.0, 2.0, ab_tag=7)
    (h,) = m.hinweise(tage, parameter(p3_58=-2.0), HEUTE)
    assert h.nach == -3.0


def test_parallel_am_anschlag_meldet_den_anschlag(m):
    tage = reihe(m, 7, -3.0, -1.0) + reihe(m, 7, 10.0, -1.0, ab_tag=7)
    (h,) = m.hinweise(tage, parameter(p3_58=3.0), HEUTE)
    assert h == m.Hinweis(
        art="heizkurve_parallel",
        tage=14,
        seit=None,
        abweichung=-1.0,
        parameter="3/58",
        von=3.0,
        einheit="K",
        anschlag=True,
    )


def test_verschiedene_vorzeichen_ergeben_zwei_baender(m):
    tage = reihe(m, 7, -3.0, -1.0) + reihe(m, 7, 10.0, 1.0, ab_tag=7)
    assert arten(m.hinweise(tage, parameter(), HEUTE)) == [
        "heizkurve_frost",
        "heizkurve_uebergang",
    ]


def test_grosser_unterschied_ergibt_zwei_baender(m):
    tage = reihe(m, 7, -3.0, -1.5) + reihe(m, 7, 10.0, -0.6, ab_tag=7)
    assert arten(m.hinweise(tage, parameter(), HEUTE)) == [
        "heizkurve_frost",
        "heizkurve_uebergang",
    ]


def test_ein_band_klein_ergibt_nur_das_andere(m):
    tage = reihe(m, 7, -3.0, -0.7) + reihe(m, 7, 10.0, -0.3, ab_tag=7)
    assert arten(m.hinweise(tage, parameter(), HEUTE)) == ["heizkurve_frost"]


def test_ohne_behaglichkeit_gelten_die_baender(m):
    gleich = reihe(m, 7, -3.0, -1.0) + reihe(m, 7, 10.0, -0.8, ab_tag=7)
    liste = m.hinweise(gleich, parameter(p3_58=None), HEUTE)
    assert [(h.art, h.parameter, h.nach) for h in liste] == [
        ("heizkurve_frost", "3/13", 82.0),
        ("heizkurve_uebergang", "3/1", 47.0),
    ]


def test_aktueller_wert_ist_letzter_eintrag(m):
    p = parameter()
    p["3/13"] += [["2026-10-05", 82.0], ["2026-10-06", None]]
    # Ohne gelesenen Wert für `3/13` gibt es nur die eine Kurve.
    assert arten(m.hinweise(reihe(m, 7, -3.0, -1.4), p, HEUTE)) == ["heizkurve_parallel"]
    p["3/13"].append(["2026-10-07", "84.0"])
    (h,) = m.hinweise(reihe(m, 7, -3.0, -1.4), p, HEUTE)
    assert h.von == 84.0


def test_steuerung_passt_an_unterdrueckt_kurvenhinweise(m):
    tage = reihe(m, 7, -3.0, -1.4) + reihe(m, 7, 10.0, 1.0, ab_tag=7)
    for p in (parameter(p3_7=2.0), parameter(p3_101=5.0)):
        (h,) = m.hinweise(tage, p, HEUTE, kreis=m.Kreis(raumfuehler=True))
        assert (h.art, h.tage, h.seit) == ("steuerung_passt_an", 14, None)


def test_kompensation_ohne_raumfuehler_laesst_die_kurvenhinweise(m):
    tage = reihe(m, 7, -3.0, -1.4, soll=None)
    assert arten(m.hinweise(tage, parameter(p3_7=2.0), HEUTE)) == ["heizkurve_frost"]
    assert set(richtungen(m.tendenzen(tage[:4], parameter(p3_7=2.0), HEUTE))) == {"kurve_frost"}
    (h,) = m.hinweise(tage, parameter(p3_101=5.0), HEUTE)
    assert h.art == "steuerung_passt_an"


# --- Eine Kurve ohne Kurvenpunkte -----------------------------------------


@pytest.mark.parametrize("fehlt", ["3/1", "3/13", "beide"])
def test_ohne_kurvenpunkte_eine_kurve_ueber_die_behaglichkeit(m, fehlt):
    p = ohne_baender() if fehlt == "beide" else parameter(**{f"p{fehlt.replace('/', '_')}": None})
    tage = reihe(m, 7, -3.0, -1.0) + reihe(m, 7, 10.0, -0.8, ab_tag=7)
    (h,) = m.hinweise(tage, p, HEUTE)
    assert (h.art, h.tage, h.parameter, h.von, h.nach, h.einheit) == (
        "heizkurve_parallel",
        14,
        "3/58",
        0.0,
        1.0,
        "K",
    )
    assert h.abweichung == pytest.approx(-0.9)


def test_eine_kurve_zaehlt_alle_tage_mit_abweichung(m):
    # Tage zwischen den Bändern und ohne Außentemperatur zählen mit.
    tage = reihe(m, 4, 2.0, 1.2) + reihe(m, 3, None, 1.2, ab_tag=4)
    tage.append(tag(m, 7, 2.0, None))
    (h,) = m.hinweise(tage, ohne_baender(p3_58=-1.0), HEUTE)
    assert (h.tage, h.abweichung, h.von, h.nach) == (7, 1.2, -1.0, -2.0)


def test_eine_kurve_grenzen(m):
    assert m.hinweise(reihe(m, 6, 2.0, -1.4), ohne_baender(), HEUTE) == []
    assert m.hinweise(reihe(m, 7, 2.0, -0.4), ohne_baender(), HEUTE) == []
    (h,) = m.hinweise(reihe(m, 7, 2.0, -5.0), ohne_baender(p3_58=1.0), HEUTE)
    assert h.nach == 3.0


def test_eine_kurve_am_anschlag_meldet_den_anschlag(m):
    (h,) = m.hinweise(reihe(m, 7, 2.0, -1.0), ohne_baender(p3_58=3.0), HEUTE)
    assert (h.art, h.parameter, h.von, h.nach, h.einheit, h.anschlag) == (
        "heizkurve_parallel",
        "3/58",
        3.0,
        None,
        "K",
        True,
    )
    assert h.abweichung == -1.0


def test_eine_kurve_ohne_behaglichkeit_nennt_nur_die_richtung(m):
    (h,) = m.hinweise(reihe(m, 7, 2.0, -1.44), ohne_baender(p3_58=None), HEUTE)
    assert h == m.Hinweis(art="heizkurve_parallel", tage=7, seit=None, abweichung=-1.4)


def test_steuerung_passt_an_gilt_auch_fuer_eine_kurve(m):
    tage = reihe(m, 7, 2.0, -1.4, soll=None)
    (h,) = m.hinweise(tage, ohne_baender(p3_7=1.5), HEUTE, kreis=m.Kreis(raumfuehler=True))
    assert (h.art, h.tage) == ("steuerung_passt_an", 7)
    assert (
        m.tendenzen(tage[:4], ohne_baender(p3_7=1.5), HEUTE, kreis=m.Kreis(raumfuehler=True)) == []
    )


def test_arten_folgen_den_kurvenpunkten(m):
    assert m.arten(parameter()) == ["kurve_uebergang", "kurve_frost", "sollwert", "morgen"]
    assert m.arten(ohne_baender()) == ["kurve", "sollwert", "morgen"]
    assert m.arten(parameter(p3_13=None)) == ["kurve", "sollwert", "morgen"]
    assert m.arten({}) == ["kurve", "sollwert", "morgen"]


def test_steuerung_passt_an_nicht_bei_null(m):
    tage = reihe(m, 7, -3.0, -1.4)
    assert arten(m.hinweise(tage, parameter(p3_7=0.0, p3_101=0.0), HEUTE)) == ["heizkurve_frost"]


# --- Raumsollwert und Vorhaltezeit ----------------------------------------


def test_hoher_sollwert_ergibt_ausgleich(m):
    (h,) = m.hinweise(reihe(m, 7, 2.0, 0.0, soll=23.0), parameter(), HEUTE)
    assert h == m.Hinweis(
        art="sollwert_ausgleich", tage=7, seit=None, parameter="3/51", von=23.0, einheit="°C"
    )


def test_sollwert_braucht_genug_heiztage(m):
    tage = [*reihe(m, 6, 2.0, 0.0, soll=23.0), tag(m, 6, 2.0, 0.0, soll=None)]
    assert m.hinweise(tage, parameter(), HEUTE) == []


def test_sollwert_unter_schwelle_ohne_hinweis(m):
    assert m.hinweise(reihe(m, 7, 2.0, 0.0, soll=22.4), parameter(), HEUTE) == []
    assert arten(m.hinweise(reihe(m, 7, 2.0, 0.0, soll=22.5), parameter(), HEUTE)) == [
        "sollwert_ausgleich"
    ]


def test_spaet_warm_verlaengert_vorhaltezeit(m):
    (h,) = m.hinweise(reihe(m, 7, 2.0, 0.0, morgen=90), parameter(), HEUTE)
    assert (h.art, h.parameter, h.von, h.nach, h.einheit, h.tage) == (
        "morgen_spaet",
        "3/6",
        60.0,
        150.0,
        "min",
        7,
    )
    assert h.minuten == 90


def test_grundlage_zaehlt_ungestoerte_tage_seit_der_aenderung(m):
    tage = reihe(m, 7, 2.0, 0.0)
    assert len(m.grundlage(tage, parameter(), HEUTE)) == 7
    assert m.grundlage(tage, {"3/1": [["2026-01-01", 45], [HEUTE, 43]]}, HEUTE) == []


def test_vorhaltezeit_rundet_auf_viertelstunden(m):
    (h,) = m.hinweise(reihe(m, 7, 2.0, 0.0, morgen=100), parameter(), HEUTE)
    assert h.nach == 165.0


def test_vorhaltezeit_hoechstens_vier_stunden(m):
    (h,) = m.hinweise(reihe(m, 7, 2.0, 0.0, morgen=90), parameter(p3_6=200.0), HEUTE)
    assert h.nach == 240.0


def test_vorhaltezeit_grenzen(m):
    assert m.hinweise(reihe(m, 7, 2.0, 0.0, morgen=59), parameter(), HEUTE) == []
    tage = [*reihe(m, 6, 2.0, 0.0, morgen=90), tag(m, 6, 2.0, 0.0)]
    assert m.hinweise(tage, parameter(), HEUTE) == []


def test_ohne_vorhaltezeit_empfiehlt_er_einen_frueheren_programmstart(m):
    (h,) = m.hinweise(reihe(m, 7, 2.0, 0.0, morgen=95), parameter(p3_6=None), HEUTE)
    assert (h.art, h.parameter, h.von, h.nach, h.einheit, h.minuten) == (
        "morgen_spaet",
        "zeitprogramm",
        None,
        90.0,
        "min",
        95,
    )


def test_schon_warm_mit_vorhaltezeit(m):
    (h,) = m.hinweise(reihe(m, 7, 2.0, 0.0, morgen=0), parameter(), HEUTE)
    assert h == m.Hinweis(
        art="morgen_frueh",
        tage=7,
        seit=None,
        parameter="3/6",
        von=60.0,
        einheit="min",
        minuten=0,
    )


@pytest.mark.parametrize("vorhaltezeit", [None, 0.0])
def test_schon_warm_ohne_vorhaltezeit_nennt_das_zeitprogramm(m, vorhaltezeit):
    tage = reihe(m, 7, 2.0, 0.0, morgen=0)
    (h,) = m.hinweise(tage, parameter(p3_6=vorhaltezeit), HEUTE)
    assert (h.art, h.parameter, h.von, h.nach, h.einheit, h.minuten) == (
        "morgen_frueh",
        "zeitprogramm",
        None,
        None,
        "min",
        0,
    )


def test_morgen_der_thermostate_empfiehlt_ihr_programm(m):
    tage = [replace(t, morgen_quelle="raeume") for t in reihe(m, 7, 2.0, 0.0, morgen=95)]
    (h,) = m.hinweise(tage, parameter(), HEUTE)
    assert (h.art, h.parameter, h.von, h.nach, h.minuten) == (
        "morgen_spaet",
        "thermostate",
        None,
        90.0,
        95,
    )
    tage = [replace(t, morgen_quelle="raeume") for t in reihe(m, 7, 2.0, 0.0, morgen=0)]
    (h,) = m.hinweise(tage, parameter(), HEUTE)
    assert (h.art, h.parameter, h.von) == ("morgen_frueh", "thermostate", None)


def test_die_mehrheit_der_tage_bestimmt_die_quelle(m):
    tage = [replace(t, morgen_quelle="raeume") for t in reihe(m, 4, 2.0, 0.0, morgen=90)]
    tage += reihe(m, 3, 2.0, 0.0, morgen=90, ab_tag=4)
    (h,) = m.hinweise(tage, parameter(), HEUTE)
    assert h.parameter == "thermostate"


def test_schon_warm_braucht_median_null_und_genug_tage(m):
    assert m.hinweise(reihe(m, 6, 2.0, 0.0, morgen=0), parameter(), HEUTE) == []
    tage = reihe(m, 4, 2.0, 0.0, morgen=0) + reihe(m, 3, 2.0, 0.0, morgen=60, ab_tag=4)
    assert arten(m.hinweise(tage, parameter(), HEUTE)) == ["morgen_frueh"]
    tage = reihe(m, 3, 2.0, 0.0, morgen=0) + reihe(m, 4, 2.0, 0.0, morgen=15, ab_tag=3)
    assert m.hinweise(tage, parameter(), HEUTE) == []


# --- Reihenfolge ----------------------------------------------------------


def test_reihenfolge(m):
    felder = {"soll": 23.0, "morgen": 90}
    tage = reihe(m, 7, -3.0, -1.4, **felder) + reihe(m, 7, 10.0, 1.0, ab_tag=7, **felder)
    assert arten(m.hinweise(tage, parameter(), HEUTE)) == [
        "heizkurve_frost",
        "heizkurve_uebergang",
        "sollwert_ausgleich",
        "morgen_spaet",
    ]
    assert arten(m.hinweise(tage, parameter(p3_7=1.0), HEUTE, kreis=m.Kreis(raumfuehler=True))) == [
        "steuerung_passt_an",
        "sollwert_ausgleich",
        "morgen_spaet",
    ]


def test_klimapunkt_rechnet_die_empfehlung_auf_das_kurvenende_hoch(m):
    # Frosttage bei −4 °C, Klimapunkt −16 °C: 24 von 36 K, die Änderung wirkt zu zwei Dritteln.
    # −1 K × 2,5 × 0,7 × 3/2 = −2,625 K.
    (h,) = m.hinweise(reihe(m, 7, -4.0, -1.0), parameter(p3_12=-16.0), HEUTE)
    assert (h.art, h.von, h.nach) == ("heizkurve_frost", 80.0, 83.0)


def test_aenderung_der_vorhaltezeit_laesst_die_kurvengrundlage_stehen(m):
    p = parameter()
    p["3/6"].append(["2027-02-27", 90.0])
    assert arten(m.hinweise(reihe(m, 7, -4.0, -1.0), p, HEUTE)) == ["heizkurve_frost"]


# --- Markierung und Fortschritt -------------------------------------------


def test_archiveintrag_ohne_markierung_bleibt_lesbar(m):
    eintrag = {
        "datum": "2026-11-01",
        "at": 2.0,
        "abweichung": 0.0,
        "soll": 21.0,
        "morgen_min": None,
        "ungestoert": True,
        "stunden": 24,
    }
    assert m.Tag(**eintrag).nachgerechnet is False
    assert m.Tag(**eintrag).sauber is None


def test_alter_eintrag_behaelt_sein_ungestoert(m):
    alt = {"at": -3.0, "abweichung": -1.4, "soll": 21.0, "morgen_min": 90, "stunden": 24}
    tage = [
        m.Tag(datum=(START + timedelta(days=i)).isoformat(), ungestoert=i != 0, **alt)
        for i in range(7)
    ]
    assert m.fortschritt(tage, parameter(), HEUTE)["kurve_frost"] == 6
    assert m.fortschritt(tage, parameter(), HEUTE)["morgen"] == 6
    assert m.hinweise(tage, parameter(), HEUTE) == []


def test_morgenzeit_zaehlt_auch_an_tagen_mit_eingriffen(m):
    tage = reihe(m, 7, 2.0, 0.0, morgen=90, ungestoert=False, sauber=3)
    assert m.fortschritt(tage, parameter(), HEUTE)["morgen"] == 7
    assert arten(m.hinweise(tage, parameter(), HEUTE)) == ["morgen_spaet"]


def test_morgenzeit_braucht_genug_stunden_und_gilt_erst_nach_der_aenderung(m):
    p = parameter()
    p["3/6"].append([(START + timedelta(days=1)).isoformat(), 90.0])
    tage = reihe(m, 7, 2.0, 0.0, morgen=90, ungestoert=False, sauber=0)
    tage.append(tag(m, 7, 2.0, 0.0, morgen=90, sauber=6, stunden=m.MIN_STUNDEN - 1))
    assert m.fortschritt(tage, p, HEUTE)["morgen"] == 5


def fortschritt_tage(m):
    """7 Frost-, 3 Übergangstage; Sollwert an 5, Morgenzeit an 2 Tagen; dazu gestört und heute."""
    frost = [tag(m, i, -3.0, -1.0, soll=23.0 if i < 5 else None) for i in range(7)]
    uebergang = [tag(m, i, 10.0, 0.0, soll=None, morgen=90) for i in range(7, 9)]
    uebergang.append(tag(m, 9, 10.0, 0.0, soll=None))
    gestoert = tag(m, 10, -3.0, -1.0, soll=23.0, morgen=90, ungestoert=False)
    heute = m.Tag(HEUTE, -3.0, -1.0, 23.0, 90, True, 24)
    return [*frost, *uebergang, gestoert, heute]


def test_fortschritt_zaehlt_je_art(m):
    assert m.fortschritt(fortschritt_tage(m), parameter(), HEUTE) == {
        "kurve": 10,
        "kurve_frost": 7,
        "kurve_uebergang": 3,
        "sollwert": 5,
        "morgen": 2,
    }


def test_fortschritt_zaehlt_nach_einer_kurvenaenderung_neu(m):
    p = parameter()
    p["3/1"].append([(START + timedelta(days=3)).isoformat(), 46.0])
    assert m.fortschritt(fortschritt_tage(m), p, date.fromisoformat(HEUTE)) == {
        "kurve": 6,
        "kurve_frost": 3,
        "kurve_uebergang": 3,
        "sollwert": 1,
        "morgen": 2,
    }


@pytest.mark.parametrize("anzahl", [6, 7])
@pytest.mark.parametrize("ungestoert", [True, False])
def test_fortschritt_und_hinweise_passen_zusammen(m, anzahl, ungestoert):
    # Gestörte Tage mit Stundenwertung zählen nur noch für die Morgenzeit.
    felder = {"soll": 23.0, "morgen": 90, "ungestoert": ungestoert, "sauber": 6 * ungestoert}
    tage = reihe(m, anzahl, -3.0, -1.4, **felder) + reihe(m, 3, 10.0, 0.0, ab_tag=7, soll=None)
    stand = m.fortschritt(tage, parameter(), HEUTE)
    gefunden = arten(m.hinweise(tage, parameter(), HEUTE))
    for art, schluessel in (
        ("heizkurve_frost", "kurve_frost"),
        ("sollwert_ausgleich", "sollwert"),
        ("morgen_spaet", "morgen"),
    ):
        erwartet = anzahl if ungestoert or schluessel == "morgen" else 0
        assert stand[schluessel] == erwartet
        assert (art in gefunden) == (stand[schluessel] >= m.MIN_TAGE)


# --- Vorläufige Tendenz ---------------------------------------------------


def richtungen(liste):
    return {t.art: (t.richtung, t.tage, t.wert) for t in liste}


def test_tendenz_erst_ab_vier_tagen(m):
    assert m.tendenzen(reihe(m, 3, 10.0, -1.0, soll=None), parameter(), HEUTE) == []
    assert richtungen(m.tendenzen(reihe(m, 4, 10.0, -1.0, soll=None), parameter(), HEUTE)) == {
        "kurve_uebergang": ("kalt", 4, -1.0),
    }


def test_ab_sieben_tagen_keine_tendenz_mehr(m):
    tage = reihe(m, 7, 10.0, -1.0, soll=23.0, morgen=90)
    assert m.tendenzen(tage, parameter(), HEUTE) == []


@pytest.mark.parametrize(
    ("ab", "erwartet"),
    [(-0.5, "kalt"), (-0.4, "unauffaellig"), (0.4, "unauffaellig"), (0.5, "warm")],
)
def test_kurventendenz_folgt_der_schwelle(m, ab, erwartet):
    tage = reihe(m, 5, -3.0, ab, soll=None)
    assert richtungen(m.tendenzen(tage, parameter(), HEUTE))["kurve_frost"][0] == erwartet


def test_sollwert_und_morgen_als_median(m):
    tage = reihe(m, 4, 20.0, 0.0, soll=22.5, morgen=60) + reihe(m, 1, 20.0, 0.0, ab_tag=4)
    assert richtungen(m.tendenzen(tage, parameter(), HEUTE)) == {
        "sollwert": ("hoch", 5, 22.5),
        "morgen": ("spaet", 4, 60),
    }


def test_niedriger_sollwert_und_frueh_warm_sind_unauffaellig(m):
    tage = reihe(m, 4, 20.0, 0.0, soll=21.0, morgen=30)
    assert richtungen(m.tendenzen(tage, parameter(), HEUTE)) == {
        "sollwert": ("unauffaellig", 4, 21.0),
        "morgen": ("unauffaellig", 4, 30),
    }


def test_morgen_tendenz_frueh_bei_median_null(m):
    tage = reihe(m, 4, 20.0, 0.0, soll=None, morgen=0)
    assert richtungen(m.tendenzen(tage, parameter(), HEUTE)) == {"morgen": ("frueh", 4, 0)}


def test_tendenz_der_einen_kurve(m):
    tage = reihe(m, 2, -3.0, -1.0, soll=None) + reihe(m, 3, 2.0, -0.6, ab_tag=2, soll=None)
    assert richtungen(m.tendenzen(tage, ohne_baender(), HEUTE)) == {"kurve": ("kalt", 5, -0.8)}


def test_tendenzen_folgen_den_arten(m):
    tage = reihe(m, 4, -3.0, -1.0, soll=None)
    assert set(richtungen(m.tendenzen(tage, parameter(), HEUTE))) == {"kurve_frost"}
    assert set(richtungen(m.tendenzen(tage, ohne_baender(), HEUTE))) == {"kurve"}


def test_steuerung_passt_an_unterdrueckt_kurventendenz(m):
    tage = reihe(m, 4, 10.0, -1.0, soll=None)
    assert m.tendenzen(tage, parameter(p3_7=1.0), HEUTE, kreis=m.Kreis(raumfuehler=True)) == []


def test_tendenz_zaehlt_wie_der_fortschritt(m):
    tage = fortschritt_tage(m)
    stand = m.fortschritt(tage, parameter(), HEUTE)
    for t in m.tendenzen(tage, parameter(), HEUTE):
        assert t.tage == stand[t.art]


# --- Parameterstand -------------------------------------------------------


def test_parameterstand_nennt_wert_und_letzte_aenderung(m):
    verlauf = {
        "3/1": [["2026-08-14", 45.0]],
        "3/13": [["2026-08-14", 80.0], ["2026-10-02", 78.0]],
        "3/6": [["2026-08-14", None]],
    }
    assert m.parameterstand(verlauf) == {
        "3/1": {"wert": 45.0, "seit": None},
        "3/13": {"wert": 78.0, "seit": "2026-10-02"},
    }


# --- Kurvenform bei einer Kurve -------------------------------------------


def test_eine_kurve_mit_gegenlaeufigen_baendern_meldet_die_kurvenform(m):
    tage = reihe(m, 7, -3.0, -1.0, soll=None) + reihe(m, 7, 10.0, 0.8, ab_tag=7, soll=None)
    for p in (ohne_baender(), ohne_baender(p3_58=None)):
        (h,) = m.hinweise(tage, p, HEUTE)
        assert h == m.Hinweis(art="kurvenform", tage=14, seit=None, abweichung=0.8, frost=-1.0)


def test_kurvenform_braucht_beide_baender_ueber_der_schwelle(m):
    # Übergang unter der Schwelle: das Mittel aller Tage zählt, hier −0,3 K.
    tage = reihe(m, 7, -3.0, -1.0, soll=None) + reihe(m, 7, 10.0, 0.4, ab_tag=7, soll=None)
    assert m.hinweise(tage, ohne_baender(), HEUTE) == []
    # Zu wenige Frosttage: das Mittel aller Tage zählt, hier +0,8 K über die Behaglichkeit.
    tage = reihe(m, 6, -3.0, -1.0, soll=None) + reihe(m, 14, 10.0, 1.6, ab_tag=6, soll=None)
    (h,) = m.hinweise(tage, ohne_baender(), HEUTE)
    assert (h.art, h.parameter, h.nach) == ("heizkurve_parallel", "3/58", -1.0)


def test_kurvenform_nur_bei_einer_kurve(m):
    tage = reihe(m, 7, -3.0, -1.0, soll=None) + reihe(m, 7, 10.0, 0.8, ab_tag=7, soll=None)
    assert arten(m.hinweise(tage, parameter(), HEUTE)) == [
        "heizkurve_frost",
        "heizkurve_uebergang",
    ]


# --- Heizkreistyp ---------------------------------------------------------


@pytest.mark.parametrize("typ", [0, 3, 4, 5])
def test_heizkreis_ohne_kurve_bekommt_keine_kurvenhinweise(m, typ):
    # Ohne Heizkurve entfällt auch der Sollwert: sein Rat verweist auf die Kurve.
    tage = reihe(m, 7, -3.0, -1.4, soll=23.0)
    assert m.arten(parameter(), kreis=m.Kreis(typ)) == ["morgen"]
    assert m.hinweise(tage, parameter(), HEUTE, kreis=m.Kreis(typ)) == []
    p = parameter(p3_7=2.0)
    assert m.hinweise(tage, p, HEUTE, kreis=m.Kreis(typ, raumfuehler=True)) == []
    kurz = reihe(m, 4, -3.0, -1.4, soll=23.0)
    assert m.tendenzen(kurz, parameter(), HEUTE, kreis=m.Kreis(typ)) == []
    morgen = reihe(m, 7, -3.0, -1.4, soll=23.0, morgen=90)
    assert arten(m.hinweise(morgen, parameter(), HEUTE, kreis=m.Kreis(typ))) == ["morgen_spaet"]


def test_fussboden_bekommt_keine_morgenhinweise(m):
    tage = reihe(m, 7, 2.0, 0.0, morgen=90)
    assert m.arten(parameter(), kreis=m.Kreis(2)) == ["kurve_uebergang", "kurve_frost", "sollwert"]
    assert m.arten(ohne_baender(), kreis=m.Kreis(2)) == ["kurve", "sollwert"]
    assert m.hinweise(tage, parameter(), HEUTE, kreis=m.Kreis(2)) == []
    assert m.hinweise(reihe(m, 7, 2.0, 0.0, morgen=0), parameter(), HEUTE, kreis=m.Kreis(2)) == []
    kurz = reihe(m, 4, 2.0, 0.0, soll=None, morgen=90)
    assert m.tendenzen(kurz, parameter(), HEUTE, kreis=m.Kreis(2)) == []


def test_fussboden_rechnet_mit_kleinerem_faktor(m):
    # −1,4 K × 1,3 × 0,7 = −1,27 K; +0,8 K × 1,3 × 0,7 = +0,73 K.
    tage = reihe(m, 7, -3.0, -1.4) + reihe(m, 7, 10.0, 0.8, ab_tag=7)
    liste = m.hinweise(tage, parameter(), HEUTE, kreis=m.Kreis(2))
    assert [(h.art, h.nach) for h in liste] == [
        ("heizkurve_frost", 81.0),
        ("heizkurve_uebergang", 44.0),
    ]


def test_hinweis_ueber_der_schwelle_aendert_mindestens_ein_grad(m):
    # −0,52 K × 1,3 × 0,7 = −0,47 K rundet auf null; der Hinweis nennt dann ein Grad.
    p = parameter(p3_13=60.0)
    (h,) = m.hinweise(reihe(m, 7, -3.0, -0.52), p, HEUTE, kreis=m.Kreis(2))
    assert (h.art, h.von, h.nach) == ("heizkurve_frost", 60.0, 61.0)
    (h,) = m.hinweise(reihe(m, 7, -3.0, 0.52), p, HEUTE, kreis=m.Kreis(2))
    assert (h.art, h.von, h.nach) == ("heizkurve_frost", 60.0, 59.0)


def test_aenderung_des_heizkreistyps_setzt_die_kurvengrundlage_zurueck(m):
    p = parameter()
    p["7/76"] = [["2026-10-01", 1.0], ["2026-11-10", 2.0]]
    tage = reihe(m, 20, -3.0, -1.4)
    assert m.grundlage(tage, p, HEUTE)[0].datum == "2026-11-11"


def test_behaglichkeit_wird_nicht_gedaempft(m):
    tage = reihe(m, 7, -3.0, -1.0) + reihe(m, 7, 10.0, -1.0, ab_tag=7)
    (h,) = m.hinweise(tage, parameter(), HEUTE, kreis=m.Kreis(2))
    assert (h.art, h.nach) == ("heizkurve_parallel", 1.0)


@pytest.mark.parametrize(
    ("verlauf", "heizflaechen", "erwartet"),
    [
        ({"7/76": [["2026-10-01", 2.0]]}, "heizkoerper", 2),
        ({"7/76": [["2026-10-01", 0.0]]}, "flaeche", 0),
        ({"7/76": [["2026-10-01", None]]}, "flaeche", 2),
        ({}, "flaeche", 2),
        ({}, "heizkoerper", 1),
        ({}, "gemischt", 1),
        ({}, None, 1),
    ],
)
def test_heizkreistyp_aus_der_steuerung_sonst_aus_den_heizflaechen(
    m, verlauf, heizflaechen, erwartet
):
    assert m.heizkreis_typ(verlauf, heizflaechen) == erwartet


# --- Vorlauf nicht erreicht -----------------------------------------------


def test_stunde_mit_verfehltem_vorlauf_ist_nicht_sauber(m):
    stunden = heiztag(())
    for h in range(24):
        stunden[str(h)]["vl"] = 45.0
    for h in range(10):
        stunden[str(h)]["vi"] = 41.9
    stunden["10"]["vi"] = 42.0
    stunden["11"].update(vi=30.0)
    del stunden["11"]["vl"]
    assert m.tag_aus_stunden("2026-11-03", stunden).sauber == 14


# --- Behaglichkeit, die Abweichung gilt dem Raumsoll ohne `3/58` -------------


@pytest.mark.parametrize(
    ("von", "d", "nach"),
    [
        (0.0, -0.7, 0.5),
        (0.5, -0.7, 1.0),
        (0.5, -0.9, 1.5),
        (1.0, 1.0, 0.0),
        (2.0, 1.0, 1.0),
    ],
)
def test_behaglichkeit_verschiebt_sich_um_die_abweichung(m, von, d, nach):
    # Raum = Basis + Fehler der Kurve, gemessen gegen die Basis: die neue Behaglichkeit ist c − d.
    (h,) = m.hinweise(reihe(m, 7, 2.0, d), ohne_baender(p3_58=von), HEUTE)
    assert (h.art, h.parameter, h.von, h.nach) == ("heizkurve_parallel", "3/58", von, nach)


def test_kleine_abweichung_aendert_die_behaglichkeit_nicht(m):
    assert m.hinweise(reihe(m, 7, 2.0, -0.2), ohne_baender(p3_58=0.5), HEUTE) == []


def test_parallele_baender_verschieben_die_behaglichkeit(m):
    tage = reihe(m, 7, -3.0, -0.7) + reihe(m, 7, 10.0, -0.7, ab_tag=7)
    (h,) = m.hinweise(tage, parameter(p3_58=0.5), HEUTE)
    assert (h.art, h.von, h.nach) == ("heizkurve_parallel", 0.5, 1.0)


def test_behaglichkeit_an_der_grenze(m):
    tage = reihe(m, 7, 2.0, -1.0)
    (h,) = m.hinweise(tage, ohne_baender(p3_58=3.0), HEUTE)
    assert (h.von, h.nach, h.anschlag) == (3.0, None, True)
    (h,) = m.hinweise(tage, ohne_baender(p3_58=2.5), HEUTE)
    assert (h.von, h.nach, h.anschlag) == (2.5, 3.0, False)


def test_auswertung_entspricht_den_einzelfunktionen(m):
    tage = reihe(m, 7, -3.0, -1.4, soll=23.0, morgen=90) + reihe(m, 5, 10.0, 0.6, ab_tag=7)
    p = parameter()
    kreis = m.Kreis(m.FUSSBODEN)
    a = m.auswerten(tage, p, HEUTE, kreis=kreis)
    assert a.arten == m.arten(p, kreis=kreis)
    assert a.hinweise == m.hinweise(tage, p, HEUTE, kreis=kreis)
    assert a.tendenzen == m.tendenzen(tage, p, HEUTE, kreis=kreis)
    assert a.fortschritt == m.fortschritt(tage, p, HEUTE)
    assert a.grundlage == len(m.grundlage(tage, p, HEUTE)) == 12
    assert a.hinweise and a.tendenzen


# --- Text für die Seitenleiste --------------------------------------------


@pytest.fixture(scope="module")
def text():
    load_standalone("automatik")
    return load_standalone("automatik.ergebnistext")


def _alle_arten(m):
    h = m.Hinweis
    return [
        h("heizkurve_frost", 9, None, -1.4, "3/13", 80.0, 82.0, "°C"),
        h("heizkurve_parallel", 8, None, -0.7, "3/58", 0.0, 0.5, "K"),
        h("heizkurve_parallel", 8, None, -1.2, "3/58", 3.0, None, "K", anschlag=True),
        h("heizkurve_parallel", 8, None, 0.6),
        h("kurvenform", 14, None, 0.8, frost=-1.0),
        h("sollwert_ausgleich", 7, None, None, "3/51", 23.0, None, "°C"),
        h("morgen_spaet", 7, None, None, "3/6", 60.0, 135.0, "min", 75),
        h("morgen_spaet", 7, None, None, "zeitprogramm", None, 60.0, "min", 60),
        h("morgen_frueh", 7, None, None, "3/6", 45.0, None, "min", 0),
        h("steuerung_passt_an", 7, None),
    ]


def test_seitenleiste_nennt_je_hinweis_eine_zeile(m, text):
    assert text.text(_alle_arten(m), lambda t: t).split("\n") == [
        "- Heizkurve bei Frost: Vorlauf bei Auslegung 80 → 82 °C (−1,4 K, 9 Tage)",
        "- Heizkurve: Behaglichkeit 0 → 0,5 K (−0,7 K, 8 Tage)",
        "- Heizkurve: Behaglichkeit am Anschlag (−1,2 K, 8 Tage)",
        "- Heizkurve: Heizkurve absenken (+0,6 K, 8 Tage)",
        "- Heizkurve: Kurvenform prüfen (Übergang +0,8 K · Frost −1,0 K, 14 Tage)",
        "- Raumsollwert: Heizkurve anpassen statt Sollwert (Sollwert 23,0 °C, 7 Tage)",
        "- Morgens zu spät warm: Vorhaltezeit 60 → 135 min (Ziel nach 75 min, 7 Tage)",
        "- Morgens zu spät warm: Programmstart 60 min früher (Ziel nach 60 min, 7 Tage)",
        "- Morgens schon warm: Vorhaltezeit 45 min kürzer möglich (Ziel nach 0 min, 7 Tage)",
        "",
        "Die Automatik ändert diese Werte nicht.",
    ]


def test_seitenleiste_ohne_empfehlung_bleibt_leer(m, text):
    assert text.text([], lambda t: t) is None
    assert text.text([m.Hinweis("steuerung_passt_an", 7, None)], lambda t: t) is None


@pytest.mark.parametrize(
    ("sprache", "punkt", "erwartet"),
    [
        ("en", True, "Heating curve: Comfort correction 0 → 0.5 K (−0.7 K, 8 days)"),
        ("nl", False, "Stooklijn: Comfortcorrectie 0 → 0,5 K (−0,7 K, 8 dagen)"),
    ],
)
def test_seitenleiste_spricht_die_sprache_der_anlage(m, text, sprache, punkt, erwartet):
    woerter = load_standalone("texte").Woerterbuch(sprache)
    hinweis = m.Hinweis("heizkurve_parallel", 8, None, -0.7, "3/58", 0.0, 0.5, "K")
    assert text.zeile(hinweis, woerter, punkt) == erwartet
    deutsch = [z for h in _alle_arten(m) if (z := text.zeile(h, lambda t: t)) is not None]
    fremd = text.text(_alle_arten(m), woerter, punkt).split("\n")
    assert not set(fremd) & {f"- {z}" for z in deutsch}


def test_kachel_und_seitenleiste_nutzen_dieselben_texte(m, text):
    h = m.Hinweis
    faelle = [
        (
            h("steuerung_passt_an", 23, None),
            ["Heizkurve", "Keine Empfehlung zur Kurve", "Anpassung durch die Steuerung aktiv"],
        ),
        (
            h("heizkurve_frost", 18, "2026-11-14", -1.4, "3/13", 80.0, 86.0, "°C"),
            [
                "Heizkurve bei Frost",
                "Vorlauf bei Auslegung 80 → 86 °C",
                "−1,4 K",
                "18 Tage seit 14.11.",
            ],
        ),
        (
            h("heizkurve_parallel", 20, None, 0.9, "3/58", 0.0, -1.0, "K"),
            ["Heizkurve", "Behaglichkeit 0 → −1 K", "+0,9 K", "20 Tage"],
        ),
        (
            h("kurvenform", 12, None, -0.9, frost=1.1),
            ["Heizkurve", "Kurvenform prüfen", "Übergang −0,9 K · Frost +1,1 K", "12 Tage"],
        ),
    ]
    for hinweis, (titel, empfehlung, *angaben) in faelle:
        t = text.texte(hinweis, lambda s: s)
        assert (t["titel"], t["empfehlung"], t["angaben"]) == (titel, empfehlung, angaben)


def test_parameterzeile_nur_fuer_parameter_mit_eigenem_verlauf(text):
    stand = {
        "3/1": {"wert": 45.0, "seit": "2026-09-20"},
        "3/58": {"wert": -0.5, "seit": None},
        "3/51": {"wert": 21.0, "seit": None},
        "3/12": {"wert": -12.0, "seit": None},
    }
    zeilen = {name: e.get("zeile") for name, e in text.parameterstand(stand, lambda s: s).items()}
    assert zeilen == {
        "3/1": "Fußpunkt 45 °C seit 20.09.",
        "3/58": "Behaglichkeit −0,5 K",
        "3/51": None,
        "3/12": None,
    }


def test_texte_der_kachel_stehen_in_jedem_woerterbuch(m, text):
    for sprache in ("en", "nl"):
        woerter = load_standalone("texte").Woerterbuch(sprache)
        for hinweis in [
            *_alle_arten(m),
            m.Hinweis("heizkurve_frost", 9, "2026-11-14", -1.4, "3/13", 80.0, 82.0, "°C"),
        ]:
            deutsch = text.texte(hinweis, lambda s: s)
            fremd = text.texte(hinweis, woerter, sprache == "en")
            assert fremd["titel"] != deutsch["titel"], (sprache, hinweis.art)
            assert not set(fremd["angaben"]) & set(deutsch["angaben"]) - {
                "−1,4 K",
                "+0,6 K",
                "−0,7 K",
                "−1,2 K",
            }, (sprache, hinweis.art)


def test_texte_zum_morgen_der_thermostate(m, text):
    h = m.Hinweis
    spaet = text.texte(
        h("morgen_spaet", 7, None, None, "thermostate", None, 90.0, "min", 95), lambda s: s
    )
    frueh = text.texte(
        h("morgen_frueh", 7, None, None, "thermostate", None, None, "min", 0), lambda s: s
    )
    assert spaet["empfehlung"] == "Thermostate 90 min früher hochschalten"
    assert frueh["empfehlung"] == "Absenkung der Thermostate wirkt kaum"
    for sprache in ("en", "nl"):
        woerter = load_standalone("texte").Woerterbuch(sprache)
        fremd = text.texte(
            h("morgen_frueh", 7, None, None, "thermostate", None, None, "min", 0), woerter
        )
        assert fremd["empfehlung"] != frueh["empfehlung"], sprache
