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
    c = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    c.neuron_by_node = {"60": "0000ABCD1234", "15": "0000ABCD5678"}

    # Ohne Anlage im Netz: Jeder Zugriff, den ein Test nicht selbst vorgibt,
    # läuft ins Leere statt in eine echte Verbindung.
    async def ohne_anlage(url, semaphore=None):
        return None, 599

    c._get = ohne_anlage
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


async def test_systemuhr_und_systemdatum_werden_nicht_von_selbst_angelegt(client):
    """Einstellwerte, die man einmal im Leben anfasst.

    Standardmäßig angelegt füllten sie die Entitätsliste und kosteten in jedem
    Durchlauf eine Anfrage an eine Anlage, die knapp zwei Sekunden je Anfrage
    braucht. Wer sie braucht, schaltet sie einzeln ein.
    """
    client.oids = {"/1/15/0/2/70/0", "/1/15/0/2/72/0"}
    client.menu_meta = {
        "/1/15/0/2/70/0": {"writeProt": False, "value": "24.12.2026"},
        "/1/15/0/2/72/0": {"writeProt": False, "value": "06:30"},
    }
    client.devices = [
        {"oid": oid, "name": name, "type": "auto", "level": "operate"}
        for oid, name in (("/1/15/0/2/70/0", "Datum"), ("/1/15/0/2/72/0", "Uhrzeit"))
    ]

    await client._apply_metadata()

    assert {d["type"] for d in client.devices} == {"date", "time"}
    assert all(d["enabled_default"] is False for d in client.devices)


async def test_auch_die_schreibgeschuetzte_systemuhr_bleibt_aus(client):
    """Schreibgeschützt wird sie als Text gelesen – die Auswahl gilt trotzdem."""
    client.oids = {"/1/15/0/2/70/0", "/1/15/0/2/72/0"}
    client.menu_meta = {
        "/1/15/0/2/70/0": {"writeProt": True, "value": "24.12.2026"},
        "/1/15/0/2/72/0": {"writeProt": True, "value": "06:30"},
    }
    client.devices = [
        {"oid": oid, "name": name, "type": "auto", "level": "operate"}
        for oid, name in (("/1/15/0/2/70/0", "Datum"), ("/1/15/0/2/72/0", "Uhrzeit"))
    ]

    await client._apply_metadata()

    assert {d["type"] for d in client.devices} == {"string_sensor"}
    assert all(d["enabled_default"] is False for d in client.devices)


async def test_ein_betriebswert_mit_datum_bleibt_an(client):
    """Nur die Systemuhr wird ausgeblendet, nicht jedes Feld mit Datum darin.

    „Urlaubsprogramm bis" und die Zirkulationszeiten sind Betriebswerte: Wer
    sie einstellt, will sie danach auch sehen.
    """
    client.oids = {"/1/15/0/3/78/0", "/1/15/0/5/70/0", "/1/15/0/0/7/0"}
    client.menu_meta = {
        "/1/15/0/3/78/0": {"writeProt": False, "value": "24.12.2026"},
        "/1/15/0/5/70/0": {"writeProt": False, "value": "06:30"},
        "/1/15/0/0/7/0": {"writeProt": True, "unit": "°C", "value": "45.7"},
    }
    client.devices = [
        {"oid": oid, "name": name, "type": "auto", "level": "operate"}
        for oid, name in (
            ("/1/15/0/3/78/0", "Urlaubsprogramm bis Datum"),
            ("/1/15/0/5/70/0", "WW-Zirkulation Einschaltzeit"),
            ("/1/15/0/0/7/0", "Kesseltemperatur Ist"),
        )
    ]

    await client._apply_metadata()

    assert all(d.get("enabled_default", True) is True for d in client.devices)


