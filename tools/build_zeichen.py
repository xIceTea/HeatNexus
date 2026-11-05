"""Das HeatNexus-Zeichen an allen Stellen aus einer Vorlage erzeugen.

Vorlage ist `assets/zeichen.svg`. Daraus entstehen `frontend/zeichen.js`, die Mitte des
Rings auf der Projektseite, die Bilder in `brand/` und `assets/` sowie die Banner.

    python tools/build_zeichen.py
"""

from __future__ import annotations

import base64
from pathlib import Path
import re
import subprocess
import sys
import tempfile

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

VORLAGE = WURZEL / "assets" / "zeichen.svg"
ZEICHEN_JS = WURZEL / "custom_components" / "heatnexus" / "frontend" / "zeichen.js"
PROJEKTSEITE = WURZEL / "docs" / "index.md"
MARKE = WURZEL / "custom_components" / "heatnexus" / "brand"
ASSETS = WURZEL / "assets"
SCHRIFT = WURZEL / "docs" / "assets" / "fonts" / "Manrope-latin.woff2"

GRUND = "#141c26"
KOPFZEILE = "Windhager · Home Assistant · Lokal"

JS_KOPF = """/** Das HeatNexus-Zeichen, erzeugt aus `assets/zeichen.svg` von `tools/build_zeichen.py`. */

let ZAEHLER = 0;

/** Ein neues Zeichen; die Verläufe tragen eigene Kennungen, damit zwei Zeichen im selben Schattenbaum nicht kollidieren. */
export function zeichenKnoten() {
  ZAEHLER += 1;
  const oben = `hn-ring-oben-${ZAEHLER}`;
  const unten = `hn-ring-unten-${ZAEHLER}`;
  const glut = `hn-glut-${ZAEHLER}`;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "zeichen");
  svg.setAttribute("viewBox", "0 0 32 32");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  svg.innerHTML = `
"""
JS_FUSS = """`;
  return svg;
}
"""


def innen() -> str:
    """Der Inhalt der Vorlage ohne das äußere `svg`-Element."""
    text = VORLAGE.read_text(encoding="utf-8")
    return re.search(r"<svg[^>]*>\n(.*)</svg>", text, re.S).group(1)


def zeichen_js() -> str:
    """`frontend/zeichen.js`; die Kennungen der Verläufe sind je Zeichen eigene."""
    teil = innen()
    for kennung, name in (
        ("zeichen-oben", "oben"),
        ("zeichen-unten", "unten"),
        ("zeichen-glut", "glut"),
    ):
        teil = teil.replace(kennung, "${" + name + "}")
    eingerueckt = "".join(f"    {zeile}\n" for zeile in teil.splitlines())
    return JS_KOPF + eingerueckt.rstrip("\n") + JS_FUSS


def haus_der_projektseite() -> str:
    """Haus und Heizkörper für die Mitte des Rings, ohne Knoten und Stützen."""
    teil = innen()
    verlauf = re.search(r'<linearGradient id="zeichen-glut".*?</linearGradient>', teil, re.S).group(
        0
    )
    haus = re.search(r'<g id="zeichen-haus".*?</g>', teil, re.S).group(0)
    heizkoerper = re.search(r'<g id="zeichen-heizkoerper".*?</g>', teil, re.S).group(0)
    inhalt = (
        f"<defs>{verlauf}</defs>\n"
        '    <g transform="translate(260 270) scale(10) translate(-16 -16.6)" fill="none" '
        'stroke-linecap="round" stroke-linejoin="round">\n'
        f"      {haus.replace('stroke="currentColor"', 'class="haus"')}\n"
        f"      {heizkoerper}\n"
        "    </g>"
    )
    return inhalt.replace("zeichen-", "ring-")


def _svg(breite: float, grund: str, farbe: str = "#eef2f6") -> str:
    style = f"<style>.knoten{{fill:{grund}}}</style>"
    return (
        f'<svg viewBox="0 0 32 32" width="{breite}" height="{breite}" style="color:{farbe}">'
        f"{style}{innen()}</svg>"
    )


def _kachel(groesse: int) -> str:
    """Das Zeichen auf der abgerundeten Kachel von `icon.png`."""
    return (
        f'<div class="kachel" style="width:{groesse}px;height:{groesse}px;'
        f'border-radius:{groesse * 0.235}px">{_svg(groesse * 0.76, "#28323f")}</div>'
    )


def _wort(groesse: float) -> str:
    return f'<span class="wort" style="font-size:{groesse}px">HeatNexus</span>'


