"""Verhalten des zyklischen Abrufs, wenn die Anlage nicht antwortet.

Eine Steuerung, die gerade neu startet oder unter Last steht, bekommt sonst
alle dreißig Sekunden eine volle Runde Anfragen und kommt nicht zur Ruhe.
Deshalb wird der Abstand nach jedem Fehlschlag verdoppelt – und, genauso
wichtig, nach der ersten gelungenen Antwort wieder auf den gewählten Takt
zurückgestellt. Ohne das Zurückstellen bliebe die Anlage nach einer einzigen
Störung dauerhaft im Fünf-Minuten-Takt.
"""

from __future__ import annotations

import contextlib
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from .conftest import ha_fehlt, requires_ha

pytestmark = requires_ha()

# **Vor** dem ersten Test importieren, nicht darin. Sobald die Fixture `hass`
# läuft, zeigt `custom_components` auf das Testverzeichnis der Testumgebung,
# und die eigene Integration ist von dort aus nicht mehr zu finden.
if not ha_fehlt():
    from custom_components.heatnexus.const import BACKOFF_MAX
    from custom_components.heatnexus.coordinator import WindhagerDataUpdateCoordinator


@pytest.fixture
def coordinator(hass):
    eintrag = MagicMock()
    eintrag.data = {"name": "Heizhaus"}
    eintrag.title = "Heizhaus"
    eintrag.entry_id = "abc123"
    client = MagicMock()
    # Eine Attrappe liefert sonst auch für Zähler wieder eine Attrappe, und der
    # Vergleich mit einer Zahl scheitert.
    client.auth_errors = 0
    client.fetch_all = AsyncMock(return_value={"oids": {}, "devices": []})
    return WindhagerDataUpdateCoordinator(
        hass, client, eintrag, "192.0.2.1", "Heizhaus", update_interval=30
    )


async def test_ohne_stoerung_bleibt_der_takt(coordinator):
    await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(seconds=30)


async def test_nach_fehlschlaegen_wird_der_abstand_groesser(coordinator):
    """Solange noch kein Wert dasteht, ist die Zeitüberschreitung ein Fehlschlag.

    Ein leeres Ergebnis als *Erfolg* abzulegen hieß, dass jeder Leser der
    Koordinatordaten eine Anlage ohne Datenpunkte sah. Der Abstand wächst
    trotzdem – darum geht es hier.
    """
    from homeassistant.helpers.update_coordinator import UpdateFailed

    coordinator.client.fetch_all.side_effect = TimeoutError("keine Antwort")

    with contextlib.suppress(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(seconds=60)

    with contextlib.suppress(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(seconds=120)


async def test_der_abstand_waechst_nicht_ins_unendliche(coordinator):
    from homeassistant.helpers.update_coordinator import UpdateFailed

    coordinator.client.fetch_all.side_effect = TimeoutError("keine Antwort")
    for _ in range(10):
        with contextlib.suppress(UpdateFailed):
            await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(seconds=BACKOFF_MAX)


async def test_die_erste_antwort_stellt_den_takt_zurueck(coordinator):
    """Der Punkt, an dem so etwas sonst hängen bleibt."""
    from homeassistant.helpers.update_coordinator import UpdateFailed

    coordinator.client.fetch_all.side_effect = TimeoutError("keine Antwort")
    with contextlib.suppress(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(seconds=60)

    coordinator.client.fetch_all.side_effect = None
    await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(seconds=30)
    assert coordinator.consecutive_timeouts == 0
