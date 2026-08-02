"""Anlagenschaubild.

Zeichnet die Anlage als Grafik – Kessel, Puffer, Heizkreise, Warmwasser,
Zirkulation, verbunden durch Vor- und Rücklauf – und legt die Live-Werte
darauf.

Das Bild wird **aus den erkannten Anlagenteilen erzeugt**, nicht als fertige
Datei mitgeliefert. Ein festes Bild würde nur zu der Anlage passen, für die es
gezeichnet wurde; hier wächst das Schaubild mit: Wer zwei Puffer hat, sieht
zwei, wer keinen hat, sieht keinen.

Ausgegeben wird ein Bild als Daten-URL plus die Liste der Beschriftungen, die
Home Assistant als `picture-elements`-Karte darüberlegt.
"""

from __future__ import annotations

import base64
import re
from typing import Any

# Maße des Schaubilds. Die Karte skaliert es auf ihre Breite, die Angaben
# sind also Verhältnisse, keine Bildpunkte.
HOEHE = 360
MODUL_BREITE = 200
RAND = 24
VORLAUF_Y = 92
RUECKLAUF_Y = 318

# Farben, an der dunklen Oberfläche von Home Assistant ausgerichtet.
FARBE_VORLAUF = "#e2543a"
FARBE_RUECKLAUF = "#3a7fe2"
FARBE_RAHMEN = "#4a5561"
FARBE_TEXT = "#c9d3de"
FARBE_TITEL = "#f2f6fa"
# Ohne Angabe zeichnen manche Browser SVG-Text mit einer Serifenschrift.
SCHRIFT = "system-ui, -apple-system, Roboto, sans-serif"

# Welcher Wert eines Anlagenteils wo im Schaubild steht.
# (Muster, Beschriftung) – die Reihenfolge bestimmt die Position von oben.
WERTE_JE_ART: dict[str, tuple[tuple[str, str], ...]] = {
    "kessel": (
        (r"kesseltemperatur ist", "Kessel"),
        (r"kesselleistung", "Leistung"),
    ),
    "puffer": (
        (r"puffer oben", "oben"),
        (r"puffer unten", "unten"),
    ),
    "heizkreis": (
        (r"vorlauftemperatur ist", "Vorlauf"),
        (r"raumtemperatur ist", "Raum"),
    ),
    "zirkulation": (
        (r"^temperatur ist$", "Temperatur"),
        (r"r(ü|ue)cklauf temperatur", "Rücklauf"),
    ),
    # Nur der Istwert. Ein Sollwert an der Stelle, an der beim Puffer die
    # zweite *gemessene* Temperatur steht, liest sich wie ein Messwert und
    # verwirrt mehr, als er nützt.
    "wasser": ((r"\bww[- ]temperatur aktueller|\bwarmwasser ist", "Warmwasser"),),
    # Zirkulation, wie sie am Heizkreis hängt (nicht die ZSP-Funktion).
    "zirkulation_ww": ((r"\bww-zirkulation ist", "Zirkulation"),),
}

# Die Pumpe eines Anlagenteils. Sie steht im Schaubild in der Leitung und
# dreht sich, solange sie läuft – im Standbild ist nicht zu erkennen, ob
# gerade etwas fließt.
PUMPE_JE_ART: dict[str, str] = {
    "kessel": r"kesselpumpe|\bpumpe\b",
    "puffer": r"pufferladepumpe",
    "heizkreis": r"heizkreispumpe",
    "wasser": r"\bww-ladepumpe",
    "zirkulation": r"zirkulationspumpe(?!.*modus)",
    "zirkulation_ww": r"\bww-zirkulationspumpe(?!.*modus)",
}

# Manche Pumpen melden keinen Zustand, sondern ihre Drehzahl in Prozent – die
# Pufferladepumpe etwa. Sie zählt genauso; „läuft" heißt dann „über null".
PUMPE_BEREICHE = ("binary_sensor", "switch", "sensor")

