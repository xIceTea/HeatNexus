"""Was wann gelesen wird – der Abrufplan des Clients.

Nicht jeder Wert ändert sich im selben Takt. Die Kesseltemperatur gehört alle
30 s abgefragt, „Betriebsstunden gesamt" nicht; ein standardmäßig
deaktivierter Fachparameter gar nicht, solange ihn niemand einschaltet. Diese
Einstufung entscheidet über die Last auf der Steuerung – bei zwei Anlagen
waren es einmal 8900 Anfragen je Stunde.

Alles hier kommt ohne Netz aus: geprüft wird die Rechnung, nicht die Leitung.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def client_module():
    from custom_components.heatnexus import client

    return client


@pytest.fixture
def client(client_module):
    c = client_module.WindhagerHttpClient("192.168.178.100", "geheim")
    c.neuron_by_node = {"60": "0000ABCD1234", "15": "0000ABCD5678"}
    return c


# ---------------------------------------------------------------------------
# Poll-Klasse: was der Wert *ist*, nicht wo er steht
# ---------------------------------------------------------------------------
def test_ein_zaehlerstand_wird_traege_gelesen(client_module):
    beschreibung = {"name": "Betriebsstunden gesamt", "state_class": "total_increasing"}
    assert client_module.WindhagerHttpClient._poll_klasse(beschreibung) == "slow"


def test_eine_arbeitseinheit_wird_traege_gelesen(client_module):
    """Kilowattstunden bewegen sich in Stunden, nicht in Sekunden."""
    assert client_module.WindhagerHttpClient._poll_klasse({"unit": "kWh"}) == "slow"


async def test_uhrzeit_und_datum_werden_nicht_von_selbst_angelegt(client, client_module):
    """Einstellwerte, die man einmal im Leben anfasst.

    Standardmäßig angelegt füllten sie die Entitätsliste und kosteten in jedem
    Durchlauf eine Anfrage an eine Anlage, die knapp zwei Sekunden je Anfrage
    braucht. Wer sie braucht, schaltet sie einzeln ein.
    """
    client.oids = {"/1/15/0/3/78/0", "/1/15/0/5/61/0", "/1/15/0/0/7/0"}
    client.menu_meta = {
        "/1/15/0/3/78/0": {"writeProt": False, "value": "24.12.2026"},
        "/1/15/0/5/61/0": {"writeProt": False, "value": "06:30"},
        "/1/15/0/0/7/0": {"writeProt": True, "unit": "°C", "value": "45.7"},
    }
    client.devices = [
        {"oid": oid, "name": name, "type": "auto", "level": "operate"}
        for oid, name in (
            ("/1/15/0/3/78/0", "Urlaubsprogramm bis Datum"),
            ("/1/15/0/5/61/0", "Schaltzeit"),
            ("/1/15/0/0/7/0", "Kesseltemperatur Ist"),
        )
    ]

    await client._apply_metadata()

    nach_typ = {d["type"]: d for d in client.devices}
    assert nach_typ["date"]["enabled_default"] is False
    assert nach_typ["time"]["enabled_default"] is False
    # Die Gegenprobe: ein Messwert bleibt selbstverständlich an.
    assert nach_typ["temperature"].get("enabled_default", True) is True


def test_ein_abgewaehlter_fachparameter_wird_traege_gelesen(client_module):
    """Er ändert sich nur, wenn ihn jemand ändert."""
    beschreibung = {"name": "Kesselsolltemperatur Minimum", "enabled_default": False}
    assert client_module.WindhagerHttpClient._poll_klasse(beschreibung) == "slow"


def test_eine_temperatur_wird_schnell_gelesen(client_module):
    assert client_module.WindhagerHttpClient._poll_klasse({"type": "temperature"}) == "fast"


def test_im_zweifel_bleibt_es_beim_mittleren_takt(client_module):
    """Lieber einmal zu oft gelesen als eine Anzeige, die nachhinkt."""
    assert client_module.WindhagerHttpClient._poll_klasse({"name": "Rätsel"}) == "normal"


# ---------------------------------------------------------------------------
# Poll-Menge
# ---------------------------------------------------------------------------
def test_abgewaehlte_entitaeten_kosten_keinen_abruf(client):
    """Sie melden ihre OID erst an, wenn der Nutzer sie in HA einschaltet."""
    client.devices = [
        {"oid": "/1/60/0/0/7/0", "name": "Kesseltemperatur Ist", "type": "temperature"},
        {"oid": "/1/60/0/9/31/0", "name": "Mindestlaufzeit", "enabled_default": False},
    ]
    client._compute_poll_oids()
    assert client.poll_oids == {"/1/60/0/0/7/0"}
    # Die Klasse steht trotzdem bereit – sonst fehlte sie beim Anmelden.
    assert client.poll_class["/1/60/0/9/31/0"] == "slow"


def test_ein_thermostat_zieht_seine_hilfswerte_mit(client):
    """Ohne sie zeigte die Klimakarte Soll- und Istwert nicht an."""
    client.devices = [{"type": "climate", "prefix": "/1/15/0"}]
    client._compute_poll_oids()
    assert client.poll_oids == set(client.climate_oids("/1/15/0"))
    # Das Thermostat ist das Bedienelement der Anlage und darf nicht nachhinken.
    assert set(client.poll_class.values()) == {"fast"}


def test_zeitprogramme_laufen_nicht_ueber_den_abruf(client):
    """Sie kommen über den object-Endpunkt, nicht über lookup."""
    client.devices = [{"oid": "/1/15/0/5/64/0", "name": "WW-Programm", "type": "time_program"}]
    client._compute_poll_oids()
    assert client.poll_oids == set()
    assert len(client.time_programs) == 1


def test_eine_eingeschaltete_entitaet_meldet_sich_selbst_an(client):
    client.devices = [{"oid": "/1/60/0/9/31/0", "name": "X", "enabled_default": False}]
    client._compute_poll_oids()
    client.register_poll_oid("/1/60/0/9/31/0")
    assert "/1/60/0/9/31/0" in client._faellig()
    client.unregister_poll_oid("/1/60/0/9/31/0")
    assert client._faellig() == set()


# ---------------------------------------------------------------------------
# Fälligkeit: der Takt hängt am eingestellten Intervall
# ---------------------------------------------------------------------------
def test_beim_ersten_durchlauf_ist_alles_faellig(client):
    """Sonst stünde ein träger Wert bis zu einer Viertelstunde ohne Anzeige da."""
    client.poll_oids = {"/schnell", "/traege"}
    client.poll_class = {"/schnell": "fast", "/traege": "slow"}
    client._tick = 0
    assert client._faellig() == {"/schnell", "/traege"}


def test_ein_traeger_wert_setzt_durchlaeufe_aus(client):
    client.poll_oids = {"/schnell", "/traege"}
    client.poll_class = {"/schnell": "fast", "/traege": "slow"}
    client._tick = 1
    assert client._faellig() == {"/schnell"}


def test_der_takt_folgt_dem_eingestellten_intervall(client_module):
    """„Alle 15 Minuten" heißt bei 30 s jeden 30. Durchlauf, bei 300 s jeden 3."""
    schnell = client_module.WindhagerHttpClient("h", "p", update_interval=30)
    langsam = client_module.WindhagerHttpClient("h", "p", update_interval=300)
    assert schnell._takte()["slow"] == 30
    assert langsam._takte()["slow"] == 3