async def test_wer_die_systemzeit_will_bekommt_sie(client_module):
    """Ein Haken bei der Einrichtung statt beide Entitäten einzeln einschalten."""
    client = client_module.WindhagerHttpClient("192.0.2.10", "geheim", zeitwerte=True)
    client.neuron_by_node = {"15": "0000ABCD5678"}
    client.oids = {"/1/15/0/2/70/0", "/1/15/0/2/72/0"}
    client.menu_meta = {
        "/1/15/0/2/70/0": {"writeProt": False, "value": "24.12.2026"},
        "/1/15/0/2/72/0": {"writeProt": False, "value": "06:30"},
    }
    client.devices = [
        {"oid": oid, "name": name, "type": "auto", "level": "operate"}
        for oid, name in (("/1/15/0/2/70/0", "Datum"), ("/1/15/0/2/72/0", "Uhrzeit"))
    ]

    await client._apply_metadata()

    assert all(d["enabled_default"] is True for d in client.devices)


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


async def test_neu_hinzugekommene_zeitprogramme_werden_sofort_gelesen(client, monkeypatch):
    """Zeitprogramme entstehen erst im Vollabzug, also nach dem ersten Durchlauf.

    Sie laufen im trägen Takt mit. Ohne den Vorgriff blieben sie bis zum
    nächsten trägen Durchlauf – bei 30 s Intervall eine Viertelstunde – ohne
    Wert und damit in Home Assistant nicht verfügbar.
    """
    programm = [{"weekdays": ["Mo"], "switchPoints": [{"time": "06:00", "value": 21}]}]
    abrufe = []

    async def fetch_object(oid):
        abrufe.append(oid)
        return {"value": programm}, 200

    monkeypatch.setattr(client, "fetch_object", fetch_object)
    client.oids = set()
    client._tick = 3  # kein träger Durchlauf
    client.time_programs = [{"oid": "/1/15/0/5/64/0", "type": "time_program"}]

    daten = await client.fetch_all()

    assert abrufe == ["/1/15/0/5/64/0"]
    assert daten["objects"] == {"/1/15/0/5/64/0": programm}


async def test_gelesene_zeitprogramme_warten_wieder_auf_den_traegen_takt(client, monkeypatch):
    """Der Vorgriff gilt dem Nachzügler, nicht jedem Durchlauf.

    Sonst kostete jedes Zeitprogramm in jedem Durchlauf eine eigene Anfrage.
    """
    abrufe = []

    async def fetch_object(oid):
        abrufe.append(oid)
        return {"value": [{"weekdays": ["Mo"], "switchPoints": []}]}, 200

    monkeypatch.setattr(client, "fetch_object", fetch_object)
    client.oids = set()
    client._tick = 3
    client.time_programs = [{"oid": "/1/15/0/5/64/0", "type": "time_program"}]

    await client.fetch_all()
    await client.fetch_all()

    assert abrufe == ["/1/15/0/5/64/0"]


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
# Zeitbudget: ein Durchlauf, der nicht fertig wird, muss trotzdem vorankommen
# ---------------------------------------------------------------------------
@pytest.fixture
def uhr(client_module, monkeypatch):
    """Eine gestellte Uhr. Sonst hinge die Prüfung an echter Wartezeit."""
    stand = [1000.0]
    monkeypatch.setattr(client_module.time, "monotonic", lambda: stand[0])
    return stand


@pytest.fixture
def langsame_anlage(client, monkeypatch, uhr):
    """Eine Anlage, die für jeden Datenpunkt eine Sekunde braucht."""
    gelesen: list[str] = []

    async def fetch_oid(oid):
        uhr[0] += 1.0
        gelesen.append(oid)
        return oid, "1"

    monkeypatch.setattr(client, "_fetch_oid", fetch_oid)
    client.oids = set()
    client.poll_oids = {f"/oid/{nummer:02d}" for nummer in range(40)}
    client.poll_class = dict.fromkeys(client.poll_oids, "fast")
    return gelesen


