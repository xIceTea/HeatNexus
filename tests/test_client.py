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


def test_schaltzustand_wird_ja_nein_sensor(client_module):
    """Bereich 0…1 ohne Einheit: ein Ausgang, der nur schaltet."""
    meta = {"writeProt": True, "typeId": 1, "minValue": "0", "maxValue": "1", "value": "0"}
    assert _resolve(client_module, meta) == "binary_sensor"


def test_drehzahl_bleibt_messwert(client_module):
    """Dieselbe typeId, aber Bereich 0…100 mit Einheit."""
    meta = {
        "writeProt": True,
        "typeId": 1,
        "minValue": "0",
        "maxValue": "100",
        "unit": "%",
        "value": "0",
    }
    assert _resolve(client_module, meta) == "sensor"


def test_schreibbarer_schalter_bleibt_zahl(client_module):
    """Ein schreibbarer Bereich wird zur Zahl - der Typwechsel bräche Bestehendes."""
    meta = {"writeProt": False, "typeId": 1, "minValue": "0", "maxValue": "1", "value": "0"}
    assert _resolve(client_module, meta) == "number"


def test_mehrfach_gefuehrte_adresse_bekommt_die_zugaenglichste_ebene():
    """`9/57` steht am PuroWIN in Service- und Werksebene – Service gewinnt."""
    from custom_components.heatnexus.device_db import get_layers

    for fct_type, adresse in ((25, "9/57"), (9, "9/57")):
        layers = get_layers(fct_type) or {}
        ebenen = [e for e in ("info", "operate", "service", "oem") if adresse in layers.get(e, [])]
        assert "oem" in ebenen and len(ebenen) > 1, f"fctType {fct_type}: Vorbedingung"

        level_of: dict[str, str] = {}
        for level in ("info", "operate", "service", "oem"):
            for gnmn in layers.get(level, []):
                level_of.setdefault(gnmn, level)

        assert level_of[adresse] != "oem"


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


def test_leermarken_der_anlage_werden_none(client_module):
    """`-.-` heißt „kein Messwert", nicht 0."""
    umwandeln = client_module.WindhagerHttpClient._wert_oder_none
    assert umwandeln("-.-") is None
    assert umwandeln("") is None
    assert umwandeln("0") == "0"
    assert umwandeln("21.5") == "21.5"


def _mit_texten(client_module, sprache, namen):
    """Ein Client, dessen Anlage die genannten Bezeichnungen geliefert hat."""
    from custom_components.heatnexus import geraetetexte

    client = client_module.WindhagerHttpClient("192.0.2.1", "secret", sprache=sprache)
    client._texte = geraetetexte.Texte(namen=namen)
    return client


def test_auf_deutsch_fuehrt_die_gepflegte_bezeichnung(client_module):
    client = _mit_texten(client_module, "de", {"0/7": "Kesseltemperatur Istwert"})
    assert client._name_fuer("0/7", "Kesseltemperatur") == "Kesseltemperatur"


def test_auf_deutsch_fuellt_die_anlage_nur_luecken(client_module):
    client = _mit_texten(client_module, "de", {"0/7": "Kesseltemperatur Istwert"})
    assert client._name_fuer("0/7", None) == "Kesseltemperatur Istwert"


def test_bei_fremder_sprache_fuehrt_die_anlage(client_module):
    client = _mit_texten(client_module, "fr", {"0/7": "Temp. chaudière"})
    assert client._name_fuer("0/7", "Kesseltemperatur") == "Temp. chaudière"


def test_ohne_geraetetext_bleibt_die_gepflegte_bezeichnung(client_module):
    """Eine Anlage, die ihre Textdateien nicht ausliefert, verliert nichts."""
    client = _mit_texten(client_module, "fr", {})
    assert client._name_fuer("0/7", "Kesseltemperatur") == "Kesseltemperatur"
