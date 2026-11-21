"""Zeitprogramme: Kontrast von Beschriftung und Warnung in jedem Farbsatz.

Die Farben entstehen erst im Browser aus Variablen, `color-mix` und relativen Farben.
Dieser Test rechnet sie aus dem Stylesheet nach und misst den Kontrast nach WCAG.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")

FRONTEND = Path(__file__).resolve().parents[1] / "custom_components" / "heatnexus" / "frontend"
MINDESTENS = 4.5

# Die Vorgaben von Home Assistant, wenn kein eigener Farbsatz gewählt ist.
HOME_ASSISTANT = {
    "home_assistant_hell": {
        "--hn-grund": "#fafafa",
        "--hn-karte": "#ffffff",
        "--hn-text": "#212121",
    },
    "home_assistant_dunkel": {
        "--hn-grund": "#111111",
        "--hn-karte": "#1c1c1c",
        "--hn-text": "#e1e1e1",
    },
}
# Wie `stil/grund.js` sie ohne eigenen Farbsatz aus der Schrift mischt.
for _satz in HOME_ASSISTANT.values():
    _satz["--hn-flaeche"] = "color-mix(in srgb, var(--hn-text) 7%, transparent)"
    _satz["--hn-gedaempft"] = "color-mix(in srgb, var(--hn-text) 72%, transparent)"
HA_AKZENT = "color-mix(in srgb, #03a9f4 60%, var(--hn-text))"
HA_WARNUNG = "#ffa600"


@pytest.fixture(scope="module")
def stand(tmp_path_factory) -> dict:
    """Farbsätze, Stylesheet und die Stücke einer Spur für jeden Wert, in Node gebaut."""
    skript = tmp_path_factory.mktemp("kontrast") / "kontrast.mjs"

    def datei(name: str) -> str:
        return (FRONTEND / name).resolve().as_uri()

    attrappe = (Path(__file__).parent / "js" / "dom-attrappe.mjs").resolve().as_uri()
    skript.write_text(
        f"""
import {{ browserAttrappe }} from "{attrappe}";
browserAttrappe();
const {{ PALETTEN }} = await import("{datei("ordnung.js")}");
const {{ ZEITPROGRAMME }} = await import("{datei("stil/zeitprogramme.js")}");
const {{ GRUND }} = await import("{datei("stil/grund.js")}");
const {{ STIL }} = await import("{datei("stil.js")}");
const {{ farbe, skala }} = await import("{datei("zeitprogramm.js")}");
const {{ tagesspur }} = await import("{datei("zeitprogrammseite.js")}");

