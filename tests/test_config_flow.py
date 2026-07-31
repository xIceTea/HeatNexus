"""Einrichtungsdialog: Adressbereinigung und Optionsprüfung."""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def flow():
    from custom_components.heatnexus import config_flow

    return config_flow


@pytest.mark.parametrize(
    ("eingabe", "erwartet"),
    [
        ("192.0.2.10", "192.0.2.10"),
        (" 192.0.2.10 ", "192.0.2.10"),
        ("http://192.0.2.10/", "192.0.2.10"),
        ("https://192.0.2.10:8080/api", "192.0.2.10"),
        ("192.0.2.10/api/1.0", "192.0.2.10"),
    ],
)
def test_clean_host(flow, eingabe, erwartet):
    assert flow.clean_host(eingabe) == erwartet


def test_info_und_betreiberebene_sind_pflicht(flow):
    from custom_components.heatnexus.const import (
        CONF_LEVELS,
        LEVEL_INFO,
        LEVEL_OPERATE,
    )

    options = flow.normalize_options({CONF_LEVELS: ["service"]})
    assert LEVEL_INFO in options[CONF_LEVELS]
    assert LEVEL_OPERATE in options[CONF_LEVELS]


def test_unbekannte_ebene_wird_verworfen(flow):
    from custom_components.heatnexus.const import CONF_LEVELS

    options = flow.normalize_options({CONF_LEVELS: ["info", "quatsch", "oem"]})
    assert options[CONF_LEVELS] == ["info", "operate", "oem"]


def test_schalter_und_intervall_werden_uebernommen(flow):
    from custom_components.heatnexus.const import (
        CONF_ENABLE_ADVANCED,
        CONF_UPDATE_INTERVAL,
        CONF_WRITABLE_ADVANCED,
    )

    options = flow.normalize_options(
        {
            CONF_ENABLE_ADVANCED: True,
            CONF_WRITABLE_ADVANCED: True,
            CONF_UPDATE_INTERVAL: 45.0,
        }
    )
    assert options[CONF_ENABLE_ADVANCED] is True
    assert options[CONF_WRITABLE_ADVANCED] is True
    assert options[CONF_UPDATE_INTERVAL] == 45
