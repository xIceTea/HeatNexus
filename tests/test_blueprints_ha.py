"""Die mitgelieferten Vorlagen gegen die Prüfung von Home Assistant.

`test_blueprints.py` prüft Aufbau und Vorlagentexte ohne Home Assistant; hier
werden die Vorlagen mit Eingaben gefüllt und als Automation validiert.
"""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

import pytest
import yaml

from .conftest import requires_ha

pytestmark = requires_ha()

VORLAGEN = (
    Path(__file__).parent.parent / "custom_components" / "heatnexus" / "blueprints" / "automation"
)


class _Lader(yaml.SafeLoader):
    """SafeLoader, der ``!input`` kennt."""


_Lader.add_constructor("!input", lambda loader, node: node.value)


def _beispiel(selektor: dict[str, Any]) -> Any:
    """Ein passender Wert für ein Eingabefeld ohne Vorgabe."""
    if "entity" in selektor:
        filter_ = (selektor["entity"] or {}).get("filter") or [{}]
        entitaet = f"{filter_[0].get('domain', 'sensor')}.beispiel"
        return [entitaet] if (selektor["entity"] or {}).get("multiple") else entitaet
    if "device" in selektor:
        return "0123456789abcdef"
    return []


def _eingaben(felder: dict[str, Any]) -> dict[str, Any]:
    """Alle Pflichtfelder einer Vorlage, auch in Abschnitten."""
    werte: dict[str, Any] = {}
    for name, feld in felder.items():
        if "input" in feld and "selector" not in feld:
            werte.update(_eingaben(feld["input"]))
        elif "default" not in feld:
            werte[name] = _beispiel(feld.get("selector") or {})
    return werte


# Die Gerätaktion der Mitteilung prüft Home Assistant gegen ein angemeldetes Mobilgerät.
OHNE_GERAET = {"automatik_empfehlung"}


def _vorlagen() -> list[str]:
    return sorted(
        p.stem for p in (VORLAGEN / "heatnexus").glob("*.yaml") if p.stem not in OHNE_GERAET
    )


@pytest.mark.parametrize("vorlage", _vorlagen())
async def test_die_vorlage_ergibt_eine_gueltige_automation(hass, vorlage):
    from homeassistant.components.automation.config import async_validate_config_item
    from homeassistant.setup import async_setup_component

    ziel = hass.config.path("blueprints", "automation")
    await hass.async_add_executor_job(lambda: shutil.copytree(VORLAGEN, ziel, dirs_exist_ok=True))
    assert await async_setup_component(hass, "blueprint", {})
    datei = VORLAGEN / "heatnexus" / f"{vorlage}.yaml"
    kopf = yaml.load(datei.read_text(encoding="utf-8"), Loader=_Lader)["blueprint"]
    konfig = {
        "id": vorlage,
        "use_blueprint": {
            "path": f"heatnexus/{vorlage}.yaml",
            "input": _eingaben(kopf["input"]),
        },
    }

    geprueft = await async_validate_config_item(hass, vorlage, konfig)

    assert geprueft is not None
    assert geprueft.validation_status == "ok", geprueft.validation_error
