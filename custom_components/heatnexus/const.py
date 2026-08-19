"""Constants for the Windhager Heater integration."""

DOMAIN = "heatnexus"
# Zugang zur Anlage. Ab Werk kennt die Steuerung „USER" und „Service" mit
# demselben Standardkennwort; „Service" sieht zusätzlich die Fachparameter.
DEFAULT_USERNAME = "USER"
SERVICE_USERNAME = "Service"
BEKANNTE_BENUTZER = [DEFAULT_USERNAME, SERVICE_USERNAME]

# Meldung an die Plattformen, sobald nachträglich Entitäten dazugekommen sind
SIGNAL_NEUE_ENTITAETEN = "heatnexus_neue_entitaeten_{}"

# ---------------------------------------------------------------------------
# Konfiguration (Einrichtungsdialog und Optionen)
# ---------------------------------------------------------------------------
CONF_SYSTEMS = "systems"  # Liste der Anlagen eines Konfigurationseintrags
CONF_LABEL = "label"  # Bezeichnung einer Anlage, z.B. "Heizhaus"
CONF_COUNT = "count"  # Anzahl der Anlagen im Einrichtungsdialog
MAX_SYSTEMS = 6

CONF_LEVELS = "levels"
CONF_ENABLE_ADVANCED = "enable_advanced"
CONF_WRITABLE_ADVANCED = "writable_advanced"
# Systemuhr und Systemdatum der Steuerung werden deaktiviert angelegt; der
# Haken legt sie aktiv an.
CONF_ZEITWERTE = "zeitwerte"
CONF_ZUSATZWERTE = "zusatzwerte"
CONF_ZUSATZGRUPPEN = "zusatzgruppen"

# Abgeleitete Werte nach ihrer Herkunft. Die Gruppe steht im Deskriptor; die
# Auswahl in den Optionen kreuzt Gruppen an, nicht Einzelwerte.
GRUPPE_LAUFZEIT = "laufzeit"
GRUPPE_ZAEHLER = "zaehler"
GRUPPE_INDIVIDUELL = "individuell"
GRUPPE_SCHALTPUNKT = "schaltpunkt"
ZUSATZGRUPPEN = {
    GRUPPE_LAUFZEIT: "Laufzeit",
    GRUPPE_ZAEHLER: "Zähler",
    GRUPPE_SCHALTPUNKT: "Schaltpunkte",
}
# Ob der LON-Adressraum überhaupt gelesen wird. Er lohnt sich, wo der
# OID-Raum dünn ist (BioWIN: 49 Werte ohne Entsprechung) und kaum, wo er
# reich ist (PuroWIN: 12, davon die meisten Bus-Verwaltung).
CONF_LON = "lon"

# Genau die beiden Datenpunkte, die die Steuerung selbst stellt (2/70 und
# 2/72). Erkannt wird am Namen, nicht an der Adresse: Ein Feld mit Datum darin
# ist noch lange kein Systemdatum – „Urlaubsprogramm bis" und die
# Zirkulationszeiten sind Betriebswerte und bleiben sichtbar.
SYSTEMZEIT_NAMEN = frozenset({"Uhrzeit", "Datum"})
# Frist für Datum und Uhrzeit der Steuerung zusammen. Reicht sie nicht,
# wird das Alter der Startwerte gegen die Serverzeit gerechnet.
UHR_TIMEOUT = 3

# Wie alt ein Wert aus dem Lesespeicher der Anlage höchstens sein darf, um
# beim Start übernommen zu werden. 0 schaltet die Übernahme ab.
CONF_STARTWERTE = "startwerte"
STARTWERTE_VORGABE = 15
STARTWERTE_WAHL = ("0", "5", "15", "60")

CONF_UPDATE_INTERVAL = "update_interval"
CONF_DASHBOARD = "dashboard"

# Mitgeliefertes Dashboard
DASHBOARD_URL = "heatnexus"
DASHBOARD_TITEL = "Heizung"

# Eigene Oberfläche (Panel) mit dem Anlagenschaubild
CONF_PANEL = "panel"
# Benachrichtigung, während die Anlage eingelesen wird. Standardmäßig aus:
# Wer nicht gerade zusieht, will keine Meldung, und beim zweiten Start steht
# ohnehin alles sofort da.
CONF_MELDUNG_EINLESEN = "meldung_einlesen"
# Entität, die in der Kopfzeile der eigenen Oberfläche als Außentemperatur
# gilt. Leer heißt: HeatNexus sucht sie sich in der Anlage selbst. Nötig,
# weil der Außenfühler oft woanders hängt als bei der Anlage, die ihn meldet.
CONF_AUSSENTEMPERATUR = "aussentemperatur"
# Erklärungen („?") in der eigenen Oberfläche. Standardmäßig an – wer die
# Anlage kennt, schaltet sie ab.
CONF_HILFE = "hilfe"
# Welche Automations-Vorlagen mitgeliefert werden. Fehlt die Angabe, kommen
# alle mit – eine Aktualisierung ändert an einer bestehenden Anlage nichts.
CONF_VORLAGEN = "vorlagen"
# Sprache der Bezeichnungen, die die Steuerung selbst mitführt. „auto" folgt
# der Spracheinstellung von Home Assistant. Die Wahl entscheidet, welche
# Textdateien der Anlage gelesen werden.
CONF_SPRACHE = "sprache"
SPRACHE_BESCHRIFTUNG: dict[str, str] = {
    "auto": "Automatisch",
    "de": "Deutsch",
    "en": "Englisch",
    "fr": "Französisch",
    "it": "Italienisch",
}
# Art des Wärmeerzeugers. Wirkt **nur auf die Zeichnung im Schaubild** – keine
# Entität, keine Einheit, kein Datenpunkt hängt davon ab. „auto" leitet sie aus
# dem gemeldeten Brennstoff und dem Funktionsnamen ab; die Auswahl ist dafür
# da, dass eine falsch erkannte Anlage trotzdem richtig aussieht.
CONF_KESSELART = "kesselart"

# Welchen zweiten Wert der Kessel im Schaubild zeigt. Die Leistung sagt am
# meisten über den Betrieb aus und bleibt Vorgabe; wer lieber die Temperatur
# im Brennraum sieht, stellt hier um. Die Bewegung des Glutbetts richtet sich
# davon unabhaengig weiter nach der Leistung - erst wenn die fehlt, springt
# sie auf die Brennkammertemperatur um.
CONF_KESSELWERT = "kesselwert"
KESSELWERT_LEISTUNG = "leistung"
KESSELWERT_BRENNKAMMER = "brennkammer"
KESSELWERTE = (KESSELWERT_LEISTUNG, KESSELWERT_BRENNKAMMER)
KESSELWERT_BESCHRIFTUNG = {
    KESSELWERT_LEISTUNG: "Kesselleistung",
    KESSELWERT_BRENNKAMMER: "Brennkammertemperatur",
}

# Ersatzskala für das Glutbett, wenn keine Leistung gemeldet wird: Unter 100 °C
# im Brennraum glimmt nichts, ab 500 °C laeuft der Kessel voll. Darueber bleibt
# es bei voller Helligkeit - heisser heisst nicht mehr Leistung.
BRENNKAMMER_KALT = 100
BRENNKAMMER_HEISS = 500

# Eco und Comfort: dieselbe befristete Uebersteuerung, die auch das Bediengeraet
# schreibt (3/4 Temperatur + 2/10 Dauer). Die Anlage kennt nur *einen*
# Uebersteuerungswert; ob er Eco oder Comfort heisst, entscheidet sie daran, ob
# er unter oder ueber dem Programmsollwert liegt.
CONF_ECO_TEMP = "eco_temperatur"
CONF_ECO_DAUER = "eco_dauer"
CONF_COMFORT_TEMP = "comfort_temperatur"
CONF_COMFORT_DAUER = "comfort_dauer"
ECO_TEMP_STANDARD = 10.0
COMFORT_TEMP_STANDARD = 22.0
UEBERSTEUERUNG_DAUER_STANDARD = 180
PANEL_URL = "heatnexus-anlage"
PANEL_TITEL = "HeatNexus"
PANEL_ELEMENT = "heatnexus-panel"


def panel_fassung(version: str) -> str:
    """Fassungsnummer so, wie sie in Pfad und Elementnamen stehen darf."""
    return "".join(z if z.isalnum() else "-" for z in (version or "0"))


def panel_js_pfad(version: str) -> str:
    """Adresse der Oberflächendatei für genau diese Fassung.

    Die Fassungsnummer steckt im Pfad, nicht in einem Anhang dahinter: Home
    Assistants Service Worker gleicht zwischengespeicherte Antworten ohne
    Suchteil ab, ein „?v=…“ wurde also übergangen und weiterhin die alte Datei
    ausgeliefert. Ein anderer Pfad ist für den Zwischenspeicher eine andere
    Datei – damit genügt ein gewöhnliches Neuladen statt Strg+Umschalt+R.
    """
    return f"{panel_verzeichnis(version)}/heatnexus-panel.js"


