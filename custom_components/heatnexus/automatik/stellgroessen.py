"""Die Parameter, die die Optimierung liest und bewertet.

Name und Einheit nennen Kachel und Benachrichtigung; Schritt und Grenzen begrenzen
die Empfehlung; die Gruppe sagt, welche Hinweise eine Änderung neu beginnen lässt.
Ohne Home Assistant testbar.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Stellgroesse:
    """Ein Parameter der Steuerung, Schlüssel `<gn>/<mn>`."""

    # Deutscher Name, zugleich Schlüssel der Übersetzung; ohne Namen nennt ihn keine Empfehlung.
    name: str | None
    einheit: str | None
    gruppe: str
    # Kleinste empfohlene Änderung und der Bereich, den die Steuerung annimmt.
    schritt: float = 1.0
    grenzen: tuple[float, float] = (-math.inf, math.inf)
    # `klima`: Bewertet wird der wirksame Sollwert; Verlauf und Link zeigen das Thermostat.
    bezug: str = "eigen"
    # Gelesen, aber ohne Entität in der Kachel.
    kachel: bool = True


TABELLE: dict[str, Stellgroesse] = {
    "3/1": Stellgroesse("Fußpunkt", "°C", "kurve"),
    "3/12": Stellgroesse(None, "°C", "kurve"),
    "3/13": Stellgroesse("Vorlauf bei Auslegung", "°C", "kurve"),
    "3/7": Stellgroesse(None, None, "kurve"),
    "3/58": Stellgroesse("Behaglichkeit", "K", "kurve", schritt=0.5, grenzen=(-3.0, 3.0)),
    "3/6": Stellgroesse("Vorhaltezeit", "min", "morgen", grenzen=(0.0, 240.0)),
    "3/51": Stellgroesse("Raumsollwert", "°C", "sollwert", bezug="klima"),
    "3/101": Stellgroesse(None, None, "kurve"),
    "7/76": Stellgroesse(None, None, "kurve", kachel=False),
}


def gruppe(name: str) -> tuple[str, ...]:
    """Die Parameter einer Gruppe in Tabellenreihenfolge."""
    return tuple(k for k, s in TABELLE.items() if s.gruppe == name)
