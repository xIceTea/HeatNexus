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
import importlib.util
from pathlib import Path
import re
import sys
from types import ModuleType

WURZEL = Path(__file__).resolve().parent.parent
KOMPONENTE = WURZEL / "custom_components" / "heatnexus"
ZIEL_DUNKEL = WURZEL / "assets" / "anlagenschema_beispiel.svg"
ZIEL_HELL = WURZEL / "assets" / "anlagenschema_beispiel_hell.svg"


def _schema() -> ModuleType:
    """`schema.py` laden – es kommt ohne Home Assistant aus."""
    paket = "heatnexus_schaubild"
    ersatz = ModuleType(paket)
    ersatz.__path__ = [str(KOMPONENTE)]
    sys.modules[paket] = ersatz
    spec = importlib.util.spec_from_file_location(f"{paket}.schema", KOMPONENTE / "schema.py")
    modul = importlib.util.module_from_spec(spec)
    sys.modules[f"{paket}.schema"] = modul
    spec.loader.exec_module(modul)
    return modul


def _teil(name: str, fct: int, werte: list[tuple[str, str]]) -> dict:
    """Ein Anlagenteil in der Form, die `dashboard._anlagen` liefert."""
    return {
        "name": name,
        "fct_type": fct,
        "entitaeten": [
            {
                "entity_id": eid,
                "name": bezeichnung,
                "hat_wert": True,
                "bereich": eid.split(".")[0],
            }
            for eid, bezeichnung in werte
        ],
    }


# Die Beispielanlage. Sie zeigt die Teile, die eine übliche Installation
# hergibt – Kessel, Puffer, Heizkreis mit Warmwasser und Zirkulation, dazu ein
# Pumpen-/Relaismodul. Bewusst keine erfundene Sonderanlage: Das Bild soll
# zeigen, was der Nutzer bekommt, nicht was maximal ginge.
BEISPIEL = [
    _teil(
        "PuroWIN",
        25,
        [("sensor.kessel", "Kesseltemperatur Ist"), ("sensor.leistung", "Kesselleistung")],
    ),
    _teil(
        "B-PLMi PUFFER",
        16,
        [
            ("sensor.puffer_oben", "Puffer oben Temperatur (TPE)"),
            ("sensor.puffer_unten", "Puffer unten Temperatur (TPA)"),
        ],
    ),
    _teil(
        "UMLZ HEIZKREIS",
        14,
        [
            ("sensor.vorlauf", "Vorlauftemperatur Ist"),
            ("sensor.raum", "Raumtemperatur Ist"),
            ("sensor.warmwasser", "Warmwasser Ist-Temperatur"),
            ("sensor.zirkulation", "WW-Zirkulation Ist-Temperatur"),
        ],
    ),
]

# Beispielwerte je Entität. Sie stammen aus einem Betriebszustand, wie er an
# einem Wintertag wirklich vorkommt: Kessel im Volllastbetrieb, Puffer oben
# warm, unten kühler, Heizkreis in Betrieb.
WERTE = {
    "sensor.kessel": "72,4 °C",
    "sensor.leistung": "38 %",
    "sensor.puffer_oben": "68,1 °C",
    "sensor.puffer_unten": "42,7 °C",
    "sensor.vorlauf": "45,0 °C",
    "sensor.raum": "21,5 °C",
    "sensor.warmwasser": "51,2 °C",
    "sensor.zirkulation": "38,6 °C",
}

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


def bild(karte: dict, farbsatz: str) -> str:
    """Ein fertiges Standbild: Untergrund, Zeichnung, Beispielwerte."""
    quelle = karte["image"] if farbsatz == "hell" else karte["dark_mode_image"]
    svg = base64.b64decode(quelle.split(",", 1)[1]).decode("utf-8")
    breite, hoehe = _masse(svg)
    stil = STIL[farbsatz]
    untergrund = f'<rect width="100%" height="100%" rx="16" fill="{stil["hintergrund"]}"/>'
    svg = re.sub(r"(<svg[^>]*>)", rf"\1{untergrund}", svg, count=1)
    kacheln = _kacheln(karte["elements"], breite, hoehe, stil)
    return svg.replace("</svg>", f"{kacheln}</svg>")


def main() -> None:
    karte = _schema().anlagenschema(BEISPIEL)
    if not karte:
        raise SystemExit("Die Beispielanlage ergibt kein Schaubild.")
    for ziel, farbsatz in ((ZIEL_DUNKEL, "dunkel"), (ZIEL_HELL, "hell")):
        ziel.write_text(bild(karte, farbsatz), encoding="utf-8")
        print(f"geschrieben: {ziel.relative_to(WURZEL)}")


if __name__ == "__main__":
    main()
