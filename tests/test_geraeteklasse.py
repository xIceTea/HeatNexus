"""Modellbezeichnung je Geräteklasse.

Die Geräteklasse steht in der `programId` eines Knotens (Stellen 6 bis 10).
Unter demselben Funktionstyp melden sich verschiedene Kessel; die Klasse
trennt sie, wo der Funktionstyp allein das Gerät nicht benennt.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import load_standalone

KOMPONENTE = Path(__file__).parent.parent / "custom_components" / "heatnexus"


@pytest.fixture(scope="module")
def geraete():
    return load_standalone("geraete")


@pytest.mark.parametrize(
    ("program_id", "klasse"),
    [
        ("90010020090a0501", "2009"),
        ("9001001D010A0506", "1d01"),
        (None, None),
        ("", None),
        ("900100", None),
        ("9001xyz9090a0501", None),
    ],
)
def test_die_klasse_steht_in_der_program_id(geraete, program_id, klasse):
    assert geraete.geraeteklasse(program_id) == klasse


def test_der_logwin_heisst_nach_seiner_klasse(geraete):
    assert geraete.modell(10, "2009") == "LogWIN Holzvergaserkessel"


@pytest.mark.parametrize("klasse", [None, "", "1415"])
def test_ohne_eigene_klasse_bleibt_das_modell_des_funktionstyps(geraete, klasse):
    assert geraete.modell(10, klasse) == "Automatik-/Zusatzkessel"


def test_ein_unbekannter_funktionstyp_hat_kein_modell(geraete):
    assert geraete.modell(99, "2009") is None


def test_die_klasse_gilt_nur_fuer_ihren_funktionstyp(geraete):
    assert geraete.modell(9, "2009") == geraete.MODELLE[9]


def test_jede_klasse_mit_eigenem_modell_ist_beim_hersteller_belegt(geraete):
    """Nur Klassen, für die der Hersteller eine eigene Ebenenliste führt."""
    db = json.loads((KOMPONENTE / "device_db.json").read_text(encoding="utf-8"))
    for (fct_type, klasse), _modell in geraete.MODELLE_JE_KLASSE.items():
        assert klasse in db["layers"][str(fct_type)].get("devices", []), (fct_type, klasse)
