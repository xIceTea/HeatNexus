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


# Ersatzpaket für die HA-freien Module. Ohne ein Paket scheitert jeder
# relative Import („from .const import …") beim Laden über den Dateipfad;
# mit ihm findet er die Nachbardatei und zieht trotzdem kein Home Assistant
# nach.
PAKET = "heatnexus_standalone"


def _paket() -> ModuleType:
    """Das Ersatzpaket anlegen (einmalig) und zurückgeben."""
    if (paket := sys.modules.get(PAKET)) is None:
        paket = ModuleType(PAKET)
        paket.__path__ = [str(COMPONENT_DIR)]
        sys.modules[PAKET] = paket
    return paket


def load_standalone(module_name: str) -> ModuleType:
    """Ein HA-freies Modul der Integration direkt aus der Datei laden."""
    voller_name = f"{PAKET}.{module_name}"
    if (vorhanden := sys.modules.get(voller_name)) is not None:
        return vorhanden

    _paket()
    path = COMPONENT_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(voller_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[voller_name] = module
    spec.loader.exec_module(module)
    return module


def ha_fehlt() -> bool:
    """Prüfen, ob die Home-Assistant-Umgebung fehlt."""
    return importlib.util.find_spec("homeassistant") is None


def requires_ha():
    """Skip-Marker, wenn keine Home-Assistant-Umgebung installiert ist."""
    return pytest.mark.skipif(
        ha_fehlt(),
        reason="Home Assistant nicht installiert (pip install -r requirements_test.txt)",
    )


# Ein Lauf ohne Home Assistant überspringt rund die Hälfte aller Tests –
# schweigend. Genau so ist in 1.0.0 ein falscher Erwartungswert bis in die CI
# durchgerutscht. Der Hinweis steht deshalb am Anfang **und** am Ende.
_WARNUNG = (
    "Home Assistant ist nicht installiert: alle Tests der Integration werden "
    "übersprungen. Ein grüner Lauf beweist hier nichts. "
    "Abhilfe: pip install -r requirements_test.txt "
    "(unter Windows nur in WSL – pytest-homeassistant-custom-component sperrt "
    "dort Sockets, die der Windows-Ereignisschleife fehlen). "
    "Verlass dich sonst auf die CI."
)


def pytest_report_header(config) -> list[str]:
    """Fehlende Testumgebung schon in der Kopfzeile melden."""
    return [f"ACHTUNG: {_WARNUNG}"] if ha_fehlt() else []


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    """Und nach dem Lauf noch einmal, dort wo man hinschaut."""
    if ha_fehlt():
        terminalreporter.write_line("")
        terminalreporter.write_line(f"ACHTUNG: {_WARNUNG}", yellow=True, bold=True)


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