const stuecke = [];
const lesen = (art, wert, rolle, tag, stelle) => {{
  const bloecke = [{{ tage: ["Mo"], punkte: tag.map(([zeit, w]) => ({{ zeit, wert: w }})) }}];
  const teile = [{{ von: 0, bis: 600, wert: tag[0][1] }}, {{ von: 600, bis: 1440, wert: tag[1][1] }}];
  const spur = tagesspur(teile, skala(bloecke, art), {{ beschriften: true }}).querySelector(".zp-spur");
  const stueck = spur.children[stelle];
  stuecke.push({{
    art, wert, rolle,
    klassen: stueck.className,
    text: stueck.textContent,
    stil: JSON.parse(JSON.stringify(stueck.style)),
  }});
}};
for (let wert = 14; wert <= 24; wert += 0.25) {{
  lesen("raum", wert, "wert", [[0, 13], [600, wert]], 1);
  lesen("raum", wert, "ruhe", [[0, wert], [600, 25]], 0);
}}
for (let wert = 40; wert <= 65; wert += 0.5) {{
  lesen("wasser", wert, "wert", [[0, 35], [600, wert]], 1);
  lesen("wasser", wert, "ruhe", [[0, wert], [600, 70]], 0);
}}
lesen("schalt", 1, "ein", [[0, 0], [600, 1]], 1);
const tarife = [0, 1, 2, 3, 4].map((wert) => farbe(wert, skala([], "tarif")));
for (const wert of [0, 1, 2, 3, 4]) {{
  lesen("tarif", wert, "wert", [[0, wert === 0 ? 1 : 0], [600, wert]], 1);
  if (wert < 4) lesen("tarif", wert, "ruhe", [[0, wert], [600, 4]], 0);
}}
console.log(JSON.stringify({{ paletten: PALETTEN, css: ZEITPROGRAMME, grund: GRUND, stil: STIL, stuecke, tarife }}));
""",
        encoding="utf-8",
    )
    ausgabe = subprocess.run(
        ["node", str(skript)], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return json.loads(ausgabe.stdout)


# ---------------------------------------------------------------------------
# Farben rechnen: sRGB, OKLab, color-mix und relative Farben
# ---------------------------------------------------------------------------
def _linear(kanal: float) -> float:
    return kanal / 12.92 if kanal <= 0.04045 else ((kanal + 0.055) / 1.055) ** 2.4


def _gamma(kanal: float) -> float:
    kanal = min(1.0, max(0.0, kanal))
    return 12.92 * kanal if kanal <= 0.0031308 else 1.055 * kanal ** (1 / 2.4) - 0.055


def _oklab(rgb):
    r, g, b = (_linear(k) for k in rgb)
    lms = (
        0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
        0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
        0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b,
    )
    lang, mittel, kurz = (math.copysign(abs(x) ** (1 / 3), x) for x in lms)
    return (
        0.2104542553 * lang + 0.7936177850 * mittel - 0.0040720468 * kurz,
        1.9779984951 * lang - 2.4285922050 * mittel + 0.4505937099 * kurz,
        0.0259040371 * lang + 0.7827717662 * mittel - 0.8086757660 * kurz,
    )


def _aus_oklab(lab):
    hell, a, b = lab
    lang = (hell + 0.3963377774 * a + 0.2158037573 * b) ** 3
    mittel = (hell - 0.1055613458 * a - 0.0638541728 * b) ** 3
    kurz = (hell - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        _gamma(4.0767416621 * lang - 3.3077115913 * mittel + 0.2309699292 * kurz),
        _gamma(-1.2684380046 * lang + 2.6097574011 * mittel - 0.3413193965 * kurz),
        _gamma(-0.0041960863 * lang - 0.7034186147 * mittel + 1.7076147010 * kurz),
    )


def _teilen(text: str, trenner: str) -> list[str]:
    """An `trenner` außerhalb von Klammern teilen."""
    teile, tiefe, anfang = [], 0, 0
    for stelle, zeichen in enumerate(text):
        tiefe += {"(": 1, ")": -1}.get(zeichen, 0)
        if tiefe == 0 and (zeichen == trenner or (trenner == " " and zeichen.isspace())):
            teile.append(text[anfang:stelle])
            anfang = stelle + 1
    teile.append(text[anfang:])
    return [teil.strip() for teil in teile if teil.strip()]


def _mischen(raum: str, eine, andere, anteil: float):
    """color-mix mit vormultiplizierter Deckkraft."""
    (f1, a1), (f2, a2) = eine, andere
    alpha = a1 * anteil + a2 * (1 - anteil)
    if alpha == 0:
        return (0.0, 0.0, 0.0), 0.0
    umrechnen = _oklab if raum == "oklab" else (lambda rgb: rgb)
    zurueck = _aus_oklab if raum == "oklab" else (lambda rgb: rgb)
    k1, k2 = umrechnen(f1), umrechnen(f2)
    gemischt = [
        (x * a1 * anteil + y * a2 * (1 - anteil)) / alpha for x, y in zip(k1, k2, strict=True)
    ]
    return tuple(zurueck(gemischt)), alpha


def _relativ(rest: str, umgebung: dict):
    """`color(from <farbe> srgb-linear <ausdruck> <ausdruck> <ausdruck>)`."""
    herkunft, raum, *ausdruecke = _teilen(rest, " ")
    assert raum == "srgb-linear" and len(ausdruecke) == 3, rest
    (farbe, alpha) = _wert(herkunft, umgebung)
    namen = dict(zip("rgb", (_linear(k) for k in farbe), strict=True))
    namen["_clamp"] = lambda unten, wert, oben: min(oben, max(unten, wert))

    def rechnen(ausdruck: str) -> float:
        python = ausdruck.replace("clamp(", "_clamp(").replace("calc(", "(")
        assert re.fullmatch(r"[\d.\s+\-*/(),rgb_clamp]+", python), ausdruck
        return eval(python, {"__builtins__": {}}, namen)

    return tuple(_gamma(rechnen(a)) for a in ausdruecke), alpha


def _wert(text: str, umgebung: dict):
    """Einen CSS-Farbwert in (rgb, alpha) übersetzen."""
    text = text.strip()
    if text.startswith("#"):
        ziffern = text[1:]
        if len(ziffern) == 3:
            ziffern = "".join(z * 2 for z in ziffern)
        return tuple(int(ziffern[i : i + 2], 16) / 255 for i in (0, 2, 4)), 1.0
    benannt = {"white": ((1.0, 1.0, 1.0), 1.0), "black": ((0.0, 0.0, 0.0), 1.0)}
    if text in benannt:
        return benannt[text]
    if text == "transparent":
        return (0.0, 0.0, 0.0), 0.0
    name, rest = re.fullmatch(r"([a-z-]+)\((.*)\)", text, re.S).groups()
    if name == "var":
        variable, *ersatz = _teilen(rest, ",")
        if variable in umgebung:
            return _wert(umgebung[variable], umgebung)
        assert ersatz, f"{variable} ist nicht gesetzt"
        return _wert(ersatz[0], umgebung)
    if name in ("rgb", "rgba"):
        zahlen = [float(z) for z in _teilen(rest, ",")]
        return tuple(z / 255 for z in zahlen[:3]), zahlen[3] if len(zahlen) > 3 else 1.0
    if name == "oklch":
        hell, chroma, ton = (float(z) for z in _teilen(rest, " "))
        winkel = math.radians(ton)
        return _aus_oklab((hell, chroma * math.cos(winkel), chroma * math.sin(winkel))), 1.0
    if name == "color-mix":
        raum, *farben = _teilen(rest, ",")
        teile = []
        for eintrag in farben:
            stuecke = _teilen(eintrag, " ")
            anteil = float(stuecke[-1][:-1]) / 100 if stuecke[-1].endswith("%") else None
            teile.append((" ".join(stuecke[:-1]) if anteil is not None else eintrag, anteil))
        (eine, p1), (andere, p2) = teile
        anteil = p1 if p1 is not None else (1 - p2 if p2 is not None else 0.5)
        return _mischen(raum.split()[-1], _wert(eine, umgebung), _wert(andere, umgebung), anteil)
    if name == "color" and rest.startswith("from "):
        return _relativ(rest[5:], umgebung)
    raise AssertionError(f"unbekannte Farbe: {text}")


def _ueber(farbe, grund):
    """Eine Farbe mit Deckkraft über einen deckenden Grund legen."""
    (vorn, alpha), (hinten, _) = farbe, grund
    return tuple(a * alpha + b * (1 - alpha) for a, b in zip(vorn, hinten, strict=True)), 1.0


def _kontrast(eine, andere) -> float:
    def leuchtdichte(farbe) -> float:
        r, g, b = (_linear(k) for k in farbe[0])
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    hell, dunkel = sorted((leuchtdichte(eine), leuchtdichte(andere)), reverse=True)
    return (hell + 0.05) / (dunkel + 0.05)


# ---------------------------------------------------------------------------
# Stylesheet lesen
# ---------------------------------------------------------------------------
def _regeln(css: str) -> dict[str, dict[str, str]]:
    """Regeln der obersten Ebene; bei doppelten Angaben gilt die letzte, wie im Browser mit Unterstützung."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    regeln: dict[str, dict[str, str]] = {}
    tiefe, anfang, kopf = 0, 0, ""
    for stelle, zeichen in enumerate(css):
        if zeichen == "{":
            if tiefe == 0:
                kopf, anfang = css[anfang:stelle].strip(), stelle + 1
            tiefe += 1
        elif zeichen == "}":
            tiefe -= 1
            if tiefe == 0:
                if not kopf.startswith("@"):
                    for waehler in (w.strip() for w in kopf.split(",")):
                        ziel = regeln.setdefault(waehler, {})
                        for angabe in _teilen(css[anfang:stelle], ";"):
                            eigenschaft, _, wert = angabe.partition(":")
                            ziel[eigenschaft.strip()] = wert.strip()
                anfang = stelle + 1
    return regeln


