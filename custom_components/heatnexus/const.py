"""Constants for the Windhager Heater integration."""

DOMAIN = "heatnexus"
DEFAULT_USERNAME = "USER"

# ---------------------------------------------------------------------------
# Konfiguration (Einrichtungsdialog und Optionen)
# ---------------------------------------------------------------------------
CONF_LEVELS = "levels"
CONF_ENABLE_ADVANCED = "enable_advanced"
CONF_WRITABLE_ADVANCED = "writable_advanced"
CONF_UPDATE_INTERVAL = "update_interval"

# Bedienebenen der Anlage, wie sie auch das InfoWIN Touch kennt
LEVEL_INFO = "info"          # Messwerte und Zustände
LEVEL_OPERATE = "operate"    # Betreiberebene: Betriebswahl, Sollwerte, Programme
LEVEL_SERVICE = "service"    # Serviceebene: Heizkurve, Grenzwerte, Estrich
LEVEL_OEM = "oem"            # Werksebene: Verbrennungsregelung, Zündung, Antriebe

ALL_LEVELS = [LEVEL_INFO, LEVEL_OPERATE, LEVEL_SERVICE, LEVEL_OEM]
# Info und Betreiberebene sind der sinnvolle Standard; die Serviceebene wird
# mitgelesen, ihre Entities sind aber zunächst deaktiviert.
DEFAULT_LEVELS = [LEVEL_INFO, LEVEL_OPERATE, LEVEL_SERVICE]
# Diese Ebenen gelten als "fortgeschritten": Entities werden nur auf Wunsch
# aktiviert und nur auf Wunsch bedienbar gemacht.
ADVANCED_LEVELS = {LEVEL_SERVICE, LEVEL_OEM}

MIN_UPDATE_INTERVAL = 15
MAX_UPDATE_INTERVAL = 300
# Poll-Intervall (s). 30 s für spürbar schnellere Aktualisierung der Climate-/
# Sensorwerte; dank schlankem Poll-Set (nur aktive OIDs) gut vertretbar.
UPDATE_INTERVAL = 30

# Maximum parallel HTTP requests against the device
FETCH_CONCURRENCY = 8

# Timeout (s) für die einmalige Erstinitialisierung (Discovery + Metadaten
# aller Datenpunkte inkl. Serviceebene). Bewusst großzügig, da getrennt vom
# schnellen zyklischen Poll-Timeout.
INIT_TIMEOUT = 120

# Persistenter Discovery-Cache (überlebt HA-Neustart -> schneller Start).
DISCOVERY_STORE_VERSION = 1
# Cache nach dieser Zeit verwerfen und neu erkennen (fängt geänderte Anlagen ab).
DISCOVERY_MAX_AGE_DAYS = 30

# Function types (fctType) as reported by /api/1.0/lookup/1
FCT_CLIMATE = 14          # Heizkreis (UML+ / UMLZ)
FCT_BOILER_SWITCH = 15    # WFBPK Heizkreis/Umschaltung (meist locked)
FCT_BUFFER = 16           # B-PLMi Pufferspeicher
FCT_ZSP = 20              # ZSP Zirkulationspumpensteuerung
FCT_PUROWIN = 25          # PuroWIN Hackgutkessel

# Legacy names kept for compatibility
CLIMATE_FUNCTION_TYPE = FCT_CLIMATE
HEATER_FUNCTION_TYPE = 9

