"""Der Systemstatus zeigt den SG-Ready-Zustand, wo eine Anlage ihn meldet."""

from __future__ import annotations

from .conftest import requires_ha

pytestmark = requires_ha()


def _e(entity_id: str, name: str) -> dict:
    return {
        "entity_id": entity_id,
        "name": name,
        "bereich": entity_id.split(".")[0],
        "hat_wert": True,
        "schluessel": None,
        "kategorie": None,
    }


def _titel(entitaeten: list[dict]) -> dict[str, str]:
    from custom_components.heatnexus.panel.muster import STATUS
    from custom_components.heatnexus.panel.suche import zeilen_aus

    return {z["titel"]: z["entity"] for z in zeilen_aus(entitaeten, STATUS)}


def test_der_zustand_steht_im_systemstatus():
    zeilen = _titel([_e("select.sg", "SG Ready"), _e("sensor.sg", "SG Ready Status")])
    assert zeilen["SG Ready"] == "sensor.sg"


def test_ohne_sg_ready_keine_zeile():
    assert "SG Ready" not in _titel([_e("sensor.kl", "Kesselleistung")])
