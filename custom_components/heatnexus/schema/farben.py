"""Farbsätze des Schaubilds: dunkel, hell, terrakotta, petrol, pflaume.

Gezeichnet wird immer im dunklen Satz; `farben_umstellen` tauscht die Farben
eines fertigen Bildes gegen die des gewählten Satzes.
"""

from __future__ import annotations

import re

# Farben, an der dunklen Oberfläche von Home Assistant ausgerichtet.
FARBE_VORLAUF = "#e2543a"


FARBE_RUECKLAUF = "#3a7fe2"


FARBE_RAHMEN = "#4a5561"


FARBE_TEXT = "#c9d3de"


FARBE_TITEL = "#f2f6fa"


# Ohne Angabe zeichnen manche Browser SVG-Text mit einer Serifenschrift.
SCHRIFT = "system-ui, -apple-system, Roboto, sans-serif"


# Platzhalter, die in den Bauteildateien stehen dürfen. Wer eine Farbe ändern
# will, ändert sie hier – nicht in elf Dateien.
FARBEN: dict[str, str] = {
    "vorlauf": FARBE_VORLAUF,
    "ruecklauf": FARBE_RUECKLAUF,
    "rahmen": FARBE_RAHMEN,
    "text": FARBE_TEXT,
    "titel": FARBE_TITEL,
    # Gehäuse: oben etwas heller als unten, damit Körper Volumen bekommen.
    "korpus": "#2b333c",
    "korpus_hell": "#3b444e",
    "korpus_dunkel": "#1d242c",
    # Wärme und Kälte im Inneren (Schichtung, Glut, Kollektor).
    "warm": "#b3341f",
    "glut": "#e2543a",
    "kalt": "#25508f",
    "schrift": SCHRIFT,
}


# Rollen, die in jedem Farbsatz denselben Wert behalten: Rot ist der Vorlauf,
# Blau der Rücklauf – eine Auskunft, keine Gestaltung. `glut` teilt sich den
# Wert mit `vorlauf`.
FESTE_ROLLEN = ("vorlauf", "ruecklauf", "glut")


# Derselbe Satz für eine helle Oberfläche. Das Schaubild als `data:`-Bild erbt
# kein CSS; gewechselt wird deshalb durch Austausch der fertigen Farbwerte im
# Ergebnis, nicht über einen zweiten Weg durch den Zeichencode.
FARBEN_HELL: dict[str, str] = {
    "vorlauf": FARBE_VORLAUF,
    "ruecklauf": FARBE_RUECKLAUF,
    "rahmen": "#7d8b9a",
    "text": "#3d4854",
    "titel": "#16202b",
    "korpus": "#dde3ea",
    "korpus_hell": "#eef2f7",
    "korpus_dunkel": "#c2ccd8",
    "warm": "#c0402a",
    "glut": FARBE_VORLAUF,
    "kalt": "#3f78c9",
    "schrift": SCHRIFT,
}


# Dritter Satz: warmes Dunkel mit Terrakotta, passend zum gleichnamigen
# Farbsatz der Oberfläche.
FARBEN_TERRAKOTTA: dict[str, str] = {
    "vorlauf": FARBE_VORLAUF,
    "ruecklauf": FARBE_RUECKLAUF,
    "rahmen": "#3a3630",
    "text": "#b8b0a8",
    "titel": "#ece8e4",
    "korpus": "#242220",
    "korpus_hell": "#322f2b",
    "korpus_dunkel": "#1a1816",
    "warm": "#a8431f",
    "glut": FARBE_VORLAUF,
    "kalt": "#436f9c",
    "schrift": SCHRIFT,
}


