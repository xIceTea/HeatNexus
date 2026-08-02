"""Wertparsing: fehlende Werte dürfen niemals als 0 durchgehen."""

from __future__ import annotations

import re

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


# ---------------------------------------------------------------------------
# Oberfläche nach einem Update
#
# Bis 1.2.0-beta.4 zeigte die Seitenleiste nach einer Aktualisierung die alte
# Ansicht, bis jemand Strg+Umschalt+R drückte. Der Dateipfad trug die Fassung
# schon, der Name des Anzeigeelements aber nicht – und ein Element lässt sich
# im Browser nur einmal je Seitensitzung anmelden. Die neue Datei übersprang
# also die Anmeldung, und die alte Klasse zeichnete weiter.
# ---------------------------------------------------------------------------
def _const():
    from .conftest import load_standalone

    return load_standalone("const")


def test_pfad_und_element_tragen_dieselbe_fassung():
    const = _const()
    for version in ("1.2.0", "1.2.0-beta.5", "", None):
        fassung = const.panel_fassung(version)
        assert fassung in const.panel_js_pfad(version)
        assert const.panel_element(version).endswith(fassung)
        # Ein Elementname muss einen Bindestrich enthalten und darf keine
        # Zeichen führen, die der Browser ablehnt.
        assert re.fullmatch(r"[a-z][a-z0-9]*(-[a-z0-9]+)+", const.panel_element(version))


def test_verschiedene_fassungen_ergeben_verschiedene_elemente():
    const = _const()
    assert const.panel_element("1.2.0-beta.4") != const.panel_element("1.2.0-beta.5")


def test_die_oberflaeche_leitet_denselben_namen_ab():
    """Die Datei im Browser muss zum Namen der Integration passen.

    Sie kennt ihre Fassung nur aus ihrer eigenen Adresse; stimmt das Muster
    nicht mit `panel_js_pfad` überein, meldet sie ein anderes Element an als
    das, welches die Integration anfordert – und die Seite bliebe leer.
    """
    from pathlib import Path

    const = _const()
    datei = Path(__file__).parent.parent / "custom_components" / "heatnexus" / "frontend"
    quelle = (datei / "heatnexus-panel.js").read_text(encoding="utf-8")

    # Das Suchmuster steht als JavaScript-Literal zwischen zwei Schrägstrichen.
    treffer = re.search(r"import\.meta\.url\.match\(/(.+?)/\)", quelle)
    assert treffer, "Die Oberfläche leitet ihren Elementnamen nicht mehr aus der Adresse ab"
    muster = re.compile(treffer.group(1))

    version = "1.2.0-beta.5"
    pfad = const.panel_js_pfad(version)
    gefunden = muster.search(pfad)
    assert gefunden, f"Das Muster der Oberfläche greift nicht auf {pfad}"
    assert f"heatnexus-panel-{gefunden.group(1)}" == const.panel_element(version)


# ---------------------------------------------------------------------------
# Meldungen zum Einlesen
#
# „HeatNexus ist bereit" erschien auch mit abgewählter Option: Die
# Fortschrittsmeldung prüfte sie, die Abschlussmeldung nicht. Beide teilen sich
# eine Kennung, die zweite ersetzt also die erste – fehlt die erste, erscheint
# die zweite aus dem Nichts.
# ---------------------------------------------------------------------------
def test_meldung_nur_mit_haken():
    import ast
    from pathlib import Path

    pfad = Path(__file__).parent.parent / "custom_components" / "heatnexus" / "__init__.py"
    quelle = pfad.read_text(encoding="utf-8")
    anfang = quelle.index("def meldung_erwuenscht")
    ende = quelle.index("def _einlesen_melden")
    raum: dict = {"CONF_MELDUNG_EINLESEN": "meldung_einlesen"}
    exec(compile(quelle[anfang:ende], str(pfad), "exec"), raum)
    erwuenscht = raum["meldung_erwuenscht"]

    assert erwuenscht({"meldung_einlesen": True}) is True
    assert erwuenscht({"meldung_einlesen": False}) is False
    assert erwuenscht({}) is False
    assert erwuenscht(None) is False

    # Und beide Meldungen fragen wirklich dieselbe Stelle.
    baum = ast.parse(quelle)
    aufrufe = [
        k.func.id
        for k in ast.walk(baum)
        if isinstance(k, ast.Call) and isinstance(k.func, ast.Name)
    ]
    assert aufrufe.count("meldung_erwuenscht") == 2, (
        "Fortschritts- und Abschlussmeldung müssen beide die Option prüfen"
    )
