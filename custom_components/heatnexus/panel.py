"""Eigene Oberfläche für die Heizung.

Meldet einen eigenen Eintrag in der Seitenleiste an, hinter dem eine
Anlagenübersicht steht: Kennwerte, Schaubild, Heizkreise, Warmwasser,
Störungen, Verlauf und Schnellzugriff – in einer Anordnung, die sich mit
Lovelace-Karten nicht bauen lässt.

**Die Aufteilung entsteht hier, nicht im Browser.** Python sucht die
Entitäten zusammen und legt sie als fertige Struktur ab; die Datei im Browser
stellt sie nur dar und holt sich die aktuellen Werte aus ``hass.states``.
Damit bleibt die gesamte Gerätekenntnis an einer Stelle, und im Browser liegt
nichts, was bei einer neuen Anlage angepasst werden müsste.

Die Struktur wird **beim Öffnen** über ``heatnexus/panel_daten`` geholt, nicht
nur beim Einrichten mitgegeben. Beim Einrichten ist die Anlage erst zur Hälfte
eingelesen: Der Vollabzug läuft im Hintergrund weiter, und die Werte der
zuerst angelegten Entitäten stehen teils noch aus. Eine damals berechnete
Aufteilung bliebe für immer halb leer – genau daran fehlten Kennwerte,
Systemstatus, Warmwasser, Schaubild und Verlauf. Die Konfiguration des Panels
enthält weiterhin einen Stand, damit die Ansicht sofort etwas zeigt.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
import re
from typing import Any

from homeassistant.components import frontend, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback
import voluptuous as vol

from .anordnung import async_register_anordnung
from .const import (
    COMFORT_TEMP_STANDARD,
    CONF_AUSSENTEMPERATUR,
    CONF_COMFORT_DAUER,
    CONF_COMFORT_TEMP,
    CONF_ECO_DAUER,
    CONF_ECO_TEMP,
    CONF_HILFE,
    DOMAIN,
    ECO_TEMP_STANDARD,
    PANEL_TITEL,
    PANEL_URL,
    UEBERSTEUERUNG_DAUER_STANDARD,
    panel_element,
    panel_js_pfad,
)
from .dashboard import (
    WARTUNG_RESTLAUFZEIT,
    WARTUNG_WEITERE,
    _anlagen,
    _muster,
    _passt,
    rueckfrage,
)
from .schema import anlagenschema

_LOGGER = logging.getLogger(__name__)

_JS_DATEI = Path(__file__).parent / "frontend" / "heatnexus-panel.js"

# Der wichtigste Wert eines Anlagenteils, für die Liste links.
#
# Die Anlage selbst zeigt je Funktion **einen** Leitwert: am Kessel die
# Kesseltemperatur, am Heizkreis die Raumtemperatur, am Puffer die obere
# Temperatur. Ohne diese Trennung gewann bisher die Kesseltemperatur auch am
# Heizkreis – der meldet sie nämlich ebenfalls.
KENNWERT_JE_FCT: dict[int, tuple[tuple[str, str, str], ...]] = {
    14: (  # Heizkreis
        (r"raumtemperatur ist", "Raumtemperatur", "mdi:home-thermometer"),
        (r"vorlauftemperatur ist", "Vorlauf", "mdi:radiator"),
    ),
    16: (  # Puffer
        (r"puffer oben", "Puffer oben", "mdi:storage-tank"),
        (r"^temperatur ist$", "Temperatur", "mdi:thermometer"),
    ),
    20: (  # ZSP Pumpen-/Relaismodul
        (r"^kesseltemperatur$|^temperatur ist$", "Temperatur", "mdi:thermometer"),
        (r"r(ü|ue)cklauf temperatur", "Rücklauf", "mdi:pipe"),
    ),
    25: (  # Kessel
        (r"kesseltemperatur ist", "Kesseltemperatur", "mdi:fire"),
    ),
}

# Rückfall für Funktionstypen ohne eigene Liste.
KENNWERT = (
    (r"kesseltemperatur ist", "Kesseltemperatur", "mdi:fire"),
    (r"puffer oben", "Puffer oben", "mdi:storage-tank"),
    (r"warmwassertemperatur", "Warmwasser", "mdi:water-boiler"),
    (r"raumtemperatur ist", "Raumtemperatur", "mdi:home-thermometer"),
    (r"vorlauftemperatur ist", "Vorlauf", "mdi:radiator"),
    (r"^temperatur ist$", "Temperatur", "mdi:thermometer"),
    (r"r(ü|ue)cklauf temperatur", "Rücklauf", "mdi:pipe"),
)

# Systemstatus rechts: Zeile für Zeile, in dieser Reihenfolge.
STATUS = (
    (r"betriebsphase", "Betriebszustand", "mdi:state-machine"),
    (r"au(ß|ss)entemperatur", "Außentemperatur", "mdi:thermometer"),
    (r"kesselleistung", "Kesselleistung", "mdi:fire"),
    (r"brennerkammertemperatur", "Brennkammertemperatur", "mdi:fireplace"),
    (r"abgastemperatur", "Abgastemperatur", "mdi:smoke"),
    (r"aktueller brennstoff", "Brennstoff", "mdi:sack"),
    (r"vorratsbeh", "Vorratsbehälter", "mdi:battery-70"),
    (r"brennerstarts", "Brennerstarts", "mdi:restart"),
    (r"betriebsstunden", "Betriebsstunden", "mdi:clock-outline"),
    (r"laufzeit bis ascheentleerung", "Bis Ascheentleerung", "mdi:delete-clock-outline"),
)

# Warmwasser hat keine eigene Funktion: Die Datenpunkte hängen am Heizkreis.
# Die Wortgrenze ist nötig – ohne sie zählte auch die Abgas-Re*zirkulation* des
# Kessels als Warmwasserwert.
WARMWASSER = _muster(
    r"\bwarmwasser",
    r"\bww[- ]",
    r"\bzirkulation",
)

# Ob überhaupt Warmwasser bereitet wird, verraten diese beiden: eine gemessene
# Warmwassertemperatur (0/4) oder der ausdrücklich gemeldete Kreis (5/76).
#
# Die Parameter allein beweisen nichts: „WW-Überhöhung", „WW-Ladepumpe" und
# „WW-Ladung max. Ladevorrang" stehen auch an einem Heizkreis ohne
# Warmwasserspeicher in der Liste. Genau daran zeigte die Oberfläche im
# Heizhaus eine Warmwasserkarte, die es dort nie gab.
# Kuratiert heißt der Datenpunkt „Warmwasser Ist-Temperatur", aus der
# Menü-Erkennung „WW-Temperatur Aktueller Wert" – beide Schreibweisen zählen.
WARMWASSER_IST = _muster(
    r"\bww[- ]temperatur",
    r"\bwarmwasser[- ]?(ist|soll)?[- ]?temperatur",
)
WARMWASSER_KREIS = _muster(r"\bww-kreis\b")

# Verlauf: Was standardmäßig als Linie erscheint. Der Nutzer kann in der
# Ansicht jede Linie ab- und weitere dazuwählen; das hier ist nur der Start.
VERLAUF = _muster(
    r"kesseltemperatur ist",
    r"abgastemperatur",
    r"brennerkammertemperatur",
    r"puffer oben",
    r"puffer unten",
    r"vorlauftemperatur ist",
    r"raumtemperatur ist",
    r"r(ü|ue)cklauf temperatur",
    r"au(ß|ss)entemperatur",
    r"kesselleistung",
)

# Wie viele Linien der Verlauf höchstens von allein anschaltet.
VERLAUF_MAX = 8

# Schnellzugriff: bedienbare Datenpunkte, die man wirklich anfasst.
# Ob vor dem Auslösen nachgefragt wird, entscheidet `dashboard.rueckfrage` –
# dieselbe Tabelle gilt für die Kacheln im Dashboard.
SCHNELLZUGRIFF = (
    (r"ww einmalladung", "Warmwasser laden", "mdi:water-boiler"),
    (r"^reinigung durchgef", "Reinigung erledigt", "mdi:broom"),
    (r"hauptreinigung durchgef(?!.*aschetonnen)", "Hauptreinigung erledigt", "mdi:broom"),
    (r"serviceausbrand", "Serviceausbrand", "mdi:fire-off"),
    (r"betriebswahl", "Betriebswahl", "mdi:tune"),
    (r"gew(ä|ae)hlter brennstoff", "Brennstoff wählen", "mdi:sack"),
)

# Höchstzahl der Warmwasserzeilen; mehr sprengt die Karte.
WARMWASSER_MAX = 6

# ---------------------------------------------------------------------------
# Reiter „Steuerung": die Anlage bedienen statt nur ablesen
# ---------------------------------------------------------------------------
# Betriebswahl eines Heizkreises bzw. des Kessels.
BETRIEBSWAHL = _muster(r"\bbetriebswahl\b")
# Zeitprogramm eines Kreises.
ZEITPROGRAMM = _muster(r"programm")
# Die Einmalladung: der einzige Warmwasser-Eingriff, den man täglich anfasst.
EINMALLADUNG = _muster(r"einmalladung")
# Die Anlage kennt zur Einmalladung zwei Einstellungen: auslösen und die
# Temperatur, auf die dabei geladen wird.
EINMALLADUNG_TEMPERATUR = _muster(r"einmalladung temperatur", r"ww-ladefreigabe temperatur")
WARMWASSER_SOLL = _muster(r"\bww[- ]temperatur sollwert", r"\bwarmwasser soll")
# Die ehrliche Rückmeldung der Einmalladung.
#
# Die Anlage trennt sauber zwischen dreierlei:
#   2/16 „Freigabe starten"  Nein/Ja – ein Auslöser, kein Zustand. Er fällt
#                            zurück, sobald der Auftrag angenommen ist.
#   3/50 „Betriebswahl"      die dauerhafte Wahl (Standby, Programm 1–3,
#                            Heizbetrieb, Absenkbetrieb, WW-Betrieb …).
#   2/9  „Betriebsart"       was die Anlage **gerade tut**. Dort stehen die
#                            vorübergehenden Zustände: „WW-Ladung",
#                            „Warmwasser Einmalladung", „Eco / Comfort",
#                            „Urlaubsprogramm", „Frostschutz".
#
# Eine Einmalladung überstimmt die Betriebswahl also nur vorübergehend; wer
# die Betriebswahl neu setzt, stellt den Grundzustand wieder her und bricht
# damit ab. Angezeigt wird deshalb die Betriebsart; die Ladepumpe ist nur der
# Rückfall für Anlagen, die keine Betriebsart melden.
BETRIEBSART = _muster(r"^betriebsart$")
WARMWASSER_LADEPUMPE = _muster(r"\bww-ladepumpe")

# Betriebsarten (2/9), die eine laufende Warmwasserladung bedeuten.
WARMWASSER_LAEDT = ("WW-Ladung", "Warmwasser Einmalladung", "Warmwasser Hygiene-Programm")

# Betriebswahl-Einträge (3/50), die bei der Warmwasserladung eine Rolle
# spielen. Es sind Muster, keine festen Namen: Welche Einträge eine Anlage
# anbietet, meldet sie selbst, und „Programm 1" heißt nicht überall gleich.
BETRIEBSWAHL_STANDBY = r"^standby$"
BETRIEBSWAHL_WW = r"^ww[- ]betrieb$|^warmwasserbetrieb$"
BETRIEBSWAHL_ZURUECK = r"^programm"

# Die Außentemperatur gehört an der Anlage in die Kopfzeile und nicht in eine
# Kachel – sie gilt für die ganze Anlage, nicht für einen Anlagenteil.
AUSSENTEMPERATUR = _muster(r"au(ß|ss)entemperatur")

# Lagerraumbefüllung. Die Anlage zeigt dazu eine eigene Seite mit
# Kesseltemperatur bzw. Vorratsbehälter-Status, Restlaufzeit, der Freigabe
# („freigegeben"/„gesperrt") und der Betriebsphase – in dieser Reihenfolge.
LAGERRAUM_ANFORDERN = _muster(r"lagerraumbef(ü|ue)llung anfordern")
LAGERRAUM_ZEILEN = (
    (r"kesseltemperatur ist", "Kesseltemperatur"),
    (r"vorratsbeh", "Vorratsbehälter"),
    (r"lagerraumbef(ü|ue)llung restlaufzeit", "Restlaufzeit"),
    (r"lagerraum bef(ü|ue)llen freigabe", "Lagerraum befüllen"),
    (r"betriebsphase", "Betriebsphase"),
)

# Bedienbares am Kessel, in dieser Reihenfolge.
KESSEL_BEDIENUNG = (
    (r"gew(ä|ae)hlter brennstoff", "Brennstoff", "mdi:sack"),
    (r"^reinigung durchgef", "Reinigung erledigt", "mdi:broom"),
    (r"hauptreinigung durchgef(?!.*aschetonnen)", "Hauptreinigung erledigt", "mdi:broom"),
    (
        r"hauptreinigung und aschetonnen durchgef",
        "Hauptreinigung + Aschetonnen",
        "mdi:delete-empty-outline",
    ),
    (r"wartung durchgef", "Wartung erledigt", "mdi:wrench-check-outline"),
    (r"serviceausbrand", "Serviceausbrand", "mdi:fire-off"),
)

# ---------------------------------------------------------------------------
# Reiter „Wartung"
# ---------------------------------------------------------------------------
WARTUNG_BRENNSTOFF = _muster(r"vorratsbeh", r"aktueller brennstoff", r"brennstoff")


# ---------------------------------------------------------------------------
# Erklärungen („?")
#
# Was ein Wert bedeutet und was eine Bedienung auslöst, steht in den
# Anleitungen der Anlage – nur hat die beim Heizen niemand zur Hand. Die Texte
# hier sind eigene, knappe Zusammenfassungen dessen, was dort erklärt wird;
# übernommen wird kein Wortlaut.
# ---------------------------------------------------------------------------
HILFE: tuple[tuple[str, str], ...] = (
    (
        r"gew(ä|ae)hlter brennstoff|^brennstoff$",
        "Womit der Kessel rechnet. Die Anlage kennt vier Einstellungen:\n\n• Hackgut normal — Wassergehalt 15 bis 30 %, Aschegehalt bis 1,5 %\n• Hackgut feucht — über 30 %, höchstens 35 % Wassergehalt\n• Hackgut normal schlackend — 15 bis 30 % Wasser, Aschegehalt über 1,5 bis etwa 3 %\n• Hackgut feucht schlackend — über 30 % Wasser, Aschegehalt über 1,5 bis etwa 3 %\n\n„Schlackend“ erkennt man an festen Klumpen in der Asche; die Anlage verlängert dann die Entaschungsintervalle. Bei unter 25 % Wassergehalt rät der Hersteller von „feucht“ ab. Nach einem Brennstoffwechsel lohnt ein Blick in die Asche: zu viele Holzkohlereste sprechen wieder für „normal“ oder „feucht“.\n\nDie Umstellung wirkt erst, nachdem der Kessel am Hauptschalter aus- und wieder eingeschaltet wurde.",
    ),
    (
        r"serviceausbrand",
        "Brennt den Kessel gezielt aus, bis weder Glut noch unverbrannter Brennstoff im Brenner liegt — danach ist er zur Reinigung bereit. Vor Reinigungs-, Wartungs- und Servicearbeiten schaltet man den Kessel so ab. Der Vorgang dauert und lässt sich nicht abbrechen.",
    ),
    (
        r"lagerraum|bef(ü|ue)llung anfordern",
        "Nimmt Kessel und Rührwerk in Betrieb, damit sich das Rührwerk beim Befüllen dreht.\n\nOhne drehendes Rührwerk darf der Lagerraum nur bis etwa einen Meter Schütthöhe befüllt werden — darüber kann das Rührwerk Schaden nehmen, und dafür besteht keine Garantie. Erst wenn hier „freigegeben“ steht, darf weiter eingeblasen werden.\n\nBei pneumatischer Zuführung wird erst freigegeben, wenn der Vorratsbehälter leer ist; er muss also zuerst leergefahren werden.",
    ),
    (
        r"durchgef(ü|ue)hrt|reinigung best|erledigt|aschetonnen",
        "Meldet der Anlage, dass die Arbeit erledigt ist, und setzt die zugehörige Reinigungsaufforderung zurück. Jede Taste betrifft nur ihren eigenen Zähler.\n\nVor Reinigungsarbeiten den Kessel über den Serviceausbrand ausschalten. Nur bestätigen, wenn wirklich gereinigt wurde — sonst meldet sich die Anlage beim nächsten Mal zu spät.",
    ),
    (
        r"einmalladung|ww[- ]ladung",
        "Lädt den Warmwasserspeicher einmalig auf, auch während einer Sperrzeit des Warmwasserprogramms.\n\nDie Anlage startet nur, wenn die Warmwassertemperatur mindestens 5 K unter dem eingestellten Wert liegt. Die eingestellte Temperatur ist der Ausschaltpunkt.",
    ),
    (
        r"betriebswahl",
        "Wie der Heizkreis gefahren wird:\n\n• Standby — Heizung aus, nur Frostschutz\n• Programm 1 bis 3 — Betrieb nach dem jeweiligen Zeitprogramm\n• Heizbetrieb — dauerhaft auf dem Sollwert Heizbetrieb\n• Absenkbetrieb — dauerhaft auf dem Absenk-Sollwert\n• Handbetrieb — Regelung von Hand\n\nAm Kessel bedeutet die Betriebswahl etwas anderes: dort schaltet sie zwischen Aus, Ein und den Sonderbetriebsarten um.",
    ),
    (
        r"^kessel$",
        "Schaltet den Kessel ein oder aus. Ausgeschaltet versorgt er weder Heizkreise noch Warmwasser; der Frostschutz bleibt aktiv.",
    ),
    (
        r"^kesseltemperatur$",
        "Der eigene Fühlereingang des Pumpen-/Relaismoduls — nicht der Kessel im Heizhaus.\n\nDas Modul misst hier die Temperatur der Leitung, an der es sitzt, und regelt danach: Kommt an seinem Eingang eine externe Wärmeanforderung an, fordert es Wärme an, bis dieser Wert die eingestellte Solltemperatur erreicht.\n\nWas der Fühler physisch misst, legt die Verdrahtung fest; die Anlage kann es nicht melden. Welche Aufgabe das Modul hat — Pumpensteuerung, externe Wärmeanforderung oder Sammelstörmeldung — steht in den Datenpunkten der Gruppe 29 auf der Serviceebene.",
    ),
    (
        r"stellwert|^mischer$",
        "Wie weit der Mischer geöffnet ist. 0 % heißt: Es wird nur Rücklauf umgewälzt, der Kreis bekommt keine Wärme vom Kessel. 100 % heißt: voller Durchgang.\n\nDazwischen mischt das Ventil kühleren Rücklauf in den Vorlauf, bis die Vorlauftemperatur zur Heizkurve passt. Im Schaubild schwenkt der Zeiger im Ventil entsprechend, und das Stück Leitung darüber färbt sich von Blau nach Rot.",
    ),
    (
        r"vorratsbeh",
        "Der Zwischenbehälter am Kessel, nicht der Lagerraum. Meldet die Anlage „Brennstoff nachfüllen“, heizt sie weiter, bis der Rest verbraucht ist; bei „Vorratsbehälter leer“ sperrt sie den Brenner.",
    ),
    (
        r"betriebsphase|betriebszustand",
        "Was der Kessel gerade tut — von Standby über Vorspülen, Zündphase und Stabilisierung bis Modulation und Ausbrand.",
    ),
    (
        r"laufzeit bis",
        "Verbleibende Betriebsstunden bis zur nächsten Arbeit. Läuft der Wert ab, fordert die Anlage sie an; bestätigt wird sie mit der zugehörigen Taste im Reiter Steuerung.",
    ),
    (
        r"restlaufzeit",
        "Wie lange die aktuelle Freigabe noch gilt. Danach stellt die Anlage von selbst zurück.",
    ),
    (
        r"behaglichkeit",
        "Verschiebt alle Raumtemperatur-Sollwerte dieses Heizkreises — Zeitprogramme, Heiz- und Absenkbetrieb — um denselben Betrag, ohne die Grundeinstellungen zu ändern. Bereich −3,0 bis +3,0 K.",
    ),
    (
        r"^sollwert$|raumtemperatur",
        "Ein hier gesetzter Wert gilt befristet und stellt danach von selbst auf die Betriebswahl zurück; die Zeitprogramme bleiben unverändert. Die Anlage nennt das „Eco / Comfort“ — gedacht zum Absenken beim Lüften oder zum Aufheizen für ein paar Stunden. Dauer 0 bis 400 Minuten, Temperatur 6 bis 30 °C.",
    ),
    (
        r"zeitprogramm|^programm [0-9]",
        "Wochenprogramm von Montag bis Sonntag. Tage lassen sich einzeln verwenden oder zu Blöcken zusammenfassen; je Tag oder Block sind bis zu sechs Schaltzeiten mit je einem Temperaturwert möglich.",
    ),
    (
        r"au(ß|ss)entemperatur",
        "Grundlage der Heizkurve: Die Anlage errechnet daraus die Vorlauftemperatur. Welcher Sensor hier gilt, lässt sich unter Konfigurieren → Allgemein festlegen.",
    ),
)

# Erklärungen für ganze Karten der Oberfläche.
HILFE_KARTEN = {
    "Anlagenübersicht": (
        "Der hydraulische Aufbau, gezeichnet aus dem, was die Anlage meldet. "
        "Rot ist der Vorlauf, blau der Rücklauf; eine Pumpe dreht sich, "
        "solange sie läuft."
    ),
    "Systemstatus": (
        "Die Werte, die den Zustand der ganzen Anlage beschreiben – der "
        "Infoebene des Bediengeräts nachempfunden."
    ),
    "Heizkreise": (
        "Je Kreis die gemessene Raumtemperatur, die aktuelle Betriebsart und "
        "der Sollwert. Ein am Thermostat gesetzter Wert gilt befristet und "
        "stellt danach von selbst zurück; die Zeitprogramme bleiben unberührt."
    ),
    "Warmwasser": (
        "Die eingestellte Warmwassertemperatur ist der Ausschaltpunkt – "
        "geladen wird, sobald die Temperatur etwa 5 K darunter fällt."
    ),
    "Lagerraum befüllen": (
        "Erst anfordern, dann warten, bis „freigegeben“ dasteht. Vorher darf "
        "nur bis etwa einen Meter Schütthöhe befüllt werden, sonst kann das "
        "Rührwerk Schaden nehmen."
    ),
    "Störungen": (
        "Meldungen der Anlage im Klartext. Fehler und Alarme müssen am "
        "Bediengerät zurückgesetzt werden, bevor die Anlage weiterläuft."
    ),
    "Schnellzugriff": "Die Bedienungen, die man im Alltag wirklich anfasst.",
    "Kessel": (
        "Die Eingriffe am Kessel. Die Bestätigungstasten setzen jeweils nur "
        "den Zähler zurück, um den es geht – bitte erst drücken, wenn die "
        "Arbeit erledigt ist."
    ),
    "Wartung": (
        "Restlaufzeiten bis zur nächsten Arbeit, Brennstoff und Zählerstände. "
        "Erreicht eine Restlaufzeit null, fordert die Anlage die Arbeit an."
    ),
    "Restlaufzeiten": (
        "Verbleibende Betriebsstunden bis Ascheentleerung, Hauptreinigung und "
        "Wartung. Erledigt wird die Arbeit am Kessel, bestätigt im Reiter "
        "Steuerung."
    ),
    "Brennstoff": (
        "Was gerade verheizt wird und wie voll der Vorratsbehälter ist – nicht "
        "der Lagerraum, sondern der Zwischenbehälter am Kessel."
    ),
    "Zählerstände": (
        "Werte, die nur nach oben laufen. Home Assistant führt daraus eine "
        "Langzeitstatistik; im Reiter Verlauf lässt sich der Zuwachs ablesen."
    ),
    "Verlauf (24 Stunden)": (
        "Jede Linie lässt sich an- und abschalten. Vorausgewählt sind die "
        "Temperaturen der Anlage, die Außentemperatur und die Kesselleistung."
    ),
    "Verlauf (48 Stunden)": (
        "Jede Linie lässt sich an- und abschalten. Vorausgewählt sind die "
        "Temperaturen der Anlage, die Außentemperatur und die Kesselleistung."
    ),
}


def hilfe(name: str) -> str:
    """Erklärung zu einem Datenpunkt – leer, wenn es keine gibt."""
    for muster, text in HILFE:
        if re.search(muster, name or "", re.IGNORECASE):
            return text
    return ""


def _erster(entitaeten: list[dict[str, Any]], muster: str) -> dict[str, Any] | None:
    """Erste passende Entität; eine mit Wert hat Vorrang.

    Ein vorhandener Wert darf keine Bedingung sein: Beim ersten Aufbau ist die
    Anlage noch nicht fertig eingelesen. Was jetzt noch leer ist, bekommt
    trotzdem seine Zeile und füllt sich mit dem nächsten Abruf.
    """
    regex = re.compile(muster, re.IGNORECASE)
    treffer = [e for e in entitaeten if regex.search(e["name"])]
    if not treffer:
        return None
    return next((e for e in treffer if e.get("hat_wert")), treffer[0])


def _zeilen(
    entitaeten: list[dict[str, Any]], vorlage: tuple[tuple[str, str, str], ...]
) -> list[dict[str, str]]:
    """Aus einer Mustervorlage die vorhandenen Entitäten als Zeilen."""
    zeilen = []
    for muster, beschriftung, symbol in vorlage:
        if (treffer := _erster(entitaeten, muster)) is not None:
            zeilen.append(
                {
                    "entity": treffer["entity_id"],
                    "titel": beschriftung,
                    "symbol": symbol,
                }
            )
    return zeilen


def _bereitet_warmwasser(entitaeten: list[dict[str, Any]]) -> bool:
    """Prüfen, ob diese Anlage überhaupt Warmwasser bereitet.

    Zwei Belege lässt die Anlage zu: eine gemessene Warmwassertemperatur oder
    einen gemeldeten Warmwasserkreis ungleich null. Solange der Vollabzug noch
    läuft, hat der Istwert womöglich noch keinen Wert – vorhanden sein reicht
    deshalb, ein Wert ist nicht nötig.
    """
    for eintrag in entitaeten:
        if _passt(eintrag["name"], WARMWASSER_IST):
            return True
        if _passt(eintrag["name"], WARMWASSER_KREIS) and (eintrag.get("wert") or 0) != 0:
            return True
    return False


def _warmwasser(entitaeten: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Zeilen der Warmwasserkarte – leer, wo es kein Warmwasser gibt."""
    if not _bereitet_warmwasser(entitaeten):
        return []
    return [
        {"entity": e["entity_id"], "titel": e["name"]}
        for e in entitaeten
        if e["kategorie"] is None and e["bereich"] != "climate" and _passt(e["name"], WARMWASSER)
    ][:WARMWASSER_MAX]