def _saetze(stand: dict) -> dict[str, dict[str, str]]:
    saetze = {name: dict(werte) for name, werte in stand["paletten"].items()}
    for name, werte in HOME_ASSISTANT.items():
        saetze[name] = {**werte, "--hn-akzent": HA_AKZENT}
    for werte in saetze.values():
        werte.setdefault("--warning-color", HA_WARNUNG)
    return saetze


def _variablen(regel: dict[str, str]) -> dict[str, str]:
    return {name: wert for name, wert in regel.items() if name.startswith("--")}


def _stueck_farben(regeln, satz, stueck):
    """Grund und Schrift eines Stücks der Spur, so wie sie am Bildschirm ankommen."""
    rahmen = regeln.get(".zp-rahmen", {})
    eigene = [regeln.get(".zp-stueck", {})]
    if "ruhe" in stueck["klassen"].split():
        eigene.append(regeln.get(".zp-stueck.ruhe", {}))
    umgebung = {**_variablen(regeln[":host"]), **satz, **_variablen(rahmen)}
    for regel in eigene:
        umgebung.update(_variablen(regel))
    inline = stueck["stil"]
    umgebung.update({k: v for k, v in inline.items() if k.startswith("--")})
    angaben = {k: v for regel in eigene for k, v in regel.items()}
    unter = _wert(rahmen.get("background", "var(--hn-grund)"), umgebung)
    grund = _ueber(_wert(inline.get("background") or angaben["background"], umgebung), unter)
    schrift = _ueber(_wert(angaben["color"], umgebung), grund)
    deckkraft = float(angaben.get("opacity", 1))
    return _ueber((grund[0], deckkraft), unter), _ueber((schrift[0], deckkraft), unter)


