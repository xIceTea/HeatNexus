"""Anlagenschaubild.

Zeichnet die Anlage als Grafik – Kessel, Puffer, Heizkreise, Warmwasser,
Zirkulation, verbunden durch Vor- und Rücklauf – und legt die Live-Werte
darauf.

Das Bild wird **aus den erkannten Anlagenteilen zusammengesetzt**, nicht als
fertiges Bild mitgeliefert. Ein festes Bild würde nur zu der Anlage passen, für
die es gezeichnet wurde; hier wächst das Schaubild mit: Wer zwei Puffer hat,
sieht zwei, wer keinen hat, sieht keinen.

Die einzelnen Anlagenteile liegen als **SVG-Dateien** in ``anlagenteile/``.
Jede Datei zeichnet ein Bauteil in einem eigenen Feld von ``MODUL_BREITE`` ×
``HOEHE``; die Mitte liegt bei x = 100, der Vorlauf auf y = 92, der Rücklauf auf
y = 318. Farben stehen darin als Platzhalter (``{{vorlauf}}``, ``{{korpus}}``,
…) und werden hier eingesetzt – sonst wäre jede Farbänderung eine Änderung an
elf Dateien. Fehlt eine Datei, greift die gezeichnete Ersatzform weiter unten;
das Schaubild bleibt also auch dann heil, wenn eine Datei fehlt.

Ausgegeben wird ein Bild als Daten-URL plus die Liste der Beschriftungen, die
Home Assistant als `picture-elements`-Karte darüberlegt.
"""

from __future__ import annotations

import base64
import contextlib
from pathlib import Path
import re
from typing import Any

# Maße des Schaubilds. Die Karte skaliert es auf ihre Breite, die Angaben
# sind also Verhältnisse, keine Bildpunkte.
HOEHE = 392
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

# Ordner mit den Bauteilzeichnungen.
TEILE_ORDNER = Path(__file__).parent / "anlagenteile"

# Platzhalter, die in den Bauteildateien stehen dürfen. Wer eine Farbe ändern
# will, ändert sie hier – nicht in elf Dateien.
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
    "schrift": SCHRIFT,
}

# Lage der Live-Werte je Anlagenart. Zwei Werte stehen ober- und unterhalb der
# Mitte, einer mittig. Bauteile mit anderer Form dürfen abweichen.
WERT_HOEHEN: dict[str, tuple[int, ...]] = {
    "puffer": (168, 258),
    "pumpenmodul": (186, 246),
    "solar": (158, 252),
}
WERT_HOEHEN_STANDARD = (170, 250)
WERT_HOEHE_EINZELN = 206

# Woran ein Anlagenteil erkennen lässt, dass Warmwasser bzw. eine Zirkulation
# daran hängt. Bei fctType 14 gehören beide Datenpunkte am Gerät zum Heizkreis,
# im Schaubild sind sie eigene Anlagenteile – so steht es auch auf dem Display
# der Anlage. Die Zirkulation braucht die Aufteilung selbst dann, wenn eine
# ZSP-Funktion vorhanden ist: Die meldet an einer der geprüften Anlagen gar
# keine Temperatur.
#
# Je zwei Schreibweisen, weil die kuratierten Tabellen anders benennen als die
# Geräte-Datenbank: „Warmwasser Ist-Temperatur" gegen „WW-Temperatur Aktueller
# Wert", „WW-Zirkulation Ist-Temperatur" gegen „WW-Zirkulationstemperatur
# Aktueller Wert". Der Sollwert darf dabei nicht mitgehen.
WARMWASSER_IST = r"\bww[- ]temperatur aktueller|\bwarmwasser ist[- ]?temperatur"
ZIRKULATION_IST = r"\bww-zirkulations?[- ]?(ist[- ])?temperatur(?!.*soll)"

# Der Stellwert des Heizkreismischers. „Laufzeit" muss draußen bleiben: Die
# Mischerlaufzeit ist eine Einstellung in Minuten, keine Stellung in Prozent.
MISCHER_IST = r"^mischer( stellwert)?$"

