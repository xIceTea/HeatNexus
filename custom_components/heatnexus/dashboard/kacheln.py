"""Karten der Übersicht je Anlagenteil: Leitwert, Kennwerte, Puffersäule, Heizkreis.

Die Rolle eines Teils folgt seinen kanonischen Schlüsseln, nie dem Namen. Die
Beschriftungen sind deutsch und gehen danach durch das Wörterbuch der Anlage.
"""

from __future__ import annotations

from typing import Any

from ..const import LAUFPHASEN
from . import auswahl

LEITWERT = "custom:heatnexus-leitwert"
KENNWERTE = "custom:heatnexus-kennwerte"
PUFFER = "custom:heatnexus-puffer"

AKZENT = "#ff8a3d"
SPALTEN = 3
VOLLE_BREITE = {"columns": 12}

# Rollen in der Reihenfolge der Übersicht: Kessel, Puffer, Heizkreis, Warmwasser.
KESSEL = "kessel"
PUFFERSPEICHER = "puffer"
HEIZKREIS = "heizkreis"
WARMWASSER = "warmwasser"
ROLLEN = (KESSEL, PUFFERSPEICHER, HEIZKREIS, WARMWASSER)

SCHALTER = {"art": "schalter"}
GANZ = {"stellen": 0}

# Je Kennwert: kanonischer Schlüssel, Beschriftung, weitere Angaben der Zelle.
KESSEL_NEBEN = (
    ("boiler_power", "Leistung"),
    ("flue_gas_temperature", "Abgas"),
    ("return_temperature", "Rücklauf"),
)
KESSEL_WERTE = (
    ("combustion_chamber_temperature", "Brennkammer", {}),
    ("burner_starts", "Brennerstarts", GANZ),
    ("operating_hours", "Betriebsstunden", GANZ),
    ("maintenance_ash_hours", "Asche", {**GANZ, "warnung_unter": 20}),
    ("maintenance_cleaning_hours", "Reinigung", {**GANZ, "warnung_unter": 20}),
    ("maintenance_main_cleaning_hours", "Hauptreinigung", {**GANZ, "warnung_unter": 50}),
    ("maintenance_service_hours", "Wartung", {**GANZ, "warnung_unter": 50}),
)
HEIZKREIS_WERTE = (
    ("flow_temperature", "Vorlauf", {}),
    ("flow_temperature_target", "Vorlauf Soll", {}),
    ("room_temperature", "Raum", {}),
    ("mixer_position", "Mischer", GANZ),
    ("circuit_pump", "Pumpe", SCHALTER),
    ("dhw_temperature", "Warmwasser", {}),
)
WARMWASSER_WERTE = (
    ("dhw_temperature", "Warmwasser", {}),
    ("dhw_temperature_target", "Soll", {}),
    ("dhw_charge_pump", "Ladepumpe", SCHALTER),
    ("dhw_circulation_pump", "Zirkulation", SCHALTER),
)
PUFFER_FUEHLER = (("oben", "buffer_top", "Oben"), ("mitte", "buffer_middle", "Mitte"))
PUFFER_UNTEN = ("unten", "buffer_bottom", "Unten")