# Die Karte liegt unter einem **festen** Pfad, anders als das Panel.
KARTE_VERZEICHNIS = "/heatnexus-karte"


def karte_verzeichnis(version: str) -> str:
    """Ordner der Kartendateien für genau diese Fassung."""
    return f"{KARTE_VERZEICHNIS}-{panel_fassung(version)}"


def karte_js_pfad(version: str) -> str:
    """Adresse des Kartenmoduls, Fassung im Pfad.

    Editor und Bausteine lädt die Karte über relative Adressen nach; ein
    Anhang `?v=` erreichte die nicht. Der feste Pfad bleibt daneben bestehen.
    """
    return f"{karte_verzeichnis(version)}/heatnexus-schaubild-karte.js"


def panel_verzeichnis(version: str) -> str:
    """Adresse des Ordners, in dem die Oberflächendateien liegen.

    Ausgeliefert wird der ganze Ordner, nicht die einzelne Datei: Die
    Oberfläche besteht aus mehreren ES-Modulen, die einander über relative
    Adressen laden (``./stil.js``). Die Fassung bleibt im Pfad – aus demselben
    Grund wie bei der Datei.
    """
    return f"/heatnexus-frontend/{panel_fassung(version)}"


def panel_element(version: str) -> str:
    """Name des Anzeigeelements für genau diese Fassung.

    Der neue *Pfad* allein genügt nicht. Ein Anzeigeelement lässt sich im
    Browser nur **einmal je Seitensitzung** anmelden; ein zweiter Aufruf von
    ``customElements.define`` mit demselben Namen scheitert. Die neue Datei
    wurde also geladen, übersprang die Anmeldung – und die **alte Klasse
    zeichnete weiter**, bis jemand mit Strg+Umschalt+R eine neue Seitensitzung
    erzwang. Mit der Fassung im Namen ist jede Fassung ein eigenes Element.

    Die Datei im Browser leitet denselben Namen aus ihrer eigenen Adresse ab;
    beide müssen also zusammenpassen (siehe `tests/test_panel.py`).
    """
    return f"{PANEL_ELEMENT}-{panel_fassung(version)}"


# Bedienebenen der Anlage, wie sie auch das InfoWIN Touch kennt
LEVEL_INFO = "info"  # Messwerte und Zustände
LEVEL_OPERATE = "operate"  # Betreiberebene: Betriebswahl, Sollwerte, Programme
LEVEL_SERVICE = "service"  # Serviceebene: Heizkurve, Grenzwerte, Estrich
LEVEL_OEM = "oem"  # Werksebene: Verbrennungsregelung, Zündung, Antriebe

ALL_LEVELS = [LEVEL_INFO, LEVEL_OPERATE, LEVEL_SERVICE, LEVEL_OEM]
# Beschriftung der Bedienebenen im Einrichtungsdialog. Sie steht hier und
# nicht nur in den Übersetzungsdateien, weil Home Assistant die
# Übersetzungen von Auswahlfeldern im Einrichtungsdialog einer eigenen
# Integration nicht zuverlässig lädt – dort stünden sonst „info", „operate",
# „service" und „oem".
LEVEL_BESCHRIFTUNG = {
    LEVEL_INFO: "Infoebene (Messwerte)",
    LEVEL_OPERATE: "Betreiberebene (Bedienung)",
    LEVEL_SERVICE: "Serviceebene (Fachparameter)",
    LEVEL_OEM: "Werksebene (Herstellerparameter)",
}
# Info und Betreiberebene sind der sinnvolle Standard; die Serviceebene wird
# mitgelesen, ihre Entities sind aber zunächst deaktiviert.
DEFAULT_LEVELS = [LEVEL_INFO, LEVEL_OPERATE, LEVEL_SERVICE]
# Diese Ebenen gelten als "fortgeschritten": Entities werden nur auf Wunsch
# aktiviert und nur auf Wunsch bedienbar gemacht.
ADVANCED_LEVELS = {LEVEL_SERVICE, LEVEL_OEM}

# Art des Wärmeerzeugers für das Schaubild. Die Schlüssel sind zugleich die
# Namenszusätze der Bauteildateien: `kessel-<art>.svg`. Wer eine weitere Art
# zeichnen will, legt die Datei ab und trägt den Schlüssel hier ein – im Code
# ist sonst nichts zu ändern.
KESSELART_AUTO = "auto"
KESSELART_STANDARD = "standard"
KESSELARTEN = [
    KESSELART_AUTO,
    "hackgut",
    "pellets",
    "scheitholz",
    "waermepumpe",
    "gas_oel",
    KESSELART_STANDARD,
]
# Beschriftung wie bei den Bedienebenen: im Einrichtungsdialog lädt Home
# Assistant die Übersetzung der Auswahlfelder nicht zuverlässig mit.
KESSELART_BESCHRIFTUNG = {
    KESSELART_AUTO: "Automatisch erkennen",
    "hackgut": "Hackgutkessel",
    "pellets": "Pelletskessel",
    "scheitholz": "Scheitholzkessel",
    "waermepumpe": "Wärmepumpe",
    "gas_oel": "Gas- oder Ölkessel",
    KESSELART_STANDARD: "Neutral (ohne Brennstoffbezug)",
}

# Das Grundintervall ist die **Untergrenze** der schnellen Klasse, kein
# Multiplikator: `poll_takte` rechnet `Ziel / Intervall`, und das Ziel der
# schnellen Klasse sind 30 Sekunden. Ein kürzeres Intervall weckt den
# Coordinator öfter, ohne dass ein Wert häufiger gelesen würde – gemessen
# blieb `fast` bei 15 s ebenfalls auf 30 s. Deshalb beginnt die Auswahl dort,
# wo sie auch wirkt.
MIN_UPDATE_INTERVAL = 30
MAX_UPDATE_INTERVAL = 300

# Poll-Klassen: nicht jeder Datenpunkt gehört in denselben Takt.
POLL_FAST = "fast"
POLL_NORMAL = "normal"
POLL_SLOW = "slow"
# Angestrebter Abstand zweier Abrufe je Klasse, in Sekunden. Daraus wird der
# Takt am tatsächlich eingestellten Intervall berechnet – eine feste Vielfache
# stimmte nur bei den voreingestellten 30 s: Bei 300 s wären aus den 15 Minuten
# der langsamen Klasse zweieinhalb Stunden geworden.
POLL_ZIEL_SEKUNDEN = {POLL_FAST: 30, POLL_NORMAL: 120, POLL_SLOW: 900}

# Entitätsarten, die die Anlage bedienen oder ihren Zustand zeigen: immer schnell.
POLL_TYPEN_SCHNELL = frozenset(
    {"climate", "temperature", "device_status", "message_text", "binary_sensor"}
)
# Stellwerte ändern sich nur, wenn jemand sie ändert – im Haus oder am
# Bediengerät. Sie laufen deshalb höchstens im mittleren Takt, auch wenn ihr
# Name nach Messwert klingt („Raumtemperatur Heizbetrieb").
POLL_TYPEN_STELLWERT = frozenset({"number", "select", "switch", "date", "time"})
# Namensbestandteile träger Werte (Zählerstände, Wartungsfristen, Kennungen).
POLL_WOERTER_TRAEGE = (
    "betriebsstunden",
    "laufzeit bis",
    "brennerstarts",
    "wärmemenge",
    "waermemenge",
    "energie",
    "verbrauch",
    "zähler",
    "zaehler",
    "software",
    "seriennummer",
    "version",
    "gesamt",
)
# Einheiten, die es nur bei Zählerständen gibt.
POLL_EINHEITEN_TRAEGE = frozenset({"h", "kWh", "MWh", "d"})
# Namensbestandteile, die einen laufenden Betriebswert kennzeichnen.
POLL_WOERTER_SCHNELL = (
    "temperatur",
    "betriebsphase",
    "betriebsart",
    "pumpe",
    "leistung",
    "meldung",
    "störung",
    "stoerung",
    "brenner",
    "vorlauf",
    "rücklauf",
    "ruecklauf",
)
# Poll-Intervall (s). 30 s für spürbar schnellere Aktualisierung der Climate-/
# Sensorwerte; dank schlankem Poll-Set (nur aktive OIDs) gut vertretbar.
UPDATE_INTERVAL = 30