# Welcher Wert eines Anlagenteils wo im Schaubild steht.
# (Muster, Beschriftung) – die Reihenfolge bestimmt die Position von oben.
WERTE_JE_ART: dict[str, tuple[tuple[str, str], ...]] = {
    "kessel": (
        (r"kesseltemperatur ist", "Kessel"),
        (r"kesselleistung", "Leistung"),
    ),
    # Zwei Schreibweisen: die kuratierte Tabelle nennt sie „Puffer oben
    # Temperatur (TPE)", die Geräte-Datenbank „Puffertemperatur TPE" bzw.
    # „Puffertemperatur oben". Beide müssen treffen.
    "puffer": (
        (r"puffer(temperatur)?[ -]?oben|puffertemperatur tpe", "oben"),
        (r"puffer(temperatur)?[ -]?unten|puffertemperatur tpa", "unten"),
    ),
    "heizkreis": (
        (r"vorlauftemperatur ist", "Vorlauf"),
        (r"raumtemperatur ist", "Raum"),
    ),
    # Das Pumpen-/Relaismodul (ZSP, fctType 20). Es ist keine Zirkulation: Es
    # kann eine Pumpe regeln, eine externe Wärmeanforderung entgegennehmen oder
    # einen Sammelalarm schalten – was davon, sagt `29/0..29/3`.
    "pumpenmodul": (
        # Beide Schreibweisen: „Kesseltemperatur" ist der Herstellername, den
        # HeatNexus ab 1.3.0-beta.4 benutzt, „Temperatur Ist" der bis dahin
        # vergebene – der steht noch in jedem gespeicherten Erkennungsstand.
        (r"^kesseltemperatur$|^temperatur ist$", "Temperatur"),
        (r"r(ü|ue)cklauf temperatur", "Rücklauf"),
    ),
    # Nur der Istwert. Ein Sollwert an der Stelle, an der beim Puffer die
    # zweite *gemessene* Temperatur steht, liest sich wie ein Messwert und
    # verwirrt mehr, als er nützt.
    "wasser": ((r"\bww[- ]temperatur aktueller|\bwarmwasser ist", "Warmwasser"),),
    # Die Warmwasser-Zirkulation.
    "zirkulation": ((ZIRKULATION_IST, "Zirkulation"),),
    "solar": (
        (r"kollektortemperatur", "Kollektor"),
        (r"ww[- ]temperatur solar|puffertemperatur tps", "Speicher"),
    ),
    # Weiche bzw. Umschaltung: was hereinkommt und was im Speicher steht.
    "umschaltung": (
        (r"kesseltemperatur(?!.*soll)", "Kessel"),
        (r"puffertemperatur (oben|tpe)", "Puffer"),
    ),
}

# Die Pumpe eines Anlagenteils. Sie steht im Schaubild in der Leitung und
# dreht sich, solange sie läuft – im Standbild ist nicht zu erkennen, ob
# gerade etwas fließt.
PUMPE_JE_ART: dict[str, str] = {
    "kessel": r"kesselpumpe|\bpumpe\b",
    "puffer": r"pufferladepumpe",
    "heizkreis": r"heizkreispumpe",
    "wasser": r"\bww-ladepumpe",
    # Das ZSP-Modul meldet keinen Pumpenzustand, sondern seine Drehzahl.
    "pumpenmodul": r"pumpendrehzahl|zirkulationspumpe(?!.*modus)",
    "zirkulation": r"\bww-zirkulationspumpe(?!.*modus)",
    "solar": r"solarpumpe|pumpensteuerung drehzahl",
}

# Manche Pumpen melden keinen Zustand, sondern ihre Drehzahl in Prozent – die
# Pufferladepumpe etwa. Sie zählt genauso; „läuft" heißt dann „über null".
PUMPE_BEREICHE = ("binary_sensor", "switch", "sensor")

