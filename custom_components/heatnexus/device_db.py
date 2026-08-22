"""Access to the bundled Windhager device database (device_db.json).

The database is generated from the official Windhager files
de-parameters.json (OID names + enum texts) and parameterLayer.json
(which datapoints belong to the Info-/Betreiberebene of each function
type). It enables automatic discovery of function types that have no
hand-curated entity table, e.g. BioWIN or AeroWIN devices.
"""

from __future__ import annotations

from functools import lru_cache
import json
import os


@lru_cache(maxsize=1)
def _db() -> dict:
    path = os.path.join(os.path.dirname(__file__), "device_db.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_name(gnmn: str) -> str | None:
    """German display name for a 'gn/mn' datapoint.

    Beschnitten wie die Aufzählungstexte: An einzelnen Namen der
    Herstellerdatei hängt ein Leerzeichen, und als Entitätsname ist es sichtbar.
    """
    name = _db()["names"].get(gnmn)
    return name.strip() if name else name


def get_enum(gnmn: str) -> dict[int, str] | None:
    """Enum value->text mapping for a 'gn/mn' datapoint, if any.

    Die Texte werden beschnitten: In der Herstellerdatei hängt an einzelnen
    Einträgen ein Leerzeichen (`"Fehler Vorratsbehälter "`). Als Zustand einer
    Entität ist das sichtbar – und es macht aus einem Zustand zwei, sobald
    jemand in einer Automation darauf vergleicht.
    """
    e = _db()["enums"].get(gnmn)
    if not e:
        return None
    return {int(k): str(v).strip() for k, v in e.items()}


def get_layers(fct_type: int) -> dict | None:
    """Info/operate datapoint lists for a function type."""
    return _db()["layers"].get(str(fct_type))


def get_conditions(fct_type: int) -> dict[str, list[dict]]:
    """Sichtbarkeitsbedingungen eines Funktionstyps: Adresse -> Bedingungssätze.

    Trifft keiner der Sätze zu, führt die Anlage den Datenpunkt zwar, er bleibt
    aber ohne Funktion.
    """
    return (_db()["layers"].get(str(fct_type)) or {}).get("conditions") or {}


def preload() -> None:
    """Datenbank einlesen.

    Home Assistant verbietet blockierende Dateizugriffe in der Ereignisschleife;
    deshalb wird die Datei beim Einrichten einmal in einem Arbeitsthread
    geladen und liegt danach im Zwischenspeicher.
    """
    _db()
