"""Der Dienst „Heizkreis umbenennen“: Objekt 4/5, Untertyp 9, höchstens 20 Byte."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


def _klima():
    from custom_components.heatnexus.climate import WindhagerThermostatClimate

    from .test_plattformen import FakeCoordinator

    koordinator = FakeCoordinator({})
    koordinator.client.write_object = AsyncMock()
    return WindhagerThermostatClimate(
        koordinator, {"id": "SN1-15-0", "name": "Heizkreis", "prefix": "/1/15/0"}
    )


async def test_der_name_geht_als_textobjekt_an_die_steuerung(hass):
    klima = _klima()
    klima.hass = hass

    await klima.async_umbenennen("Wohnhaus")

    oid, rumpf, schluessel = klima.coordinator.client.write_object.call_args.args
    assert oid == "/1/15/0/4/5/0"
    assert rumpf == {"OID": oid, "typeId": 30, "subtypeId": 9, "value": "Wohnhaus"}
    assert schluessel == "name_abgelehnt"


async def test_ein_name_ueber_20_byte_wird_abgelehnt(hass):
    """Umlaute zählen doppelt: 19 Zeichen mit zwei Umlauten sind 21 Byte."""
    from custom_components.heatnexus.exceptions import WindhagerValueError

    klima = _klima()
    klima.hass = hass

    with pytest.raises(WindhagerValueError):
        await klima.async_umbenennen("Fußbodenheizung Süd")

    klima.coordinator.client.write_object.assert_not_awaited()