def _kennung(entitaeten: list[dict[str, Any]], muster: tuple, bereiche: tuple = ()) -> str | None:
    """Entity-ID der ersten passenden Entität, optional auf Plattformen begrenzt."""
    for eintrag in entitaeten:
        if bereiche and eintrag["bereich"] not in bereiche:
            continue
        if _passt(eintrag["name"], muster):
            return eintrag["entity_id"]
    return None


def _steuerung(anlage: dict[str, Any]) -> dict[str, Any]:
    """Der Reiter „Steuerung": alles, was man an der Anlage wirklich verstellt.

    Vorbild ist die Bedienung der Anlage selbst – Heizkreis, Warmwasser,
    Kessel. Was nur abgelesen wird, gehört in die Übersicht.
    """
    alle = [e for teil in anlage["teile"] for e in teil["entitaeten"]]

    heizkreise = []
    for teil in anlage["teile"]:
        thermostat = next((e for e in teil["entitaeten"] if e["bereich"] == "climate"), None)
        if thermostat is None:
            continue
        heizkreise.append(
            {
                # Die Gerätekennung überlebt eine erneute Erkennung und ist
                # damit der einzige Anker, an dem eine selbst gewählte
                # Anordnung diese Karte wiedererkennt.
                "id": teil["id"],
                "entity": thermostat["entity_id"],
                "titel": teil["name"],
                "betriebswahl": _kennung(teil["entitaeten"], BETRIEBSWAHL, ("select",)),
                "betriebswahl_hilfe": hilfe("Betriebswahl"),
                "programm": _kennung(teil["entitaeten"], ZEITPROGRAMM, ("sensor",)),
                # Eco und Comfort schreiben dieselbe befristete Übersteuerung
                # wie das Bediengerät: Temperatur (3/4) und Dauer (2/10). Die
                # Anlage kennt nur einen Übersteuerungswert – ob er Eco oder
                # Comfort heißt, entscheidet sie daran, ob er unter oder über
                # dem Programmsollwert liegt.
                "uebersteuerung_temperatur": _kennung(
                    teil["entitaeten"], _muster(r"^temperatur$"), ("number",)
                ),
                "uebersteuerung_dauer": _kennung(
                    teil["entitaeten"], _muster(r"^dauer$"), ("number",)
                ),
                "vorlauf": (
                    v["entity_id"]
                    if (v := _erster(teil["entitaeten"], r"vorlauftemperatur ist"))
                    else None
                ),
            }
        )

    warmwasser = None
    if _bereitet_warmwasser(alle):
        ist = _erster(alle, r"\bww[- ]temperatur aktueller|\bwarmwasser ist")
        warmwasser = {
            "ist": ist["entity_id"] if ist else None,
            "soll": _kennung(alle, WARMWASSER_SOLL),
            "laden": _kennung(alle, EINMALLADUNG, ("switch", "button")),
            # Die Temperatur der Einmalladung ist an der Anlage Teil derselben
            # Bedienung; ohne sie lädt man auf einen Wert, den man nicht sieht.
            "laden_temperatur": _kennung(alle, EINMALLADUNG_TEMPERATUR, ("number",)),
            # Woran man sieht, dass wirklich geladen wird: Der Auslöser (2/16)
            # faellt zurueck, sobald die Anlage den Auftrag angenommen hat.
            # Die Ladepumpe laeuft dagegen, solange geladen wird.
            "laeuft": _kennung(alle, WARMWASSER_LADEPUMPE, ("binary_sensor",)),
            # Was die Anlage gerade tut – daran hängt die Rückmeldung.
            "betriebsart": _kennung(alle, BETRIEBSART, ("sensor",)),
            "laedt_wenn": list(WARMWASSER_LAEDT),
            # Über die Betriebswahl kommt man zurück in den Grundzustand; in
            # der Anlagen-App ist das der Weg, eine Ladung abzubrechen.
            "betriebswahl": _kennung(alle, BETRIEBSWAHL, ("select",)),
            "programm": _kennung(alle, _muster(r"ww[- ].*programm"), ("sensor",)),
        }

    kessel = []
    for teil in anlage["teile"]:
        for muster, beschriftung, symbol in KESSEL_BEDIENUNG:
            treffer = next(
                (
                    e
                    for e in teil["entitaeten"]
                    if e["bereich"] in ("switch", "button", "select")
                    and re.search(muster, e["name"], re.IGNORECASE)
                ),
                None,
            )
            if treffer is not None:
                kessel.append(
                    {
                        "entity": treffer["entity_id"],
                        "titel": beschriftung,
                        "symbol": symbol,
                        "frage": rueckfrage(treffer["name"]),
                        "hilfe": hilfe(treffer["name"]) or hilfe(beschriftung),
                    }
                )

    # Lagerraumbefüllung: anfordern und dann ablesen, ob freigegeben ist.
    # Ohne die Anforderungstaste hat die Karte keinen Zweck.
    lagerraum = None
    if (anfordern := _kennung(alle, LAGERRAUM_ANFORDERN, ("button",))) is not None:
        lagerraum = {
            "anfordern": anfordern,
            "frage": rueckfrage("Lagerraumbefüllung anfordern"),
            "hilfe": HILFE_KARTEN.get("Lagerraum befüllen", ""),
            "zeilen": [
                {"entity": treffer["entity_id"], "titel": beschriftung}
                for muster, beschriftung in LAGERRAUM_ZEILEN
                if (treffer := _erster(alle, muster)) is not None
            ],
        }

    return {
        "heizkreise": heizkreise,
        "warmwasser": warmwasser,
        "kessel": kessel,
        "lagerraum": lagerraum,
    }


