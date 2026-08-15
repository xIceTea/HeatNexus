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

# Derselbe Satz für eine helle Oberfläche.
#
# **Warum überhaupt zwei Sätze.** Das Schaubild steckt als `data:`-Adresse in
# einem `<img>`; darin erbt es kein CSS, und das Erscheinungsbild des
# Betrachters ist beim Zeichnen nicht bekannt. Auf hellem Grund verschwanden
# die dunklen Gehäuse zwar nicht, aber Rahmen und Beschriftung wurden unlesbar
# blass – sie waren für einen dunklen Hintergrund gerechnet.
#
# Umgesetzt wird der Wechsel als **Austausch der fertigen Farbwerte** im
# gezeichneten Bild, nicht als zweiter Weg durch den Zeichencode: Jede Farbe
# kommt aus genau diesem Satz und steht als eindeutige Zeichenfolge (`#e2543a`)
# im Ergebnis. Ein zweiter Pfad durch elf Bauteildateien und zwanzig
# Zeichenfunktionen wäre die Stelle, an der später einer von beiden vergessen
# wird.
FARBEN_HELL: dict[str, str] = {
    "vorlauf": "#c8412a",
    "ruecklauf": "#2b63b8",
    "rahmen": "#7d8b9a",
    "text": "#3d4854",
    "titel": "#16202b",
    "korpus": "#dde3ea",
    "korpus_hell": "#eef2f7",
    "korpus_dunkel": "#c2ccd8",
    "warm": "#c0402a",
    # Muss denselben Wert haben wie `vorlauf`: Im dunklen Satz sind beide
    # `#e2543a`, und der Austausch geschieht am fertigen Bild – dort ist nicht
    # mehr zu unterscheiden, welche Rolle eine Farbe hatte. Die Prüfung
    # darunter besteht darauf.
    "glut": "#c8412a",
    "kalt": "#3f78c9",
    "schrift": SCHRIFT,
}

# Dritter Satz: warmes Dunkel mit Terrakotta, passend zum gleichnamigen
# Farbsatz der Oberfläche.
FARBEN_TERRAKOTTA: dict[str, str] = {
    "vorlauf": "#d2603a",
    "ruecklauf": "#5b8ab8",
    "rahmen": "#3a3630",
    "text": "#b8b0a8",
    "titel": "#ece8e4",
    "korpus": "#242220",
    "korpus_hell": "#322f2b",
    "korpus_dunkel": "#1a1816",
    "warm": "#a8431f",
    # Muss `vorlauf` entsprechen – siehe `FARBEN_HELL`.
    "glut": "#d2603a",
    "kalt": "#436f9c",
    "schrift": SCHRIFT,
}

# Vierter Satz: ruhiges Dunkel mit Petrol. `vorlauf` bleibt warm – die
# Strömungsrichtung liest man an der Farbe, nicht an der Lage.
FARBEN_PETROL: dict[str, str] = {
    "vorlauf": "#e0714d",
    "ruecklauf": "#3f8fb8",
    "rahmen": "#2e3c3f",
    "text": "#93a3a3",
    "titel": "#e4ecec",
    "korpus": "#192226",
    "korpus_hell": "#26312f",
    "korpus_dunkel": "#10171a",
    "warm": "#b34a2a",
    # Muss `vorlauf` entsprechen – siehe `FARBEN_HELL`.
    "glut": "#e0714d",
    "kalt": "#2a5c94",
    "schrift": SCHRIFT,
}

# Fünfter Satz: dunkles Violett mit Pflaume.
FARBEN_PFLAUME: dict[str, str] = {
    "vorlauf": "#d9705f",
    "ruecklauf": "#6b7fd2",
    "rahmen": "#3a3145",
    "text": "#a297ad",
    "titel": "#ece7f0",
    "korpus": "#211b2a",
    "korpus_hell": "#2e2639",
    "korpus_dunkel": "#16121c",
    "warm": "#b34a4a",
    # Muss `vorlauf` entsprechen – siehe `FARBEN_HELL`.
    "glut": "#d9705f",
    "kalt": "#4d5aa8",
    "schrift": SCHRIFT,
}

THEMA_DUNKEL = "dunkel"
THEMA_HELL = "hell"
THEMA_TERRAKOTTA = "terrakotta"
THEMA_PETROL = "petrol"
THEMA_PFLAUME = "pflaume"

# Was die Oberfläche anbieten darf. `auto` folgt dem Erscheinungsbild von Home
# Assistant, die übrigen legen den Satz fest.
FARBSATZ_AUTO = "auto"
FARBSAETZE = (
    FARBSATZ_AUTO,
    THEMA_DUNKEL,
    THEMA_HELL,
    THEMA_TERRAKOTTA,
    THEMA_PETROL,
    THEMA_PFLAUME,
)

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

# Die gemessene Vorlauftemperatur eines Heizkreises – die Wärme, die wirklich
# im Heizkörper ankommt. Der Sollwert darf nicht mitgehen.
VORLAUF_IST = r"^vorlauftemperatur ist$"

# Die Brennkammertemperatur: wahlweise zweiter Wert am Kessel und Ersatzskala
# für das Glutbett, wenn keine Leistung gemeldet wird.
BRENNKAMMER_IST = r"brennerkammertemperatur|brennkammertemperatur"

# Der Analog-Sollwert des Pumpen-/Relaismoduls (0/95): die Temperatur, mit der
# gerade Wärme angefordert wird. Über null heißt: Es liegt eine Anforderung an.
#
# Er steht bewusst vor der Kesseltemperatur (0/7). Die misst den Fühler des
# Moduls – bei einer Fernwärmeübergabe also den Speicher auf der *anderen*
# Seite. Im Schaubild sah es damit so aus, als stünde diese Temperatur im
# Heizhaus, und die ganze Darstellung stimmte nicht mehr.
ANALOG_SOLLWERT = r"^analog[- ]sollwert$"
KESSELLEISTUNG_IST = r"kesselleistung"

