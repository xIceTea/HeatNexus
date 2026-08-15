"""Die fünf Farbsätze des Schaubilds als bewegtes Bild.

Ein Standbild je Satz zeigt fünf Bilder nebeneinander und beantwortet die
Frage nicht, um die es geht: wie dieselbe Anlage in einem anderen Satz
aussieht. Hier läuft sie durch – Dunkel, Hell, Terrakotta, Petrol, Pflaume –
während Pumpen und Strömung weitergehen.

Aufgebaut auf `build_schaubild_animation.py`: dieselbe Zeichnung, dieselben
Ebenen, dasselbe Stylesheet der Oberfläche. Hier kommen nur zwei Dinge dazu,
die der Farbsatz ändert und die nicht im Bild stecken:

* die Zeichnung selbst, umgestellt über `schema.farben_umstellen`,
* die Farbvariablen der Oberfläche aus `PALETTEN` in `ordnung.js` – von ihnen
  hängen Kartengrund, Linien und der Akzent der laufenden Pumpe ab.

    python tools/build_farbsaetze_animation.py
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))

from beispielanlage import WURZEL, karte, schema_modul
import build_schaubild_animation as bewegung

ZIEL = WURZEL / "assets" / "anlagenschema_farbsaetze.gif"

# Reihenfolge im Film. Dunkel steht am Anfang: Es ist die Vorgabe.
SAETZE = ["dunkel", "hell", "terrakotta", "petrol", "pflaume"]
NAMEN = {
    "dunkel": "Dunkel",
    "hell": "Hell",
    "terrakotta": "Terrakotta",
    "petrol": "Petrol",
    "pflaume": "Pflaume",
}

# Wie lange ein Satz steht. Zwölf Aufnahmen zu 100 ms sind gut eine Sekunde –
# lang genug zum Hinsehen, kurz genug, dass der Film nicht zieht.
JE_SATZ = 12

# Der Zustand, in dem die Anlage gezeigt wird. Gewählt ist der einzige
# Augenblick, in dem **alle fünf** Pumpen fördern: Steht eine still, sieht es
# im Standbild nach einem Fehler aus statt nach Betrieb.
SZENE = 50


def _temperaturfarben() -> dict[str, dict[str, str]]:
    """Warm und kalt je Satz – sie färben Speicherinhalt und Heizkörper."""
    schema = schema_modul()
    saetze = {
        "dunkel": schema.FARBEN,
        "hell": schema.FARBEN_HELL,
        "terrakotta": schema.FARBEN_TERRAKOTTA,
        "petrol": schema.FARBEN_PETROL,
        "pflaume": schema.FARBEN_PFLAUME,
    }
    return {name: {"warm": f["warm"], "kalt": f["kalt"]} for name, f in saetze.items()}


def _zeichnung(svg: str, satz: str) -> str:
    """Die Zeichnung im gewünschten Satz als Datenadresse."""
    schema = schema_modul()
    umgestellt = svg if satz == "dunkel" else schema.farben_umstellen(svg, satz)
    kodiert = base64.b64encode(umgestellt.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{kodiert}"


def _aufnahme(daten: dict, bild_nr: int, satz: str, quelle: str, temperatur: dict) -> str:
    """Eine Aufnahme im gegebenen Farbsatz."""
    lage = bewegung.zustand(SZENE)
    sekunde = bild_nr * bewegung.BILD_DAUER_MS / 1000
    halt = (
        f"<style>.b{bild_nr} .schaubild *{{animation-play-state:paused !important;"
        f"animation-delay:-{sekunde:.2f}s !important}}</style>"
    )
    return (
        f'{halt}<div class="rahmen b{bild_nr} satz-{satz}"><div class="schaubild">'
        f'<img src="{quelle}" alt="">'
        f"{bewegung._schichtung(daten, lage, temperatur)}"
        f"{bewegung._fluss(daten, lage)}"
        f"{bewegung._glut(daten, lage)}"
        f"{bewegung._heizkoerper(daten, lage, temperatur)}"
        f"{bewegung._speicher(daten, lage)}"
        f"{bewegung._werte(daten, lage)}"
        f"{bewegung._senkrecht(daten, lage)}"
        f"{bewegung._pumpen(daten, lage)}"
        f"</div>"
        f'<div class="satzname">{NAMEN[satz]}</div>'
        f"</div>"
    )


def _seite(
    daten: dict, auftraege: list[tuple[int, str]], paletten: dict, temperaturen: dict
) -> str:
    """Mehrere Aufnahmen untereinander, jede in ihrem Satz."""
    svg = daten["svg"]
    bloecke = "".join(
        _aufnahme(daten, nr, satz, _zeichnung(svg, satz), temperaturen[satz])
        for nr, satz in auftraege
    )
    # Je Satz die Farbvariablen der Oberfläche. Ohne sie bliebe der Akzent der
    # laufenden Pumpe in allen fünf Sätzen derselbe.
    regeln = []
    for satz in SAETZE:
        werte = "".join(f"{name}:{wert};" for name, wert in paletten[satz].items())
        regeln.append(f".satz-{satz}{{{werte}background:{paletten[satz]['--hn-karte']}}}")
    return (
        "<!doctype html><meta charset='utf-8'><style>"
        "html,body{margin:0;padding:0}"
        f".rahmen{{width:{bewegung.BREITE}px;height:{bewegung.HOEHE}px;"
        "overflow:hidden;position:relative}"
        ".satzname{position:absolute;left:24px;top:18px;"
        "font:600 20px/1 system-ui,-apple-system,Roboto,sans-serif;"
        "color:var(--hn-text);opacity:0.7;letter-spacing:0.02em}"
        f"{''.join(regeln)}"
        f"{bewegung._stil()}</style>{bloecke}"
    )


def _aufnehmen(daten: dict, browser: str, arbeit: Path) -> list:
    """Alle Aufnahmen, Seite für Seite."""
    from PIL import Image

    auftraege = [(nr, satz) for satz in SAETZE for nr in range(JE_SATZ)]
    paletten = bewegung.paletten()
    temperaturen = _temperaturfarben()
    bilder: list[Image.Image] = []
    for anfang in range(0, len(auftraege), bewegung.JE_SEITE):
        teilliste = auftraege[anfang : anfang + bewegung.JE_SEITE]
        html = arbeit / f"farbsaetze_{anfang}.html"
        html.write_text(_seite(daten, teilliste, paletten, temperaturen), encoding="utf-8")
        aufnahme_datei = arbeit / f"farbsaetze_{anfang}.png"
        subprocess.run(
            [
                browser,
                "--headless",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--window-size={bewegung.BREITE},{bewegung.HOEHE * len(teilliste)}",
                f"--screenshot={aufnahme_datei}",
                html.as_uri(),
            ],
            check=True,
            capture_output=True,
        )
        seite_bild = Image.open(aufnahme_datei).convert("RGB")
        hoehe = round(bewegung.HOEHE * bewegung.GIF_BREITE / bewegung.BREITE)
        for platz in range(len(teilliste)):
            teil = seite_bild.crop(
                (0, platz * bewegung.HOEHE, bewegung.BREITE, (platz + 1) * bewegung.HOEHE)
            )
            bilder.append(teil.resize((bewegung.GIF_BREITE, hoehe), Image.LANCZOS))
        print(f"aufgenommen: {teilliste[0][1]} … {teilliste[-1][1]}")
    return bilder


def _schreiben(bilder: list) -> None:
    """Die Bildfolge als GIF ablegen.

    Eine gemeinsame Farbtafel über alle fünf Sätze, damit die Verdichtung
    zwischen den Bildern greift. Bei fünf verschiedenen Gehäusefarben braucht
    sie mehr Platz als die des einzelnen Satzes – daher 256 statt 128.
    """
    from PIL import Image

    streifen = Image.new("RGB", (bilder[0].width, bilder[0].height * len(SAETZE)))
    for platz in range(len(SAETZE)):
        streifen.paste(bilder[platz * JE_SATZ], (0, platz * bilder[0].height))
    tafel = streifen.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    gemeinsam = [b.quantize(palette=tafel, dither=Image.Dither.NONE) for b in bilder]
    gemeinsam[0].save(
        ZIEL,
        save_all=True,
        append_images=gemeinsam[1:],
        duration=bewegung.BILD_DAUER_MS,
        loop=0,
        optimize=True,
    )
    groesse = ZIEL.stat().st_size / 1024
    print(f"geschrieben: {ZIEL.relative_to(WURZEL)} ({groesse:.0f} kB, {len(bilder)} Bilder)")


def main() -> None:
    daten = karte()
    browser = bewegung._browser()
    with tempfile.TemporaryDirectory() as ordner:
        _schreiben(_aufnehmen(daten, browser, Path(ordner)))


if __name__ == "__main__":
    main()
    print(json.dumps({"saetze": SAETZE, "je_satz": JE_SATZ}, ensure_ascii=False))