def test_jede_beschriftung_im_balken_hebt_sich_ab(stand):
    regeln = _regeln(stand["css"])
    zu_schwach = []
    for name, satz in _saetze(stand).items():
        for stueck in stand["stuecke"]:
            assert stueck["text"], stueck
            grund, schrift = _stueck_farben(regeln, satz, stueck)
            wert = _kontrast(grund, schrift)
            if wert < MINDESTENS:
                zu_schwach.append(
                    f"{name} {stueck['art']} {stueck['rolle']} {stueck['wert']}: {wert:.2f}"
                )
    assert not zu_schwach, (
        f"{len(zu_schwach)} Beschriftungen unter {MINDESTENS}:1: {zu_schwach[:12]}"
    )


def test_die_warnung_hebt_sich_von_der_karte_ab(stand):
    regeln = _regeln(stand["css"])
    zu_schwach = []
    for name, satz in _saetze(stand).items():
        umgebung = {**_variablen(regeln[":host"]), **satz}
        karte = _wert("var(--hn-karte)", umgebung)
        schrift = _ueber(_wert(regeln[".zp-warnung"]["color"], umgebung), karte)
        if (wert := _kontrast(schrift, karte)) < MINDESTENS:
            zu_schwach.append(f"{name}: {wert:.2f}")
    assert not zu_schwach, zu_schwach


FLAECHE = 3.0


def _flaechen(regeln, satz) -> dict:
    """Grund, Karte und Fläche eines Farbsatzes als deckende Farben."""
    umgebung = {**_variablen(regeln[":host"]), **satz}
    karte = _wert("var(--hn-karte)", umgebung)
    flaechen = {"grund": _wert("var(--hn-grund)", umgebung), "karte": karte}
    if "--hn-flaeche" in satz:
        flaechen["flaeche"] = _ueber(_wert("var(--hn-flaeche)", umgebung), karte)
    return flaechen


def test_tarife_heben_sich_von_jeder_flaeche_ab(stand):
    regeln = _regeln(stand["css"])
    zu_schwach = []
    for name, satz in _saetze(stand).items():
        umgebung = {**_variablen(regeln[":host"]), **satz}
        for nummer, ton in enumerate(stand["tarife"], start=1):
            for wo, flaeche in _flaechen(regeln, satz).items():
                farbe = _ueber(_wert(ton, umgebung), flaeche)
                if (wert := _kontrast(farbe, flaeche)) < FLAECHE:
                    zu_schwach.append(f"{name} Tarif {nummer} auf {wo}: {wert:.2f}")
    assert not zu_schwach, zu_schwach


