"""Rechnungen der Automatik mit Home Assistant: Lernstunden, gemeinsamer Verlauf, Ziel der Stunde.

Die Lernstunden werden gegen die lineare Rechnung geprüft, die Aufzeichnung ist eine Attrappe.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import random
import time

import pytest

from .conftest import requires_ha
from .test_automatik_rechnung import zufallsreihe

pytestmark = requires_ha()

ANFANG = datetime(2026, 10, 1, tzinfo=UTC)


def _linear(reihen, art, raum_art, zeiten, boegen):
    """Die Lernstunden wie vor der Bisektion: jede Abfrage durchläuft die ganze Reihe."""
    from custom_components.heatnexus.automatik import eingaben, hausmodell, tagesansicht

    raum = [
        eingaben.raumwert([eingaben.mittel_der_stunde(r, z) for r in reihen.raeume], raum_art)
        for z in zeiten
    ]
    ganz = []
    for z, r in zip(zeiten, raum, strict=True):
        at = eingaben.mittel_der_stunde(reihen.at, z)
        quelle = eingaben.mittel_der_stunde(reihen.heizen, z)
        if r is None or at is None or quelle is None:
            ganz.append(None)
            continue
        wolken = eingaben.wert_zur_stunde(reihen.wolken, z)
        bogen = boegen.get(z.date())
        sonne = 0.0 if bogen is None else tagesansicht.sonnenanteil(z.hour, *bogen, wolken)
        heizen = quelle if art == "pumpe" else max(0.0, quelle - r)
        wind = eingaben.wert_zur_stunde(reihen.wind, z)
        ganz.append(hausmodell.Stunde(r, None, at, sonne, wind, heizen))
    ergebnis = {}
    for i, stunde in enumerate(ganz[:-1]):
        if stunde is not None:
            danach = raum[i + 1] if ganz[i + 1] is not None else None
            ergebnis.setdefault(zeiten[i].date(), []).append(replace(stunde, raum_danach=danach))
    return ergebnis


def _zufallsreihen(saat: int, stunden: int):
    from custom_components.heatnexus.automatik.vorausschau import Reihen

    zufall = random.Random(saat)
    return Reihen(
        [zufallsreihe(zufall, ANFANG, stunden) for _ in range(3)],
        *(zufallsreihe(zufall, ANFANG, stunden) for _ in range(4)),
    )


@pytest.mark.parametrize(("saat", "art"), [(1, "vorlauf"), (2, "pumpe"), (3, "vorlauf")])
@pytest.mark.parametrize("raum_art", ["mittel", "minimum"])
def test_lernstunden_gleichen_der_linearen_rechnung(saat, art, raum_art):
    from custom_components.heatnexus.automatik.vorausschau import lernstunden

    reihen = _zufallsreihen(saat, 96)
    zeiten = [ANFANG + timedelta(hours=h) for h in range(97)]
    boegen = {(ANFANG + timedelta(days=t)).date(): (7.5, 18.25) for t in range(4)}

    assert lernstunden(reihen, art, raum_art, zeiten, boegen) == _linear(
        reihen, art, raum_art, zeiten, boegen
    )


def test_lernstunden_aus_minutenwerten_blockieren_nicht():
    from custom_components.heatnexus.automatik.vorausschau import Reihen, lernstunden

    # Ein Fühler mit Minutentakt über vierzehn Tage, je Raum, Außentemperatur und Vorlauf.
    minuten = [(ANFANG + timedelta(minutes=i), 20.0 + i % 7 / 10) for i in range(14 * 24 * 60)]
    reihen = Reihen([minuten, minuten, minuten], minuten, minuten, [], [])
    zeiten = [ANFANG + timedelta(hours=h) for h in range(14 * 24 + 1)]

    beginn = time.perf_counter()
    stunden = lernstunden(reihen, "vorlauf", "mittel", zeiten, {})
    dauer = time.perf_counter() - beginn

    assert sum(len(s) for s in stunden.values()) == 14 * 24
    assert dauer < 1.0