async def test_ein_zu_grosser_durchlauf_behaelt_was_er_gelesen_hat(
    client, client_module, langsame_anlage
):
    """Der Fall aus #2: mehr Datenpunkte, als in das Zeitfenster passen.

    Vorher lief der Abruf in die Zeitüberschreitung des Coordinators. Damit
    war alles Gelesene verloren *und* der Zähler der Poll-Klassen blieb
    stehen – derselbe zu große Durchlauf stand danach unverändert wieder an,
    dauerhaft. Jetzt hört der Abruf von selbst auf und zählt weiter.
    """
    daten = await client.fetch_all(budget=10)

    assert len(langsame_anlage) == client_module.POLL_BLOCK
    assert client._rest == client.poll_oids - set(langsame_anlage)
    assert client._tick == 1
    assert len(daten["oids"]) == client_module.POLL_BLOCK


async def test_der_rest_kommt_im_naechsten_durchlauf_zuerst(client, client_module, langsame_anlage):
    """Ohne Vorrang stünden dieselben Werte immer wieder hinten an."""
    await client.fetch_all(budget=10)
    rest = set(client._rest)

    await client.fetch_all(budget=10)

    zweiter_durchlauf = langsame_anlage[client_module.POLL_BLOCK :]
    assert set(zweiter_durchlauf) <= rest


async def test_ohne_zeitgrenze_wird_alles_gelesen(client, langsame_anlage):
    """Die Grenze ist eine Notbremse, keine Drosselung."""
    await client.fetch_all()

    assert len(langsame_anlage) == 40
    assert client._rest == set()


# ---------------------------------------------------------------------------
# Abgelehnte Datenpunkte
# ---------------------------------------------------------------------------
async def test_ein_abgelehnter_datenpunkt_wird_nicht_wieder_gefragt(client, monkeypatch):
    """Die Anlage lehnt Positionen ab, die sie nicht führt.

    Beim Einlesen der Metadaten wurden sie schon bisher verworfen. Positionen
    aus den Menü-Ebenen liefen daran vorbei und wurden anschließend in jedem
    Durchlauf erneut angefragt, obwohl die Antwort feststeht (#2).
    """

    async def _get(url, semaphore=None):
        return {"code": 409, "reason": "Target returns invalid Identifier: 63-127"}, 409

    monkeypatch.setattr(client, "_get", _get)
    client.poll_oids = {"/1/15/0/1/20/0"}
    client.poll_class = {"/1/15/0/1/20/0": "fast"}

    oid, wert = await client._fetch_oid("/1/15/0/1/20/0")

    assert (oid, wert) == ("/1/15/0/1/20/0", None)
    assert client.poll_oids == set()
    assert client._faellig() == set()


async def test_eine_entitaet_kann_einen_abgelehnten_datenpunkt_nicht_zurueckholen(client):
    """Sonst meldete sie ihn beim nächsten Start gleich wieder an."""
    client._abgemeldet = {"/1/16/0/1/20/0"}

    client.register_poll_oid("/1/16/0/1/20/0")

    assert client._faellig() == set()


def test_ein_neues_einlesen_holt_abgelehnte_datenpunkte_nicht_zurueck(client):
    """Die Climate-Endungen kommen ungeprüft dazu, auch die Heizkreispumpe.

    Führt eine Anlage sie nicht, lehnt sie jede Anfrage darauf ab. Ohne diesen
    Abzug stünde die Position nach jedem Neustart und jedem `rediscover`
    wieder im Abruf.
    """
    client.devices = [{"prefix": "/1/16/0", "name": "HK2", "type": "climate"}]
    client._abgemeldet = {"/1/16/0/1/20/0"}

    client._compute_poll_oids()

    assert "/1/16/0/1/20/0" not in client.poll_oids
    assert "/1/16/0/0/1/0" in client.poll_oids


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
    assert beschreibung["alt_id"] == "192-0-2-10-1-60-0-0-7-0"
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


