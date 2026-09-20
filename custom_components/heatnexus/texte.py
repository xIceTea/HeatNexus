"""Oberflächentexte in der gewählten Sprache.

Der deutsche Text ist zugleich der Schlüssel: Die Tabellen in `panel/muster.py`
und die Ansichten in `dashboard.py` führen ihre Beschriftungen weiter im
Klartext, und ein fehlender Eintrag fällt auf Deutsch zurück statt auf eine
leere Kachel.

Die Datenpunktnamen selbst kommen nicht von hier, sondern aus dem Textwerk der
Steuerung (`geraetetexte.py`).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .const import CONF_SPRACHE, DOMAIN
from .geraetetexte import sprache_aufloesen

_LOGGER = logging.getLogger(__name__)

ORDNER = Path(__file__).parent / "texte"
QUELLSPRACHE = "de"


def _laden(sprache: str) -> dict[str, str]:
    """Wörterbuch einer Sprache; unlesbares oder fehlendes ergibt nichts."""
    datei = ORDNER / f"{sprache}.json"
    try:
        inhalt = json.loads(datei.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        _LOGGER.warning("Wörterbuch %s ist unlesbar; Texte bleiben deutsch", datei.name)
        return {}
    return {k: v for k, v in inhalt.items() if isinstance(v, str) and v}


class Woerterbuch:
    """Übersetzt Oberflächentexte, oder gibt den deutschen zurück."""

    def __init__(self, sprache: str | None) -> None:
        self.sprache = sprache or QUELLSPRACHE
        self._eintraege = {} if self.sprache == QUELLSPRACHE else _laden(self.sprache)

    def __call__(self, text: str) -> str:
        """Kurzform für die Übersetzung eines Textes."""
        return self._eintraege.get(text, text)

    @property
    def fuer_frontend(self) -> dict[str, str]:
        """Was die Oberfläche im Browser selbst übersetzen muss."""
        return dict(self._eintraege)


# Felder der Nutzlast, die Klartext für den Betrachter tragen. Was nicht im
# Wörterbuch steht – Namen von Anlagenteilen etwa – bleibt unverändert.
TEXTFELDER = frozenset(
    {
        "titel",
        "untertitel",
        "frage",
        "titel_abbrechen",
        "frage_abbrechen",
        "hilfe",
        "hinweis",
        "beschriftung",
    }
)

# Dieselben Felder in der Lovelace-Konfiguration des Dashboards.
LOVELACE_FELDER = frozenset({"title", "name", "confirmation_text", "content"})


def uebersetze_baum(daten, woerterbuch: Woerterbuch, felder=TEXTFELDER):
    """Die Textfelder einer fertigen Nutzlast übersetzen.

    Läuft einmal über das Ergebnis statt die Sprache durch jede Funktion zu
    reichen. Unbekannte Texte bleiben stehen.
    """
    if isinstance(daten, dict):
        return {
            k: woerterbuch(v)
            if k in felder and isinstance(v, str)
            else uebersetze_baum(v, woerterbuch, felder)
            for k, v in daten.items()
        }
    if isinstance(daten, list):
        return [uebersetze_baum(e, woerterbuch, felder) for e in daten]
    return daten


def sprache_der_oberflaeche(hass) -> str:
    """Die eingestellte Sprache; bei mehreren Anlagen gilt die erste.

    Gelesen wird aus den Optionen, nicht aus den Laufzeitdaten: Die Oberfläche
    wird auch aufgebaut, während ein Eintrag noch lädt.
    """
    ha_sprache = getattr(hass.config, "language", None)
    for eintrag in hass.config_entries.async_entries(DOMAIN):
        optionen = eintrag.options or {}
        gewaehlt = optionen.get(CONF_SPRACHE)
        if gewaehlt is None:
            gewaehlt = next(
                (je.get(CONF_SPRACHE) for je in optionen.values() if isinstance(je, dict)), None
            )
        if sprache := sprache_aufloesen(gewaehlt, ha_sprache):
            return sprache
    return "de"
