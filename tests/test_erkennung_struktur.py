"""Die Struktur der Anlage (`/1`): Was eine Absage beim Einrichten bedeutet."""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


def _client(status: int, daten=None):
    from custom_components.heatnexus.client import WindhagerHttpClient

    c = WindhagerHttpClient("192.0.2.10", "geheim")

    async def get(url, semaphore=None):
        return daten, status

    c._get = get
    return c


async def test_ein_abgewiesenes_passwort_ist_ein_anmeldefehler():
    from custom_components.heatnexus.exceptions import InvalidAuth

    with pytest.raises(InvalidAuth):
        await _client(401)._discover(nur_kern=True)


async def test_ein_anderer_status_nennt_ihn():
    from custom_components.heatnexus.exceptions import CannotConnect

    with pytest.raises(CannotConnect) as fehler:
        await _client(503)._discover(nur_kern=True)

    assert fehler.value.translation_key == "struktur_unlesbar"
    assert fehler.value.translation_placeholders["status"] == "503"


async def test_beim_einrichten_fragt_home_assistant_nach_dem_passwort():
    from homeassistant.exceptions import ConfigEntryAuthFailed

    from custom_components.heatnexus import _grunddaten_lesen

    with pytest.raises(ConfigEntryAuthFailed):
        await _grunddaten_lesen(_client(401), "192.0.2.10")
