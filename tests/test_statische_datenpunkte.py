"""Datenpunkte, die in keiner Menü-Ebene stehen.

Die Menü-Abfrage ist die Hauptquelle der Erkennung – aber nicht die einzige.
Die Steuerung führt einige Positionen ausschließlich in ihrer statischen
Navigation: Sonderzeitprogramm, Störspeicher, Passwort. Der Menü-Abzug findet
sie nie, weil sie dort schlicht nicht vorkommen.

Die Anlage liefert diese Liste selbst aus, unter ``/res/``. Geprüft wird hier
das Auslesen dieser Liste – ohne Netz, an den Formen, die die Steuerung
tatsächlich schreibt.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def client_module():
    from custom_components.heatnexus import client

    return client


# Die Zuordnungsdatei benennt die Position im letzten OID-Abschnitt.
ZUORDNUNG = """<?xml version="1.0" encoding="utf-8"?>
<staticnavassignment>
  <fct type="0">
    <staticentry type="errorlog" oidextension="2/90/0"/>
    <staticentry type="timeprogram" oidextension="4/80/0"/>
  </fct>
  <fct type="18">
    <staticentry type="parameter" oidextension="4/42/0"/>
  </fct>
</staticnavassignment>
"""

# Die Navigationsdatei schreibt dieselbe Adresse zweistellig und mit Doppelpunkt.
NAVIGATION = """<?xml version="1.0" encoding="utf-8"?>
<staticnav>
  <timeprogram gnmn="03:61"><text><de>Zeitprogramm 1</de></text></timeprogram>
  <timeprogram gnmn="05:62"><text><de>Legionellenprogramm</de></text></timeprogram>
</staticnav>
"""


def test_die_zuordnungsdatei_nennt_ihre_positionen(client_module):
    assert client_module._statische_positionen(ZUORDNUNG) == {"2/90", "4/80", "4/42"}


def test_zweistellige_adressen_werden_wie_im_menue_geschrieben(client_module):
    """„03:61" und „3/61" sind dieselbe Position.

    Alles andere im Client rechnet mit der Menü-Schreibweise; käme die
    führende Null durch, entstünde eine zweite Kennung für denselben
    Datenpunkt.
    """
    assert client_module._statische_positionen(NAVIGATION) == {"3/61", "5/62"}


def test_eine_unlesbare_datei_kostet_keine_erkennung(client_module):
    """Eine ältere Firmware liefert diese Dateien womöglich gar nicht.

    Dann werden eben keine zusätzlichen Positionen geprüft – die Erkennung
    darf daran nicht scheitern.
    """
    assert client_module._statische_positionen("<html>404</html>") == set()
    assert client_module._statische_positionen("") == set()


# ---------------------------------------------------------------------------
# Von der Anlage holen
# ---------------------------------------------------------------------------
@pytest.fixture
def client(client_module):
    c = client_module.WindhagerHttpClient("192.0.2.10", "geheim")
    # Die Erkennung fragt die Steuerung einmal nach sich selbst und einmal nach
    # ihren Knoten. Beides ist hier nicht der Prüfgegenstand; ein gefüllter
    # Stand überspringt die Anfragen.
    c.geraeteinfo = {"device": "MB66xx"}
    c.werksbezeichnung = {"15": "UMUMLZ"}
    return c


async def test_beide_ressourcen_zusammen_ergeben_die_positionen(client, monkeypatch):
    """Die Steuerung verteilt die Angaben auf zwei Dateien."""

    async def ressource(pfad):
        return {"xml/StaticNavAssignment.xml": ZUORDNUNG, "xml/StaticNav.xml": NAVIGATION}[pfad]

    monkeypatch.setattr(client, "_ressource", ressource)
    assert await client._statische_adressen() == {"2/90", "4/80", "4/42", "3/61", "5/62"}


async def test_eine_fehlende_ressource_nimmt_die_andere_nicht_mit(client, monkeypatch):
    """Eine Firmware ohne die eine Datei liefert womöglich die andere."""

    async def ressource(pfad):
        return NAVIGATION if pfad == "xml/StaticNav.xml" else None

    monkeypatch.setattr(client, "_ressource", ressource)
    assert await client._statische_adressen() == {"3/61", "5/62"}


async def test_die_positionen_werden_je_erkennung_einmal_geholt(client, monkeypatch):
    """Sie gelten für die ganze Anlage, nicht je Funktion.

    Bei zwei Kesseln mit je vier Funktionen wären es sonst acht Abrufe
    derselben zwei Dateien.
    """
    abrufe = []

    async def fetch(url, semaphore=None):
        return [
            {
                "nodeId": 15,
                "neuronId": "0000ABCD5678",
                "functions": [
                    {"fctId": 0, "fctType": 14, "name": "Heizkreis 1"},
                    {"fctId": 1, "fctType": 14, "name": "Heizkreis 2"},
                ],
            }
        ]

    async def read_function_menus(prefix, fct_type):
        return {}

    async def statische_adressen():
        abrufe.append("gelesen")
        return {"4/80"}

    monkeypatch.setattr(client, "fetch", fetch)
    monkeypatch.setattr(client, "_read_function_menus", read_function_menus)
    monkeypatch.setattr(client, "_statische_adressen", statische_adressen)

    await client._discover()

    assert abrufe == ["gelesen"]
    # Angeboten wird die Position trotzdem an jeder Funktion.
    assert {"/1/15/0/4/80/0", "/1/15/1/4/80/0"} <= client.oids


# ---------------------------------------------------------------------------
# In der Erkennung
# ---------------------------------------------------------------------------
async def test_eine_statische_position_wird_zum_datenpunkt(client, monkeypatch):
    """Sonst fehlte das Sonderzeitprogramm, das in keinem Menü steht.

    Ob die Position an dieser Funktion überhaupt existiert, klärt anschließend
    die Metadatenabfrage – eine, die es nicht gibt, fällt dort heraus.
    """

    async def fetch(url, semaphore=None):
        assert url == "/1"
        return [
            {
                "nodeId": 15,
                "neuronId": "0000ABCD5678",
                "functions": [{"fctId": 0, "fctType": 14, "name": "Heizkreis"}],
            }
        ]

    async def read_function_menus(prefix, fct_type):
        return {}

    async def statische_adressen():
        return {"4/80"}

    monkeypatch.setattr(client, "fetch", fetch)
    monkeypatch.setattr(client, "_read_function_menus", read_function_menus)
    monkeypatch.setattr(client, "_statische_adressen", statische_adressen)

    await client._discover()

    assert "/1/15/0/4/80/0" in client.oids


async def test_der_kurzdurchlauf_liest_keine_ressourcen(client, monkeypatch):
    """Die Einrichtung soll mit wenigen Anfragen stehen."""

    async def fetch(url, semaphore=None):
        return [{"nodeId": 15, "neuronId": "X", "functions": []}]

    async def statische_adressen():
        raise AssertionError("darf im Kurzdurchlauf nicht aufgerufen werden")

    monkeypatch.setattr(client, "fetch", fetch)
    monkeypatch.setattr(client, "_statische_adressen", statische_adressen)

    await client._discover(nur_kern=True)
