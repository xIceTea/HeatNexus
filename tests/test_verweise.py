"""Gespeicherte Entitäts-IDs folgen einer Umbenennung im Entitätsregister."""

from __future__ import annotations

from .conftest import requires_ha

pytestmark = requires_ha()


def test_automatik_nennt_nur_geaenderte_felder():
    from custom_components.heatnexus.verweise import automatik_umschreiben

    konfig = {"wetter": "weather.a", "aussen": "sensor.x", "raeume": ["sensor.x", "sensor.y"]}

    assert automatik_umschreiben(konfig, "sensor.x", "sensor.z") == {
        "aussen": "sensor.z",
        "raeume": ["sensor.z", "sensor.y"],
    }
    assert automatik_umschreiben(konfig, "sensor.q", "sensor.z") == {}


def test_bedingung_ohne_treffer_bleibt_unveraendert():
    from custom_components.heatnexus.verweise import bedingung_umschreiben

    regel = {"art": "differenz", "quelle": "sensor.vl", "gegen": "sensor.rl", "ein": 5.0}

    assert bedingung_umschreiben(regel, "sensor.rl", "sensor.ruecklauf") == {
        **regel,
        "gegen": "sensor.ruecklauf",
    }
    assert bedingung_umschreiben(regel, "sensor.anderes", "sensor.neu") is None


async def test_aussentemperatur_und_waermequelle_folgen(hass):
    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.const import (
        CONF_AUSSENTEMPERATUR,
        DOMAIN,
        SUBEINTRAG_QUELLE,
    )
    from custom_components.heatnexus.verweise import verweise_verfolgen

    regel = {"art": "schwelle", "quelle": "sensor.solar_vl", "ein": 40.0, "aus": 35.0}
    eintrag = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_AUSSENTEMPERATUR: "sensor.aussen"},
        subentries_data=[
            ConfigSubentryData(
                data={"host": "192.0.2.10", "id": "q1", "art": "solar", "bedingung": regel},
                subentry_type=SUBEINTRAG_QUELLE,
                title="Solar",
                unique_id=None,
            )
        ],
    )
    eintrag.add_to_hass(hass)
    verweise_verfolgen(hass)
    register = er.async_get(hass)
    aussen = register.async_get_or_create("sensor", "test", "aussen", suggested_object_id="aussen")
    solar = register.async_get_or_create(
        "sensor", "test", "solar_vl", suggested_object_id="solar_vl"
    )

    register.async_update_entity(aussen.entity_id, new_entity_id="sensor.garten")
    register.async_update_entity(solar.entity_id, new_entity_id="sensor.kollektor")
    await hass.async_block_till_done()

    assert eintrag.options[CONF_AUSSENTEMPERATUR] == "sensor.garten"
    (sub,) = eintrag.subentries.values()
    assert sub.data["bedingung"] == {**regel, "quelle": "sensor.kollektor"}


async def test_aenderungen_waehrend_des_neuladens_laden_nicht_noch_einmal(hass):
    import asyncio
    from unittest.mock import patch

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus import _async_options_updated
    from custom_components.heatnexus.const import CONF_AUSSENTEMPERATUR, DOMAIN

    eintrag = MockConfigEntry(domain=DOMAIN, options={CONF_AUSSENTEMPERATUR: "sensor.neu"})
    eintrag.add_to_hass(hass)
    eintrag.runtime_data = {"optionen": {CONF_AUSSENTEMPERATUR: "sensor.alt"}}
    freigabe = asyncio.Event()
    aufrufe: list[str] = []

    async def neu_laden(entry_id: str) -> bool:
        aufrufe.append(entry_id)
        await freigabe.wait()
        return True

    with patch.object(hass.config_entries, "async_reload", neu_laden):
        laeufe = [hass.async_create_task(_async_options_updated(hass, eintrag)) for _ in range(2)]
        await asyncio.sleep(0)
        freigabe.set()
        await asyncio.gather(*laeufe)

    assert aufrufe == [eintrag.entry_id]
    assert "neuladen" not in eintrag.runtime_data


async def test_ungueltige_automatik_haelt_die_uebrigen_nicht_auf(hass):
    from unittest.mock import patch

    from custom_components.heatnexus import verweise

    class Verwaltung:
        def __init__(self) -> None:
            self.eingestellt: list[str] = []

        async def laden(self) -> None:
            return None

        def konfigurationen(self):
            return [("hk1", {"aussen": "sensor.x"}), ("hk2", {"aussen": "sensor.x"})]

        async def einstellen(self, device_id: str, aenderung: dict) -> dict:
            if device_id == "hk1":
                raise ValueError("Raumfühler und Wetter-Entität sind nötig.")
            self.eingestellt.append(device_id)
            return aenderung

    verwaltung = Verwaltung()
    with patch.object(verweise, "verwaltung_holen", return_value=verwaltung):
        await verweise.verweise_umschreiben(hass, "sensor.x", "sensor.y")

    assert verwaltung.eingestellt == ["hk2"]
