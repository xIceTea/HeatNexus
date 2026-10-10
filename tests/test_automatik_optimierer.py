"""Optimierungshinweise der Automatik.

Geprüft werden die Tageszusammenfassung und jede Regel, die aus ungestörten
Tagen einen Hinweis zu Heizkurve, Raumsollwert oder Vorhaltezeit ableitet.
"""

from __future__ import annotations

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


def tag(m, i, at, ab, *, soll=21.0, morgen=None, ungestoert=True, stunden=24):
    datum = (START + timedelta(days=i)).isoformat()
    return m.Tag(datum, at, ab, soll, morgen, ungestoert, stunden)


def reihe(m, anzahl, at, ab, *, ab_tag=0, **felder):
    return [tag(m, ab_tag + i, at, ab, **felder) for i in range(anzahl)]


def parameter(**werte):
    """Anfangsstand je Parameter; `p3_13=80` steht für `3/13`."""
    basis = {"p3_13": 80.0, "p3_1": 45.0, "p3_58": 0.0, "p3_6": 60.0, "p3_7": 0.0, "p3_101": None}
    basis.update(werte)
    return {k[1:].replace("_", "/"): [["2026-10-01", v]] for k, v in basis.items()}


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


def test_andere_aktion_stoert_den_tag(m):
    for aktion in ("absenkung", "heizpause", "nur_ww"):
        stunden = stunden_eines_tages(h13={"aktion": aktion})
        assert m.tag_aus_stunden("2026-11-03", stunden).ungestoert is False


def test_vorgabe_des_nutzers_stoert_den_tag(m):
    stunden = stunden_eines_tages(h19={"vorgabe": True})
    assert m.tag_aus_stunden("2026-11-03", stunden).ungestoert is False


def test_im_beobachten_zaehlt_ein_geplanter_eingriff_nicht(m):
    stunden = stunden_eines_tages(h13={"aktion": "absenkung", "beobachtet": True})
    assert m.tag_aus_stunden("2026-11-03", stunden).ungestoert is True


def test_stunde_ohne_betriebsart_beginnt_keinen_heizblock(m):
    stunden = stunden_eines_tages()
    for h in range(6):
        del stunden[str(h)]["ba"]
    assert m.tag_aus_stunden("2026-11-03", stunden).morgen_min is None


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


def test_heizbetrieb_ab_mitternacht_hat_keine_morgenzeit(m):
    stunden = stunden_eines_tages()
    for s in stunden.values():
        s["ba"] = 1
    assert m.tag_aus_stunden("2026-11-03", stunden).morgen_min is None


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
    (h,) = m.hinweise(reihe(m, 7, -3.0, -1.4), parameter(), HEUTE)
    assert h == m.Hinweis(
        art="heizkurve_frost",
        tage=7,
        seit=None,
        abweichung=-1.4,
        parameter="3/13",
        von=80.0,
        nach=86.0,
        einheit="°C",
    )


def test_frost_aenderung_hoechstens_zehn(m):
    (h,) = m.hinweise(reihe(m, 7, -3.0, -3.0), parameter(), HEUTE)
    assert h.nach == 90.0
    (h,) = m.hinweise(reihe(m, 7, -3.0, 4.0), parameter(), HEUTE)
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


def test_uebergang_rundet_halbe_weg_von_null(m):
    (h,) = m.hinweise(reihe(m, 7, 10.0, 0.5), parameter(), HEUTE)
    assert h.nach == 43.0
    (h,) = m.hinweise(reihe(m, 7, 10.0, -0.5), parameter(), HEUTE)
    assert h.nach == 47.0


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


def test_parallel_am_anschlag_ohne_hinweis(m):
    tage = reihe(m, 7, -3.0, -1.0) + reihe(m, 7, 10.0, -1.0, ab_tag=7)
    assert m.hinweise(tage, parameter(p3_58=3.0), HEUTE) == []


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


def test_ohne_bekannten_wert_kein_kurvenhinweis(m):
    tage = reihe(m, 7, -3.0, -1.4) + reihe(m, 7, 10.0, 1.0, ab_tag=7)
    p = parameter()
    del p["3/13"]
    assert arten(m.hinweise(tage, p, HEUTE)) == ["heizkurve_uebergang"]
    p = parameter(p3_1=None)
    assert arten(m.hinweise(tage, p, HEUTE)) == ["heizkurve_frost"]
    gleich = reihe(m, 7, -3.0, -1.0) + reihe(m, 7, 10.0, -0.8, ab_tag=7)
    assert m.hinweise(gleich, parameter(p3_58=None), HEUTE) == []


def test_aktueller_wert_ist_letzter_eintrag(m):
    p = parameter()
    p["3/13"] += [["2026-10-05", 82.0], ["2026-10-06", None]]
    assert m.hinweise(reihe(m, 7, -3.0, -1.4), p, HEUTE) == []
    p["3/13"].append(["2026-10-07", "84.0"])
    (h,) = m.hinweise(reihe(m, 7, -3.0, -1.4), p, HEUTE)
    assert h.von == 84.0


def test_steuerung_passt_an_unterdrueckt_kurvenhinweise(m):
    tage = reihe(m, 7, -3.0, -1.4) + reihe(m, 7, 10.0, 1.0, ab_tag=7)
    for p in (parameter(p3_7=2.0), parameter(p3_101=5.0)):
        (h,) = m.hinweise(tage, p, HEUTE)
        assert (h.art, h.tage, h.seit) == ("steuerung_passt_an", 14, None)


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
    assert m.hinweise(reihe(m, 7, 2.0, 0.0, morgen=90), parameter(p3_6=None), HEUTE) == []


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
    assert arten(m.hinweise(tage, parameter(p3_7=1.0), HEUTE)) == [
        "steuerung_passt_an",
        "sollwert_ausgleich",
        "morgen_spaet",
    ]


def test_klimapunkt_rechnet_die_empfehlung_auf_das_kurvenende_hoch(m):
    # Frosttage bei −4 °C, Klimapunkt −16 °C: 24 von 36 K, die Änderung wirkt zu zwei Dritteln.
    (h,) = m.hinweise(reihe(m, 7, -4.0, -1.0), parameter(p3_12=-16.0), HEUTE)
    assert (h.art, h.von, h.nach) == ("heizkurve_frost", 80.0, 86.0)


def test_aenderung_der_vorhaltezeit_laesst_die_kurvengrundlage_stehen(m):
    p = parameter()
    p["3/6"].append(["2027-02-27", 90.0])
    assert arten(m.hinweise(reihe(m, 7, -4.0, -1.0), p, HEUTE)) == ["heizkurve_frost"]
