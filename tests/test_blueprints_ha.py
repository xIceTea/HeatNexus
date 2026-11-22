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


async def _abwesend_einrichten(hass):
    """Die Vorlage Abwesenheit mit einer Person und 30 Minuten Verzögerung."""
    from homeassistant.setup import async_setup_component

    ziel = hass.config.path("blueprints", "automation")
    await hass.async_add_executor_job(lambda: shutil.copytree(VORLAGEN, ziel, dirs_exist_ok=True))
    hass.states.async_set("person.a", "home")
    hass.states.async_set("climate.hk", "heat", {"preset_mode": "3"})
    aufrufe: list = []

    async def absenken(aufruf) -> None:
        # Die Person kehrt zurück, sonst wartete der Lauf bis zum Testende.
        aufrufe.append(aufruf)
        hass.states.async_set("person.a", "home")

    hass.services.async_register("climate", "set_preset_mode", absenken)
    konfig = {
        "id": "abwesend",
        "use_blueprint": {
            "path": "heatnexus/heizkreis_abwesend.yaml",
            "input": {
                "anwesenheit": ["person.a"],
                "heizkreis": "climate.hk",
                "verzoegerung": {"minutes": 30},
            },
        },
    }
    assert await async_setup_component(hass, "automation", {"automation": [konfig]})
    await hass.async_block_till_done()
    return aufrufe


async def _nach(hass, minuten: int) -> None:
    from datetime import timedelta

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=minuten))
    await hass.async_block_till_done()


@pytest.mark.parametrize("unterwegs", ["not_home", "Arbeit"])
async def test_abwesend_senkt_auch_ab_wenn_die_person_eine_zone_erreicht(hass, unterwegs):
    aufrufe = await _abwesend_einrichten(hass)
    hass.states.async_set("person.a", "not_home")
    await hass.async_block_till_done()
    await _nach(hass, 10)
    hass.states.async_set("person.a", unterwegs)
    await hass.async_block_till_done()
    await _nach(hass, 31)
    assert [str(a.data["preset_mode"]) for a in aufrufe] == ["5"]


async def test_abwesend_senkt_nicht_ab_wenn_die_person_vorher_zurueckkommt(hass):
    aufrufe = await _abwesend_einrichten(hass)
    hass.states.async_set("person.a", "Arbeit")
    await hass.async_block_till_done()
    await _nach(hass, 10)
    hass.states.async_set("person.a", "home")
    await hass.async_block_till_done()
    await _nach(hass, 31)
    assert aufrufe == []


def test_eine_automations_yaml_in_fremdem_zeichensatz_bricht_nichts_ab(tmp_path):
    """Ein Umlaut in CP1252 ließ das Setup scheitern; erkannt wird die Vorlage trotzdem."""
    from custom_components.heatnexus import blueprints

    datei = tmp_path / "automations.yaml"
    datei.write_bytes(
        "- alias: Küche\n  use_blueprint:\n    path: heatnexus/test.yaml\n".encode("cp1252")
    )
    assert blueprints._wird_benutzt(datei, "test") is True
    datei.write_bytes("- alias: Küche\n".encode("cp1252"))
    assert blueprints._wird_benutzt(datei, "test") is False


async def test_gleichzeitige_eintraege_halten_vorlagen_nicht_fuer_geaendert(hass, caplog):
    """Nach einem Update starten mehrere Einträge zugleich; keiner meldet fremde Änderungen."""
    import asyncio

    from custom_components.heatnexus.blueprints import async_install_blueprints

    await async_install_blueprints(hass, "1.0.0")
    await asyncio.gather(*(async_install_blueprints(hass, "2.0.0") for _ in range(7)))

    assert "Selbst geänderte" not in caplog.text
