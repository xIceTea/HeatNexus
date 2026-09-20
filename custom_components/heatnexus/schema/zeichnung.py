"""Das Schaubild zeichnen: Layoutmaße, Kästen, Rohre, Beschriftungen.

Die Maße gelten je Anlagenart; daraus entstehen SVG-Text und die
`state-label`-Elemente an derselben Stelle.
"""

from __future__ import annotations

import base64
from typing import Any

from .bauteile import aus_datei
from .farben import FARBE_RAHMEN, FARBE_RUECKLAUF, FARBE_TITEL, FARBE_VORLAUF, FARBEN, SCHRIFT

# Maße des Schaubilds. Die Karte skaliert es auf ihre Breite, die Angaben
# sind also Verhältnisse, keine Bildpunkte.
HOEHE = 392


MODUL_BREITE = 200


RAND = 24


VORLAUF_Y = 92


RUECKLAUF_Y = 318


# Lage der Live-Werte je Anlagenart. Zwei Werte stehen ober- und unterhalb der
# Mitte, einer mittig. Bauteile mit anderer Form dürfen abweichen.
WERT_HOEHEN: dict[str, tuple[int, ...]] = {
    "puffer": (168, 258),
    "pumpenmodul": (186, 246),
    "solar": (158, 252),
}


WERT_HOEHEN_STANDARD = (170, 250)


WERT_HOEHE_EINZELN = 206


def _escape(text: str) -> str:
    """Text für die Verwendung in SVG entschärfen."""
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def speicherfuehler(modul: dict[str, Any]) -> tuple[str | None, str | None]:
    """Die Fühler, aus denen sich die Farbe des Speicherinhalts ergibt.

    Rückgabe ist ``(oben, unten)``. Der Puffer hat zwei echte Fühler
    (`21/65` TPE, `21/66` TPA) und zeigt damit eine Schichtung: Ist er
    durchgeladen, steht er durchgehend in einer Farbe; steht unten kaltes
    Wasser, sieht man die Grenze. Der Boiler meldet nur einen Istwert und wird
    deshalb gleichmäßig eingefärbt – eine zweite Temperatur zu erfinden wäre
    schlimmer als keine: Er sähe halb geladen aus, ohne dass es jemand
    gemessen hätte.
    """
    art = modul.get("art")
    if art not in SPEICHER_ARTEN:
        return None, None

    def suche(*beschriftungen: str) -> str | None:
        for wert in modul.get("werte", []):
            if wert.get("beschriftung") in beschriftungen:
                return wert.get("entity_id")
        return None

    if art == "puffer":
        oben, unten = suche("oben"), suche("unten")
        # Ein einzelner Pufferfühler ergibt keine Schichtung. Dann bleibt es
        # bei der gezeichneten Füllung.
        return (oben, unten) if oben and unten else (None, None)
    return suche("Warmwasser"), None


def hat_speicherfarbe(modul: dict[str, Any]) -> bool:
    """Ob die Oberfläche den Inhalt dieses Speichers einfärbt.

    Eine Stelle für zwei Entscheidungen: ob der Körper in der Zeichnung
    ungefüllt bleibt und ob eine Farbfläche darunter kommt. Liefen die
    auseinander, stünde entweder ein farbloses Loch im Bild oder wieder ein
    Farbklotz über der Zeichnung.
    """
    return speicherfuehler(modul)[0] is not None


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


# Mitte eines Bauteilfeldes in dessen eigenem Koordinatensystem. Bauteile
# zeichnen bei 0…MODUL_BREITE; erst das Gesamtbild schiebt sie an ihren Platz.
MITTE = MODUL_BREITE // 2


# Ober- und Unterkante der Bauteilzeichnung je Art.
#
# Die Anschlussstutzen reichen bis dorthin. Vorher waren sie fest 30 Bildpunkte
# lang, die Bauteile fangen aber verschieden hoch an: Beim Pumpenmodul (y=150)
# endete der Stutzen bei 122 und darunter klaffte ein Loch, beim Kessel (y=120)
# lag er richtig. Ein paar Punkte zu tief schadet nichts – der Stutzen wird vor
# dem Bauteil gezeichnet und verschwindet dahinter.
KANTEN_JE_ART: dict[str, tuple[int, int]] = {
    "kessel": (126, 288),
    "puffer": (116, 296),
    "heizkreis": (132, 278),
    "wasser": (124, 292),
    "zirkulation": (148, 264),
    "pumpenmodul": (150, 266),
    "solar": (158, 244),
    "umschaltung": (132, 284),
    "modul": (132, 280),
    "heizstab": (150, 270),
    "fremdquelle": (152, 264),
}


