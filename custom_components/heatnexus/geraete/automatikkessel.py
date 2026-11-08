"""Automatik- und Zusatzkessel (fctType 10).

Ohne kuratierte Tabelle: Alles kommt aus den Menü-Ebenen der Anlage. Die
Übersichtsebene des Herstellers hebt Kesseltemperatur und Betriebsart auf info.
"""

from __future__ import annotations

from . import statuszeilen

FCT_TYPE = 10
MODELL = "Automatik-/Zusatzkessel"
# Geräteklasse aus der `programId`. Die Klasse 2009 ist der LogWIN.
MODELLE_JE_KLASSE: dict[str, str] = {"2009": "LogWIN Holzvergaserkessel"}
RANG = 14
SYMBOL = "mdi:fire"
SCHAUBILD = "kessel"

STATUSZEILEN = statuszeilen.KESSEL
EXTRA_OIDS: tuple[str, ...] = ()
KESSELART: str | None = None

# Namen, die erst im Zusammenhang dieser Baureihe eindeutig sind.
# Der Kesselmischer heißt in der Tabelle wie der Heizkreismischer.
NAMEN: dict[str, str] = {
    "20/108": "Betriebszustand",
    "43/20": "Kaminkehrer Restzeit",
    "0/7": "Kesseltemperatur Ist",
    "58/115": "Mischer Wärmeerzeuger",
    # „Gerätetyp" heißt auch 12/38; 39/61 meldet die Leistung in kW.
    "39/61": "Nennleistung",
    "43/103": "Wärmemengenzähler Auswahl",
    "12/105": "Elektrische Zündung",
    "46/103": "Zündzeit Vorgabe",
    "46/104": "Zündmodus",
}

TABELLEN: dict[str, dict[int, str]] = {
    "46/104": {0: "Keine Zündung", 1: "Sofort", 2: "Automatisch", 3: "Sperrzeit", 4: "Fern"},
}

NUR_BUS: tuple[str, ...] = ()

# Zündung des LogWIN 2025 über die Zündoption `46/100`. Bedienbar nur bei
# eingeschalteter elektrischer Zündung (`12/105`) und in Standby, Zündphase oder
# „Zündung bereit" (`2/1` = 3, 6, 13); ein brennender Kessel wird nicht gezündet.
_zuendbereit = {"12/105": ("1",), "2/1": ("3", "6", "13")}
# Abbrechen geht nur, solange ein Zündauftrag läuft (`46/104` sofort, automatisch, Sperrzeit).
_zuendung_laeuft = {**_zuendbereit, "46/104": ("1", "2", "3")}
_nachlesen = ("46/104", "2/1")


def _zuendtaste(name: str, wert: str, endung: str, icon: str, freigabe: dict) -> dict:
    return {
        "oid": "/46/100/0",
        "name": name,
        "platform": "button",
        "press_value": wert,
        "key_suffix": endung,
        "klassen": ("2009",),
        "freigabe": freigabe,
        "nachlesen": _nachlesen,
        "category": "config",
        "icon": icon,
    }


ENTITAETEN: list[dict] = [
    _zuendtaste("Sofort zünden", "2", "zuenden_sofort", "mdi:fire", _zuendbereit),
    _zuendtaste("Automatisch zünden", "4", "zuenden_automatisch", "mdi:fire-circle", _zuendbereit),
    # Sperren bis zu Datum und Uhrzeit, die vorher an `46/102` und `46/101` stehen.
    _zuendtaste("Zündung sperren bis", "3", "zuendung_sperren", "mdi:fire-off", _zuendbereit),
    _zuendtaste(
        "Zündung abbrechen", "0", "zuendung_abbrechen", "mdi:close-circle", _zuendung_laeuft
    ),
    {
        "oid": "/46/101/0",
        "name": "Zündung um",
        "platform": "time",
        "klassen": ("2009",),
        "freigabe": {"12/105": ("1",)},
        "category": "config",
        "icon": "mdi:clock-outline",
    },
    {
        "oid": "/46/102/0",
        "name": "Zündung am",
        "platform": "date",
        "klassen": ("2009",),
        "freigabe": {"12/105": ("1",)},
        "category": "config",
        "icon": "mdi:calendar",
    },
]
