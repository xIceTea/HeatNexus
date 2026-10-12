"""Die mitgelieferten Vorlagen gegen die Prüfung von Home Assistant.

`test_blueprints.py` prüft Aufbau und Vorlagentexte ohne Home Assistant; hier
werden die Vorlagen mit Eingaben gefüllt und als Automation validiert.
"""

from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

VORLAGEN = (
    Path(__file__).parent.parent / "custom_components" / "heatnexus" / "blueprints" / "automation"
)

EINGABEN = {
    "heizkreis_abwesend": {
        "anwesenheit": ["person.a"],
        "heizkreis": "climate.heizkreis",
    },
    "legionellenschutz": {
        "warmwasser_ist": "sensor.warmwasser",
        "einmalladung": "switch.einmalladung",
        "ladetemperatur": "number.ladetemperatur",
        "betriebswahl": ["select.betriebswahl"],
    },
}


@pytest.mark.parametrize("vorlage", sorted(EINGABEN))
async def test_die_vorlage_ergibt_eine_gueltige_automation(hass, vorlage):
    from homeassistant.components.automation.config import async_validate_config_item
    from homeassistant.setup import async_setup_component

    ziel = hass.config.path("blueprints", "automation")
    await hass.async_add_executor_job(lambda: shutil.copytree(VORLAGEN, ziel, dirs_exist_ok=True))
    assert await async_setup_component(hass, "blueprint", {})
    konfig = {
        "id": vorlage,
        "use_blueprint": {"path": f"heatnexus/{vorlage}.yaml", "input": EINGABEN[vorlage]},
    }

    geprueft = await async_validate_config_item(hass, vorlage, konfig)

    assert geprueft is not None
    assert geprueft.validation_status == "ok", geprueft.validation_error
