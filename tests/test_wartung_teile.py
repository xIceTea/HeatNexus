"""Die Wartung nennt zu jeder Zeile ihren Anlagenteil."""

from __future__ import annotations

from .conftest import requires_ha

pytestmark = requires_ha()


def _e(entity_id: str, name: str) -> dict:
    return {
        "entity_id": entity_id,
        "name": name,
        "bereich": "sensor",
        "hat_wert": True,
        "schluessel": None,
        "kategorie": None,
    }


def test_betriebsstunden_von_kessel_und_waermepumpe_bleiben_unterscheidbar():
    from custom_components.heatnexus.panel.wartung import wartung

    anlage = {
        "teile": [
            {"name": "BioWIN", "entitaeten": [_e("sensor.k", "Betriebsstunden")]},
            {"name": "AeroWIN", "entitaeten": [_e("sensor.w", "Betriebsstunden")]},
        ]
    }
    zeilen = [z for liste in wartung(anlage).values() if isinstance(liste, list) for z in liste]
    assert {(z["entity"], z["teil"]) for z in zeilen} >= {
        ("sensor.k", "BioWIN"),
        ("sensor.w", "AeroWIN"),
    }
