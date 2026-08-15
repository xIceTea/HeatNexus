"""Das bewegte Schaubild für das README erzeugen.

**Was hier entsteht.** Ein Standbild zeigt eine Anlage, aber nicht, was sie
tut. Die Oberfläche bewegt das Schaubild: Pumpen drehen sich, die Bänder auf
Vor- und Rücklauf zeigen die Förderrichtung, der Puffer meldet „lädt" oder
„entlädt", das Glutbett folgt der Kesselleistung, Speicher und Heizkörper
färben sich nach ihren Fühlern. Im README war davon nichts zu sehen.

**Wie es entsteht.** Nicht nachgebaut, sondern abgefilmt: Der Ablauf setzt
dieselbe Zeichnung, dieselben Zustandsklassen und **dasselbe Stylesheet** ein,
das die Oberfläche benutzt (`frontend/stil.js`). Die Bewegung wird dabei
angehalten und Bild für Bild um einen festen Zeitschritt weitergestellt
(`animation-delay` plus `animation-play-state: paused`); ein kopfloser Browser
macht die Aufnahmen, Pillow legt sie zum GIF zusammen.

Damit kann das Bild nicht auseinanderlaufen: Ändert sich die Bewegung in der
Oberfläche, ändert sie sich beim nächsten Lauf hier mit.

    python tools/build_schaubild_animation.py

Eine Näherung bleibt: `color-mix` löst der Browser auf – im GIF steht das
Ergebnis, nicht die Rechnung.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))

from beispielanlage import KOMPONENTE, WURZEL, karte

ZIELE = {
    "dunkel": WURZEL / "assets" / "anlagenschema_animation.gif",
    "hell": WURZEL / "assets" / "anlagenschema_animation_hell.gif",
}
STIL_DATEI = KOMPONENTE / "frontend" / "stil.js"

# Der Untergrund je Farbsatz. Die Marken darüber bleiben in beiden Fällen
# dunkel – so hält es die Oberfläche auch, ihr Stylesheet kennt für sie nur
# einen Satz Farben.
UNTERGRUND = {"dunkel": "#151d26", "hell": "#f4f6f9"}

BREITE, HOEHE = 1048, 392
# Auf diese Breite wird das GIF verkleinert. 1048 Bildpunkte mal sechzig
# Aufnahmen wären als GIF zweistellig megabyteschwer; das README zeigt es
# ohnehin schmaler.
GIF_BREITE = 880
BILD_DAUER_MS = 100
# So viele Aufnahmen kommen auf eine Seite. Mehr macht die Seite so hoch, dass
# der kopflose Browser sie abschneidet.
JE_SEITE = 10

SCHAUBILD_DATEI = KOMPONENTE / "frontend" / "teile" / "schaubild.js"


def _laufrad() -> str:
    """Das Laufrad der Oberfläche, aus `teile/schaubild.js` gelesen.

    Abgeschrieben liefe es auseinander: Der Drehpunkt liegt im Nullpunkt des
    Kastens, und genau daran hängt, ob das Rad rund läuft oder eiert.
    """
    quelle = SCHAUBILD_DATEI.read_text(encoding="utf-8")
    treffer = re.search(r"rad\.innerHTML =\s*(.*?);", quelle, re.S)
    if not treffer:
        raise SystemExit("Das Laufrad in teile/schaubild.js nicht gefunden.")
    inhalt = "".join(re.findall(r"'([^']*)'", treffer.group(1)))
    return f'<svg viewBox="-12 -12 24 24" aria-hidden="true">{inhalt}</svg>'


# ---------------------------------------------------------------------------
# Der Ablauf
# ---------------------------------------------------------------------------
# Eine Heizsaison in sechs Sekunden: Die Anlage steht, der Kessel springt an,
# der Puffer lädt und wird von oben nach unten wärmer, der Heizkreis nimmt
# Wärme ab, danach Warmwasser und Zirkulation. Zum Schluss geht die
# Pufferladung aus – dann steht am Speicher „entlädt".
BILDER = 60


def _rampe(bild: int, von_bild: int, bis_bild: int, von: float, bis: float) -> float:
    """Ein Wert, der zwischen zwei Aufnahmen gleichmäßig übergeht."""
    if bild <= von_bild:
        return von
    if bild >= bis_bild:
        return bis
    anteil = (bild - von_bild) / (bis_bild - von_bild)
    return von + (bis - von) * anteil


def zustand(bild: int) -> dict:
    """Messwerte und Pumpenzustände einer einzelnen Aufnahme."""
    kessel = _rampe(bild, 8, 22, 28, 76)
    kessel = _rampe(bild, 50, 59, kessel, 68) if bild >= 50 else kessel
    leistung = _rampe(bild, 8, 18, 0, 72)
    leistung = _rampe(bild, 48, 59, leistung, 26) if bild >= 48 else leistung
    return {
        "werte": {
            "sensor.kesseltemperatur_ist": kessel,
            "sensor.kesselleistung": leistung,
            "sensor.puffer_oben": _rampe(bild, 20, 38, 34, 70),
            "sensor.puffer_unten": _rampe(bild, 26, 48, 30, 49),
            "sensor.vorlauftemperatur_ist": _rampe(bild, 32, 46, 22, 48),
            "sensor.raumtemperatur_ist": _rampe(bild, 34, 59, 19.8, 21.4),
            "sensor.ww_temperatur": _rampe(bild, 44, 57, 39, 55),
            "sensor.ww_zirkulation_ist": _rampe(bild, 46, 59, 26, 38),
        },
        "pumpen": {
            "binary_sensor.kesselpumpe": bild >= 10,
            # Geht am Ende aus, während Heizkreis und Warmwasser weiterlaufen –
            # erst dadurch wechselt die Marke von „lädt" auf „entlädt".
            "binary_sensor.pufferladepumpe": 20 <= bild < 52,
            "binary_sensor.heizkreispumpe": bild >= 32,
            "binary_sensor.ww_ladepumpe": bild >= 44,
            "binary_sensor.ww_zirkulationspumpe": bild >= 48,
        },
    }


# ---------------------------------------------------------------------------
# Die Ebenen über dem Bild – dieselbe Aufteilung wie `frontend/teile/schaubild.js`
# ---------------------------------------------------------------------------
def _stil() -> str:
    """Das Stylesheet der Oberfläche aus `stil.js` herausholen."""
    quelle = STIL_DATEI.read_text(encoding="utf-8")
    treffer = re.search(r"export const STIL = `(.*)`;", quelle, re.S)
    if not treffer:
        raise SystemExit("STIL in stil.js nicht gefunden.")
    return treffer.group(1)


# Die Temperaturfarben des dunklen Satzes. Sie stehen als Vorgabe hier, weil
# `build_farbsaetze_animation.py` dieselben Ebenen mit anderen Werten zeichnet.
TEMPERATURFARBEN = {"warm": "#b3341f", "kalt": "#25508f"}
LEITUNGSFARBEN = {"vorlauf": "#e2543a", "ruecklauf": "#3a7fe2"}


def _grad(wert: float, kalt: float, heiss: float) -> float:
    spanne = heiss - kalt
    return max(0.0, min(1.0, (wert - kalt) / spanne)) if spanne > 0 else 0.0


def _farbe(anteil: float, warm: str, kalt: str) -> str:
    return f"color-mix(in oklab, {warm} {round(anteil * 100)}%, {kalt})"


def _text(wert: float) -> str:
    return f"{wert:.1f} °C".replace(".", ",")


def _fluss(karte_daten: dict, lage: dict) -> str:
    """Die beiden waagrechten Bänder auf Vor- und Rücklauf."""
    laeuft = "laeuft" if any(lage["pumpen"].values()) else ""
    teile = []
    leitungen = karte_daten["leitungen"]
    for richtung in ("vorlauf", "ruecklauf"):
        teile.append(
            f'<div class="fluss {richtung} {laeuft}" style="left:{leitungen["left"]};'
            f'width:{leitungen["width"]};top:{leitungen[f"{richtung}_top"]}"></div>'
        )
    return "".join(teile)


def _senkrecht(karte_daten: dict, lage: dict) -> str:
    """Die Stichleitungen: Sie strömen nur, wo die Pumpe des Teils fördert."""
    teile = []
    for eintrag in karte_daten["pumpen"]:
        laeuft = "laeuft" if lage["pumpen"].get(eintrag["entity"]) else ""
        for richtung in ("vorlauf", "ruecklauf"):
            if not (hoehe := eintrag.get(f"{richtung}_hoehe")):
                continue
            teile.append(
                f'<div class="fluss senkrecht {richtung} {laeuft}" '
                f'style="left:{eintrag["left"]};top:{eintrag[f"{richtung}_top"]};'
                f'height:{hoehe}"></div>'
            )
    return "".join(teile)


def _pumpen(karte_daten: dict, lage: dict) -> str:
    teile = []
    for eintrag in karte_daten["pumpen"]:
        laeuft = "laeuft" if lage["pumpen"].get(eintrag["entity"]) else ""
        teile.append(
            f'<div class="pumpe {laeuft}" style="left:{eintrag["left"]};top:{eintrag["top"]}">'
            f"{_laufrad()}</div>"
        )
    return "".join(teile)


def _glut(karte_daten: dict, lage: dict) -> str:
    """Das Glutbett: Helligkeit nach Kesselleistung, wie in der Oberfläche."""
    teile = []
    for eintrag in karte_daten["brenner"]:
        leistung = lage["werte"].get(eintrag["entity"]) or 0
        anteil = max(0.0, min(100.0, leistung)) / 100
        brennt = anteil > 0
        deckkraft = 0.35 + anteil * 0.65 if brennt else 0
        teile.append(
            f'<div class="glut {"brennt" if brennt else ""}" '
            f'style="left:{eintrag["left"]};top:{eintrag["top"]};width:{eintrag["breite"]};'
            f'opacity:{deckkraft:.2f}"></div>'
        )
    return "".join(teile)


def _schichtung(karte_daten: dict, lage: dict, temperatur: dict | None = None) -> str:
    """Speicherfüllung: oben und unten getrennt, Grenze wandert mit."""
    temperatur = temperatur or TEMPERATURFARBEN
    teile = []
    for eintrag in karte_daten["schichtung"]:
        oben = lage["werte"].get(eintrag["oben"])
        unten = lage["werte"].get(eintrag["unten"]) if eintrag.get("unten") else None
        kalt, heiss = float(eintrag["kalt"]), float(eintrag["heiss"])

        def farbe(grad: float, kalt: float = kalt, heiss: float = heiss) -> str:
            return _farbe(_grad(grad, kalt, heiss), temperatur["warm"], temperatur["kalt"])

        if eintrag.get("unten"):
            grund = (
                f"linear-gradient(to bottom, {farbe(oben)} 0%, {farbe(oben)} 29%, "
                f"{farbe((oben + unten) / 2)} 50%, {farbe(unten)} 71%, {farbe(unten)} 100%)"
            )
        else:
            grund = farbe(oben)
        teile.append(
            f'<div class="schichtung da" style="left:{eintrag["left"]};top:{eintrag["top"]};'
            f"width:{eintrag['breite']};height:{eintrag['hoehe']};"
            f'border-radius:{eintrag["ecke"]};background:{grund}"></div>'
        )
    return "".join(teile)


def _heizkoerper(karte_daten: dict, lage: dict, temperatur: dict | None = None) -> str:
    temperatur = temperatur or TEMPERATURFARBEN
    teile = []
    for eintrag in karte_daten["heizkoerper"]:
        grad = lage["werte"].get(eintrag["entity"])
        anteil = _grad(grad, float(eintrag["kalt"]), float(eintrag["heiss"]))
        warm = _farbe(anteil, LEITUNGSFARBEN["vorlauf"], LEITUNGSFARBEN["ruecklauf"])
        kuehl = _farbe(anteil, temperatur["warm"], temperatur["kalt"])
        glanz = (
            "linear-gradient(to right, transparent 0 18%, "
            "rgba(255, 255, 255, 0.18) 18% 46%, transparent 46%)"
        )
        fuellung = f"{glanz}, linear-gradient(to bottom, {warm}, {kuehl})"
        raster = float(eintrag["raster"].rstrip("%"))
        glieder = "".join(
            f'<div class="glied" style="left:{raster * i:.4f}%;width:{eintrag["glied"]};'
            f'background:{fuellung}"></div>'
            for i in range(eintrag.get("anzahl") or 0)
        )
        heiss = "heiss" if anteil > 0.66 else ""
        teile.append(
            f'<div class="heizkoerper da {heiss}" style="left:{eintrag["left"]};'
            f'top:{eintrag["top"]};width:{eintrag["breite"]};height:{eintrag["hoehe"]}">'
            f"{glieder}</div>"
        )
    return "".join(teile)


def _speicher(karte_daten: dict, lage: dict) -> str:
    """„lädt" / „entlädt" – dieselbe Rechnung wie in der Oberfläche."""
    teile = []
    for eintrag in karte_daten["speicher"]:
        pumpe = bool(lage["pumpen"].get(eintrag.get("laden")))
        kessel = lage["werte"].get(eintrag.get("kessel"))
        oben = lage["werte"].get(eintrag.get("oben"))
        waermer = (
            True
            if kessel is None or oben is None
            else kessel > oben + float(eintrag.get("hysterese") or 0)
        )
        laedt = pumpe and waermer
        zieht = any(lage["pumpen"].get(e) for e in eintrag.get("entnahme") or [])
        klasse = "laedt" if laedt else ("entlaedt" if zieht else "")
        text = "lädt" if laedt else ("entlädt" if zieht else "")
        teile.append(
            f'<div class="speicher {klasse}" style="left:{eintrag["left"]};'
            f'top:{eintrag["top"]}">{text}</div>'
        )
    return "".join(teile)


def _werte(karte_daten: dict, lage: dict) -> str:
    teile = []
    for element in karte_daten["elements"]:
        wert = lage["werte"].get(element["entity"])
        if wert is None:
            continue
        text = f"{round(wert)} %" if element["entity"].endswith("leistung") else _text(wert)
        stil = element["style"]
        teile.append(
            f'<div class="marke-wert" style="left:{stil["left"]};top:{stil["top"]}">{text}</div>'
        )
    return "".join(teile)


def aufnahme(karte_daten: dict, bild_nr: int, sekunde: float, farbsatz: str) -> str:
    """Eine einzelne Aufnahme als HTML-Block."""
    lage = zustand(bild_nr)
    quelle = karte_daten["image"] if farbsatz == "hell" else karte_daten["dark_mode_image"]
    # Die Bewegung wird angehalten und um `sekunde` vorgestellt – so entsteht
    # aus laufenden CSS-Animationen eine Bildfolge.
    halt = (
        f"<style>.b{bild_nr} .schaubild *{{animation-play-state:paused !important;"
        f"animation-delay:-{sekunde:.2f}s !important}}</style>"
    )
    return (
        f'{halt}<div class="rahmen b{bild_nr}"><div class="schaubild">'
        f'<img src="{quelle}" alt="">'
        f"{_schichtung(karte_daten, lage)}"
        f"{_fluss(karte_daten, lage)}"
        f"{_glut(karte_daten, lage)}"
        f"{_heizkoerper(karte_daten, lage)}"
        f"{_speicher(karte_daten, lage)}"
        f"{_werte(karte_daten, lage)}"
        f"{_senkrecht(karte_daten, lage)}"
        f"{_pumpen(karte_daten, lage)}"
        f"</div></div>"
    )


def seite(karte_daten: dict, nummern: list[int], farbsatz: str) -> str:
    """Mehrere Aufnahmen untereinander – eine Browseraufnahme reicht dann."""
    grund = UNTERGRUND[farbsatz]
    bloecke = "".join(aufnahme(karte_daten, n, n * BILD_DAUER_MS / 1000, farbsatz) for n in nummern)
    return (
        "<!doctype html><meta charset='utf-8'><style>"
        f"html,body{{margin:0;padding:0;background:{grund}}}"
        f".rahmen{{width:{BREITE}px;height:{HOEHE}px;background:{grund};"
        "overflow:hidden;position:relative}"
        f"{_stil()}</style>{bloecke}"
    )


# ---------------------------------------------------------------------------
# Aufnahme und Zusammenbau
# ---------------------------------------------------------------------------
BROWSER = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/usr/bin/chromium",
    "/usr/bin/google-chrome",
]


def _browser() -> str:
    for pfad in BROWSER:
        if Path(pfad).exists():
            return pfad
    if gefunden := shutil.which("chromium") or shutil.which("google-chrome"):
        return gefunden
    raise SystemExit("Kein kopfloser Browser gefunden (Edge, Chrome oder Chromium).")


FARBEN = 128


def _farbtafel(bilder: list) -> object:
    """Eine Farbtafel, die zu allen Bildern passt.

    Gebildet aus einer Auswahl über den ganzen Ablauf – die Anlage geht von
    kalt nach warm, eine Tafel aus dem ersten Bild allein kennte kein Rot.
    """
    from PIL import Image

    auswahl = bilder[:: max(1, len(bilder) // 8)]
    streifen = Image.new("RGB", (bilder[0].width, bilder[0].height * len(auswahl)))
    for platz, bild in enumerate(auswahl):
        streifen.paste(bild, (0, platz * bilder[0].height))
    return streifen.quantize(colors=FARBEN, method=Image.Quantize.MEDIANCUT)


def _aufnehmen(daten: dict, browser: str, farbsatz: str, arbeit: Path) -> list:
    """Alle Aufnahmen eines Farbsatzes, Seite für Seite."""
    from PIL import Image

    bilder: list[Image.Image] = []
    for anfang in range(0, BILDER, JE_SEITE):
        nummern = list(range(anfang, min(anfang + JE_SEITE, BILDER)))
        html = arbeit / f"seite_{farbsatz}_{anfang}.html"
        html.write_text(seite(daten, nummern, farbsatz), encoding="utf-8")
        aufnahme_datei = arbeit / f"seite_{farbsatz}_{anfang}.png"
        subprocess.run(
            [
                browser,
                "--headless",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--window-size={BREITE},{HOEHE * len(nummern)}",
                f"--screenshot={aufnahme_datei}",
                html.as_uri(),
            ],
            check=True,
            capture_output=True,
        )
        seite_bild = Image.open(aufnahme_datei).convert("RGB")
        for platz in range(len(nummern)):
            teil = seite_bild.crop((0, platz * HOEHE, BREITE, (platz + 1) * HOEHE))
            hoehe = round(HOEHE * GIF_BREITE / BREITE)
            bilder.append(teil.resize((GIF_BREITE, hoehe), Image.LANCZOS))
        print(f"aufgenommen ({farbsatz}): Bild {nummern[0]}–{nummern[-1]}")
    return bilder


def main() -> None:
    daten = karte()
    browser = _browser()
    with tempfile.TemporaryDirectory() as ordner:
        for farbsatz, ziel in ZIELE.items():
            bilder = _aufnehmen(daten, browser, farbsatz, Path(ordner))
            _schreiben(bilder, ziel)


def _schreiben(bilder: list, ziel: Path) -> None:
    """Die Bildfolge als GIF ablegen."""
    from PIL import Image

    # **Eine gemeinsame Farbtafel für alle Bilder.** Sucht sich jedes Bild
    # seine eigene, ändern sich die Farbnummern von Bild zu Bild, und die
    # Zwischenbildverdichtung des GIF-Formats greift nicht mehr – die Datei
    # wird ohne jeden sichtbaren Gewinn doppelt so groß.
    tafel = _farbtafel(bilder)
    gemeinsam = [b.quantize(palette=tafel, dither=Image.Dither.NONE) for b in bilder]
    gemeinsam[0].save(
        ziel,
        save_all=True,
        append_images=gemeinsam[1:],
        duration=BILD_DAUER_MS,
        loop=0,
        optimize=True,
    )
    groesse = ziel.stat().st_size / 1024
    print(f"geschrieben: {ziel.relative_to(WURZEL)} ({groesse:.0f} kB, {len(bilder)} Bilder)")


if __name__ == "__main__":
    main()
    # Der Ablauf ist Teil des Ergebnisses: Wer ihn ändert, sieht hier, was
    # das GIF zeigt, ohne es öffnen zu müssen.
    print(json.dumps({"bilder": BILDER, "dauer_ms": BILD_DAUER_MS}, ensure_ascii=False))