KANTEN_STANDARD = (126, 288)


# Lage des Glutbetts im Kessel. Dort legt die Oberfläche einen Schein darüber,
# solange der Kessel Leistung bringt. Die Werte stammen aus den Zeichnungen
# `kessel-*.svg`, in denen der Brennraum bei y = 230…282 sitzt.
GLUTBETT_Y = 258


GLUTBETT_BREITE = 76


# Lage des Mischers im Heizkreis – dieselbe Stelle, an der `heizkreis.svg` das
# Ventil zeichnet. Darüber liegt der Stellungsanzeiger, darunter das Stück
# Vorlauf, dessen Farbe die Beimischung zeigt.
MISCHER_Y = 112


MISCHER_MARKE = 26


# Der Körper des Heizkörpers: die fünf Glieder aus `heizkreis.svg`, von x = 50
# bis x = 152 und von y = 140 bis y = 272. Die Zeichnung füllt sie mit einem
# festen Verlauf – ein Heizkörper, der immer gleich glüht, auch wenn 27 °C
# durchlaufen. Darüber liegt deshalb eine eigene Ebene, die ihre Farbe aus der
# Vorlauftemperatur nimmt.
HEIZKOERPER_X = 50


HEIZKOERPER_BREITE = 102


HEIZKOERPER_Y = 140


HEIZKOERPER_HOEHE = 132


# Das Raster der Glieder, ebenfalls aus `heizkreis.svg`: jedes Glied 14 breit,
# der Abstand von Glied zu Glied 22. Fünf Glieder ergeben 5 × 22 − 8 = 102 und
# damit genau HEIZKOERPER_BREITE.
#
# **Diese beiden Zahlen gehören als Anteil in die Ansicht, nicht als
# Bildpunkte.** Die Karte skaliert das Bild auf ihre Breite; ein Streifenmuster
# in festen Bildpunkten sitzt danach neben den gezeichneten Gliedern, und
# dazwischen blitzt die rote Füllung der Zeichnung durch – der Heizkörper sah
# blau-rot gestreift aus.
HEIZKOERPER_GLIED = 14


HEIZKOERPER_RASTER = 22


HEIZKOERPER_ANZAHL = 5


# Die Glanzkante in jedem Glied, aus derselben Datei: 4 breit, 3 vom linken
# Rand des Glieds entfernt. Sie liegt in der Zeichnung *über* der Füllung und
# wird von der Ebene verdeckt – deshalb malt die Ebene sie mit.
HEIZKOERPER_GLANZ_VON = 3


HEIZKOERPER_GLANZ_BIS = 7


# Die Skala dafür. Unten die Farbe des Rücklaufs, oben die des Vorlaufs –
# dieselben beiden Farben, die auch die Leitungen tragen, damit das Bild eine
# Sprache spricht.
#
# Die Grenzen sind keine Erfindung: Die Anlage meldet als Bereich für „Vorlauf
# min." 10–50 °C und für „Vorlauf max." 30–90 °C. 25 °C ist damit sicher kalt,
# 65 °C sicher heiß, und dazwischen liegt der Bereich, in dem sich ein
# Heizkreis tatsächlich bewegt.
HEIZKOERPER_KALT = 25.0


HEIZKOERPER_HEISS = 65.0