# Funktionstyp -> Art im Schaubild.
#
# **Diese Zuordnung ist nicht geraten.** Sie stammt aus den offiziellen
# Windhager-Dateien: `parameterLayer.json` führt je Funktionstyp die Liste
# seiner Datenpunkte, `de-parameters.json` deren Namen. Wer sie ändern will,
# lese sie dort nach – der Weg steht in `_intern/HERSTELLER-REFERENZ.md` 5.3.
# Bis 1.2.0 standen hier fünf Zuordnungen falsch, weil sie aus Namen abgeleitet
# waren statt aus der Parameterliste.
#
# Kurzform des Belegs je Typ:
#   1  Heizkurve, Kühlgrenzen, Estrich; Zeitprogramme 3/61..3/63 (Heizprogramme)
#   2  0/4 WW-Temperatur, Hygiene-Programm; Zeitprogramme 5/61, 5/62, 5/64
#   4  „Kaskadenmanager" – so nennt die Anlage ihn selbst; Folgeschaltung, ZSK
#   5  58/56 Kollektortemperatur, Kollektor spülen, Hydraulikschema Solar
#  13  „Solar ES" – ebenfalls von der Anlage benannt
#   6  60/30 Ionisationsstrom, 60/27 Anlagendruck, Netzbetriebsstunden
#   7  52/40 COP, Silentmode, Betriebsstunden Heizen/Warmwasser
#   8  56/5 Aktuelle Stufe E-Heizung, Betriebsstunden Stufe 1..3
#   9  Laufzeit bis Reinigung, Brennstoffverbrauch, Sondenumschaltung (BioWIN)
#  10  Startverzögerung Automatikkessel, O2-Signal, Puffertemperaturen
#  14  wie 1, aber ältere Baureihe (1/20 Heizkreispumpe) samt Warmwasser
#  15  Automatikkessel / Festbrennstoff / Pufferspeicher, Umschaltventil
#  16  21/65 TPE, 21/66 TPA, Pufferladepumpe
#  20  Pumpensteuerung, Ext. Wärmeanforderung, Summenstörmeldung
#  21  Puffertemperatur oben/mitte/unten, Beladegrad, Kälte-Puffertemperatur
#  24  58/12 Pumpe Wärmeerzeuger, Schichtladung, Rücklaufhochhaltung
#  25  PuroWIN
#  26  Kosten Strom, PV-Eingang, SG Ready, Bivalenztemperatur (Wärmepumpe)
#  27  50/70 Betriebsphase, Wärmemenge Heizen/Kühlen, E-Heizung (Wärmepumpe)
#
ART_JE_FCT: dict[int, str] = {
    # Wärmeerzeuger. Auch Wärmepumpe und E-Heizung stehen hier: Im Schaubild
    # sitzen sie an derselben Stelle wie ein Kessel. Welche Zeichnung es wird,
    # entscheidet die Kesselart.
    6: "kessel",  # Gas-/Ölbrennwertgerät
    7: "kessel",  # Wärmepumpe
    8: "kessel",  # E-Heizung / Zusatzheizung
    9: "kessel",  # BioWIN Pelletskessel
    10: "kessel",  # Automatik-/Zusatzkessel
    25: "kessel",  # PuroWIN
    26: "kessel",  # Wärmepumpe (Energiemanagement)
    27: "kessel",  # Wärmepumpe
    # Speicher
    16: "puffer",  # B-PLMi
    21: "puffer",  # Pufferspeicher neuerer Bauart
    # Heizkreise
    1: "heizkreis",  # Infinity PLUS
    14: "heizkreis",  # UML / UMLZ
    # Warmwasser als eigene Funktion. Bei fctType 14 hängt es dagegen am
    # Heizkreis – daraus macht `_module` ebenfalls ein eigenes Anlagenteil.
    2: "wasser",
    5: "solar",
    13: "solar",  # „Solar ES"
    # Module in der Leitung
    20: "pumpenmodul",  # ZSP
    24: "pumpenmodul",  # Pumpe Wärmeerzeuger / Schichtladung
    4: "umschaltung",  # Kaskade: hydraulische Weiche mit Folgeschaltung
    15: "umschaltung",  # Automatikkessel / Festbrennstoff / Puffer
}
ART_UNBEKANNT = "modul"

