"""Helper functions for Windhager integration.

Dieses Modul kommt bewusst ohne aiohttp und ohne Home Assistant aus: Was hier
steht, lässt sich lokal prüfen, auch wenn keine der beiden Umgebungen
installiert ist. Deshalb liegen die reinen Umrechnungen hier und nicht im
Client.
"""

from __future__ import annotations

import logging
from typing import Any

from .const import EINHEITEN, POLL_ZIEL_SEKUNDEN, UPDATE_INTERVAL, ZAEHLER_WOERTER

_LOGGER = logging.getLogger(__name__)


def reihenfolge_mischen(basis: list[str], rest: list[str]) -> list[str]:
    """Zwei Reihenfolgen zusammenführen: ``basis`` gilt, ``rest`` füllt auf.

    Was in ``basis`` steht, behält seinen Platz. Alles, was nur in ``rest``
    steht, wird dort eingefügt, wo es nach ``rest`` hingehört: direkt hinter
    dem nächsten Vorgänger, der bereits einen Platz hat. Hat es keinen, kommt
    es nach vorn.
    """
    ergebnis = list(basis)
    for stelle, eintrag in enumerate(rest):
        if eintrag in ergebnis:
            continue
        ziel = 0
        for vorheriger in reversed(rest[:stelle]):
            if vorheriger in ergebnis:
                ziel = ergebnis.index(vorheriger) + 1
                break
        ergebnis.insert(ziel, eintrag)
    return ergebnis


def ordnung_anwenden(standard: list[str], gespeichert: list[str]) -> list[str]:
    """Eine gespeicherte Reihenfolge auf das anwenden, was es wirklich gibt.

    Gebraucht wird das für die selbst gewählte Anordnung der Karten in der
    Oberfläche. **Ein neu erkanntes Anlagenteil darf sie nicht zerreißen:**
    Gespeichert ist nur die Reihenfolge bekannter Kennungen; was neu
    dazukommt, landet an der Stelle, an der es von Haus aus stünde, und nicht
    am Ende. Kennungen, die es nicht mehr gibt, fallen still weg.

    Dieselbe Rechnung steht als ``ordnungAnwenden`` in
    ``frontend/heatnexus-panel.js``; ``tests/test_anordnung.py`` hält beide
    Fassungen gegeneinander.
    """
    vorhanden = set(standard)
    return reihenfolge_mischen([e for e in gespeichert if e in vorhanden], standard)


def parse_value(value: Any, as_type: type = float, oid: str | None = None) -> Any | None:
    """Safely parse a value with error handling."""
    if value is None:
        return None
    try:
        if as_type is int:
            return int(float(value))
        return as_type(value)
    except (ValueError, TypeError):
        _LOGGER.debug("Invalid value %r for %s", value, oid)
        return None


# Schreibschutz macht aus einer bedienbaren Entität ihre nur-lesende
# Entsprechung.
READONLY_FALLBACK = {
    "number": "sensor",
    "select": "enum_sensor",
    "switch": "binary_sensor",
    "time": "string_sensor",
}


def lesetyp(typ: str, einheit: str | None) -> str:
    """Nur-lesende Entsprechung einer bedienbaren Entität.

    Eine Temperatur bleibt dabei eine Temperatur: Fiele sie auf den
    allgemeinen Zahlensensor zurück, verlöre sie Geräteklasse, Statistik und
    Anzeigegenauigkeit. Bei einer Anlage, die fast jeden Wert als schreibbaren
    Zahlenbereich meldet, trifft das die halbe Liste – auf der Testanlage 57
    °C-Werte, sobald die Serviceebene nicht bedienbar ist (Standard).
    """
    if typ == "number" and (einheit or "").strip() == "°C":
        return "temperature"
    # Ein „Schalter" mit Einheit (z.B. Kaminkehrer 9/90 in min) ist in
    # Wahrheit ein Zähler -> normaler Sensor.
    if typ == "switch" and einheit:
        return "sensor"
    return READONLY_FALLBACK[typ]