# ---------------------------------------------------------------------------
# Namen und Kennungen
# ---------------------------------------------------------------------------
def test_gleichnamige_datenpunkte_bekommen_ihre_adresse(client):
    """„Betriebswahl" gibt es als Bedienung (3/50) und als Anzeige (4/14)."""
    client.devices = [
        {"oid": "/1/15/0/3/50/0", "name": "Betriebswahl", "device_id": "g1"},
        {"oid": "/1/15/0/4/14/0", "name": "Betriebswahl", "device_id": "g1"},
        {"oid": "/1/60/0/0/7/0", "name": "Kesseltemperatur Ist", "device_id": "g2"},
    ]
    client._namen_vereindeutigen()
    assert [d["name"] for d in client.devices] == [
        "Betriebswahl (3/50)",
        "Betriebswahl (4/14)",
        "Kesseltemperatur Ist",
    ]


def test_gleiche_namen_an_verschiedenen_geraeten_bleiben_gleich(client):
    """Der Gerätename steht in HA davor – dort ist nichts zu verwechseln."""
    client.devices = [
        {"oid": "/1/15/0/0/1/0", "name": "Raumtemperatur Ist", "device_id": "kreis1"},
        {"oid": "/1/16/0/0/1/0", "name": "Raumtemperatur Ist", "device_id": "kreis2"},
    ]
    client._namen_vereindeutigen()
    assert {d["name"] for d in client.devices} == {"Raumtemperatur Ist"}


def test_die_steuerung_nimmt_die_kleinste_seriennummer(client):
    """Sie ändert sich nur, wenn genau dieser Baustein getauscht wird."""
    assert client.steuerung_kennung() == "steuerung-0000ABCD1234"


