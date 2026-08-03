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
    "Abhilfe: pip install -r requirements_test.txt. "
    "Verlass dich sonst auf die CI."
)


# ---------------------------------------------------------------------------
# Windows: die Socket-Sperre der Testumgebung wieder lockern
#
# `pytest-homeassistant-custom-component` sperrt vor jedem Test alle Sockets
# und lässt nur Unix-Sockets durch – unter Linux genau richtig, denn asyncio
# baut seine Selbstweck-Leitung dort aus einem Unix-Paar.
#
# Unter Windows gibt es keine Unix-Sockets. asyncio nimmt dort ein AF_INET-Paar
# (`socket.socketpair()` in `proactor_events._make_self_pipe`), und das fällt
# in die Sperre. Weil `asyncio_mode = "auto"` jedem Test eine Ereignisschleife
# gibt, scheitert damit **jeder** Test schon beim Aufbau – auch ein rein
# rechnender ohne jeden Bezug zu Home Assistant.
#
# Abgeschaltet wird deshalb nur *ein* Teil der Sperre: das Verbot, überhaupt
# einen Socket anzulegen. Die Zielbeschränkung des Plugins bleibt in Kraft –
# `socket_allow_hosts(["127.0.0.1"])` läuft weiter, ein Test kommt also nach
# wie vor nicht ins Netz.
#
# Warum als Ersatz für die Funktion und nicht als eigener Hook: Die Hooks einer
# conftest laufen **vor** denen der Plugins, der Sperr-Hook käme also hinterher
# und setzte alles zurück. Mit `trylast` liefe der eigene Hook zwar zuletzt,
# aber erst nach dem von pytest selbst – und der hat die Fixtures da längst
# aufgebaut, mitsamt der Ereignisschleife, an der es scheitert. Bleibt, die
# Sperre an der Wurzel wirkungslos zu machen.
#
# Unter Linux – und damit in der CI – ändert sich nichts.
if sys.platform == "win32":  # pragma: no cover - plattformabhängig
    try:
        import pytest_socket
    except ImportError:  # Testumgebung ohne Home Assistant
        pass
    else:
        pytest_socket.disable_socket = lambda *args, **kwargs: None
        pytest_socket.enable_socket()


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