# Unter dieser Temperatur glimmt nichts, darüber wird es voll.
BRENNKAMMER_KALT = 100
BRENNKAMMER_HEISS = 500

# Welcher Wert eines Anlagenteils wo im Schaubild steht.
# (Muster, Beschriftung, kanonische Schlüssel) – die Reihenfolge bestimmt die
# Position von oben. Der Schlüssel steht hinten und gewinnt, wo es ihn gibt;
# ohne ihn bliebe das Schaubild in einer fremden Sprache leer.
Wert = tuple[str, str, tuple[str, ...]]

WERTE_JE_ART: dict[str, tuple[Wert, ...]] = {
    # Der zweite Wert am Kessel ist wählbar (Option „kesselwert"); hier steht
    # die Vorgabe. `_werte_je_art` tauscht ihn gegebenenfalls aus.
    "kessel": (
        (r"kesseltemperatur ist", "Kessel", ("boiler_temperature",)),
        (r"kesselleistung", "Leistung", ("boiler_power",)),
    ),
    # Zwei Schreibweisen: die kuratierte Tabelle nennt sie „Puffer oben
    # Temperatur (TPE)", die Geräte-Datenbank „Puffertemperatur TPE" bzw.
    # „Puffertemperatur oben". Beide müssen treffen.
    "puffer": (
        (r"puffer(temperatur)?[ -]?oben|puffertemperatur tpe", "oben", ("buffer_top",)),
        (r"puffer(temperatur)?[ -]?unten|puffertemperatur tpa", "unten", ("buffer_bottom",)),
    ),
    "heizkreis": (
        (r"vorlauftemperatur ist", "Vorlauf", ("flow_temperature",)),
        (r"raumtemperatur ist", "Raum", ("room_temperature",)),
    ),
    # Das Pumpen-/Relaismodul (ZSP, fctType 20). Es ist keine Zirkulation: Es
    # kann eine Pumpe regeln, eine externe Wärmeanforderung entgegennehmen oder
    # einen Sammelalarm schalten – was davon, sagt `29/0..29/3`.
    # Bewusst leer: siehe `_module`. Was das Modul tut, zeigen seine Lampen.
    "pumpenmodul": (),
    # Nur der Istwert. Ein Sollwert an der Stelle, an der beim Puffer die
    # zweite *gemessene* Temperatur steht, liest sich wie ein Messwert und
    # verwirrt mehr, als er nützt.
    "wasser": (
        (r"\bww[- ]temperatur aktueller|\bwarmwasser ist", "Warmwasser", ("dhw_temperature",)),
    ),
    # Die Warmwasser-Zirkulation.
    "zirkulation": ((ZIRKULATION_IST, "Zirkulation", ("dhw_circulation_temperature",)),),
    "solar": (
        (r"kollektortemperatur", "Kollektor", ("collector_temperature",)),
        (
            r"ww[- ]temperatur solar|puffertemperatur tps",
            "Speicher",
            ("solar_storage_temperature",),
        ),
    ),
    # Weiche bzw. Umschaltung: was hereinkommt und was im Speicher steht.
    "umschaltung": (
        (r"kesseltemperatur(?!.*soll)", "Kessel", ("boiler_temperature",)),
        (r"puffertemperatur (oben|tpe)", "Puffer", ("buffer_top",)),
    ),
}

# Die Pumpe eines Anlagenteils. Sie steht im Schaubild in der Leitung und
# dreht sich, solange sie läuft – im Standbild ist nicht zu erkennen, ob
# gerade etwas fließt.
#
# Kessel-, Puffer- und Solarpumpe haben (noch) keinen kanonischen Schlüssel:
# Ihre Adressen unterscheiden sich je Baureihe und sind nicht belegt. Dort
# bleibt es beim Namen.
PUMPE_JE_ART: dict[str, tuple[str, tuple[str, ...]]] = {
    "kessel": (r"kesselpumpe|\bpumpe\b", ()),
    "puffer": (r"pufferladepumpe", ()),
    "heizkreis": (r"heizkreispumpe", ("circuit_pump",)),
    "wasser": (r"\bww-ladepumpe", ("dhw_charge_pump",)),
    # Das ZSP-Modul meldet keinen Pumpenzustand, sondern seine Drehzahl.
    "pumpenmodul": (r"pumpendrehzahl|zirkulationspumpe(?!.*modus)", ("pump_speed",)),
    "zirkulation": (r"\bww-zirkulationspumpe(?!.*modus)", ("dhw_circulation_pump",)),
    "solar": (r"solarpumpe|pumpensteuerung drehzahl", ()),
}

# Manche Pumpen melden keinen Zustand, sondern ihre Drehzahl in Prozent – die
# Pufferladepumpe etwa. Sie zählt genauso; „läuft" heißt dann „über null".
PUMPE_BEREICHE = ("binary_sensor", "switch", "sensor")

# Funktionstyp -> Art im Schaubild.
#
# **Diese Zuordnung ist nicht geraten.** Sie stammt aus den offiziellen
# Windhager-Dateien: `parameterLayer.json` führt je Funktionstyp die Liste
# seiner Datenpunkte, `de-parameters.json` deren Namen. Wer sie ändern will,
# lese sie dort nach – aus Namen abgeleitet gerät die Zuordnung falsch.
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
# genug, und bei fremden Anlagen ist es oft das Einzige, was vorliegt.
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


