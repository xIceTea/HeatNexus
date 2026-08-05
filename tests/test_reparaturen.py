"""Was passiert, wenn die Anlage nicht mehr antwortet oder abweist.

Zwei Fälle, die vorher still blieben:

* **Das Passwort stimmt nicht mehr.** Die Anlage wies jede Anfrage ab, die
  Entitäten standen auf „nicht verfügbar", und niemand sagte, woran es liegt.
  Jetzt fragt Home Assistant von sich aus nach.
* **Die Anlage ist weg.** Statt einer Benachrichtigung, die man wegklickt und
  die nie wiederkommt, steht das Problem in den Reparaturen – und verschwindet
  von selbst, sobald wieder Werte kommen.
"""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from .conftest import ha_fehlt, requires_ha

pytestmark = requires_ha()

if not ha_fehlt():
    from homeassistant.exceptions import ConfigEntryAuthFailed
    from homeassistant.helpers import issue_registry as ir
    from homeassistant.helpers.update_coordinator import UpdateFailed

    from custom_components.heatnexus import WindhagerDataUpdateCoordinator
    from custom_components.heatnexus.const import AUTH_FEHLER_GRENZE, DOMAIN


@pytest.fixture
def coordinator(hass):
    eintrag = MagicMock()
    eintrag.data = {"name": "Heizhaus"}
    eintrag.title = "Heizhaus"
    eintrag.entry_id = "abc123"
    client = MagicMock()
    client.auth_errors = 0
    client.fetch_all = AsyncMock(return_value={"oids": {}, "devices": []})
    return WindhagerDataUpdateCoordinator(
        hass, client, eintrag, "192.0.2.1", "Heizhaus", update_interval=30
    )


def _stoerung(hass, coordinator):
    return ir.async_get(hass).async_get_issue(
        DOMAIN, f"nicht_erreichbar_{coordinator.entry.entry_id}_{coordinator.host}"
    )


async def test_ein_einzelner_abgewiesener_zugriff_zaehlt_nicht(coordinator):
    """Die Steuerung vergibt ihre Nonce nur einmal - ein 401 ist Alltag."""
    coordinator.client.auth_errors = AUTH_FEHLER_GRENZE - 1
    await coordinator._async_update_data()


async def test_mehrere_abweisungen_fragen_nach_dem_passwort(coordinator):
    coordinator.client.auth_errors = AUTH_FEHLER_GRENZE
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_eine_stumme_anlage_landet_in_den_reparaturen(hass, coordinator):
    coordinator.client.fetch_all.side_effect = TimeoutError("keine Antwort")
    for _ in range(3):
        with contextlib.suppress(UpdateFailed):
            await coordinator._async_update_data()

    eintrag = _stoerung(hass, coordinator)
    assert eintrag is not None
    assert eintrag.severity == ir.IssueSeverity.ERROR
    assert eintrag.translation_placeholders["anlage"] == "Heizhaus"


async def test_der_eintrag_verschwindet_von_selbst(hass, coordinator):
    """Der Teil, der bei Reparatureinträgen gern fehlt."""
    coordinator.client.fetch_all.side_effect = TimeoutError("keine Antwort")
    for _ in range(3):
        with contextlib.suppress(UpdateFailed):
            await coordinator._async_update_data()
    assert _stoerung(hass, coordinator) is not None

    coordinator.client.fetch_all.side_effect = None
    await coordinator._async_update_data()
    assert _stoerung(hass, coordinator) is None
