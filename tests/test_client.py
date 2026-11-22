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


def test_zeitprogramm_trotz_mitgeschicktem_wert(client_module):
    """Manche Baureihen melden zum Zeitprogramm ein leeres `value` mit.

    Ohne den Subtyp fiele der Datenpunkt bis zur letzten Regel durch und
    entstünde als Textsensor, der nichts anzeigen kann.
    """
    meta = {"writeProt": False, "typeId": 30, "subtypeId": 14, "value": ""}
    assert _resolve(client_module, meta) == "time_program"


def test_text_bleibt_text_auch_mit_wert(client_module):
    """Gegenprobe: Subtyp 9 ist ein Text, ob mit Wert oder ohne."""
    meta = {"writeProt": True, "typeId": 30, "subtypeId": 9, "value": "PW 400"}
    assert _resolve(client_module, meta) == "string_sensor"


def test_programm_laut_herstellerliste_trotz_unbekanntem_subtyp(client_module):
    """Der Hersteller führt `3/61` am Infinity-Heizkreis als Objekt."""
    meta = {"writeProt": False, "typeId": 30, "subtypeId": 17, "value": ""}
    beschreibung = {"oid": "/1/15/0/3/61/0", "fct_type": 1, "name": "Programm 1"}
    assert _resolve(client_module, meta, beschreibung) == "time_program"


def test_ohne_herstellereintrag_bleibt_der_unbekannte_subtyp_text(client_module):
    """Gegenprobe: Dieselbe Antwort an einer Adresse, die kein Objekt ist."""
    meta = {"writeProt": False, "typeId": 30, "subtypeId": 17, "value": ""}
    beschreibung = {"oid": "/1/15/0/0/1/0", "fct_type": 1, "name": "Raumtemperatur"}
    assert _resolve(client_module, meta, beschreibung) == "string_sensor"


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


def _puffer_client(client_module, modulfunktion):
    """Ein Puffermodul mit den drei Adressen, die an der Rolle hängen.

    Bewusst ohne `prefix`: Den führt der Deskriptor nicht, und ein Test, der
    ihn setzt, prüft eine Form, die es im Betrieb nicht gibt.
    """
    client = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    adressen = ["1/22", "21/65", "21/66", "22/75"]
    client.devices = [
        client_module.WindhagerHttpClient._deskriptor(
            oid=f"/1/16/1/{a}/0", fct_type=16, name=a, type="sensor"
        )
        for a in adressen
    ]
    client.oids = {d["oid"] for d in client.devices}
    meta = {"/1/16/1/20/4/0": {"value": str(modulfunktion)}}
    return client, meta


def test_transferpumpe_faellt_bei_pufferladung_weg(client_module):
    """Modulfunktion 3 lädt den Puffer über TPE/TPA – ohne Transferpumpe."""
    client, meta = _puffer_client(client_module, 3)
    client._rollen_filter(meta)

    namen = {d["name"] for d in client.devices}
    assert namen == {"1/22", "21/65", "21/66"}
    assert "/1/16/1/22/75/0" not in client.oids


def test_zweiter_fuehler_faellt_bei_nur_tpe_weg(client_module):
    """Modulfunktion 2 kennt nur TPE, TPA ist dort nicht verdrahtet."""
    client, meta = _puffer_client(client_module, 2)
    client._rollen_filter(meta)

    assert {d["name"] for d in client.devices} == {"1/22", "21/65"}


def test_transferpumpe_bleibt_bei_modulfunktion_null(client_module):
    """Bei 0 fördert die Transferpumpe, dafür entfällt die Pumpe zum Erzeuger."""
    client, meta = _puffer_client(client_module, 0)
    client._rollen_filter(meta)

    assert {d["name"] for d in client.devices} == {"21/65", "22/75"}


def test_pumpenmodul_ohne_pumpensteuerung_verliert_seine_drehzahl(client_module):
    """Die Herstellerdatei knüpft `0/22` an `29/1` – steht der auf Nein, entfällt sie."""
    client = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    adressen = ["0/22", "0/7", "0/95", "9/57"]
    client.devices = [
        client_module.WindhagerHttpClient._deskriptor(
            oid=f"/1/14/0/{a}/0", fct_type=20, name=a, type="sensor"
        )
        for a in adressen
    ]
    client.oids = {d["oid"] for d in client.devices}
    client._rollen_filter(
        {
            "/1/14/0/29/1/0": {"value": "0"},  # keine Pumpensteuerung
            "/1/14/0/29/2/0": {"value": "1"},  # aber externe Wärmeanforderung
        }
    )

    # 0/22 und 0/7 hängen an 29/1, 0/95 an 29/2. 9/57 trägt am ZSP keine Bedingung.
    assert {d["name"] for d in client.devices} == {"0/95", "9/57"}


