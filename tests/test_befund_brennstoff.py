"""Brennstoff-Reichweite: Verbrauch je Tag, Vorrat, Lieferungen mit Korrektur, Datum „reicht bis“."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from .conftest import load_standalone

HEUTE = date(2026, 11, 20)


@pytest.fixture(scope="module")
def bs():
    load_standalone("befund")
    return load_standalone("befund.brennstoff")


def tage(anzahl: int, ende: date = HEUTE, **werte) -> list[str]:
    return [(ende - timedelta(days=anzahl - i)).isoformat() for i in range(anzahl)]


def test_art_und_weise_je_baureihe(bs):
    assert bs.art_von(9, None) == "pellets"
    assert bs.art_von(25, 0) == "hackgut"
    assert bs.art_von(25, 2) == "pellets"
    assert bs.art_von(10, None) == "scheitholz"
    assert bs.weise_von(9, hat_zaehler=True) == "zaehler"
    assert bs.weise_von(9, hat_zaehler=False) == "waerme"
    assert bs.weise_von(25, hat_zaehler=False) == "waerme"
    assert bs.weise_von(10, hat_zaehler=True) == "anheizen"
    assert bs.EINHEIT == {"pellets": "t", "hackgut": "Srm", "scheitholz": "Rm"}


def test_heizwerte_nach_lwf(bs):
    assert bs.HEIZWERT == {"pellets": 4800.0, "hackgut": 745.0, "scheitholz": 1885.0}
    assert bs.fuellmenge(18.0) == 50.0
    assert bs.fuellmenge(35.6) == 64.0


def test_verbrauch_aus_waerme(bs):
    tage_k = {d: {"kwh": 120.0} for d in tage(3)}
    lager = {"art": "hackgut", "weise": "waerme"}
    verbrauch = bs.tagesverbrauch(lager, tage_k, {})
    assert verbrauch[tage(1)[0]] == pytest.approx(120 / (0.9 * 745), abs=1e-4)


def test_verbrauch_aus_zaehler_der_steuerung(bs):
    zaehler = dict(zip(tage(4), [11.50, 11.53, 11.53, 11.58], strict=True))
    verbrauch = bs.tagesverbrauch({"art": "pellets", "weise": "zaehler"}, {}, zaehler)
    assert list(verbrauch.values()) == pytest.approx([0.03, 0.0, 0.05])


def test_verbrauch_aus_anheizvorgaengen(bs):
    zaehler = dict(zip(tage(3), [20.0, 22.0, 23.0], strict=True))
    lager = {"art": "scheitholz", "weise": "anheizen", "fuellmenge": 48.8}
    verbrauch = bs.tagesverbrauch(lager, {}, zaehler)
    assert list(verbrauch.values()) == pytest.approx([0.2, 0.1])


def test_zaehlersprung_zaehlt_nicht(bs):
    zaehler = dict(zip(tage(3), [11.50, 0.0, 0.02], strict=True))
    verbrauch = bs.tagesverbrauch({"art": "pellets", "weise": "zaehler"}, {}, zaehler)
    assert list(verbrauch.values()) == pytest.approx([0.02])


def test_korrektur_wirkt_auf_den_verbrauch(bs):
    tage_k = {d: {"kwh": 120.0} for d in tage(2)}
    lager = {"art": "hackgut", "weise": "waerme", "korrekturen": [1.2, 1.4]}
    verbrauch = bs.tagesverbrauch(lager, tage_k, {})
    assert next(iter(verbrauch.values())) == pytest.approx(1.3 * 120 / (0.9 * 745), abs=1e-4)


def test_bestand_zieht_verbrauch_seit_lieferung_ab(bs):
    lager = {"bestand": 10.0, "seit": "2026-11-17"}
    verbrauch = {"2026-11-16": 1.0, "2026-11-18": 0.5, "2026-11-19": 0.5}
    assert bs.bestand(lager, verbrauch) == pytest.approx(9.0)
    assert bs.bestand({}, verbrauch) is None


def test_lieferung_mit_rest_lernt_korrektur(bs):
    lager = {"art": "hackgut", "weise": "waerme", "bestand": 10.0, "seit": "2026-11-01"}
    roh = {"2026-11-05": 2.0, "2026-11-10": 2.0}
    neu = bs.geliefert(lager, 30.0, 4.0, HEUTE, roh)
    # Tatsächlich 6 Srm verbraucht, gerechnet 4 Srm: Korrektur 1,5.
    assert neu["korrekturen"] == [1.5]
    assert neu["bestand"] == 34.0
    assert neu["seit"] == "2026-11-20"
    assert neu["lieferungen"][-1] == {"tag": "2026-11-20", "menge": 30.0, "rest": 4.0}
    assert lager["bestand"] == 10.0


def test_korrektur_begrenzt_und_nur_drei(bs):
    lager = {"bestand": 10.0, "seit": "2026-11-01", "korrekturen": [1.0, 1.1, 1.2]}
    neu = bs.geliefert(lager, 5.0, 0.0, HEUTE, {"2026-11-05": 1.0})
    assert neu["korrekturen"] == [1.1, 1.2, 2.0]


def test_lieferung_ohne_rest_rechnet_weiter(bs):
    lager = {"bestand": 10.0, "seit": "2026-11-01", "korrekturen": [1.2]}
    neu = bs.geliefert(lager, 5.0, None, HEUTE, {"2026-11-05": 2.0}, aktuell=8.0)
    assert neu["bestand"] == 13.0
    assert neu["korrekturen"] == [1.2]


def test_reicht_bis_aus_mittel_der_letzten_tage(bs):
    lager = {"art": "hackgut", "weise": "waerme", "bestand": 10.0, "seit": "2026-11-01"}
    je_tag = 120 / (0.9 * 745)
    verbrauch = {d: je_tag for d in tage(14)}
    b = bs.befund(lager | {"bestand": 10.0 + 14 * je_tag}, verbrauch, HEUTE)
    assert b.art == "brennstoff"
    assert b.wert == 56.0
    assert b.angaben["datum"] == (HEUTE + timedelta(days=56)).isoformat()
    assert b.angaben["einheit"] == "Srm"
    assert b.stufe == "vorlaeufig"


def test_ohne_vorrat_braucht_daten(bs):
    assert bs.befund({"art": "pellets"}, {}, HEUTE).grund == "vorrat"


def test_bald_leer_ist_hinweis(bs):
    lager = {"art": "pellets", "weise": "zaehler", "bestand": 0.3, "seit": HEUTE.isoformat()}
    verbrauch = {d: 0.05 for d in tage(14)}
    b = bs.befund(lager, verbrauch, HEUTE)
    assert b.wert == 6.0
    assert b.status == "hinweis"
    assert b.stufe == "belastbar"


def test_ohne_verbrauch_ruht(bs):
    lager = {"art": "pellets", "weise": "zaehler", "bestand": 3.0, "seit": HEUTE.isoformat()}
    b = bs.befund(lager, {d: 0.0 for d in tage(14)}, HEUTE)
    assert b.wert is None
    assert b.angaben["ruht"] is True


def test_vorjahr_ueberspringt_den_sommer(bs):
    heute = date(2027, 4, 1)
    verbrauch = {}
    for i in range(380, 0, -1):
        tag = heute - timedelta(days=i)
        verbrauch[tag.isoformat()] = 0.05 if tag.month in (10, 11, 12, 1, 2, 3, 4) else 0.002
    lager = {"art": "pellets", "weise": "zaehler", "bestand": 2.0, "seit": "2026-01-01"}
    b = bs.befund(
        lager | {"bestand": 2.0 + sum(v for d, v in verbrauch.items() if d > "2026-01-01")},
        verbrauch,
        heute,
    )
    assert b.angaben["vorjahr"] is True
    assert b.angaben["datum"] > "2027-10-01"