# Was für ein Anlagenteil das ist – für die Geräteseite in Home Assistant.
#
# Der Gerätename kommt von der Anlage selbst und ist oft von Hand vergeben —
# er beschreibt dann den Raum oder die Nutzung. Als Modell taugt er nicht: Dort
# gehört hin, um was für ein Gerät es sich handelt. Die Nummern sind dieselben
# `fctType`-Werte wie in `dashboard.FCT_RANG`.
FCT_MODELL: dict[int, str] = {
    1: "Heizkreis (Infinity PLUS)",
    2: "Warmwasser",
    4: "Kaskade",
    5: "Solar",
    6: "Gas-/Ölkessel",
    7: "Wärmepumpe",
    8: "Zusatzheizung",
    9: "BioWIN Pelletskessel",
    10: "Automatik-/Zusatzkessel",
    14: "Heizkreis (UML/UMLZ)",
    15: "Umschaltung Kessel/Puffer",
    16: "Pufferspeicher (B-PLMi)",
    20: "Pumpen-/Relaismodul (ZSP)",
    21: "Pufferspeicher",
    24: "Pumpe Wärmeerzeuger",
    25: "PuroWIN Hackgutkessel",
    26: "Wärmepumpe (Energiemanagement)",
    27: "Wärmepumpe",
}

# Datenpunkte, die jedes Modul über sich selbst führt.
OID_SOFTWAREVERSION = "4/92"
OID_HARDWAREVERSION = "4/93"

# Ab wie vielen abgewiesenen Anfragen in Folge nach dem Passwort gefragt wird.
#
# Ein einzelner `401` heißt hier nichts: Die Steuerung vergibt ihre Nonce nur
# einmal, und ein verbrauchter kostet einen Anlauf. Drei hintereinander sind
# etwas anderes - dann stimmt das Passwort nicht mehr.
AUTH_FEHLER_GRENZE = 3

# Obergrenze, wenn die Anlage nicht antwortet.
#
# Nach jedem Fehlschlag verdoppelt sich der Abstand, höchstens aber bis hierhin.
# Eine Anlage, die gerade neu startet oder überlastet ist, bekommt sonst alle
# dreißig Sekunden eine volle Runde Anfragen und kommt nicht zur Ruhe. Fünf
# Minuten sind lang genug, um sie in Frieden zu lassen, und kurz genug, dass
# niemand auf eine Rückkehr wartet.
BACKOFF_MAX = 300

# Nachfassen nach einer Bedienung.
#
# Die Anlage übernimmt einen geschriebenen Wert nicht sofort: Sie quittiert den
# Auftrag und arbeitet ihn ab. Ein einzelner Abruf direkt danach liest deshalb
# oft noch den alten Stand, und bis zum nächsten Takt vergehen 30 Sekunden – in
# denen die Oberfläche behauptet, nichts sei passiert.
#
# Nachgefasst wird nur der **eine** geschriebene Datenpunkt, nicht das ganze
# Poll-Set: Das kostet sechs Anfragen statt sechsmal siebzig.
NACHFASS_ANZAHL = 6
NACHFASS_INTERVALL = 3

# ---------------------------------------------------------------------------
# Einheiten der Anlage -> Home-Assistant-Konvention
#
# Die Steuerung meldet ihre Einheiten so, wie sie am Display stehen ("U/min",
# "m^3/h"). Home Assistant erwartet eigene Schreibweisen und leitet aus der
# Geräteklasse ab, ob ein Wert umgerechnet, in der Statistik geführt und mit
# wie vielen Nachkommastellen angezeigt wird. Ohne diese Tabelle lief alles
# außer den °C-Werten als namenloser Zahlensensor ohne Langzeitverlauf.
#
# Aufbau: Geräteeinheit -> (HA-Einheit, device_class, state_class, Stellen)
# ---------------------------------------------------------------------------
EINHEITEN: dict[str, tuple[str, str | None, str, int]] = {
    "°C": ("°C", "temperature", "measurement", 1),
    # Kelvin steht hier immer für eine Differenz (Überhöhung, Spreizung) und
    # nicht für eine absolute Temperatur – deshalb ohne Geräteklasse.
    "K": ("K", None, "measurement", 1),
    "%": ("%", None, "measurement", 0),
    "kW": ("kW", "power", "measurement", 1),
    "W": ("W", "power", "measurement", 0),
    "kWh": ("kWh", "energy", "total_increasing", 1),
    "MWh": ("MWh", "energy", "total_increasing", 2),
    "A": ("A", "current", "measurement", 2),
    "V": ("V", "voltage", "measurement", 1),
    "Hz": ("Hz", "frequency", "measurement", 1),
    "U/min": ("rpm", None, "measurement", 0),
    "m^3/h": ("m³/h", "volume_flow_rate", "measurement", 1),
    "m³/h": ("m³/h", "volume_flow_rate", "measurement", 1),
    # Liter je Stunde ohne Geräteklasse: Home Assistant kennt für den
    # Volumenstrom nur L/min, mL/s, m³/h, ft³/min und gal/min. Die Anlage
    # meldet L/h; umgerechnet stünde eine andere Zahl da als am InfoWIN.
    "l/h": ("L/h", None, "measurement", 1),
    "s": ("s", "duration", "measurement", 0),
    "min": ("min", "duration", "measurement", 0),
    "h": ("h", "duration", "measurement", 0),
    "d": ("d", "duration", "measurement", 0),
    # Tonnen ohne Geräteklasse: Home Assistant lässt für `weight` nur bis
    # Kilogramm zu und weist `t` mit einer Warnung ab. Die Anlage meldet den
    # Brennstoffverbrauch aber in Tonnen; umgerechnet stünde in der Anzeige
    # eine andere Zahl als am InfoWIN. Der Langzeitverlauf hängt an der
    # Statistikklasse, nicht an der Geräteklasse, und bleibt erhalten.
    "t": ("t", None, "total_increasing", 2),
    "kg": ("kg", "weight", "total_increasing", 1),
    "bar": ("bar", "pressure", "measurement", 2),
    "mbar": ("mbar", "pressure", "measurement", 1),
    "Pa": ("Pa", "pressure", "measurement", 0),
}

# Dieselben Größen in der Schreibweise des LON-Adressraums. Als Verweis statt
# als zweiter Eintrag: Ändert sich die Umrechnung, ändert sie sich für beide.
EINHEITEN["rpm"] = EINHEITEN["U/min"]
EINHEITEN["Std"] = EINHEITEN["h"]

# Namensbestandteile, die einen Zählerstand kennzeichnen: Sie laufen nur nach
# oben und gehören damit in die Langzeitstatistik als Summe, nicht als Messwert.
ZAEHLER_WOERTER = (
    "betriebsstunden",
    "brennerstarts",
    "verbrauch",
    "zähler",
    "zaehler",
    "wärmemenge",
    "waermemenge",
    "gesamt",
)

# Gleichzeitige Anfragen an die Anlage.
#
# Drei – und zwar gemessen, nicht geschätzt. Der Versuch mit sechs brachte
# nichts: Die Antwortzeit je Datenpunkt stieg von 765 ms auf 1287 ms, während
# ein vollständiger Abruf nur von 11,0 s auf 10,4 s sank. Die Steuerung
# arbeitet Anfragen praktisch nacheinander ab; mehr Parallelität verteilt
# dieselbe Zeit auf mehr Verbindungen und belastet sie stärker.
#
# Der einzige wirksame Hebel ist deshalb, **weniger zu fragen** – nicht,
# schneller zu fragen.
FETCH_CONCURRENCY = 3
POLL_CONCURRENCY = 3

# Nach je so vielen gelesenen Datenpunkten prüft der Abruf, ob seine Zeit noch
# reicht. Klein genug, um das Zeitfenster nicht zu überziehen, groß genug, dass
# die Warteschlange nicht leerläuft.
POLL_BLOCK = POLL_CONCURRENCY * 5

# Ein Menü-Abruf liefert höchstens so viele Datenpunkte; der Rest kommt über
# ?offset=<n> nach.
MENU_PAGE_SIZE = 10

# Datenpunkte, die in keiner Menü-Ebene auftauchen, aber vorhanden und für die
# Bedienung nötig sind. Sie werden zusätzlich einzeln gelesen.
# (An zwei Anlagen erhoben: Zeitprogramme, Warmwasser- und Zirkulationswerte,
# gemessene Raumtemperatur.)
EXTRA_OIDS_BY_FCT: dict[int, tuple[str, ...]] = {
    14: (  # Heizkreis
        "0/1",
        "0/4",
        "0/118",
        "1/4",
        "1/65",
        "1/118",
        "2/9",
        "4/82",
        "3/61",
        "3/62",
        "3/63",
        "5/51",
        "5/61",
        "5/64",
        "5/65",
        "5/70",
        "5/71",
    ),
    16: ("0/7", "2/9", "4/82"),  # Puffer
    20: ("0/7", "1/7", "4/92", "4/93"),  # ZSP Pumpen-/Relaismodul
    # Kessel: Störcode, Softwarestand – und die Lagerraumbefüllung.
    # 39/107 meldet „Gesperrt"/„Freigegeben", 39/5 die Restlaufzeit der
    # Freigabe. Beide stehen in keiner Bedienebene und fehlten deshalb, obwohl
    # die Anlage sie führt und das InfoWIN Touch sie anzeigt.
    25: ("0/97", "4/92", "39/107", "39/5"),
}

