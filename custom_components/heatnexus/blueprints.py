"""Mitgelieferte Automations-Vorlagen bereitstellen.

Die Vorlagen liegen in der Integration und werden beim Einrichten nach
``<config>/blueprints/automation/heatnexus/`` kopiert. Danach stehen sie
unter Einstellungen → Automationen → Blueprint verwenden ohne Import aus
dem Netz bereit.

Aktualisiert werden sie nur beim Versionswechsel der Integration. Eine
Vorlage, die der Nutzer selbst geändert hat, bleibt dabei unangetastet: Die
Marke merkt sich den Hash jeder abgelegten Datei, weicht die Datei davon ab,
wird sie weder überschrieben noch entfernt.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
from pathlib import Path
import re
import shutil

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_QUELLE = Path(__file__).parent / "blueprints" / "automation" / DOMAIN
_MARKE = ".heatnexus-version"
# Hashes aller bisher ausgelieferten Vorlagen; gilt, solange die Marke noch keine Hashes trägt.
_AUSGELIEFERT = Path(__file__).parent / "blueprints" / "ausgeliefert.json"


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
        # Gesucht wird ein ASCII-Pfad; ein fremder Zeichensatz drumherum darf nicht scheitern.
        return f"{DOMAIN}/{kennung}.yaml" in automationen.read_text(
            encoding="utf-8", errors="replace"
        )
    return True


def _hash(datei: Path) -> str:
    return hashlib.sha256(datei.read_bytes()).hexdigest()


def _marke_lesen(marke: Path) -> tuple[str, dict[str, str]]:
    """Version und Hashes der abgelegten Dateien; ältere Marken tragen nur die Version."""
    if not marke.is_file():
        return "", {}
    text = marke.read_text(encoding="utf-8").strip()
    try:
        inhalt = json.loads(text)
    except ValueError:
        return text, {}
    if not isinstance(inhalt, dict):
        return text, {}
    return str(inhalt.get("version", "")), dict(inhalt.get("dateien") or {})


def _ausgeliefert() -> frozenset[str]:
    if not _AUSGELIEFERT.is_file():
        return frozenset()
    return frozenset(json.loads(_AUSGELIEFERT.read_text(encoding="utf-8")))


def _kopieren(
    ziel: Path, version: str, gewaehlt: set[str] | None, automationen: Path
) -> tuple[int, int, list[str]]:
    """Vorlagen ablegen und abgewählte entfernen; ohne Auswahl alle.

    Zurück kommt ``(geschrieben, entfernt, übersprungen)``. Eine Vorlage, die
    eine Automation benutzt oder die der Nutzer geändert hat, bleibt liegen.
    """
    if not _QUELLE.is_dir():
        return 0, 0, []
    if gewaehlt is None:
        gewaehlt = set(verfuegbare())

    marke = ziel / _MARKE
    bekannt, hashes = _marke_lesen(marke)
    aktuell = bekannt == version
    unveraendert = set(hashes.values()) if hashes else set(_ausgeliefert())

    ziel.mkdir(parents=True, exist_ok=True)
    geschrieben = 0
    entfernt = 0
    uebersprungen: list[str] = []
    neue: dict[str, str] = {}
    for datei in sorted(_QUELLE.glob("*.yaml")):
        vorhanden = ziel / datei.name
        quelle = _hash(datei)
        eigen = vorhanden.is_file() and _hash(vorhanden) not in unveraendert | {quelle}
        if datei.stem not in gewaehlt:
            if eigen:
                uebersprungen.append(datei.name)
            elif vorhanden.is_file() and not _wird_benutzt(automationen, datei.stem):
                vorhanden.unlink()
                entfernt += 1
            continue
        if eigen:
            uebersprungen.append(datei.name)
            continue
        neue[datei.name] = quelle
        # Bei gleicher Version nur ergänzen, sonst alles auffrischen.
        if vorhanden.is_file() and aktuell:
            continue
        shutil.copyfile(datei, vorhanden)
        geschrieben += 1

    if geschrieben or entfernt or not aktuell or neue != hashes:
        marke.write_text(json.dumps({"version": version, "dateien": neue}), encoding="utf-8")
    return geschrieben, entfernt, uebersprungen


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
    wahl = None if gewaehlt is None else set(gewaehlt)
    try:
        geschrieben, entfernt, uebersprungen = await hass.async_add_executor_job(
            _kopieren, ziel, version, wahl, automationen
        )
    except OSError as err:
        _LOGGER.warning("Automations-Vorlagen konnten nicht abgelegt werden: %s", err)
        return
    if geschrieben:
        _LOGGER.info("%d Automations-Vorlagen bereitgestellt in %s", geschrieben, ziel)
    if entfernt:
        _LOGGER.info("%d abgewählte Automations-Vorlagen entfernt", entfernt)
    if uebersprungen:
        _LOGGER.warning(
            "Selbst geänderte Automations-Vorlagen bleiben unverändert: %s. "
            "Wer die neue Fassung möchte, löscht die Datei; sie wird beim nächsten Start neu angelegt",
            ", ".join(uebersprungen),
        )
