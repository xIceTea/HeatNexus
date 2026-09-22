"""Die Bauteilzeichnungen aus `anlagenteile/`: laden, einfärben, vermessen.

Jede Datei ist ein SVG-Bruchstück mit Farbplatzhaltern; Lampe und Wärmefläche
sind darin markiert und werden hier ausgelesen.
"""

from __future__ import annotations

from pathlib import Path
import re

from .farben import FARBEN

# Ordner mit den Bauteilzeichnungen.
TEILE_ORDNER = Path(__file__).parent.parent / "anlagenteile"


# ---------------------------------------------------------------------------
# Bauteildateien
# ---------------------------------------------------------------------------
# Kennungen, die eine Bauteildatei selbst vergibt.
_ID = re.compile(r'id="([A-Za-z][\w.:-]*)"')


def _alle_bauteile() -> dict[str, str]:
    """Alle Bauteilzeichnungen einlesen.

    Beim Import, nicht beim ersten Schaubild: Das Schaubild entsteht in der
    Ereignisschleife, und ein Dateizugriff dort blockiert sie. Die Dateien sind
    klein genug, um dauerhaft im Speicher zu bleiben.
    """
    teile: dict[str, str] = {}
    try:
        dateien = sorted(TEILE_ORDNER.glob("*.svg"))
    except OSError:
        return teile
    for pfad in dateien:
        try:
            inhalt = pfad.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if inhalt:
            teile[pfad.name] = inhalt
    return teile


BAUTEILE: dict[str, str] = _alle_bauteile()


def bauteilnamen() -> list[str]:
    """Alle Bauteilzeichnungen, die zur Wahl stehen."""
    return sorted(name.removesuffix(".svg") for name in BAUTEILE)


def bauteil(dateiname: str) -> str | None:
    """Eine Bauteilzeichnung – oder ``None``, wenn es sie nicht gibt.

    Der Inhalt ist ein SVG-Bruchstück ohne ``<svg>``-Wurzel: Es wird in das
    Gesamtbild eingesetzt, nicht als eigenes Bild ausgeliefert.
    """
    return BAUTEILE.get(dateiname)


def einfaerben(fragment: str) -> str:
    """Farbplatzhalter einsetzen."""
    for name, wert in FARBEN.items():
        fragment = fragment.replace("{{" + name + "}}", wert)
    return fragment


def _ids_eindeutig(fragment: str, praefix: str) -> str:
    """Kennungen eines Bruchstücks eindeutig machen.

    Zwei Puffer im selben Bild brächten sonst zweimal ``id="schichtung"`` mit;
    ein Verlauf gewönne, der andere bliebe leer.

    Ersetzt werden nur die drei Schreibweisen, in denen unsere Dateien auf eine
    Kennung verweisen. Alle drei enthalten das schließende Zeichen und können
    deshalb nicht in einen längeren Namen hineinrutschen: ``url(#kessel)``
    trifft nicht ``kesselrand``.
    """
    for alt in dict.fromkeys(_ID.findall(fragment)):
        neu = f"{praefix}{alt}"
        fragment = (
            fragment.replace(f'id="{alt}"', f'id="{neu}"')
            .replace(f"url(#{alt})", f"url(#{neu})")
            .replace(f'href="#{alt}"', f'href="#{neu}"')
        )
    return fragment


# Platzhalter in den Bauteildateien, die **keine** Farbe sind, sondern vom
# Zustand der Anlage abhängen. Sie werden je Bauteil eingesetzt, nicht aus der
# festen Tafel – stehen aber hier, damit der Test sie von einem Tippfehler
# unterscheiden kann.
#
# `koerper`  Füllung des Speicherkörpers: der neutrale Verlauf, oder `none`,
#            wenn die Oberfläche die gemessene Schichtung darunterlegt.
ZUSATZ_PLATZHALTER = frozenset({"koerper"})


# Der Punkt in der Glutfarbe, den jede Kesselzeichnung trägt: im Bild eine rote
# Lampe. Wo genau er sitzt, sagt die Zeichnung selbst – so trägt es auch für
# eine eigene Zeichnung, die hier niemand kennt.
_LAMPENPUNKT = re.compile(
    r'<circle[^>]*\s+cx="(?P<x>[\d.]+)"[^>]*\s+cy="(?P<y>[\d.]+)"[^>]*\s+r="(?P<r>[\d.]+)"'
    r'[^>]*fill="\{\{glut\}\}"'
)


