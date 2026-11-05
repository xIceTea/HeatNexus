"""Keine Entität bietet einen Namen an, den Home Assistant abgekündigt hat.

Abgekündigte Entitätsnamen meldet HA nur einmal, beim Laden der Klasse. Dieser
Test fragt die Basisklassen direkt, unabhängig davon, wann das Modul geladen wurde.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


def _abgekuendigte_mitglieder() -> tuple[type, ...]:
    from homeassistant.helpers import deprecation

    namen = ("DeprecatedEntityProperty", "DeprecatedEntityAttr")
    return tuple(t for n in namen if (t := getattr(deprecation, n, None)) is not None)


def _entitaetsklassen() -> list[type]:
    from homeassistant.helpers.entity import Entity

    import custom_components.heatnexus as paket

    klassen = []
    for info in pkgutil.walk_packages(paket.__path__, f"{paket.__name__}."):
        modul = importlib.import_module(info.name)
        klassen += [
            k
            for _, k in inspect.getmembers(modul, inspect.isclass)
            if issubclass(k, Entity) and k.__module__ == modul.__name__
        ]
    return klassen


def test_der_waechter_faengt_abgekuendigte_namen_beim_laden_der_klasse():
    from homeassistant.components.climate import ClimateEntity

    from . import conftest

    if not hasattr(ClimateEntity, "native_current_temperature"):
        pytest.skip("Diese Fassung kennt die native_-Namen der Klima-Entität nicht")
    vorher = len(conftest._ABKUENDIGUNGEN.meldungen)

    class AlteKlima(ClimateEntity):
        _attr_temperature_unit = "°C"

    neu = conftest._ABKUENDIGUNGEN.meldungen[vorher:]
    del conftest._ABKUENDIGUNGEN.meldungen[vorher:]
    assert any("_attr_temperature_unit" in m for m in neu), neu


def test_keine_entitaet_bietet_abgekuendigte_namen_an():
    arten = _abgekuendigte_mitglieder()
    if not arten:
        pytest.skip("Diese Fassung kündigt keine Entitätsnamen an der Klasse ab")
    klassen = _entitaetsklassen()
    assert klassen
    funde = []
    for klasse in klassen:
        eigene = [k for k in klasse.__mro__ if k.__module__.startswith("custom_components.")]
        fremde = [k for k in klasse.__mro__ if k.__module__.startswith("homeassistant.")]
        abgekuendigt = {n for b in fremde for n, w in vars(b).items() if isinstance(w, arten)}
        funde += [
            f"{k.__module__}.{k.__qualname__}.{n}"
            for k in eigene
            for n in abgekuendigt & set(vars(k))
        ]
    assert not funde, sorted(set(funde))