# Timeout (s) für die einmalige Erstinitialisierung (Discovery + Metadaten
# aller Datenpunkte inkl. Serviceebene). Bewusst großzügig, da getrennt vom
# schnellen zyklischen Poll-Timeout.
INIT_TIMEOUT = 240

# Zeitfenster (s) für einen zyklischen Abruf.
#
# Der **erste** Abruf nach dem Start ist der größte: Da ist noch kein Wert da,
# also ist jede Poll-Klasse fällig – auch die trägen, die sonst nur jeden
# fünfzehnten Durchlauf drankommen. Auf einer Anlage mit knapp zwei Sekunden
# Antwortzeit je Anfrage passte das nicht mehr in dreißig Sekunden; der Abruf
# lief in die Zeitüberschreitung und die Oberfläche blieb leer. Danach hält
# der reguläre Takt das Fenster locker ein.
ABRUF_TIMEOUT = 30
ERSTABRUF_TIMEOUT = 180

# Zeitfenster (s) für eine einzelne Anfrage. Ohne eigene Grenze wartet aiohttp
# fünf Minuten auf einen Knoten, der annimmt und dann schweigt. Großzügig
# bemessen: Eine Menü-Ebene liefert bis zu hundert Datenpunkte auf einmal.
ANFRAGE_TIMEOUT = 120
VERBINDUNG_TIMEOUT = 10

# Abstand, den der Abruf zum Zeitfenster hält. Er hört von selbst auf, sobald
# das Budget aufgebraucht ist, und nimmt den Rest in den nächsten Durchlauf
# mit. Ein abgebrochener Abruf dagegen verliert alles Gelesene und stellt
# denselben Durchlauf unverändert wieder an.
ABRUF_RESERVE = 5

# Persistenter Discovery-Cache (überlebt HA-Neustart -> schneller Start).
DISCOVERY_STORE_VERSION = 1
# Cache nach dieser Zeit verwerfen und neu erkennen (fängt geänderte Anlagen ab).
DISCOVERY_MAX_AGE_DAYS = 30

# Wann ein Erkennungslauf als misslungen gilt: Findet er deutlich weniger als
# der bekannte Stand, schwächelt die Steuerung – der alte Stand bleibt stehen.
# Unterhalb der Mindestzahl ist der Vergleich sinnlos, dort zählt jeder Wert.
ERKENNUNG_MIN_ANTEIL = 0.8
ERKENNUNG_MIN_DATENPUNKTE = 20

# Function types (fctType) as reported by /api/1.0/lookup/1
FCT_CLIMATE = 14  # Heizkreis (UML+ / UMLZ)
# Der LON-Adressraum eines Knotens. Er meldet sich als Funktion `NV's` ohne
# Funktionstyp; die Steuerung deutet dort die Adresse um (der Member ist der
# `nvIndex`, die Gruppe fällt weg). Deshalb läuft er nicht durch die
# gewöhnliche Erkennung, sondern über einen eigenen Weg.
FCT_NV = -1
FCT_BOILER_SWITCH = 15  # Umschaltung Automatikkessel/Festbrennstoff/Puffer
FCT_BUFFER = 16  # B-PLMi Pufferspeicher
FCT_ZSP = 20  # ZSP Pumpen-/Relaismodul (Pumpe, ext. Wärmeanforderung, Sammelalarm)
FCT_PUROWIN = 25  # PuroWIN Hackgutkessel
FCT_BIOWIN = 9  # BioWIN Pelletskessel

# Legacy names kept for compatibility
CLIMATE_FUNCTION_TYPE = FCT_CLIMATE
HEATER_FUNCTION_TYPE = 9

# ---------------------------------------------------------------------------
# Auswahltabellen, die von der Geräte-Datenbank abweichen
#
# **Normalerweise steht hier nichts.** Die Tabellen kommen aus
# `device_db.json`, erzeugt aus den offiziellen Windhager-Dateien. Eine
# Tabelle zusätzlich von Hand hier zu führen heißt zwei Quellen für dieselbe
# Auskunft; die laufen irgendwann auseinander, und welche dann gilt, sieht man
# dem Code nicht an.
#
# Was hier einzutragen ist: eine Tabelle, deren Text an der **echten Anlage**
# nachweislich anders lautet als in der Herstellerdatei. Sie geht der
# erzeugten dann vor (`entity._enum_map`, `client._apply_metadata`). Mit
# Begründung, sonst wandert sie beim nächsten Aufräumen wieder hinaus.
#
# Schlüssel sind "gn/mn", die Werte ganzzahlig: Echte Auswahllisten haben
# Lücken (Betriebswahl Puffer `20/15` kennt keine 5).
# ---------------------------------------------------------------------------
ENUMS: dict[str, dict[int, str]] = {}

# ---------------------------------------------------------------------------
# Declarative entity definitions per function type.
#
# Each entry:
#   oid:    OID suffix relative to "/1/<node>/<fct>" (always starts with /)
#   name:   Display name (German, like the InfoWIN Touch display)
#   platform: temperature | sensor | enum_sensor | string_sensor |
#             binary_sensor | select | number | switch
# Optional keys:
#   unit, state_class, device_class, enum (key into ENUMS),
#   min/max/step (number), category ("diagnostic"/"config"), icon
#
# min/max/step values originate from the Windhager Betreiberebene
# (verified against connect.windhager.com and the local device).
# ---------------------------------------------------------------------------

# Zähler, die Läufe zählen – Bezugspunkt für „seit Start". Angegeben als
# Datenpunktkennung des Herstellers (`gn/mn`), nicht als Baureihe: Was diese
# Adresse führt, führt sie an jedem Aggregat, das sie kennt.
STARTZAEHLER = frozenset(
    {
        "2/80",  # Anzahl der Brennerstarts
        "52/56",  # Anzahl Starts (Wärmepumpe)
        "52/49",  # Anzahl Starts Heizen
        "52/57",  # Anzahl Starts Kühlen
    }
)

# Tageswerte, die die Anlage selbst führt. Sie bekommen keine Ableitung, und
# ihr Gesamtzähler bekommt kein zweites „heute" daneben.
TAGESZAEHLER: dict[str, str] = {
    "52/50": "52/51",  # Betriebsstunden Heizen -> … heute
    "52/52": "52/53",  # Betriebsstunden Warmwasser -> … heute
    "52/54": "52/55",  # Betriebsstunden Kühlen -> … heute
}
# Dieselbe Auskunft als Menge: Ist dieser Datenpunkt selbst schon ein Tageswert?
TAGESWERTE = frozenset(TAGESZAEHLER.values())

# Welche Betriebszustände als Lauf gelten, je Zustandstabelle und als
# **Zahlen**: Beschriftungen wechseln mit Sprache und Baureihe, die Codes
# nicht. Ohne Eintrag entsteht keine Betriebsdauer – geraten wird nichts.
_WP_LAUF = frozenset({4, 5, 6, 7, 8, 9})

LAUFPHASEN: dict[str, frozenset[int]] = {
    # Kessel: Vorspülen bis Modulation, Anheizen, Schichtladung, Ausbrand.
    "2/1": frozenset({5, 6, 7, 8, 15, 16, 17}),
    # Wärmepumpe und Kaskadenstufe: Heizen, Kühlen, Abtauen, Silentmode.
    "50/6": _WP_LAUF,
    "56/6": _WP_LAUF,
    # Wärmepumpenmodul: Vorwärmen zählt zum Lauf, Pausenzeit nicht.
    "50/70": frozenset({3, 4, 5, 6}),
    "59/17": frozenset({1}),
}

# Welchen Stundenzähler die Laufzeit aus dem Zustand ersetzt, je
# Zustandstabelle. Nur diesen: Ein Wartungszähler auf demselben Gerät zählt
# etwas anderes und behält seine Ableitung.
LAUFZEIT_ERSETZT: dict[str, frozenset[str]] = {
    "2/1": frozenset({"2/81"}),
    "50/6": frozenset({"52/50", "52/52", "52/54"}),
    "56/6": frozenset({"52/50", "52/52", "52/54"}),
}

