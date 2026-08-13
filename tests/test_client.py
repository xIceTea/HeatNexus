"""Client: Plattform-Auflösung aus Geräte-Metadaten und Discovery-Cache.

Benötigt eine installierte HA-Umgebung, weil ``custom_components.heatnexus``
beim Import Home Assistant lädt.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def client_module():
    from custom_components.heatnexus import client

    return client


def _resolve(client_module, meta, descriptor=None):
    return client_module.WindhagerHttpClient._resolve_auto_type(descriptor or {}, meta)


def test_writable_enum_becomes_select(client_module):
    meta = {"writeProt": False, "enum": "[0,1,2]", "value": "1"}
    assert _resolve(client_module, meta) == "select"


def test_readonly_enum_becomes_enum_sensor(client_module):
    meta = {"writeProt": True, "enum": "[0,1,2]", "value": "1"}
    assert _resolve(client_module, meta) == "enum_sensor"


def test_writable_range_becomes_number(client_module):
    meta = {"writeProt": False, "minValue": "10", "maxValue": "30", "step": "0.5", "value": "21"}
    assert _resolve(client_module, meta) == "number"


def test_celsius_value_becomes_temperature(client_module):
    meta = {"writeProt": True, "unit": "°C", "value": "45.7"}
    assert _resolve(client_module, meta) == "temperature"


def test_writable_time_becomes_time(client_module):
    meta = {"writeProt": False, "value": "06:30"}
    assert _resolve(client_module, meta) == "time"


def test_writable_date_becomes_date(client_module):
    meta = {"writeProt": False, "value": "24.12.2026"}
    assert _resolve(client_module, meta) == "date"


def test_time_program_without_value(client_module):
    meta = {"writeProt": False, "typeId": 30}
    assert _resolve(client_module, meta) == "time_program"


def test_umlaut_aus_der_dos_codepage(client_module):
    """Ein von Hand vergebener Name bringt „ü" als 0x81 – nur CP850 kennt das."""
    roh = b'{"name": "S\x81dbau"}'
    assert "Südbau" in client_module.WindhagerHttpClient._decode(roh)


def test_umlaut_aus_cp1252(client_module):
    roh = b'{"name": "S\xfcdbau"}'
    assert "Südbau" in client_module.WindhagerHttpClient._decode(roh)


def test_utf8_bleibt_unangetastet(client_module):
    roh = '{"name": "Wärmeanforderung"}'.encode()
    assert "Wärmeanforderung" in client_module.WindhagerHttpClient._decode(roh)


def test_kennung_haengt_an_der_seriennummer(client_module):
    """Die Kennung darf die Adresse nicht enthalten – sonst bricht ein Umzug."""
    client = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    client.neuron_by_node = {"60": "0702bb000002", "15": "0702aa000001"}

    assert client._kennung("/1/60/0/0/7/0") == "0702bb000002-0-0-7-0"
    assert client._geraetekennung("/1/15/0") == "0702aa000001-0"
    # Steuerung: die kleinste Seriennummer ihrer Knoten.
    assert client.steuerung_kennung() == "steuerung-0702aa000001"


def test_kennung_faellt_ohne_seriennummer_auf_die_adresse_zurueck(client_module):
    client = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    assert client._kennung("/1/60/0/0/7/0") == "192-0-2-10-0-0-7-0"
    assert client.steuerung_kennung() is None


def test_alte_kennung_bleibt_reproduzierbar(client_module):
    """Für die Umstellung muss die frühere Kennung exakt nachbildbar sein."""
    client = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    assert client._alte_kennung("/1/60/0/0/7/0") == "192-0-2-10-1-60-0-0-7-0"


def test_discovery_roundtrip_is_json_safe(client_module):
    """export_discovery muss per HA-Store persistierbar sein (keine Sets)."""
    import json

    client = client_module.WindhagerHttpClient("192.0.2.1", "secret")
    client.oids = {"/1/15/0/0/0/0"}
    client.devices = [{"id": "x", "oid": "/1/15/0/0/0/0", "type": "temperature"}]
    client.poll_oids = {"/1/15/0/0/0/0"}

    exported = client.export_discovery()
    json.dumps(exported)  # darf nicht werfen

    restored = client_module.WindhagerHttpClient("192.0.2.1", "secret")
    restored.restore_discovery(exported)
    assert restored.oids == client.oids
    assert restored.poll_oids == client.poll_oids
    assert restored.devices == client.devices


# ----------------------------------------------------------------- Sammelabruf
def _mit_positionen(client_module, positionen):
    """Client mit vorgegebenen Menü-Positionen."""
    client = client_module.WindhagerHttpClient("192.0.2.1", "secret")
    client.menu_pos = dict(positionen)
    return client


