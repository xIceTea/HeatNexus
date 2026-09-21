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


# Eine Ebenendatei in der Form des Herstellers: Datenpunkte einzeln oder in
# Gruppen, die Merkmale am Eintrag, eine Geräteklasse neben `default`.
EBENEN_MIT_MERKMALEN = {
    "default/9": {
        "info": [
            {"oid": "4/92", "endpoint": "object"},
            {"oid": "23/100", "type": "reset", "reset": "0.00"},
        ],
        "service": [{"group_name": "G", "parameters": [{"oid": "42/18", "restart": True}]}],
    },
    "1415/9": {"operate": [{"oid": "4/93", "endpoint": "object"}]},
}


def test_objekt_datenpunkte_kommen_aus_allen_klassen(generator):
    """Ob ein Datenpunkt ein Objekt ist, hängt an ihm, nicht an der Klasse."""
    ebenen = generator.sammle_ebenen(EBENEN_MIT_MERKMALEN, {})
    assert ebenen["9"]["objekte"] == ["4/92", "4/93"]


def test_ruecksetzwerte_werden_uebernommen(generator):
    ebenen = generator.sammle_ebenen(EBENEN_MIT_MERKMALEN, {})
    assert ebenen["9"]["ruecksetzen"] == {"23/100": "0.00"}


def test_neustart_merkmal_wird_auch_in_gruppen_gefunden(generator):
    ebenen = generator.sammle_ebenen(EBENEN_MIT_MERKMALEN, {})
    assert ebenen["9"]["neustart"] == ["42/18"]
