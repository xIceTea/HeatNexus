"""Welche Datenpunkte das Dashboard wo zeigt – Namensmuster und kanonische Schlüssel.

Je Ansicht eine Tabelle: Vorrang in der Übersicht, Rundinstrumente, Wartung,
Zustand, Verlauf, und die Rückfrage vor einer Taste.
"""

from __future__ import annotations

import re

from .. import geraete

# Fachliche Reihenfolge der Anlagenteile: Alphabetisch stünde der Puffer vor
# dem Kessel. Den Rang trägt jede Baureihe in ihrem Modul unter `geraete/`,
# Typen ohne Eintrag landen hinten.
FCT_RANG: dict[int, int] = geraete.RANG


RANG_UNBEKANNT = 80


def namensmuster(*ausdruecke: str) -> tuple[re.Pattern, ...]:
    """Namensausdrücke als Muster, Groß- und Kleinschreibung gleich."""
    return tuple(re.compile(a, re.IGNORECASE) for a in ausdruecke)


# Werte, die in der Übersicht zuerst stehen sollen.
# Je Zeile: Muster und die kanonischen Schlüssel, die dasselbe meinen.
UEBERSICHT_VORRANG: tuple[tuple[re.Pattern, tuple[str, ...]], ...] = (
    (re.compile(r"betriebsphase", re.IGNORECASE), ("operating_phase",)),
    (re.compile(r"betriebsart", re.IGNORECASE), ("operating_mode",)),
    (re.compile(r"betriebswahl", re.IGNORECASE), ("mode_selection",)),
    (re.compile(r"kesseltemperatur ist", re.IGNORECASE), ("boiler_temperature",)),
    (re.compile(r"kesselleistung", re.IGNORECASE), ("boiler_power",)),
    (re.compile(r"aktueller brennstoff", re.IGNORECASE), ("fuel_current",)),
    (re.compile(r"vorratsbeh", re.IGNORECASE), ("fuel_storage_status",)),
    (re.compile(r"puffer oben", re.IGNORECASE), ("buffer_top",)),
    (re.compile(r"puffer unten", re.IGNORECASE), ("buffer_bottom",)),
    (re.compile(r"au(ß|ss)entemperatur", re.IGNORECASE), ("outdoor_temperature",)),
    (re.compile(r"raumtemperatur ist", re.IGNORECASE), ("room_temperature",)),
    (re.compile(r"raumtemperatur soll", re.IGNORECASE), ("room_temperature_target",)),
    (re.compile(r"vorlauftemperatur ist", re.IGNORECASE), ("flow_temperature",)),
    (re.compile(r"warmwasser", re.IGNORECASE), ("dhw_temperature",)),
    (re.compile(r"heizkreispumpe", re.IGNORECASE), ("circuit_pump",)),
    (re.compile(r"pumpe", re.IGNORECASE), ()),
    (re.compile(r"temperatur ist", re.IGNORECASE), ()),
)


# Wartungsansicht: Restlaufzeiten, Zähler, Brennstoff.
#
# Zu jeder Musterliste gehört eine Liste kanonischer Schlüssel. Sie steht
# daneben statt darin, weil die Muster hier als Liste ausgewertet werden und
# nicht Zeile für Zeile: Getroffen wird, was **eines** von beiden erfüllt.
WARTUNG_RESTLAUFZEIT = namensmuster(r"laufzeit bis")


WARTUNG_RESTLAUFZEIT_SCHLUESSEL = (
    "maintenance_ash_hours",
    "maintenance_cleaning_hours",
    "maintenance_main_cleaning_hours",
    "maintenance_service_hours",
)


WARTUNG_WEITERE = namensmuster(
    r"vorratsbeh",
    r"aktueller brennstoff",
    r"gew(ä|ae)hlter brennstoff",
    r"reinigung best",
    r"betriebsstunden",
    r"brennerstarts",
    r"serviceausbrand",
)


WARTUNG_WEITERE_SCHLUESSEL = (
    "fuel_storage_status",
    "fuel_current",
    "fuel_selected",
    "cleaning_confirm",
    "operating_hours",
    "burner_starts",
)


# Schaubild-Ansicht: der Zustand der Anlage in Kurzform.
ZUSTAND = namensmuster(
    r"betriebsphase",
    r"meldung klartext",
    r"au(ß|ss)entemperatur",
    r"kesselleistung",
    r"aktueller brennstoff",
    r"vorratsbeh",
)


# „Meldung Klartext" hat keine Adresse: Der Text entsteht aus `FE01msg` und
# steht in keiner Datenpunkttabelle. Dort bleibt es beim Namen.
ZUSTAND_SCHLUESSEL = (
    "operating_phase",
    "outdoor_temperature",
    "boiler_power",
    "fuel_current",
    "fuel_storage_status",
)


# Auswertung: was in einen Verlauf gehört.
VERLAUF = namensmuster(
    r"kesseltemperatur",
    r"abgastemperatur",
    r"puffer oben",
    r"puffer unten",
    r"vorlauftemperatur",
    r"raumtemperatur",
    r"au(ß|ss)entemperatur",
    r"kesselleistung",
    r"r(ü|ue)cklauf temperatur",
)


VERLAUF_SCHLUESSEL = (
    "boiler_temperature",
    "flue_gas_temperature",
    "buffer_top",
    "buffer_bottom",
    "flow_temperature",
    "room_temperature",
    "outdoor_temperature",
    "boiler_power",
    "return_temperature",
)


