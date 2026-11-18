"""Farbsätze des Schaubilds: HeatNexus, Terrakotta, Petrol, Pflaume, Windhager, je Fassung.

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
# Brennstoff im Vorratsbehälter: Pellets hellbraun, Hackgut dunkler. Holz bleibt in
# jedem Farbsatz holzfarben, deshalb stehen die Werte in jedem Satz gleich.
HOLZ: dict[str, str] = {
    "pellets": "#c9a26b",
    "pellets_dunkel": "#9c7a47",
    "hackgut": "#a87c4f",
    "hackgut_dunkel": "#7e5a35",
}


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
    **HOLZ,
    "schrift": SCHRIFT,
}


# Rollen, die in jedem Farbsatz denselben Wert behalten: Rot ist der Vorlauf,
# Blau der Rücklauf – eine Auskunft, keine Gestaltung. `glut` teilt sich den
# Wert mit `vorlauf`.
FESTE_ROLLEN = ("vorlauf", "ruecklauf", "glut", *HOLZ)


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
    **HOLZ,
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
    **HOLZ,
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
    **HOLZ,
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
    **HOLZ,
    "kalt": "#4d5aa8",
    "schrift": SCHRIFT,
}


# Windhager-Stil, angelehnt an die Bediengeräte: grauer Grund, helle Flächen,
# Puffer warm rot, kalt blau.
FARBEN_WINDHAGER: dict[str, str] = {
    "vorlauf": FARBE_VORLAUF,
    "ruecklauf": FARBE_RUECKLAUF,
    "rahmen": "#565656",
    "text": "#404040",
    "titel": "#363636",
    "korpus": "#e5e5e5",
    "korpus_hell": "#f2f2f2",
    "korpus_dunkel": "#bdbdbd",
    "warm": "#e22f43",
    "glut": FARBE_VORLAUF,
    **HOLZ,
    "kalt": "#5f8dc7",
    "schrift": SCHRIFT,
}


# Helle Fassungen von Terrakotta, Petrol und Pflaume: der helle Satz, im Ton des
# jeweiligen Akzents getönt.
FARBEN_TERRAKOTTA_HELL: dict[str, str] = {
    "vorlauf": FARBE_VORLAUF,
    "ruecklauf": FARBE_RUECKLAUF,
    "rahmen": "#9a8a7c",
    "text": "#4d4038",
    "titel": "#2a2420",
    "korpus": "#e9e0d6",
    "korpus_hell": "#f5efe8",
    "korpus_dunkel": "#d6c8b9",
    "warm": "#b5482a",
    "glut": FARBE_VORLAUF,
    **HOLZ,
    "kalt": "#4a76a8",
    "schrift": SCHRIFT,
}


FARBEN_PETROL_HELL: dict[str, str] = {
    "vorlauf": FARBE_VORLAUF,
    "ruecklauf": FARBE_RUECKLAUF,
    "rahmen": "#7f9894",
    "text": "#3a4e4b",
    "titel": "#1a2624",
    "korpus": "#d9e6e3",
    "korpus_hell": "#edf4f2",
    "korpus_dunkel": "#bfd3cf",
    "warm": "#b8492c",
    "glut": FARBE_VORLAUF,
    **HOLZ,
    "kalt": "#2f6aa8",
    "schrift": SCHRIFT,
}


FARBEN_PFLAUME_HELL: dict[str, str] = {
    "vorlauf": FARBE_VORLAUF,
    "ruecklauf": FARBE_RUECKLAUF,
    "rahmen": "#918599",
    "text": "#4a3f54",
    "titel": "#241d2b",
    "korpus": "#e5dfec",
    "korpus_hell": "#f2eef6",
    "korpus_dunkel": "#d0c6dc",
    "warm": "#b8454f",
    "glut": FARBE_VORLAUF,
    **HOLZ,
    "kalt": "#5562b3",
    "schrift": SCHRIFT,
}


# Dunkle Fassung des Windhager-Stils. Die Bediengeräte kennen keine; Grundton ist
# das Anthrazit der Kesselgehäuse, Puffer warm und kalt bleiben wie im hellen Satz.
FARBEN_WINDHAGER_DUNKEL: dict[str, str] = {
    "vorlauf": FARBE_VORLAUF,
    "ruecklauf": FARBE_RUECKLAUF,
    "rahmen": "#6b747b",
    "text": "#d0d4d7",
    "titel": "#f2f2f2",
    "korpus": "#343c42",
    "korpus_hell": "#3e474e",
    "korpus_dunkel": "#252c31",
    "warm": "#e22f43",
    "glut": FARBE_VORLAUF,
    **HOLZ,
    "kalt": "#5f8dc7",
    "schrift": SCHRIFT,
}


# Ein Thema ist Farbsatz und Fassung zusammen, „<satz>_<hell|dunkel>“.
THEMA_DUNKEL = "heatnexus_dunkel"


THEMA_HELL = "heatnexus_hell"


THEMA_TERRAKOTTA = "terrakotta_dunkel"


THEMA_PETROL = "petrol_dunkel"


THEMA_PFLAUME = "pflaume_dunkel"


THEMA_TERRAKOTTA_HELL = "terrakotta_hell"


THEMA_PETROL_HELL = "petrol_hell"


THEMA_PFLAUME_HELL = "pflaume_hell"


THEMA_WINDHAGER = "windhager_hell"


THEMA_WINDHAGER_DUNKEL = "windhager_dunkel"


# Was die Oberfläche anbieten darf. „home_assistant“ nimmt die Farben des
# Themas von Home Assistant; die übrigen gibt es in den genannten Fassungen.
FARBSATZ_HOME_ASSISTANT = "home_assistant"


FARBSAETZE = (FARBSATZ_HOME_ASSISTANT, "heatnexus", "terrakotta", "petrol", "pflaume", "windhager")


FASSUNGEN: dict[str, tuple[str, ...]] = {
    "heatnexus": ("hell", "dunkel"),
    "terrakotta": ("hell", "dunkel"),
    "petrol": ("hell", "dunkel"),
    "pflaume": ("hell", "dunkel"),
    "windhager": ("hell", "dunkel"),
}


HELLIGKEITEN = ("auto", "hell", "dunkel")


# Bis 1.15 trug ein Schlüssel Satz und Helligkeit zugleich.
ALTE_FARBSAETZE: dict[str, tuple[str, str]] = {
    "auto": (FARBSATZ_HOME_ASSISTANT, "auto"),
    "dunkel": ("heatnexus", "dunkel"),
    "hell": ("heatnexus", "hell"),
    "terrakotta": ("terrakotta", "dunkel"),
    "petrol": ("petrol", "dunkel"),
    "pflaume": ("pflaume", "dunkel"),
    "windhager": ("windhager", "hell"),
    "windhager_dunkel": ("windhager", "dunkel"),
}


def farbwahl_uebersetzen(einstellungen: dict) -> dict:
    """Einen alten Farbsatz in Satz und Helligkeit teilen; mit Helligkeit gilt der Wert schon neu."""
    alt = einstellungen.get("farbsatz")
    if "helligkeit" in einstellungen or alt not in ALTE_FARBSAETZE:
        return einstellungen
    satz, helligkeit = ALTE_FARBSAETZE[alt]
    return {**einstellungen, "farbsatz": satz, "helligkeit": helligkeit}


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
    THEMA_TERRAKOTTA_HELL: entsprechung(FARBEN_TERRAKOTTA_HELL),
    THEMA_PETROL_HELL: entsprechung(FARBEN_PETROL_HELL),
    THEMA_PFLAUME_HELL: entsprechung(FARBEN_PFLAUME_HELL),
    THEMA_WINDHAGER: entsprechung(FARBEN_WINDHAGER),
    THEMA_WINDHAGER_DUNKEL: entsprechung(FARBEN_WINDHAGER_DUNKEL),
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