def _wartung(anlage: dict[str, Any]) -> dict[str, Any]:
    """Der Reiter „Wartung": Restlaufzeiten, Brennstoff, Zählerstände."""
    alle = [e for teil in anlage["teile"] for e in teil["entitaeten"]]

    def zeilen(bedingung) -> list[dict[str, str]]:
        return [
            {"entity": e["entity_id"], "titel": e["name"]}
            for e in alle
            if e["kategorie"] is None and bedingung(e)
        ]

    return {
        "restlaufzeiten": zeilen(lambda e: _passt(e["name"], WARTUNG_RESTLAUFZEIT)),
        "brennstoff": zeilen(
            lambda e: (
                _passt(e["name"], WARTUNG_BRENNSTOFF)
                and not _passt(e["name"], WARTUNG_RESTLAUFZEIT)
            )
        ),
        # Zählerstände erkennt man an der Statistikklasse, nicht am Namen.
        "zaehler": zeilen(lambda e: e.get("state_class") == "total_increasing"),
        "weitere": zeilen(
            lambda e: (
                _passt(e["name"], WARTUNG_WEITERE)
                and not _passt(e["name"], WARTUNG_RESTLAUFZEIT)
                and not _passt(e["name"], WARTUNG_BRENNSTOFF)
                and e.get("state_class") != "total_increasing"
            )
        ),
    }