def _finde(
    entitaeten: list[dict[str, Any]], muster: str, *schluessel: str
) -> dict[str, Any] | None:
    """Erste passende Entität; eine mit Wert hat Vorrang.

    Ein Wert darf keine Bedingung sein. Das Schaubild wird gebaut, während die
    Anlage noch eingelesen wird – wäre der Wert Pflicht, bliebe es leer und
    füllte sich auch später nicht mehr.

    **Der kanonische Schlüssel gewinnt, der Name bleibt der Rückfall** – wie in
    `dashboard._trifft`, aber eigenständig: Dieses Modul importiert nichts aus
    Home Assistant, damit es sich ohne dessen Installation prüfen lässt.
    """
    regex = re.compile(muster, re.IGNORECASE)
    treffer = [
        e
        for e in entitaeten
        if (schluessel and e.get("schluessel") in schluessel) or regex.search(e["name"] or "")
    ]
    if not treffer:
        return None
    return next((e for e in treffer if e.get("hat_wert")), treffer[0])


def _werte_je_art(art: str, kesselwert: str | None) -> tuple[Wert, ...]:
    """Die Wertevorlage einer Art, mit dem gewählten zweiten Kesselwert."""
    vorlage = WERTE_JE_ART.get(art, ())
    if art != "kessel" or kesselwert != "brennkammer":
        return vorlage
    return (vorlage[0], (BRENNKAMMER_IST, "Brennkammer", ("combustion_chamber_temperature",)))


def _werte(
    entitaeten: list[dict[str, Any]], art: str, kesselwert: str | None = None
) -> list[dict[str, Any]]:
    """Die Messwerte eines Anlagenteils in der Reihenfolge des Schaubilds."""
    werte = []
    for muster, beschriftung, schluessel in _werte_je_art(art, kesselwert):
        if (treffer := _finde(entitaeten, muster, *schluessel)) is not None:
            werte.append({"entity_id": treffer["entity_id"], "beschriftung": beschriftung})
    return werte


def _pumpe(entitaeten: list[dict[str, Any]], art: str) -> str | None:
    """Die Pumpe eines Anlagenteils, sofern sie als Zustand gemeldet wird."""
    muster, schluessel = PUMPE_JE_ART.get(art, ("", ()))
    if not muster:
        return None
    treffer = _finde(
        [e for e in entitaeten if e.get("bereich") in PUMPE_BEREICHE], muster, *schluessel
    )
    return treffer["entity_id"] if treffer else None


def _mischer(entitaeten: list[dict[str, Any]]) -> str | None:
    """Der Stellwert des Heizkreismischers in Prozent, sofern gemeldet.

    Die Anlage nennt den Datenpunkt `1/21` „Mischer"; die kuratierte Tabelle
    „Mischer Stellwert". Beide Schreibweisen zählen.
    """
    treffer = _finde(
        [e for e in entitaeten if (e.get("unit") or "") == "%" or e.get("bereich") == "sensor"],
        MISCHER_IST,
        "mixer_position",
    )
    return treffer["entity_id"] if treffer else None


# Woran ein Pumpen-/Relaismodul erkennen lässt, dass es eine Aufgabe hat: ein
# eigener **Messwert** oder eine der Funktionen aus Gruppe 29. Sollwerte zählen
# ausdrücklich nicht – „Solltemperatur ext. Wärmeanforderung" und
# „Digital-Sollwert WWK" meldet auch ein Modul, an dem nichts hängt. Deshalb
# sind alle Muster verankert: unverankert fischte
# `ext. wärmeanforderung` genau diesen Sollwert mit heraus.
MODUL_AUFGABE: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"^kesseltemperatur$", ("boiler_temperature",)),
    (r"^temperatur ist$", ()),
    (r"^ext\.? w(ä|ae)rmeanforderung$", ()),
    (r"^pumpensteuerung$", ()),
    (r"^relaisfunktion$", ()),
)


def modul_in_betrieb(entitaeten: list[dict[str, Any]]) -> bool:
    """Ob ein Pumpen-/Relaismodul an dieser Anlage überhaupt eine Aufgabe hat.

    Der ZSP ist ein Universalmodul: Es kann eine Pumpe regeln, eine externe
    Wärmeanforderung entgegennehmen oder einen Sammelalarm schalten – oder als
    Klemmenkasten dasitzen und nichts davon. Welche Aufgabe verdrahtet ist,
    sagt die Anlage nicht als Wert; sie sagt es dadurch, **welche Datenpunkte
    sie überhaupt beantwortet**. Fehlende beantwortet sie mit 404 bzw. 409, und
    die fliegen schon in `client._apply_metadata` heraus.

    Ein verdrahtetes Modul führt Kesseltemperatur (``0/7``), Pumpendrehzahl
    (``0/22``) oder externe Anforderung (``29/2``); ein unbenutztes meldet
    davon keinen einzigen, sondern nur Sollwerte und den Aktorentest. Ohne
    diese Unterscheidung stünde es im Schaubild als Kasten in der Leitung, durch
    den nichts fließt, mit Lampen, die nie angehen.
    """
    return _pumpe(entitaeten, "pumpenmodul") is not None or any(
        _finde(entitaeten, muster, *schluessel) is not None for muster, schluessel in MODUL_AUFGABE
    )


# Bereiche, deren Zustand sich als Beschriftung im Bild lesen lässt.
WERT_BEREICHE = ("sensor", "number", "binary_sensor", "select")


def teil_kennung(teil: dict[str, Any]) -> str:
    """Stabile Kennung eines Anlagenteils für die Auswahl."""
    return str(teil.get("id") or teil.get("name") or "")


