"""Der kanonische Schlüssel muss dort ankommen, wo er gebraucht wird.

`kanonisch.py` selbst ist geprüft — aber ein Tippfehler im Feldnamen oder eine
Kennung, die die Zerlegung nicht hergibt, legt den ganzen Mechanismus still,
**ohne dass irgendetwas auffällt**: Auf Deutsch greift weiterhin der
Namensrückfall, und erst eine fremdsprachige Anlage zeigt leere Karten. Diese
Datei prüft deshalb die Verdrahtung, nicht die Tabelle.
"""

from __future__ import annotations

import re

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def dashboard():
    from custom_components.heatnexus import dashboard

    return dashboard


def _muster(*ausdruecke: str) -> tuple[re.Pattern, ...]:
    return tuple(re.compile(a, re.IGNORECASE) for a in ausdruecke)


AUSSEN = _muster(r"au(ß|ss)entemperatur")


# ---------------------------------------------------------------------------
# _trifft: Schlüssel zuerst, Name als Rückfall
# ---------------------------------------------------------------------------
def test_der_schluessel_gewinnt_gegen_einen_fremden_namen(dashboard):
    """Genau dafür ist er da: englische Namen, deutsche Muster."""
    eintrag = {"name": "Outdoor temperature", "schluessel": "outdoor_temperature"}
    assert dashboard._trifft(eintrag, AUSSEN, "outdoor_temperature")


def test_ohne_schluessel_zaehlt_weiter_der_name(dashboard):
    """Die Tabelle deckt bei weitem nicht alles ab."""
    assert dashboard._trifft(
        {"name": "Außentemperatur", "schluessel": None}, AUSSEN, "outdoor_temperature"
    )


def test_ohne_angegebenen_schluessel_bleibt_es_beim_muster(dashboard):
    """Aufrufer ohne kanonische Entsprechung verhalten sich wie vorher."""
    assert dashboard._trifft({"name": "Außentemperatur", "schluessel": None}, AUSSEN)
    assert not dashboard._trifft({"name": "Kesseltemperatur", "schluessel": None}, AUSSEN)


def test_ein_fremder_schluessel_verhindert_den_rueckfall_nicht(dashboard):
    """Bewusst nachsichtig.

    Sonst fiele ein Datenpunkt weg, den das Muster bisher gefunden hat — eine
    stille Regression. Erst wenn ein Bereich vollständig umgestellt ist, darf
    „Schlüssel vorhanden, aber ein anderer" als „passt nicht" gelten.
    """
    eintrag = {"name": "Außentemperatur", "schluessel": "boiler_temperature"}
    assert dashboard._trifft(eintrag, AUSSEN, "outdoor_temperature")


def test_ein_eintrag_ohne_namen_bricht_nichts(dashboard):
    """Beim ersten Aufbau steht noch nicht alles bereit."""
    assert not dashboard._trifft({}, AUSSEN, "outdoor_temperature")


# ---------------------------------------------------------------------------
# _anlagen stempelt den Schlüssel auf jede Entität
# ---------------------------------------------------------------------------
async def test_jede_entitaet_traegt_ihren_schluessel(
    dashboard, hass, device_registry, entity_registry
):
    """Der Schritt dazwischen: ohne ihn liefe `_trifft` immer ins Muster.

    Gebaut wird eine echte Registry-Lage, keine Attrappe — die Kennung, aus
    der der Schlüssel entsteht, vergibt Home Assistant selbst.
    """
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.const import DOMAIN

    # Bewusst `MockConfigEntry`: Die Registry verlangt einen Eintrag, den sie
    # kennt, und dessen Signatur ändert sich zwischen HA-Fassungen.
    eintrag = MockConfigEntry(domain=DOMAIN, title="Heizhaus", data={}, options={})
    eintrag.add_to_hass(hass)
    eintrag_id = eintrag.entry_id

    geraet = device_registry.async_get_or_create(
        config_entry_id=eintrag_id,
        identifiers={(DOMAIN, "0000ABCD1234-0")},
        name="PuroWIN",
        manufacturer="Windhager",
    )

    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "0000ABCD1234-0-0-7-0",
        suggested_object_id="kesseltemperatur",
        device_id=geraet.id,
        original_name="Kesseltemperatur Ist",
        config_entry=eintrag,
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "0000ABCD1234-0-9-31-0",
        suggested_object_id="mindestlaufzeit",
        device_id=geraet.id,
        original_name="Mindestlaufzeit",
        config_entry=eintrag,
    )
    hass.states.async_set("sensor.kesseltemperatur", "63.5")
    hass.states.async_set("sensor.mindestlaufzeit", "20")
    await hass.async_block_till_done()

    anlagen = dashboard._anlagen(hass)
    entitaeten = [e for anlage in anlagen for teil in anlage["teile"] for e in teil["entitaeten"]]
    je_kennung = {e["entity_id"]: e.get("schluessel") for e in entitaeten}

    assert je_kennung["sensor.kesseltemperatur"] == "boiler_temperature"
    # Ohne kanonische Entsprechung bleibt das Feld leer – und der Name gilt.
    assert je_kennung["sensor.mindestlaufzeit"] is None
