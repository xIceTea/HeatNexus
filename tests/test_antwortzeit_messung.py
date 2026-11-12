"""Messreihe: nur Anfragen im Abruf, Ring von 60 Minuten, Dauern der laufenden Stunde."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from .conftest import ha_fehlt, load_standalone, requires_ha


@pytest.fixture(scope="module")
def az():
    return load_standalone("client.antwortzeit")


def test_ausserhalb_des_abrufs_wird_nichts_erfasst(az):
    reihe = az.Messreihe(uhr=lambda: 10.0)
    reihe.antwort(0.2)
    reihe.fehler()
    assert reihe.eintraege() == ()


def test_im_abruf_zaehlen_antwort_und_fehler(az):
    reihe = az.Messreihe(uhr=lambda: 10.0)
    token = az.IM_ABRUF.set(True)
    try:
        reihe.antwort(0.25)
        reihe.fehler()
    finally:
        az.IM_ABRUF.reset(token)
    assert reihe.eintraege() == ((10.0, 250.0), (10.0, None))
    assert reihe.stunde_abholen() == [250.0]
    assert reihe.stunde_abholen() == []


def test_ring_haelt_eine_stunde(az):
    zeit = [0.0]
    reihe = az.Messreihe(uhr=lambda: zeit[0])
    token = az.IM_ABRUF.set(True)
    try:
        reihe.antwort(0.1)
        zeit[0] = az.HALTEN_S + 1.0
        reihe.antwort(0.1)
    finally:
        az.IM_ABRUF.reset(token)
    assert [z for z, _ in reihe.eintraege()] == [az.HALTEN_S + 1.0]


if not ha_fehlt():
    from custom_components.heatnexus.client import WindhagerHttpClient
    from custom_components.heatnexus.client.antwortzeit import IM_ABRUF, Messreihe


@requires_ha()
@pytest.mark.parametrize(
    ("status", "erwartet"),
    [
        (200, "antwort"),
        (404, "antwort"),
        (409, "antwort"),
        (503, "fehler"),
        (None, "fehler"),
        (401, None),
    ],
)
def test_transport_ordnet_status_zu(status, erwartet):
    client = WindhagerHttpClient.__new__(WindhagerHttpClient)
    client.messreihe = MagicMock()
    client._messen(0.3, status)
    if erwartet == "antwort":
        client.messreihe.antwort.assert_called_once_with(0.3)
        client.messreihe.fehler.assert_not_called()
    elif erwartet == "fehler":
        client.messreihe.fehler.assert_called_once_with()
        client.messreihe.antwort.assert_not_called()
    else:
        client.messreihe.antwort.assert_not_called()
        client.messreihe.fehler.assert_not_called()


def _client_mit_anfrage(fehler: BaseException):
    client = WindhagerHttpClient.__new__(WindhagerHttpClient)
    client._ensure_session = AsyncMock()
    client._semaphore = asyncio.Semaphore(1)
    client.request_count = client.request_errors = 0
    client.queue_seconds = client.request_seconds = 0.0
    client.messreihe = Messreihe()
    anfrage = MagicMock()
    anfrage.__aenter__ = AsyncMock(side_effect=fehler)
    anfrage.__aexit__ = AsyncMock(return_value=False)
    client._session = MagicMock()
    client._session.request = MagicMock(return_value=anfrage)
    return client


@requires_ha()
@pytest.mark.parametrize(
    ("fehler", "erwartet"),
    [(asyncio.CancelledError(), ()), (TimeoutError(), ((1.0, None),))],
)
async def test_abbruch_zaehlt_nicht_als_fehlantwort(fehler, erwartet):
    client = _client_mit_anfrage(fehler)
    client.messreihe._uhr = lambda: 1.0
    token = IM_ABRUF.set(True)
    try:
        with pytest.raises(type(fehler)):
            await client._get("http://192.0.2.1/api/1.0/lr/1/60")
    finally:
        IM_ABRUF.reset(token)
    assert client.messreihe.eintraege() == erwartet
