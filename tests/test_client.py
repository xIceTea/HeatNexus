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
    """Der Funktionsname „Hebebühne" kommt mit 0x81 – nur CP850 kennt das."""
    roh = b'{"name": "Hebeb\x81hne"}'
    assert "Hebebühne" in client_module.WindhagerHttpClient._decode(roh)


def test_umlaut_aus_cp1252(client_module):
    roh = b'{"name": "Hebeb\xfchne"}'
    assert "Hebebühne" in client_module.WindhagerHttpClient._decode(roh)


def test_utf8_bleibt_unangetastet(client_module):
    roh = '{"name": "Wärmeanforderung"}'.encode()
    assert "Wärmeanforderung" in client_module.WindhagerHttpClient._decode(roh)


def test_kennung_haengt_an_der_seriennummer(client_module):
    """Die Kennung darf die Adresse nicht enthalten – sonst bricht ein Umzug."""
    client = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    client.neuron_by_node = {"60": "070269ad1601", "15": "070261a50401"}

    assert client._kennung("/1/60/0/0/7/0") == "070269ad1601-0-0-7-0"
    assert client._geraetekennung("/1/15/0") == "070261a50401-0"
    # Steuerung: die kleinste Seriennummer ihrer Knoten.
    assert client.steuerung_kennung() == "steuerung-070261a50401"


def test_kennung_faellt_ohne_seriennummer_auf_die_adresse_zurueck(client_module):
    client = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    assert client._kennung("/1/60/0/0/7/0") == "192-0-2-10-0-0-7-0"
    assert client.steuerung_kennung() is None


def test_alte_kennung_bleibt_reproduzierbar(client_module):
    """Für die Umstellung muss die frühere Kennung exakt nachbildbar sein."""
    client = client_module.WindhagerHttpClient("192.168.178.100", "geheim")
    assert client._alte_kennung("/1/60/0/0/7/0") == "192-168-178-100-1-60-0-0-7-0"


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
