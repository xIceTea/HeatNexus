"""Steuerungen eines Eintrags nachträglich entfernen.

Geprüft wird, dass genau die eine Steuerung mit allem, was an ihr hängt,
verschwindet und die übrigen unberührt bleiben.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

A, B = "192.0.2.10", "192.0.2.20"


def _koordinator(hass, eintrag, host: str, kennung: str):
    return SimpleNamespace(
        host=host,
        entry=eintrag,
        hass=hass,
        client=SimpleNamespace(steuerung_kennung=lambda: kennung),
    )


@pytest.fixture
async def anlage(hass):
    from homeassistant.config_entries import ConfigSubentry
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.storage import Store
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.automatik.verwaltung import verwaltung_holen
    from custom_components.heatnexus.const import CONF_LABEL, CONF_SYSTEMS, DOMAIN
    from custom_components.heatnexus.erkennungsstand import store_key
    from custom_components.heatnexus.registrierung import uebergeordnet

    eintrag = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=2,
        unique_id="kennung-a-kennung-b",
        data={
            CONF_SYSTEMS: [
                {"host": A, CONF_LABEL: "Kesselhaus", "kennung": "kennung-a"},
                {"host": B, CONF_LABEL: "Nebengebäude", "kennung": "kennung-b"},
            ]
        },
        options={A: {"levels": ["info"]}, B: {"levels": ["info", "operate"]}, "sprache": "de"},
    )
    eintrag.add_to_hass(hass)
    hass.config_entries.async_add_subentry(
        eintrag,
        ConfigSubentry(
            data={"host": A, "id": "q1", "art": "solar"},
            subentry_type="waermequelle",
            title="Solaranlage",
            unique_id="q1",
        ),
    )
    geraete, entitaeten = dr.async_get(hass), er.async_get(hass)
    for kennung, name in (("steuerung-a", "Kesselhaus"), ("steuerung-b", "Nebengebäude")):
        geraete.async_get_or_create(
            config_entry_id=eintrag.entry_id, identifiers={(DOMAIN, kennung)}, name=name
        )
    for kreis, steuerung in (("hk-a", "steuerung-a"), ("hk-b", "steuerung-b")):
        geraet = geraete.async_get_or_create(
            config_entry_id=eintrag.entry_id,
            identifiers={(DOMAIN, kreis)},
            name=f"Heizkreis {kreis[-1].upper()}",
            **uebergeordnet(hass, steuerung, eintrag.entry_id),
        )
        entitaeten.async_get_or_create(
            "sensor", DOMAIN, f"{kreis}-vorlauf", config_entry=eintrag, device_id=geraet.id
        )
    eintrag.runtime_data = {
        "coordinators": {
            A: _koordinator(hass, eintrag, A, "steuerung-a"),
            B: _koordinator(hass, eintrag, B, "steuerung-b"),
        }
    }
    verwaltung = verwaltung_holen(hass)
    await verwaltung.laden()
    for kreis in ("hk-a", "hk-b"):
        verwaltung._daten["heizkreise"][kreis] = {
            "konfig": {"entry_id": eintrag.entry_id, "heizkreis": kreis}
        }
    await Store(hass, 1, store_key(eintrag, A)).async_save({"devices": []})
    return eintrag, verwaltung


async def test_folgen_nennen_automatik_und_waermequelle(hass, anlage):
    from custom_components.heatnexus import steuerungen

    eintrag, _ = anlage
    folgen = steuerungen.folgen(hass, eintrag, A)

    assert folgen.geraete == 2
    assert folgen.automatiken == ["Heizkreis A"]
    assert folgen.quellen == ["Solaranlage"]


async def test_entfernen_raeumt_nur_die_eine_steuerung_ab(hass, anlage):
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.storage import Store

    from custom_components.heatnexus import steuerungen
    from custom_components.heatnexus.const import CONF_SYSTEMS, DOMAIN
    from custom_components.heatnexus.erkennungsstand import store_key
    from custom_components.heatnexus.registrierung import geraet_suchen

    eintrag, verwaltung = anlage
    await steuerungen.entfernen(hass, eintrag, A)
    await hass.async_block_till_done()

    assert [s["host"] for s in eintrag.data[CONF_SYSTEMS]] == [B]
    assert A not in eintrag.options and B in eintrag.options
    assert eintrag.options["sprache"] == "de"
    assert eintrag.unique_id == "kennung-b"
    geraete, eid = dr.async_get(hass), eintrag.entry_id
    assert geraet_suchen(geraete, "steuerung-a", eid) is None
    assert geraet_suchen(geraete, "hk-a", eid) is None
    assert geraet_suchen(geraete, "hk-b", eid) is not None
    entitaeten = er.async_get(hass)
    assert entitaeten.async_get_entity_id("sensor", DOMAIN, "hk-a-vorlauf") is None
    assert entitaeten.async_get_entity_id("sensor", DOMAIN, "hk-b-vorlauf") is not None
    assert verwaltung.konfig("hk-a") is None and verwaltung.konfig("hk-b") is not None
    assert not [s for s in eintrag.subentries.values() if s.subentry_type == "waermequelle"]
    assert await Store(hass, 1, store_key(eintrag, A)).async_load() is None


def test_kennung_des_eintrags_folgt_den_steuerungen():
    from custom_components.heatnexus import steuerungen

    assert (
        steuerungen.kennung_des_eintrags(
            [
                {"host": B, "kennung": "kennung-b"},
                {"host": "192.0.2.30"},
                {"host": A, "kennung": "a"},
            ]
        )
        == "192.0.2.30-a-kennung-b"
    )