# ---------------------------------------------------------------------------
# Enum tables (generated from Windhager de-parameters.json, keyed by "gn/mn")
# Keys are integers because enums can contain gaps (e.g. 20/15 has no 5).
# ---------------------------------------------------------------------------
ENUMS: dict[str, dict[int, str]] = {
    "2/1": {  # Betriebsphase Kessel
        0: "Brenner gesperrt", 1: "Selbsttest", 2: "WE ausschalten",
        3: "Standby", 4: "Brenner AUS", 5: "Vorspülen", 6: "Zündphase",
        7: "Stabilisierung", 8: "Modulation", 9: "Gerät gesperrt",
        10: "Standby Sperrzeit", 11: "Gebläse AUS",
        12: "Verkleidungstür offen", 13: "Zündung bereit",
        14: "Abbruch Zündung", 15: "Anheizvorgang", 16: "Schichtladung",
        17: "Ausbrand",
    },
    "2/9": {  # Betriebsart (Statusanzeige)
        0: "Standby", 1: "Heizbetrieb", 2: "Absenkbetrieb", 3: "WW-Ladung",
        4: "Eco / Comfort", 5: "Urlaubsprogramm", 6: "Estrich",
        7: "Frostschutz", 8: "Standby", 9: "Handbetrieb", 10: "Testbetrieb",
        11: "Kaminkehrer", 12: "Brenner AUS", 13: "Brenner EIN",
        14: "Automatikkessel", 15: "FB-Kessel", 16: "Pufferspeicher",
        17: "Warmwasser Hygiene-Programm", 18: "Warmwasser Einmalladung",
        19: "Automatikbetrieb", 20: "Kühlen", 21: "Standby",
    },
    "2/59": {  # Betriebsart Zuführung/Kessel (Übersicht)
        0: "Ausgeschaltet", 1: "Abschaltvorgang",
        2: "Festbrennstoff-/Pufferbetrieb", 3: "Brennstoffzuführung in Betrieb",
        4: "Brennstoffzuführung", 5: "Kessel-Temperatur",
        6: "Brennstoffzuführung in Betrieb", 7: "Brennstoffzuführung",
        8: "Handbetrieb", 9: "Kaminkehrerfunktion", 10: "Aktorentest",
        11: "Installationsvorgang aktiv", 12: "Brennstoffzuführung in Betrieb",
        13: "Inbetriebnahme", 14: "Lagerraum befüllen", 15: "Lagerraum befüllen",
        16: "Grundeinstellungen",
    },
    "3/50": {  # Betriebswahl Heizkreis
        0: "Standby", 1: "Programm 1", 2: "Programm 2", 3: "Programm 3",
        4: "Heizbetrieb", 5: "Absenkbetrieb", 6: "WW-Betrieb",
        7: "Handbetrieb", 8: "Kühlen",
    },
    "20/15": {  # Betriebswahl Puffer (B-PLMi) - Achtung Lücke bei 5!
        0: "Standby", 1: "Automatikbetrieb", 2: "Festbrennstoffbetrieb",
        3: "Pufferbetrieb", 4: "Auto mit Zeitprogramm",
        6: "Handbetrieb", 7: "Kaminkehrerfunktion",
    },
    "7/12": {  # Drehzahlregelung
        0: "AUS", 1: "0..10V", 2: "PWM", 3: "PWM", 4: "ohne", 5: "LIN",
    },
    "14/19": {  # Betriebsart Zuführung
        0: "ausgeschaltet", 1: "ohne Zeitsteuerung",
        2: "mit Freigabezeit", 3: "mit Startzeit",
    },
    "38/126": {  # Gewählter Brennstoff
        0: "Hackgut normal", 1: "Hackgut feucht", 2: "Pellets",
        3: "Hackgut normal schlackend", 4: "Hackgut feucht schlackend",
    },
    "38/127": {  # Aktueller Brennstoff
        0: "Hackgut normal", 1: "Hackgut feucht", 2: "Pellets",
        3: "Hackgut normal schlackend", 4: "Hackgut feucht schlackend",
    },
    "39/94": {  # Reinigung bestätigen
        0: "Nein", 1: "Reinigung", 2: "Hauptreinigung", 3: "Wartung",
        4: "Hauptreinigung und Aschetonnen entleeren",
    },
    "43/34": {  # Sonde (Saugzuführung)
        0: "Aus", 1: "Ein", 2: "Leer",
    },
    "9/75": {  # Betriebswahl Kessel / Sonderfunktionen
        0: "AUS", 1: "EIN", 2: "Handbetrieb", 3: "Kaminkehrer",
        4: "Aktorentest", 5: "Inbetriebnahme", 6: "Serviceausbrand",
        7: "Lagerraum befüllen",
    },
    "39/76": {  # Vorratsbehälter Status
        0: "Fehler Vorratsbehälter", 1: "Vorratsbehälter leer",
        2: "Vorratsbehälter teilgefüllt", 3: "Vorratsbehälter voll",
    },
}

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