def test_bedingung_ohne_lesbaren_schaltwert_nimmt_nichts_weg(client_module):
    """Ohne den Schaltwert bleibt alles stehen – Unwissen darf nichts löschen."""
    client = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    client.devices = [
        client_module.WindhagerHttpClient._deskriptor(
            oid="/1/14/0/0/22/0", fct_type=20, name="0/22", type="sensor"
        )
    ]
    client.oids = {"/1/14/0/0/22/0"}
    client._rollen_filter({})

    assert len(client.devices) == 1


def test_unbekannte_rolle_nimmt_nichts_weg(client_module):
    """Ohne lesbaren Parameter bleibt jeder Datenpunkt stehen."""
    client, _ = _puffer_client(client_module, 3)
    client._rollen_filter({})

    assert len(client.devices) == 4


def _puffer_mit_sollwert(client_module):
    """Ein Puffermodul mit Sollwert und Hysterese, wie es die Anlage meldet."""
    client = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    client.devices = [
        client_module.WindhagerHttpClient._deskriptor(
            id=f"SN-1-{a.replace('/', '-')}-0",
            oid=f"/1/16/1/{a}/0",
            fct_type=16,
            name=n,
            type="temperature",
        )
        for a, n in (
            ("1/15", "Puffertemperatur Sollwert"),
            ("9/35", "Hysterese"),
            ("9/57", "Solltemperatur ext. Wärmeanforderung"),
            ("21/65", "Puffer oben Temperatur (TPE)"),
        )
    ]
    client.oids = {d["oid"] for d in client.devices}
    return client


def test_schaltpunkte_entstehen_aus_sollwert_und_hysterese(client_module):
    """Zwei Schaltpunkte je Puffer: wann geladen wird und was geliefert wird."""
    client = _puffer_mit_sollwert(client_module)
    client._schaltpunkte({})

    punkte = {d["name"]: d for d in client.devices if d["type"] == "schaltpunkt"}
    assert set(punkte) == {"Einschaltpunkt", "Anforderungstemperatur"}
    # Der Schaltpunkt hängt am Sollwert, die Hysterese kommt als Auslöser dazu.
    assert punkte["Einschaltpunkt"]["oid"] == "/1/16/1/1/15/0"
    assert punkte["Einschaltpunkt"]["ausloeser_oid"] == "/1/16/1/9/35/0"
    assert punkte["Einschaltpunkt"]["anteil"] == -0.5
    assert punkte["Anforderungstemperatur"]["anteil"] == 1.0
    assert all(not d["enabled_default"] for d in punkte.values())


def test_hysterese_wird_beim_einlesen_mitgenommen(client_module):
    """Sie liegt auf der Serviceebene; ohne Vorgabe bliebe der Wert stundenlang leer."""
    client = _puffer_mit_sollwert(client_module)
    client._schaltpunkte({"/1/16/1/9/35/0": {"value": "16.0"}})

    punkte = {d["name"]: d for d in client.devices if d["type"] == "schaltpunkt"}
    assert punkte["Einschaltpunkt"]["hysterese_vorgabe"] == 16.0


def test_ohne_hysterese_kein_schaltpunkt(client_module):
    """Fehlt einer der beiden Werte, entsteht kein Schaltpunkt."""
    client = _puffer_mit_sollwert(client_module)
    client.devices = [d for d in client.devices if not d["oid"].endswith("/9/35/0")]
    client._schaltpunkte({})

    assert not [d for d in client.devices if d["type"] == "schaltpunkt"]


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


def test_ohne_geraetetext_springt_die_englische_herstellertabelle_ein(client_module):
    """Eine Steuerung ohne Textdateien bekommt englische Namen aus der Datenbank."""
    client = _mit_texten(client_module, "en", {})
    assert client._name_fuer("0/0", "Außentemperatur") == "Outside temperature"


def test_eine_luecke_der_herstellertabelle_fuellt_die_englische(client_module, monkeypatch):
    """Fehlt ein niederländischer Name, erscheint der englische statt des deutschen."""
    from custom_components.heatnexus.client import erkennung

    echt = erkennung.get_name
    monkeypatch.setattr(erkennung, "get_name", lambda g, s="de": None if s == "nl" else echt(g, s))
    client = _mit_texten(client_module, "nl", {})
    assert client._name_fuer("0/104", "Abgasdruck") == "Exhaust pressure"


def test_der_geraetetext_geht_der_englischen_tabelle_vor(client_module):
    client = _mit_texten(client_module, "en", {"0/0": "Outdoor temp."})
    assert client._name_fuer("0/0", "Außentemperatur") == "Outdoor temp."