def _anlage_daten(anlage: dict[str, Any], aussen_gewaehlt: str | None = None) -> dict[str, Any]:
    """Alles, was die Oberfläche für eine Anlage braucht."""
    alle = [e for teil in anlage["teile"] for e in teil["entitaeten"]]

    kennwerte = []
    for teil in anlage["teile"]:
        vorlage = KENNWERT_JE_FCT.get(teil.get("fct_type")) or KENNWERT
        for muster, beschriftung, symbol in vorlage:
            if (treffer := _erster(teil["entitaeten"], muster)) is not None:
                kennwerte.append(
                    {
                        "entity": treffer["entity_id"],
                        "titel": teil["name"],
                        "untertitel": beschriftung,
                        "symbol": symbol,
                    }
                )
                break

    heizkreise = []
    for teil in anlage["teile"]:
        thermostat = next(
            (e for e in teil["entitaeten"] if e["bereich"] == "climate"),
            None,
        )
        if thermostat is None:
            continue
        heizkreise.append(
            {
                "entity": thermostat["entity_id"],
                "titel": teil["name"],
                "vorlauf": (
                    v["entity_id"]
                    if (v := _erster(teil["entitaeten"], r"vorlauftemperatur ist"))
                    else None
                ),
            }
        )

    warmwasser = _warmwasser(alle)

    stoerungen = [
        {"entity": e["entity_id"], "titel": e["name"]}
        for e in alle
        if e["kategorie"] == "diagnostic" and "klartext" in e["name"].lower()
    ]

    # Ohne Warmwasserbereitung hat auch die Taste „Warmwasser laden" nichts
    # verloren – der Datenpunkt existiert am Heizkreis trotzdem.
    hat_warmwasser = _bereitet_warmwasser(alle)
    schnellzugriff = []
    for teil in anlage["teile"]:
        for muster, beschriftung, symbol in SCHNELLZUGRIFF:
            if not hat_warmwasser and _passt(beschriftung, WARMWASSER):
                continue
            treffer = next(
                (
                    e
                    for e in teil["entitaeten"]
                    if e["bereich"] in ("switch", "button", "select")
                    and re.search(muster, e["name"], re.IGNORECASE)
                ),
                None,
            )
            if treffer is not None:
                eintrag = {
                    "entity": treffer["entity_id"],
                    "titel": beschriftung,
                    "symbol": symbol,
                    "frage": rueckfrage(treffer["name"]),
                    "hilfe": hilfe(treffer["name"]) or hilfe(beschriftung),
                }
                # Die Warmwasserladung meldet ihren Zustand nicht am Auslöser,
                # sondern in der Betriebsart. Ohne diesen Hinweis wirkt die
                # Taste, als hätte sie nichts bewirkt.
                if _passt(beschriftung, WARMWASSER):
                    eintrag["zustand_an"] = _kennung(alle, BETRIEBSART, ("sensor",))
                    eintrag["zustand_wenn"] = list(WARMWASSER_LAEDT)
                    # Zweiter Beleg für „lädt gerade": die Ladepumpe.
                    #
                    # Die Betriebsart allein genügt nicht. Sie meldet je nach
                    # Baureihe andere Worte, und an einem Kreis, der nur einen
                    # einzigen Wert kennt (`allowed: [0]`), meldet sie den
                    # Ladezustand überhaupt nicht. Dann blieb die Taste auf
                    # „Warmwasser laden" stehen und ein zweiter Druck löste
                    # eine weitere Ladung aus, statt abzubrechen.
                    eintrag["zustand_pumpe"] = _kennung(
                        alle, WARMWASSER_LADEPUMPE, ("binary_sensor",)
                    )
                    # Die Betriebswahl gehört zur Ladung dazu.
                    #
                    # Steht der Kreis auf Standby, ist er abgeschaltet und
                    # nimmt den Ladeauftrag gar nicht erst an – erst der
                    # WW-Betrieb macht ihn ausführbar. Und abbrechen lässt
                    # sich eine laufende Ladung nur über die Betriebswahl:
                    # Der Auslöser selbst fällt sofort zurück und hat danach
                    # keinen Zustand mehr, den man zurücknehmen könnte.
                    eintrag["betriebswahl"] = _kennung(
                        teil["entitaeten"], BETRIEBSWAHL, ("select",)
                    )
                    eintrag["betriebswahl_aus"] = BETRIEBSWAHL_STANDBY
                    eintrag["betriebswahl_ww"] = BETRIEBSWAHL_WW
                    eintrag["betriebswahl_zurueck"] = BETRIEBSWAHL_ZURUECK
                    eintrag["titel_abbrechen"] = "Warmwasser laden abbrechen"
                schnellzugriff.append(eintrag)

    bild = anlagenschema(anlage["teile"], anlage.get("kesselart"), anlage.get("kesselwert"))
    # **Jede Anlage behält ihren eigenen Messwert.** Die in den Optionen
    # gewählte Entität gilt nur für die Ansicht „Alle" – dort gibt es keine
    # einzelne Anlage, deren Fühler man nehmen könnte. Bis 1.2.0-beta.3
    # überschrieb die Auswahl jede Anlage, und das Heizhaus zeigte plötzlich
    # den Fühler des Wohnhauses.
    aussen = _kennung(alle, AUSSENTEMPERATUR) or aussen_gewaehlt
    return {
        # Die Anordnung der Karten wird je Anlage gespeichert. Ohne eigene
        # Kennung teilten sich Heizhaus und Wohnhaus eine Reihenfolge – wer
        # im Heizhaus etwas verschob, verschob es im Wohnhaus mit.
        "id": anlage.get("id") or anlage["name"],
        "name": anlage["name"],
        # Erklärungen je Karte – im Browser als „?" neben der Überschrift.
        "hilfe": dict(HILFE_KARTEN),
        # Die Außentemperatur gilt für die ganze Anlage und steht deshalb oben,
        # nicht in der Liste der Anlagenteile.
        "aussentemperatur": aussen,
        "steuerung": _steuerung(anlage),
        "wartung": _wartung(anlage),
        "kennwerte": kennwerte,
        "status": _zeilen(alle, STATUS),
        "heizkreise": heizkreise,
        "warmwasser": warmwasser,
        "stoerungen": stoerungen,
        "schnellzugriff": schnellzugriff[:6],
        "verlauf": [e["entity_id"] for e in alle if _passt(e["name"], VERLAUF)][:VERLAUF_MAX],
        # Alles, was sich sonst noch als Linie eignet – in der Ansicht
        # dazuwaehlbar.
        "verlauf_moeglich": [
            {"entity": e["entity_id"], "titel": e["name"]}
            for e in alle
            if e["kategorie"] is None and e["bereich"] == "sensor"
        ],
        "schema": bild["image"] if bild else None,
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
        "schema_speicher": bild.get("speicher", []) if bild else [],
    }


