"""Die Beispielanlage für die Bilder in README und Dokumentation.

Einmal beschrieben, dreifach benutzt: Standbild und Bewegtbild des Schaubilds
(`build_schaubild_beispiel.py`, `build_schaubild_animation.py`) und der
Rundgang durch die Oberfläche (`build_panel_rundgang.py`). Sonst zeigte das
README drei verschiedene Häuser.

Die Anlage entspricht einer üblichen Installation: Kessel, Puffer, Heizkreis
mit Warmwasser und Zirkulation – jeweils mit ihrer Pumpe, denn ohne Pumpe
zeichnet das Schaubild keine Förderrichtung, und dazu das, was man an einer
Anlage wirklich abliest und bedient.

**Erfundene Werte, echte Struktur.** Kein Datenpunkt hier stammt von einer
Anlage des Nutzers; die Adressen und Namen sind die der Geräte-Datenbank, die
Zahlen sind gewählt.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

WURZEL = Path(__file__).resolve().parent.parent
KOMPONENTE = WURZEL / "custom_components" / "heatnexus"

__all__ = [
    "KOMPONENTE",
    "STANDBILD",
    "TEILE",
    "WURZEL",
    "anlage",
    "karte",
    "schema_modul",
    "teil",
    "zustaende",
]


def schema_modul() -> ModuleType:
    """`schema.py` laden – es kommt ohne Home Assistant aus."""
    paket = "heatnexus_beispiel"
    if (fertig := sys.modules.get(f"{paket}.schema")) is not None:
        return fertig
    ersatz = ModuleType(paket)
    ersatz.__path__ = [str(KOMPONENTE)]
    sys.modules[paket] = ersatz
    spec = importlib.util.spec_from_file_location(f"{paket}.schema", KOMPONENTE / "schema.py")
    modul = importlib.util.module_from_spec(spec)
    sys.modules[f"{paket}.schema"] = modul
    spec.loader.exec_module(modul)
    return modul


def _eintrag(
    entity_id: str,
    name: str,
    *,
    zustand: str | None = None,
    einheit: str | None = None,
    kategorie: str | None = None,
    state_class: str | None = None,
    wert: float | None = None,
    attribute: dict | None = None,
) -> dict:
    """Eine Entität in der Form, die `dashboard._anlagen` liefert.

    ``zustand``, ``einheit`` und ``attribute`` liest nur der Rundgang: Sie
    füllen die nachgebildete Zustandstabelle von Home Assistant. Schaubild und
    Dashboard sehen sie nicht.
    """
    return {
        "entity_id": entity_id,
        "name": name,
        "kategorie": kategorie,
        "bereich": entity_id.split(".")[0],
        "hat_wert": zustand is not None,
        "wert": wert,
        "state_class": state_class,
        "schluessel": None,
        "zustand": zustand,
        "einheit": einheit,
        "attribute": attribute or {},
    }


def teil(name: str, fct: int, kennung: str, eintraege: list[dict]) -> dict:
    """Ein Anlagenteil mit seinen Entitäten."""
    return {
        "name": name,
        "id": kennung,
        "anlage_id": "steuerung",
        "fct_type": fct,
        "rang": 0,
        "symbol": "mdi:fire",
        "entitaeten": eintraege,
    }


TEILE = [
    teil(
        "PuroWIN",
        25,
        "geraet_kessel",
        [
            _eintrag(
                "sensor.kesseltemperatur_ist",
                "Kesseltemperatur Ist",
                zustand="72.4",
                einheit="°C",
                wert=72.4,
            ),
            _eintrag("sensor.kesselleistung", "Kesselleistung", zustand="38", einheit="%", wert=38),
            _eintrag("binary_sensor.kesselpumpe", "Kesselpumpe", zustand="on", wert=1),
            _eintrag("sensor.betriebsphase", "Betriebsphase", zustand="Leistungsbrand"),
            _eintrag(
                "sensor.abgastemperatur",
                "Abgastemperatur",
                zustand="142.0",
                einheit="°C",
                wert=142.0,
            ),
            _eintrag("sensor.aktueller_brennstoff", "Aktueller Brennstoff", zustand="Hackgut"),
            _eintrag("sensor.vorratsbehaelter", "Vorratsbehälter Status", zustand="voll"),
            _eintrag(
                "sensor.brennerstarts",
                "Brennerstarts",
                zustand="4128",
                state_class="total_increasing",
                wert=4128,
            ),
            _eintrag(
                "sensor.betriebsstunden",
                "Betriebsstunden",
                zustand="11840",
                einheit="h",
                state_class="total_increasing",
                wert=11840,
            ),
            _eintrag(
                "sensor.laufzeit_ascheentleerung",
                "Laufzeit bis Ascheentleerung",
                zustand="62",
                einheit="h",
                wert=62,
            ),
            _eintrag(
                "sensor.laufzeit_hauptreinigung",
                "Laufzeit bis Hauptreinigung",
                zustand="310",
                einheit="h",
                wert=310,
            ),
            _eintrag(
                "sensor.laufzeit_wartung",
                "Laufzeit bis Wartung",
                zustand="780",
                einheit="h",
                wert=780,
            ),
            _eintrag(
                "select.gewaehlter_brennstoff",
                "Gewählter Brennstoff",
                zustand="Hackgut",
                attribute={"options": ["Hackgut", "Pellets", "Späne"]},
            ),
            _eintrag("button.reinigung_durchgefuehrt", "Reinigung durchgeführt", zustand="unknown"),
            _eintrag(
                "button.hauptreinigung_durchgefuehrt",
                "Hauptreinigung durchgeführt",
                zustand="unknown",
            ),
            _eintrag("button.wartung_durchgefuehrt", "Wartung durchgeführt", zustand="unknown"),
            _eintrag("button.serviceausbrand", "Serviceausbrand starten", zustand="unknown"),
            _eintrag(
                "sensor.meldung_klartext",
                "Meldung Klartext",
                zustand="Kein Fehler",
                kategorie="diagnostic",
                attribute={"stoerung_aktiv": False},
            ),
        ],
    ),
    teil(
        "B-PLMi PUFFER",
        16,
        "geraet_puffer",
        [
            _eintrag(
                "sensor.puffer_oben",
                "Puffer oben Temperatur (TPE)",
                zustand="68.1",
                einheit="°C",
                wert=68.1,
            ),
            _eintrag(
                "sensor.puffer_unten",
                "Puffer unten Temperatur (TPA)",
                zustand="42.7",
                einheit="°C",
                wert=42.7,
            ),
            _eintrag("binary_sensor.pufferladepumpe", "Pufferladepumpe", zustand="on", wert=1),
        ],
    ),
    teil(
        "UMLZ HEIZKREIS",
        14,
        "geraet_heizkreis",
        [
            _eintrag(
                "climate.umlz_heizkreis",
                "UMLZ HEIZKREIS",
                zustand="heat",
                attribute={
                    "current_temperature": 21.5,
                    "temperature": 21.0,
                    "min_temp": 5,
                    "max_temp": 30,
                    "hvac_modes": ["heat", "off"],
                    "preset_mode": "2",
                    "preset_modes": ["0", "1", "2", "3", "4", "5", "6", "7"],
                    "friendly_name": "UMLZ HEIZKREIS",
                },
            ),
            _eintrag(
                "sensor.aussentemperatur", "Außentemperatur", zustand="2.4", einheit="°C", wert=2.4
            ),
            _eintrag(
                "sensor.vorlauftemperatur_ist",
                "Vorlauftemperatur Ist",
                zustand="45.0",
                einheit="°C",
                wert=45.0,
            ),
            _eintrag(
                "sensor.raumtemperatur_ist",
                "Raumtemperatur Ist",
                zustand="21.5",
                einheit="°C",
                wert=21.5,
            ),
            _eintrag("binary_sensor.heizkreispumpe", "Heizkreispumpe", zustand="on", wert=1),
            _eintrag(
                "select.betriebswahl",
                "Betriebswahl",
                zustand="Programm 1",
                attribute={
                    "options": [
                        "Standby",
                        "Programm 1",
                        "Programm 2",
                        "Heizbetrieb",
                        "Absenkbetrieb",
                        "WW-Betrieb",
                    ]
                },
            ),
            _eintrag("sensor.betriebsart", "Betriebsart", zustand="Heizbetrieb"),
            _eintrag(
                "sensor.heizprogramm",
                "Heizprogramm 1",
                zustand="aktiv",
                attribute={
                    "blocks": [
                        {
                            "weekdays": ["mo", "di", "mi", "do", "fr"],
                            "switchPoints": [
                                {"time": "05:30", "value": 21.0},
                                {"time": "22:00", "value": 18.0},
                            ],
                        },
                        {
                            "weekdays": ["sa", "so"],
                            "switchPoints": [
                                {"time": "07:00", "value": 21.5},
                                {"time": "23:00", "value": 18.0},
                            ],
                        },
                    ]
                },
            ),
            _eintrag(
                "number.uebersteuerung_temperatur",
                "Temperatur",
                zustand="21.0",
                einheit="°C",
                wert=21.0,
                attribute={"min": 5, "max": 30, "step": 0.5},
            ),
            _eintrag(
                "number.uebersteuerung_dauer",
                "Dauer",
                zustand="180",
                einheit="min",
                wert=180,
                attribute={"min": 0, "max": 600, "step": 10},
            ),
            # Warmwasser und Zirkulation hängen als Datenpunkte am Heizkreis.
            _eintrag(
                "sensor.ww_temperatur",
                "WW-Temperatur Aktueller Wert",
                zustand="51.2",
                einheit="°C",
                wert=51.2,
            ),
            _eintrag(
                "number.ww_temperatur_sollwert",
                "WW-Temperatur Sollwert",
                zustand="49.5",
                einheit="°C",
                wert=49.5,
                attribute={"min": 10, "max": 65, "step": 0.5},
            ),
            _eintrag("binary_sensor.ww_ladepumpe", "WW-Ladepumpe", zustand="off", wert=0),
            _eintrag("switch.ww_einmalladung", "WW Einmalladung", zustand="off", wert=0),
            _eintrag(
                "number.ww_einmalladung_temperatur",
                "WW Einmalladung Temperatur",
                zustand="65.0",
                einheit="°C",
                wert=65.0,
                attribute={"min": 10, "max": 70, "step": 0.5},
            ),
            _eintrag(
                "sensor.ww_zirkulation_ist",
                "WW-Zirkulation Ist-Temperatur",
                zustand="38.6",
                einheit="°C",
                wert=38.6,
            ),
            _eintrag(
                "binary_sensor.ww_zirkulationspumpe", "WW-Zirkulationspumpe", zustand="on", wert=1
            ),
            _eintrag("sensor.ww_kreis", "WW-Kreis", zustand="1", wert=1),
        ],
    ),
]


def anlage() -> dict:
    """Die Beispielanlage als Ganzes, wie `dashboard._anlagen` sie liefert."""
    return {
        "id": "anlage_heizhaus",
        "name": "Heizhaus",
        "kesselart": "hackgut",
        "kesselwert": "leistung",
        "teile": TEILE,
    }


def zustaende(ueberschreiben: dict[str, dict] | None = None) -> dict:
    """Die Zustandstabelle von Home Assistant, nachgebildet.

    ``ueberschreiben`` setzt einzelne Zustände für ein einzelnes Bild – so
    entsteht aus derselben Anlage einmal der ruhige Betrieb und einmal die
    anliegende Störung.
    """
    tabelle: dict[str, dict] = {}
    for anlagenteil in TEILE:
        for eintrag in anlagenteil["entitaeten"]:
            attribute = {"friendly_name": eintrag["name"], **eintrag["attribute"]}
            if eintrag["einheit"]:
                attribute["unit_of_measurement"] = eintrag["einheit"]
            tabelle[eintrag["entity_id"]] = {
                "entity_id": eintrag["entity_id"],
                "state": eintrag["zustand"] if eintrag["zustand"] is not None else "unknown",
                "attributes": attribute,
            }
    for kennung, geaendert in (ueberschreiben or {}).items():
        eintrag = tabelle.setdefault(
            kennung, {"entity_id": kennung, "state": "unknown", "attributes": {}}
        )
        eintrag["state"] = geaendert.get("state", eintrag["state"])
        eintrag["attributes"] = {**eintrag["attributes"], **geaendert.get("attributes", {})}
    return tabelle


# Werte für das Standbild des Schaubilds.
STANDBILD = {
    "sensor.kesseltemperatur_ist": "72,4 °C",
    "sensor.kesselleistung": "38 %",
    "sensor.puffer_oben": "68,1 °C",
    "sensor.puffer_unten": "42,7 °C",
    "sensor.vorlauftemperatur_ist": "45,0 °C",
    "sensor.raumtemperatur_ist": "21,5 °C",
    "sensor.ww_temperatur": "51,2 °C",
    "sensor.ww_zirkulation_ist": "38,6 °C",
}


def karte() -> dict:
    """Das Schaubild der Beispielanlage, so wie es die Anlage bekäme."""
    ergebnis = schema_modul().anlagenschema(TEILE)
    if not ergebnis:
        raise SystemExit("Die Beispielanlage ergibt kein Schaubild.")
    return ergebnis