PUROWIN_ENTITIES = [
    # --- Infoebene / Übersicht (read only) ---
    {"oid": "/0/7/0", "name": "Kesseltemperatur Ist", "platform": "temperature"},
    {"oid": "/1/7/0", "name": "Kesseltemperatur Soll", "platform": "temperature"},
    {
        "oid": "/0/9/0",
        "name": "Kesselleistung",
        "platform": "sensor",
        "unit": "%",
        "state_class": "measurement",
    },
    {"oid": "/0/11/0", "name": "Abgastemperatur", "platform": "temperature"},
    {"oid": "/0/45/0", "name": "Brennkammertemperatur", "platform": "temperature"},
    {
        "oid": "/0/42/0",
        "name": "O2 Signal",
        "platform": "sensor",
        "unit": "%",
        "state_class": "measurement",
    },
    {"oid": "/2/1/0", "name": "Betriebsphase", "platform": "enum_sensor", "enum": "2/1"},
    {"oid": "/2/59/0", "name": "Betriebsart", "platform": "enum_sensor", "enum": "2/59"},
    {
        "oid": "/2/80/0",
        "name": "Brennerstarts",
        "platform": "sensor",
        "state_class": "total_increasing",
    },
    {
        "oid": "/2/81/0",
        "name": "Betriebsstunden",
        "platform": "sensor",
        "unit": "h",
        "state_class": "total_increasing",
    },
    # Restlaufzeiten: "measurement", damit Home Assistant sie in die Statistik
    # aufnimmt. Ohne state_class gäbe es keinen Langzeitverlauf und die
    # Auswertung "wann war zuletzt Ascheentleerung" wäre nicht möglich.
    {
        "oid": "/39/91/0",
        "name": "Laufzeit bis Ascheentleerung",
        "platform": "sensor",
        "unit": "h",
        "state_class": "measurement",
        "icon": "mdi:delete-clock-outline",
    },
    {
        "oid": "/39/92/0",
        "name": "Laufzeit bis Hauptreinigung",
        "platform": "sensor",
        "unit": "h",
        "state_class": "measurement",
        "icon": "mdi:broom",
    },
    {
        "oid": "/39/93/0",
        "name": "Laufzeit bis Wartung",
        "platform": "sensor",
        "unit": "h",
        "state_class": "measurement",
        "icon": "mdi:wrench-clock",
    },
    # Gepacktes Statusregister, Bedeutung der Bits unbekannt. Ohne Deutung ist
    # es kein Störungsmelder: Die Geräteklasse `problem` gehört an den Sensor
    # aus `FExxmsg`, der die Meldung im Klartext führt.
    {
        "oid": "/32/0/14",
        "name": "Statusregister",
        "platform": "binary_sensor",
        "category": "diagnostic",
    },
    {"oid": "/0/97/0", "name": "Alarmcode", "platform": "sensor", "category": "diagnostic"},
    {
        "oid": "/4/92/0",
        "name": "Softwareversion",
        "platform": "string_sensor",
        "category": "diagnostic",
    },
    {
        "oid": "/39/61/0",
        "name": "Nennleistung",
        "platform": "sensor",
        "unit": "kW",
        "category": "diagnostic",
    },
    # --- Betreiberebene (operate, schreibbar) ---
    # „Reinigung bestätigen" gibt es weiter unten als einzelne Tasten je Arbeit
    # statt als Auswahlliste.
    {
        "oid": "/39/57/0",
        "name": "Aschetonne entleeren",
        "platform": "switch",
        "category": "config",
        "icon": "mdi:delete-empty",
    },
    {
        "oid": "/14/75/0",
        "name": "Korrektur Reinigungsintervall",
        "platform": "number",
        "unit": "%",
        "min": -50,
        "max": 50,
        "step": 10,
        "category": "config",
    },
    {
        "oid": "/14/19/0",
        "name": "Betriebsart Zuführung",
        "platform": "select",
        "enum": "14/19",
        "category": "config",
    },
    {
        "oid": "/14/11/0",
        "name": "Zuführung Freigabezeit Beginn",
        "platform": "time",
        "category": "config",
        "icon": "mdi:clock-start",
    },
    {
        "oid": "/14/10/0",
        "name": "Zuführung Freigabezeit Ende",
        "platform": "time",
        "category": "config",
        "icon": "mdi:clock-end",
    },
    {
        "oid": "/14/20/0",
        "name": "Zuführung Startzeit",
        "platform": "time",
        "category": "config",
        "icon": "mdi:clock-outline",
    },
    {
        "oid": "/40/69/0",
        "name": "Ascheaustragung Freigabezeit Beginn",
        "platform": "time",
        "category": "config",
        "icon": "mdi:clock-start",
    },
    {
        "oid": "/40/70/0",
        "name": "Ascheaustragung Freigabezeit Ende",
        "platform": "time",
        "category": "config",
        "icon": "mdi:clock-end",
    },
    {
        "oid": "/39/95/0",
        "name": "Brennstoffzuführung anfordern",
        "platform": "switch",
        "category": "config",
        "icon": "mdi:pine-tree-box",
    },
    {
        "oid": "/38/127/0",
        "name": "Aktueller Brennstoff",
        "platform": "enum_sensor",
        "enum": "38/127",
    },
    # Achtung: Wechsel wird erst nach Aus-/Einschalten am Hauptschalter wirksam
    {
        "oid": "/38/126/0",
        "name": "Gewählter Brennstoff",
        "platform": "select",
        "enum": "38/126",
        "category": "config",
    },
    # Die Anlage meldet hier eine Restlaufzeit in Minuten, keinen Schalter:
    # `typeId 4`, Einheit min, schreibgeschützt. 0 heißt, die Funktion steht.
    {
        "oid": "/9/90/0",
        "name": "Kaminkehrer",
        "platform": "sensor",
        "unit": "min",
        "device_class": "duration",
        "state_class": "measurement",
        "category": "diagnostic",
        "icon": "mdi:account-hard-hat",
    },
    {
        "oid": "/10/110/0",
        "name": "Kaminkehrer Leistung",
        "platform": "number",
        "unit": "%",
        "min": 30,
        "max": 100,
        "step": 1,
        "category": "config",
    },
    # Sondenumschaltung (nur bei Saugzuführung mit Sonden vorhanden,
    # nicht vorhandene OIDs werden bei der Discovery automatisch entfernt)
    {
        "oid": "/43/34/0",
        "name": "Sonde 1",
        "platform": "select",
        "enum": "43/34",
        "category": "config",
    },
    {
        "oid": "/43/35/0",
        "name": "Sonde 2",
        "platform": "select",
        "enum": "43/34",
        "category": "config",
    },
    {
        "oid": "/43/36/0",
        "name": "Sonde 3",
        "platform": "select",
        "enum": "43/34",
        "category": "config",
    },
    {
        "oid": "/43/37/0",
        "name": "Sonde 4",
        "platform": "select",
        "enum": "43/34",
        "category": "config",
    },
    {
        "oid": "/43/38/0",
        "name": "Sonde 5",
        "platform": "select",
        "enum": "43/34",
        "category": "config",
    },
    {
        "oid": "/43/39/0",
        "name": "Sonde 6",
        "platform": "select",
        "enum": "43/34",
        "category": "config",
    },
    {
        "oid": "/43/40/0",
        "name": "Sonde 7",
        "platform": "select",
        "enum": "43/34",
        "category": "config",
    },
    {
        "oid": "/43/41/0",
        "name": "Sonde 8",
        "platform": "select",
        "enum": "43/34",
        "category": "config",
    },
    {
        "oid": "/43/79/0",
        "name": "Sonden zurücksetzen",
        "platform": "button",
        "press_value": "1",
        "category": "config",
        "icon": "mdi:restore",
    },
    {
        "oid": "/39/76/0",
        "name": "Vorratsbehälter Status",
        "platform": "enum_sensor",
        "enum": "39/76",
    },
    # Betriebswahl 9/75 kennt mehrere Eingriffe, die man einzeln auslöst:
    #   6 Serviceausbrand (läuft ca. 1 h)
    #   7 Lagerraum befüllen
    # Als eigene Tasten sind sie auffindbar; als Auswahlliste war der
    # Serviceausbrand einen Fehlgriff vom Bunkerbefüllen entfernt.
    {
        "oid": "/9/75/0",
        "name": "Serviceausbrand starten",
        "platform": "button",
        "press_value": "6",
        "category": "config",
        "icon": "mdi:fire-alert",
    },
    # „Kessel EIN/AUS" ist am InfoWIN Touch der oberste Menüpunkt überhaupt –
    # und fehlte hier. Betriebswahl 0 ist AUS, 1 ist EIN; alles darüber sind
    # Sonderbetriebsarten, in denen der Kessel ebenfalls nicht aus ist.
    {
        "oid": "/9/75/0",
        "name": "Kessel",
        "platform": "switch",
        "key_suffix": "ein_aus",
        "category": "config",
        "icon": "mdi:power",
    },
    {
        "oid": "/9/75/0",
        "name": "Lagerraumbefüllung anfordern",
        "platform": "button",
        "press_value": "7",
        "key_suffix": "befuellen",
        "category": "config",
        "icon": "mdi:warehouse",
    },
    # „Reinigung bestätigen" (39/94) ist am Gerät eine Auswahlliste:
    #   1 Reinigung · 2 Hauptreinigung · 3 Wartung
    #   4 Hauptreinigung und Aschetonnen entleeren
    # Als Liste muss man erst lesen, was man wählt, und wählt im Zweifel
    # falsch. Je Arbeit eine eigene Taste mit Rückfrage ist eindeutig.
    {
        "oid": "/39/94/0",
        "name": "Reinigung durchgeführt",
        "platform": "button",
        "press_value": "1",
        "key_suffix": "reinigung",
        "category": "config",
        "icon": "mdi:broom",
    },
    {
        "oid": "/39/94/0",
        "name": "Hauptreinigung durchgeführt",
        "platform": "button",
        "press_value": "2",
        "key_suffix": "hauptreinigung",
        "category": "config",
        "icon": "mdi:broom",
    },
    {
        "oid": "/39/94/0",
        "name": "Wartung durchgeführt",
        "platform": "button",
        "press_value": "3",
        "key_suffix": "wartung",
        "category": "config",
        "icon": "mdi:wrench-check-outline",
    },
    {
        "oid": "/39/94/0",
        "name": "Hauptreinigung und Aschetonnen durchgeführt",
        "platform": "button",
        "press_value": "4",
        "key_suffix": "hauptreinigung_asche",
        "category": "config",
        "icon": "mdi:delete-empty-outline",
    },
    {
        "oid": "/9/75/0",
        "name": "Betriebswahl Kessel",
        "platform": "enum_sensor",
        "enum": "9/75",
        "key_suffix": "status",
        "category": "diagnostic",
    },
    # Fehlertext zum Alarmcode (0/97). Das gepackte Roh-Meldungsregister
    # (/32/0/14) wurde entfernt – die lesbare Geräte-Meldung kommt jetzt aus
    # FE01msg ("<Gerät> Meldung"-Sensor, device_status).
    {"oid": "/0/97/0", "name": "Alarmtext", "platform": "error_sensor", "key_suffix": "text"},
]

