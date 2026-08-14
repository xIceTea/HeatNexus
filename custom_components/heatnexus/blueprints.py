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

import contextlib
import logging
from pathlib import Path
import re
import shutil

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_QUELLE = Path(__file__).parent / "blueprints" / "automation" / DOMAIN
_MARKE = ".heatnexus-version"


_NAME = re.compile(r"^\s{2}name:\s*(.+?)\s*$", re.MULTILINE)


def verfuegbare() -> dict[str, str]:
    """Kennung -> Anzeigename aller mitgelieferten Vorlagen.

    Die Kennung ist der Dateiname ohne Endung; an ihr hängen die Automationen
    der Nutzer, sie darf sich nicht ändern.
    """
    if not _QUELLE.is_dir():
        return {}
    gefunden: dict[str, str] = {}
    for datei in sorted(_QUELLE.glob("*.yaml")):
        kopf = datei.read_text(encoding="utf-8")[:400]
        treffer = _NAME.search(kopf)
        gefunden[datei.stem] = treffer.group(1) if treffer else datei.stem
    return gefunden


def _wird_benutzt(automationen: Path, kennung: str) -> bool:
    """Ob eine Automation diese Vorlage verwendet.

    Gelesen wird `automations.yaml`; Automationen aus eigenen Paketen sieht
    diese Prüfung nicht. Im Zweifel bleibt die Datei liegen.
    """
    if not automationen.is_file():
        return False
    with contextlib.suppress(OSError):
        return f"{DOMAIN}/{kennung}.yaml" in automationen.read_text(encoding="utf-8")
    return True


def _kopieren(ziel: Path, version: str, gewaehlt: set[str], automationen: Path) -> tuple[int, int]:
    """Vorlagen ablegen und abgewählte entfernen.

    Zurück kommt ``(geschrieben, entfernt)``. Eine Vorlage, die eine
    Automation benutzt, bleibt auch abgewählt liegen – sonst stünde die
    Automation ohne ihren Bauplan da.
    """
    if not _QUELLE.is_dir():
        return 0, 0

    marke = ziel / _MARKE
    bekannt = marke.read_text(encoding="utf-8").strip() if marke.is_file() else ""
    aktuell = bekannt == version

    ziel.mkdir(parents=True, exist_ok=True)
    geschrieben = 0
    entfernt = 0
    for datei in sorted(_QUELLE.glob("*.yaml")):
        vorhanden = ziel / datei.name
        if datei.stem not in gewaehlt:
            if vorhanden.is_file() and not _wird_benutzt(automationen, datei.stem):
                vorhanden.unlink()
                entfernt += 1
            continue
        # Bei gleicher Version nur ergänzen, sonst alles auffrischen.
        if vorhanden.is_file() and aktuell:
            continue
        shutil.copyfile(datei, vorhanden)
        geschrieben += 1

    if geschrieben or entfernt or not aktuell:
        marke.write_text(version, encoding="utf-8")
    return geschrieben, entfernt


async def async_install_blueprints(
    hass: HomeAssistant, version: str, gewaehlt: list[str] | None = None
) -> None:
    """Vorlagen ins Konfigurationsverzeichnis legen.

    Ohne Auswahl kommen alle mit – so ändert eine Aktualisierung nichts an
    einer bestehenden Installation. Fehler bleiben folgenlos: Die Integration
    funktioniert auch ohne die Vorlagen, sie sind eine Beigabe.
    """
    ziel = Path(hass.config.path("blueprints", "automation", DOMAIN))
    automationen = Path(hass.config.path("automations.yaml"))
    wahl = set(verfuegbare()) if gewaehlt is None else set(gewaehlt)
    try:
        geschrieben, entfernt = await hass.async_add_executor_job(
            _kopieren, ziel, version, wahl, automationen
        )
    except OSError as err:
        _LOGGER.warning("Automations-Vorlagen konnten nicht abgelegt werden: %s", err)
        return
    if geschrieben:
        _LOGGER.info("%d Automations-Vorlagen bereitgestellt in %s", geschrieben, ziel)
    if entfernt:
        _LOGGER.info("%d abgewählte Automations-Vorlagen entfernt", entfernt)
