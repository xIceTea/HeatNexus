"""Der Weg zur Anlage: lesen, schreiben, und was bei Fehlern passiert.

Geprüft wird gegen eine Sitzungsattrappe, nicht gegen ein Gerät. Was hier
zählt, ist das Verhalten an den Rändern: Ein Zeichensatz, den die Steuerung
benutzt und Python nicht erwartet; eine Antwort ohne JSON; ein abgelehnter
Schreibvorgang; ein einzelner `401`, der noch kein falsches Passwort ist.

Für jeden dieser Fälle gab es einmal einen Fehlerbericht.
"""

from __future__ import annotations

import json

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def client_module():
    from custom_components.heatnexus import client

    return client


class _Antwort:
    """Was `aiohttp` zurückgibt, so weit der Client es anfasst."""

    def __init__(self, status: int = 200, rohdaten: bytes = b"{}"):
        self.status = status
        self._rohdaten = rohdaten
        self.request_info = None
        self.history = ()

    async def read(self) -> bytes:
        return self._rohdaten

    async def text(self) -> str:
        return self._rohdaten.decode("latin-1")

    async def json(self):
        return json.loads(self._rohdaten.decode("utf-8"))


class _Sitzung:
    """Merkt sich jede Anfrage und gibt der Reihe nach vorbereitete Antworten."""

    def __init__(self, *antworten: _Antwort):
        self._antworten = list(antworten) or [_Antwort()]
        self.anfragen: list[tuple] = []

    async def request(self, methode, url, data=None):
        self.anfragen.append((methode, str(url), data))
        return self._antworten.pop(0) if len(self._antworten) > 1 else self._antworten[0]

    async def close(self):
        return None


@pytest.fixture
def client(client_module):
    def bauen(*antworten: _Antwort):
        c = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
        c._session = _Sitzung(*antworten)
        return c

    return bauen


# ---------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------
async def test_ein_wert_wird_gelesen_und_gezaehlt(client):
    c = client(_Antwort(200, b'{"value": "63.5"}'))
    assert await c._fetch_oid("/1/60/0/0/7/0") == ("/1/60/0/0/7/0", "63.5")
    assert c.request_count == 1
    assert c.request_errors == 0


async def test_die_leermarke_der_anlage_wird_kein_nullwert(client):
    """`-.-` heißt „kein Fühler angeschlossen". Eine 0 daraus wäre gelogen."""
    c = client(_Antwort(200, b'{"value": "-.-"}'))
    assert await c._fetch_oid("/1/60/0/0/7/0") == ("/1/60/0/0/7/0", None)


async def test_ein_umlaut_aus_der_dos_codepage_kommt_lesbar_an(client):
    """`ü` liegt dort auf 0x81 – ein Byte, das CP1252 nicht einmal kennt."""
    c = client(_Antwort(200, '{"name": "Südbau"}'.encode("cp850")))
    daten, status = await c._get("http://egal/")
    assert status == 200
    assert daten["name"] == "Südbau"


async def test_eine_antwort_ohne_json_bricht_nichts_ab(client):
    """Die Steuerung antwortet auf manche Adressen mit reinem Text."""
    c = client(_Antwort(503, b"endpoint <log> does not exist."))
    assert await c._get("http://egal/") == (None, 503)


async def test_ein_fehlender_datenpunkt_liefert_keinen_wert(client):
    c = client(_Antwort(404, b"not found"))
    assert await c._fetch_oid("/1/60/0/9/99/0") == ("/1/60/0/9/99/0", None)


async def test_die_steuerung_nennt_sich_selbst(client):
    """Eine Anfrage liefert Modell und Firmwarestand der Steuerung."""
    c = client(_Antwort(200, b'{"device": "MB6621", "version": "0.10.1", "serialnumber": "123"}'))
    await c._lese_geraeteinfo()
    assert c.geraeteinfo["device"] == "MB6621"
    assert c._session.anfragen[0][1].endswith("/api/1.0/info/deviceinfo")


async def test_ohne_auskunft_bleibt_die_geraeteinfo_leer(client):
    """Ältere Steuerungen kennen den Endpunkt nicht – das ist kein Fehler."""
    c = client(_Antwort(404, b"not found"))
    await c._lese_geraeteinfo()
    assert c.geraeteinfo == {}


async def test_die_knotenliste_nennt_die_werksbezeichnung(client):
    """`lookup /1` gibt unter `device` nur eine Zahl, `nodes` den Namen."""
    c = client(
        _Antwort(
            200,
            b'[{"nodeId": 15, "name": "eigener Name", '
            b'"device": {"id": 38, "name": "UMUMLZ", "DeviceClass": "29.01"}}]',
        )
    )
    await c._lese_knotendaten()
    assert c.werksbezeichnung == {"15": "UMUMLZ"}
    assert c._session.anfragen[0][1].endswith("/api/1.0/nodes")


async def test_ohne_knotenliste_bleibt_die_werksbezeichnung_leer(client):
    c = client(_Antwort(404, b"not found"))
    await c._lese_knotendaten()
    assert c.werksbezeichnung == {}


async def test_die_verbindungspruefung_gibt_den_status_mit(client):
    """Der Status geht mit, nicht nur das Ergebnis.

    Der Einrichtungsdialog muss „nicht erreichbar" von „Passwort falsch"
    unterscheiden können; dazu braucht er die Zahl.
    """
    c = client(_Antwort(200, b"[1]"))
    daten, status = await c.probe()
    assert (daten, status) == ([1], 200)
    assert c._session.anfragen[0][1].endswith("/api/1.0/lookup/1")