def werte_je_schluessel(teil: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Je kanonischem Schlüssel die erste Entität, die gerade einen Wert hat."""
    gefunden: dict[str, dict[str, Any]] = {}
    for e in teil["entitaeten"]:
        if (schluessel := e.get("schluessel")) and e["hat_wert"]:
            gefunden.setdefault(schluessel, e)
    return gefunden


def rolle(teil: dict[str, Any]) -> str | None:
    """Was ein Anlagenteil in der Übersicht ist, oder nichts."""
    werte = werte_je_schluessel(teil)
    if "operating_phase" in werte and "boiler_temperature" in werte:
        return KESSEL
    if "buffer_top" in werte:
        return PUFFERSPEICHER
    if auswahl.thermostate(teil):
        return HEIZKREIS
    if "dhw_temperature" in werte:
        return WARMWASSER
    return None


def _laufphasen(phase: dict[str, Any]) -> list[str]:
    """Die Zustandstexte, in denen der Brenner läuft – gewählt nach Zahlencode."""
    codes = LAUFPHASEN.get(phase.get("adresse") or "", frozenset())
    optionen = phase.get("optionen") or {}
    return [text for wert, text in sorted(optionen.items()) if int(wert) in codes]


def _kennwerte(
    werte: dict[str, dict[str, Any]], tabelle: tuple, titel: str | None = None
) -> list[dict[str, Any]]:
    """Kennwerte-Karte aus einer Tabelle; ohne einen Treffer keine."""
    zellen = []
    for schluessel, name, zusatz in tabelle:
        if e := werte.get(schluessel):
            zelle = {"name": name, "entity": e["entity_id"], **zusatz}
            if zusatz is SCHALTER:
                zelle |= {"an": "läuft", "aus": "aus"}
            zellen.append(zelle)
    if not zellen:
        return []
    karte: dict[str, Any] = {"type": KENNWERTE}
    if titel:
        karte["titel"] = titel
    return [{**karte, "spalten": SPALTEN, "werte": zellen, "grid_options": VOLLE_BREITE}]


def _kessel(teil: dict[str, Any], werte: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    phase = werte["operating_phase"]
    leitwert = {
        "type": LEITWERT,
        "ueberschrift": teil["name"],
        "zustand": phase["entity_id"],
        "gross": werte["boiler_temperature"]["entity_id"],
        "gross_name": "Kessel",
        "akzent": AKZENT,
        "aktiv": _laufphasen(phase),
        "neben": [
            {"name": name, "entity": werte[s]["entity_id"], "stellen": 0}
            for s, name in KESSEL_NEBEN
            if s in werte
        ],
        "grid_options": VOLLE_BREITE,
    }
    return [leitwert, *_kennwerte(werte, KESSEL_WERTE)]


def _puffer(teil: dict[str, Any], werte: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    karte: dict[str, Any] = {"type": PUFFER, "titel": teil["name"]}
    for feld, schluessel, name in (*PUFFER_FUEHLER, PUFFER_UNTEN):
        e = werte.get(schluessel)
        karte |= {feld: e["entity_id"] if e else None, f"name_{feld}": name}
    pumpe = werte.get("buffer_charge_pump")
    karte["neben"] = [{"name": "Ladepumpe", "entity": pumpe["entity_id"]}] if pumpe else []
    return [{**karte, "grid_options": VOLLE_BREITE}]


def _heizkreis(teil: dict[str, Any], werte: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    kachel = {
        "type": "tile",
        "entity": auswahl.thermostate(teil)[0]["entity_id"],
        "name": teil["name"],
        "vertical": False,
        "features_position": "bottom",
        "features": [{"type": "climate-preset-modes", "style": "dropdown"}],
        "grid_options": VOLLE_BREITE,
    }
    return [kachel, *_kennwerte(werte, HEIZKREIS_WERTE)]


def teilkarten(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Die Karten eines Anlagenteils nach seiner Rolle; ohne Rolle keine."""
    werte = werte_je_schluessel(teil)
    art = rolle(teil)
    if art == KESSEL:
        return _kessel(teil, werte)
    if art == PUFFERSPEICHER:
        return _puffer(teil, werte)
    if art == HEIZKREIS:
        return _heizkreis(teil, werte)
    if art == WARMWASSER:
        return _kennwerte(werte, WARMWASSER_WERTE, titel=teil["name"])
    return []


def anlagenkarten(anlage: dict[str, Any]) -> list[dict[str, Any]]:
    """Alle Karten einer Anlage, Kessel vor Puffer vor Heizkreis vor Warmwasser."""
    platz = {art: stelle for stelle, art in enumerate(ROLLEN)}
    teile = sorted(anlage["teile"], key=lambda t: platz.get(rolle(t) or "", len(ROLLEN)))
    return [karte for teil in teile for karte in teilkarten(teil)]
