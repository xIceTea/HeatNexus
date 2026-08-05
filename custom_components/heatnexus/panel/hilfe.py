"""Die Erklärungen hinter dem Fragezeichen.

Was ein Wert bedeutet und was eine Bedienung auslöst, steht in den Anleitungen
der Anlage – nur hat die beim Heizen niemand zur Hand. Die Texte hier sind
eigene, knappe Zusammenfassungen dessen, was dort erklärt wird; übernommen
wird kein Wortlaut.

Sie stehen bewusst in einer eigenen Datei: Es ist der Teil, der am häufigsten
wächst, und er hat mit der Aufbereitung der Daten nichts zu tun.
"""

from __future__ import annotations

import re

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
