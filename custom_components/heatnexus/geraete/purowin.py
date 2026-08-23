"""PuroWIN Hackgutkessel (fctType 25).

Modellname, Rang, Symbol, Schaubildteil und die kuratierte
Datenpunkttabelle dieser Baureihe.
"""

from __future__ import annotations

FCT_TYPE = 25
MODELL = "PuroWIN Hackgutkessel"
RANG = 10
SYMBOL = "mdi:fire"
SCHAUBILD = "kessel"

# Störcode, Softwarestand und die Lagerraumbefüllung stehen in keiner
# Bedienebene; das InfoWIN Touch zeigt sie trotzdem an.
EXTRA_OIDS: tuple[str, ...] = ("0/97", "4/92", "39/107", "39/5")

# Was diese Baureihe nur über den LON-Bus hergibt. Leer: Ihre Netzwerknamen
# tragen nichts bei, was nicht schon als Datenpunkt dasteht.
KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
NAMEN: dict[str, str] = {}

NUR_BUS: tuple[str, ...] = ()

ENTITAETEN: list[dict] = [
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
    # Betriebswahl 9/75 kennt mehrere Eingriffe (6 Serviceausbrand, 7
    # Lagerraum befüllen). Je Eingriff eine eigene Taste: In einer Auswahlliste
    # liegt der Serviceausbrand einen Fehlgriff vom Bunkerbefüllen entfernt.
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
    # Die Kaminkehrerfunktion gehört zu „Kaminkehrer Leistung" und
    # „Kaminkehrer": Sie hält die eingestellte Leistung, damit die Abgasmessung
    # unter festen Bedingungen läuft, und zählt die Restzeit herunter.
    {
        "oid": "/9/75/0",
        "name": "Kaminkehrer starten",
        "platform": "button",
        "press_value": "3",
        "key_suffix": "kaminkehrer",
        "category": "config",
        "icon": "mdi:account-hard-hat",
    },
    # Der Hersteller beendet die Messung mit einer Abbruchtaste oder nach
    # 60 min von selbst. Der Abbruch ist die Betriebswahl zurück auf EIN.
    {
        "oid": "/9/75/0",
        "name": "Kaminkehrer beenden",
        "platform": "button",
        "press_value": "1",
        "key_suffix": "kaminkehrer_aus",
        "category": "config",
        "icon": "mdi:stop-circle-outline",
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
    # „Reinigung bestätigen" (39/94) ist am Gerät eine Auswahlliste aus vier
    # Arbeiten. Je Arbeit eine eigene Taste ist eindeutig, eine Liste lädt zum
    # Fehlgriff ein.
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