PUROWIN_ENTITIES = [
    # --- Infoebene / Übersicht (read only) ---
    {"oid": "/0/7/0",  "name": "Kesseltemperatur Ist", "platform": "temperature"},
    {"oid": "/1/7/0",  "name": "Kesseltemperatur Soll", "platform": "temperature"},
    {"oid": "/0/9/0",  "name": "Kesselleistung", "platform": "sensor", "unit": "%", "state_class": "measurement"},
    {"oid": "/0/11/0", "name": "Abgastemperatur", "platform": "temperature"},
    {"oid": "/0/45/0", "name": "Brennerkammertemperatur", "platform": "temperature"},
    {"oid": "/0/42/0", "name": "O2 Signal", "platform": "sensor", "unit": "%", "state_class": "measurement"},
    {"oid": "/2/1/0",  "name": "Betriebsphase", "platform": "enum_sensor", "enum": "2/1"},
    {"oid": "/2/59/0", "name": "Betriebsart", "platform": "enum_sensor", "enum": "2/59"},
    {"oid": "/2/80/0", "name": "Brennerstarts", "platform": "sensor", "state_class": "total_increasing"},
    {"oid": "/2/81/0", "name": "Betriebsstunden", "platform": "sensor", "unit": "h", "state_class": "total_increasing"},
    {"oid": "/39/91/0", "name": "Laufzeit bis Ascheentleerung", "platform": "sensor", "unit": "h"},
    {"oid": "/39/92/0", "name": "Laufzeit bis Hauptreinigung", "platform": "sensor", "unit": "h"},
    {"oid": "/39/93/0", "name": "Laufzeit bis Wartung", "platform": "sensor", "unit": "h"},
    {"oid": "/32/0/14", "name": "Störung aktiv", "platform": "binary_sensor", "device_class": "problem"},
    {"oid": "/0/97/0",  "name": "Alarmcode", "platform": "sensor", "category": "diagnostic"},
    {"oid": "/4/92/0",  "name": "Softwareversion", "platform": "string_sensor", "category": "diagnostic"},
    {"oid": "/39/61/0", "name": "Nennleistung", "platform": "sensor", "unit": "kW", "category": "diagnostic"},

    # --- Betreiberebene (operate, schreibbar) ---
    {"oid": "/39/94/0", "name": "Reinigung bestätigen", "platform": "select", "enum": "39/94", "category": "config"},
    {"oid": "/39/57/0", "name": "Aschetonne entleeren", "platform": "switch", "category": "config", "icon": "mdi:delete-empty"},
    {"oid": "/14/75/0", "name": "Korrektur Reinigungsintervall", "platform": "number",
     "unit": "%", "min": -50, "max": 50, "step": 10, "category": "config"},
    {"oid": "/14/19/0", "name": "Betriebsart Zuführung", "platform": "select", "enum": "14/19", "category": "config"},
    {"oid": "/14/11/0", "name": "Zuführung Freigabezeit Beginn", "platform": "time", "category": "config", "icon": "mdi:clock-start"},
    {"oid": "/14/10/0", "name": "Zuführung Freigabezeit Ende", "platform": "time", "category": "config", "icon": "mdi:clock-end"},
    {"oid": "/14/20/0", "name": "Zuführung Startzeit", "platform": "time", "category": "config", "icon": "mdi:clock-outline"},
    {"oid": "/40/69/0", "name": "Ascheaustragung Freigabezeit Beginn", "platform": "time", "category": "config", "icon": "mdi:clock-start"},
    {"oid": "/40/70/0", "name": "Ascheaustragung Freigabezeit Ende", "platform": "time", "category": "config", "icon": "mdi:clock-end"},
    {"oid": "/39/95/0", "name": "Brennstoffzuführung anfordern", "platform": "switch", "category": "config", "icon": "mdi:pine-tree-box"},
    {"oid": "/38/127/0", "name": "Aktueller Brennstoff", "platform": "enum_sensor", "enum": "38/127"},
    # Achtung: Wechsel wird erst nach Aus-/Einschalten am Hauptschalter wirksam
    {"oid": "/38/126/0", "name": "Gewählter Brennstoff", "platform": "select", "enum": "38/126", "category": "config"},
    {"oid": "/9/90/0",   "name": "Kaminkehrer", "platform": "switch", "category": "config", "icon": "mdi:account-hard-hat"},
    {"oid": "/10/110/0", "name": "Kaminkehrer Leistung", "platform": "number",
     "unit": "%", "min": 30, "max": 100, "step": 1, "category": "config"},

    # Sondenumschaltung (nur bei Saugzuführung mit Sonden vorhanden,
    # nicht vorhandene OIDs werden bei der Discovery automatisch entfernt)
    {"oid": "/43/34/0", "name": "Sonde 1", "platform": "select", "enum": "43/34", "category": "config"},
    {"oid": "/43/35/0", "name": "Sonde 2", "platform": "select", "enum": "43/34", "category": "config"},
    {"oid": "/43/36/0", "name": "Sonde 3", "platform": "select", "enum": "43/34", "category": "config"},
    {"oid": "/43/37/0", "name": "Sonde 4", "platform": "select", "enum": "43/34", "category": "config"},
    {"oid": "/43/38/0", "name": "Sonde 5", "platform": "select", "enum": "43/34", "category": "config"},
    {"oid": "/43/39/0", "name": "Sonde 6", "platform": "select", "enum": "43/34", "category": "config"},
    {"oid": "/43/40/0", "name": "Sonde 7", "platform": "select", "enum": "43/34", "category": "config"},
    {"oid": "/43/41/0", "name": "Sonde 8", "platform": "select", "enum": "43/34", "category": "config"},
    {"oid": "/43/79/0", "name": "Sonden zurücksetzen", "platform": "button",
     "press_value": "1", "category": "config", "icon": "mdi:restore"},
    {"oid": "/39/76/0", "name": "Vorratsbehälter Status", "platform": "enum_sensor", "enum": "39/76"},

    # Serviceausbrand: schreibt 6 auf Betriebswahl 9/75 (läuft ca. 1 h!)
    # Bestätigungsdialog im Dashboard per "confirmation:" an der Button-Karte.
    {"oid": "/9/75/0", "name": "Serviceausbrand starten", "platform": "button",
     "press_value": "6", "category": "config", "icon": "mdi:fire-alert"},
    {"oid": "/9/75/0", "name": "Betriebswahl Kessel", "platform": "enum_sensor",
     "enum": "9/75", "key_suffix": "status", "category": "diagnostic"},

    # Fehlertext zum Alarmcode (0/97). Das gepackte Roh-Meldungsregister
    # (/32/0/14) wurde entfernt – die lesbare Geräte-Meldung kommt jetzt aus
    # FE01msg ("<Gerät> Meldung"-Sensor, device_status).
    {"oid": "/0/97/0", "name": "Alarmtext", "platform": "error_sensor", "key_suffix": "text"},
]