# ---------------------------------------------------------------------------
# Abgewiesene Anfragen
# ---------------------------------------------------------------------------
async def test_ein_einzelner_401_ist_noch_kein_falsches_passwort(client):
    """Er kann auch ein verbrauchter Digest-Nonce sein. Erst mehrere zählen."""
    c = client(_Antwort(401, b""), _Antwort(200, b"{}"))
    await c._get("http://egal/")
    assert c.auth_errors == 1
    await c._get("http://egal/")
    assert c.auth_errors == 0


async def test_ein_abbruch_wird_als_fehler_gezaehlt(client, client_module):
    c = client()

    async def scheitern(*_args, **_kwargs):
        raise OSError("Netz weg")

    c._session.request = scheitern
    with pytest.raises(OSError):
        await c._get("http://egal/")
    assert c.request_errors == 1
    # Gezählt wird sie trotzdem: Sonst sähe die Statistik besser aus als die Lage.
    assert c.request_count == 1


# ---------------------------------------------------------------------------
# Schreiben
# ---------------------------------------------------------------------------
async def test_ein_wert_wird_geschrieben(client):
    c = client(_Antwort(200, b""))
    await c.update("/1/15/0/3/4/0", "21.5")
    methode, url, rumpf = c._session.anfragen[0]
    assert methode == "PUT"
    assert url.endswith("/api/1.0/datapoint")
    assert json.loads(rumpf) == {"OID": "/1/15/0/3/4/0", "value": "21.5"}


async def test_ein_abgelehnter_schreibvorgang_bleibt_nicht_still(client):
    """Sonst meldete die Oberfläche „übernommen", und nichts wäre übernommen."""
    import aiohttp

    c = client(_Antwort(409, b"invalid Identifier"))
    with pytest.raises(aiohttp.ClientResponseError):
        await c.update("/1/15/0/3/51/0", "21.5")


# ---------------------------------------------------------------------------
# object-Endpunkt (Zeitprogramme)
# ---------------------------------------------------------------------------
def test_die_adresse_des_objekt_endpunkts_bleibt_unkodiert(client):
    """Die Schrägstriche gehören in den Suchteil, nicht als %2F.

    Der lokale Endpunkt liest `OID` groß geschrieben als vollständigen Pfad;
    die Form des Portals (`?node_id=&function_id=&oid=`) beantwortet er nicht.
    """
    c = client()
    assert str(c._object_url("/1/15/0/5/64/0")) == (
        "http://192.0.2.10/api/1.0/object?OID=/1/15/0/5/64/0"
    )


async def test_ein_zeitprogramm_wird_gelesen(client):
    rohdaten = b'{"value": [{"weekdays": ["Mo"], "switchPoints": [{"time": "06:00"}]}]}'
    c = client(_Antwort(200, rohdaten))
    daten, status = await c.fetch_object("/1/15/0/5/64/0")
    assert status == 200
    assert daten["value"][0]["weekdays"] == ["Mo"]


async def test_ein_unlesbares_objekt_meldet_status_null(client):
    """`0` heißt: gar keine Antwort. Das ist etwas anderes als ein Fehlercode."""
    c = client()

    async def scheitern(*_args, **_kwargs):
        raise OSError("Netz weg")

    c._session.request = scheitern
    assert await c.fetch_object("/1/15/0/5/64/0") == (None, 0)


async def test_ein_zeitprogramm_wird_geschrieben(client):
    c = client(_Antwort(200, b""))
    await c.write_object("/1/15/0/5/64/0", {"value": [{"weekdays": ["Mo"]}]})
    methode, url, rumpf = c._session.anfragen[0]
    assert methode == "PUT"
    assert "OID=/1/15/0/5/64/0" in url
    assert json.loads(rumpf)["value"][0]["weekdays"] == ["Mo"]


async def test_ein_abgelehntes_zeitprogramm_bleibt_nicht_still(client):
    import aiohttp

    c = client(_Antwort(400, b"bad request"))
    with pytest.raises(aiohttp.ClientResponseError):
        await c.write_object("/1/15/0/5/64/0", {"value": []})


# ---------------------------------------------------------------------------
# Sammelabruf
# ---------------------------------------------------------------------------
async def test_ein_fenster_liefert_nur_die_gebrauchten_werte(client):
    """Mitgelesen ist nicht angefordert.

    Ein Fenster schleppt ungenutzte Positionen mit. Sie gehören nicht ins
    Ergebnis, sonst stünden Werte in der Anzeige, die niemand wollte.
    """
    rohdaten = json.dumps(
        [
            {"OID": "/1/60/0/0/7/0", "value": "63.5"},
            {"OID": "/1/60/0/0/8/0", "value": "12"},
            {"OID": "/1/60/0/0/9/0", "value": "-.-"},
        ]
    ).encode("utf-8")
    c = client(_Antwort(200, rohdaten))
    werte = await c._fetch_fenster("/1/60/0", "0", 7, 3, {"/1/60/0/0/7/0", "/1/60/0/0/9/0"})
    assert werte == {"/1/60/0/0/7/0": "63.5", "/1/60/0/0/9/0": None}


async def test_ein_gescheitertes_fenster_bricht_den_durchlauf_nicht_ab(client):
    """Sonst risse ein einzelner Aussetzer den ganzen Abruf mit."""
    c = client(_Antwort(500, b"kaputt"))
    assert await c._fetch_fenster("/1/60/0", "0", 0, 10, {"/1/60/0/0/7/0"}) == {}