# ---------------------------------------------------------------------------
# Ein misslungener Abruf ist kein Messwert
# ---------------------------------------------------------------------------
async def _einen_wert(client, monkeypatch, antwort):
    """Einen Durchlauf über genau eine OID fahren, mit vorgegebener Antwort."""

    async def get(url, semaphore=None):
        return antwort()

    monkeypatch.setattr(client, "_get", get)
    client.oids = {"/1/60/0/2/81/0"}
    client.devices = [{"oid": "/1/60/0/2/81/0", "name": "Betriebsstunden", "type": "sensor"}]
    client._compute_poll_oids()
    return await client.fetch_all()


async def test_eine_zeitueberschreitung_loescht_den_bekannten_wert_nicht(client, monkeypatch):
    """Sonst steht ein träger Wert bis zum nächsten trägen Durchlauf leer da.

    Die Steuerung antwortet eine Anfrage nach der anderen; läuft daneben der
    Vollabzug, geht ein Abruf schon einmal in die Zeitüberschreitung. Wird
    daraus ein leerer Wert, verschwindet die Anzeige – bei der trägen Klasse
    für eine Viertelstunde.
    """
    zustand = {"antworten": True}

    def antwort():
        if not zustand["antworten"]:
            raise TimeoutError("keine Antwort")
        return {"value": "18116"}, 200

    daten = await _einen_wert(client, monkeypatch, antwort)
    assert daten["oids"]["/1/60/0/2/81/0"] == "18116"

    zustand["antworten"] = False
    client._tick = 0  # auch ein träger Wert ist wieder fällig
    daten = await client.fetch_all()

    assert daten["oids"]["/1/60/0/2/81/0"] == "18116"


async def test_ein_misslungener_abruf_wird_sofort_wiederholt(client, monkeypatch):
    """Nicht erst im eigenen Takt – sonst dauert die Erholung eine Viertelstunde."""

    async def get(url, semaphore=None):
        raise TimeoutError("keine Antwort")

    monkeypatch.setattr(client, "_get", get)
    client.oids = {"/1/60/0/2/81/0"}
    client.devices = [
        {"oid": "/1/60/0/2/81/0", "name": "Betriebsstunden", "state_class": "total_increasing"}
    ]
    client._compute_poll_oids()

    await client.fetch_all()
    client._tick = 1  # kein träger Durchlauf

    assert "/1/60/0/2/81/0" in client._faellig()


async def test_ein_abgelehnter_datenpunkt_bleibt_ohne_wert(client, monkeypatch):
    """Die Anlage sagt, dass es ihn nicht gibt – das ist eine Auskunft, kein Ausfall."""

    def antwort():
        return {"value": "18116"}, 200

    daten = await _einen_wert(client, monkeypatch, antwort)
    assert daten["oids"]["/1/60/0/2/81/0"] == "18116"

    async def get(url, semaphore=None):
        return {"reason": "invalid Identifier"}, 409

    monkeypatch.setattr(client, "_get", get)
    client._tick = 0
    daten = await client.fetch_all()

    assert daten["oids"].get("/1/60/0/2/81/0") is None


async def test_gezieltes_nachlesen_meldet_nur_was_ankam(client, monkeypatch):
    """Sonst überschriebe das Nachfassen einen gültigen Wert mit einem leeren."""

    async def get(url, semaphore=None):
        if url.endswith("/1/60/0/2/81/0"):
            raise TimeoutError("keine Antwort")
        return {"value": "42"}, 200

    monkeypatch.setattr(client, "_get", get)

    gelesen = await client.fetch_oids(["/1/60/0/2/81/0", "/1/60/0/0/7/0"])

    assert gelesen == {"/1/60/0/0/7/0": "42"}