# Woran ein Heizkreis erkennen lässt, dass an ihm Warmwasser hängt. Die
# Datenpunkte gehören am Gerät zum Heizkreis, im Schaubild ist Warmwasser aber
# ein eigener Anlagenteil – so steht es auch auf dem Display der Anlage.
WARMWASSER_IST = r"\bww[- ]temperatur aktueller|\bwarmwasser ist[- ]?temperatur"

# Die Zirkulation hängt am Gerät ebenfalls am Heizkreis, ist im Schaubild aber
# ein eigener Kreis. Ohne diese Aufteilung fehlt sie ganz, wenn die
# ZSP-Funktion selbst keine Temperatur meldet – so wie an einer der beiden
# geprüften Anlagen.
ZIRKULATION_IST = r"\bww-zirkulation ist[- ]?temperatur"

# Funktionstyp -> Art im Schaubild.
ART_JE_FCT: dict[int, str] = {
    25: "kessel",
    9: "kessel",
    1: "kessel",
    2: "kessel",
    10: "kessel",
    16: "puffer",
    14: "heizkreis",
    15: "heizkreis",
    5: "wasser",
    6: "wasser",
    4: "wasser",
    20: "zirkulation",
}
ART_UNBEKANNT = "modul"


def _art(fct_type: Any) -> str:
    try:
        return ART_JE_FCT.get(int(fct_type), ART_UNBEKANNT)
    except (TypeError, ValueError):
        return ART_UNBEKANNT


def _escape(text: str) -> str:
    """Text für die Verwendung in SVG entschärfen."""
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _finde(entitaeten: list[dict[str, Any]], muster: str) -> dict[str, Any] | None:
    """Erste Entität, deren Name zum Muster passt; eine mit Wert hat Vorrang.

    Ein Wert darf keine Bedingung sein. Das Schaubild wird gebaut, während die
    Anlage noch eingelesen wird – wäre der Wert Pflicht, bliebe es leer und
    füllte sich auch später nicht mehr.
    """
    regex = re.compile(muster, re.IGNORECASE)
    treffer = [e for e in entitaeten if regex.search(e["name"])]
    if not treffer:
        return None
    return next((e for e in treffer if e.get("hat_wert")), treffer[0])


def _werte(entitaeten: list[dict[str, Any]], art: str) -> list[dict[str, Any]]:
    """Die Messwerte eines Anlagenteils in der Reihenfolge des Schaubilds."""
    werte = []
    for muster, beschriftung in WERTE_JE_ART.get(art, ()):
        if (treffer := _finde(entitaeten, muster)) is not None:
            werte.append({"entity_id": treffer["entity_id"], "beschriftung": beschriftung})
    return werte


def _pumpe(entitaeten: list[dict[str, Any]], art: str) -> str | None:
    """Die Pumpe eines Anlagenteils, sofern sie als Zustand gemeldet wird."""
    muster = PUMPE_JE_ART.get(art)
    if not muster:
        return None
    treffer = _finde([e for e in entitaeten if e.get("bereich") in PUMPE_BEREICHE], muster)
    return treffer["entity_id"] if treffer else None