def waehlbare_werte(
    teile: list[dict[str, Any]], kesselwert: str | None = None
) -> list[dict[str, Any]]:
    """Je Anlagenteil die Werte, die zur Auswahl stehen, samt Vorgabe.

    Die Liste kommt aus der Erkennung, nicht aus einer gepflegten Tabelle – nur
    so trägt sie auch auf Baureihen, für die es hier kein Namensmuster gibt.
    """
    liste = []
    for teil in teile:
        art = _art(teil.get("fct_type"))
        werte = [
            {"entity": e["entity_id"], "name": e.get("name") or e["entity_id"]}
            for e in teil["entitaeten"]
            if e.get("bereich") in WERT_BEREICHE and e.get("kategorie") != "config"
        ]
        if not werte:
            continue
        liste.append(
            {
                "id": teil_kennung(teil),
                "titel": teil.get("name") or "",
                "art": art,
                "werte": sorted(werte, key=lambda w: w["name"]),
                "vorgabe": [w["entity_id"] for w in _werte(teil["entitaeten"], art, kesselwert)],
            }
        )
    return liste


def _gewaehlte_werte(
    teil: dict[str, Any], art: str, kesselwert: str | None, gewaehlt: list[str]
) -> list[dict[str, Any]]:
    """Die gewählten Werte in ihrer Reihenfolge, mit bekannter Beschriftung.

    Was das Schaubild ohnehin kennt, behält seine Rolle (`oben`, `unten`); alles
    Übrige bekommt seinen Namen. Ohne die Rolle wüsste der Puffer nicht mehr,
    welcher Fühler oben sitzt.
    """
    bekannt = {w["entity_id"]: w for w in _werte(teil["entitaeten"], art, kesselwert)}
    namen = {e["entity_id"]: e.get("name") or e["entity_id"] for e in teil["entitaeten"]}
    werte = []
    for entity in gewaehlt:
        if entity in bekannt:
            werte.append(bekannt[entity])
        elif entity in namen:
            werte.append({"entity_id": entity, "beschriftung": namen[entity]})
    return werte


