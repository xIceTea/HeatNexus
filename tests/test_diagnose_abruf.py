"""Diagnoseexport: Zustand des Abrufs, ungeladener Eintrag, Hostnamen."""

from __future__ import annotations

from datetime import timedelta
import json
from types import SimpleNamespace

import pytest

from .conftest import requires_ha
from .test_diagnostics import _coordinator

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def diagnostics():
    from custom_components.heatnexus import diagnostics

    return diagnostics


def _eintrag(host: str, koordinator) -> SimpleNamespace:
    return SimpleNamespace(
        entry_id="eintrag1",
        version=2,
        subentries={},
        options={host: {"levels": ["info"]}},
        runtime_data={
            "name": "HeatNexus",
            "fassung": "1.14.0",
            "coordinators": {host: koordinator},
        },
    )


async def test_der_export_nennt_den_zustand_des_abrufs(diagnostics, hass):
    koordinator = _coordinator()
    koordinator.last_update_success = False
    koordinator.last_exception = OSError("Verbindung abgelehnt")
    koordinator.update_interval = timedelta(seconds=120)
    koordinator._fehlschlaege = 2

    daten = await diagnostics.async_get_config_entry_diagnostics(
        hass, _eintrag("192.0.2.10", koordinator)
    )

    abruf = daten["anlagen"]["anlage_1"]["abruf"]
    assert abruf["letzter_abruf_erfolgreich"] is False
    assert "Verbindung abgelehnt" in abruf["letzter_fehler"]
    assert abruf["takt_s"] == 120
    assert abruf["fehlschlaege_in_folge"] == 2
    assert abruf["abgemeldet"] == ["/1/60/0/9/9/0"]
    assert abruf["sprache"] == "de"


async def test_ein_nicht_geladener_eintrag_liefert_trotzdem_einen_export(diagnostics, hass):
    eintrag = SimpleNamespace(entry_id="eintrag1", version=2, subentries={}, options={})

    daten = await diagnostics.async_get_config_entry_diagnostics(hass, eintrag)

    assert daten["eintrag"]["geladen"] is False


async def test_ein_hostname_steht_nicht_im_export(diagnostics, hass):
    host = "heizung.example.net"
    koordinator = _coordinator()
    koordinator.client.host = host
    koordinator.last_exception = OSError(f"Cannot connect to host {host}:80")

    daten = await diagnostics.async_get_config_entry_diagnostics(hass, _eintrag(host, koordinator))

    assert host not in json.dumps(daten)
    assert "anlage_1" in daten["eintrag"]["optionen"]


async def test_eine_ipv6_adresse_steht_nicht_im_export(diagnostics, hass):
    host = "2001:db8::10"
    koordinator = _coordinator()
    koordinator.client.host = host

    daten = await diagnostics.async_get_config_entry_diagnostics(hass, _eintrag(host, koordinator))

    assert host not in json.dumps(daten)