def test_englische_auswahltexte_ohne_textdatei_der_steuerung(client_module):
    client = _mit_texten(client_module, "en", {})
    assert client._enum_texte_fuer("9/75")[1] == "On"
    assert _mit_texten(client_module, "de", {})._enum_texte_fuer("9/75") is None


async def test_meldungssensoren_tragen_die_sprache(client_module, monkeypatch):
    """Ohne Textdatei der Steuerung wählt die Sprache die Tabelle der Störungstexte."""
    client = _mit_texten(client_module, "en", {})
    client.geraeteinfo = {"device": "MB66xx", "version": "1.0"}
    client.werksbezeichnung = {"60": "PuroWIN"}

    async def fetch(url, semaphore=None):
        return [
            {
                "nodeId": 60,
                "neuronId": "0000PUROWIN1",
                "FE01msg": "PUR 09  OK",
                "functions": [{"fctId": 0, "fctType": 25, "lock": False, "name": "PuroWIN"}],
            }
        ]

    monkeypatch.setattr(client, "fetch", fetch)
    await client._discover(nur_kern=True)

    meldungen = [d for d in client.devices if d["type"] == "message_text"]
    assert meldungen
    assert all(d["sprache"] == "en" for d in meldungen)


async def test_meldungssensoren_entstehen_auch_ohne_fe01msg_im_abzug(client_module, monkeypatch):
    """Fehlt `FE01msg` beim Einlesen, meldet der Kessel trotzdem Störungen."""
    client = _mit_texten(client_module, "de", {})
    client.geraeteinfo = {"device": "MB66xx", "version": "1.0"}
    client.werksbezeichnung = {"60": "PuroWIN"}

    async def fetch(url, semaphore=None):
        return [
            {
                "nodeId": 60,
                "neuronId": "0000PUROWIN1",
                "functions": [{"fctId": 0, "fctType": 25, "lock": False, "name": "PuroWIN"}],
            },
            {"nodeId": 90, "neuronId": "0000BEDIEN01", "functions": []},
        ]

    monkeypatch.setattr(client, "fetch", fetch)
    await client._discover(nur_kern=True)

    typen = {d["type"] for d in client.devices if d["id"].startswith("0000PUROWIN1-fe01")}
    assert typen == {"device_status", "message_text", "stoerung", "message_list"}
    assert not [d for d in client.devices if d["id"].startswith("0000BEDIEN01")]


async def _kessel_erkennen(client, monkeypatch) -> dict[str, dict]:
    """Volle Erkennung eines Kessels mit einem Datenpunkt aus dem Menü, je Adresse."""
    from custom_components.heatnexus import geraetetexte

    client.geraeteinfo = {"device": "MB66xx", "version": "1.0"}
    client.werksbezeichnung = {"60": "PuroWIN"}

    async def fetch(url, semaphore=None):
        return [
            {
                "nodeId": 60,
                "neuronId": "0000PUROWIN1",
                "functions": [{"fctId": 0, "fctType": 25, "lock": False, "name": "PuroWIN"}],
            }
        ]

    async def menues(prefix, fct_type):
        return {f"{prefix}/12/38/0": {"value": "1"}}

    async def keine_positionen():
        return set()

    async def keine_texte():
        return geraetetexte.Texte()

    monkeypatch.setattr(client, "fetch", fetch)
    monkeypatch.setattr(client, "_read_function_menus", menues)
    monkeypatch.setattr(client, "_statische_adressen", keine_positionen)
    monkeypatch.setattr(client, "_lade_geraetetexte", keine_texte)
    await client._discover()
    return {d["oid"]: d for d in client.devices if d.get("oid")}


async def test_englische_deskriptoren_tragen_den_deutschen_namen(client_module, monkeypatch):
    """Einstufung und Oberfläche erkennen Datenpunkte an deutschen Namen."""
    client = client_module.WindhagerHttpClient("192.0.2.1", "secret", sprache="en")
    je_adresse = await _kessel_erkennen(client, monkeypatch)

    kuratiert = je_adresse["/1/60/0/0/7/0"]
    assert kuratiert["name"] == "Boiler temp. current value"
    assert kuratiert["name_de"] == "Kesseltemperatur Ist"
    aus_dem_menue = je_adresse["/1/60/0/12/38/0"]
    assert aus_dem_menue["name"] == "Device type"
    assert aus_dem_menue["name_de"] == "Gerätetyp"


