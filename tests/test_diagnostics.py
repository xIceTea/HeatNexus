"""Diagnoseexport: was drinsteht – und vor allem, was nicht.

Der Export landet in Fehlerberichten und wird oft ungelesen weitergereicht.
Adresse und Seriennummer dürfen darin nicht auftauchen, auch nicht als Teil
einer zusammengesetzten Kennung wie ``12345678-0-7-0``. Genau das prüft diese
Datei; alles andere am Export ist Beiwerk.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

SERIENNUMMER = "0000ABCD1234"
ADRESSE = "192.0.2.10"


@pytest.fixture(scope="module")
def diagnostics():
    from custom_components.heatnexus import diagnostics

    return diagnostics


def _client():
    return SimpleNamespace(
        neuron_by_node={"60": SERIENNUMMER},
        oids={"/1/60/0/0/7/0", "/1/60/0/2/1/0"},
        poll_oids={"/1/60/0/0/7/0"},
        poll_class={"/1/60/0/0/7/0": "fast", "/1/60/0/2/1/0": "slow"},
        abrufplan={"/1/60/0/0/7/0"},
        _dynamic_oids=set(),
        time_programs=[],
        _objects_supported=True,
        _vollstaendig=True,
        request_count=42,
        levels=["info", "operate"],
        enable_advanced=False,
        writable_advanced=False,
        host=ADRESSE,
        statistik=lambda: {"anfragen": 42, "anfragen_je_stunde": 120},
    )


def _coordinator():
    return SimpleNamespace(
        label="Heizhaus",
        client=_client(),
        data={
            "devices": [
                {
                    "id": f"{SERIENNUMMER}-0-7-0",
                    # Die frühere, adressgebundene Kennung. Sie hängt an jeder
                    # Beschreibung und trägt die Adresse mit Bindestrichen –
                    # ohne sie in der Vorlage bewiese der Test unten nichts.
                    "alt_id": "192-168-178-100-1-60-0-0-7-0",
                    "alt_device_id": "192-168-178-100-1-60-0",
                    "device_id": f"{SERIENNUMMER}-0",
                    "device_name": "PuroWIN",
                    "fct_type": 25,
                    "type": "temperature",
                    "level": "info",
                    "oid": "/1/60/0/0/7/0",
                },
                {
                    "id": f"{SERIENNUMMER}-2-1-0",
                    "alt_id": "192-168-178-100-1-60-0-2-1-0",
                    "alt_device_id": "192-168-178-100-1-60-0",
                    "device_id": f"{SERIENNUMMER}-0",
                    "device_name": "PuroWIN",
                    "fct_type": 25,
                    "type": "enum_sensor",
                    "level": "service",
                    "oid": "/1/60/0/2/1/0",
                },
            ],
            "status": {"60": "keine Meldung"},
            "oids": {"/1/60/0/0/7/0": "63.5"},
        },
    )


@pytest.fixture
def export(diagnostics, hass):
    """Der fertige Diagnoseexport eines Eintrags mit einer Anlage."""
    eintrag = SimpleNamespace(
        entry_id="eintrag1",
        version=1,
        options={ADRESSE: {"levels": ["info"]}, "password": "geheim"},
        runtime_data={"name": "HeatNexus", "coordinators": {ADRESSE: _coordinator()}},
    )
    return diagnostics.async_get_config_entry_diagnostics(hass, eintrag)


async def test_der_export_nennt_die_anlagen_durchnummeriert(export):
    daten = await export
    assert daten["eintrag"]["anlagen"] == 1
    assert list(daten["anlagen"]) == ["anlage_1"]
    assert daten["anlagen"]["anlage_1"]["bezeichnung"] == "Heizhaus"


async def test_keine_seriennummer_im_export(export):
    """Auch nicht als Teil einer Kennung – dort steckt sie in jeder Zeile."""
    daten = await export
    assert SERIENNUMMER not in json.dumps(daten)


async def test_keine_adresse_im_export(export):
    daten = await export
    text = json.dumps(daten)
    assert ADRESSE not in text
    # **Auch nicht mit Bindestrichen.** Die frühere Kennung trägt die Adresse
    # als `192-168-178-100-…`; ein Muster, das nach Punkten sucht, sieht sie
    # nicht. Bis 1.5.0-beta.4 stand sie deshalb in jeder Zeile des Exports.
    assert ADRESSE.replace(".", "-") not in text
    # Der Optionsschlüssel ist die Adresse der Anlage; er wird zu „anlage".
    assert "anlage" in daten["eintrag"]["optionen"]


async def test_das_passwort_bleibt_draussen(export):
    daten = await export
    assert daten["eintrag"]["optionen"]["password"] != "geheim"


async def test_die_seriennummer_bleibt_wiedererkennbar(export):
    """Geschwärzt, aber gleichbleibend – sonst ließe sich nichts zuordnen."""
    daten = await export
    kennungen = [b["id"] for b in daten["anlagen"]["anlage_1"]["beschreibungen"]]
    # `SN<Anlage>-<lfd. Seriennummer>`, dahinter unverändert die Datenpunktadresse.
    assert kennungen == ["SN1-1-0-7-0", "SN1-1-2-1-0"]


async def test_geraete_stehen_einmal_mit_ihrer_zahl(export):
    """Je Gerät eine Zeile, nicht je Datenpunkt."""
    geraete = (await export)["anlagen"]["anlage_1"]["geraete"]
    assert len(geraete) == 1
    assert geraete[0]["name"] == "PuroWIN"
    assert geraete[0]["entitaeten"] == 2


async def test_entitaeten_werden_nach_typ_und_ebene_gezaehlt(export):
    anlage = (await export)["anlagen"]["anlage_1"]
    assert anlage["entitaeten_nach_typ"] == {"enum_sensor": 1, "temperature": 1}
    assert anlage["entitaeten_nach_ebene"] == {"info": 1, "service": 1}


async def test_das_abrufverhalten_geht_mit(export):
    """Ohne die Zahlen ist jede Aussage über den Abruf geschätzt."""
    assert (await export)["anlagen"]["anlage_1"]["abrufverhalten"]["anfragen"] == 42


async def test_die_registrierung_zaehlt_was_home_assistant_fuehrt(diagnostics, hass):
    """Zwei Entitäten sind registriert, eine davon abgeschaltet und verwaist.

    Erst diese Zahlen zeigen, ob eine vermisste Entität gar nicht entstand,
    abgeschaltet wurde oder aus einer früheren Erkennung übrig ist.
    """
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    konfig = MockConfigEntry(domain="heatnexus", entry_id="eintrag1", data={}, options={})
    konfig.add_to_hass(hass)
    registrierung = er.async_get(hass)
    registrierung.async_get_or_create(
        "sensor", "heatnexus", f"{SERIENNUMMER}-0-7-0", config_entry=konfig
    )
    registrierung.async_get_or_create(
        "sensor",
        "heatnexus",
        "fremde-kennung",
        config_entry=konfig,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    eintrag = SimpleNamespace(
        entry_id="eintrag1",
        version=1,
        options={},
        runtime_data={"name": "HeatNexus", "coordinators": {ADRESSE: _coordinator()}},
    )
    zahlen = (await diagnostics.async_get_config_entry_diagnostics(hass, eintrag))["registrierung"]
    assert zahlen["entitaeten"] == 2
    assert zahlen["abgeschaltet"] == 1
    assert zahlen["nach_bereich"] == {"sensor": 2}
    assert zahlen["verwaist"] == 1
    assert zahlen["verwaiste_kennungen"] == ["fremde-kennung"]
    # Die verwaiste Zeile ist abgeschaltet, steht also niemandem im Weg.
    assert zahlen["verwaist_aktiv"] == 0


async def test_die_diagnose_nennt_manuell_eingeschaltete(diagnostics, hass):
    """Ab Werk aus und trotzdem aktiv: Das war jemand von Hand."""
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    konfig = MockConfigEntry(domain="heatnexus", entry_id="eintrag2", data={}, options={})
    konfig.add_to_hass(hass)
    registrierung = er.async_get(hass)
    registrierung.async_get_or_create(
        "sensor", "heatnexus", f"{SERIENNUMMER}-0-7-0", config_entry=konfig
    )

    koordinator = _coordinator()
    koordinator.data["devices"][0]["enabled_default"] = False
    eintrag = SimpleNamespace(
        entry_id="eintrag2",
        version=1,
        options={},
        runtime_data={"name": "HeatNexus", "coordinators": {ADRESSE: koordinator}},
    )
    zahlen = (await diagnostics.async_get_config_entry_diagnostics(hass, eintrag))["registrierung"]
    assert zahlen["manuell_eingeschaltet"] == 1


def test_eine_adresse_wird_als_schluessel_erkannt(diagnostics):
    assert diagnostics._ist_adresse("192.0.2.10")
    assert not diagnostics._ist_adresse("levels")
    assert not diagnostics._ist_adresse(42)


async def test_jede_beschreibung_nennt_ihre_klasse_und_ob_sie_gelesen_wird(export):
    """Ohne beides ist bei einem Fehlerbericht offen, warum ein Wert fehlt."""
    anlage = (await export)["anlagen"]["anlage_1"]
    nach_oid = {b["oid"]: b for b in anlage["beschreibungen"]}

    assert nach_oid["/1/60/0/0/7/0"]["poll_klasse"] == "fast"
    assert nach_oid["/1/60/0/0/7/0"]["im_abruf"] is True
    assert nach_oid["/1/60/0/2/1/0"]["im_abruf"] is False
    assert anlage["anlage"]["abrufklassen"] == {"fast": 1}