# Speicher, deren Inhalt eingefärbt wird: Puffer und Warmwasserboiler.
#
# Die Farbe liegt **unter** der Zeichnung. Das Bauteil lässt seinen Körper
# ungefüllt (`{{koerper}}` wird zu `none`), die Oberfläche legt die gemessene
# Temperatur darunter, und alles Gezeichnete – Kontur, Dämmnähte, Stutzen,
# Register – bleibt darüber sichtbar. Läge die Farbe oben, deckte sie das zu.
#
# Je Art die Geometrie ihres Körpers, wörtlich aus der Bauteildatei:
#   Puffer  `puffer.svg`  x = 42…158, y = 116…296, Eckradius 30
#   Boiler  `wasser.svg`  x = 48…152, y = 124…292, Eckradius 48
#
# `kalt`/`heiss` spannen die Skala. Weiter gefasst als beim Heizkörper: Ein
# Puffer wird bis 75…85 °C geladen (so melden es die beiden geprüften Anlagen
# als „Puffer Maximaltemperatur") und kann unten auf Rücklaufniveau abkühlen.
# Der Boiler bleibt darunter – 60 °C ist die übliche Solltemperatur, darüber
# liegt nur noch die Legionellenschaltung.
#
# `grund` ist der Verlauf, den die Fläche ohne Messwerte trägt: derselbe, den
# die Zeichnung sonst selbst gemalt hätte. Ohne ihn klaffte beim Laden ein
# Loch im Bauteil.
SPEICHER_ARTEN: dict[str, dict[str, Any]] = {
    "puffer": {
        "x": 42,
        "y": 116,
        "breite": 116,
        "hoehe": 180,
        "ecke": 30,
        "kalt": 25.0,
        "heiss": 80.0,
        "fuellung": "url(#schichtung)",
        "grund": f"linear-gradient(to bottom, {FARBEN['korpus_hell']} 0%, "
        f"{FARBEN['korpus_dunkel']} 100%)",
    },
    "wasser": {
        "x": 48,
        "y": 124,
        "breite": 104,
        "hoehe": 168,
        "ecke": 48,
        "kalt": 20.0,
        "heiss": 65.0,
        "fuellung": "url(#boiler)",
        "grund": f"linear-gradient(to bottom, {FARBEN['warm']} 0%, "
        f"{FARBEN['warm']} 70%, {FARBEN['kalt']} 100%)",
    },
}


# Zwischen den beiden Temperaturen des Puffers ist Platz für ein Wort.
# `WERT_HOEHEN["puffer"]` setzt sie auf 168 und 258.
SPEICHER_Y = 213


# Wie viel wärmer als der untere Fühler der Kessel sein muss, damit die Ladung
# gilt. Dort holt die Ladepumpe ihr Wasser; liegt der Kessel darüber, trägt sie
# Wärme ein – auch wenn der obere Bereich längst wärmer ist als der Kessel.
LADE_TOLERANZ = 0.5


# Die Lampen des Pumpen-/Relaismoduls, aus `pumpenmodul.svg`: fünf Klemmen
# oben, eine Betriebslampe rechts unten. Liegt eine Wärmeanforderung an,
# blinken die Klemmen grün und die Betriebslampe wechselt von Rot auf Grün –
# so sieht man am Bild selbst, dass gerade angefordert wird.
# Die Radien sind größer als die gezeichneten Punkte darunter: Die grüne
# Lampe muss die rote vollständig verdecken, sonst schimmert Rot am Rand
# durch.
ZSP_KLEMMEN = ((72, 164, 4), (86, 164, 4), (100, 164, 4), (114, 164, 4), (128, 164, 4))


ZSP_BETRIEBSLAMPE = (136, 252, 6)


# Gehäuse und gezeichnete Pumpe des Moduls, wörtlich aus `pumpenmodul.svg`.
# Liegt eine Wärmeanforderung an, legt die Oberfläche darüber die Wärme im
# Gehäuse, ein langsam drehendes Laufrad und die Abgabe nach außen.
ZSP_GEHAEUSE = (52, 150, 96, 116)


ZSP_PUMPE = (100, 212, 26)


# Arten, deren Pumpe dem Speicher Wärme entnimmt.
ENTNAHME_ARTEN = ("heizkreis", "wasser", "zirkulation", "pumpenmodul")


def _ersatzform(art: str) -> str:
    """Gezeichnete Form, wenn es für ein Anlagenteil keine Datei gibt.

    Bewusst schlicht: Sie ist der Rückfall, nicht die Gestaltung. Ein fehlendes
    Bauteil darf das Schaubild nicht zerreißen.
    """
    if art == "puffer":
        return (
            f'<rect x="{MITTE - 58}" y="118" width="116" height="176" rx="26" '
            f'fill="{FARBEN["warm"]}" stroke="{FARBE_RAHMEN}" stroke-width="2"/>'
        )
    if art == "zirkulation":
        return (
            f'<circle cx="{MITTE}" cy="206" r="52" fill="{FARBEN["korpus_dunkel"]}" '
            f'stroke="{FARBE_RAHMEN}" stroke-width="2"/>'
        )
    return (
        f'<rect x="{MITTE - 56}" y="126" width="112" height="160" rx="12" '
        f'fill="{FARBEN["korpus"]}" stroke="{FARBE_RAHMEN}" stroke-width="2"/>'
    )


