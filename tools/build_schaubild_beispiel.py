"""Das Beispiel-Schaubild für README und Dokumentation erzeugen.

**Warum es dieses Werkzeug gibt.** Das Bild in `assets/` war einmal von Hand
zusammengesetzt worden – und stand danach vier Fassungen lang unverändert da,
während sich die Zeichnung weiterentwickelte. Wer das README aufschlug, sah
einen Stand, den die Integration längst nicht mehr ausliefert.

Erzeugt wird deshalb aus derselben Quelle, aus der auch die Anlage ihr
Schaubild bekommt: `schema.anlagenschema()`. Neu erzeugen mit

    python tools/build_schaubild_beispiel.py

Zwei Dateien entstehen, für den hellen und den dunklen Farbsatz – das README
zeigt über ``<picture>`` je nach Erscheinungsbild das passende.

Die Messwerte trägt die Anlage im Betrieb als eigene Elemente über das Bild
(`picture-elements`). Für ein Standbild geht das nicht, deshalb werden hier
Beispielwerte an genau den Stellen eingesetzt, an denen die Karte sie später
auch anzeigt: aus `elements[…]["style"]`, nicht nach Augenmaß.
"""

from __future__ import annotations

import base64
from pathlib import Path
import re
import sys

# Der Nachbar im selben Verzeichnis. Die Zeile ist nötig, weil dieses Werkzeug
# auch über den Dateipfad geladen wird (aus dem Test heraus) und dann nicht im
# Suchpfad steht.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from beispielanlage import STANDBILD as WERTE
from beispielanlage import TEILE as BEISPIEL  # noqa: F401  (der Test greift darauf zu)
from beispielanlage import WURZEL, karte, schema_modul

ZIEL_DUNKEL = WURZEL / "assets" / "anlagenschema_beispiel.svg"
ZIEL_HELL = WURZEL / "assets" / "anlagenschema_beispiel_hell.svg"

# Die Beschriftung ahmt die Kachel der `picture-elements`-Karte nach: heller
# Text auf abgedunkeltem Grund. Im hellen Farbsatz kehrt sich das um, sonst
# stünde weiße Schrift auf weißem Papier.
#
# `hintergrund` gibt es nur hier. In Home Assistant sitzt die Zeichnung auf
# einer Karte und bekommt deren Untergrund; als einzelne Datei im README hat
# sie keinen. Ohne ihn stünde die dunkle Beschriftung auf weißem Papier und
# wäre praktisch unlesbar – genau so sah das alte Bild aus.
STIL = {
    "dunkel": {
        "schrift": "#ffffff",
        "grund": "rgba(10, 14, 19, 0.72)",
        "hintergrund": "#151d26",
    },
    "hell": {
        "schrift": "#12181f",
        "grund": "rgba(255, 255, 255, 0.82)",
        "hintergrund": "#f4f6f9",
    },
}
SCHRIFTGROESSE = 15
ZEICHENBREITE = 8.2  # Näherung für die Breite der Kachel
KACHEL_HOEHE = 24


def _schema():
    """Der Zugang zum Zeichenmodul, den auch der Test benutzt."""
    return schema_modul()


def _masse(svg: str) -> tuple[float, float]:
    """Breite und Höhe aus dem viewBox."""
    _, _, breite, hoehe = re.search(r'viewBox="([^"]+)"', svg).group(1).split()
    return float(breite), float(hoehe)


def _prozent(wert: str) -> float:
    return float(wert.rstrip("%")) / 100


def _kacheln(elemente: list[dict], breite: float, hoehe: float, farben: dict) -> str:
    """Die Beispielwerte als SVG-Kacheln, an den Stellen der echten Karte."""
    teile = []
    for element in elemente:
        text = WERTE.get(element["entity"])
        if not text:
            continue
        stil = element["style"]
        x = _prozent(stil["left"]) * breite
        y = _prozent(stil["top"]) * hoehe
        kachel = max(len(text) * ZEICHENBREITE + 18, 44)
        teile.append(
            f'<rect x="{x - kachel / 2:.1f}" y="{y - KACHEL_HOEHE / 2:.1f}" '
            f'width="{kachel:.1f}" height="{KACHEL_HOEHE}" rx="8" fill="{farben["grund"]}"/>'
            f'<text x="{x:.1f}" y="{y + 5:.1f}" text-anchor="middle" '
            f'font-family="system-ui, -apple-system, Segoe UI, sans-serif" '
            f'font-size="{SCHRIFTGROESSE}" font-weight="600" '
            f'fill="{farben["schrift"]}">{text}</text>'
        )
    return "".join(teile)


def bild(karte_daten: dict, farbsatz: str) -> str:
    """Ein fertiges Standbild: Untergrund, Zeichnung, Beispielwerte."""
    quelle = karte_daten["image"] if farbsatz == "hell" else karte_daten["dark_mode_image"]
    svg = base64.b64decode(quelle.split(",", 1)[1]).decode("utf-8")
    breite, hoehe = _masse(svg)
    stil = STIL[farbsatz]
    untergrund = f'<rect width="100%" height="100%" rx="16" fill="{stil["hintergrund"]}"/>'
    svg = re.sub(r"(<svg[^>]*>)", rf"\1{untergrund}", svg, count=1)
    kacheln = _kacheln(karte_daten["elements"], breite, hoehe, stil)
    return svg.replace("</svg>", f"{kacheln}</svg>")


def main() -> None:
    daten = karte()
    for ziel, farbsatz in ((ZIEL_DUNKEL, "dunkel"), (ZIEL_HELL, "hell")):
        ziel.write_text(bild(daten, farbsatz), encoding="utf-8")
        print(f"geschrieben: {ziel.relative_to(WURZEL)}")


if __name__ == "__main__":
    main()