async def test_englische_ableitungen_heissen_englisch(client_module, monkeypatch):
    """Zusätze, Laufzeiten, Rücksetz- und Abfragetasten folgen der Sprache; der deutsche Name bleibt."""
    client = client_module.WindhagerHttpClient("192.0.2.1", "secret", sprache="en")
    await _kessel_erkennen(client, monkeypatch)
    quelle = {
        "id": "x-0-2-81-0",
        "oid": "/1/60/0/2/81/0",
        "name": "Operating hours",
        "name_de": "Betriebsstunden",
    }

    heute = client._ableitung(quelle, "heute", "zaehler_heute", "heute")
    laufzeit = client._ableitung(
        {**quelle, "name": "", "name_de": None}, "laufzeit", "laufzeit", "Laufzeit Zyklus"
    )
    punkt = client._ableitung(
        quelle, "schaltpunkt", "schaltpunkt", "", name_ersetzen="Einschaltpunkt"
    )

    assert (heute["name"], heute["name_de"]) == ("Operating hours today", "Betriebsstunden heute")
    assert (laufzeit["name"], laufzeit["name_de"]) == ("Cycle runtime", "Laufzeit Zyklus")
    assert (punkt["name"], punkt["name_de"]) == ("Switch-on point", "Einschaltpunkt")
    client._abfragetasten()
    assert {d["name"] for d in client.devices if d.get("type") == "refresh"} == {
        "Refresh values now"
    }


async def test_niederlaendische_ableitungen_heissen_niederlaendisch(client_module, monkeypatch):
    """Zusätze kommen aus der eigenen Sprache, nicht englisch an einen niederländischen Namen gehängt."""
    client = client_module.WindhagerHttpClient("192.0.2.1", "secret", sprache="nl")
    await _kessel_erkennen(client, monkeypatch)
    quelle = {
        "id": "x-0-2-81-0",
        "oid": "/1/60/0/2/81/0",
        "name": "Bedrijfsuren",
        "name_de": "Betriebsstunden",
    }

    heute = client._ableitung(quelle, "heute", "zaehler_heute", "heute")

    assert (heute["name"], heute["name_de"]) == ("Bedrijfsuren vandaag", "Betriebsstunden heute")
    client._abfragetasten()
    assert {d["name"] for d in client.devices if d.get("type") == "refresh"} == {
        "Waarden nu opvragen"
    }


def test_jeder_name_einer_ableitung_hat_eine_englische_fassung(client_module):
    """Ohne Eintrag bliebe der Name einer Ableitung auf Englisch deutsch."""
    import json
    from pathlib import Path

    from custom_components.heatnexus.client import ableitungen

    datei = (
        Path(__file__).parent.parent / "custom_components" / "heatnexus" / "sprachen" / "en.json"
    )
    englisch = json.loads(datei.read_text(encoding="utf-8"))
    namen = {"heute", "seit Start", "zurücksetzen", "Werte jetzt abfragen", "Datenpunkt {gnmn}"}
    namen |= set(ableitungen.AbleitungenMixin._LAUFZEITEN.values())
    for regel in [*ableitungen.SCHALTPUNKTE, *ableitungen.VERBRAUCHER_ABSTAND]:
        namen |= {regel[k] for k in ("name", "abstand_name", "schaltpunkt_name") if regel.get(k)}
    assert sorted(namen - set(englisch)) == []


async def test_deutsche_deskriptoren_bleiben_ohne_zweitnamen(client_module, monkeypatch):
    client = client_module.WindhagerHttpClient("192.0.2.1", "secret", sprache="de")
    je_adresse = await _kessel_erkennen(client, monkeypatch)

    assert je_adresse["/1/60/0/0/7/0"]["name"] == "Kesseltemperatur Ist"
    assert je_adresse["/1/60/0/12/38/0"]["name"] == "Gerätetyp"
    assert not any("name_de" in d for d in client.devices)


def test_die_ww_hysterese_steht_bei_den_warmwasserwerten(client_module):
    """Der Herstellername „Hysterese Ein" nennt seinen Bezug nicht."""
    client = _mit_texten(client_module, "de", {"5/0": "Hysterese Ein"})
    name = client_module.NAME_OVERRIDES["5/0"]
    assert client._name_fuer("5/0", name).startswith("WW-")


def test_die_beiden_einsteller_von_eco_comfort_stehen_beieinander(client_module):
    """„Dauer" und „Temperatur" allein nennen ihre Funktion nicht."""
    client = _mit_texten(client_module, "de", {})
    for gnmn in ("2/10", "3/4"):
        name = client_module.NAME_OVERRIDES[gnmn]
        assert client._name_fuer(gnmn, name).startswith("Eco/Comfort ")


