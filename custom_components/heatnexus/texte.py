"""Oberflächentexte in der gewählten Sprache.

Der deutsche Text ist zugleich der Schlüssel: Die Tabellen in `panel/muster.py`
und die Ansichten in `dashboard.py` führen ihre Beschriftungen weiter im
Klartext, und ein fehlender Eintrag fällt auf Deutsch zurück statt auf eine
leere Kachel.

Die Datenpunktnamen selbst kommen nicht von hier, sondern aus dem Textwerk der
Steuerung (`geraetetexte.py`).
"""

from __future__ import annotations

from functools import lru_cache
import json
import logging
from pathlib import Path

from .const import CONF_SPRACHE, DOMAIN
from .geraetetexte import SPRACHE_AUTO

_LOGGER = logging.getLogger(__name__)

ORDNER = Path(__file__).parent / "sprachen"
QUELLSPRACHE = "de"
RUECKFALL = "en"


@lru_cache(maxsize=4)
def _laden(sprache: str) -> dict[str, str]:
    """Wörterbuch einer Sprache; unlesbares oder fehlendes ergibt nichts.

    Gelesen wird aus der Ereignisschleife heraus, deshalb nur einmal je
    Sprache.
    """
    datei = ORDNER / f"{sprache}.json"
    try:
        inhalt = json.loads(datei.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        _LOGGER.warning("Wörterbuch %s ist unlesbar; Texte bleiben deutsch", datei.name)
        return {}
    return inhalt if isinstance(inhalt, dict) else {}


class Woerterbuch:
    """Übersetzt Oberflächentexte, oder gibt den deutschen zurück."""

    def __init__(self, sprache: str | None) -> None:
        self.sprache = sprache or QUELLSPRACHE
        self._eintraege = {} if self.sprache == QUELLSPRACHE else self._waehlen(self.sprache)

    @staticmethod
    def _waehlen(sprache: str) -> dict[str, str]:
        """Das Wörterbuch der Sprache, sonst das englische.

        Wer eine fremde Sprache wählt, versteht die deutsche Quelle in aller
        Regel nicht; Englisch trägt weiter als der Rückfall auf Deutsch.
        """
        return _laden(sprache) or _laden(RUECKFALL)

    def __call__(self, text: str) -> str:
        """Kurzform für die Übersetzung eines Textes."""
        return self._eintraege.get(text, text)

    def __bool__(self) -> bool:
        """Wahr, sobald es etwas zu übersetzen gibt."""
        return bool(self._eintraege)

    @property
    def fuer_frontend(self) -> dict[str, str]:
        """Was die Oberfläche im Browser selbst übersetzen muss.

        Eine Kopie: Das Wörterbuch liegt im Zwischenspeicher und darf von
        keinem Aufrufer verändert werden.
        """
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
    if not woerterbuch:
        return daten
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
    """Die Sprache der Oberfläche; bei mehreren Anlagen gilt die erste.

    Gelesen aus den Optionen, nicht aus den Laufzeitdaten: Die Oberfläche
    entsteht auch, während ein Eintrag noch lädt. Bei „Automatisch" gilt die
    Sprache von Home Assistant – eigene Texte hängen an keinem Namensmuster.
    """
    eintraege = hass.config_entries.async_entries(DOMAIN)
    if not eintraege:
        return QUELLSPRACHE
    gewaehlt = (eintraege[0].options or {}).get(CONF_SPRACHE)
    if gewaehlt and gewaehlt != SPRACHE_AUTO:
        return gewaehlt
    ha_sprache = getattr(hass.config, "language", None) or QUELLSPRACHE
    return ha_sprache.split("-")[0]


def woerterbuch(hass) -> Woerterbuch:
    """Das Wörterbuch für die eingestellte Sprache."""
    return Woerterbuch(sprache_der_oberflaeche(hass))
