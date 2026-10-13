"""Bedienung am Thermostat: Merker, optimistische Anzeige und Schreibfehler."""

from __future__ import annotations

import pytest

from .conftest import requires_ha
from .test_plattformen import _entitaet

pytestmark = requires_ha()


class _Hass:
    """Hält Hintergrundaufgaben fest, statt sie laufen zu lassen."""

    def __init__(self) -> None:
        """Leere Aufzeichnung."""
        self.aufgaben: list[str] = []

    def async_create_task(self, coro, *_args, **_kwargs):
        self.aufgaben.append(coro.__name__)
        coro.close()

    def async_create_background_task(self, coro, name, *_args, **_kwargs):
        self.async_create_task(coro)


class _Eintrag:
    def __init__(self) -> None:
        """Leere Aufzeichnung."""
        self.hintergrund: list[str] = []

    def async_create_background_task(self, hass, coro, name, *_args, **_kwargs):
        self.hintergrund.append(name)
        coro.close()


class _Plattform:
    def __init__(self) -> None:
        """Eine Plattform mit Konfigurationseintrag."""
        self.config_entry = _Eintrag()


@pytest.fixture
def thermostat(monkeypatch):
    from custom_components.heatnexus import climate as modul

    entitaet, koordinator = _entitaet(
        modul.WindhagerThermostatClimate,
        {"/1/15/0/3/50/0": "6", "/1/15/0/2/10/0": "0"},
        prefix="/1/15/0",
        id="SN1-15-0-1-1-0",
    )
    entitaet.hass = _Hass()
    entitaet.platform = _Plattform()
    entitaet.async_write_ha_state = lambda: None
    geplant: list[float] = []

    def _spaeter(_hass, verzoegerung, _aktion):
        geplant.append(verzoegerung)
        return lambda: None

    monkeypatch.setattr(modul, "async_call_later", _spaeter)
    entitaet.geplant = geplant
    return entitaet, koordinator, modul


async def test_eine_gewaehlte_voreinstellung_loescht_den_ruecksprung(thermostat):
    entitaet, _, _ = thermostat
    entitaet._modus_davor = 6
    await entitaet.async_set_preset_mode("4")
    assert entitaet._modus_davor is None


async def test_ein_gewaehlter_modus_loescht_den_ruecksprung(thermostat):
    entitaet, _, _ = thermostat
    entitaet._modus_davor = 6
    await entitaet.async_set_hvac_mode("off")
    assert entitaet._modus_davor is None


async def test_ein_schreibfehler_nimmt_die_anzeige_zurueck(thermostat):
    entitaet, koordinator, _ = thermostat
    entitaet._modus_davor = 0

    async def kaputt(_oid, _wert):
        raise RuntimeError("409")

    koordinator.client.update = kaputt
    with pytest.raises(RuntimeError):
        await entitaet.async_set_preset_mode("4")
    assert entitaet._optimistic_mode is None
    assert entitaet._modus_davor == 0
    assert entitaet.preset_mode == "6"


async def test_eine_fehlgeschlagene_vorgabe_hinterlaesst_keinen_merker(thermostat):
    entitaet, koordinator, _ = thermostat

    async def kaputt(_oid, _wert):
        raise RuntimeError("Zeitüberschreitung")

    koordinator.client.update = kaputt
    with pytest.raises(RuntimeError):
        await entitaet.async_set_vorgabe(21.0, 60)
    assert entitaet._modus_davor is None
    assert entitaet._optimistic_target is None
    assert entitaet._optimistic_mode is None


async def test_die_optimistische_anzeige_laeuft_auch_ohne_abruf_ab(thermostat):
    entitaet, _, modul = thermostat
    await entitaet.async_set_preset_mode("4")
    assert entitaet.geplant
    assert min(entitaet.geplant) > modul.OPTIMISTIC_MAX_AGE_S


async def test_nach_der_bedienung_liest_der_koordinator_nach(thermostat):
    entitaet, koordinator, _ = thermostat
    await entitaet.async_set_preset_mode("4")
    assert koordinator.nachgefasst
