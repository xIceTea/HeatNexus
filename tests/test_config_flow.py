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


def test_anlagenkennung_kommt_aus_der_seriennummer(flow):
    """Die Kennung darf nicht an der Adresse hängen."""
    struktur = [
        {"nodeId": 60, "neuronId": "0702bb000002"},
        {"nodeId": 14, "neuronId": "0702cc000003"},
        {"nodeId": 15, "neuronId": "0702aa000001"},
    ]
    # Immer die kleinste Seriennummer – unabhängig von der Reihenfolge, in der
    # die Anlage ihre Knoten meldet.
    assert flow.anlagenkennung(struktur) == "0702aa000001"
    assert flow.anlagenkennung(list(reversed(struktur))) == "0702aa000001"


def test_anlagenkennung_ohne_seriennummer(flow):
    assert flow.anlagenkennung([{"nodeId": 1}]) == ""
    assert flow.anlagenkennung([]) == ""


def test_menueschritt_fuer_jede_anlage(flow):
    """Auch die siebte Anlage muss einen Schritt bekommen."""
    optionen = flow.WindhagerOptionsFlow()
    assert callable(optionen.async_step_anlage_0)
    assert callable(optionen.async_step_anlage_9)
    for unbekannt in ("async_step_anlage_x", "irgendwas_anderes"):
        with pytest.raises(AttributeError):
            getattr(optionen, unbekannt)


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


def test_zeitwerte_sind_abwaehlbar_und_standardmaessig_aus(flow):
    """Uhrzeiten und Datumsfelder sind Einstellwerte, keine Messwerte.

    Wer sie doch alle haben will, setzt den Haken einmal, statt jede Entität
    einzeln in Home Assistant einzuschalten.
    """
    from custom_components.heatnexus.const import CONF_ZEITWERTE

    assert flow.normalize_options({})[CONF_ZEITWERTE] is False
    assert flow.normalize_options({CONF_ZEITWERTE: True})[CONF_ZEITWERTE] is True


def test_zeitwerte_aendern_den_umfang(flow):
    """Sie entscheiden, was abgefragt wird – der Erkennungsstand gilt dann nicht mehr."""
    from custom_components.heatnexus import _scope_fingerprint

    umfang = {
        "levels": ["info", "operate"],
        "enable_advanced": False,
        "writable_advanced": False,
        "username": "USER",
    }
    assert _scope_fingerprint(umfang) != _scope_fingerprint({**umfang, "zeitwerte": True})


def test_kesselart_wird_uebernommen_und_geprueft(flow):
    """Die Kesselart wirkt nur auf das Schaubild – aber sie muss ankommen."""
    from custom_components.heatnexus.const import CONF_KESSELART, KESSELART_AUTO

    assert flow.normalize_options({CONF_KESSELART: "pellets"})[CONF_KESSELART] == "pellets"
    # Fehlt sie oder ist sie unbekannt, wird automatisch erkannt.
    assert flow.normalize_options({})[CONF_KESSELART] == KESSELART_AUTO
    assert flow.normalize_options({CONF_KESSELART: "dampfmaschine"})[CONF_KESSELART] == (
        KESSELART_AUTO
    )


def test_kesselart_aendert_den_umfang_nicht(flow):
    """Eine andere Zeichnung darf die Anlage nicht neu einlesen lassen.

    Der Erkennungsstand hängt am Umfang. Käme die Kesselart darin vor, kostete
    jede Umstellung einen vollen Neuabzug von 30–120 s.
    """
    from custom_components.heatnexus import _scope_fingerprint

    umfang = {
        "levels": ["info", "operate"],
        "enable_advanced": False,
        "writable_advanced": False,
        "username": "USER",
    }
    assert _scope_fingerprint(umfang) == _scope_fingerprint({**umfang, "kesselart": "pellets"})