def poll_takte(intervall: int | None) -> dict[str, int]:
    """Wie viele Durchläufe eine Poll-Klasse aussetzt.

    Der Takt hängt am eingestellten Abfrageintervall: „alle 15 Minuten" muss
    bei 30 s jeden 30. Durchlauf bedeuten, bei 300 s jeden dritten. Eine feste
    Vielfache stimmte nur bei der Voreinstellung – bei 300 s wären daraus
    zweieinhalb Stunden geworden.
    """
    takt = max(1, int(intervall or UPDATE_INTERVAL))
    return {klasse: max(1, round(ziel / takt)) for klasse, ziel in POLL_ZIEL_SEKUNDEN.items()}


def _nachkommastellen(schritt: Any) -> int | None:
    """Wie viele Stellen die Schrittweite der Anlage verlangt."""
    try:
        wert = float(schritt)
    except (TypeError, ValueError):
        return None
    if not 0 < wert < 1:
        return None
    return len(str(schritt).rstrip("0").partition(".")[2]) or None


def messgroesse(beschreibung: dict[str, Any]) -> dict[str, Any]:
    """Einheit, Geräteklasse, Statistikklasse und Genauigkeit festlegen.

    Die Anlage meldet ihre Einheiten in Displayschreibweise („U/min",
    „m^3/h"); Home Assistant erwartet eigene. Und ohne Statistikklasse führt
    der Rekorder keinen Langzeitverlauf – bis hierher galt das für alles außer
    den °C-Werten.

    Kuratierte Angaben aus `const.py` haben Vorrang: Dort steht, was die
    Tabelle nicht wissen kann, etwa dass eine Restlaufzeit in Stunden ein
    Messwert ist und kein Zählerstand.
    """
    if beschreibung.get("type") not in ("sensor", "temperature", "number"):
        return beschreibung
    roh = (beschreibung.get("unit") or "").strip()
    if not roh:
        return beschreibung
    # „20" und „21" meldet die Anlage als Einheit von Datum und Uhrzeit – das
    # sind Formatkennungen, keine Maßeinheiten.
    if roh.isdigit():
        beschreibung["unit"] = None
        return beschreibung

    eintrag = EINHEITEN.get(roh)
    if eintrag is None:
        return beschreibung
    einheit, geraeteklasse, statistik, stellen = eintrag
    beschreibung["unit"] = einheit
    if beschreibung.get("device_class") is None:
        beschreibung["device_class"] = geraeteklasse
    if beschreibung["type"] == "number":
        # Zahlenfelder kennen weder Statistik noch Anzeigegenauigkeit.
        return beschreibung
    if beschreibung.get("state_class") is None:
        name = (beschreibung.get("name") or "").lower()
        if any(wort in name for wort in ZAEHLER_WOERTER):
            statistik = "total_increasing"
        beschreibung["state_class"] = statistik
    if beschreibung.get("precision") is None:
        genauer = _nachkommastellen(beschreibung.get("step"))
        beschreibung["precision"] = max(stellen, genauer) if genauer else stellen
    return beschreibung


def get_oid_raw(coordinator: Any, oid: str, prefix: str = "") -> str | None:
    """Get the raw string value for an OID (or None)."""
    if not coordinator.data:
        return None
    return coordinator.data.get("oids", {}).get(f"{prefix}{oid}")


def get_oid_value(
    coordinator: Any, oid: str, prefix: str = "", default: Any = None
) -> float | None:
    """Get OID value as float with error handling.

    NOTE: default is None on purpose. The old default of "0" masked missing
    values as 0.0, which made frozen/broken datapoints look like real data.
    """
    full_path = f"{prefix}{oid}"
    value = get_oid_raw(coordinator, oid, prefix)
    if value is None:
        value = default
    return parse_value(value, float, full_path)