# Zeitprogramm eines Kreises.
# **Nicht einfach „programm".** Der Heizkreis führt unter `4/60` ein
# Estrich-Ausheizprogramm, das schlicht „Programm" heißt (beenden,
# Belegreifheizen, Funktionsheizen). Es ist kein Zeitprogramm, hat keine
# Schaltzeiten und gehört weder in die Steuerungsübersicht noch in den Reiter
# Zeitprogramme. Mit dem bloßen Teilwort stand es dort – und verdrängte als
# erster Treffer die echten Programme, sobald jemand den Datenpunkt einschaltete.
ZEITPROGRAMM = namensmuster(
    r"programm\s*\d",
    r"zeitprogramm",
    r"\bww[- ]programm",
    r"zirkulations?programm",
)


# Tasten, die in der Übersicht je Anlage stehen: alltäglich, ohne Rückfrage.
UEBERSICHT_TASTEN = namensmuster(r"ww einmalladung", r"werte jetzt abfragen")


# Plattformen, die der Nutzer bedient statt nur abliest.
BEDIENBAR = frozenset({"climate", "select", "number", "switch", "button", "time", "date"})


# Eingriffe, bei denen vor dem Auslösen nachgefragt wird. Gefragt wird nur dort,
# wo ein Fehlgriff Arbeit macht, Brennstoff kostet oder die Anlage tagelang
# anders fährt – nicht aus Prinzip: Eine Rückfrage, die immer kommt, klickt man
# irgendwann blind weg.
RUECKFRAGE: tuple[tuple[re.Pattern, str], ...] = (
    (
        re.compile(r"^kessel$", re.IGNORECASE),
        "Damit wird der Kessel ein- bzw. ausgeschaltet. Ausgeschaltet heizt er "
        "weder Heizkreise noch Warmwasser – nur der Frostschutz bleibt aktiv.",
    ),
    (
        re.compile(r"serviceausbrand", re.IGNORECASE),
        "Der Kessel brennt den restlichen Brennstoff aus und geht danach in den "
        "Stillstand. Das dauert und verbraucht Brennstoff. Wirklich auslösen?",
    ),
    (
        re.compile(r"reinigung best", re.IGNORECASE),
        "Damit meldest du der Anlage, dass die Reinigung erledigt ist: Die "
        "Wartungszähler beginnen von vorn. Wirklich bestätigen?",
    ),
    # Die einzelnen Bestätigungstasten fragen jede für sich nach – sie setzen
    # je einen Wartungszähler zurück, und ein Fehlgriff fällt erst auf, wenn
    # die Anlage Monate später zu spät warnt.
    (
        re.compile(r"hauptreinigung und aschetonnen durchgef", re.IGNORECASE),
        "Wurde die Hauptreinigung durchgeführt und wurden die Aschetonnen "
        "entleert? Die Anlage setzt beide Zähler zurück.",
    ),
    (
        re.compile(r"hauptreinigung durchgef", re.IGNORECASE),
        "Wurde die Hauptreinigung durchgeführt? Die Anlage setzt den Zähler "
        "für die Hauptreinigung zurück.",
    ),
    (
        re.compile(r"^reinigung durchgef", re.IGNORECASE),
        "Wurde die Reinigung durchgeführt? Die Anlage setzt den Reinigungszähler zurück.",
    ),
    (
        re.compile(r"wartung durchgef", re.IGNORECASE),
        "Wurde die Wartung durchgeführt? Die Anlage setzt den Zähler für die Wartung zurück.",
    ),
    (
        re.compile(r"gew(ä|ae)hlter brennstoff", re.IGNORECASE),
        "Die Verbrennungsregelung stellt sich auf den gewählten Brennstoff ein. "
        "Passt die Angabe nicht zum tatsächlichen Vorrat, läuft der Kessel "
        "schlechter. Die Änderung wirkt erst, nachdem der Kessel am "
        "Hauptschalter aus- und wieder eingeschaltet wurde. Wirklich umstellen?",
    ),
    (
        re.compile(r"estrich", re.IGNORECASE),
        "Das Estrichprogramm fährt ein festes Temperaturprofil über Tage und "
        "lässt sich nicht einfach abbrechen. Wirklich starten?",
    ),
    (
        re.compile(r"legionellen", re.IGNORECASE),
        "Die Legionellenschaltung heizt den Speicher auf hohe Temperatur. Wirklich auslösen?",
    ),
    (
        re.compile(r"kaminkehrerbetrieb", re.IGNORECASE),
        "Der Kessel fährt auf die eingestellte Kaminkehrer-Leistung und hält "
        "sie für die Abgasmessung. Ausschalten stellt die Betriebswahl zurück "
        "auf EIN; nach 60 Minuten endet die Messung von selbst.",
    ),
    (
        re.compile(r"lagerraumbef(ü|ue)llung anfordern|lagerraum bef(ü|ue)llen", re.IGNORECASE),
        "Soll die Lagerraumbefüllung jetzt durchgeführt werden? Die Anlage "
        "gibt sie nur frei, wenn ihr Zustand das zulässt – ob sie freigegeben "
        "ist und wie lange noch, steht danach unter „Lagerraum befüllen”.",
    ),
)


def rueckfrage(name: str) -> str:
    """Rückfragetext für einen Datenpunkt – leer heißt: ohne Nachfrage."""
    for muster, text in RUECKFRAGE:
        if muster.search(name):
            return text
    return ""


# Zustände, mit denen sich keine Karte lohnt.
OHNE_WERT = frozenset({"unavailable", "unknown", "none", ""})


# Höchstzahl der Linien in einem Verlaufsdiagramm.
VERLAUF_MAX = 6
