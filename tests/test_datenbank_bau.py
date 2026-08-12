"""Der Generator der Geräte-Datenbank: Zusammenführen der Namenslisten.

Drei Listen liefern Datenpunktnamen, geordnet nach Verlässlichkeit. Geprüft
wird die Regel, nach der sie sich überlagern — ein leerer Eintrag der
verlässlicheren Liste darf einen vorhandenen Namen nicht verdrängen.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest

WERKZEUG = Path(__file__).resolve().parents[1] / "tools" / "build_device_db.py"


@pytest.fixture(scope="module")
def generator() -> ModuleType:
    """Den Generator ohne Netzzugriff aus der Datei laden."""
    spec = importlib.util.spec_from_file_location("heatnexus_datenbankbau", WERKZEUG)
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


def test_ein_leerer_name_verdraengt_keinen_vorhandenen(generator):
    """Die reguläre Liste hat Vorrang – aber nur, wo sie etwas zu sagen hat."""
    namen = generator.sammle_namen(
        {"oids": {"52/113": "", "0/7": "Kesseltemperatur"}},
        {"oids_oem": {"52/113": "TerraWIN Heat Circuit Use Excess Energy"}},
    )
    assert namen["52/113"] == "TerraWIN Heat Circuit Use Excess Energy"
    assert namen["0/7"] == "Kesseltemperatur"


def test_die_regulaere_liste_gewinnt_wo_sie_etwas_sagt(generator):
    """Dort steht der Name, der auch am Bedienteil erscheint."""
    namen = generator.sammle_namen(
        {"oids": {"0/7": "Kesseltemperatur Ist"}},
        {"oids_oem": {"0/7": "Boiler temperature"}},
    )
    assert namen["0/7"] == "Kesseltemperatur Ist"


def test_nur_leerzeichen_zaehlt_als_leer(generator):
    namen = generator.sammle_namen(
        {"oids": {"52/0": "   "}},
        {"oids_oem": {"52/0": "AEW Evo Actual power consumtion"}},
    )
    assert namen["52/0"] == "AEW Evo Actual power consumtion"
