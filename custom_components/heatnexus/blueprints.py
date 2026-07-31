"""Mitgelieferte Automations-Vorlagen bereitstellen.

Die Vorlagen liegen in der Integration und werden beim Einrichten nach
``<config>/blueprints/automation/heatnexus/`` kopiert. Danach stehen sie
unter Einstellungen → Automationen → Blueprint verwenden ohne Import aus
dem Netz bereit.

Aktualisiert werden sie nur beim Versionswechsel der Integration. Eine
Vorlage ist ein Bauplan, kein Nutzerdokument – die eigenen Angaben stecken
in der jeweiligen Automation und bleiben davon unberührt.
"""

from __future__ import annotations

import logging
from pathlib import Path
import shutil

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_QUELLE = Path(__file__).parent / "blueprints" / "automation" / DOMAIN
_MARKE = ".heatnexus-version"


def _kopieren(ziel: Path, version: str) -> int:
    """Vorlagen ablegen; gibt die Zahl der geschriebenen Dateien zurück."""
    if not _QUELLE.is_dir():
        return 0

    marke = ziel / _MARKE
    bekannt = marke.read_text(encoding="utf-8").strip() if marke.is_file() else ""
    aktuell = bekannt == version

    ziel.mkdir(parents=True, exist_ok=True)
    geschrieben = 0
    for datei in sorted(_QUELLE.glob("*.yaml")):
        vorhanden = ziel / datei.name
        # Bei gleicher Version nur ergänzen, sonst alles auffrischen.
        if vorhanden.is_file() and aktuell:
            continue
        shutil.copyfile(datei, vorhanden)
        geschrieben += 1

    if geschrieben or not aktuell:
        marke.write_text(version, encoding="utf-8")
    return geschrieben


async def async_install_blueprints(hass: HomeAssistant, version: str) -> None:
    """Vorlagen ins Konfigurationsverzeichnis legen.

    Fehler bleiben folgenlos: Die Integration funktioniert auch ohne die
    Vorlagen, sie sind eine Beigabe.
    """
    ziel = Path(hass.config.path("blueprints", "automation", DOMAIN))
    try:
        anzahl = await hass.async_add_executor_job(_kopieren, ziel, version)
    except OSError as err:
        _LOGGER.warning("Automations-Vorlagen konnten nicht abgelegt werden: %s", err)
        return
    if anzahl:
        _LOGGER.info("%d Automations-Vorlagen bereitgestellt in %s", anzahl, ziel)