def _kasten(
    x: int, platz: int, modul: dict[str, Any], kesselart: str | None, mischer: bool = True
) -> str:
    """Ein Anlagenteil an seinem Platz im Gesamtbild."""
    art = modul["art"]
    # Der Speicherkörper bleibt leer, wenn die Oberfläche die gemessene
    # Temperatur darunterlegt – sonst deckt sie die Zeichnung zu.
    zusatz = {}
    if (masse := SPEICHER_ARTEN.get(art)) is not None:
        zusatz["koerper"] = "none" if hat_speicherfarbe(modul) else masse["fuellung"]
    inhalt = aus_datei(
        art,
        kesselart if art == "kessel" else None,
        f"t{platz}-",
        zusatz,
        modul.get("zeichnung"),
    )
    if inhalt is None:
        inhalt = _ersatzform(art)
    # Das Stellglied des Heizkreises steht in einer eigenen Datei: Wer es nicht
    # sehen will, bekommt den Kreis ohne Ventil.
    if (
        mischer
        and art == "heizkreis"
        and modul.get("mischer")
        and (zeichen := aus_datei(art, None, f"t{platz}-m", None, "heizkreis-mischer")) is not None
    ):
        inhalt += zeichen

    oben, unten = KANTEN_JE_ART.get(art, KANTEN_STANDARD)
    anschluss = (
        f'<rect x="{MITTE - 2}" y="{VORLAUF_Y}" width="4" height="{oben - VORLAUF_Y}" '
        f'fill="{FARBE_VORLAUF}" opacity="0.7"/>'
        f'<rect x="{MITTE - 2}" y="{unten}" width="4" height="{RUECKLAUF_Y - unten}" '
        f'fill="{FARBE_RUECKLAUF}" opacity="0.7"/>'
    )
    # Größer als die Messwerte darüber: Der Name des Anlagenteils ist das
    # erste, wonach man im Schaubild sucht, und die Karte skaliert das Bild
    # auf ihre Breite – bei vier Anlagenteilen wird daraus schnell Kleingedrucktes.
    titel = (
        f'<text x="{MITTE}" y="{RUECKLAUF_Y + 58}" text-anchor="middle" '
        f'fill="{FARBE_TITEL}" font-size="19" font-weight="600" font-family="{SCHRIFT}">'
        f"{_escape(modul['titel'])}</text>"
    )
    return f'<g transform="translate({x},0)">{anschluss}{inhalt}{titel}</g>'


def beschriftungen(x: int, modul: dict[str, Any], breite: int) -> list[dict[str, Any]]:
    """Die Live-Werte eines Anlagenteils als picture-elements-Einträge."""
    mitte = x + MODUL_BREITE // 2
    # Zwei Werte werden ober- und unterhalb der Mitte gesetzt, einer mittig.
    hoehen = (
        WERT_HOEHEN.get(modul["art"], WERT_HOEHEN_STANDARD)
        if len(modul["werte"]) > 1
        else (WERT_HOEHE_EINZELN,)
    )

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


def schaubild_svg(
    module: list[dict[str, Any]], kesselart: str | None, mischer: bool = True
) -> tuple[str, int]:
    """Das Schaubild als SVG-Text und seine Breite."""
    breite = max(2 * RAND + len(module) * MODUL_BREITE, 400)
    teile = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {breite} {HOEHE}" '
        f'width="{breite}" height="{HOEHE}">',
        _rohre(breite),
    ]
    for platz, modul in enumerate(module):
        teile.append(_kasten(RAND + platz * MODUL_BREITE, platz, modul, kesselart, mischer))
    teile.append("</svg>")
    return "".join(teile), breite


def datenadresse(svg: str) -> str:
    """Ein fertiges SVG als `data:`-Adresse für ein `<img>`."""
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
