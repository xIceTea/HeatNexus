"""Befund in Home Assistant: sammelt ohne Automatik, speichert je Anlage, liefert den Stand."""

from __future__ import annotations

from datetime import timedelta

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

PREFIX = "/1/15/0"
KESSEL = "/1/15/1"
HEIZKREIS = "SN1-2-0"


class Coordinator:
    label = "Anlage A"
    host = "192.0.2.10"

    def __init__(self) -> None:
        """Ein Heizkreis und ein Kessel mit Zählern."""
        self.data = {
            "devices": [
                {
                    "type": "climate",
                    "id": f"{HEIZKREIS}-thermostat",
                    "device_id": HEIZKREIS,
                    "prefix": PREFIX,
                    "device_name": "Heizkreis",
                },
                {
                    "type": "sensor",
                    "id": "SN1-1-0-2-80-0",
                    "device_id": "SN1-1-0",
                    "oid": f"{KESSEL}/2/80/0",
                },
            ],
            "oids": {
                f"{PREFIX}/0/0/0": "8.5",
                f"{PREFIX}/1/2/0": "45.0",
                f"{PREFIX}/0/2/0": "44.0",
                f"{PREFIX}/1/1/0": "21.0",
                f"{PREFIX}/2/10/0": "0",
                f"{PREFIX}/3/21/0": "18.0",
                f"{KESSEL}/2/80/0": "6585",
                f"{KESSEL}/2/81/0": "18201",
                f"{KESSEL}/0/9/0": "50",
                f"{KESSEL}/11/2/0": "40",
            },
        }

    def async_add_listener(self, _rueckruf):
        return lambda: None


@pytest.fixture
async def anlage(hass):
    from homeassistant.config_entries import ConfigEntryState
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.befund.laufzeit import befund_holen
    from custom_components.heatnexus.const import DOMAIN

    eintrag = MockConfigEntry(domain=DOMAIN, state=ConfigEntryState.LOADED)
    eintrag.add_to_hass(hass)
    eintrag.runtime_data = {"coordinators": {"192.0.2.10": Coordinator()}}
    verwaltung = befund_holen(hass)
    await verwaltung.eintrag_starten(eintrag)
    yield verwaltung, eintrag
    await verwaltung.eintrag_stoppen(eintrag)


async def test_sammelt_ohne_automatik_und_liefert_stand(hass, anlage):
    from homeassistant.util import dt as dt_util

    verwaltung, _ = anlage
    anlage_id = verwaltung.anlagen()[0]
    sammler = verwaltung.sammler[anlage_id]
    jetzt = dt_util.now().replace(minute=0, second=0, microsecond=0)
    for m in range(0, 65, 5):
        await sammler.messen(jetzt + timedelta(minutes=m))
    stunde = sammler.archiv.stunden(HEIZKREIS)[0]
    assert stunde["at"] == 8.5
    assert stunde["eingriff"] is False
    stand = verwaltung.stand(anlage_id)
    assert [a["art"] for a in stand["abschnitte"]] == ["haus", "heizkreis", "kessel"]
    kessel = stand["abschnitte"][2]["befunde"][0]
    assert kessel["angaben"]["gesamt_h_je_start"] == pytest.approx(2.76, abs=0.01)


async def test_kesselleistung_in_kw(hass, anlage):
    from homeassistant.util import dt as dt_util

    verwaltung, _ = anlage
    sammler = next(iter(verwaltung.sammler.values()))
    jetzt = dt_util.now().replace(minute=0, second=0, microsecond=0)
    await sammler.messen(jetzt)
    await sammler.messen(jetzt + timedelta(hours=1))
    stunde = next(iter(sammler.archiv.stunden_k[KESSEL].values()))
    assert stunde["kwh"] == pytest.approx(20.0)


async def test_nachrechnen_ohne_recorder_ist_leer(hass, anlage):
    verwaltung, _ = anlage
    sammler = next(iter(verwaltung.sammler.values()))
    assert await sammler.nachrechnen() == 0


async def test_stoppen_speichert_und_entfernt(hass, anlage):
    verwaltung, eintrag = anlage
    await verwaltung.eintrag_stoppen(eintrag)
    assert verwaltung.anlagen() == []


async def test_websocket_liefert_anlagen(hass, hass_ws_client, anlage):
    from custom_components.heatnexus.befund.websocket import async_register_befund

    async_register_befund(hass)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "heatnexus/befund"})
    antwort = await client.receive_json()
    assert antwort["success"]
    stand = next(iter(antwort["result"]["anlagen"].values()))
    assert {"lage", "abschnitte", "anlage", "stand"} <= set(stand)


async def test_entfernen_verwirft_das_archiv(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.befund.laufzeit import eintrag_entfernt, speicher
    from custom_components.heatnexus.const import DOMAIN

    eintrag = MockConfigEntry(domain=DOMAIN, data={"systems": [{"host": "192.0.2.10"}]})
    await speicher(hass, eintrag.entry_id, "192.0.2.10").async_save({"fassung": 1})
    await eintrag_entfernt(hass, eintrag)
    assert await speicher(hass, eintrag.entry_id, "192.0.2.10").async_load() is None


async def test_sensoren_je_heizkreis_und_kessel(hass, anlage):
    from custom_components.heatnexus.befund.entitaeten import anmelden

    _, eintrag = anlage
    angelegt = []
    anmelden(hass, eintrag, angelegt.extend)
    kennungen = sorted(s.unique_id for s in angelegt)
    assert kennungen == sorted(
        [
            f"{HEIZKREIS}-befund-{art}"
            for art in ("waermespeicher", "heizgrenze", "raeume", "naechte", "vorlauf")
        ]
        + [f"SN1-1-0-befund-{art}" for art in ("laufzeit", "energie")]
    )
    sensor = next(s for s in angelegt if s.unique_id.endswith("heizgrenze"))
    sensor.hass = hass
    assert sensor.native_value is None
    assert sensor.extra_state_attributes["status"] == "sammelt"
