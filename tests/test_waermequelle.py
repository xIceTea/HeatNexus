"""Wärmequellen, die nicht an der Steuerung hängen.

Sie entstehen aus den Optionen und lesen fremde Entitäten. Geprüft wird, dass
ihre Kennung stabil bleibt und dass die Anzeige nur behauptet, was gemessen
wurde.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

SOLAR = {
    "id": "q1",
    "name": "Solaranlage",
    "art": "solar",
    "bedingung": {
        "art": "differenz",
        "quelle": "sensor.kollektor",
        "gegen": "sensor.puffer",
        "ein": 8,
        "aus": 3,
    },
}


@pytest.fixture(scope="module")
def modul():
    from custom_components.heatnexus import waermequelle

    return waermequelle


def _koordinator(host="192.0.2.10", label="Anlage 1"):
    """Ein Koordinator, dessen Steuerung ihre Seriennummer kennt."""
    return SimpleNamespace(
        host=host,
        label=label,
        client=SimpleNamespace(steuerung_kennung=lambda: "SN1"),
    )


def _eintrag(quellen):
    from custom_components.heatnexus.const import CONF_QUELLEN

    return SimpleNamespace(options={"192.0.2.10": {CONF_QUELLEN: list(quellen)}})


def test_jede_quelle_wird_zu_einer_beschreibung(modul):
    beschreibungen = modul.beschreibungen(_eintrag([SOLAR]), _koordinator())

    assert len(beschreibungen) == 1
    assert beschreibungen[0]["id"] == "SN1-waermequelle-q1"
    assert beschreibungen[0]["name"] == "Solaranlage"
    assert beschreibungen[0]["bedingung"]["ein"] == 8


def test_eine_quelle_unbekannter_bauart_wird_nicht_gebaut(modul):
    beschreibungen = modul.beschreibungen(
        _eintrag([{**SOLAR, "art": "kernfusion"}]), _koordinator()
    )

    assert beschreibungen == []


def test_quellen_einer_anderen_anlage_bleiben_dort(modul):
    beschreibungen = modul.beschreibungen(_eintrag([SOLAR]), _koordinator(host="192.0.2.99"))

    assert beschreibungen == []


def test_die_quelle_haengt_unter_ihrer_steuerung(modul):
    from custom_components.heatnexus.const import DOMAIN

    beschreibung = modul.beschreibungen(_eintrag([SOLAR]), _koordinator())[0]

    info = modul.geraet_info(_koordinator(), beschreibung)

    assert info["identifiers"] == {(DOMAIN, "SN1-waermequelle-q1")}
    assert info["name"] == "Anlage 1 · Solaranlage"
    assert info["via_device"] == (DOMAIN, "SN1")


def test_alle_kennungen_zaehlen_zum_bestand(modul):
    kennungen = modul.kennungen(_eintrag([SOLAR]), {"192.0.2.10": _koordinator()})

    assert kennungen == {"SN1-waermequelle-q1"}


# ---------------------------------------------------------------------------
# Die Entität
# ---------------------------------------------------------------------------
def _sensor(hass, beschreibung=None):
    from custom_components.heatnexus.binary_sensor import WaermequelleBinarySensor
    from custom_components.heatnexus.waermequelle import beschreibungen

    beschreibung = beschreibung or beschreibungen(_eintrag([SOLAR]), _koordinator())[0]
    entitaet = WaermequelleBinarySensor(_koordinator(), beschreibung)
    entitaet.hass = hass
    return entitaet


async def test_die_quelle_liefert_waerme_ueber_der_einschaltschwelle(hass):
    hass.states.async_set("sensor.kollektor", "70")
    hass.states.async_set("sensor.puffer", "50")
    entitaet = _sensor(hass)

    entitaet._auswerten()

    assert entitaet.is_on is True


async def test_zwischen_den_schwellen_bleibt_es_beim_bisherigen_ergebnis(hass):
    """Ohne den Zwischenbereich flattert die Anzeige an der Grenze."""
    hass.states.async_set("sensor.kollektor", "55")
    hass.states.async_set("sensor.puffer", "50")
    entitaet = _sensor(hass)
    entitaet._laeuft = True

    entitaet._auswerten()

    assert entitaet.is_on is True


async def test_unter_der_ausschaltschwelle_endet_die_lieferung(hass):
    hass.states.async_set("sensor.kollektor", "51")
    hass.states.async_set("sensor.puffer", "50")
    entitaet = _sensor(hass)
    entitaet._laeuft = True

    entitaet._auswerten()

    assert entitaet.is_on is False


async def test_ohne_messwert_wird_keine_lieferung_behauptet(hass):
    """Eine fehlende Entität darf keine Wärme vortäuschen."""
    hass.states.async_set("sensor.kollektor", "70")
    entitaet = _sensor(hass)
    entitaet._laeuft = True

    entitaet._auswerten()

    assert entitaet.is_on is False


async def test_ein_zustand_als_bedingung_braucht_keine_schwelle(hass):
    from custom_components.heatnexus.waermequelle import beschreibungen

    heizstab = {
        "id": "q2",
        "name": "Heizstab",
        "art": "heizstab",
        "bedingung": {"art": "zustand", "quelle": "switch.heizstab"},
    }
    hass.states.async_set("switch.heizstab", "on")
    entitaet = _sensor(hass, beschreibungen(_eintrag([heizstab]), _koordinator())[0])

    entitaet._auswerten()
    assert entitaet.is_on is True

    hass.states.async_set("switch.heizstab", "off")
    entitaet._auswerten()
    assert entitaet.is_on is False
