"""Anlagenschaubild.

Zeichnet die Anlage als Grafik – Kessel, Puffer, Heizkreise, Warmwasser,
Zirkulation, verbunden durch Vor- und Rücklauf – und legt die Live-Werte
darauf.

Das Bild wird **aus den erkannten Anlagenteilen zusammengesetzt**, nicht als
fertiges Bild mitgeliefert. Ein festes Bild würde nur zu der Anlage passen, für
die es gezeichnet wurde; hier wächst das Schaubild mit: Wer zwei Puffer hat,
sieht zwei, wer keinen hat, sieht keinen.

Die einzelnen Anlagenteile liegen als **SVG-Dateien** in ``anlagenteile/``.
Jede Datei zeichnet ein Bauteil in einem eigenen Feld von ``MODUL_BREITE`` ×
``HOEHE``; die Mitte liegt bei x = 100, der Vorlauf auf y = 92, der Rücklauf auf
y = 318. Farben stehen darin als Platzhalter (``{{vorlauf}}``, ``{{korpus}}``,
…) und werden hier eingesetzt – sonst wäre jede Farbänderung eine Änderung an
elf Dateien. Fehlt eine Datei, greift die gezeichnete Ersatzform in `zeichnung.py`;
das Schaubild bleibt also auch dann heil, wenn eine Datei fehlt.

Ausgegeben wird ein Bild als Daten-URL plus die Liste der Beschriftungen, die
Home Assistant als `picture-elements`-Karte darüberlegt.

Das Paket: `farben` (Farbsätze), `werte` (was ein Anlagenteil zeigt),
`bauteile` (die SVG-Dateien), `zeichnung` (Maße und Kästen), `karte` (die
fertige Karte). Hier steht nur, was andere Module davon brauchen.
"""

from __future__ import annotations

from .farben import FARBSAETZE
from .karte import anlagenschema, schaubild_daten, schaubild_nutzdaten
from .werte import ANALOG_SOLLWERT, kesselart_erkennen, modul_in_betrieb, passt, traegt, treffer

__all__ = [
    "ANALOG_SOLLWERT",
    "FARBSAETZE",
    "anlagenschema",
    "kesselart_erkennen",
    "modul_in_betrieb",
    "passt",
    "schaubild_daten",
    "schaubild_nutzdaten",
    "traegt",
    "treffer",
]
