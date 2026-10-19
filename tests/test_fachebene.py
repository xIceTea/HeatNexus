"""Kuratierte Fachparameter folgen der Ebene des Herstellers."""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

PRAEFIX = "/1/30/0"


@pytest.fixture(scope="module")
def client_module():
    from custom_components.heatnexus import client

    return client


def _kuratiert(client_module, fct_type: int, freigabe: bool) -> dict[str, dict]:
    """Die kuratierten Beschreibungen eines Funktionstyps nach dem Schreibschutz."""
    from custom_components.heatnexus.const import FCT_ENTITY_MAP
    from custom_components.heatnexus.device_db import get_layers

    c = client_module.WindhagerHttpClient(
        "192.0.2.10", "geheim", levels=["info", "operate"], writable_advanced=freigabe
    )
    c.oids, c.devices = set(), []
    fct = {"fctId": 0, "fctType": fct_type, "name": "Teil"}
    level_of, _ = c._ebenen_und_gruppen(get_layers(fct_type) or {})
    for definition in FCT_ENTITY_MAP[fct_type]:
        c._add_entity(definition, PRAEFIX, "/1/30", fct, level_of)
    for d in c.devices:
        c._fachebene_nur_lesend(d)
    return {d["oid"].removeprefix(PRAEFIX): d for d in c.devices}


def test_ein_kuratierter_serviceparameter_bleibt_ohne_freigabe_lesbar(client_module):
    puffer = _kuratiert(client_module, 16, freigabe=False)
    assert puffer["/9/32/0"]["level"] == "service"
    assert puffer["/9/32/0"]["type"] != "number"
    assert puffer["/20/15/0"]["type"] == "select"


def test_mit_freigabe_bleibt_er_einstellbar(client_module):
    puffer = _kuratiert(client_module, 16, freigabe=True)
    assert puffer["/9/32/0"]["type"] == "number"


def test_ein_werksparameter_des_kessels_bleibt_ohne_freigabe_lesbar(client_module):
    kessel = _kuratiert(client_module, 25, freigabe=False)
    assert kessel["/37/53/0"]["level"] == "oem"
    assert kessel["/37/53/0"]["type"] != "number"


@pytest.mark.parametrize("adresse", ["/5/6/0", "/5/0/0"])
def test_ausdruecklich_bedienbare_eintraege_bleiben_einstellbar(client_module, adresse):
    heizkreis = _kuratiert(client_module, 14, freigabe=False)
    assert heizkreis[adresse]["level"] == "operate"
    assert heizkreis[adresse]["type"] in ("select", "number")


def test_das_alte_eingabefeld_eines_fachparameters_wird_geloescht(hass):
    """Ohne Freigabe ist der Fachparameter eine Anzeige mit derselben Kennung."""
    from types import SimpleNamespace

    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus import stilllegung
    from custom_components.heatnexus.const import DOMAIN
    from custom_components.heatnexus.entity import TYP_DOMAENE

    kennung = "SN1-1-9-32-0"
    vorher = dict(TYP_DOMAENE)
    TYP_DOMAENE["sensor"] = "sensor"
    eintrag = MockConfigEntry(domain=DOMAIN, title="HeatNexus", data={}, options={})
    eintrag.add_to_hass(hass)
    registry = er.async_get(hass)
    feld = registry.async_get_or_create("number", DOMAIN, kennung, config_entry=eintrag)
    anzeige = registry.async_get_or_create("sensor", DOMAIN, kennung, config_entry=eintrag)
    beschreibung = {"id": kennung, "type": "sensor", "level": "service", "enabled_default": True}
    koordinator = SimpleNamespace(
        data={"devices": [beschreibung]},
        client=SimpleNamespace(_vollstaendig=True, writable_advanced=False),
    )
    try:
        stilllegung.abgewaehlte_entitaeten_stilllegen(hass, eintrag, {"a": koordinator})
    finally:
        TYP_DOMAENE.clear()
        TYP_DOMAENE.update(vorher)

    assert registry.async_get(feld.entity_id) is None
    assert registry.async_get(anzeige.entity_id) is not None