def test_der_abstand_entsteht_an_der_gemessenen_temperatur(client_module):
    """Der Schaltpunkt hängt am Sollwert, der Abstand an TPE."""
    client = _puffer_mit_sollwert(client_module)
    client._schaltpunkte({"/1/16/1/9/35/0": {"value": "16.0"}})

    abstaende = {d["name"]: d for d in client.devices if d["type"] == "schaltpunkt_abstand"}
    assert set(abstaende) == {"Einschaltpunkt Delta"}
    abstand = abstaende["Einschaltpunkt Delta"]
    assert abstand["oid"] == "/1/16/1/21/65/0"
    assert abstand["bezugs_oid"] == "/1/16/1/1/15/0"
    assert abstand["ausloeser_oid"] == "/1/16/1/9/35/0"
    assert abstand["unit"] == "K"


def _heizkreis_mit_warmwasser(client_module):
    """Ein Heizkreis mit den vier Adressen der Warmwasserbereitung."""
    client = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    client.devices = [
        client_module.WindhagerHttpClient._deskriptor(
            id=f"SN-1-{a.replace('/', '-')}-0",
            oid=f"/1/14/0/{a}/0",
            fct_type=14,
            name=n,
            type="temperature",
        )
        for a, n in (
            ("0/4", "Warmwasser Ist-Temperatur"),
            ("1/4", "Warmwasser Soll-Temperatur"),
            ("5/0", "Hysterese Ein"),
            ("1/66", "WW-Ladepumpe"),
        )
    ]
    client.oids = {d["oid"] for d in client.devices}
    return client


def test_der_warmwasser_abstand_entsteht_am_istwert(client_module):
    """Er hängt am Istwert und zieht Soll, Hysterese und Pumpe dazu."""
    client = _heizkreis_mit_warmwasser(client_module)
    client._verbraucherabstand({"/1/14/0/5/0/0": {"value": "1.0"}})

    abstaende = [d for d in client.devices if d["type"] == "ww_abstand"]
    assert len(abstaende) == 1
    abstand = abstaende[0]
    assert abstand["oid"] == "/1/14/0/0/4/0"
    assert abstand["soll_oid"] == "/1/14/0/1/4/0"
    assert abstand["hysterese_oid"] == "/1/14/0/5/0/0"
    assert abstand["zustand_oid"] == "/1/14/0/1/66/0"
    assert abstand["hysterese_vorgabe"] == 1.0
    assert abstand["unit"] == "K"


def test_ohne_warmwasser_entsteht_kein_abstand(client_module):
    """Ein Heizkreis ohne Warmwasserfühler bekommt den Wert nicht."""
    client = _heizkreis_mit_warmwasser(client_module)
    client.devices = [d for d in client.devices if not d["oid"].endswith("/0/4/0")]
    client._verbraucherabstand({})

    assert not [d for d in client.devices if d["type"] == "ww_abstand"]


def test_schaltpunkte_sind_in_den_optionen_waehlbar(client_module):
    """Ohne Gruppe erschienen sie in keiner Auswahl und blieben für immer aus."""
    client = _puffer_mit_sollwert(client_module)
    client._schaltpunkte({})

    abgeleitet = [d for d in client.devices if d["type"] in ("schaltpunkt", "schaltpunkt_abstand")]
    assert abgeleitet
    assert all(d.get("gruppe") for d in abgeleitet)
    assert all(d["id"] in {k["id"] for k in client.zusatzkandidaten} for d in abgeleitet)


def test_ein_angekreuzter_schaltpunkt_entsteht_eingeschaltet(client_module):
    client = _puffer_mit_sollwert(client_module)
    client._schaltpunkte({})
    kennung = next(d["id"] for d in client.devices if d["type"] == "schaltpunkt_abstand")

    client.devices = [
        d for d in client.devices if d["type"] not in ("schaltpunkt", "schaltpunkt_abstand")
    ]
    client.zusatzkandidaten = []
    client.zusatzwerte = {kennung}
    client._schaltpunkte({})

    gewaehlt = next(d for d in client.devices if d["id"] == kennung)
    assert gewaehlt["enabled_default"] is True


def _kessel_mit_zaehlern(client_module):
    """Ein Kessel mit Betriebsphase, Betriebsstunden und Wartungszähler."""
    client = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    client.devices = [
        client_module.WindhagerHttpClient._deskriptor(
            id=f"SN-0-{a.replace('/', '-')}-0",
            oid=f"/1/60/0/{a}/0",
            device_id="SN-0",
            fct_type=25,
            name=n,
            type=t,
            unit=u,
            state_class=s,
            enum=e,
        )
        for a, n, t, u, s, e in (
            ("2/1", "Betriebsphase", "enum_sensor", None, None, "2/1"),
            ("2/81", "Betriebsstunden", "sensor", "h", "total_increasing", None),
            (
                "37/17",
                "Betriebsstunden bis Reinigungsausbrand",
                "sensor",
                "h",
                "total_increasing",
                None,
            ),
        )
    ]
    client.oids = {d["oid"] for d in client.devices}
    return client