# ---------------------------------------------------------------------------
# Abfragetaste je Anlagenteil
# ---------------------------------------------------------------------------
def test_jedes_anlagenteil_bekommt_eine_abfragetaste(client):
    client.devices = [
        {"oid": "/1/60/0/0/7/0", "device_id": "abcd-0", "device_name": "PuroWIN", "fct_type": 25},
        {"oid": "/1/60/0/2/81/0", "device_id": "abcd-0", "device_name": "PuroWIN", "fct_type": 25},
        {"oid": "/1/15/0/0/2/0", "device_id": "abcd-1", "device_name": "Heizkreis", "fct_type": 14},
    ]
    client._abfragetasten()

    tasten = [d for d in client.devices if d.get("type") == "refresh"]
    assert [t["device_id"] for t in tasten] == ["abcd-0", "abcd-1"]
    assert {t["name"] for t in tasten} == {"Werte jetzt abfragen"}
    # Ohne Kategorie steht sie im Abschnitt Steuerung, nicht in der Konfiguration.
    assert all(t.get("category") is None for t in tasten)
    assert {t["id"] for t in tasten} == {"abcd-0-abfragen", "abcd-1-abfragen"}


def test_eine_taste_ohne_datenpunkt_entsteht_nicht(client):
    """Das Steuerungsgerät führt nur Meldungen; dort gibt es nichts zu lesen."""
    client.devices = [{"type": "device_status", "device_id": "abcd-0", "device_name": "PuroWIN"}]
    client._abfragetasten()

    assert not [d for d in client.devices if d.get("type") == "refresh"]


async def test_die_taste_liest_nur_das_eigene_anlagenteil(client, monkeypatch):
    gelesen = []

    async def fetch_oids(oids):
        gelesen.extend(oids)
        return dict.fromkeys(oids, "1")

    monkeypatch.setattr(client, "fetch_oids", fetch_oids)
    client.devices = [
        {"oid": "/1/60/0/0/7/0", "device_id": "abcd-0", "name": "Kessel", "type": "temperature"},
        {"oid": "/1/15/0/0/2/0", "device_id": "abcd-1", "name": "Vorlauf", "type": "temperature"},
    ]
    client._compute_poll_oids()

    await client.geraet_abfragen("abcd-0")

    assert gelesen == ["/1/60/0/0/7/0"]


async def test_die_taste_fragt_nicht_ab_was_der_abruf_auslaesst(client, monkeypatch):
    """Ein Kessel führt mehrere hundert Positionen; gelesen wird das Aktive."""

    async def fetch_oids(oids):
        return dict.fromkeys(oids, "1")

    monkeypatch.setattr(client, "fetch_oids", fetch_oids)
    client.devices = [
        {
            "oid": "/1/60/0/9/31/0",
            "device_id": "abcd-0",
            "name": "Mindestlaufzeit",
            "enabled_default": False,
        }
    ]
    client._compute_poll_oids()

    assert await client.geraet_abfragen("abcd-0") == {}


# ---------------------------------------------------------------------------
# Abgleich im Hintergrund
# ---------------------------------------------------------------------------
async def test_der_abgleich_laesst_traege_werte_stehen(client, monkeypatch):
    """Ein Abgleich liest den Bestand neu ein, nicht die Werte.

    Träge Adressen sind danach bis zu eine Viertelstunde nicht fällig; fällt
    ihr Wert dabei aus dem Bestand, steht die Entität so lange leer da.
    """
    beschreibungen = [
        {
            "oid": "/1/60/0/2/81/0",
            "id": "abcd-0-2-81-0",
            "name": "Betriebsstunden",
            "type": "sensor",
            "state_class": "total_increasing",
            "device_id": "abcd-0",
            "device_name": "PuroWIN",
        },
        {
            "oid": "/1/60/0/0/7/0",
            "id": "abcd-0-0-7-0",
            "name": "Kesseltemperatur",
            "type": "temperature",
            "device_id": "abcd-0",
            "device_name": "PuroWIN",
        },
    ]

    async def get(url, semaphore=None):
        return {"value": "18116"}, 200

    monkeypatch.setattr(client, "_get", get)
    client.restore_discovery(
        {
            "oids": [d["oid"] for d in beschreibungen],
            "devices": [dict(d) for d in beschreibungen],
            "poll_oids": [d["oid"] for d in beschreibungen],
        }
    )

    daten = await client.fetch_all()
    assert daten["oids"]["/1/60/0/2/81/0"] == "18116"

    # Der Abgleich baut Deskriptoren und Abrufsatz neu auf, wie `_discover`
    # und `_apply_metadata` es tun.
    async def discover(nur_kern=False):
        client.devices = [dict(d) for d in beschreibungen]
        client.oids = {d["oid"] for d in beschreibungen}

    async def apply_metadata():
        client.devices = [dict(d) for d in client.devices]

    monkeypatch.setattr(client, "_discover", discover)
    monkeypatch.setattr(client, "_apply_metadata", apply_metadata)
    await client.async_init(erzwingen=True)

    daten = await client.fetch_all()

    assert daten["oids"].get("/1/60/0/2/81/0") == "18116"