def _uebersteuerung(hass: HomeAssistant) -> dict[str, dict[str, float]]:
    """Die eingestellten Werte für Eco und Comfort.

    Sie gelten für alle Heizkreise: Die Anlage kennt je Kreis nur *einen*
    Übersteuerungswert, zwei getrennte Vorgaben je Kreis hätten dort nichts,
    worin sie stehen könnten.
    """
    optionen: dict[str, Any] = {}
    for eintrag in hass.config_entries.async_entries(DOMAIN):
        optionen = {**(eintrag.options or {}), **optionen}
    return {
        "eco": {
            "temperatur": float(optionen.get(CONF_ECO_TEMP, ECO_TEMP_STANDARD)),
            "dauer": float(optionen.get(CONF_ECO_DAUER, UEBERSTEUERUNG_DAUER_STANDARD)),
        },
        "comfort": {
            "temperatur": float(optionen.get(CONF_COMFORT_TEMP, COMFORT_TEMP_STANDARD)),
            "dauer": float(optionen.get(CONF_COMFORT_DAUER, UEBERSTEUERUNG_DAUER_STANDARD)),
        },
    }


def _gewaehlte_aussentemperatur(hass: HomeAssistant) -> str | None:
    """In den Optionen festgelegte Außentemperatur, falls vorhanden."""
    for eintrag in hass.config_entries.async_entries(DOMAIN):
        if gewaehlt := (eintrag.options or {}).get(CONF_AUSSENTEMPERATUR):
            return str(gewaehlt)
    return None