# Alle Arten, für die es eine Bauteilzeichnung geben muss. `zirkulation` steht
# in keinem Funktionstyp: Sie entsteht in `_module` aus den Datenpunkten eines
# Heizkreises.
ALLE_ARTEN = set(ART_JE_FCT.values()) | {"zirkulation", ART_UNBEKANNT}


def _art(fct_type: Any) -> str:
    try:
        return ART_JE_FCT.get(int(fct_type), ART_UNBEKANNT)
    except (TypeError, ValueError):
        return ART_UNBEKANNT


# ---------------------------------------------------------------------------
# Art des Wärmeerzeugers
# ---------------------------------------------------------------------------
# Erste Quelle: der Funktionstyp, wo er die Art schon festlegt. Eine
# Wärmepumpe verbrennt nichts – bei ihr braucht es keinen Brennstoff und keinen
# Namen, um die Zeichnung zu wählen.
KESSELART_JE_FCT: dict[int, str] = {
    6: "gas_oel",
    7: "waermepumpe",
    26: "waermepumpe",
    27: "waermepumpe",
}

# Zweite Quelle: der Brennstoff, den die Anlage selbst meldet (`38/126`,
# `38/127`). Er ist eindeutig – ein PuroWIN kann Hackgut *oder* Pellets
# verbrennen, die Baureihe allein verrät es nicht.
BRENNSTOFF_ENTITAET = re.compile(r"(aktueller|gew(ä|ae)hlter) brennstoff", re.IGNORECASE)
BRENNSTOFF_ART: tuple[tuple[str, str], ...] = (
    (r"pellet", "pellets"),
    (r"hackgut|hackschnitzel", "hackgut"),
    (r"scheitholz|st(ü|ue)ckholz|stueckholz", "scheitholz"),
)

# Dritte Quelle: der Name der Funktion. Die Windhager-Baureihen sind sprechend
# genug, und bei fremden Anlagen ist es oft das Einzige, was wir haben.
NAME_ART: tuple[tuple[str, str], ...] = (
    (r"aerowin|w(ä|ae)rmepumpe|heat\s?pump", "waermepumpe"),
    (r"purowin", "hackgut"),
    (r"biowin|pelletswin|pelletskessel|\bpellet", "pellets"),
    (r"logwin|vario\s?win|scheitholz|st(ü|ue)ckholz|holzvergaser", "scheitholz"),
    (r"duo\s?win|gas|\b(ö|oe)l\b|brennwert|therme", "gas_oel"),
)


def kesselart_erkennen(teile: list[dict[str, Any]]) -> str | None:
    """Art des Wärmeerzeugers aus den Anlagenteilen ableiten.

    Gibt einen Schlüssel aus ``const.KESSELARTEN`` zurück oder ``None``, wenn
    sich nichts sagen lässt. ``None`` heißt „neutral zeichnen" – nicht raten.
    Die Funktion wirkt ausschließlich auf die Zeichnung.
    """
    kessel = [t for t in teile if _art(t.get("fct_type")) == "kessel"]
    for teil in kessel:
        with contextlib.suppress(TypeError, ValueError):
            if art := KESSELART_JE_FCT.get(int(teil.get("fct_type"))):
                return art
    for teil in kessel:
        for eintrag in teil.get("entitaeten", []):
            if not BRENNSTOFF_ENTITAET.search(eintrag.get("name") or ""):
                continue
            text = str(eintrag.get("text") or "")
            for muster, art in BRENNSTOFF_ART:
                if re.search(muster, text, re.IGNORECASE):
                    return art
    for teil in kessel:
        for muster, art in NAME_ART:
            if re.search(muster, teil.get("name") or "", re.IGNORECASE):
                return art
    return None


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


