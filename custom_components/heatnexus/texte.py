"""Oberflächentexte in der gewählten Sprache.

Der deutsche Text ist zugleich der Schlüssel; ein fehlender Eintrag fällt auf
Deutsch zurück. Die Datenpunktnamen kommen aus `geraetetexte.py`.
"""

from __future__ import annotations

from functools import lru_cache
import json
import logging
from pathlib import Path
import re

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


def eigene_fassung(sprache: str, text: str) -> str | None:
    """Die Fassung eines Textes im Wörterbuch genau dieser Sprache, ohne Rückfall."""
    return _laden(sprache).get(text) if sprache != QUELLSPRACHE else None


class Woerterbuch:
    """Übersetzt Oberflächentexte, oder gibt den deutschen zurück."""

    def __init__(self, sprache: str | None) -> None:
        self.sprache = sprache or QUELLSPRACHE
        self._eintraege = {} if self.sprache == QUELLSPRACHE else self._waehlen(self.sprache)

    @staticmethod
    def _waehlen(sprache: str) -> dict[str, str]:
        """Das Wörterbuch der Sprache, über das englische gelegt.

        Wer eine fremde Sprache wählt, versteht die deutsche Quelle in aller
        Regel nicht; was die Sprache nicht führt, erscheint englisch.
        """
        if sprache == RUECKFALL:
            return _laden(RUECKFALL)
        return {**_laden(RUECKFALL), **_laden(sprache)}

    def __call__(self, text: str) -> str:
        """Kurzform für die Übersetzung eines Textes."""
        return self._eintraege.get(text, text)

    def satz(self, text: str) -> str:
        """Einen fertigen Satz übersetzen, auch mit Werten darin; Unbekanntes bleibt deutsch.

        Die Werte eines Musters werden selbst nachgeschlagen: „{grund} Pausiert bis {zeit}.“
        """
        if not self._eintraege or not text:
            return text
        if text in self._eintraege:
            return self._eintraege[text]
        for suche, namen, fremd in _muster(self.sprache):
            if (treffer := suche.match(text)) is None:
                continue
            ergebnis = fremd
            for name, wert in zip(namen, treffer.groups(), strict=True):
                ergebnis = ergebnis.replace("{" + name + "}", self._wert(wert))
            return ergebnis
        return text

    def _wert(self, wert: str) -> str:
        """Ein Wert im Satz, übersetzt und mit dem Dezimalzeichen der Sprache."""
        wert = self.satz(wert)
        if self.sprache in DEZIMALPUNKT:
            wert = _DEZIMALKOMMA.sub(".", wert)
        return wert

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


# Sprachen, die Dezimalzahlen mit Punkt schreiben; die übrigen behalten das Komma.
DEZIMALPUNKT = frozenset({"en"})
_DEZIMALKOMMA = re.compile(r"(?<=\d),(?=\d)")

# Sätze mit Zahlen stehen als Muster im Wörterbuch: „Sonnentag – {soll} °C bis {zeit}.“
_PLATZHALTER = re.compile(r"\{(\w+)\}")
# Kürzere feste Anteile trügen zu wenig, um einen Satz sicher zu erkennen.
MUSTER_MIN_ZEICHEN = 6


@lru_cache(maxsize=4)
def _muster(sprache: str) -> tuple[tuple[re.Pattern[str], tuple[str, ...], str], ...]:
    """Die Einträge mit Platzhaltern als Suchmuster, der längste feste Anteil zuerst."""
    gefunden = []
    for deutsch, fremd in Woerterbuch._waehlen(sprache).items():
        teile = _PLATZHALTER.split(deutsch)
        namen = tuple(teile[1::2])
        fest = "".join(teile[0::2])
        if not namen or len(fest.strip()) < MUSTER_MIN_ZEICHEN:
            continue
        suche = "".join(re.escape(t) if i % 2 == 0 else "(.+?)" for i, t in enumerate(teile))
        gefunden.append((len(fest), re.compile(suche + r"\Z", re.DOTALL), namen, fremd))
    gefunden.sort(key=lambda eintrag: -eintrag[0])
    return tuple((suche, namen, fremd) for _, suche, namen, fremd in gefunden)


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
LOVELACE_FELDER = frozenset({"title", "name", "heading", "text", "confirmation_text", "content"})


def uebersetze_baum(daten, woerterbuch: Woerterbuch, felder=TEXTFELDER):
    """Die Textfelder einer fertigen Nutzlast übersetzen.

    Läuft einmal über das Ergebnis statt die Sprache durch jede Funktion zu
    reichen. Unbekannte Texte bleiben stehen.
    """
    if not woerterbuch:
        return daten
    if isinstance(daten, dict):
        return {
            k: woerterbuch.satz(v)
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
    if isinstance(gewaehlt, str) and gewaehlt and gewaehlt != SPRACHE_AUTO:
        return gewaehlt
    ha_sprache = getattr(hass.config, "language", None)
    if not isinstance(ha_sprache, str) or not ha_sprache:
        return QUELLSPRACHE
    return ha_sprache.split("-")[0]


def woerterbuch(hass) -> Woerterbuch:
    """Das Wörterbuch für die eingestellte Sprache."""
    return Woerterbuch(sprache_der_oberflaeche(hass))


def woerterbuch_zu(objekt) -> Woerterbuch:
    """Das Wörterbuch zum Home Assistant eines Objekts; ohne eines bleibt es deutsch."""
    hass = getattr(objekt, "hass", None)
    return woerterbuch(hass) if hass is not None else Woerterbuch(None)
