"""Rechnungen der Automatik ohne Home Assistant: Stundenwerte.

Geprüft wird die Stundenabfrage per Bisektion gegen die lineare Fassung.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import random

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def eingaben():
    load_standalone("automatik")
    return load_standalone("automatik.eingaben")


def zufallsreihe(zufall: random.Random, anfang: datetime, stunden: int) -> list:
    """Werte in unregelmäßigen Abständen, mit Lücken, doppelten Zeiten und `None`."""
    reihe, zeit = [], anfang - timedelta(minutes=zufall.randint(0, 90))
    ende = anfang + timedelta(hours=stunden)
    while zeit < ende:
        wert = None if zufall.random() < 0.1 else round(zufall.uniform(15, 25), 2)
        reihe.append((zeit, wert))
        if zufall.random() < 0.05:
            reihe.append((zeit, round(zufall.uniform(15, 25), 2)))
        sprung = zufall.choice([1, 5, 17, 30, 59, 60, 61, 120, 400])
        zeit += timedelta(minutes=sprung, seconds=zufall.randint(0, 59))
    return reihe


@pytest.mark.parametrize("saat", range(8))
def test_stundenreihe_gleicht_der_linearen_rechnung(eingaben, saat):
    zufall = random.Random(saat)
    anfang = datetime(2026, 10, 1, tzinfo=UTC)
    reihe = zufallsreihe(zufall, anfang, 72)
    schnell = eingaben.Stundenreihe(reihe)

    for h in range(-2, 75):
        stunde = anfang + timedelta(hours=h)
        assert schnell.mittel(stunde) == eingaben.mittel_der_stunde(reihe, stunde)
        assert schnell.zur_stunde(stunde) == eingaben.wert_zur_stunde(reihe, stunde)


def test_stundenreihe_ohne_werte(eingaben):
    leer = eingaben.Stundenreihe([])
    stunde = datetime(2026, 10, 1, tzinfo=UTC)
    assert leer.mittel(stunde) is None
    assert leer.zur_stunde(stunde) is None


SPRECHENDE_NAMEN = {
    ("sensor", "automatik_abweichung"): "Abstand zum Raumziel",
    ("sensor", "automatik_system_raeume"): "Mittlere Raumtemperatur",
    ("sensor", "automatik_system_sonnentag_heute"): "Dauer Sonnentag heute",
    ("sensor", "automatik_system_nur_ww_heute"): "Dauer nur Warmwasser heute",
    ("sensor", "automatik_system_vorrang_heute"): "Laufzeit Vorrangquelle heute",
    ("binary_sensor", "automatik_system_ueber_heizgrenze"): "Außentemperatur über Heizgrenze",
}


def test_automatik_werte_nennen_ihre_groesse():
    import json
    from pathlib import Path

    ordner = Path(__file__).parents[1] / "custom_components" / "heatnexus" / "translations"
    deutsch = json.loads((ordner / "de.json").read_text(encoding="utf-8"))["entity"]

    for (plattform, schluessel), name in SPRECHENDE_NAMEN.items():
        assert deutsch[plattform][schluessel]["name"] == name
    for schluessel in ("automatik_zustand", "automatik_empfehlung"):
        assert deutsch["sensor"][schluessel]["state"]["sicherheit"] == "Sicherheitsregel aktiv"