async def test_ein_leer_gewordener_wert_wird_einmal_nachgelesen(client, monkeypatch):
    """Die Leermarke der Anlage darf einen trägen Wert nicht für eine Viertelstunde tilgen.

    `-` und `-.-` heißen „kein Messwert". Antwortet die Steuerung unter Last
    so auf eine Adresse, die eben noch einen Wert hatte, ist die Anzeige sonst
    bis zum nächsten Durchlauf ihrer Klasse leer.
    """
    antwort = {"wert": "18116"}

    async def get(url, semaphore=None):
        return {"value": antwort["wert"]}, 200

    monkeypatch.setattr(client, "_get", get)
    client.oids = {"/1/60/0/2/81/0"}
    client.devices = [
        {"oid": "/1/60/0/2/81/0", "name": "Betriebsstunden", "state_class": "total_increasing"}
    ]
    client._compute_poll_oids()

    await client.fetch_all()
    antwort["wert"] = "-"
    client._tick = 0
    daten = await client.fetch_all()

    assert daten["oids"]["/1/60/0/2/81/0"] is None
    client._tick = 1  # kein träger Durchlauf
    assert "/1/60/0/2/81/0" in client._faellig()


async def test_ein_dauerhaft_leerer_wert_wird_nicht_ewig_nachgelesen(client, monkeypatch):
    """Ein nicht angeschlossener Fühler bleibt leer – ein Nachlesen genügt."""

    async def get(url, semaphore=None):
        return {"value": "-.-"}, 200

    monkeypatch.setattr(client, "_get", get)
    client.oids = {"/1/60/0/2/81/0"}
    client.devices = [
        {"oid": "/1/60/0/2/81/0", "name": "Betriebsstunden", "state_class": "total_increasing"}
    ]
    client._compute_poll_oids()

    await client.fetch_all()
    client._tick = 0
    await client.fetch_all()

    client._tick = 1
    assert "/1/60/0/2/81/0" not in client._faellig()


def test_ein_lueckenhafter_abrufplan_ueberlebt_den_neustart_nicht(client_module):
    """Der Plan entsteht aus den Deskriptoren, nicht aus dem Zwischenspeicher.

    Ein abgebrochener Erkennungslauf hinterlässt einen halben Plan; übernommen
    statt neu bestimmt, blieben seine Datenpunkte dauerhaft ungelesen.
    """
    c = client_module.WindhagerHttpClient("192.0.2.10", "geheim")

    c.restore_discovery(
        {
            "oids": ["/1/60/0/2/81/0"],
            "devices": [
                {
                    "id": "SN1-3-0-2-81-0",
                    "oid": "/1/60/0/2/81/0",
                    "name": "Betriebsstunden",
                    "type": "sensor",
                    "enabled_default": True,
                }
            ],
            "poll_oids": [],
        }
    )

    assert "/1/60/0/2/81/0" in c.poll_oids


