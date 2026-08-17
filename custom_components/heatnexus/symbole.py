"""Symbole je Anlagenteil und je Datenpunkt.

Eine Stelle für alle Oberflächen: Dashboard, Panel und Karte zeigen dasselbe
Symbol für dieselbe Sache. Ohne Bezug auf Home Assistant.
"""

from __future__ import annotations

import re
from typing import Any

# Symbol je Funktionstyp, für Überschriften und als Rückfall einer Zeile.
FCT_SYMBOL: dict[int, str] = {
    25: "mdi:fire",
    9: "mdi:fire",
    10: "mdi:fire",
    7: "mdi:heat-pump",
    26: "mdi:heat-pump",
    27: "mdi:heat-pump",
    6: "mdi:fire",
    8: "mdi:heating-coil",
    4: "mdi:layers-triple",
    15: "mdi:valve",
    16: "mdi:storage-tank",
    21: "mdi:storage-tank",
    24: "mdi:pump",
    1: "mdi:radiator",
    14: "mdi:radiator",
    2: "mdi:water-boiler",
    5: "mdi:solar-power-variant",
    20: "mdi:pump",
}
SYMBOL_UNBEKANNT = "mdi:heating-coil"

# Je Zeile: Muster, kanonische Schlüssel, Symbol. Der Schlüssel gewinnt, das
# Muster bleibt der Rückfall – die Namen der Anlage hängen an der Sprache, die
# Adresse eines Datenpunkts nicht.
WERT_SYMBOLE: tuple[tuple[re.Pattern[str], tuple[str, ...], str], ...] = (
    (re.compile(r"betriebsphase", re.IGNORECASE), ("operating_phase",), "mdi:state-machine"),
    (
        re.compile(r"^laufzeit aktuell$", re.IGNORECASE),
        ("operating_phase_runtime",),
        "mdi:timer-play-outline",
    ),
    (
        re.compile(r"^laufzeit heute$", re.IGNORECASE),
        ("operating_phase_runtime_today",),
        "mdi:timer-outline",
    ),
    (
        re.compile(r"laufzeit bis ascheentleerung", re.IGNORECASE),
        ("maintenance_ash_hours",),
        "mdi:delete-clock-outline",
    ),
    (
        re.compile(r"laufzeit bis reinigung", re.IGNORECASE),
        ("maintenance_cleaning_hours",),
        "mdi:broom",
    ),
    (re.compile(r"kesseltemperatur", re.IGNORECASE), ("boiler_temperature",), "mdi:fire"),
    (re.compile(r"kesselleistung", re.IGNORECASE), ("boiler_power",), "mdi:fire"),
    (
        re.compile(r"brenn(er)?kammertemperatur", re.IGNORECASE),
        ("combustion_chamber_temperature",),
        "mdi:fireplace",
    ),
    (re.compile(r"abgastemperatur", re.IGNORECASE), ("flue_gas_temperature",), "mdi:smoke"),
    (re.compile(r"brennstoff", re.IGNORECASE), ("fuel_current", "fuel_selected"), "mdi:sack"),
    (re.compile(r"vorratsbeh", re.IGNORECASE), ("fuel_storage_status",), "mdi:battery-70"),
    (
        re.compile(r"brennerstarts", re.IGNORECASE),
        ("burner_starts", "burner_starts_today"),
        "mdi:restart",
    ),
    (
        re.compile(r"betriebsstunden", re.IGNORECASE),
        ("operating_hours", "operating_hours_today"),
        "mdi:clock-outline",
    ),
    (
        re.compile(r"puffer (oben|unten|mitte)", re.IGNORECASE),
        ("buffer_top", "buffer_bottom"),
        "mdi:storage-tank",
    ),
    (
        re.compile(r"zirkulation", re.IGNORECASE),
        ("dhw_circulation_pump",),
        "mdi:reload",
    ),
    (
        re.compile(r"warmwasser|\bww[- ]temperatur", re.IGNORECASE),
        ("dhw_temperature",),
        "mdi:water-boiler",
    ),
    (
        re.compile(r"raumtemperatur", re.IGNORECASE),
        ("room_temperature", "room_temperature_target"),
        "mdi:home-thermometer",
    ),
    (re.compile(r"vorlauftemperatur", re.IGNORECASE), ("flow_temperature",), "mdi:radiator"),
    (re.compile(r"r(ü|ue)cklauf", re.IGNORECASE), ("return_temperature",), "mdi:pipe"),
    (
        re.compile(r"au(ß|ss)entemperatur", re.IGNORECASE),
        ("outdoor_temperature",),
        "mdi:thermometer",
    ),
    (re.compile(r"betriebswahl", re.IGNORECASE), ("mode_selection",), "mdi:tune"),
    (re.compile(r"^betriebsart", re.IGNORECASE), ("operating_mode",), "mdi:tune"),
    (
        re.compile(r"pumpe|pumpendrehzahl", re.IGNORECASE),
        ("circuit_pump", "dhw_charge_pump", "pump_speed"),
        "mdi:pump",
    ),
    (re.compile(r"mischer", re.IGNORECASE), (), "mdi:valve"),
    (re.compile(r"analog.*sollwert", re.IGNORECASE), ("analog_setpoint",), "mdi:thermometer-alert"),
    (re.compile(r"reinigung", re.IGNORECASE), (), "mdi:broom"),
    (re.compile(r"wartung", re.IGNORECASE), (), "mdi:wrench-outline"),
    (re.compile(r"st(ö|oe)rung|meldung", re.IGNORECASE), (), "mdi:message-alert-outline"),
    (re.compile(r"zeitprogramm|programm", re.IGNORECASE), (), "mdi:calendar-clock"),
    (re.compile(r"druck", re.IGNORECASE), (), "mdi:gauge"),
    (re.compile(r"temperatur", re.IGNORECASE), (), "mdi:thermometer"),
)


def symbol_je_fct(fct_type: Any) -> str:
    """Symbol des Anlagenteils; Unbekanntes bekommt die Heizschlange."""
    try:
        return FCT_SYMBOL.get(int(fct_type), SYMBOL_UNBEKANNT)
    except (TypeError, ValueError):
        return SYMBOL_UNBEKANNT


def symbol_fuer_wert(eintrag: dict[str, Any], fct_type: Any = None) -> str:
    """Symbol eines Datenpunkts, sonst das seines Anlagenteils."""
    schluessel = eintrag.get("schluessel")
    if schluessel:
        for _muster, schluesselliste, symbol in WERT_SYMBOLE:
            if schluessel in schluesselliste:
                return symbol
    name = eintrag.get("name") or ""
    for muster, _schluesselliste, symbol in WERT_SYMBOLE:
        if muster.search(name):
            return symbol
    return symbol_je_fct(fct_type)
