"""Der Befüllgrad ist ein errechneter Wert und nur eine Anzeige.

Die Steuerung meldet ihn ohne Schreibschutz. Zurückgesetzt wird er über den
Warnlevel, der deshalb ein Eingabefeld bleibt.
"""

from __future__ import annotations

import pytest

from .anlagenkatalog import HOST, Nachspiel
from .conftest import requires_ha

pytestmark = requires_ha()

ANLAGEN = ["biowin-1415-puffer", "biowin-1415-touch2", "duowin"]
UMFANG = {"levels": ["info", "operate"]}


async def _beschreibungen(anlage: str) -> dict[str, dict]:
    from custom_components.heatnexus.client import WindhagerHttpClient

    client = WindhagerHttpClient(HOST, "x", **UMFANG)
    Nachspiel(anlage).einsetzen(client)
    await client.async_init_basic()
    await client.async_init()
    return {d["oid"]: d for d in client.devices if d.get("oid")}


@pytest.mark.parametrize("anlage", ANLAGEN)
@pytest.mark.parametrize("adresse", ["43/42", "43/78"])
async def test_der_befuellgrad_ist_eine_anzeige_in_prozent(anlage, adresse):
    d = (await _beschreibungen(anlage))[f"/1/60/0/{adresse}/0"]
    assert d["type"] == "sensor"
    assert d.get("unit") == "%"
    assert d.get("state_class") == "measurement"


@pytest.mark.parametrize("anlage", ANLAGEN)
async def test_der_warnlevel_bleibt_ein_eingabefeld(anlage):
    d = (await _beschreibungen(anlage))["/1/60/0/43/77/0"]
    assert d["type"] == "number"


@pytest.mark.parametrize("adresse", ["43-42", "43-78"])
def test_das_alte_eingabefeld_wird_geloescht(hass, adresse):
    """Die Anzeige trägt dieselbe Kennung; das Eingabefeld bliebe sonst stillgelegt stehen."""
    from types import SimpleNamespace

    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus import stilllegung
    from custom_components.heatnexus.const import DOMAIN
    from custom_components.heatnexus.entity import TYP_DOMAENE

    kennung = f"SN1-0-{adresse}-0"
    vorher = dict(TYP_DOMAENE)
    TYP_DOMAENE["sensor"] = "sensor"
    eintrag = MockConfigEntry(domain=DOMAIN, title="HeatNexus", data={}, options={})
    eintrag.add_to_hass(hass)
    registry = er.async_get(hass)
    feld = registry.async_get_or_create("number", DOMAIN, kennung, config_entry=eintrag)
    anzeige = registry.async_get_or_create("sensor", DOMAIN, kennung, config_entry=eintrag)
    koordinator = SimpleNamespace(
        data={"devices": [{"id": kennung, "type": "sensor", "enabled_default": True}]},
        client=SimpleNamespace(_vollstaendig=True),
    )

    try:
        stilllegung.abgewaehlte_entitaeten_stilllegen(hass, eintrag, {"a": koordinator})
    finally:
        TYP_DOMAENE.clear()
        TYP_DOMAENE.update(vorher)

    assert registry.async_get(feld.entity_id) is None
    assert registry.async_get(anzeige.entity_id).disabled_by is None