# Trägt eine Zeichnung mehrere Punkte in der Glutfarbe, benennt `data-lampe`
# den einen, der die Betriebslampe ist.
_LAMPENMARKE = re.compile(r"<circle[^>]*\sdata-lampe[^>]*>")


def _kreismasse(tag: str) -> tuple[float, float, float] | None:
    """Mittelpunkt und Halbmesser eines gezeichneten Kreises."""
    masse = []
    for name in ("cx", "cy", "r"):
        wert = re.search(rf'\s{name}="([\d.]+)"', tag)
        if wert is None:
            return None
        masse.append(float(wert.group(1)))
    return masse[0], masse[1], masse[2]


def lampenpunkt(
    art: str, kesselart: str | None = None, zeichnung: str | None = None
) -> tuple[float, float, float] | None:
    """Stelle und Größe der Betriebslampe in der Zeichnung eines Anlagenteils."""
    for dateiname in _bauteil_dateien(art, kesselart, zeichnung):
        fragment = bauteil(dateiname)
        if fragment is None:
            continue
        if (marke := _LAMPENMARKE.search(fragment)) and (stelle := _kreismasse(marke.group(0))):
            return stelle
        if treffer := _LAMPENPUNKT.search(fragment):
            return (
                float(treffer.group("x")),
                float(treffer.group("y")),
                float(treffer.group("r")),
            )
        return None
    return None


# Trägt eine Zeichnung eine Fläche, die sich im Betrieb erwärmt, benennt
# `data-waerme` ihr Rechteck; `data-dreh` neigt es wie das Bauteil darunter.
_WAERMEMARKE = re.compile(r"<rect[^>]*\sdata-waerme[^>]*?/>", re.S)


def waermeflaeche(art: str, zeichnung: str | None = None) -> dict[str, float] | None:
    """Fläche einer Bauteilzeichnung, die sich im Betrieb erwärmt."""
    for dateiname in _bauteil_dateien(art, None, zeichnung):
        fragment = bauteil(dateiname)
        if fragment is None or (marke := _WAERMEMARKE.search(fragment)) is None:
            continue
        masse: dict[str, float] = {}
        for name, schluessel in (
            ("x", "x"),
            ("y", "y"),
            ("width", "breite"),
            ("height", "hoehe"),
            ("rx", "ecke"),
            ("data-dreh", "dreh"),
        ):
            wert = re.search(rf'\s{name}="(-?[\d.]+)"', marke.group(0))
            if wert is None and schluessel in ("x", "y", "breite", "hoehe"):
                break
            masse[schluessel] = float(wert.group(1)) if wert else 0.0
        else:
            return masse
    return None


def kessellampe(
    kesselart: str | None, zeichnung: str | None = None
) -> tuple[float, float, float] | None:
    """Stelle und Größe der Betriebslampe in der gewählten Kesselzeichnung."""
    return lampenpunkt("kessel", kesselart, zeichnung)


def _bauteil_dateien(
    art: str, kesselart: str | None, zeichnung: str | None = None
) -> tuple[str, ...]:
    """Dateinamen für ein Anlagenteil, in der Reihenfolge der Bevorzugung."""
    if zeichnung:
        return (f"{zeichnung}.svg", f"{art}.svg")
    if art == "kessel" and kesselart:
        return (f"kessel-{kesselart}.svg", "kessel.svg")
    return (f"{art}.svg",)


def aus_datei(
    art: str,
    kesselart: str | None,
    praefix: str,
    zusatz: dict[str, str] | None = None,
    zeichnung: str | None = None,
) -> str | None:
    """Bauteilzeichnung, fertig eingefärbt und mit eindeutigen Kennungen.

    ``zusatz`` füllt Platzhalter, die nicht aus der festen Farbtafel kommen –
    beim Puffer die Füllung des Speicherkörpers, die von den vorhandenen
    Fühlern abhängt. Sie wird vor ``_ids_eindeutig`` eingesetzt, damit ein
    darin genannter Verlauf mit umbenannt wird.
    """
    for dateiname in _bauteil_dateien(art, kesselart, zeichnung):
        if (fragment := bauteil(dateiname)) is not None:
            for name, wert in (zusatz or {}).items():
                fragment = fragment.replace("{{" + name + "}}", wert)
            return _ids_eindeutig(einfaerben(fragment), praefix)
    return None