def _module(
    teile: list[dict[str, Any]],
    kesselwert: str | None = None,
    auswahl: dict[str, list[str]] | None = None,
    teile_aus: list[str] | tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Anlagenteile, die sich zeichnen lassen, mit ihren Werten.

    Warmwasser bekommt einen eigenen Kasten, obwohl seine Datenpunkte am
    Heizkreis hängen – auf dem Display der Anlage steht es genauso.
    """
    module: list[dict[str, Any]] = []
    for teil in teile:
        art = _art(teil.get("fct_type"))
        kennung = teil_kennung(teil)
        if kennung in set(teile_aus or ()):
            continue
        gewaehlt = (auswahl or {}).get(kennung)
        werte = (
            _gewaehlte_werte(teil, art, kesselwert, gewaehlt)
            if gewaehlt is not None
            else _werte(teil["entitaeten"], art, kesselwert)
        )
        # Das Pumpen-/Relaismodul wird auch ohne Messwert gezeichnet: Seine
        # Kesseltemperatur misst bei einer Fernwärmeübergabe den Speicher auf
        # der anderen Seite – im Schaubild sagt die Zahl nichts. Dass das Modul
        # in der Leitung sitzt, muss man trotzdem sehen; seinen Zustand zeigen
        # die Lampen. Ein Modul ohne Aufgabe bleibt aber draußen, siehe
        # `modul_in_betrieb`.
        if art == "pumpenmodul" and not modul_in_betrieb(teil["entitaeten"]):
            continue
        if werte or art == "pumpenmodul":
            module.append(
                {
                    "titel": teil["name"],
                    "art": art,
                    "werte": werte,
                    "pumpe": _pumpe(teil["entitaeten"], art),
                    "mischer": _mischer(teil["entitaeten"]) if art == "heizkreis" else None,
                    # Die Temperatur, die tatsächlich in den Heizkörper geht.
                    # Nicht der Sollwert: Der steht auch dann auf 45 °C, wenn
                    # der Kreis abgeschaltet ist und der Körper kalt hängt.
                    "vorlauf": (
                        e["entity_id"]
                        if art == "heizkreis"
                        and (e := _finde(teil["entitaeten"], VORLAUF_IST, "flow_temperature"))
                        else None
                    ),
                    # Für Auswertungen, die über die angezeigten Werte
                    # hinausgehen – etwa die Lampen des Pumpen-/Relaismoduls.
                    "entitaeten": teil["entitaeten"],
                    # Für das Glutbett, unabhängig davon, welcher Wert im Bild
                    # steht: Leistung zuerst, Brennkammertemperatur als Ersatz.
                    "leistung": (
                        e["entity_id"]
                        if art == "kessel"
                        and (e := _finde(teil["entitaeten"], KESSELLEISTUNG_IST, "boiler_power"))
                        else None
                    ),
                    "brennkammer": (
                        e["entity_id"]
                        if art == "kessel"
                        and (
                            e := _finde(
                                teil["entitaeten"],
                                BRENNKAMMER_IST,
                                "combustion_chamber_temperature",
                            )
                        )
                        else None
                    ),
                }
            )
        # Hängt an diesem Kreis eine Warmwasserbereitung, wird sie als eigener
        # Anlagenteil dahinter gezeichnet.
        if (
            art == "heizkreis"
            and _finde(teil["entitaeten"], WARMWASSER_IST, "dhw_temperature") is not None
        ):
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
        if art in ("heizkreis", "wasser") and _finde(
            teil["entitaeten"], ZIRKULATION_IST, "dhw_circulation_temperature"
        ):
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


# Platzhalter in den Bauteildateien, die **keine** Farbe sind, sondern vom
# Zustand der Anlage abhängen. Sie werden je Bauteil eingesetzt, nicht aus der
# festen Tafel – stehen aber hier, damit der Test sie von einem Tippfehler
# unterscheiden kann.
#
# `koerper`  Füllung des Speicherkörpers: der neutrale Verlauf, oder `none`,
#            wenn die Oberfläche die gemessene Schichtung darunterlegt.
ZUSATZ_PLATZHALTER = frozenset({"koerper"})


def _bauteil_dateien(art: str, kesselart: str | None) -> tuple[str, ...]:
    """Dateinamen für ein Anlagenteil, in der Reihenfolge der Bevorzugung."""
    if art == "kessel" and kesselart:
        return (f"kessel-{kesselart}.svg", "kessel.svg")
    return (f"{art}.svg",)


def _aus_datei(
    art: str, kesselart: str | None, praefix: str, zusatz: dict[str, str] | None = None
) -> str | None:
    """Bauteilzeichnung, fertig eingefärbt und mit eindeutigen Kennungen.

    ``zusatz`` füllt Platzhalter, die nicht aus der festen Farbtafel kommen –
    beim Puffer die Füllung des Speicherkörpers, die von den vorhandenen
    Fühlern abhängt. Sie wird vor ``_ids_eindeutig`` eingesetzt, damit ein
    darin genannter Verlauf mit umbenannt wird.
    """
    for dateiname in _bauteil_dateien(art, kesselart):
        if (fragment := _bauteil(dateiname)) is not None:
            for name, wert in (zusatz or {}).items():
                fragment = fragment.replace("{{" + name + "}}", wert)
            return _ids_eindeutig(_farben(fragment), praefix)
    return None


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

# Wie viel wärmer der Kessel sein muss, damit wirklich in den Puffer geladen
# wird. Ohne diesen Abstand gälte schon ein Zehntelgrad Messrauschen als
# Ladung.
LADE_HYSTERESE = 2.0

# Die Lampen des Pumpen-/Relaismoduls, aus `pumpenmodul.svg`: fünf Klemmen
# oben, eine Betriebslampe rechts unten. Liegt eine Wärmeanforderung an,
# blinken die Klemmen grün und die Betriebslampe wechselt von Rot auf Grün –
# so sieht man am Bild selbst, dass gerade angefordert wird.
# Die Radien sind größer als die gezeichneten Punkte darunter: Die grüne
# Lampe muss die rote vollständig verdecken, sonst schimmert Rot am Rand
# durch.
ZSP_KLEMMEN = ((74, 164, 4), (88, 164, 4), (102, 164, 4), (116, 164, 4), (130, 164, 4))
ZSP_BETRIEBSLAMPE = (136, 252, 6)


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


def _kasten(x: int, platz: int, modul: dict[str, Any], kesselart: str | None) -> str:
    """Ein Anlagenteil an seinem Platz im Gesamtbild."""
    art = modul["art"]
    # Der Speicherkörper bleibt leer, wenn die Oberfläche die gemessene
    # Temperatur darunterlegt – sonst deckt sie die Zeichnung zu.
    zusatz = {}
    if (masse := SPEICHER_ARTEN.get(art)) is not None:
        zusatz["koerper"] = "none" if hat_speicherfarbe(modul) else masse["fuellung"]
    inhalt = _aus_datei(art, kesselart if art == "kessel" else None, f"t{platz}-", zusatz)
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


def _entsprechung(ziel: dict[str, str]) -> dict[str, str]:
    """Dunkle Farbe -> Farbe des Zielsatzes, für den Austausch im fertigen Bild.

    Zwei Rollen dürfen sich einen dunklen Wert teilen (``vorlauf`` und ``glut``
    sind beide ``#e2543a``); dann teilen sie sich auch den neuen, sonst
    entscheidet die Reihenfolge im Wörterbuch, welche Rolle die falsche bekommt.
    """
    abbildung: dict[str, str] = {}
    for name, dunkel in FARBEN.items():
        if name == "schrift":
            continue
        neu = ziel[name]
        if abbildung.setdefault(dunkel, neu) != neu:
            raise ValueError(
                f"{dunkel} soll gleichzeitig {abbildung[dunkel]} und {neu} werden "
                f"(Rolle {name}) – im fertigen Bild ist das nicht zu unterscheiden."
            )
    return abbildung


# Dunkler Farbwert -> Wert des Zielsatzes, je Thema. Der Browser bekommt
# diese Tabellen und tauscht damit selbst; das spart je Satz ein volles Bild.
FARBABBILDUNGEN = {
    THEMA_HELL: _entsprechung(FARBEN_HELL),
    THEMA_TERRAKOTTA: _entsprechung(FARBEN_TERRAKOTTA),
    THEMA_PETROL: _entsprechung(FARBEN_PETROL),
    THEMA_PFLAUME: _entsprechung(FARBEN_PFLAUME),
}
_FARBSTELLE = re.compile(
    "|".join(sorted(map(re.escape, FARBABBILDUNGEN[THEMA_HELL]), reverse=True))
)


def farben_umstellen(svg: str, thema: str | None) -> str:
    """Ein fertiges Schaubild auf einen anderen Farbsatz umstellen.

    In **einem** Durchgang, nicht als Kette einzelner Ersetzungen: Sonst könnte
    eine gerade eingesetzte Farbe von der nächsten Regel noch einmal getroffen
    werden. Der dunkle Satz steht schon im Bild.
    """
    abbildung = FARBABBILDUNGEN.get(thema or "")
    if abbildung is None:
        return svg
    return _FARBSTELLE.sub(lambda treffer: abbildung[treffer.group(0)], svg)


def _datenadresse(svg: str) -> str:
    """Ein fertiges SVG als `data:`-Adresse für ein `<img>`."""
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def anlagenschema(
    teile: list[dict[str, Any]],
    kesselart: str | None = None,
    kesselwert: str | None = None,
    auswahl: dict[str, list[str]] | None = None,
    teile_aus: list[str] | tuple[str, ...] = (),
) -> dict[str, Any] | None:
    """Eine `picture-elements`-Karte für eine Anlage – oder nichts.

    Erwartet die Anlagenteile in der Form, die `dashboard._anlagen` liefert.
    ``kesselart`` wählt die Kesselzeichnung; ohne Angabe wird sie aus den
    Anlagenteilen abgeleitet.

    **Beide Farbsätze werden mitgeliefert**, nicht einer nach Vorgabe: Das Bild
    steckt als `data:`-Adresse in einem `<img>` und erbt dort kein CSS, die
    Karte wird aber serverseitig gebaut – zu diesem Zeitpunkt ist das
    Erscheinungsbild des Betrachters nicht bekannt, und bei einem Umschalten
    gäbe es niemanden, der neu zeichnet. ``image`` trägt den hellen Satz,
    ``dark_mode_image`` den dunklen; genau so erwartet es die
    `picture-elements`-Karte. Die eigene Oberfläche wählt mit derselben Angabe
    (`panel/daten.py`).
    """
    module = _module(teile, kesselwert, auswahl, teile_aus)
    # Ein Bild aus lauter leeren Kästen hilft niemandem: Mindestens ein
    # Anlagenteil muss etwas messen.
    if not any(m["werte"] for m in module):
        return None

    if kesselart is None:
        kesselart = kesselart_erkennen(teile)
    svg, breite = _svg(module, kesselart)

    elemente: list[dict[str, Any]] = []
    pumpen: list[dict[str, Any]] = []
    brenner: list[dict[str, Any]] = []
    mischer: list[dict[str, Any]] = []
    heizkoerper: list[dict[str, Any]] = []
    schichtung: list[dict[str, Any]] = []
    speicher: list[dict[str, Any]] = []
    lampen: list[dict[str, Any]] = []
    # Wer dem Speicher Wärme entnimmt: alle Pumpen der Verbraucher. Wird
    # gleich zweimal gebraucht – für die Marke am Speicher und für seine
    # Stichleitung.
    entnahme = [m["pumpe"] for m in module if m.get("pumpe") and m["art"] in ENTNAHME_ARTEN]

    for platz, modul in enumerate(module):
        x = RAND + platz * MODUL_BREITE
        elemente += _beschriftungen(x, modul, breite)
        if modul.get("pumpe"):
            # Die Pumpe sitzt im Rücklauf, unterhalb ihres Anlagenteils.
            mitte = x + MODUL_BREITE // 2
            oben, unten = KANTEN_JE_ART.get(modul["art"], KANTEN_STANDARD)
            pumpen.append(
                {
                    "entity": modul["pumpe"],
                    "left": f"{mitte / breite * 100:.2f}%",
                    "top": f"{RUECKLAUF_Y / HOEHE * 100:.2f}%",
                    "titel": modul["titel"],
                    # Die beiden senkrechten Stichleitungen dieses Anlagenteils.
                    # Sie strömen nur, solange **seine** Pumpe fördert – daran
                    # sieht man, wohin die Wärme gerade geht. Die waagrechten
                    # Leitungen strömen dagegen immer, sobald irgendwo etwas
                    # läuft: Dort steht das Wasser ja auch nicht still.
                    "vorlauf_top": f"{VORLAUF_Y / HOEHE * 100:.2f}%",
                    "vorlauf_hoehe": f"{(oben - VORLAUF_Y) / HOEHE * 100:.2f}%",
                    "ruecklauf_top": f"{unten / HOEHE * 100:.2f}%",
                    "ruecklauf_hoehe": f"{(RUECKLAUF_Y - unten) / HOEHE * 100:.2f}%",
                    # Ein Speicher strömt in beide Richtungen: Seine eigene
                    # Pumpe lädt ihn, entnommen wird ihm von den Pumpen der
                    # Verbraucher – und dabei dreht die Ladepumpe nicht.
                    "entnahme": entnahme if modul["art"] == "puffer" else [],
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
        # Der Heizkörper färbt sich nach dem, was durch ihn fließt: kalt in der
        # Farbe des Rücklaufs, heiß in der des Vorlaufs. Ohne gemessene
        # Vorlauftemperatur bleibt es bei der Zeichnung.
        if modul["art"] == "heizkreis" and modul.get("vorlauf"):
            heizkoerper.append(
                {
                    "entity": modul["vorlauf"],
                    "left": f"{(x + HEIZKOERPER_X) / breite * 100:.2f}%",
                    "top": f"{HEIZKOERPER_Y / HOEHE * 100:.2f}%",
                    "breite": f"{HEIZKOERPER_BREITE / breite * 100:.2f}%",
                    "hoehe": f"{HEIZKOERPER_HOEHE / HOEHE * 100:.2f}%",
                    # Anteile der Ebenenbreite, nicht Bildpunkte – siehe
                    # HEIZKOERPER_GLIED.
                    "glied": f"{HEIZKOERPER_GLIED / HEIZKOERPER_BREITE * 100:.4f}%",
                    "raster": f"{HEIZKOERPER_RASTER / HEIZKOERPER_BREITE * 100:.4f}%",
                    "glanz_von": f"{HEIZKOERPER_GLANZ_VON / HEIZKOERPER_BREITE * 100:.4f}%",
                    "glanz_bis": f"{HEIZKOERPER_GLANZ_BIS / HEIZKOERPER_BREITE * 100:.4f}%",
                    "anzahl": HEIZKOERPER_ANZAHL,
                    "kalt": HEIZKOERPER_KALT,
                    "heiss": HEIZKOERPER_HEISS,
                    "titel": modul["titel"],
                }
            )

        # Der Wärmeerzeuger bekommt ein Glutbett, das mitgeht, solange er
        # Leistung bringt. Maßgeblich ist die Kesselleistung: Die Betriebsphase
        # heißt auf jeder Baureihe anders, eine Zahl über null nicht.
        if modul["art"] == "kessel":
            # Erste Wahl bleibt die Leistung, unabhängig davon, welcher Wert
            # angezeigt wird. Fehlt sie, dient die Brennkammertemperatur als
            # Ersatzskala – dort heißt kalt 100 °C und voll 500 °C.
            leistung = modul.get("leistung")
            ersatz = modul.get("brennkammer")
            if leistung or ersatz:
                mitte = x + MODUL_BREITE // 2
                brenner.append(
                    {
                        "entity": leistung,
                        "ersatz": ersatz,
                        "ersatz_min": BRENNKAMMER_KALT,
                        "ersatz_max": BRENNKAMMER_HEISS,
                        "left": f"{mitte / breite * 100:.2f}%",
                        "top": f"{GLUTBETT_Y / HOEHE * 100:.2f}%",
                        "breite": f"{GLUTBETT_BREITE / breite * 100:.2f}%",
                        "titel": modul["titel"],
                    }
                )

    # Der Wärmeerzeuger meldet keine eigene Pumpe – sein Wasser bewegt die
    # Pufferladepumpe. Nur die Leitung, keine Pumpenmarke: An dieser Stelle
    # sitzt keine Pumpe.
    ladepumpe = next((m["pumpe"] for m in module if m["art"] == "puffer" and m.get("pumpe")), None)
    if ladepumpe:
        for platz, modul in enumerate(module):
            if modul["art"] != "kessel" or modul.get("pumpe"):
                continue
            mitte = RAND + platz * MODUL_BREITE + MODUL_BREITE // 2
            oben, unten = KANTEN_JE_ART.get("kessel", KANTEN_STANDARD)
            pumpen.append(
                {
                    "entity": ladepumpe,
                    "left": f"{mitte / breite * 100:.2f}%",
                    "top": f"{RUECKLAUF_Y / HOEHE * 100:.2f}%",
                    "titel": modul["titel"],
                    "nur_strang": True,
                    "vorlauf_top": f"{VORLAUF_Y / HOEHE * 100:.2f}%",
                    "vorlauf_hoehe": f"{(oben - VORLAUF_Y) / HOEHE * 100:.2f}%",
                    "ruecklauf_top": f"{unten / HOEHE * 100:.2f}%",
                    "ruecklauf_hoehe": f"{(RUECKLAUF_Y - unten) / HOEHE * 100:.2f}%",
                }
            )

    # Die Lampen des Pumpen-/Relaismoduls. Sie hängen am Analog-Sollwert: über
    # null fordert das Modul Wärme an.
    for platz, modul in enumerate(module):
        if modul["art"] != "pumpenmodul":
            continue
        soll = _finde(modul.get("entitaeten") or [], ANALOG_SOLLWERT, "analog_setpoint")
        if soll is None:
            continue
        x = RAND + platz * MODUL_BREITE
        for lx, ly, r in (*ZSP_KLEMMEN, ZSP_BETRIEBSLAMPE):
            lampen.append(
                {
                    "entity": soll["entity_id"],
                    "left": f"{(x + lx) / breite * 100:.2f}%",
                    "top": f"{ly / HOEHE * 100:.2f}%",
                    "groesse": f"{(2 * r) / breite * 100:.2f}%",
                    "art": "betrieb" if (lx, ly, r) == ZSP_BETRIEBSLAMPE else "klemme",
                    "titel": modul["titel"],
                }
            )

    # Die Kesseltemperatur des ersten Wärmeerzeugers. Ohne sie liesse sich
    # nicht sagen, ob die laufende Ladepumpe wirklich Wärme in den Puffer
    # bringt oder nur umwälzt.
    kessel_ist = next(
        (
            w["entity_id"]
            for m in module
            if m["art"] == "kessel"
            for w in m["werte"]
            if w.get("beschriftung") == "Kessel"
        ),
        None,
    )
    # Der eingefärbte Inhalt von Puffer und Boiler. Beide laufen über dieselbe
    # Ebene: Der Puffer hat zwei Fühler und zeigt damit eine Schichtung, der
    # Boiler einen und wird gleichmäßig eingefärbt.
    for platz, modul in enumerate(module):
        masse = SPEICHER_ARTEN.get(modul["art"])
        if masse is None:
            continue
        oben, unten = speicherfuehler(modul)
        if oben is None:
            continue
        x = RAND + platz * MODUL_BREITE
        schichtung.append(
            {
                "oben": oben,
                "unten": unten,
                "left": f"{(x + masse['x']) / breite * 100:.2f}%",
                "top": f"{masse['y'] / HOEHE * 100:.2f}%",
                "breite": f"{masse['breite'] / breite * 100:.2f}%",
                "hoehe": f"{masse['hoehe'] / HOEHE * 100:.2f}%",
                # Der Eckradius als Anteil je Achse – sonst verzieht er sich,
                # sobald die Karte das Bild skaliert.
                "ecke": (
                    f"{masse['ecke'] / masse['breite'] * 100:.2f}%"
                    f" / {masse['ecke'] / masse['hoehe'] * 100:.2f}%"
                ),
                "kalt": masse["kalt"],
                "heiss": masse["heiss"],
                # Ohne Messwerte trägt die Fläche denselben Verlauf, den die
                # Zeichnung sonst selbst gemalt hätte.
                "grund": masse["grund"],
                "titel": modul["titel"],
            }
        )

    for platz, modul in enumerate(module):
        if modul["art"] != "puffer":
            continue
        mitte = RAND + platz * MODUL_BREITE + MODUL_BREITE // 2
        oben = next(
            (w["entity_id"] for w in modul["werte"] if w.get("beschriftung") == "oben"),
            None,
        )
        speicher.append(
            {
                # „lädt" heißt: Die Ladepumpe fördert **und** der Kessel ist
                # wärmer als der obere Pufferbereich. Die Pumpe allein genügt
                # nicht – sie läuft auch, wenn der Kessel gerade direkt in
                # einen Heizkreis fährt und dem Puffer nichts zugeht.
                #
                # „entlädt": Ein Verbraucher zieht, ohne dass geladen wird.
                # Läuft beides, bleibt es bei „lädt"; welche Richtung netto
                # überwiegt, hängt vom Massenstrom ab, und den misst die
                # Anlage nicht.
                "laden": modul.get("pumpe"),
                "kessel": kessel_ist,
                "oben": oben,
                "hysterese": LADE_HYSTERESE,
                "entnahme": entnahme,
                "left": f"{mitte / breite * 100:.2f}%",
                "top": f"{SPEICHER_Y / HOEHE * 100:.2f}%",
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
        "image": _datenadresse(farben_umstellen(svg, THEMA_HELL)),
        "dark_mode_image": _datenadresse(svg),
        # Die `picture-elements`-Karte kennt nur hell und dunkel. Wer mehr
        # Farbsätze braucht, stellt die Zeichnung selbst um.
        "svg": svg,
        "elements": elemente,
        "leitungen": leitungen,
        # Die Pumpen liegen nicht im Bild: Ein Standbild kann sich nicht
        # drehen. Sie werden als eigene Marken darübergelegt.
        "pumpen": pumpen,
        # Ebenso das Glutbett der Wärmeerzeuger und die Mischerstellung.
        "brenner": brenner,
        "mischer": mischer,
        # Der Heizkörper, eingefärbt nach seiner Vorlauftemperatur.
        "heizkoerper": heizkoerper,
        # Die Schichtung des Puffers aus seinen beiden Fühlern.
        "schichtung": schichtung,
        # Ob der Puffer gerade beladen oder entleert wird.
        "speicher": speicher,
        # Die Lampen des Pumpen-/Relaismoduls, siehe ZSP_KLEMMEN.
        "lampen": lampen,
    }


def schaubild_daten(
    anlagen: list[dict[str, Any]],
    auswahl: dict[str, list[str]] | None = None,
    teile_aus: list[str] | tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Schaubild je Anlage, wie die Lovelace-Karte es bekommt.

    Die Kennung entscheidet, welche Anlage eine Karte zeigt – nicht die Reihenfolge.
    """
    return [
        {
            "id": anlage.get("id") or anlage["name"],
            "name": anlage["name"],
            **schaubild_nutzdaten(anlage, auswahl, teile_aus),
        }
        for anlage in anlagen
    ]


def schaubild_nutzdaten(
    anlage: dict[str, Any],
    auswahl: dict[str, list[str]] | None = None,
    teile_aus: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    """Die Schaubild-Felder einer Anlage – Bilder, Lagen, Bewegung.

    Oberfläche und Karte lesen dieselben Felder; zwei Aufbauwege wären zwei Quellen.
    """
    bild = anlagenschema(
        anlage["teile"],
        anlage.get("kesselart"),
        anlage.get("kesselwert"),
        auswahl,
        teile_aus,
    )
    return {
        # Die Zeichnung geht **einmal** hinaus, dazu die Farbtabellen. Welcher
        # Satz gilt, weiß erst der Browser; er tauscht die Werte selbst.
        "schema_svg": bild["svg"] if bild else None,
        # Was sich einstellen lässt: je Anlagenteil die Werte dieser Anlage.
        "schema_teile": waehlbare_werte(anlage["teile"], anlage.get("kesselwert")),
        # Die Grundfarben für die Überlagerungen – Mischer, Heizkörper,
        # Schichtung. Sie liegen über dem Bild und erben dessen Farben nicht.
        "schema_grundfarben": {
            rolle: FARBEN[rolle] for rolle in ("vorlauf", "ruecklauf", "warm", "kalt")
        },
        # Je Thema eine eigene Kopie: Eine flache reichte die Tabellen selbst
        # heraus, und wer sie änderte, änderte den Modulzustand mit.
        "schema_farben": (
            {thema: dict(werte) for thema, werte in FARBABBILDUNGEN.items()} if bild else {}
        ),
        "schema_werte": (
            [
                {
                    "entity": el["entity"],
                    "left": el["style"]["left"],
                    "top": el["style"]["top"],
                }
                for el in bild["elements"]
            ]
            if bild
            else []
        ),
        "schema_pumpen": bild.get("pumpen", []) if bild else [],
        # Bewegung im Schaubild: die Leitungen strömen, solange eine Pumpe
        # läuft, das Glutbett glimmt, solange der Kessel Leistung bringt.
        "schema_leitungen": bild.get("leitungen") if bild else None,
        "schema_brenner": bild.get("brenner", []) if bild else [],
        "schema_anforderung": bild.get("anforderung", []) if bild else [],
        "schema_mischer": bild.get("mischer", []) if bild else [],
        # Der Heizkörper färbt sich nach seiner Vorlauftemperatur.
        "schema_heizkoerper": bild.get("heizkoerper", []) if bild else [],
        # Die Schichtung des Puffers – oben und unten je nach Messwert.
        "schema_schichtung": bild.get("schichtung", []) if bild else [],
        "schema_lampen": bild.get("lampen", []) if bild else [],
        "schema_speicher": bild.get("speicher", []) if bild else [],
    }