def test_der_betriebsstundenzaehler_weicht_der_laufzeit(client_module):
    """Sie misst denselben Lauf minutengenau; zwei Antworten wären eine zu viel."""
    client = _kessel_mit_zaehlern(client_module)
    client._abgeleitete_zaehler()

    assert not [d for d in client.devices if d["oid"].endswith("/2/81/0") and d.get("gruppe")]


def test_ein_wartungszaehler_behaelt_seine_ableitung(client_module):
    """Er zählt bis zum Ausbrand, nicht den Lauf – die Laufzeit ersetzt ihn nicht."""
    client = _kessel_mit_zaehlern(client_module)
    client._abgeleitete_zaehler()

    abgeleitet = [d for d in client.devices if d["oid"].endswith("/37/17/0") and d.get("gruppe")]
    assert [d["type"] for d in abgeleitet] == ["zaehler_heute"]


def test_der_abstand_traegt_das_delta_symbol(client_module):
    """Er ist kein Messwert der Anlage – das Symbol trennt ihn sichtbar."""
    client = _puffer_mit_sollwert(client_module)
    client._schaltpunkte({})

    abstand = next(d for d in client.devices if d["type"] == "schaltpunkt_abstand")
    assert abstand["name"] == "Einschaltpunkt Delta"
    assert abstand["icon"] == "mdi:delta"


def test_der_ww_einschaltpunkt_entsteht_aus_soll_und_hysterese(client_module):
    """Der Abstand nennt einen Punkt – den soll man auch ablesen können."""
    client = _heizkreis_mit_warmwasser(client_module)
    client._verbraucherabstand({})

    punkt = next(d for d in client.devices if d["type"] == "schaltpunkt")
    assert punkt["name"] == "WW-Einschaltpunkt"
    assert punkt["anteil"] == -1.0
    assert punkt["oid"] == "/1/14/0/1/4/0"
    assert punkt["id"].endswith("-ww-schaltpunkt")
    assert punkt["enabled_default"] is False


def test_die_frostschutzgrenze_heisst_nicht_wie_ihr_messwert(client_module):
    """Am Heizkreis führt die Herstellertabelle beide Adressen gleich benannt."""
    assert client_module.name_override(14, "3/23") == "Frostschutzgrenze Außentemperatur"


def test_dieselbe_adresse_bleibt_an_anderer_funktion_unberuehrt(client_module):
    """Die Übersteuerung gilt nur dort, wo sie belegt ist."""
    assert client_module.name_override(25, "3/23") is None


def test_die_flache_tabelle_gilt_weiterhin(client_module):
    """Ohne Eintrag je Funktionstyp bleibt es beim gepflegten Namen."""
    assert client_module.name_override(25, "5/0") == "WW-Hysterese Ein"


def _umschaltmodul(client_module, automatikkessel, pufferspeicher):
    """Puffermodul fct 15 mit drei Entitäten auf `2/2` bzw. `2/9`."""
    client = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    client.devices = [
        client_module.WindhagerHttpClient._deskriptor(
            oid=f"/1/17/0/{adresse}/0",
            fct_type=15,
            name=zusatz,
            type="binary_sensor",
            zusatz=zusatz,
        )
        for adresse, zusatz in (
            ("2/2", "pufferladepumpe"),
            ("2/2", "umschaltventil_1"),
            ("2/9", "pufferladung"),
        )
    ]
    client.oids = {d["oid"] for d in client.devices}
    meta = {
        "/1/17/0/20/0/0": {"value": str(automatikkessel)},
        "/1/17/0/20/2/0": {"value": str(pufferspeicher)},
    }
    return client, meta


def test_ohne_automatikkessel_entfallen_nur_die_umschaltventile(client_module):
    client, meta = _umschaltmodul(client_module, automatikkessel=0, pufferspeicher=1)
    client._rollen_filter(meta)

    assert {d["name"] for d in client.devices} == {"pufferladepumpe", "pufferladung"}
    # Die Pumpe sitzt auf derselben Adresse und braucht sie weiter.
    assert "/1/17/0/2/2/0" in client.oids