def test_ohne_bekannte_knoten_gibt_es_keine_steuerungskennung(client_module):
    assert client_module.WindhagerHttpClient("h", "p").steuerung_kennung() is None


def test_die_datenpunktadresse_ist_relativ_zum_praefix(client_module):
    gnmn = client_module.WindhagerHttpClient._gnmn
    assert gnmn("/1/15/0", "/1/15/0/3/50/0") == "3/50"
    # Passt der Präfix nicht, bleibt die OID stehen statt falsch zu raten.
    assert gnmn("/1/15/0", "/1") == "/1"


# ---------------------------------------------------------------------------
# Beschreibungen aus den kuratierten Tabellen
# ---------------------------------------------------------------------------
def test_eine_kuratierte_beschreibung_traegt_beide_kennungen(client):
    """Beide Kennungen, neue und alte.

    `alt_id` ist der Weg für Bestandsinstallationen: Ohne ihn verlören sie bei
    der Umstellung Namen, Bereich und Verlauf jeder Entität.
    """
    client.oids = set()
    client.devices = []
    client._add_entity(
        {"oid": "/0/7/0", "name": "Kesseltemperatur Ist", "platform": "temperature"},
        "/1/60/0",
        "/1/60",
        {"name": "PuroWIN", "fctType": 25},
    )
    (beschreibung,) = client.devices
    assert beschreibung["oid"] == "/1/60/0/0/7/0"
    assert beschreibung["id"] == "0000ABCD1234-0-0-7-0"
    assert beschreibung["alt_id"] == "192-168-178-100-1-60-0-0-7-0"
    assert beschreibung["device_id"] == "0000ABCD1234-0"
    assert beschreibung["fct_type"] == 25
    assert client.oids == {"/1/60/0/0/7/0"}


def test_ein_knotenweiter_datenpunkt_haengt_am_knoten_nicht_an_der_funktion(client):
    """Sonst bekäme jede Funktion desselben Knotens ihre eigene Meldung."""
    client.oids = set()
    client.devices = []
    client._add_entity(
        {"oid": "/2/1/0", "name": "Meldung", "platform": "sensor", "node_level": True},
        "/1/60/0",
        "/1/60",
        {"name": "PuroWIN", "fctType": 25},
    )
    assert client.devices[0]["oid"] == "/1/60/2/1/0"


def test_ein_namenszusatz_landet_in_beiden_kennungen(client):
    """Zwei Entitäten auf derselben OID – ohne Zusatz teilten sie sich die Kennung."""
    client.oids = set()
    client.devices = []
    client._add_entity(
        {"oid": "/0/7/0", "name": "X", "platform": "sensor", "key_suffix": "text"},
        "/1/60/0",
        "/1/60",
        {"name": "PuroWIN", "fctType": 25},
    )
    (beschreibung,) = client.devices
    assert beschreibung["id"].endswith("-text")
    assert beschreibung["alt_id"].endswith("-text")


# ---------------------------------------------------------------------------
# Zeitprogramm oder bloß eine Liste
# ---------------------------------------------------------------------------
def test_ein_zeitprogramm_wird_erkannt(client_module):
    wert = [{"weekdays": ["Mo"], "switchPoints": [{"time": "06:00", "value": 21}]}]
    assert client_module._ist_zeitprogramm(wert)


def test_die_funktionsliste_eines_knotens_ist_keins(client_module):
    """Auch sie ist eine Liste von Objekten und ging vorher als Programm durch."""
    assert not client_module._ist_zeitprogramm([{"fctType": 25, "lock": False}])


def test_ein_text_ist_kein_zeitprogramm(client_module):
    assert not client_module._ist_zeitprogramm("PW 400")
    assert not client_module._ist_zeitprogramm([])


# ---------------------------------------------------------------------------
# Statistik
# ---------------------------------------------------------------------------
def test_ohne_anfragen_wird_nichts_gemittelt(client):
    """Kein Wert ist ehrlicher als eine Division durch null."""
    zahlen = client.statistik()
    assert zahlen["anfragen"] == 0
    assert zahlen["dauer_je_anfrage_ms"] is None
    assert zahlen["wartezeit_je_anfrage_ms"] is None


def test_die_statistik_mittelt_ueber_die_anfragen(client):
    client.request_count = 4
    client.request_seconds = 2.0
    client.queue_seconds = 0.4
    zahlen = client.statistik()
    assert zahlen["dauer_je_anfrage_ms"] == 500.0
    assert zahlen["wartezeit_je_anfrage_ms"] == 100.0