CLIMATE_EXTRA_ENTITIES = [
    # --- Infoebene Heizkreis / Warmwasser (read only) ---
    {"oid": "/0/0/0", "name": "Außentemperatur", "platform": "temperature"},
    {"oid": "/0/1/0", "name": "Raumtemperatur Ist", "platform": "temperature"},
    {"oid": "/1/1/0", "name": "Raumtemperatur Soll", "platform": "temperature"},
    {"oid": "/0/2/0", "name": "Vorlauftemperatur Ist", "platform": "temperature"},
    {"oid": "/1/2/0", "name": "Vorlauftemperatur Soll", "platform": "temperature"},
    {"oid": "/0/7/0", "name": "Kesseltemperatur Ist", "platform": "temperature"},
    {"oid": "/1/7/0", "name": "Kesseltemperatur Soll", "platform": "temperature"},
    {"oid": "/0/4/0", "name": "Warmwasser Ist-Temperatur", "platform": "temperature"},
    {"oid": "/1/4/0", "name": "Warmwasser Soll-Temperatur", "platform": "temperature"},
    {"oid": "/0/118/0", "name": "WW-Zirkulation Ist-Temperatur", "platform": "temperature"},
    {"oid": "/1/118/0", "name": "WW-Zirkulation Soll-Temperatur", "platform": "temperature"},
    {
        "oid": "/1/20/0",
        "name": "Heizkreispumpe",
        "platform": "binary_sensor",
        "device_class": "running",
    },
    {
        "oid": "/1/21/0",
        "name": "Mischer Stellwert",
        "platform": "sensor",
        "unit": "%",
        "state_class": "measurement",
    },
    {
        "oid": "/1/65/0",
        "name": "WW-Zirkulationspumpe",
        "platform": "binary_sensor",
        "device_class": "running",
    },
    # **Der Modus der Zirkulationspumpe gehört zur Bedienung, nicht auf die
    # Serviceebene.** Der Hersteller führt `5/6` dort; dadurch entstand die
    # Entität abgeschaltet, und ohne sie wusste die Oberfläche nicht, welches
    # der beiden gleichnamigen Zirkulationsprogramme gerade wirkt – es standen
    # kommentarlos beide da. Wer eine Zirkulation hat, stellt genau hier ein,
    # wonach sie sich richtet.
    {
        "oid": "/5/6/0",
        "name": "WW-Zirkulationspumpe Modus",
        "platform": "select",
        "enum": "5/6",
        "category": "config",
        "icon": "mdi:reload",
    },
    # **Die Einschalthysterese der Warmwasserladung.** Sie sagt, wie weit die
    # Temperatur unter den Sollwert fallen darf, bevor die Anlage nachlädt –
    # Werk 5 K, Bereich 1 bis 20 K. Sie gilt für die Ladung überhaupt, nicht
    # nur für die Einmalladung; die Oberfläche sagt mit ihr vorher, ob ein
    # Ladeauftrag angenommen wird. Der Hersteller führt sie auf der
    # Serviceebene, wodurch sie abgeschaltet entstand und praktisch niemand
    # sie fand.
    {
        "oid": "/5/0/0",
        "name": "Hysterese Ein",
        "platform": "number",
        "unit": "K",
        "min": 1,
        "max": 20,
        "step": 0.5,
        "category": "config",
        "icon": "mdi:arrow-expand-vertical",
    },
    {
        "oid": "/1/66/0",
        "name": "WW-Ladepumpe",
        "platform": "binary_sensor",
        "device_class": "running",
    },
    {"oid": "/2/9/0", "name": "Betriebsart", "platform": "enum_sensor", "enum": "2/9"},
    # --- Betreiberebene (operate, schreibbar) ---
    {
        "oid": "/3/50/0",
        "name": "Betriebswahl",
        "platform": "select",
        "enum": "3/50",
        "category": "config",
    },
    {
        "oid": "/3/58/0",
        "name": "Behaglichkeitskorrektur",
        "platform": "number",
        "unit": "K",
        "min": -3.0,
        "max": 3.0,
        "step": 0.1,
        "category": "config",
    },
    {
        "oid": "/3/51/0",
        "name": "Raumtemperatur Heizbetrieb",
        "platform": "number",
        "unit": "°C",
        "min": 10,
        "max": 30,
        "step": 0.5,
        "category": "config",
        "device_class": "temperature",
    },
    {
        "oid": "/3/53/0",
        "name": "Raumtemperatur Absenkbetrieb",
        "platform": "number",
        "unit": "°C",
        "min": 10,
        "max": 30,
        "step": 0.5,
        "category": "config",
        "device_class": "temperature",
    },
    {
        "oid": "/5/51/0",
        "name": "WW Einmalladung Temperatur",
        "platform": "number",
        "unit": "°C",
        "min": 10,
        "max": 75,
        "step": 0.5,
        "category": "config",
        "device_class": "temperature",
    },
    {
        "oid": "/2/16/0",
        "name": "WW Einmalladung",
        "platform": "switch",
        "category": "config",
        "icon": "mdi:water-boiler",
    },
]

