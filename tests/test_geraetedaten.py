"""Was auf der Geräteseite in Home Assistant steht.

Bis 1.6.0 waren die Geräte nackt: kein Software-, kein Hardwarestand, keine
Seriennummer, und als Modell stand der von Hand vergebene Anlagenname („KFZ
Werkstatt"). Dabei liefert die Anlage all das – die Seriennummer bildet sogar
schon jede Entitätskennung.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from .conftest import ha_fehlt, requires_ha

pytestmark = requires_ha()

if not ha_fehlt():
    from custom_components.heatnexus.entity import geraet_info

PREFIX = "/1/15/0"


def _coordinator(oids: dict | None = None, neuronen: dict | None = None):
    coordinator = MagicMock()
    coordinator.label = "Heizhaus"
    coordinator.data = {"oids": oids or {}}
    coordinator.client.neuron_by_node = neuronen or {}
    coordinator.client.steuerung_kennung = lambda: "steuerung-0702"
    return coordinator


def _beschreibung(**rest):
    eintrag = {
        "device_id": "0702-15-0",
        "device_name": "KFZ Werkstatt",
        "prefix": PREFIX,
        "fct_type": 14,
    }
    eintrag.update(rest)
    return eintrag


def test_modell_sagt_was_das_geraet_ist():
    """Nicht, wie der Nutzer es genannt hat – das steht schon im Namen."""
    info = geraet_info(_coordinator(), _beschreibung())
    assert info["model"] == "Heizkreis (UML/UMLZ)"
    assert info["name"] == "Heizhaus · KFZ Werkstatt"


def test_unbekannter_funktionstyp_behaelt_den_anlagennamen():
    info = geraet_info(_coordinator(), _beschreibung(fct_type=99))
    assert info["model"] == "KFZ Werkstatt"


def test_seriennummer_kommt_vom_knoten():
    info = geraet_info(_coordinator(neuronen={"15": "0702ab12cd34"}), _beschreibung())
    assert info["serial_number"] == "0702ab12cd34"


def test_software_und_hardwarestand_stehen_am_geraet():
    coordinator = _coordinator(
        oids={f"{PREFIX}/4/92/0": "V 1.11", f"{PREFIX}/4/93/0": "E1"},
    )
    info = geraet_info(coordinator, _beschreibung())
    assert info["sw_version"] == "V 1.11"
    assert info["hw_version"] == "E1"


@pytest.mark.parametrize("wert", [None, "", "   "])
def test_ohne_wert_bleibt_das_feld_leer(wert):
    """Ein leeres Feld ist ehrlich; „unbekannt" wäre eine Behauptung.

    Beim ersten Start ist die Anlage noch nicht fertig eingelesen – dann gibt
    es die Stände schlicht noch nicht.
    """
    coordinator = _coordinator(oids={f"{PREFIX}/4/92/0": wert})
    assert "sw_version" not in geraet_info(coordinator, _beschreibung())
