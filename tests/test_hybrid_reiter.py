"""Reiter „Hybrid“: Zustand, Kostenvergleich und Diagramme des Hybridmanagers."""

from __future__ import annotations

import pytest

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


@pytest.fixture
def anlage():
    return {
        "teile": [
            {
                "name": "Hybrid",
                "fct_type": 26,
                "entitaeten": [
                    _e("sensor.art", "Betriebsart"),
                    _e("sensor.biv", "Zustand Bivalenz"),
                    _e("number.biv_hz", "Bivalenztemperatur Heizung"),
                    _e("number.kosten", "Kosten Pellets"),
                    _e("sensor.heizwert", "Wärmemenge Pellets (kWh/kg)"),
                    _e("sensor.wg", "Wirkungsgrad Pelletskessel"),
                    _e("number.t1", "Tarif 1"),
                    _e("number.t2", "Tarif 2"),
                    _e("sensor.aussen", "Aussentemperatur Regelung"),
                ],
            },
            {
                "name": "AeroWIN",
                "fct_type": 7,
                "entitaeten": [
                    _e("sensor.cop", "COP aktuell"),
                    _e("sensor.leistung", "Aktuelle Leistung"),
                    _e("sensor.wm", "Wärmemenge Heizen"),
                ],
            },
            {
                "name": "BioWIN",
                "fct_type": 9,
                "entitaeten": [_e("sensor.kl", "Kesselleistung")],
            },
        ]
    }


def test_ohne_hybridmanager_kein_reiter():
    from custom_components.heatnexus.panel.hybrid import hybrid

    assert hybrid({"teile": [{"name": "BioWIN", "fct_type": 9, "entitaeten": []}]}) is None


def test_der_kostenvergleich_kennt_seine_eingaben(anlage):
    from custom_components.heatnexus.panel.hybrid import hybrid

    w = hybrid(anlage)["wirtschaftlichkeit"]
    assert (w["kosten"], w["heizwert"], w["wirkungsgrad"]) == (
        "number.kosten",
        "sensor.heizwert",
        "sensor.wg",
    )
    assert w["tarife"] == [
        {"nummer": 1, "entity": "number.t1"},
        {"nummer": 2, "entity": "number.t2"},
    ]
    assert w["cop"] == "sensor.cop"


def test_zustand_grenzen_und_diagramme(anlage):
    from custom_components.heatnexus.panel.hybrid import hybrid

    daten = hybrid(anlage)
    assert [z["titel"] for z in daten["zustand"]] == ["Betriebsart", "Bivalenz", "Außentemperatur"]
    assert [z["titel"] for z in daten["grenzen"]] == ["Bivalenztemperatur Heizung"]
    titel = [d["titel"] for d in daten["diagramme"]]
    assert titel == ["Temperaturen", "Wer heizt", "Leistungszahl", "Wärmemenge je Tag"]
    wer_heizt = daten["diagramme"][1]["karte"]
    assert wer_heizt["entities"] == ["sensor.leistung", "sensor.kl"]
    assert daten["diagramme"][3]["karte"]["type"] == "statistics-graph"