CLIMATE_EXTRA_ENTITIES = [
    # --- Infoebene Heizkreis / Warmwasser (read only) ---
    {"oid": "/0/0/0",   "name": "Außentemperatur", "platform": "temperature"},
    {"oid": "/0/1/0",   "name": "Raumtemperatur Ist", "platform": "temperature"},
    {"oid": "/1/1/0",   "name": "Raumtemperatur Soll", "platform": "temperature"},
    {"oid": "/0/2/0",   "name": "Vorlauftemperatur Ist", "platform": "temperature"},
    {"oid": "/1/2/0",   "name": "Vorlauftemperatur Soll", "platform": "temperature"},
    {"oid": "/0/7/0",   "name": "Kesseltemperatur Ist", "platform": "temperature"},
    {"oid": "/1/7/0",   "name": "Kesseltemperatur Soll", "platform": "temperature"},
    {"oid": "/0/4/0",   "name": "Warmwasser Ist-Temperatur", "platform": "temperature"},
    {"oid": "/1/4/0",   "name": "Warmwasser Soll-Temperatur", "platform": "temperature"},
    {"oid": "/0/118/0", "name": "WW-Zirkulation Ist-Temperatur", "platform": "temperature"},
    {"oid": "/1/118/0", "name": "WW-Zirkulation Soll-Temperatur", "platform": "temperature"},
    {"oid": "/1/20/0",  "name": "Heizkreispumpe", "platform": "binary_sensor", "device_class": "running"},
    {"oid": "/1/21/0",  "name": "Mischer Stellwert", "platform": "sensor", "unit": "%", "state_class": "measurement"},
    {"oid": "/1/65/0",  "name": "WW-Zirkulationspumpe", "platform": "binary_sensor", "device_class": "running"},
    {"oid": "/1/66/0",  "name": "WW-Ladepumpe", "platform": "binary_sensor", "device_class": "running"},
    {"oid": "/2/9/0",   "name": "Betriebsart", "platform": "enum_sensor", "enum": "2/9"},

    # --- Betreiberebene (operate, schreibbar) ---
    {"oid": "/3/50/0", "name": "Betriebswahl", "platform": "select", "enum": "3/50", "category": "config"},
    {"oid": "/3/58/0", "name": "Behaglichkeitskorrektur", "platform": "number",
     "unit": "K", "min": -3.0, "max": 3.0, "step": 0.1, "category": "config"},
    {"oid": "/3/51/0", "name": "Raumtemperatur Heizbetrieb", "platform": "number",
     "unit": "°C", "min": 10, "max": 30, "step": 0.5, "category": "config", "device_class": "temperature"},
    {"oid": "/3/53/0", "name": "Raumtemperatur Absenkbetrieb", "platform": "number",
     "unit": "°C", "min": 10, "max": 30, "step": 0.5, "category": "config", "device_class": "temperature"},
    {"oid": "/5/51/0", "name": "WW Einmalladung Temperatur", "platform": "number",
     "unit": "°C", "min": 10, "max": 75, "step": 0.5, "category": "config", "device_class": "temperature"},
    {"oid": "/2/16/0", "name": "WW Einmalladung", "platform": "switch", "category": "config", "icon": "mdi:water-boiler"},
]

