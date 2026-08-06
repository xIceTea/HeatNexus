"""Suchmuster und Tabellen der Oberfläche.

Hier steht, **woran** die Oberfläche einen Datenpunkt erkennt – nicht, was sie
daraus macht. Die Namen der Anlage sind nicht stabil genug für feste
Zeichenketten: Die kuratierte Tabelle nennt einen Wert anders als die
Geräte-Datenbank, und zwei Baureihen nennen ihn wieder anders. Deshalb Muster,
und deshalb an einer Stelle statt verstreut über die Aufbereitung.
"""

from __future__ import annotations

from ..dashboard import _muster
from ..schema import ANALOG_SOLLWERT

# Aufbau einer Zeile: **Muster, Beschriftung, Symbol, kanonische Schlüssel.**
#
# Der Schlüssel steht hinten, weil er der Zusatz ist und nicht die Regel: Es
# gibt ihn längst nicht für jeden Datenpunkt (`kanonisch.KANONISCH`), und wo er
# fehlt, bleibt das Muster die einzige Auskunft. Wo er steht, gewinnt er – das
# ist der Weg zu den übrigen Sprachen der Anlage, denn die Adresse eines
# Datenpunkts ändert sich mit der Sprache nicht, sein Name schon.
Zeile = tuple[str, str, str, tuple[str, ...]]

# Der wichtigste Wert eines Anlagenteils, für die Liste links.
#
# Die Anlage selbst zeigt je Funktion **einen** Leitwert: am Kessel die
# Kesseltemperatur, am Heizkreis die Raumtemperatur, am Puffer die obere
# Temperatur. Ohne diese Trennung gewann bisher die Kesseltemperatur auch am
# Heizkreis – der meldet sie nämlich ebenfalls.
KENNWERT_JE_FCT: dict[int, tuple[Zeile, ...]] = {
    14: (  # Heizkreis
        (r"raumtemperatur ist", "Raumtemperatur", "mdi:home-thermometer", ("room_temperature",)),
        (r"vorlauftemperatur ist", "Vorlauf", "mdi:radiator", ("flow_temperature",)),
    ),
    16: (  # Puffer
        (r"puffer oben", "Puffer oben", "mdi:storage-tank", ("buffer_top",)),
        # „Temperatur ist" ohne Zusatz: Welche Adresse dahintersteht, hängt an
        # der Baureihe. Ohne Beleg kein Schlüssel.
        (r"^temperatur ist$", "Temperatur", "mdi:thermometer", ()),
    ),
    # Das Pumpen-/Relaismodul zeigt seine **Anforderung**, nicht seinen Fühler.
    # Dessen Kesseltemperatur (0/7) misst bei einer Fernwärmeübergabe den
    # Speicher auf der anderen Seite – in der Übersicht sagt sie nichts. Der
    # Sollwert erscheint erst über null; darunter liegt keine Anforderung an.
    20: (  # ZSP Pumpen-/Relaismodul
        (ANALOG_SOLLWERT, "Anforderung", "mdi:thermometer-alert", ("analog_setpoint",)),
    ),
    25: (  # Kessel
        (r"kesseltemperatur ist", "Kesseltemperatur", "mdi:fire", ("boiler_temperature",)),
    ),
}

# Rückfall für Funktionstypen ohne eigene Liste.
KENNWERT: tuple[Zeile, ...] = (
    (r"kesseltemperatur ist", "Kesseltemperatur", "mdi:fire", ("boiler_temperature",)),
    (r"puffer oben", "Puffer oben", "mdi:storage-tank", ("buffer_top",)),
    (r"warmwassertemperatur", "Warmwasser", "mdi:water-boiler", ("dhw_temperature",)),
    (r"raumtemperatur ist", "Raumtemperatur", "mdi:home-thermometer", ("room_temperature",)),
    (r"vorlauftemperatur ist", "Vorlauf", "mdi:radiator", ("flow_temperature",)),
    (r"^temperatur ist$", "Temperatur", "mdi:thermometer", ()),
    (r"r(ü|ue)cklauf temperatur", "Rücklauf", "mdi:pipe", ("return_temperature",)),
)

# Systemstatus rechts: Zeile für Zeile, in dieser Reihenfolge.
STATUS: tuple[Zeile, ...] = (
    (r"betriebsphase", "Betriebszustand", "mdi:state-machine", ("operating_phase",)),
    (r"au(ß|ss)entemperatur", "Außentemperatur", "mdi:thermometer", ("outdoor_temperature",)),
    (r"kesselleistung", "Kesselleistung", "mdi:fire", ("boiler_power",)),
    (
        r"brennerkammertemperatur",
        "Brennkammertemperatur",
        "mdi:fireplace",
        ("combustion_chamber_temperature",),
    ),
    (r"abgastemperatur", "Abgastemperatur", "mdi:smoke", ("flue_gas_temperature",)),
    (r"aktueller brennstoff", "Brennstoff", "mdi:sack", ("fuel_current",)),
    (r"vorratsbeh", "Vorratsbehälter", "mdi:battery-70", ("fuel_storage_status",)),
    (r"brennerstarts", "Brennerstarts", "mdi:restart", ("burner_starts",)),
    (r"betriebsstunden", "Betriebsstunden", "mdi:clock-outline", ("operating_hours",)),
    (
        r"laufzeit bis ascheentleerung",
        "Bis Ascheentleerung",
        "mdi:delete-clock-outline",
        ("maintenance_ash_hours",),
    ),
)