def test_ohne_pufferspeicher_entfaellt_die_pufferladung(client_module):
    client, meta = _umschaltmodul(client_module, automatikkessel=1, pufferspeicher=0)
    client._rollen_filter(meta)

    assert {d["name"] for d in client.devices} == {"pufferladepumpe", "umschaltventil_1"}
    assert "/1/17/0/2/9/0" not in client.oids


def test_unbekannter_wert_am_umschaltmodul_nimmt_nichts_weg(client_module):
    client, meta = _umschaltmodul(client_module, automatikkessel=7, pufferspeicher=7)
    client._rollen_filter(meta)

    assert len(client.devices) == 3


def _gefiltert(client_module, fct_type, adressen, werte):
    """Namen der Adressen, die nach dem Rollenfilter an einem Gerät stehen bleiben."""
    client = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    client.devices = [
        client_module.WindhagerHttpClient._deskriptor(
            oid=f"/1/20/0/{a}/0", fct_type=fct_type, name=a, type="sensor"
        )
        for a in adressen
    ]
    client.oids = {d["oid"] for d in client.devices}
    client._rollen_filter({f"/1/20/0/{a}/0": {"value": w} for a, w in werte.items()})
    return {d["name"] for d in client.devices}


_INFINITY_PROGRAMME = ("3/61", "3/62", "3/63", "58/78", "58/79", "58/80")


@pytest.mark.parametrize(
    ("regelart", "bleibt"),
    [
        ("1", {"3/61", "3/62", "3/63"}),
        ("2", {"3/61", "3/62", "3/63"}),
        ("4", {"58/78", "58/79", "58/80"}),
        ("0", set(_INFINITY_PROGRAMME)),
        ("3", set(_INFINITY_PROGRAMME)),
        ("5", set(_INFINITY_PROGRAMME)),
        ("9", set(_INFINITY_PROGRAMME)),
    ],
)
def test_infinity_programme_entfallen_nur_beim_belegten_gegenwert(client_module, regelart, bleibt):
    """Pumpenkreis, Fan Coil und unbekannte Regelarten behalten Heiz- und Vorlaufprogramme."""
    namen = _gefiltert(client_module, 1, _INFINITY_PROGRAMME, {"7/76": regelart})
    assert namen == bleibt


@pytest.mark.parametrize(
    ("betriebsart", "bleibt"),
    [
        ("0", set()),
        ("1", {"0/118", "1/118"}),
        ("2", {"0/118", "1/118", "59/18"}),
        ("3", {"0/118", "1/118"}),
        ("4", {"0/118", "1/118", "59/18"}),
    ],
)
def test_zirkulationswerte_entfallen_nur_beim_belegten_gegenwert(
    client_module, betriebsart, bleibt
):
    """`5/6` = 4 „EIN“ nennt die Herstellerebene nicht; dort bleibt alles stehen."""
    namen = _gefiltert(client_module, 2, ("0/118", "1/118", "59/18"), {"5/6": betriebsart})
    assert namen == bleibt


@pytest.mark.parametrize(("kuehlen", "bleibt"), [("0", False), ("1", True), ("2", True)])
def test_kuehlprogramm_entfaellt_nur_ohne_kuehlen(client_module, kuehlen, bleibt):
    namen = _gefiltert(client_module, 1, ("59/48",), {"58/102": kuehlen})
    assert ("59/48" in namen) is bleibt


def test_kuehlprogramm_bleibt_ohne_lesbares_kuehlen(client_module):
    assert _gefiltert(client_module, 1, ("59/48",), {}) == {"59/48"}


@pytest.mark.parametrize(
    ("konfiguration", "bleibt"), [("0", True), ("1", False), ("2", True), ("4", True)]
)
def test_kuehlzeitprogramm_entfaellt_nur_bei_reinem_heizen(client_module, konfiguration, bleibt):
    namen = _gefiltert(client_module, 14, ("51/108",), {"51/115": konfiguration})
    assert ("51/108" in namen) is bleibt


def _logwin_mit_spiegel(client_module, mit_modul: bool, modul_adressen=("0/15", "23/87")):
    """LogWIN (fct 10) mit gespiegeltem Puffer, auf Wunsch neben dem Puffermodul (fct 15)."""
    client = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    eintraege = [(65, 10, "0/7"), (65, 10, "0/15"), (65, 10, "23/87")]
    if mit_modul:
        eintraege += [(17, 15, adresse) for adresse in modul_adressen]
    client.devices = [
        client_module.WindhagerHttpClient._deskriptor(
            oid=f"/1/{knoten}/0/{adresse}/0", fct_type=fct, name=f"{fct} {adresse}", type="sensor"
        )
        for knoten, fct, adresse in eintraege
    ]
    client.oids = {d["oid"] for d in client.devices}
    return client