def test_tarife_tragen_eigene_farben(stand):
    """Keine Stufe der Temperaturfarben, und je zwei Tarife unterscheiden sich sichtbar."""
    regeln = _regeln(stand["css"])
    assert not any("--zp-t" in ton.replace("--zp-tarif", "") for ton in stand["tarife"])
    for name, satz in _saetze(stand).items():
        umgebung = {**_variablen(regeln[":host"]), **satz}
        lab = [_oklab(_wert(ton, umgebung)[0]) for ton in stand["tarife"]]
        for i, eine in enumerate(lab):
            for j, andere in enumerate(lab[i + 1 :], start=i + 1):
                abstand = math.dist(eine, andere)
                assert abstand >= 0.08, (
                    f"{name}: Tarif {i + 1} und {j + 1} liegen {abstand:.3f} auseinander"
                )


def test_gedaempfte_schrift_haelt_auf_jeder_flaeche(stand):
    regeln = _regeln(stand["css"])
    zu_schwach = []
    for name, satz in _saetze(stand).items():
        umgebung = {**_variablen(regeln[":host"]), **satz}
        for wo, flaeche in _flaechen(regeln, satz).items():
            schrift = _ueber(_wert("var(--hn-gedaempft)", umgebung), flaeche)
            if (wert := _kontrast(schrift, flaeche)) < MINDESTENS:
                zu_schwach.append(f"{name} auf {wo}: {wert:.2f}")
    assert not zu_schwach, zu_schwach


def test_fehler_und_warnung_halten_auf_hellem_und_dunklem_grund(stand):
    grund = _variablen(_regeln(stand["grund"])[":host"])
    zu_schwach = []
    for name, satz in _saetze(stand).items():
        umgebung = {**grund, **satz}
        for token in ("--hn-fehler", "--hn-warnung"):
            for wo, flaeche in _flaechen({":host": {}}, umgebung).items():
                schrift = _ueber(_wert(f"var({token})", umgebung), flaeche)
                if (wert := _kontrast(schrift, flaeche)) < MINDESTENS:
                    zu_schwach.append(f"{name} {token} auf {wo}: {wert:.2f}")
    assert not zu_schwach, zu_schwach


def test_keine_schrift_traegt_das_feste_rot_oder_gelb(stand):
    """Fehler und Warnung lesen ihre Farbe aus dem Farbsatz; die festen Töne sind nur auf dunklem Grund lesbar."""
    fest = []
    for waehler, regel in _regeln(stand["stil"]).items():
        for eigenschaft in ("color", "--hn-farbe"):
            if regel.get(eigenschaft, "").lower() in ("#ff8a80", "#ffd54f"):
                fest.append(f"{waehler} {eigenschaft}")
    assert not fest, fest


def test_der_leere_reiter_dimmt_mit_farbe(stand):
    regeln = _regeln(stand["css"])
    leer = regeln[".zp-reiter button.leer"]
    assert "opacity" not in leer
    zu_schwach = []
    for name, satz in _saetze(stand).items():
        umgebung = {**_variablen(regeln[":host"]), **satz}
        flaechen = _flaechen(regeln, satz)
        flaeche = flaechen.get("flaeche", flaechen["karte"])
        schrift = _ueber(_wert(leer["color"], umgebung), flaeche)
        if (wert := _kontrast(schrift, flaeche)) < MINDESTENS:
            zu_schwach.append(f"{name}: {wert:.2f}")
    assert not zu_schwach, zu_schwach


def test_die_rechnung_trifft_bekannte_werte():
    """Schwarz auf Weiß ergibt 21:1, das Orange von Home Assistant auf Weiß knapp 2:1."""
    weiss, schwarz = _wert("#ffffff", {}), _wert("#000000", {})
    assert round(_kontrast(weiss, schwarz), 2) == 21.0
    assert round(_kontrast(_wert(HA_WARNUNG, {}), weiss), 2) == 1.96
    mitte = _wert("color-mix(in srgb, #ffffff 50%, #000000)", {})
    assert mitte[0] == pytest.approx((0.5, 0.5, 0.5))
    assert _wert("oklch(1 0 0)", {})[0] == pytest.approx((1.0, 1.0, 1.0), abs=1e-4)