async def test_die_sammelseite_wird_nur_einmal_ausprobiert(client, monkeypatch):
    """Antwortet die Steuerung leer, kostet jeder weitere Versuch eine Anfrage."""
    anfragen: list[str] = []

    async def antwort(url, semaphore=None):
        anfragen.append(url)
        if "count=-1" in url:
            return [], 200
        if "offset=" in url:
            return [], 200
        return [{"OID": f"{url[-2:]}/0"}], 200

    monkeypatch.setattr(client, "_get", antwort)

    for menu in ("97", "98"):
        await client._read_menu("/1/60/0", menu, 50, None)

    assert sum(1 for u in anfragen if "count=-1" in u) == 1


def test_eine_taste_kostet_keinen_abruf(client):
    """Sie zeigt nichts an; ihre Adresse wird nur beschrieben."""
    client.devices = [
        {"oid": "/1/60/0/0/7/0", "name": "Kesseltemperatur Ist", "type": "temperature"},
        {"oid": "/1/60/0/9/75/0", "name": "Serviceausbrand starten", "type": "button"},
    ]

    client._compute_poll_oids()

    assert client.poll_oids == {"/1/60/0/0/7/0"}


async def test_der_erste_abruf_nimmt_den_lesespeicher_mit(client, monkeypatch):
    """Sonst steht die Anzeige zwanzig Sekunden lang leer."""
    from datetime import datetime

    client.devices = [{"oid": "/1/60/0/0/7/0", "name": "Kesseltemperatur Ist"}]
    client.oids = {"/1/60/0/0/7/0"}
    client._compute_poll_oids()
    jetzt = datetime(2026, 8, 18, 12, 0, 0)

    async def speicher(url, semaphore=None):
        assert url.endswith("/api/1.0/datapoints")
        return [
            {
                "OID": "/1/60/0/0/7/0",
                "value": "63.5",
                "timestamp": "2026-08-18 11:58:00",
            }
        ], 200

    monkeypatch.setattr(client, "_get", speicher)
    await client._startwerte_lesen(15, jetzt)

    assert client._letzte_werte == {"/1/60/0/0/7/0": "63.5"}


async def test_der_lesespeicher_ueberschreibt_nichts(client, monkeypatch):
    """Was der Abruf gelesen hat, gilt – der Speicher ist nur der Anfang."""
    from datetime import datetime

    client.devices = [{"oid": "/1/60/0/0/7/0", "name": "Kesseltemperatur Ist"}]
    client.oids = {"/1/60/0/0/7/0"}
    client._compute_poll_oids()
    client._letzte_werte["/1/60/0/0/7/0"] = "70.0"

    async def speicher(url, semaphore=None):
        return [
            {
                "OID": "/1/60/0/0/7/0",
                "value": "63.5",
                "timestamp": "2026-08-18 11:58:00",
            }
        ], 200

    monkeypatch.setattr(client, "_get", speicher)
    await client._startwerte_lesen(15, datetime(2026, 8, 18, 12, 0, 0))

    assert client._letzte_werte["/1/60/0/0/7/0"] == "70.0"


def test_ein_sollwert_laeuft_nicht_im_schnellen_takt(client_module):
    """Sein Name klingt nach Messwert, geändert wird er trotzdem nur von Hand."""
    beschreibung = {"name": "Raumtemperatur Heizbetrieb", "type": "number"}
    assert client_module.WindhagerHttpClient._poll_klasse(beschreibung) == "normal"


def test_eine_neu_angemeldete_adresse_wird_sofort_gelesen(client):
    """Sonst stünde ein träger Wert nach dem Start bis zum nächsten Takt leer."""
    client.register_poll_oid("/1/16/1/9/35/0")
    assert "/1/16/1/9/35/0" in client._faellig()


def test_eine_bekannte_adresse_draengelt_sich_nicht_vor(client):
    """Wer schon einen Wert hat, wartet auf seinen Takt."""
    client._letzte_werte["/1/16/1/9/35/0"] = "17.0"
    client.register_poll_oid("/1/16/1/9/35/0")
    assert "/1/16/1/9/35/0" not in (client._rest or set())