def test_am_logwin_entfallen_die_vom_puffermodul_gespiegelten_werte(client_module):
    client = _logwin_mit_spiegel(client_module, mit_modul=True)
    client._spiegel_verwerfen()

    assert {d["name"] for d in client.devices} == {"10 0/7", "15 0/15", "15 23/87"}
    assert client.oids == {"/1/65/0/0/7/0", "/1/17/0/0/15/0", "/1/17/0/23/87/0"}


def test_ohne_puffermodul_behaelt_das_logwin_seinen_puffer(client_module):
    client = _logwin_mit_spiegel(client_module, mit_modul=False)
    client._spiegel_verwerfen()

    assert len(client.devices) == 3


@pytest.mark.parametrize(
    ("modul_adressen", "am_logwin"),
    [
        ((), {"0/7", "0/15", "23/87"}),
        (("23/87",), {"0/7", "0/15"}),
        (("2/9",), {"0/7", "0/15", "23/87"}),
    ],
)
def test_das_logwin_verliert_nur_was_das_puffermodul_selbst_fuehrt(
    client_module, modul_adressen, am_logwin
):
    """Ein Puffermodul ohne lesbare Werte nimmt dem Kessel nichts weg."""
    client = _logwin_mit_spiegel(client_module, mit_modul=True, modul_adressen=modul_adressen)
    client._spiegel_verwerfen()

    assert {d["name"][3:] for d in client.devices if d["fct_type"] == 10} == am_logwin


@pytest.mark.parametrize("schaltwert", ["-", "-.-", "", "Text"])
def test_unlesbarer_schaltwert_der_herstellerbedingung_nimmt_nichts_weg(client_module, schaltwert):
    assert _gefiltert(client_module, 20, ("0/22",), {"29/1": schaltwert}) == {"0/22"}


@pytest.mark.parametrize(
    ("quelle", "bleibt"),
    [
        ({"value": "7", "minValue": "0", "maxValue": "1"}, True),
        ({"value": "7", "enum": "[0,1]"}, True),
        ({"value": "0", "minValue": "0", "maxValue": "1"}, False),
        ({"value": "0.0", "enum": "[0,1]"}, False),
    ],
)
def test_herstellerbedingung_nimmt_nur_bei_einem_wert_aus_dem_bereich_weg(
    client_module, quelle, bleibt
):
    """Ein Wert außerhalb dessen, was die Steuerung für die Einstellung meldet, ist kein Gegenbeleg."""
    client = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    client.devices = [
        client_module.WindhagerHttpClient._deskriptor(
            oid="/1/14/0/0/22/0", fct_type=20, name="0/22", type="sensor"
        )
    ]
    client.oids = {"/1/14/0/0/22/0"}
    client._rollen_filter({"/1/14/0/29/1/0": quelle})

    assert bool(client.devices) is bleibt


@pytest.mark.parametrize(
    ("werte", "bleibt"),
    [
        ({"29/1": "0"}, True),
        ({"29/1": "0", "29/0": "-"}, True),
        ({"29/1": "0", "29/0": "1"}, True),
        ({"29/1": "0", "29/0": "0"}, False),
    ],
)
def test_mehrere_saetze_nehmen_nur_weg_wenn_jeder_widerspricht(client_module, werte, bleibt):
    """`22/31` gilt mit `29/1` oder `29/0`; ein unbekannter Satz kann die Adresse freischalten."""
    assert ("22/31" in _gefiltert(client_module, 20, ("22/31",), werte)) is bleibt


@pytest.mark.parametrize(
    "quelle", [{"value": "7"}, {"value": "7", "minValue": "0", "maxValue": "9"}, {"value": "-"}]
)
def test_unbelegte_modulfunktion_nimmt_nichts_weg(client_module, quelle):
    """Die Rollentabelle nennt die Modulfunktionen 0–5; eine andere ist kein Gegenbeleg."""
    client, _ = _puffer_client(client_module, 0)
    client._rollen_filter({"/1/16/1/20/4/0": quelle})

    assert len(client.devices) == 4


def test_das_puffermodul_fuehrt_seine_betriebsart_als_eigene_entitaet():
    """Neben der abgeleiteten Pufferladung: Der Verlauf soll 14, 15 und 16 unterscheiden."""
    from custom_components.heatnexus.geraete import umschaltung

    eintraege = [e for e in umschaltung.ENTITAETEN if e["oid"] == "/2/9/0"]
    art = next(e for e in eintraege if e["platform"] == "enum_sensor")
    assert art["enum"] == "2/9"
    # Ohne Zusatz behält die Entität die Kennung, die sie vor der Tabelle hatte.
    assert "key_suffix" not in art
