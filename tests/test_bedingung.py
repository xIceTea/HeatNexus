"""Wann ein Vorgang als laufend gilt.

Die Bedingung entscheidet, ob eine unabhängige Wärmequelle Wärme liefert und
ob an einem Pumpen-/Relaismodul abgenommen wird. Ein falsches Ja behauptet
einen Zustand der Anlage; geprüft wird deshalb vor allem, wann sie Nein sagt.
"""

from __future__ import annotations

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def bedingung():
    """Das Modul kommt ohne Home Assistant aus."""
    return load_standalone("bedingung")


# ---------------------------------------------------------------------------
# Zustand
# ---------------------------------------------------------------------------
def test_ein_eingeschalteter_zustand_gilt_als_laufend(bedingung):
    regel = {"art": "zustand", "quelle": "switch.solar"}
    assert bedingung.erfuellt(regel, {"switch.solar": "on"}) is True
    assert bedingung.erfuellt(regel, {"switch.solar": "off"}) is False


@pytest.mark.parametrize("zustand", ["unavailable", "unknown", "none", "", "0"])
def test_ohne_belastbaren_zustand_lautet_die_antwort_nein(bedingung, zustand):
    """Eine Abnahme zu behaupten, die niemand gemessen hat, wäre schlimmer."""
    regel = {"art": "zustand", "quelle": "switch.solar"}
    assert bedingung.erfuellt(regel, {"switch.solar": zustand}) is False


def test_ein_fehlender_wert_gilt_nicht_als_laufend(bedingung):
    regel = {"art": "zustand", "quelle": "switch.solar"}
    assert bedingung.erfuellt(regel, {}) is False


def test_benannte_zustaende_schliessen_alles_andere_aus(bedingung):
    """Eine Betriebsart meldet Worte, keine Schalterstellung."""
    regel = {"art": "zustand", "quelle": "sensor.art", "zustaende": ["Laden", "Nachlauf"]}
    assert bedingung.erfuellt(regel, {"sensor.art": "laden"}) is True
    assert bedingung.erfuellt(regel, {"sensor.art": "Bereitschaft"}) is False


def test_ein_klartext_ohne_benannte_zustaende_kennt_kein_aus(bedingung):
    """Ein Statustext heißt weder on noch off: Ohne Auswahl gilt jeder als an."""
    ohne = {"art": "zustand", "quelle": "sensor.status"}
    mit = {**ohne, "zustaende": ["Solaranlage aktiv"]}

    assert bedingung.erfuellt(ohne, {"sensor.status": "Solaranlage inaktiv"}) is True
    assert bedingung.erfuellt(mit, {"sensor.status": "Solaranlage inaktiv"}) is False
    assert bedingung.erfuellt(mit, {"sensor.status": "Solaranlage aktiv"}) is True


# ---------------------------------------------------------------------------
# Schwelle mit getrennter Ein- und Ausschaltgrenze
# ---------------------------------------------------------------------------
def test_die_schwelle_schaltet_ein_und_wieder_aus(bedingung):
    regel = {"art": "schwelle", "quelle": "sensor.kollektor", "ein": 60, "aus": 45}
    assert bedingung.erfuellt(regel, {"sensor.kollektor": "61"}) is True
    assert bedingung.erfuellt(regel, {"sensor.kollektor": "44"}, lief=True) is False


def test_zwischen_den_schwellen_bleibt_es_beim_bisherigen(bedingung):
    """Ohne Zwischenbereich flattert die Anzeige an der Grenze."""
    regel = {"art": "schwelle", "quelle": "sensor.kollektor", "ein": 60, "aus": 45}
    werte = {"sensor.kollektor": "50"}
    assert bedingung.erfuellt(regel, werte, lief=True) is True
    assert bedingung.erfuellt(regel, werte, lief=False) is False


def test_eine_umgekehrte_schwelle_meldet_unterschreitung(bedingung):
    """Liegt die Ausschaltgrenze höher, ist „darunter" gemeint."""
    regel = {"art": "schwelle", "quelle": "sensor.puffer_unten", "ein": 40, "aus": 50}
    assert bedingung.erfuellt(regel, {"sensor.puffer_unten": "38"}) is True
    assert bedingung.erfuellt(regel, {"sensor.puffer_unten": "52"}, lief=True) is False


def test_ohne_ausschaltgrenze_genuegt_die_eine(bedingung):
    regel = {"art": "schwelle", "quelle": "sensor.kollektor", "ein": 60}
    assert bedingung.erfuellt(regel, {"sensor.kollektor": "60"}) is True
    assert bedingung.erfuellt(regel, {"sensor.kollektor": "59"}) is False


# ---------------------------------------------------------------------------
# Differenz
# ---------------------------------------------------------------------------
def test_die_differenz_zweier_fuehler_traegt_die_solarregel(bedingung):
    """Kollektor minus Puffer unten – so arbeitet jeder Solarregler."""
    regel = {
        "art": "differenz",
        "quelle": "sensor.kollektor",
        "gegen": "sensor.puffer_unten",
        "ein": 8,
        "aus": 3,
    }
    werte = {"sensor.kollektor": "70", "sensor.puffer_unten": "60"}
    assert bedingung.erfuellt(regel, werte) is True
    assert bedingung.erfuellt(regel, {**werte, "sensor.kollektor": "62"}, lief=True) is False


def test_fehlt_der_gegenwert_gilt_die_differenz_nicht(bedingung):
    regel = {"art": "differenz", "quelle": "sensor.a", "gegen": "sensor.b", "ein": 8}
    assert bedingung.erfuellt(regel, {"sensor.a": "70"}) is False


# ---------------------------------------------------------------------------
# Unvollständige Angaben
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "regel",
    [
        {},
        {"art": "schwelle"},
        {"art": "erfunden", "quelle": "sensor.a"},
        {"art": "schwelle", "quelle": "sensor.a"},
        {"art": "differenz", "quelle": "sensor.a", "ein": 8},
    ],
)
def test_eine_unvollstaendige_regel_meldet_nie_laufend(bedingung, regel):
    assert bedingung.vollstaendig(regel) is False
    assert bedingung.erfuellt(regel, {"sensor.a": "99"}) is False


def test_die_quellen_werden_zum_abruf_gemeldet(bedingung):
    """Die Entitäten müssen bekannt sein, sonst hört niemand auf ihre Änderung."""
    regel = {"art": "differenz", "quelle": "sensor.a", "gegen": "sensor.b", "ein": 8}
    assert bedingung.quellen(regel) == ["sensor.a", "sensor.b"]
    assert bedingung.quellen({"art": "zustand", "quelle": "switch.x"}) == ["switch.x"]


# ---------------------------------------------------------------------------
# Beschreibung für den Dialog
# ---------------------------------------------------------------------------
def test_die_regel_laesst_sich_als_satz_lesen(bedingung):
    regel = {
        "art": "differenz",
        "quelle": "sensor.kollektor",
        "gegen": "sensor.puffer",
        "ein": 8,
        "aus": 3,
    }
    satz = bedingung.beschreibung(
        regel, {"sensor.kollektor": "Kollektor", "sensor.puffer": "Puffer"}
    )
    assert satz == "Kollektor minus Puffer erreicht 8, endet bei 3"
    assert bedingung.beschreibung({}) == "unvollständig"