def _seite(inhalt: str, breite: int, hoehe: int, grund: str = "transparent") -> str:
    schrift = base64.b64encode(SCHRIFT.read_bytes()).decode("ascii")
    return f"""<!doctype html><meta charset="utf-8"><style>
@font-face {{ font-family: Manrope; src: url(data:font/woff2;base64,{schrift}) format("woff2"); font-weight: 200 800; }}
html, body {{ margin: 0; padding: 0; background: transparent; }}
.flaeche {{ position: relative; overflow: hidden; width: {breite}px; height: {hoehe}px; background: {grund};
  font-family: Manrope, sans-serif; color: #f2f5f8; display: flex; align-items: center; justify-content: center; }}
.kachel {{ display: grid; place-items: center; flex: none; box-sizing: border-box;
  background: linear-gradient(165deg, #2f3746, #1e2733); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.07); }}
.wort {{ font-weight: 800; letter-spacing: -0.03em; line-height: 1; color: #f2f5f8; }}
.zeile {{ font-weight: 500; color: #9fb0c0; letter-spacing: 0.01em; }}
.leuchten {{ position: absolute; inset: 0; background:
  radial-gradient(38% 90% at 12% 50%, rgba(247, 120, 50, 0.22), transparent 70%),
  radial-gradient(40% 95% at 92% 45%, rgba(59, 180, 242, 0.16), transparent 72%); }}
.ring {{ position: absolute; border-radius: 50%; border: 1px solid rgba(255, 255, 255, 0.05); }}
.stapel {{ position: relative; display: flex; flex-direction: column; }}
</style><div class="flaeche">{inhalt}</div>"""


def banner_quer(breite: int, hoehe: int) -> str:
    """Breites Banner für das README: Zeichen links, Name und Zeile rechts davon."""
    einheit = hoehe / 500
    ringe = "".join(
        f'<div class="ring" style="width:{m * einheit}px;height:{m * einheit}px;'
        f'right:{(-m / 2 + 170) * einheit}px;top:{(250 - m / 2) * einheit}px"></div>'
        for m in (380, 620, 860, 1100)
    )
    return (
        f'<div class="leuchten"></div>{ringe}'
        f'<div style="position:relative;display:flex;align-items:center;gap:{64 * einheit}px;'
        f'width:100%;padding-left:{130 * einheit}px">{_svg(330 * einheit, GRUND)}'
        f'<div class="stapel" style="gap:{22 * einheit}px">{_wort(138 * einheit)}'
        f'<span class="zeile" style="font-size:{36 * einheit}px">{KOPFZEILE}</span></div></div>'
    )


def banner_hoch(breite: int, hoehe: int) -> str:
    """Vorschaubild der Projektseite: alles mittig untereinander."""
    return (
        '<div class="leuchten"></div>'
        '<div class="stapel" style="align-items:center;gap:30px">'
        f'{_svg(360, GRUND)}{_wort(112)}<span class="zeile" style="font-size:30px">{KOPFZEILE}</span></div>'
    )


def logo(breite: int, hoehe: int) -> str:
    """Kachel und Name nebeneinander."""
    kachel = round(hoehe * 0.8)
    return (
        f'<div style="display:flex;align-items:center;gap:{hoehe * 0.16}px">{_kachel(kachel)}'
        f"{_wort(hoehe * 0.56)}</div>"
    )


def _aufnehmen(browser: str, html: str, breite: int, hoehe: int, ziel: Path) -> None:
    with tempfile.TemporaryDirectory() as ordner:
        seite = Path(ordner) / "seite.html"
        seite.write_text(html, encoding="utf-8")
        subprocess.run(
            [
                browser,
                "--headless",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                "--default-background-color=00000000",
                f"--user-data-dir={Path(ordner) / 'profil'}",
                f"--window-size={breite},{hoehe}",
                f"--screenshot={ziel}",
                seite.as_uri(),
            ],
            check=True,
            capture_output=True,
        )
    print(f"geschrieben: {ziel.relative_to(WURZEL)}")


def bilder() -> None:
    from build_schaubild_animation import _browser

    browser = _browser()
    for groesse, name in ((256, "icon.png"), (512, "icon@2x.png")):
        html = _seite(_kachel(groesse), groesse, groesse)
        _aufnehmen(browser, html, groesse, groesse, MARKE / name)
        _aufnehmen(browser, html, groesse, groesse, ASSETS / name)
    for breite, hoehe, ziel in (
        (512, 128, MARKE / "logo.png"),
        (1024, 256, MARKE / "logo@2x.png"),
        (648, 160, ASSETS / "logo.png"),
    ):
        _aufnehmen(
            browser, _seite(logo(breite, hoehe), breite, hoehe, "#16202b"), breite, hoehe, ziel
        )
    verlauf = "linear-gradient(120deg, #1a2430, #121a24 55%, #16202b)"
    _aufnehmen(
        browser,
        _seite(banner_quer(2000, 500), 2000, 500, verlauf),
        2000,
        500,
        ASSETS / "banner_small.png",
    )
    _aufnehmen(
        browser,
        _seite(banner_hoch(1600, 800), 1600, 800, verlauf),
        1600,
        800,
        ASSETS / "banner.png",
    )


def main() -> None:
    ZEICHEN_JS.write_text(zeichen_js(), encoding="utf-8", newline="\n")
    roh = PROJEKTSEITE.read_bytes().decode("utf-8")
    neu, anzahl = re.subn(
        r"(<!-- zeichen:anfang -->).*?([ \t]*<!-- zeichen:ende -->)",
        lambda m: f"{m.group(1)}\n    {haus_der_projektseite()}\n{m.group(2)}",
        roh.replace("\r\n", "\n"),
        flags=re.S,
    )
    if anzahl != 1:
        raise SystemExit("Die Marken für das Zeichen in docs/index.md fehlen.")
    if "\r\n" in roh:
        neu = neu.replace("\n", "\r\n")
    PROJEKTSEITE.write_bytes(neu.encode("utf-8"))
    bilder()


if __name__ == "__main__":
    main()
