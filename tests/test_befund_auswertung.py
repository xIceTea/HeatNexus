"""Auswertung des Befunds: Abschnitte je Anlage, Zählung der Lage, fehlende Daten mit Grund."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def m():
    load_standalone("befund")
    return load_standalone("befund.auswertung"), load_standalone("befund.archiv")


def kontext(aus, raeume=("climate.a",), kessel=True):
    kreis = aus.Kreis("hk", "UMLZ", list(raeume), ta_heiz=18.0, ta_absenk=5.0)
    liste = [aus.Kessel("k", "PuroWIN", 40.0, (6585.0, 18201.0))] if kessel else []
    return aus.Kontext("DE", [kreis], liste, waermequelle_extern=not kessel)


def gefuellt(arch):
    """Dreißig Tage, die von 22 auf 7 °C abkühlen; geheizt wird unter 17 °C von 6 bis 22 Uhr."""
    archiv = arch.Archiv()
    t = datetime(2026, 9, 1, 0, 0)
    for h in range(24 * 30):
        zeit = t + timedelta(hours=h)
        at = 22.0 - h / 48
        heizt = at < 17 and 6 <= zeit.hour < 22
        archiv.messen(
            "hk",
            zeit,
            {
                "at": at,
                "vl": 45.0 if heizt else 0.0,
                "vi": 45.0,
                "soll": 21.0,
                "eingriff": False,
                "raeume": {"climate.a": [21.1, 21.0]},
            },
        )
        archiv.messen_kessel("k", zeit, {"starts": 100 + h // 24, "bh": 300 + h // 12, "kw": 4.0})
    return archiv


def test_abschnitte_mit_kessel(m):
    aus, arch = m
    ergebnis = aus.anlage(gefuellt(arch), kontext(aus))
    assert [a["art"] for a in ergebnis["abschnitte"]] == ["haus", "heizkreis", "kessel"]
    assert ergebnis["abschnitte"][0]["kennung"] == "hk"
    assert ergebnis["lage"]["befunde"] == 8
    assert ergebnis["lage"]["seit"] == "2026-09-01"


def test_heizgrenze_mit_vergleich(m):
    aus, arch = m
    haus = aus.anlage(gefuellt(arch), kontext(aus))["abschnitte"][0]
    grenze = next(b for b in haus["befunde"] if b["art"] == "heizgrenze")
    assert grenze["vergleich"] == {"eingestellt": 18.0}
    kessel = aus.anlage(gefuellt(arch), kontext(aus))["abschnitte"][-1]
    energie = next(b for b in kessel["befunde"] if b["art"] == "energie")
    assert energie["vergleich"]["rechengrenze"] == 15.0


def test_ohne_kessel_verweis_auf_waermeerzeuger(m):
    aus, arch = m
    ergebnis = aus.anlage(gefuellt(arch), kontext(aus, kessel=False))
    assert ergebnis["abschnitte"][-1]["art"] == "waermeerzeuger"


def test_ohne_raeume_brauchen_raumbefunde_daten(m):
    aus, arch = m
    ergebnis = aus.anlage(gefuellt(arch), kontext(aus, raeume=()))
    heizkreis = next(a for a in ergebnis["abschnitte"] if a["art"] == "heizkreis")
    status = {b["art"]: b["status"] for b in heizkreis["befunde"]}
    assert status["raeume"] == "braucht_daten"
    assert status["naechte"] == "braucht_daten"
    assert ergebnis["lage"]["braucht_daten"] == 3


def test_leeres_archiv(m):
    aus, arch = m
    ergebnis = aus.anlage(arch.Archiv(), kontext(aus))
    assert ergebnis["lage"]["seit"] is None
    assert ergebnis["lage"]["befunde"] == 8


def test_waermespeicher_ohne_laufende_automatik_nennt_den_grund(m):
    aus, arch = m
    haus = aus.anlage(gefuellt(arch), kontext(aus))["abschnitte"][0]
    speicher = haus["befunde"][0]
    assert speicher["status"] == "braucht_daten"
    assert speicher["grund"] == "automatik"


def test_versorgte_heiztage_zaehlen_beim_kessel(m):
    aus, arch = m
    archiv = gefuellt(arch)
    kreis = aus.Kreis("leer", "Heizhaus", [])
    kessel = aus.Kessel("k", "PuroWIN", 40.0, (6585.0, 18201.0))
    ohne = aus.anlage(archiv, aus.Kontext("DE", [kreis], [kessel]))
    versorgt = aus.heiztage(archiv, ["hk"])
    mit = aus.anlage(archiv, aus.Kontext("DE", [kreis], [kessel], versorgte_heiztage=versorgt))
    lauf = {
        name: next(b for b in e["abschnitte"][-1]["befunde"] if b["art"] == "laufzeit")
        for name, e in (("ohne", ohne), ("mit", mit))
    }
    assert lauf["ohne"]["angaben"]["starts"] == 0
    assert lauf["mit"]["angaben"]["starts"] > 0


def test_kessel_vergleicht_starts_mit_und_ohne_automatik(m):
    aus, arch = m
    archiv = gefuellt(arch)
    befunde = aus.anlage(archiv, kontext(aus))["abschnitte"][-1]["befunde"]
    assert [b["art"] for b in befunde] == ["laufzeit", "starts", "energie"]


def test_eingriffstage_der_mitversorgten_zaehlen_beim_kessel(m):
    aus, arch = m
    archiv = gefuellt(arch)
    tage = aus.eingriffstage(archiv, ["hk"])
    assert tage and set(tage.values()) == {None}