BUFFER_ENTITIES = [
    # --- Infoebene (read only) ---
    {"oid": "/21/65/0", "name": "Puffer oben Temperatur (TPE)", "platform": "temperature"},
    {"oid": "/21/66/0", "name": "Puffer unten Temperatur (TPA)", "platform": "temperature"},
    {"oid": "/0/7/0", "name": "Kesseltemperatur", "platform": "temperature"},
    {"oid": "/0/8/0", "name": "Rücklauf Temperatur", "platform": "temperature"},
    {"oid": "/1/8/0", "name": "Rücklauf Sollwert", "platform": "temperature"},
    {
        "oid": "/1/22/0",
        "name": "Pufferladepumpe Drehzahl",
        "platform": "sensor",
        "unit": "%",
        "state_class": "measurement",
    },
    # Stellwert der Rücklaufhochhaltung, kein Kesselmischer. Deren Bauart
    # steht in `20/124` und trägt denselben Namen ohne Zusatz.
    {
        "oid": "/1/102/0",
        "name": "Rücklaufhochhaltung Stellwert",
        "platform": "sensor",
        "unit": "%",
        "state_class": "measurement",
    },
    {"oid": "/2/9/0", "name": "Betriebsart", "platform": "enum_sensor", "enum": "2/9"},
    {
        "oid": "/7/12/0",
        "name": "Drehzahlregelung Modus",
        "platform": "enum_sensor",
        "enum": "7/12",
        "category": "diagnostic",
    },
    # --- Betreiberebene (operate, schreibbar) ---
    {
        "oid": "/20/15/0",
        "name": "Betriebswahl",
        "platform": "select",
        "enum": "20/15",
        "category": "config",
    },
    # --- Serviceebene (schreibbar, Gerät kann Schreibzugriff verweigern) ---
    {
        "oid": "/20/14/0",
        "name": "Pufferladepumpe min Drehzahl",
        "platform": "number",
        "unit": "%",
        "min": 10,
        "max": 100,
        "step": 1,
        "category": "config",
    },
    {
        "oid": "/20/22/0",
        "name": "Pufferladepumpe max Drehzahl",
        "platform": "number",
        "unit": "%",
        "min": 50,
        "max": 100,
        "step": 1,
        "category": "config",
    },
    {
        "oid": "/9/32/0",
        "name": "Puffer Minimaltemperatur",
        "platform": "number",
        "unit": "°C",
        "min": 20,
        "max": 60,
        "step": 1,
        "category": "config",
        "device_class": "temperature",
    },
    {
        "oid": "/10/31/0",
        "name": "Puffer Maximaltemperatur",
        "platform": "number",
        "unit": "°C",
        "min": 60,
        "max": 100,
        "step": 1,
        "category": "config",
        "device_class": "temperature",
    },
    {
        "oid": "/20/28/0",
        "name": "Minimale Laufzeit Pufferladung",
        "platform": "number",
        "unit": "min",
        "min": 0,
        "max": 360,
        "step": 15,
        "category": "config",
    },
    {
        "oid": "/20/29/0",
        "name": "Laufzeitoptimierung Sollwert",
        "platform": "number",
        "unit": "°C",
        "min": 60,
        "max": 85,
        "step": 1,
        "category": "config",
        "device_class": "temperature",
    },
]

# Die Namen sind die des Herstellers. `0/7` heißt bei fctType 20
# „Kesseltemperatur" – gemeint ist der eigene Fühlereingang des Moduls, nicht
# der Kessel dahinter. Ein kürzeres „Temperatur Ist" verschwiege, worum es
# geht, und wäre in keiner Unterlage nachschlagbar. Was der Fühler misst,
# erklärt der Hilfetext in `panel.py`.
ZSP_ENTITIES = [
    {"oid": "/0/7/0", "name": "Kesseltemperatur", "platform": "temperature"},
    {"oid": "/1/7/0", "name": "Kesseltemperatur Soll", "platform": "temperature"},
    {
        "oid": "/0/22/0",
        "name": "Pumpendrehzahl",
        "platform": "sensor",
        "unit": "%",
        "state_class": "measurement",
    },
]

# fctType -> entity definition table
# ---------------------------------------------------------------------------
# BioWIN Pelletskessel (fctType 9)
#
# **Ohne eigene Hardware zusammengestellt – aber nicht geraten.** Jeder
# Datenpunkt hier ist doppelt belegt:
#
# 1. Er steht in der `overview`-Ebene, die Windhager selbst in
#    `parameterLayer.json` für `default/9` führt – die Herstellerantwort auf
#    „was gehört auf die Titelseite des Kessels".
# 2. Er wird von einem öffentlichen BioWIN-II-Projekt an einer laufenden
#    Anlage tatsächlich abgefragt.
#
# Beide Listen decken sich bis auf die Reihenfolge. Was nur in einer von
# beiden steht, ist hier nicht aufgenommen.
#
# Der Unterschied zum PuroWIN steckt in den Wartungszählern: Der BioWIN führt
# sie unter `20/61..20/63`, der PuroWIN unter `39/91..39/93`. Wer das
# verwechselt, bekommt an beiden Anlagen leere Zeilen.
#
# Einheiten bleiben beim Brennstoffverbrauch bewusst offen: Die Anlage meldet
# sie selbst (kg oder t), und `helpers.messgroesse` macht daraus den
# Zählerstand. Ein fest eingetragener Wert wäre eine Behauptung über eine
# Anlage, die hier niemand hat.
# ---------------------------------------------------------------------------
BIOWIN_ENTITIES = [
    # --- Titelbild / Infoebene (read only) ---
    {"oid": "/0/7/0", "name": "Kesseltemperatur Ist", "platform": "temperature"},
    {"oid": "/1/7/0", "name": "Kesseltemperatur Soll", "platform": "temperature"},
    {
        "oid": "/0/9/0",
        "name": "Kesselleistung",
        "platform": "sensor",
        "unit": "%",
        "state_class": "measurement",
    },
    {"oid": "/0/11/0", "name": "Abgastemperatur", "platform": "temperature"},
    {"oid": "/2/1/0", "name": "Betriebsphase", "platform": "enum_sensor", "enum": "2/1"},
    {"oid": "/2/59/0", "name": "Betriebsart", "platform": "enum_sensor", "enum": "2/59"},
    {
        "oid": "/2/80/0",
        "name": "Brennerstarts",
        "platform": "sensor",
        "state_class": "total_increasing",
    },
    {
        "oid": "/2/81/0",
        "name": "Betriebsstunden",
        "platform": "sensor",
        "unit": "h",
        "state_class": "total_increasing",
    },
    {
        "oid": "/0/22/0",
        "name": "Pumpensteuerung Drehzahl",
        "platform": "sensor",
        "unit": "%",
        "state_class": "measurement",
    },
    # Restlaufzeiten: "measurement" wie beim PuroWIN – nur so entsteht ein
    # Langzeitverlauf, aus dem sich ablesen lässt, wann zuletzt gereinigt
    # wurde. Die Adressen sind die des BioWIN, nicht die des PuroWIN.
    {
        "oid": "/20/61/0",
        "name": "Laufzeit bis Reinigung",
        "platform": "sensor",
        "unit": "h",
        "state_class": "measurement",
        "icon": "mdi:broom",
    },
    {
        "oid": "/20/62/0",
        "name": "Laufzeit bis Hauptreinigung",
        "platform": "sensor",
        "unit": "h",
        "state_class": "measurement",
        "icon": "mdi:broom",
    },
    {
        "oid": "/20/63/0",
        "name": "Laufzeit bis Wartung",
        "platform": "sensor",
        "unit": "h",
        "state_class": "measurement",
        "icon": "mdi:wrench-clock",
    },
    {
        "oid": "/23/100/0",
        "name": "Brennstoffverbrauch seit Befüllung",
        "platform": "sensor",
        "icon": "mdi:sack",
    },
    {
        "oid": "/23/103/0",
        "name": "Brennstoffverbrauch gesamt",
        "platform": "sensor",
        "icon": "mdi:sack",
    },
    # Aus dem Abgleich zweier unabhängiger BioWIN-Quellen nachgetragen
    # (sessl3r BioWin102, FKW9 BioWIN2 Touch). Von 18 Adressen, die in beiden
    # stehen und hier fehlten, bleibt diese eine übrig: Der Rest steht in
    # Ebenen, die der Hersteller für diesen Funktionstyp nicht als Info- oder
    # Betreiberebene führt, oder ist ein Zeitwert, den die Erkennung ohnehin
    # anlegt. Ein fremder Abzug belegt, dass es eine Adresse *gibt* – nicht,
    # dass sie an diesen Funktionstyp gehört.
    {
        "oid": "/14/19/0",
        "name": "Betriebsart Zuführung",
        "platform": "enum_sensor",
        "icon": "mdi:transfer",
    },
]

FCT_ENTITY_MAP = {
    FCT_PUROWIN: PUROWIN_ENTITIES,
    FCT_BIOWIN: BIOWIN_ENTITIES,
    FCT_CLIMATE: CLIMATE_EXTRA_ENTITIES,
    FCT_BUFFER: BUFFER_ENTITIES,
    FCT_ZSP: ZSP_ENTITIES,
}

# Schaltpunkte, die die Anlage nicht anzeigt, aber aus zwei ihrer Werte
# hervorgehen. `bezug` ist der Sollwert, `hysterese` der Aufschlag, `anteil`
# sein Vorzeichen und Bruchteil.
SCHALTPUNKTE: tuple[dict[str, object], ...] = (
    {
        "fct_type": 16,
        "bezug": "1/15",
        "hysterese": "9/35",
        "anteil": -0.5,
        "name": "Letzte Einschalttemperatur",
        # Gegen diese Temperatur läuft die Schwelle: Fällt sie darunter,
        # beginnt die Ladung. Daraus entsteht zusätzlich der Abstand in Kelvin.
        "messwert": "21/65",
        "abstand_name": "Abstand bis Ladung",
    },
    {
        "fct_type": 16,
        "bezug": "9/57",
        "hysterese": "9/35",
        "anteil": 1.0,
        "name": "Anforderung liefert",
    },
)