def _hilfe_gewuenscht(hass: HomeAssistant) -> bool:
    """Ob die Erklärungen angezeigt werden sollen (Standard: ja)."""
    for eintrag in hass.config_entries.async_entries(DOMAIN):
        if CONF_HILFE in (eintrag.options or {}):
            return bool(eintrag.options[CONF_HILFE])
    return True


def panel_daten(hass: HomeAssistant) -> dict[str, Any]:
    """Die vollständige Struktur für die Oberfläche."""
    aussen = _gewaehlte_aussentemperatur(hass)
    daten = {
        "anlagen": [_anlage_daten(anlage, aussen) for anlage in _anlagen(hass)],
        # Eco und Comfort gelten für alle Anlagen gemeinsam.
        "uebersteuerung": _uebersteuerung(hass),
        # Die Außentemperatur der Ansicht „Alle". Dort steht keine einzelne
        # Anlage im Vordergrund, also gilt die gewählte Entität – und nur dort.
        "aussentemperatur": aussen,
    }
    if not _hilfe_gewuenscht(hass):
        # Abgewählt: Die Texte gar nicht erst mitschicken.
        for anlage in daten["anlagen"]:
            anlage["hilfe"] = {}
            for bereich in ("schnellzugriff",):
                for eintrag in anlage.get(bereich) or []:
                    eintrag.pop("hilfe", None)
            steuerung = anlage.get("steuerung") or {}
            for eintrag in steuerung.get("kessel") or []:
                eintrag.pop("hilfe", None)
            for kreis in steuerung.get("heizkreise") or []:
                kreis.pop("betriebswahl_hilfe", None)
            if steuerung.get("lagerraum"):
                steuerung["lagerraum"].pop("hilfe", None)
    return daten


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/panel_daten"})
@callback
def _ws_panel_daten(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Die Aufteilung frisch berechnen, so wie sie gerade gilt."""
    connection.send_result(msg["id"], panel_daten(hass))


async def async_setup_panel(hass: HomeAssistant, version: str = "") -> None:
    """Die Oberfläche in der Seitenleiste anmelden.

    Fehler bleiben folgenlos – das Dashboard und die Entitäten funktionieren
    auch ohne sie.
    """
    try:
        await _async_setup_panel(hass, version)
    except Exception as err:
        _LOGGER.warning("Oberfläche konnte nicht angemeldet werden: %s", err)


async def _async_setup_panel(hass: HomeAssistant, version: str = "") -> None:
    """Eigentliche Anmeldung.

    Die Fassungsnummer steckt im *Pfad* der Oberflächendatei, nicht als
    Fragezeichen-Anhang dahinter. Home Assistant legt seine Oberfläche über
    einen Service-Worker im Browser ab, und der vergleicht Adressen ohne
    Suchteil – ein Anhang wie ``?v=1.1.0`` wird dabei schlicht übergangen und
    die alte Datei weiter ausgeliefert. Ein neuer Pfad ist für den
    Zwischenspeicher dagegen eine neue Datei; die Oberfläche erscheint nach
    einer Aktualisierung von selbst, ohne dass jemand neu laden muss.
    """
    pfad = panel_js_pfad(version)
    registriert: set[str] = hass.data.setdefault(f"{DOMAIN}_panel_dateien", set())
    if pfad not in registriert:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(pfad, str(_JS_DATEI), cache_headers=False)]
        )
        registriert.add(pfad)
    if not hass.data.get(f"{DOMAIN}_panel_datei"):
        websocket_api.async_register_command(hass, _ws_panel_daten)
        hass.data[f"{DOMAIN}_panel_datei"] = True
    # Die selbst gewählte Anordnung hängt am Panel, nicht an einer Anlage.
    async_register_anordnung(hass)

    daten = panel_daten(hass)
    if not daten["anlagen"]:
        return

    # update=True ersetzt eine bestehende Anmeldung – nötig, weil sich mit dem
    # Umfang auch die Aufteilung ändert.
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=PANEL_TITEL,
        sidebar_icon="mdi:radiator",
        frontend_url_path=PANEL_URL,
        config={
            "_panel_custom": {
                "name": panel_element(version),
                "module_url": pfad,
                "embed_iframe": False,
                "trust_external": False,
            },
            "daten": daten,
        },
        require_admin=False,
        update=True,
    )
    hass.data[f"{DOMAIN}_panel"] = True
    _LOGGER.info("Oberfläche %s in der Seitenleiste angemeldet", PANEL_TITEL)


async def async_remove_panel(hass: HomeAssistant) -> None:
    """Die Oberfläche wieder aus der Seitenleiste nehmen."""
    if not hass.data.pop(f"{DOMAIN}_panel", None):
        return
    with contextlib.suppress(Exception):
        frontend.async_remove_panel(hass, PANEL_URL)
    _LOGGER.info("Oberfläche %s entfernt", PANEL_TITEL)
