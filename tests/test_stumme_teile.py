"""Teile, die die Steuerung führt, die aber keine Werte liefern, stehen in den Reparaturen."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from .conftest import ha_fehlt, requires_ha

pytestmark = requires_ha()

if not ha_fehlt():
    from homeassistant.const import CONF_HOST
    from homeassistant.helpers import issue_registry as ir

    from custom_components.heatnexus.const import CONF_LABEL, CONF_SYSTEMS, DOMAIN
    from custom_components.heatnexus.erkennungsstand import (
        stumme_teile_entfernen,
        stumme_teile_melden,
    )

HOST = "192.0.2.20"
STRUKTUR = [
    {
        "nodeId": 60,
        "name": "BioWIN",
        "functions": [
            {"fctId": 0, "fctType": 9, "lock": False, "name": "BioWIN"},
            {"fctId": 5, "fctType": 14, "lock": True, "name": "UMLZ (1)"},
        ],
    },
    {
        "nodeId": 15,
        "name": "WFBPK",
        "functions": [
            {"fctId": 1, "fctType": 16, "lock": False, "name": "Pellet"},
            {"fctId": 32, "fctType": -1, "lock": False, "name": "NV's"},
        ],
    },
    {
        "nodeId": 16,
        "name": "WFBPK",
        "functions": [
            {"fctId": 1, "fctType": 16, "lock": False, "name": "-"},
        ],
    },
]


@pytest.fixture
def anlage():
    from custom_components.heatnexus import client

    c = client.WindhagerHttpClient(HOST, "geheim", levels=["info", "operate"])
    c._teilnamen = c._teilnamen_lesen(STRUKTUR)
    c.devices = []
    return c


def test_die_namen_kommen_aus_knoten_und_funktion(anlage):
    assert anlage._teilnamen == {
        "/1/60/0": "BioWIN",
        "/1/15/1": "WFBPK Pellet",
        "/1/16/1": "WFBPK",
    }


def test_ein_teil_ohne_antwort_und_ohne_wert_ist_stumm(anlage):
    anlage._wurzel_ohne_antwort = {"/1/15/1", "/1/60/0"}
    anlage.devices = [
        {"id": "a", "oid": "/1/60/0/0/7/0", "device_id": anlage._geraetekennung("/1/60/0")},
        # Ein Meldungssensor hängt am Knoten und zählt nicht als Wert.
        {"id": "b", "device_id": anlage._geraetekennung("/1/15/1")},
    ]
    assert anlage.stumme_teile == ["WFBPK Pellet"]


def test_ein_teil_mit_antwort_ist_nicht_stumm(anlage):
    anlage._wurzel_ohne_antwort = set()
    assert anlage.stumme_teile == []


async def test_die_schweigende_wurzel_bleibt_vermerkt(anlage, monkeypatch):
    async def menue_abruf(url):
        return None, 502

    monkeypatch.setattr(anlage, "_menue_abruf", menue_abruf)
    anlage._wurzel_luecken, anlage._wurzel_ohne_antwort = set(), set()
    assert await anlage._read_function_menus("/1/15/1", 16) == {}
    # Die Lücke weicht dem Einzelweg; vermerkt bleibt, dass die Wurzel schwieg.
    assert not anlage._wurzel_luecken
    assert anlage._wurzel_ohne_antwort == {"/1/15/1"}


def _eintrag():
    eintrag = MagicMock()
    eintrag.entry_id = "e1"
    eintrag.data = {CONF_SYSTEMS: [{CONF_HOST: HOST, CONF_LABEL: "Heizraum"}]}
    return eintrag


def _eintrag_im_register(hass):
    return ir.async_get(hass).async_get_issue(DOMAIN, f"stumme_teile_e1_{HOST}")


async def test_stumme_teile_stehen_in_den_reparaturen(hass):
    stumme_teile_melden(hass, _eintrag(), HOST, ["WFBPK Pellet", "WFBPK"])
    eintrag = _eintrag_im_register(hass)
    assert eintrag is not None
    assert eintrag.is_persistent is True
    assert eintrag.translation_placeholders == {
        "anlage": "Heizraum",
        "teile": "WFBPK Pellet, WFBPK",
    }


async def test_ein_vollstaendiger_lauf_nimmt_den_eintrag_zurueck(hass):
    stumme_teile_melden(hass, _eintrag(), HOST, ["WFBPK"])
    stumme_teile_melden(hass, _eintrag(), HOST, [])
    assert _eintrag_im_register(hass) is None


async def test_das_entfernen_des_eintrags_raeumt_auf(hass):
    stumme_teile_melden(hass, _eintrag(), HOST, ["WFBPK"])
    stumme_teile_entfernen(hass, _eintrag())
    assert _eintrag_im_register(hass) is None