# Vierter Satz: ruhiges Dunkel mit Petrol.
FARBEN_PETROL: dict[str, str] = {
    "vorlauf": FARBE_VORLAUF,
    "ruecklauf": FARBE_RUECKLAUF,
    "rahmen": "#2e3c3f",
    "text": "#93a3a3",
    "titel": "#e4ecec",
    "korpus": "#192226",
    "korpus_hell": "#26312f",
    "korpus_dunkel": "#10171a",
    "warm": "#b34a2a",
    "glut": FARBE_VORLAUF,
    "kalt": "#2a5c94",
    "schrift": SCHRIFT,
}


# Fünfter Satz: dunkles Violett mit Pflaume.
FARBEN_PFLAUME: dict[str, str] = {
    "vorlauf": FARBE_VORLAUF,
    "ruecklauf": FARBE_RUECKLAUF,
    "rahmen": "#3a3145",
    "text": "#a297ad",
    "titel": "#ece7f0",
    "korpus": "#211b2a",
    "korpus_hell": "#2e2639",
    "korpus_dunkel": "#16121c",
    "warm": "#b34a4a",
    "glut": FARBE_VORLAUF,
    "kalt": "#4d5aa8",
    "schrift": SCHRIFT,
}


THEMA_DUNKEL = "dunkel"


THEMA_HELL = "hell"


THEMA_TERRAKOTTA = "terrakotta"


THEMA_PETROL = "petrol"


THEMA_PFLAUME = "pflaume"


# Was die Oberfläche anbieten darf. `auto` folgt dem Erscheinungsbild von Home
# Assistant, die übrigen legen den Satz fest.
FARBSATZ_AUTO = "auto"


FARBSAETZE = (
    FARBSATZ_AUTO,
    THEMA_DUNKEL,
    THEMA_HELL,
    THEMA_TERRAKOTTA,
    THEMA_PETROL,
    THEMA_PFLAUME,
)


def entsprechung(ziel: dict[str, str]) -> dict[str, str]:
    """Dunkle Farbe -> Farbe des Zielsatzes, für den Austausch im fertigen Bild.

    Zwei Rollen dürfen sich einen dunklen Wert teilen (``vorlauf`` und ``glut``
    sind beide ``#e2543a``); dann teilen sie sich auch den neuen, sonst
    entscheidet die Reihenfolge im Wörterbuch, welche Rolle die falsche bekommt.
    """
    abbildung: dict[str, str] = {}
    for name, dunkel in FARBEN.items():
        if name == "schrift":
            continue
        neu = ziel[name]
        if abbildung.setdefault(dunkel, neu) != neu:
            raise ValueError(
                f"{dunkel} soll gleichzeitig {abbildung[dunkel]} und {neu} werden "
                f"(Rolle {name}) – im fertigen Bild ist das nicht zu unterscheiden."
            )
    return abbildung


# Dunkler Farbwert -> Wert des Zielsatzes, je Thema. Der Browser bekommt
# diese Tabellen und tauscht damit selbst; das spart je Satz ein volles Bild.
FARBABBILDUNGEN = {
    THEMA_HELL: entsprechung(FARBEN_HELL),
    THEMA_TERRAKOTTA: entsprechung(FARBEN_TERRAKOTTA),
    THEMA_PETROL: entsprechung(FARBEN_PETROL),
    THEMA_PFLAUME: entsprechung(FARBEN_PFLAUME),
}


_FARBSTELLE = re.compile(
    "|".join(sorted(map(re.escape, FARBABBILDUNGEN[THEMA_HELL]), reverse=True))
)


def farben_umstellen(svg: str, thema: str | None) -> str:
    """Ein fertiges Schaubild auf einen anderen Farbsatz umstellen.

    In **einem** Durchgang, nicht als Kette einzelner Ersetzungen: Sonst könnte
    eine gerade eingesetzte Farbe von der nächsten Regel noch einmal getroffen
    werden. Der dunkle Satz steht schon im Bild.
    """
    abbildung = FARBABBILDUNGEN.get(thema or "")
    if abbildung is None:
        return svg
    return _FARBSTELLE.sub(lambda treffer: abbildung[treffer.group(0)], svg)