BUFFER_ENTITIES = [
    # --- Infoebene (read only) ---
    {"oid": "/21/65/0", "name": "Puffer oben Temperatur (TPE)", "platform": "temperature"},
    {"oid": "/21/66/0", "name": "Puffer unten Temperatur (TPA)", "platform": "temperature"},
    {"oid": "/0/7/0",   "name": "Kesseltemperatur", "platform": "temperature"},
    {"oid": "/0/8/0",   "name": "Rücklauf Temperatur", "platform": "temperature"},
    {"oid": "/1/8/0",   "name": "Rücklauf Sollwert", "platform": "temperature"},
    {"oid": "/1/22/0",  "name": "Pufferladepumpe Drehzahl", "platform": "sensor", "unit": "%", "state_class": "measurement"},
    {"oid": "/1/102/0", "name": "Mischer Kessel", "platform": "sensor", "unit": "%", "state_class": "measurement"},
    {"oid": "/2/9/0",   "name": "Betriebsart", "platform": "enum_sensor", "enum": "2/9"},
    {"oid": "/7/12/0",  "name": "Drehzahlregelung Modus", "platform": "enum_sensor", "enum": "7/12", "category": "diagnostic"},

    # --- Betreiberebene (operate, schreibbar) ---
    {"oid": "/20/15/0", "name": "Betriebswahl", "platform": "select", "enum": "20/15", "category": "config"},

    # --- Serviceebene (schreibbar, Gerät kann Schreibzugriff verweigern) ---
    {"oid": "/20/14/0", "name": "Pufferladepumpe min Drehzahl", "platform": "number",
     "unit": "%", "min": 10, "max": 100, "step": 1, "category": "config"},
    {"oid": "/20/22/0", "name": "Pufferladepumpe max Drehzahl", "platform": "number",
     "unit": "%", "min": 50, "max": 100, "step": 1, "category": "config"},
    {"oid": "/9/32/0",  "name": "Puffer Minimaltemperatur", "platform": "number",
     "unit": "°C", "min": 20, "max": 60, "step": 1, "category": "config", "device_class": "temperature"},
    {"oid": "/10/31/0", "name": "Puffer Maximaltemperatur", "platform": "number",
     "unit": "°C", "min": 60, "max": 100, "step": 1, "category": "config", "device_class": "temperature"},
    {"oid": "/20/28/0", "name": "Minimale Laufzeit Pufferladung", "platform": "number",
     "unit": "min", "min": 0, "max": 360, "step": 15, "category": "config"},
    {"oid": "/20/29/0", "name": "Laufzeitoptimierung Sollwert", "platform": "number",
     "unit": "°C", "min": 60, "max": 85, "step": 1, "category": "config", "device_class": "temperature"},
]

