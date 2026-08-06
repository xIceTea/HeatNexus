"""Digest-Anmeldung an der Anlage.

Bis 1.5.0 lag dafür eine eigene Datei im Projekt, abgeleitet von `requests`.
Jetzt macht es aiohttp selbst — und das ist der Grund für diesen Test: Die
Anmeldung ist der einzige Weg zur Anlage. Fällt sie aus, antwortet die
Steuerung auf **jede** Anfrage mit `401`, und die Integration steht still.

Geprüft wird gegen einen kleinen Server, der sich genauso verhält wie die
Steuerung: erst eine Aufforderung (`401` mit `WWW-Authenticate: Digest`), dann
die Antwort nur, wenn die Rückgabe stimmt.
"""

from __future__ import annotations

import hashlib

import pytest

from .conftest import requires_digest_auth, requires_ha

pytestmark = [requires_ha(), requires_digest_auth()]

BENUTZER = "USER"
PASSWORT = "geheim"
NONCE = "dcd98b7102dd2f0e8b11d0f600bfb0c093"
REALM = "Windhager"


def _erwartete_antwort(methode: str, pfad: str, nonce_count: str, cnonce: str, qop: str) -> str:
    """Die Rückgabe, die ein richtig rechnender Client schicken muss."""
    ha1 = hashlib.md5(f"{BENUTZER}:{REALM}:{PASSWORT}".encode()).hexdigest()
    ha2 = hashlib.md5(f"{methode}:{pfad}".encode()).hexdigest()
    if qop:
        return hashlib.md5(f"{ha1}:{NONCE}:{nonce_count}:{cnonce}:{qop}:{ha2}".encode()).hexdigest()
    return hashlib.md5(f"{ha1}:{NONCE}:{ha2}".encode()).hexdigest()


def _kopf_zerlegen(kopf: str) -> dict[str, str]:
    felder = {}
    for teil in kopf.removeprefix("Digest ").split(","):
        if "=" not in teil:
            continue
        schluessel, wert = teil.split("=", 1)
        felder[schluessel.strip()] = wert.strip().strip('"')
    return felder


@pytest.fixture
async def anlage(aiohttp_server, socket_enabled):
    """Ein Server, der sich wie die Steuerung anmelden lässt."""
    from aiohttp import web

    versuche: list[str] = []

    async def datenpunkt(request: web.Request) -> web.Response:
        kopf = request.headers.get("Authorization", "")
        versuche.append(kopf)
        if not kopf.startswith("Digest "):
            return web.Response(
                status=401,
                headers={
                    "WWW-Authenticate": (
                        f'Digest realm="{REALM}", qop="auth", nonce="{NONCE}", '
                        'opaque="5ccc069c403ebaf9f0171e9517f40e41"'
                    )
                },
            )
        felder = _kopf_zerlegen(kopf)
        erwartet = _erwartete_antwort(
            request.method,
            request.path_qs,
            felder.get("nc", ""),
            felder.get("cnonce", ""),
            felder.get("qop", ""),
        )
        if felder.get("response") != erwartet:
            return web.Response(status=401, text="falsche Antwort")
        return web.json_response({"OID": "/1/15/0/0/0/0", "value": "12.5"})

    app = web.Application()
    app.router.add_get("/api/1.0/lookup/1/15/0/0/0/0", datenpunkt)
    server = await aiohttp_server(app)
    server.versuche = versuche
    return server


async def test_die_anlage_laesst_sich_anmelden(anlage):
    """Der ganze Weg: Aufforderung, Rückgabe, Nutzdaten."""
    from custom_components.heatnexus.client import WindhagerHttpClient

    client = WindhagerHttpClient(f"{anlage.host}:{anlage.port}", PASSWORT, username=BENUTZER)
    try:
        daten, status = await client._get(
            f"http://{anlage.host}:{anlage.port}/api/1.0/lookup/1/15/0/0/0/0"
        )
    finally:
        await client.close()

    assert status == 200
    assert daten["value"] == "12.5"
    # Erst ohne Anmeldung, dann mit: Genau so verhält sich auch die Steuerung.
    assert anlage.versuche[0] == ""
    assert anlage.versuche[-1].startswith("Digest ")


async def test_falsches_passwort_kommt_nicht_durch(anlage):
    """Die Gegenprobe.

    Ohne sie wäre der Test oben wertlos: Er bliebe auch dann grün, wenn der
    Server die Anmeldung gar nicht prüfte.
    """
    from custom_components.heatnexus.client import WindhagerHttpClient

    client = WindhagerHttpClient(f"{anlage.host}:{anlage.port}", "falsch", username=BENUTZER)
    try:
        _, status = await client._get(
            f"http://{anlage.host}:{anlage.port}/api/1.0/lookup/1/15/0/0/0/0"
        )
    finally:
        await client.close()

    assert status == 401
