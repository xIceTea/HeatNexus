"""Umrechnung aufgezeichneter Zeitreihen in Stundenwerte der Optimierung.

Geprüft werden Stufenwert je Stunde, Lücken, Vorgaben des Nutzers, Raumziele und
der Durchgang bis zum zusammengefassten Tag.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from .conftest import load_standalone

ZONE = timezone(timedelta(hours=1))
TAG = date(2026, 10, 5)


@pytest.fixture(scope="module")
def n():
    load_standalone("automatik")
    return load_standalone("automatik.nachrechnen")


@pytest.fixture(scope="module")
def o():
    load_standalone("automatik")
    return load_standalone("automatik.optimierer")


def zeit(stunde: int, minute: int = 0, tag: date = TAG, zone=ZONE) -> datetime:
    return datetime.combine(tag, time(stunde, minute), zone)


def vortag() -> datetime:
    return zeit(23, 30, TAG - timedelta(days=1))


def reihen(n, **abweichend):
    """Ein ruhiger Tag: Heizbetrieb 6 bis 21 Uhr, Raum ab 8 Uhr am Ziel."""
    felder = {
        "at": [(vortag(), 3.0), (zeit(12), 5.0)],
        "soll": [(vortag(), 18.0), (zeit(6), 21.0), (zeit(22), 18.0)],
        "vl": [(vortag(), 30.0), (zeit(6), 45.0), (zeit(22), 30.0)],
        "ba": [(vortag(), 2.0), (zeit(6), 1.0), (zeit(22), 2.0)],
        "restzeit": [(vortag(), 0.0)],
        "raeume": [([(vortag(), 17.0), (zeit(7, 30), 20.5), (zeit(8, 30), 21.2)], None)],
        "raum_art": "mittel",
    }
    felder.update(abweichend)
    return n.Reihen(**felder)


def test_vollstaendiger_tag_ergibt_24_stunden(n):
    ergebnis = n.stunden_je_tag(reihen(n), [TAG])

    stunden = ergebnis[TAG.isoformat()]
    assert sorted(stunden, key=int) == [str(h) for h in range(24)]
    assert stunden["5"] == {"at": 3.0, "ab": -1.0, "ziel": 18.0, "soll": 18.0, "vl": 30.0, "ba": 2}
    # Um 7:30 steigt der Raum auf 20,5; die Stunde behält den Wert von ihrem Beginn.
    assert stunden["7"] == {"at": 3.0, "ab": -4.0, "ziel": 21.0, "soll": 21.0, "vl": 45.0, "ba": 1}
    assert stunden["8"]["ab"] == -0.5
    assert stunden["12"]["at"] == 5.0
    assert stunden["21"]["ab"] == pytest.approx(0.2)
    assert stunden["22"]["ba"] == 2


def test_stundenschluessel_und_betriebsart_wie_im_live_verlauf(n):
    stunden = n.stunden_je_tag(reihen(n), [TAG])[TAG.isoformat()]

    assert "7" in stunden and "07" not in stunden
    assert isinstance(stunden["7"]["ba"], int)
    assert "vorgabe" not in stunden["7"]


def test_wechsel_zur_vollen_stunde_gilt_fuer_diese_stunde(n):
    stunden = n.stunden_je_tag(reihen(n), [TAG])[TAG.isoformat()]

    assert stunden["5"]["soll"] == 18.0
    assert stunden["6"]["soll"] == 21.0


def test_luecke_laesst_betroffene_stunden_ohne_feld(n):
    at = [(vortag(), 3.0), (zeit(10, 15), None), (zeit(13, 5), 6.0)]

    stunden = n.stunden_je_tag(reihen(n, at=at), [TAG])[TAG.isoformat()]

    assert stunden["10"]["at"] == 3.0
    assert all("at" not in stunden[str(h)] for h in (11, 12))
    # Gilt zum Stundenbeginn nichts, zählt der erste Wert innerhalb der Stunde.
    assert stunden["13"]["at"] == 6.0


def test_vor_dem_ersten_wert_fehlt_das_feld(n):
    vl = [(zeit(6), 45.0)]

    stunden = n.stunden_je_tag(reihen(n, vl=vl), [TAG])[TAG.isoformat()]

    assert "vl" not in stunden["5"]
    assert stunden["6"]["vl"] == 45.0


def test_ohne_wert_zum_stundenbeginn_zaehlt_der_erste_der_stunde(n):
    vl = [(zeit(6, 20), 45.0), (zeit(6, 40), 50.0)]

    stunden = n.stunden_je_tag(reihen(n, vl=vl), [TAG])[TAG.isoformat()]

    assert stunden["6"]["vl"] == 45.0
    assert stunden["7"]["vl"] == 50.0


def test_vorlauf_ist_als_eigenes_feld(n):
    vi = [(vortag(), 28.0), (zeit(6, 30), 44.0)]

    stunden = n.stunden_je_tag(reihen(n, vi=vi), [TAG])[TAG.isoformat()]

    assert (stunden["5"]["vi"], stunden["6"]["vi"], stunden["7"]["vi"]) == (28.0, 28.0, 44.0)
    assert "vi" not in n.stunden_je_tag(reihen(n), [TAG])[TAG.isoformat()]["7"]


def test_verfehlter_vorlauf_nimmt_die_heizstunden_heraus(n, o):
    voll = n.stunden_je_tag(reihen(n), [TAG])[TAG.isoformat()]
    # Ab 14 Uhr bleibt der Vorlauf mehr als 3 K unter dem Soll von 45 °C.
    vi = [(vortag(), 30.0), (zeit(6), 45.0), (zeit(14), 41.0)]
    knapp = n.stunden_je_tag(reihen(n, vi=vi), [TAG])[TAG.isoformat()]

    ohne = o.tag_aus_stunden(TAG.isoformat(), voll).sauber
    assert o.tag_aus_stunden(TAG.isoformat(), knapp).sauber == ohne - 8


def test_stunde_ganz_ohne_werte_entfaellt(n):
    leer = n.Reihen(
        at=[(zeit(10), 4.0)], soll=[], vl=[], ba=[], restzeit=[], raeume=[], raum_art="mittel"
    )

    stunden = n.stunden_je_tag(leer, [TAG])[TAG.isoformat()]

    assert sorted(stunden, key=int) == [str(h) for h in range(10, 24)]
    assert stunden["10"] == {"at": 4.0}


def test_tag_ohne_jeden_wert_entfaellt(n):
    zweiter = TAG + timedelta(days=1)
    leer = n.Reihen(
        at=[(zeit(10), 4.0), (zeit(23, 30), None)],
        soll=[],
        vl=[],
        ba=[],
        restzeit=[],
        raeume=[],
        raum_art="mittel",
    )

    ergebnis = n.stunden_je_tag(leer, [TAG, zweiter])

    assert list(ergebnis) == [TAG.isoformat()]


def test_restzeit_in_stunde_9_setzt_vorgabe_nur_dort(n):
    restzeit = [(vortag(), 0.0), (zeit(9, 10), 40.0), (zeit(9, 50), 0.0)]

    stunden = n.stunden_je_tag(reihen(n, restzeit=restzeit), [TAG])[TAG.isoformat()]

    assert [h for h, s in stunden.items() if s.get("vorgabe")] == ["9"]
    assert stunden["9"]["vorgabe"] is True


def test_laufende_restzeit_gilt_fuer_jede_beruehrte_stunde(n):
    restzeit = [(vortag(), 0.0), (zeit(9, 30), 120.0), (zeit(11), 60.0), (zeit(12), 0.0)]

    stunden = n.stunden_je_tag(reihen(n, restzeit=restzeit), [TAG])[TAG.isoformat()]

    assert [h for h, s in stunden.items() if s.get("vorgabe")] == ["9", "10", "11"]


def test_raum_mit_festem_ziel_und_raum_mit_raumsoll(n):
    raeume = [
        ([(vortag(), 20.0)], 20.5),
        ([(vortag(), 22.0)], None),
    ]

    stunden = n.stunden_je_tag(reihen(n, raeume=raeume), [TAG])[TAG.isoformat()]

    # 12 Uhr, Raumsoll 21: (20 − 20,5) und (22 − 21) gemittelt.
    assert stunden["12"]["ab"] == pytest.approx(0.25)
    # 3 Uhr, Raumsoll 18: (20 − 20,5) und (22 − 18) gemittelt.
    assert stunden["3"]["ab"] == pytest.approx(1.75)


def test_ziel_ist_das_mittel_der_raumziele(n):
    raeume = [
        ([(vortag(), 20.0)], 20.5),
        ([(vortag(), 22.0)], None),
    ]

    stunden = n.stunden_je_tag(reihen(n, raeume=raeume), [TAG])[TAG.isoformat()]

    # Der Raum ohne eigenes Ziel zählt mit dem Raumsoll: 21 um 12 Uhr, 18 um 3 Uhr.
    assert stunden["12"]["ziel"] == pytest.approx(20.75)
    assert stunden["3"]["ziel"] == pytest.approx(19.25)


def test_thermostate_heben_morgens_an_ohne_die_steuerung(n, o):
    # Die Steuerung heizt ab Mitternacht auf 21 °C, die Thermostate heben um 4 Uhr von 19 auf 21 °C.
    ziel = [(vortag(), 19.0), (zeit(4), 21.0), (zeit(22), 19.0)]
    raum = [(vortag(), 20.8), (zeit(4), 19.8), (zeit(6), 20.9)]
    felder = {
        "soll": [(vortag(), 21.0)],
        "ba": [(vortag(), 1.0)],
        "raeume": [(raum, ziel)],
        "eigene_ziele": True,
    }

    stunden = n.stunden_je_tag(reihen(n, **felder), [TAG])[TAG.isoformat()]
    tag = o.tag_aus_stunden(TAG.isoformat(), stunden)

    assert (stunden["3"]["ziel"], stunden["4"]["ziel"]) == (19.0, 21.0)
    assert (tag.morgen_min, tag.morgen_quelle) == (120, "raeume")


def test_raum_mit_zielreihe_faellt_ohne_ziel_auf_raumsoll_zurueck(n):
    ziel = [(vortag(), 19.0), (zeit(12), None)]
    raeume = [([(vortag(), 20.0)], ziel)]

    stunden = n.stunden_je_tag(reihen(n, raeume=raeume), [TAG])[TAG.isoformat()]

    assert stunden["11"]["ab"] == pytest.approx(1.0)
    assert stunden["12"]["ab"] == pytest.approx(-1.0)


def test_kaeltester_raum_bei_art_minimum(n):
    raeume = [([(vortag(), 20.0)], 20.5), ([(vortag(), 22.0)], None)]

    stunden = n.stunden_je_tag(reihen(n, raeume=raeume, raum_art="minimum"), [TAG])[TAG.isoformat()]

    assert stunden["12"]["ab"] == pytest.approx(-0.5)


def test_haelfte_der_raeume_genuegt_fuer_die_abweichung(n):
    raeume = [
        ([(vortag(), 20.0), (zeit(14, 10), None), (zeit(16), 20.0)], None),
        ([(vortag(), 21.5)], None),
    ]

    stunden = n.stunden_je_tag(reihen(n, raeume=raeume), [TAG])[TAG.isoformat()]

    assert stunden["14"]["ab"] == pytest.approx(-0.25)
    # Ohne den ersten Raum zählt der verbliebene allein.
    assert stunden["15"]["ab"] == pytest.approx(0.5)
    assert stunden["16"]["ab"] == pytest.approx(-0.25)


def test_weniger_als_die_haelfte_der_raeume_laesst_abweichung_weg(n):
    luecke = [(vortag(), 20.0), (zeit(14, 10), None), (zeit(16), 20.0)]
    raeume = [(luecke, None), (list(luecke), None), ([(vortag(), 21.5)], None)]

    stunden = n.stunden_je_tag(reihen(n, raeume=raeume), [TAG])[TAG.isoformat()]

    assert "ab" in stunden["14"]
    assert "ab" not in stunden["15"]
    assert "ab" in stunden["16"]


def test_ausgeschalteter_thermostat_zaehlt_nicht_zur_abweichung(n):
    raeume = [([(vortag(), 20.0)], None), ([(vortag(), 17.0)], 20.0)]
    aus = [[], [(vortag(), 1.0), (zeit(12), 0.0)]]

    stunden = n.stunden_je_tag(reihen(n, raeume=raeume, aus=aus), [TAG])[TAG.isoformat()]

    # Bis 12 Uhr ist der Thermostat aus; es zählt der erste Raum gegen das Raumsoll 21.
    assert stunden["11"]["ab"] == pytest.approx(-1.0)
    assert stunden["12"]["ab"] == pytest.approx(-2.0)


def test_nur_ausgeschaltete_thermostate_ergeben_keine_abweichung(n):
    raeume = [([(vortag(), 17.0)], 20.0)]
    aus = [[(vortag(), 1.0)]]

    stunden = n.stunden_je_tag(reihen(n, raeume=raeume, aus=aus), [TAG])[TAG.isoformat()]

    assert all("ab" not in s for s in stunden.values())


def test_ausgeschalteter_thermostat_gilt_fuer_die_haelfte_als_gemeldet(n):
    luecke = [(vortag(), 20.0), (zeit(14, 10), None), (zeit(16), 20.0)]
    raeume = [(luecke, None), ([(vortag(), 17.0)], 20.0), ([(vortag(), 21.5)], None)]
    raeume.append((list(luecke), None))
    aus = [[], [(vortag(), 1.0)]]

    stunden = n.stunden_je_tag(reihen(n, raeume=raeume, aus=aus), [TAG])[TAG.isoformat()]

    # Um 15 Uhr melden zwei von vier Räumen, einer davon ausgeschaltet; es zählt der dritte allein.
    assert stunden["15"]["ab"] == pytest.approx(0.5)


def test_ohne_raeume_und_ohne_raumsoll_keine_abweichung(n):
    ohne_raeume = n.stunden_je_tag(reihen(n, raeume=[]), [TAG])[TAG.isoformat()]
    ohne_soll = n.stunden_je_tag(reihen(n, soll=[]), [TAG])[TAG.isoformat()]

    assert all("ab" not in s for s in ohne_raeume.values())
    assert all("ab" not in s for s in ohne_soll.values())


def test_abweichung_auf_zwei_stellen_gerundet(n):
    raeume = [([(vortag(), 20.123)], None), ([(vortag(), 21.0)], None)]

    stunden = n.stunden_je_tag(reihen(n, raeume=raeume), [TAG])[TAG.isoformat()]

    assert stunden["12"]["ab"] == round((20.123 - 21 + 0) / 2, 2)


def test_mehrere_tage_getrennt(n):
    zweiter = TAG + timedelta(days=1)
    at = [(vortag(), 3.0), (zeit(12, 0, zweiter), 9.0)]

    ergebnis = n.stunden_je_tag(reihen(n, at=at), [TAG, zweiter])

    assert list(ergebnis) == [TAG.isoformat(), zweiter.isoformat()]
    assert ergebnis[TAG.isoformat()]["23"]["at"] == 3.0
    assert ergebnis[zweiter.isoformat()]["12"]["at"] == 9.0


def test_umstellung_auf_sommerzeit_ohne_stunde_2(n):
    wien = ZoneInfo("Europe/Vienna")
    tag = date(2027, 3, 28)
    at = [(datetime.combine(tag - timedelta(days=1), time(23), wien), 4.0)]
    leer = n.Reihen(at=at, soll=[], vl=[], ba=[], restzeit=[], raeume=[], raum_art="mittel")

    stunden = n.stunden_je_tag(leer, [tag])[tag.isoformat()]

    assert "2" not in stunden
    assert len(stunden) == 23


def test_durchgang_bis_zum_tag(n, o):
    ruhig = TAG
    gestoert = TAG + timedelta(days=1)
    ende = datetime.combine(gestoert + timedelta(days=1), time(0), ZONE)
    restzeit = [(vortag(), 0.0), (zeit(15, 0, gestoert), 30.0), (zeit(15, 30, gestoert), 0.0)]
    tage = [ruhig, gestoert]

    def taeglich(werte):
        reihe = []
        for tag in tage:
            reihe += [(zeit(h, 0, tag), wert) for h, wert in werte]
        return [*reihe, (ende, None)]

    r = reihen(
        n,
        soll=taeglich([(0, 18.0), (6, 21.0), (22, 18.0)]),
        ba=taeglich([(0, 2.0), (6, 1.0), (22, 2.0)]),
        restzeit=restzeit,
        raeume=[(taeglich([(0, 17.0), (6, 20.0), (8, 21.4)]), None)],
    )

    ergebnis = n.stunden_je_tag(r, tage)
    erster = o.tag_aus_stunden(ruhig.isoformat(), ergebnis[ruhig.isoformat()])
    zweiter = o.tag_aus_stunden(gestoert.isoformat(), ergebnis[gestoert.isoformat()])

    assert erster.ungestoert is True
    assert erster.stunden == 24
    assert erster.morgen_min == 120
    assert erster.soll == 21.0
    # Die Vorgabe nimmt ihre Stunde und zwei Erholungsstunden heraus.
    assert (zweiter.sauber, zweiter.ungestoert) == (erster.sauber - 3, True)