# Wie weit es bis zum nächsten Schaltpunkt eines Verbrauchers ist. Alle vier
# Adressen liegen auf derselben Funktion; eine weitere Baureihe braucht eine
# Zeile, keinen Umbau.
VERBRAUCHER_ABSTAND: tuple[dict[str, object], ...] = (
    {
        "fct_type": 14,
        "ist": "0/4",
        "soll": "1/4",
        "hysterese": "5/0",
        "zustand": "1/66",
        "name": "Abstand Warmwasser",
    },
)

# Was der Rollenparameter eines Moduls nicht einschließt, ist nicht verdrahtet.
# `nur_bei` nennt je Adresse die Werte, bei denen sie dazugehört.
ROLLEN_FILTER: dict[int, dict[str, object]] = {
    FCT_BUFFER: {
        "quelle": "20/4",
        "nur_bei": {
            # Die Transferpumpe nennt allein Modulfunktion 0.
            "22/75": (0,),
            # Der zweite Pufferfühler kommt erst mit „TPE/TPA" dazu.
            "21/66": (3, 4, 5),
            # Bei 0 fördert die Transferpumpe, sonst die Pumpe zum Erzeuger.
            "1/22": (1, 2, 3, 4, 5),
        },
    },
}

# Welche Funktions-Ids an einem Knoten geprüft werden, der in `GET /1` keine
# gewöhnliche Funktion meldet. Bei einem Kessel ist es die 0; mehr zu prüfen
# hieße raten, und jeder Versuch kostet eine Anfrage an eine träge Steuerung.
FCT_IDS_UNGEMELDET: tuple[int, ...] = (0,)

# Wieviele Adressen einer kuratierten Tabelle mindestens zutreffen müssen,
# damit sie als Fingerabdruck zählt.
#
# **Ohne diese Schwelle gewinnt die kleinste Tabelle.** Der Typ einer nicht
# gemeldeten Funktion wird über den Anteil ihrer Adressen bestimmt, die sich
# wiederfinden. Eine Tabelle mit drei Einträgen erreicht schon bei zwei
# Treffern zwei Drittel – mehr als eine große Tabelle je erreicht, und ein
# Heizkreis wäre als Pumpenmodul erkannt worden. Umgekehrt reicht die reine
# Trefferzahl nicht: An einem BioWIN treffen mehr PuroWIN-Adressen zu als
# BioWIN-Adressen, weil die PuroWIN-Tabelle dreimal so groß ist.
FINGERABDRUCK_MIN_TREFFER = 5

# Fehler-/Meldetexte (aus Windhager ErrorTexte, lang=de)
ERROR_TEXTS: dict[int, str] = {
    1: "Primärluftklappe blockiert oder defekt.",
    3: "Sekundärluftklappe blockiert oder defekt.",
    5: "Entaschung / Rostrüttelung defekt oder steckt. Brennertopf reinigen.",
    6: "Motor Förderschnecke defekt",
    8: "Heizflächenreinigung defekt. Heizflächenreinigung überprüfen.",
    15: "Netzspannung nicht vorhanden",
    16: "Saugzuggebläse defekt. Gebläserad und Gebläsekasten reinigen.",
    17: "Saugzuggebläse steckt. Gebläserad reinigen.",
    18: "Saugzuggebläse instabil",
    37: "Klappe Pelletszuführung öffnet nicht. Klappe in Zuführeinheit überprüfen.",
    40: "Absperreinheit defekt. Absperreinheit der Pelletszuführung öffnet oder schließt nicht.",
    41: "Schalter Deckel Vorratsbehälter defekt",
    42: "Relais Saugturbine defekt. Netzstecker am Kessel abstecken.",
    57: "Brennerstörung",
    62: "Zuluftklappe defekt bzw. öffnet nicht. Klappe überprüfen.",
    71: "Sicherheits-/Notschalter offen",
    76: "Kesselfühler defekt. Kesselfühler und Anschlüsse prüfen.",
    78: "Thermocontrolfühler defekt",
    88: "O2-Sonde defekt. O2-Sonde und Anschlüsse überprüfen.",
    89: "O2-Sonde Heizung defekt",
    101: "TWE-Fühler defekt",
    103: "Kessel-Fühler defekt",
    104: "TPE-Fühler defekt",
    105: "TPA-Fühler defekt",
    107: "Saugzuggebläse steckt. Gebläserad reinigen.",
    114: "Weichen-/Pufferfühler defekt",
    115: "ZSK Kesselfühler defekt",
    128: "Keine Flammenbildung im Regelbetrieb. Kessel und Brenner reinigen.",
    129: "Maximale Ausbrandzeit überschritten",
    130: "Brennraumtemperatur zu gering",
    133: "Sicherheitstemperatur Abschaltung. Anlage und Fülldruck überprüfen.",
    135: "Übertemperatur am Schneckenrohr",
    144: "Sicherheitseinrichtung unterbrochen",
    155: "Wassermangelsicherung hat angesprochen. Anlagendruck überprüfen.",
    156: "Kein Unterdruck im Brennraum bzw. Sensor defekt.",
    171: "Maximale Anheizzeit überschritten. Brennertopf reinigen.",
    186: "Keine Kommunikation mit MES Modul",
    187: "Keine Kommunikation mit Feuerungsautomat",
    188: "Interner Fehler",
    189: "Keine Kommunikation mit Zusatzprint",
    191: "GAS-FA meldet Störung",
    194: "Keine Kommunikation mit einem Wärmeerzeuger",
    195: "Brennraumtür im Betrieb geöffnet",
    206: "Überwachung der Förderschnecke defekt",
    208: "Heizflächenreinigung defekt",
    226: "Keine Flammenbildung beim Zünden. Zündvorgang nicht erfolgreich",
    238: "Zuführung saugt keine Pellets an. Vorrat im Lagerraum und Zuführschlauch überprüfen.",
    239: "Sondenumschaltung defekt. Umschalteinheit überprüfen.",
    240: "Absperreinheit Pelletszuführung offen. Absperreinheit schließt nicht.",
    241: "Deckel Vorratsbehälter offen. Deckel schließen.",
    266: "Fülltürschalter schaltet nicht. Nicht mehr einheizen.",
    268: "Verkleidungstürschalter defekt",
    281: "Abgastemperaturfühler defekt",
    296: "Vorlauffühler defekt",
    297: "Sollwert wird nicht erreicht",
    299: "RT-Fühler defekt",
    300: "WW-Fühler defekt",
    320: "Notbetrieb! Reinigung",
    321: "Notbetrieb! Hauptreinigung",
    322: "Aschebox entleeren, Brennraum und Brennertopf reinigen.",
    324: "Wartung. Die Wartung ist Voraussetzung für die Gerätegarantie.",
    330: "Brennraumtemperatur zu gering. Hauptreinigung durchführen.",
    345: "Brennraumtür offen. Brenner gesperrt.",
    356: "Brennraumdruck nicht stabil",
    372: "Anheizauswertung: zu geringe Brennkammertemperatur beim Anheizen.",
    373: "Zu geringe Leistungsabnahme beim Anheizen.",
    374: "Anheizabbruch",
    375: "Anheizen bei zu hoher Kesseltemperatur",
    381: "Vorratsbehälter leer. Zeitprogramm sperrt Zuführung. Freigabezeit in Betreiberebene ändern.",
    382: "Klappe oder Schalter im Vorratsbehälter defekt.",
    387: "Fehler Kommunikation Feuerungsautomat. Reset-Taste mind. 5 s drücken.",
    390: "Notbetrieb! Kessel und Brenner reinigen. Reinigung bestätigen.",
    393: "Fehlermeldung E1",
    395: "Brennraum- oder Aschetür offen.",
    396: "Verkleidungstür schließen.",
    438: "Eine Zone im Lagerraum ist leer. Vorrat im Lagerraum überprüfen.",
    496: "Anlagen-Frostschutz aktiv",
    499: "Raum-Frostschutz aktiv",
    500: "WW-Frostschutz aktiv",
    504: "TP/TW Frostschutz aktiv",
    520: "Reinigung: Aschelade entleeren, Asche unter Nachheizfläche entfernen. Thermocontrolfühler reinigen.",
    521: "Hauptreinigung entsprechend der Bedienungsanleitung durchführen.",
    522: "Reinigung: Aschebox entleeren, Brennraum und Brennertopf reinigen.",
    523: "Hauptreinigung entsprechend der Bedienungsanleitung durchführen.",
    524: "Wartung. Die Wartung ist Voraussetzung für die Gerätegarantie.",
    581: "Vorratsbehälter ist fast leer. Pellets/Brennstoff nachfüllen.",
    582: "Vorratsbehälter ist leer. Nachfüllen. Brenner wird gesperrt.",
    590: "Kessel und Brenner reinigen. Reinigung bestätigen.",
    591: "Vorsicht beim Öffnen der Fülltür. Fülltür mind. 15 s anlüften.",
    595: "Tür offen",
}
