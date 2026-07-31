"""Gemeinsame Test-Fixtures.

Die reinen Logikmodule (error_texts, helpers, device_db) werden bewusst per
Dateipfad geladen, damit sie ohne installierte Home-Assistant-Umgebung
getestet werden können. Alles, was das Paket ``custom_components.heatnexus``
importiert, zieht Home Assistant nach und wird bei fehlender Umgebung
übersprungen.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest

COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "heatnexus"


def load_standalone(module_name: str) -> ModuleType:
    """Ein HA-freies Modul der Integration direkt aus der Datei laden."""
    path = COMPONENT_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"windhager_{module_name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def requires_ha():
    """Skip-Marker, wenn keine Home-Assistant-Umgebung installiert ist."""
    return pytest.mark.skipif(
        importlib.util.find_spec("homeassistant") is None,
        reason="Home Assistant nicht installiert (pip install -r requirements_test.txt)",
    )


@pytest.fixture(scope="session")
def error_texts() -> ModuleType:
    """Modul error_texts (Störungsdekodierung)."""
    return load_standalone("error_texts")


@pytest.fixture(scope="session")
def helpers() -> ModuleType:
    """Modul helpers (Wertparsing)."""
    return load_standalone("helpers")


@pytest.fixture(scope="session")
def device_db() -> ModuleType:
    """Modul device_db (Zugriff auf die Geräte-Datenbank)."""
    return load_standalone("device_db")
