"""Hybridmanager: Karte in der Steuerung und Diagramme im Verlauf."""

from __future__ import annotations

import pytest

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


@pytest.fixture
def anlage():
    return {
        "teile": [
            {
                "name": "Hybrid",
                "fct_type": 26,
                "entitaeten": [
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


def test_ohne_hybridmanager_keine_karte():
    from custom_components.heatnexus.panel.hybrid import hybrid

    assert hybrid({"teile": [{"name": "BioWIN", "fct_type": 9, "entitaeten": []}]}) is None


def test_die_karte_kennt_preis_tarife_und_vergleich(anlage):
    from custom_components.heatnexus.panel.hybrid import hybrid

    karte = hybrid(anlage)["karte"]
    assert (karte["kosten"], karte["heizwert"], karte["wirkungsgrad"]) == (
        "number.kosten",
        "sensor.heizwert",
        "sensor.wg",
    )
    assert karte["tarife"] == [
        {"nummer": 1, "entity": "number.t1"},
        {"nummer": 2, "entity": "number.t2"},
    ]
    assert karte["cop"] == "sensor.cop"


def test_ohne_werksebene_fehlen_heizwert_und_wirkungsgrad(anlage):
    """Beide stehen nur in der Werksebene; die Karte zeigt dann einen Hinweis statt nichts."""
    from custom_components.heatnexus.panel.hybrid import hybrid

    ohne = ("sensor.heizwert", "sensor.wg")
    teil = anlage["teile"][0]
    teil["entitaeten"] = [e for e in teil["entitaeten"] if e["entity_id"] not in ohne]
    karte = hybrid(anlage)["karte"]
    assert karte["kosten"] == "number.kosten"
    assert (karte["heizwert"], karte["wirkungsgrad"]) == (None, None)


def test_die_diagramme_fuer_den_verlauf(anlage):
    from custom_components.heatnexus.panel.hybrid import hybrid

    diagramme = hybrid(anlage)["diagramme"]
    assert [d["titel"] for d in diagramme] == [
        "Temperaturen",
        "Wer heizt",
        "Leistungszahl",
        "Wärmemenge je Tag",
    ]
    assert diagramme[1]["karte"]["entities"] == ["sensor.leistung", "sensor.kl"]
    assert diagramme[3]["karte"]["type"] == "statistics-graph"