def test_sammel_plan_buendelt_benachbarte_positionen(client_module):
    """Vier Datenpunkte einer Ebene werden ein Fenster, keine vier Abrufe."""
    client = _mit_positionen(
        client_module,
        {
            "/1/60/0/0/7/0": ("/1/60/0", "98", 2),
            "/1/60/0/0/8/0": ("/1/60/0", "98", 3),
            "/1/60/0/0/9/0": ("/1/60/0", "98", 4),
            "/1/60/0/1/0/0": ("/1/60/0", "98", 5),
        },
    )

    fenster, einzeln = client.sammel_plan(set(client.menu_pos))

    assert einzeln == set()
    assert len(fenster) == 1
    prefix, menu_id, offset, count, erwartet = fenster[0]
    assert (prefix, menu_id, offset, count) == ("/1/60/0", "98", 2, 4)
    assert erwartet == set(client.menu_pos)


def test_sammel_plan_trennt_bei_zu_grosser_luecke(client_module):
    """Ein Fenster über eine weite Lücke würde nur fremde Datenpunkte laden."""
    client = _mit_positionen(
        client_module,
        {
            "/1/60/0/0/1/0": ("/1/60/0", "100", 0),
            "/1/60/0/0/2/0": ("/1/60/0", "100", 1),
            "/1/60/0/9/8/0": ("/1/60/0", "100", 40),
            "/1/60/0/9/9/0": ("/1/60/0", "100", 41),
        },
    )

    fenster, einzeln = client.sammel_plan(set(client.menu_pos))

    assert einzeln == set()
    assert sorted((f[2], f[3]) for f in fenster) == [(0, 2), (40, 2)]


def test_sammel_plan_laesst_einzelgaenger_einzeln(client_module):
    """Ein einzelner Datenpunkt in einer Ebene lohnt kein Fenster."""
    client = _mit_positionen(
        client_module,
        {
            "/1/15/0/0/0/0": ("/1/15/0", "96", 0),
            "/1/16/1/0/1/0": ("/1/16/1", "98", 3),
            "/1/16/1/0/2/0": ("/1/16/1", "98", 4),
        },
    )

    fenster, einzeln = client.sammel_plan(set(client.menu_pos))

    assert einzeln == {"/1/15/0/0/0/0"}
    assert len(fenster) == 1
    assert fenster[0][4] == {"/1/16/1/0/1/0", "/1/16/1/0/2/0"}


def test_sammel_plan_ohne_positionen_faellt_auf_einzelabrufe_zurueck(client_module):
    """Ein Cache aus einer älteren Fassung kennt keine Positionen."""
    client = _mit_positionen(client_module, {})

    fenster, einzeln = client.sammel_plan({"/1/60/0/0/7/0", "/1/15/0/0/0/0"})

    assert fenster == []
    assert einzeln == {"/1/60/0/0/7/0", "/1/15/0/0/0/0"}


def test_sammel_plan_ueberschreitet_die_fenstergrenze_nicht(client_module):
    """Die Steuerung beantwortet nur begrenzt große Fenster."""
    from custom_components.heatnexus.const import SAMMEL_MAX

    positionen = {f"/1/60/0/0/{i}/0": ("/1/60/0", "100", i) for i in range(SAMMEL_MAX + 10)}
    client = _mit_positionen(client_module, positionen)

    fenster, einzeln = client.sammel_plan(set(positionen))

    assert einzeln == set()
    assert all(f[3] <= SAMMEL_MAX for f in fenster)
    # Alle Datenpunkte bleiben abgedeckt – Bündeln darf nichts verlieren.
    abgedeckt = set()
    for f in fenster:
        abgedeckt |= f[4]
    assert abgedeckt == set(positionen)


def test_positionen_ueberleben_den_cache(client_module):
    """Ohne persistierte Positionen wäre nach jedem Neustart Einzelabruf."""
    import json

    client = client_module.WindhagerHttpClient("192.0.2.1", "secret")
    client.oids = {"/1/15/0/0/0/0"}
    client.devices = []
    client.poll_oids = {"/1/15/0/0/0/0"}
    client.menu_pos = {"/1/15/0/0/0/0": ("/1/15/0", "96", 3)}

    exported = client.export_discovery()
    json.dumps(exported)

    restored = client_module.WindhagerHttpClient("192.0.2.1", "secret")
    restored.restore_discovery(exported)
    assert restored.menu_pos == {"/1/15/0/0/0/0": ("/1/15/0", "96", 3)}


def test_leermarken_der_anlage_werden_none(client_module):
    """`-.-` heißt „kein Messwert", nicht 0."""
    umwandeln = client_module.WindhagerHttpClient._wert_oder_none
    assert umwandeln("-.-") is None
    assert umwandeln("") is None
    assert umwandeln("0") == "0"
    assert umwandeln("21.5") == "21.5"
