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