def _mischer(entitaeten: list[dict[str, Any]]) -> str | None:
    """Der Stellwert des Heizkreismischers in Prozent, sofern gemeldet.

    Die Anlage nennt den Datenpunkt `1/21` „Mischer"; die kuratierte Tabelle
    „Mischer Stellwert". Beide Schreibweisen zählen.
    """
    treffer = _finde(
        [e for e in entitaeten if (e.get("unit") or "") == "%" or e.get("bereich") == "sensor"],
        MISCHER_IST,
    )
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
                    "mischer": _mischer(teil["entitaeten"]) if art == "heizkreis" else None,
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
        # Auch an einer eigenständigen Warmwasserfunktion (fctType 2) hängt die
        # Zirkulation als Datenpunkt, nicht als eigene Funktion.
        if art in ("heizkreis", "wasser") and _finde(teil["entitaeten"], ZIRKULATION_IST):
            kreis = _werte(teil["entitaeten"], "zirkulation")
            if kreis:
                module.append(
                    {
                        "titel": "Zirkulation",
                        "art": "zirkulation",
                        "werte": kreis,
                        "pumpe": _pumpe(teil["entitaeten"], "zirkulation"),
                    }
                )
    return module


# ---------------------------------------------------------------------------
# Bauteildateien
# ---------------------------------------------------------------------------
# Kennungen, die eine Bauteildatei selbst vergibt.
_ID = re.compile(r'id="([A-Za-z][\w.:-]*)"')