def _module(teile: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Anlagenteile, die sich zeichnen lassen, mit ihren Werten.

    Warmwasser bekommt einen eigenen Kasten, obwohl seine Datenpunkte am
    Heizkreis hängen – auf dem Display der Anlage steht es genauso.
    """
    module: list[dict[str, Any]] = []
    for teil in teile:
        art = _art(teil.get("fct_type"))
        werte = _werte(teil["entitaeten"], art)
        if werte:
            module.append(
                {
                    "titel": teil["name"],
                    "art": art,
                    "werte": werte,
                    "pumpe": _pumpe(teil["entitaeten"], art),
                }
            )
        # Hängt an diesem Kreis eine Warmwasserbereitung, wird sie als eigener
        # Anlagenteil dahinter gezeichnet.
        if art == "heizkreis" and _finde(teil["entitaeten"], WARMWASSER_IST) is not None:
            wasser = _werte(teil["entitaeten"], "wasser")
            if wasser:
                module.append(
                    {
                        "titel": "Warmwasser",
                        "art": "wasser",
                        "werte": wasser,
                        "pumpe": _pumpe(teil["entitaeten"], "wasser"),
                    }
                )
        if art == "heizkreis" and _finde(teil["entitaeten"], ZIRKULATION_IST) is not None:
            kreis = _werte(teil["entitaeten"], "zirkulation_ww")
            if kreis:
                module.append(
                    {
                        "titel": "Zirkulation",
                        "art": "zirkulation",
                        "werte": kreis,
                        "pumpe": _pumpe(teil["entitaeten"], "zirkulation_ww"),
                    }
                )
    return module


# ---------------------------------------------------------------------------
# Zeichnen
# ---------------------------------------------------------------------------
def _rohre(breite: int) -> str:
    """Vor- und Rücklauf als durchgehende Linien."""
    return (
        f'<rect x="{RAND}" y="{VORLAUF_Y - 3}" width="{breite - 2 * RAND}" height="6" rx="3" '
        f'fill="{FARBE_VORLAUF}" opacity="0.85"/>'
        f'<rect x="{RAND}" y="{RUECKLAUF_Y - 3}" width="{breite - 2 * RAND}" height="6" rx="3" '
        f'fill="{FARBE_RUECKLAUF}" opacity="0.85"/>'
    )


def _kasten(x: int, modul: dict[str, Any]) -> str:
    """Ein Anlagenteil als Form, passend zu seiner Art."""
    art = modul["art"]
    mitte = x + MODUL_BREITE // 2
    titel = (
        f'<text x="{mitte}" y="{RUECKLAUF_Y + 30}" text-anchor="middle" '
        f'fill="{FARBE_TITEL}" font-size="15" font-weight="600" font-family="{SCHRIFT}">'
        f"{_escape(modul['titel'])}</text>"
    )
    anschluss = (
        f'<rect x="{mitte - 2}" y="{VORLAUF_Y}" width="4" height="30" fill="{FARBE_VORLAUF}" '
        f'opacity="0.7"/>'
        f'<rect x="{mitte - 2}" y="{RUECKLAUF_Y - 30}" width="4" height="30" '
        f'fill="{FARBE_RUECKLAUF}" opacity="0.7"/>'
    )

    if art == "puffer":
        form = (
            f'<rect x="{mitte - 58}" y="118" width="116" height="176" rx="26" '
            f'fill="url(#schichtung)" stroke="{FARBE_RAHMEN}" stroke-width="2"/>'
            f'<line x1="{mitte - 58}" y1="206" x2="{mitte + 58}" y2="206" '
            f'stroke="{FARBE_RAHMEN}" stroke-width="1" opacity="0.5"/>'
        )
    elif art == "kessel":
        form = (
            f'<rect x="{mitte - 62}" y="122" width="124" height="168" rx="12" '
            f'fill="url(#kessel)" stroke="{FARBE_RAHMEN}" stroke-width="2"/>'
            f'<rect x="{mitte - 40}" y="238" width="80" height="34" rx="6" '
            f'fill="{FARBE_VORLAUF}" opacity="0.35"/>'
        )
    elif art == "heizkreis":
        stege = "".join(
            f'<rect x="{mitte - 48 + i * 20}" y="140" width="10" height="130" rx="5" '
            f'fill="url(#waerme)" opacity="0.9"/>'
            for i in range(5)
        )
        form = (
            f'<rect x="{mitte - 58}" y="128" width="116" height="154" rx="10" '
            f'fill="#1d242c" stroke="{FARBE_RAHMEN}" stroke-width="2"/>{stege}'
        )
    elif art == "wasser":
        form = (
            f'<rect x="{mitte - 50}" y="126" width="100" height="164" rx="46" '
            f'fill="url(#warmwasser)" stroke="{FARBE_RAHMEN}" stroke-width="2"/>'
        )
    elif art == "zirkulation":
        form = (
            f'<circle cx="{mitte}" cy="206" r="52" fill="#1d242c" '
            f'stroke="{FARBE_RAHMEN}" stroke-width="2"/>'
            f'<path d="M {mitte - 18} 182 L {mitte + 22} 206 L {mitte - 18} 230 Z" '
            f'fill="{FARBE_RUECKLAUF}" opacity="0.8"/>'
        )
    else:
        form = (
            f'<rect x="{mitte - 56}" y="132" width="112" height="148" rx="10" '
            f'fill="#1d242c" stroke="{FARBE_RAHMEN}" stroke-width="2"/>'
        )

    return anschluss + form + titel


def _beschriftungen(x: int, modul: dict[str, Any], breite: int) -> list[dict[str, Any]]:
    """Die Live-Werte eines Anlagenteils als picture-elements-Einträge."""
    mitte = x + MODUL_BREITE // 2
    # Zwei Werte werden ober- und unterhalb der Mitte gesetzt, einer mittig.
    hoehen = (170, 250) if len(modul["werte"]) > 1 else (206,)

    elemente = []
    for wert, y in zip(modul["werte"], hoehen, strict=False):
        elemente.append(
            {
                "type": "state-label",
                "entity": wert["entity_id"],
                "prefix": "",
                "style": {
                    "top": f"{y / HOEHE * 100:.1f}%",
                    "left": f"{mitte / breite * 100:.1f}%",
                    "transform": "translate(-50%, -50%)",
                    "color": "#ffffff",
                    "font-size": "15px",
                    "font-weight": "600",
                    "background": "rgba(10, 14, 19, 0.72)",
                    "padding": "3px 9px",
                    "border-radius": "8px",
                    "white-space": "nowrap",
                },
            }
        )
    return elemente


def _svg(module: list[dict[str, Any]]) -> tuple[str, int]:
    """Das Schaubild als SVG-Text und seine Breite."""
    breite = max(2 * RAND + len(module) * MODUL_BREITE, 400)
    teile = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {breite} {HOEHE}" '
        f'width="{breite}" height="{HOEHE}">',
        "<defs>",
        '<linearGradient id="schichtung" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#b3341f"/>'
        '<stop offset="55%" stop-color="#8a4a52"/>'
        '<stop offset="100%" stop-color="#25508f"/>'
        "</linearGradient>",
        '<linearGradient id="kessel" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#3b444e"/>'
        '<stop offset="100%" stop-color="#232a32"/>'
        "</linearGradient>",
        '<linearGradient id="warmwasser" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#b3341f"/>'
        '<stop offset="100%" stop-color="#6d3038"/>'
        "</linearGradient>",
        '<linearGradient id="waerme" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#e2543a"/>'
        '<stop offset="100%" stop-color="#8a3b2c"/>'
        "</linearGradient>",
        "</defs>",
        _rohre(breite),
    ]
    for platz, modul in enumerate(module):
        teile.append(_kasten(RAND + platz * MODUL_BREITE, modul))
    teile.append("</svg>")
    return "".join(teile), breite


def anlagenschema(teile: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Eine `picture-elements`-Karte für eine Anlage – oder nichts.

    Erwartet die Anlagenteile in der Form, die `dashboard._anlagen` liefert.
    """
    module = _module(teile)
    if not module:
        return None

    svg, breite = _svg(module)
    daten = base64.b64encode(svg.encode("utf-8")).decode("ascii")

    elemente: list[dict[str, Any]] = []
    pumpen: list[dict[str, Any]] = []
    for platz, modul in enumerate(module):
        x = RAND + platz * MODUL_BREITE
        elemente += _beschriftungen(x, modul, breite)
        if modul.get("pumpe"):
            # Die Pumpe sitzt im Rücklauf, unterhalb ihres Anlagenteils.
            mitte = x + MODUL_BREITE // 2
            pumpen.append(
                {
                    "entity": modul["pumpe"],
                    "left": f"{mitte / breite * 100:.2f}%",
                    "top": f"{RUECKLAUF_Y / HOEHE * 100:.2f}%",
                    "titel": modul["titel"],
                }
            )

    return {
        "type": "picture-elements",
        "image": f"data:image/svg+xml;base64,{daten}",
        "elements": elemente,
        # Die Pumpen liegen nicht im Bild: Ein Standbild kann sich nicht
        # drehen. Sie werden als eigene Marken darübergelegt.
        "pumpen": pumpen,
    }