ZSP_ENTITIES = [
    {"oid": "/0/7/0",  "name": "Temperatur Ist", "platform": "temperature"},
    {"oid": "/1/7/0",  "name": "Temperatur Soll", "platform": "temperature"},
    {"oid": "/0/22/0", "name": "Pumpendrehzahl", "platform": "sensor", "unit": "%", "state_class": "measurement"},
]

# fctType -> entity definition table
FCT_ENTITY_MAP = {
    FCT_PUROWIN: PUROWIN_ENTITIES,
    FCT_CLIMATE: CLIMATE_EXTRA_ENTITIES,
    FCT_BUFFER: BUFFER_ENTITIES,
    FCT_ZSP: ZSP_ENTITIES,
}

# Fehler-/Meldetexte (aus Windhager ErrorTexte, lang=de)
ERROR_TEXTS: dict[int, str] = {
    1: 'Primärluftklappe blockiert oder defekt.',
    3: 'Sekundärluftklappe blockiert oder defekt.',
    5: 'Entaschung / Rostrüttelung defekt oder steckt. Brennertopf reinigen.',
    6: 'Motor Förderschnecke defekt',
    8: 'Heizflächenreinigung defekt. Heizflächenreinigung überprüfen.',
    15: 'Netzspannung nicht vorhanden',
    16: 'Saugzuggebläse defekt. Gebläserad und Gebläsekasten reinigen.',
    17: 'Saugzuggebläse steckt. Gebläserad reinigen.',
    18: 'Saugzuggebläse instabil',
    37: 'Klappe Pelletszuführung öffnet nicht. Klappe in Zuführeinheit überprüfen.',
    40: 'Absperreinheit defekt. Absperreinheit der Pelletszuführung öffnet oder schließt nicht.',
    41: 'Schalter Deckel Vorratsbehälter defekt',
    42: 'Relais Saugturbine defekt. Netzstecker am Kessel abstecken.',
    57: 'Brennerstörung',
    62: 'Zuluftklappe defekt bzw. öffnet nicht. Klappe überprüfen.',
    71: 'Sicherheits-/Notschalter offen',
    76: 'Kesselfühler defekt. Kesselfühler und Anschlüsse prüfen.',
    78: 'Thermocontrolfühler defekt',
    88: 'O2-Sonde defekt. O2-Sonde und Anschlüsse überprüfen.',
    89: 'O2-Sonde Heizung defekt',
    101: 'TWE-Fühler defekt',
    103: 'Kessel-Fühler defekt',
    104: 'TPE-Fühler defekt',
    105: 'TPA-Fühler defekt',
    107: 'Saugzuggebläse steckt. Gebläserad reinigen.',
    114: 'Weichen-/Pufferfühler defekt',
    115: 'ZSK Kesselfühler defekt',
    128: 'Keine Flammenbildung im Regelbetrieb. Kessel und Brenner reinigen.',
    129: 'Maximale Ausbrandzeit überschritten',
    130: 'Brennraumtemperatur zu gering',
    133: 'Sicherheitstemperatur Abschaltung. Anlage und Fülldruck überprüfen.',
    135: 'Übertemperatur am Schneckenrohr',
    144: 'Sicherheitseinrichtung unterbrochen',
    155: 'Wassermangelsicherung hat angesprochen. Anlagendruck überprüfen.',
    156: 'Kein Unterdruck im Brennraum bzw. Sensor defekt.',
    171: 'Maximale Anheizzeit überschritten. Brennertopf reinigen.',
    186: 'Keine Kommunikation mit MES Modul',
    187: 'Keine Kommunikation mit Feuerungsautomat',
    188: 'Interner Fehler',
    189: 'Keine Kommunikation mit Zusatzprint',
    191: 'GAS-FA meldet Störung',
    194: 'Keine Kommunikation mit einem Wärmeerzeuger',
    195: 'Brennraumtür im Betrieb geöffnet',
    206: 'Überwachung der Förderschnecke defekt',
    208: 'Heizflächenreinigung defekt',
    226: 'Keine Flammenbildung beim Zünden. Zündvorgang nicht erfolgreich',
    238: 'Zuführung saugt keine Pellets an. Vorrat im Lagerraum und Zuführschlauch überprüfen.',
    239: 'Sondenumschaltung defekt. Umschalteinheit überprüfen.',
    240: 'Absperreinheit Pelletszuführung offen. Absperreinheit schließt nicht.',
    241: 'Deckel Vorratsbehälter offen. Deckel schließen.',
    266: 'Fülltürschalter schaltet nicht. Nicht mehr einheizen.',
    268: 'Verkleidungstürschalter defekt',
    281: 'Abgastemperaturfühler defekt',
    296: 'Vorlauffühler defekt',
    297: 'Sollwert wird nicht erreicht',
    299: 'RT-Fühler defekt',
    300: 'WW-Fühler defekt',
    320: 'Notbetrieb! Reinigung',
    321: 'Notbetrieb! Hauptreinigung',
    322: 'Aschebox entleeren, Brennraum und Brennertopf reinigen.',
    324: 'Wartung. Die Wartung ist Voraussetzung für die Gerätegarantie.',
    330: 'Brennraumtemperatur zu gering. Hauptreinigung durchführen.',
    345: 'Brennraumtür offen. Brenner gesperrt.',
    356: 'Brennraumdruck nicht stabil',
    372: 'Anheizauswertung: zu geringe Brennkammertemperatur beim Anheizen.',
    373: 'Zu geringe Leistungsabnahme beim Anheizen.',
    374: 'Anheizabbruch',
    375: 'Anheizen bei zu hoher Kesseltemperatur',
    381: 'Vorratsbehälter leer. Zeitprogramm sperrt Zuführung. Freigabezeit in Betreiberebene ändern.',
    382: 'Klappe oder Schalter im Vorratsbehälter defekt.',
    387: 'Fehler Kommunikation Feuerungsautomat. Reset-Taste mind. 5 s drücken.',
    390: 'Notbetrieb! Kessel und Brenner reinigen. Reinigung bestätigen.',
    393: 'Fehlermeldung E1',
    395: 'Brennraum- oder Aschetür offen.',
    396: 'Verkleidungstür schließen.',
    438: 'Eine Zone im Lagerraum ist leer. Vorrat im Lagerraum überprüfen.',
    496: 'Anlagen-Frostschutz aktiv',
    499: 'Raum-Frostschutz aktiv',
    500: 'WW-Frostschutz aktiv',
    504: 'TP/TW Frostschutz aktiv',
    520: 'Reinigung: Aschelade entleeren, Asche unter Nachheizfläche entfernen. Thermocontrolfühler reinigen.',
    521: 'Hauptreinigung entsprechend der Bedienungsanleitung durchführen.',
    522: 'Reinigung: Aschebox entleeren, Brennraum und Brennertopf reinigen.',
    523: 'Hauptreinigung entsprechend der Bedienungsanleitung durchführen.',
    524: 'Wartung. Die Wartung ist Voraussetzung für die Gerätegarantie.',
    581: 'Vorratsbehälter ist fast leer. Pellets/Brennstoff nachfüllen.',
    582: 'Vorratsbehälter ist leer. Nachfüllen. Brenner wird gesperrt.',
    590: 'Kessel und Brenner reinigen. Reinigung bestätigen.',
    591: 'Vorsicht beim Öffnen der Fülltür. Fülltür mind. 15 s anlüften.',
    595: 'Tür offen',
}