def _alle_bauteile() -> dict[str, str]:
    """Alle Bauteilzeichnungen einlesen.

    **Beim Import des Moduls, nicht beim ersten Schaubild.** Home Assistant
    lädt eine Integration in einem eigenen Thread, dort ist Lesen von der
    Platte erlaubt; das Schaubild dagegen entsteht in der Ereignisschleife, und
    ein Dateizugriff blockiert sie. Genau das meldete Home Assistant in
    1.2.0-beta.1 als „Detected blocking call to read_text".

    Es sind rund zwanzig Kilobyte – die dürfen dauerhaft im Speicher stehen.
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


def _bauteil(dateiname: str) -> str | None:
    """Eine Bauteilzeichnung – oder ``None``, wenn es sie nicht gibt.

    Der Inhalt ist ein SVG-Bruchstück ohne ``<svg>``-Wurzel: Es wird in das
    Gesamtbild eingesetzt, nicht als eigenes Bild ausgeliefert.
    """
    return BAUTEILE.get(dateiname)


def _farben(fragment: str) -> str:
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


def _bauteil_dateien(art: str, kesselart: str | None) -> tuple[str, ...]:
    """Dateinamen für ein Anlagenteil, in der Reihenfolge der Bevorzugung."""
    if art == "kessel" and kesselart:
        return (f"kessel-{kesselart}.svg", "kessel.svg")
    return (f"{art}.svg",)


def _aus_datei(art: str, kesselart: str | None, praefix: str) -> str | None:
    """Bauteilzeichnung, fertig eingefärbt und mit eindeutigen Kennungen."""
    for dateiname in _bauteil_dateien(art, kesselart):
        if (fragment := _bauteil(dateiname)) is not None:
            return _ids_eindeutig(_farben(fragment), praefix)
    return None


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


def _kasten(x: int, platz: int, modul: dict[str, Any], kesselart: str | None) -> str:
    """Ein Anlagenteil an seinem Platz im Gesamtbild."""
    art = modul["art"]
    inhalt = _aus_datei(art, kesselart if art == "kessel" else None, f"t{platz}-")
    if inhalt is None:
        inhalt = _ersatzform(art)

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


def _beschriftungen(x: int, modul: dict[str, Any], breite: int) -> list[dict[str, Any]]:
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


def _svg(module: list[dict[str, Any]], kesselart: str | None) -> tuple[str, int]:
    """Das Schaubild als SVG-Text und seine Breite."""
    breite = max(2 * RAND + len(module) * MODUL_BREITE, 400)
    teile = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {breite} {HOEHE}" '
        f'width="{breite}" height="{HOEHE}">',
        _rohre(breite),
    ]
    for platz, modul in enumerate(module):
        teile.append(_kasten(RAND + platz * MODUL_BREITE, platz, modul, kesselart))
    teile.append("</svg>")
    return "".join(teile), breite


def anlagenschema(
    teile: list[dict[str, Any]], kesselart: str | None = None
) -> dict[str, Any] | None:
    """Eine `picture-elements`-Karte für eine Anlage – oder nichts.

    Erwartet die Anlagenteile in der Form, die `dashboard._anlagen` liefert.
    ``kesselart`` wählt die Kesselzeichnung; ohne Angabe wird sie aus den
    Anlagenteilen abgeleitet.
    """
    module = _module(teile)
    if not module:
        return None

    if kesselart is None:
        kesselart = kesselart_erkennen(teile)
    svg, breite = _svg(module, kesselart)
    daten = base64.b64encode(svg.encode("utf-8")).decode("ascii")

    elemente: list[dict[str, Any]] = []
    pumpen: list[dict[str, Any]] = []
    brenner: list[dict[str, Any]] = []
    mischer: list[dict[str, Any]] = []
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
        # Der Mischer zeigt seine Stellung, nicht Bewegung: Ein dauernd
        # drehendes Ventil läse sich wie eine Pumpe, und die dreht sich im
        # Bild schon. Der Anzeiger schwenkt, das Stück Vorlauf darüber färbt
        # sich nach der Beimischung.
        if modul.get("mischer"):
            mitte = x + MODUL_BREITE // 2
            oben, _unten = KANTEN_JE_ART["heizkreis"]
            mischer.append(
                {
                    "entity": modul["mischer"],
                    "left": f"{mitte / breite * 100:.2f}%",
                    "top": f"{MISCHER_Y / HOEHE * 100:.2f}%",
                    "groesse": f"{MISCHER_MARKE / breite * 100:.2f}%",
                    # Das Stück Vorlauf zwischen Leitung und Ventil.
                    "stutzen_top": f"{VORLAUF_Y / HOEHE * 100:.2f}%",
                    "stutzen_hoehe": f"{(oben - VORLAUF_Y) / HOEHE * 100:.2f}%",
                    "titel": modul["titel"],
                }
            )
        # Der Wärmeerzeuger bekommt ein Glutbett, das mitgeht, solange er
        # Leistung bringt. Maßgeblich ist die Kesselleistung: Die Betriebsphase
        # heißt auf jeder Baureihe anders, eine Zahl über null nicht.
        if modul["art"] == "kessel":
            leistung = next(
                (w for w in modul["werte"] if w.get("beschriftung") == "Leistung"),
                None,
            )
            if leistung is not None:
                mitte = x + MODUL_BREITE // 2
                brenner.append(
                    {
                        "entity": leistung["entity_id"],
                        "left": f"{mitte / breite * 100:.2f}%",
                        "top": f"{GLUTBETT_Y / HOEHE * 100:.2f}%",
                        "breite": f"{GLUTBETT_BREITE / breite * 100:.2f}%",
                        "titel": modul["titel"],
                    }
                )

    # Lage der beiden Leitungen in Prozent des Bildes. Die Oberfläche legt
    # darüber eine bewegte Ebene: Ein Bild als Daten-URL kennt keine Zustände
    # aus Home Assistant, es kann also nicht selbst anzeigen, ob etwas fließt.
    leitungen = {
        "left": f"{RAND / breite * 100:.2f}%",
        "width": f"{(breite - 2 * RAND) / breite * 100:.2f}%",
        "vorlauf_top": f"{VORLAUF_Y / HOEHE * 100:.2f}%",
        "ruecklauf_top": f"{RUECKLAUF_Y / HOEHE * 100:.2f}%",
    }

    return {
        "type": "picture-elements",
        "image": f"data:image/svg+xml;base64,{daten}",
        "elements": elemente,
        "leitungen": leitungen,
        # Die Pumpen liegen nicht im Bild: Ein Standbild kann sich nicht
        # drehen. Sie werden als eigene Marken darübergelegt.
        "pumpen": pumpen,
        # Ebenso das Glutbett der Wärmeerzeuger und die Mischerstellung.
        "brenner": brenner,
        "mischer": mischer,
    }
