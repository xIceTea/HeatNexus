"""Wertparsing: fehlende Werte dürfen niemals als 0 durchgehen."""

from __future__ import annotations

import pytest


def test_decimals_survive(helpers):
    assert helpers.parse_value("45.7", float) == pytest.approx(45.7)


def test_int_parsing_truncates_float_strings(helpers):
    assert helpers.parse_value("45.7", int) == 45


def test_missing_value_is_none(helpers):
    assert helpers.parse_value(None, float) is None


@pytest.mark.parametrize("raw", ["-.-", "-", "", "kaputt"])
def test_invalid_values_are_none(helpers, raw):
    assert helpers.parse_value(raw, float) is None


class _Coordinator:
    def __init__(self, oids):
        self.data = {"oids": oids}


def test_get_oid_value_uses_prefix(helpers):
    coordinator = _Coordinator({"/1/15/0/1/1/0": "21.5"})
    assert helpers.get_oid_value(coordinator, "/1/1/0", "/1/15/0") == pytest.approx(21.5)


def test_get_oid_value_missing_returns_none_not_zero(helpers):
    coordinator = _Coordinator({})
    assert helpers.get_oid_value(coordinator, "/1/1/0", "/1/15/0") is None


# ---------------------------------------------------------------------------
# Paketaufbau
#
# In 1.2.0-beta.1 scheiterte die Einrichtung mit
# „module 'custom_components.heatnexus.time' has no attribute 'monotonic'".
# Ursache: `__init__.py` *ist* der Namensraum des Pakets. Importiert Home
# Assistant die Plattform `heatnexus.time`, setzt Python sie als Attribut
# `time` auf das Paket und überschreibt damit das dortige `import time`.
# Ob es knallte, hing am Wettlauf zwischen Plattform-Import und Einrichtung –
# deshalb fiel es monatelang nicht auf.
# ---------------------------------------------------------------------------
def test_init_importiert_kein_modul_wie_eine_eigene_datei():
    """Kein Name in `__init__.py` darf so heißen wie eine Nachbardatei."""
    import ast
    from pathlib import Path

    ordner = Path(__file__).parent.parent / "custom_components" / "heatnexus"
    nachbarn = {p.stem for p in ordner.glob("*.py")} - {"__init__"}

    baum = ast.parse((ordner / "__init__.py").read_text(encoding="utf-8"))
    namen: set[str] = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            for teil in knoten.names:
                namen.add((teil.asname or teil.name).split(".")[0])
        elif isinstance(knoten, ast.ImportFrom) and knoten.level == 0:
            namen.update((teil.asname or teil.name) for teil in knoten.names)

    kollision = namen & nachbarn
    assert not kollision, (
        f"{sorted(kollision)} heißt wie eine Datei des Pakets und wird beim "
        "Laden der gleichnamigen Plattform überschrieben. Abhilfe: "
        "`from x import y` statt `import x`, oder `import x as z`."
    )


# ---------------------------------------------------------------------------
# object-Endpunkt: nicht jede Liste ist ein Zeitprogramm
#
# An der Anlage gemessen (PuroWIN, 518 Datenpunkte): `typeId 30` steht für
# „über den object-Endpunkt lesen", nicht für „Zeitprogramm". Erst `subtypeId`
# sagt, was drinsteht – 14 Zeitprogramm, 9 Text, 10 Funktionsliste. Die
# Funktionsliste ist ebenfalls eine Liste von Objekten und ging vorher als
# Zeitprogramm durch.
# ---------------------------------------------------------------------------
def test_nur_echte_zeitprogramme_gelten_als_zeitprogramm():
    from pathlib import Path

    pfad = Path(__file__).parent.parent / "custom_components" / "heatnexus" / "client.py"
    quelle = pfad.read_text(encoding="utf-8")
    # Nur die Funktion laden – der Rest des Moduls zieht aiohttp nach.
    anfang = quelle.index("def _ist_zeitprogramm")
    ende = quelle.index("class WindhagerHttpClient")
    raum: dict = {}
    exec(compile(quelle[anfang:ende], str(pfad), "exec"), raum)
    ist_zeitprogramm = raum["_ist_zeitprogramm"]

    assert ist_zeitprogramm(
        [{"weekdays": ["Mo"], "switchPoints": [{"time": "06:00", "value": 21}]}]
    )
    assert ist_zeitprogramm([{"switchPoints": []}])
    # Die Funktionsliste eines Knotens – /1/60/0/4/1/0
    assert not ist_zeitprogramm([{"fctType": 25, "lock": False}])
    # Text – /1/60/0/12/38/0 meldet "PW 400"
    assert not ist_zeitprogramm("PW 400")
    assert not ist_zeitprogramm([])
    assert not ist_zeitprogramm(None)