# Warmwasser hat keine eigene Funktion: Die Datenpunkte hängen am Heizkreis.
# Die Wortgrenze ist nötig – ohne sie zählte auch die Abgas-Re*zirkulation* des
# Kessels als Warmwasserwert.
WARMWASSER = _muster(
    r"\bwarmwasser",
    r"\bww[- ]",
    r"\bzirkulation",
)
WARMWASSER_SCHLUESSEL = (
    "dhw_temperature",
    "dhw_temperature_target",
    "dhw_charge_pump",
    "dhw_circulation_pump",
    "dhw_circulation_mode",
    "dhw_circulation_temperature",
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

# Eigene Zeilen in der Heizungsübersicht. Warmwasser und Zirkulation hängen als
# Datenpunkte am Heizkreis, liest man aber täglich – sie gehören in die Liste
# der Kennwerte. Beide Schreibweisen zählen, weil die kuratierte Tabelle anders
# benennt als die Geräte-Datenbank; der Sollwert darf nicht mitgehen, sonst
# stünde er statt des Messwerts da.
WARMWASSER_IST_KENNWERT = r"\bww[- ]temperatur aktueller|\bwarmwasser ist[- ]?temperatur"
ZIRKULATION_IST_KENNWERT = r"\bww-zirkulations?[- ]?(ist[- ])?temperatur(?!.*soll)"

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
VERLAUF_SCHLUESSEL = (
    "boiler_temperature",
    "flue_gas_temperature",
    "combustion_chamber_temperature",
    "buffer_top",
    "buffer_bottom",
    "flow_temperature",
    "room_temperature",
    "return_temperature",
    "outdoor_temperature",
    "boiler_power",
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
# Das Zirkulationsprogramm und der Datenpunkt, der darüber entscheidet, ob es
# überhaupt etwas tut: `5/6` „WW-Zirkulationspumpe" mit den Werten Aus, Mit
# Zeitsteuerung, Mit Temperatursteuerung, Mit Impulssteuerung, EIN. Nur bei
# „Mit Zeitsteuerung" richtet sich die Pumpe nach dem Programm.
ZIRKULATIONSPROGRAMM = _muster(r"zirkulations?programm")
ZIRKULATIONSPUMPE = _muster(r"zirkulationspumpe")
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

# Wie weit die Warmwassertemperatur unter dem eingestellten Wert liegen muss,
# damit die Anlage eine Einmalladung überhaupt annimmt. Der eingestellte Wert
# ist der Ausschaltpunkt; darüber startet sie nicht. Die Anleitung nennt dafür
# den Serviceparameter „Hysterese EIN" (5/0, Werk 5 K, Bereich 1–20 K).
WARMWASSER_ABSTAND = 5.0
# Genau dieser Serviceparameter, falls die Anlage ihn hergibt. Er steht auf der
# Serviceebene und ist standardmäßig abgeschaltet; dann bleibt es beim
# Werkswert oben.
WARMWASSER_HYSTERESE = r"^hysterese ein$"

# Betriebsarten (2/9), die eine laufende Warmwasserladung bedeuten.
WARMWASSER_LAEDT = ("WW-Ladung", "Warmwasser Einmalladung", "Warmwasser Hygiene-Programm")

# Betriebswahl-Einträge (3/50), die bei der Warmwasserladung eine Rolle
# spielen. Es sind Muster, keine festen Namen: Welche Einträge eine Anlage
# anbietet, meldet sie selbst, und „Programm 1" heißt nicht überall gleich.
BETRIEBSWAHL_STANDBY = r"^standby$"
BETRIEBSWAHL_WW = r"^ww[- ]betrieb$|^warmwasserbetrieb$"
BETRIEBSWAHL_ZURUECK = r"^programm"
# Das Urlaubsprogramm steht **nicht** in der Betriebswahl: `3/50` kennt
# Standby, Programm 1–3, Heiz-, Absenk-, WW-, Handbetrieb und Kühlen – mehr
# nicht. Der Urlaub entsteht aus dem Datum (`3/78`) und meldet sich nur in der
# Betriebsart (`2/9` = 5). Für die Warmwasserladung zählt er wie Standby: Der
# Kreis nimmt den Auftrag nicht an, es muss vorher umgeschaltet werden.
BETRIEBSART_URLAUB = r"^urlaub"

# Die Außentemperatur gehört an der Anlage in die Kopfzeile und nicht in eine
# Kachel – sie gilt für die ganze Anlage, nicht für einen Anlagenteil.
AUSSENTEMPERATUR = _muster(r"au(ß|ss)entemperatur")

# Lagerraumbefüllung. Die Anlage zeigt dazu eine eigene Seite mit
# Kesseltemperatur bzw. Vorratsbehälter-Status, Restlaufzeit, der Freigabe
# („freigegeben"/„gesperrt") und der Betriebsphase – in dieser Reihenfolge.
LAGERRAUM_ANFORDERN = _muster(r"lagerraumbef(ü|ue)llung anfordern")
LAGERRAUM_ZEILEN: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (r"kesseltemperatur ist", "Kesseltemperatur", ("boiler_temperature",)),
    (r"vorratsbeh", "Vorratsbehälter", ("fuel_storage_status",)),
    (r"lagerraumbef(ü|ue)llung restlaufzeit", "Restlaufzeit", ()),
    (r"lagerraum bef(ü|ue)llen freigabe", "Lagerraum befüllen", ()),
    (r"betriebsphase", "Betriebsphase", ("operating_phase",)),
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
