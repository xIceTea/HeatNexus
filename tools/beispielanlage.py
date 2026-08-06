"""Die Beispielanlage für README-Bilder – einmal beschrieben, zweimal benutzt.

Standbild (`build_schaubild_beispiel.py`) und Bewegtbild
(`build_schaubild_animation.py`) müssen dieselbe Anlage zeigen; sonst springt
das README zwischen zwei verschiedenen Häusern hin und her.

Die Anlage entspricht einer üblichen Installation: Kessel, Puffer, Heizkreis
mit Warmwasser und Zirkulation – jeweils mit ihrer Pumpe, denn ohne Pumpe
zeichnet das Schaubild keine Förderrichtung.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

WURZEL = Path(__file__).resolve().parent.parent
KOMPONENTE = WURZEL / "custom_components" / "heatnexus"

__all__ = ["KOMPONENTE", "STANDBILD", "TEILE", "WURZEL", "karte", "schema_modul", "teil"]


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


def teil(name: str, fct: int, werte: list[tuple[str, str]]) -> dict:
    """Ein Anlagenteil in der Form, die `dashboard._anlagen` liefert."""
    return {
        "name": name,
        "fct_type": fct,
        "entitaeten": [
            {
                "entity_id": eid,
                "name": bezeichnung,
                "hat_wert": True,
                "bereich": eid.split(".")[0],
            }
            for eid, bezeichnung in werte
        ],
    }


TEILE = [
    teil(
        "PuroWIN",
        25,
        [
            ("sensor.kessel", "Kesseltemperatur Ist"),
            ("sensor.leistung", "Kesselleistung"),
            ("binary_sensor.kesselpumpe", "Kesselpumpe"),
        ],
    ),
    teil(
        "B-PLMi PUFFER",
        16,
        [
            ("sensor.puffer_oben", "Puffer oben Temperatur (TPE)"),
            ("sensor.puffer_unten", "Puffer unten Temperatur (TPA)"),
            ("binary_sensor.pufferladepumpe", "Pufferladepumpe"),
        ],
    ),
    teil(
        "UMLZ HEIZKREIS",
        14,
        [
            ("sensor.vorlauf", "Vorlauftemperatur Ist"),
            ("sensor.raum", "Raumtemperatur Ist"),
            ("binary_sensor.heizkreispumpe", "Heizkreispumpe"),
            ("sensor.warmwasser", "Warmwasser Ist-Temperatur"),
            ("binary_sensor.ww_ladepumpe", "WW-Ladepumpe"),
            ("sensor.zirkulation", "WW-Zirkulation Ist-Temperatur"),
            ("binary_sensor.ww_zirkulationspumpe", "WW-Zirkulationspumpe"),
        ],
    ),
]

# Werte für das Standbild: ein Betriebszustand, wie er an einem Wintertag
# wirklich vorkommt – Kessel unter Last, Puffer oben warm, unten kühler.
STANDBILD = {
    "sensor.kessel": "72,4 °C",
    "sensor.leistung": "38 %",
    "sensor.puffer_oben": "68,1 °C",
    "sensor.puffer_unten": "42,7 °C",
    "sensor.vorlauf": "45,0 °C",
    "sensor.raum": "21,5 °C",
    "sensor.warmwasser": "51,2 °C",
    "sensor.zirkulation": "38,6 °C",
}


def karte() -> dict:
    """Das Schaubild der Beispielanlage, so wie es die Anlage bekäme."""
    ergebnis = schema_modul().anlagenschema(TEILE)
    if not ergebnis:
        raise SystemExit("Die Beispielanlage ergibt kein Schaubild.")
    return ergebnis
