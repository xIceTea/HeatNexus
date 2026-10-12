"""Einrichtungsdialog, Neu konfigurieren und Neu anmelden im laufenden Home Assistant.

Der Client ist die Attrappe aus `test_einrichtung.py`; geprüft wird, was die
Abläufe am Eintrag hinterlassen.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from .conftest import ha_fehlt, requires_frontend, requires_ha, requires_moderne_ha
from .test_einrichtung import AttrappenClient

pytestmark = [requires_ha(), requires_frontend(), requires_moderne_ha()]

if not ha_fehlt():  # pragma: no branch - ohne HA wird die Datei übersprungen
    from custom_components.heatnexus.const import (
        CONF_SPRACHE,
        CONF_SPRACHE_ANLAGE,
        CONF_SYSTEMS,
        DOMAIN,
        SPRACHE_WIE_HEATNEXUS,
    )

ALT = "192.0.2.10"
NEU = "192.0.2.20"
KENNUNG = "0000ABCD1234"
STRUKTUR = [{"nodeId": 15, "neuronId": KENNUNG, "functions": []}]


@pytest.fixture(autouse=True)
def _eigene_integration(enable_custom_integrations):
    """Ohne diesen Schalter legt die Testumgebung eigene Integrationen nicht vor."""
    return enable_custom_integrations


@pytest.fixture(autouse=True)
async def _aufraeumen(hass):
    """Zeitgeber ablaufen lassen und jeden geladenen Eintrag entladen."""
    yield

    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    from custom_components.heatnexus.einlesen import MELDUNG_VERZOEGERUNG

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=MELDUNG_VERZOEGERUNG + 1))
    await hass.async_block_till_done()
    for geladen in hass.config_entries.async_entries(DOMAIN):
        if geladen.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(geladen.entry_id)
    await hass.async_block_till_done()


def _verbindung(struktur: list | None = None, fehler: Exception | None = None) -> AsyncMock:
    """Die Prüfung der Verbindung, ohne ins Netz zu gehen."""
    if fehler is not None:
        return AsyncMock(side_effect=fehler)
    return AsyncMock(return_value=STRUKTUR if struktur is None else struktur)


@pytest.fixture
def eintrag(hass):
    """Ein Eintrag mit einer Steuerung, wie ihn der Dialog anlegt."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    eintrag = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=2,
        title="Heizhaus",
        unique_id=KENNUNG,
        data={
            "name": "Heizhaus",
            CONF_SYSTEMS: [
                {"host": ALT, "password": "geheim", "label": "Heizhaus", "username": "USER"}
            ],
        },
        options={ALT: {"levels": ["info", "operate"]}, CONF_SPRACHE: "auto"},
    )
    eintrag.add_to_hass(hass)
    return eintrag


async def _einrichten(hass, eintrag) -> None:
    with patch("custom_components.heatnexus.WindhagerHttpClient", AttrappenClient):
        assert await hass.config_entries.async_setup(eintrag.entry_id) is True
        await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# Neue Einrichtung
# ---------------------------------------------------------------------------
async def _neu_einrichten(hass) -> Any:
    """Den Einrichtungsdialog einmal ganz durchlaufen."""
    with (
        patch("custom_components.heatnexus.config_flow.validate_connection", _verbindung()),
        patch("custom_components.heatnexus.WindhagerHttpClient", AttrappenClient),
    ):
        ablauf = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        ablauf = await hass.config_entries.flow.async_configure(
            ablauf["flow_id"], {"name": "Heizhaus", "count": 1}
        )
        ablauf = await hass.config_entries.flow.async_configure(
            ablauf["flow_id"],
            {"label": "Heizhaus", "host": ALT, "username": "USER", "password": "geheim"},
        )
        ablauf = await hass.config_entries.flow.async_configure(ablauf["flow_id"], {})
        await hass.async_block_till_done()
    return ablauf["result"]


@pytest.mark.parametrize("ha_sprache", ["en", "nl"])
async def test_ein_frischer_eintrag_folgt_der_sprache_von_home_assistant(hass, ha_sprache):
    """Die Umstellung alter Einträge darf einen neuen nicht auf Deutsch festlegen."""
    from custom_components.heatnexus.texte import sprache_des_eintrags

    hass.config.language = ha_sprache

    eintrag = await _neu_einrichten(hass)

    assert eintrag.options[CONF_SPRACHE_ANLAGE] == SPRACHE_WIE_HEATNEXUS
    assert sprache_des_eintrags(hass, eintrag) == ha_sprache
