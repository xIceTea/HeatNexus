"""Die Erkennung an einer Anlage, die hier nicht steht.

Getestet wird gegen einen **BioWIN-Kessel** (fctType 9). Es gibt keinen zum
Nachmessen; deshalb bekommt die Erkennung hier eine erfundene Anlage
vorgesetzt, deren Antworten der Form entsprechen, die jede Steuerung liefert.

Was das trägt: Der ganze Weg von der Anlagenstruktur bis zur fertigen
Beschreibung läuft durch – kuratierte Tabelle, Ebenenzuordnung aus der
Geräte-Datenbank, Auflösung des Typs aus den Metadaten, Aussortieren dessen,
was die Anlage nicht kennt. Bricht daran etwas, merkt es sonst erst der erste
fremde Nutzer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


async def keine_geraetetexte():
    """Das Textwerk der Steuerung spielt in diesen Tests keine Rolle."""
    from custom_components.heatnexus import geraetetexte

    return geraetetexte.Texte()


@pytest.fixture(scope="module")
def client_module():
    from custom_components.heatnexus import client

    return client


PRAEFIX = "/1/60/0"

# Was die erfundene Anlage über ihre Menü-Ebenen meldet. Die Adressen stammen
# aus den Ebenen des Funktionstyps 9 in der Geräte-Datenbank, die Metadaten
# haben die Form, die jede Steuerung liefert.
MENUE_DATEN = {
    # Infoebene, nicht kuratiert: Verbrauchszähler
    f"{PRAEFIX}/20/87/0": {"writeProt": True, "unit": "l", "value": "310"},
    # Infoebene: Zählerstand
    f"{PRAEFIX}/20/61/0": {"writeProt": True, "unit": "h", "value": "142"},
    # Serviceebene, nicht kuratiert: Brennkammertemperatur
    f"{PRAEFIX}/0/45/0": {"writeProt": True, "unit": "°C", "value": "812"},
    # Werksebene
    f"{PRAEFIX}/12/101/0": {"writeProt": False, "unit": "%", "value": "17"},
}

# Adressen und die Bedienebene, in der die Geräte-Datenbank sie führt. Beide
# stehen **nicht** in der kuratierten Tabelle – sonst entstünden sie ohnehin.
INFO = f"{PRAEFIX}/20/87/0"
SERVICE = f"{PRAEFIX}/0/45/0"
WERK = f"{PRAEFIX}/12/101/0"


def _anlage(client_module, levels=("info", "operate")):
    c = client_module.WindhagerHttpClient("192.0.2.10", "geheim", levels=list(levels))
    # Struktur und Selbstauskunft der Steuerung, ohne Netz.
    c.geraeteinfo = {"device": "MB66xx", "version": "1.0"}
    c.werksbezeichnung = {"60": "BioWIN"}
    return c


async def _erkennen(client_module, monkeypatch, levels=("info", "operate"), menue=None):
    """Die Erkennung einmal vollständig laufen lassen."""
    c = _anlage(client_module, levels)

    async def fetch(url, semaphore=None):
        return [
            {
                "nodeId": 60,
                "neuronId": "0000BIOWIN01",
                "name": "BioWIN",
                "functions": [{"fctId": 0, "fctType": 9, "lock": False, "name": "BioWIN"}],
            }
        ]

    async def read_function_menus(prefix, fct_type):
        return dict(MENUE_DATEN if menue is None else menue)

    async def statische_adressen():
        return set()

    monkeypatch.setattr(c, "fetch", fetch)
    monkeypatch.setattr(c, "_read_function_menus", read_function_menus)
    monkeypatch.setattr(c, "_statische_adressen", statische_adressen)
    monkeypatch.setattr(c, "_lade_geraetetexte", keine_geraetetexte)
    await c._discover()
    return c


async def test_die_anlage_wird_ueberhaupt_erkannt(client_module, monkeypatch):
    """Ein Kessel ohne Beschreibungen wäre eine leere Integration."""
    c = await _erkennen(client_module, monkeypatch)
    assert c.devices
    assert {d["fct_type"] for d in c.devices} == {9}


async def test_die_kuratierte_tabelle_greift(client_module, monkeypatch):
    """Sie hat Vorrang vor dem, was die Menü-Ebenen hergeben."""
    from custom_components.heatnexus.const import BIOWIN_ENTITIES

    c = await _erkennen(client_module, monkeypatch)
    erkannt = {d["oid"] for d in c.devices}
    kuratiert = {f"{PRAEFIX}{e['oid']}" for e in BIOWIN_ENTITIES if not e.get("node_level")}
    fehlend = sorted(kuratiert - erkannt)
    assert fehlend == [], f"kuratierte Adressen fehlen: {fehlend}"


async def test_die_kennung_haengt_an_der_seriennummer(client_module, monkeypatch):
    """Sie übersteht einen Adresswechsel – die Adresse täte das nicht."""
    c = await _erkennen(client_module, monkeypatch)
    assert all(d["id"].startswith("0000BIOWIN01-") for d in c.devices)


async def test_die_gewaehlten_bedienebenen_entscheiden(client_module, monkeypatch):
    """Was erscheint, hängt an der Ebene, in der die Datenbank die Adresse führt.

    Mit Info und Betreiber steht die Abgastemperatur da, die Kesseltemperatur
    (Serviceebene) und der Werksparameter nicht. Wer die Ebenen dazuwählt,
    bekommt sie – sonst wäre die Auswahl wirkungslos.
    """
    schmal = await _erkennen(client_module, monkeypatch)
    erkannt = {d["oid"] for d in schmal.devices}
    assert INFO in erkannt
    assert SERVICE not in erkannt
    assert WERK not in erkannt

    breit = await _erkennen(
        client_module, monkeypatch, levels=("info", "operate", "service", "oem")
    )
    erkannt = {d["oid"] for d in breit.devices}
    assert SERVICE in erkannt
    assert WERK in erkannt


async def test_fachparameter_sind_vorab_abgeschaltet(client_module, monkeypatch):
    """Angelegt, aber deaktiviert: Sonst kostet jeder von ihnen eine Anfrage."""
    c = await _erkennen(client_module, monkeypatch, levels=("info", "operate", "service"))
    service = next(d for d in c.devices if d["oid"] == SERVICE)
    assert service.get("enabled_default") is False


async def test_ein_geraet_ohne_menues_bleibt_bedienbar(client_module, monkeypatch):
    """Ältere Firmware liefert keine Menüliste – dann trägt die Tabelle allein."""
    c = await _erkennen(client_module, monkeypatch, menue={})
    assert c.devices, "ohne Menü-Ebenen entstand keine einzige Beschreibung"


async def test_der_kessel_bekommt_kein_thermostat(client_module, monkeypatch):
    """Climate gehört an den Heizkreis, nicht an den Wärmeerzeuger."""
    c = await _erkennen(client_module, monkeypatch)
    assert "climate" not in {d["type"] for d in c.devices}


# ---------------------------------------------------------------------------
# Ein Knoten, der antwortet, ohne sich anzukündigen
# ---------------------------------------------------------------------------
# Die Metadaten stammen von einer echten BioWIN-2-Anlage, deren Kessel in
# `GET /1` ausschließlich seinen LON-Adressraum meldet – keine Funktion mit
# `fctType`. Bis dahin entstand für so einen Kessel keine einzige Entität.
# Adressen, Einheiten, Grenzen und Schreibschutz sind übernommen, die Werte
# ersetzt.
UNGEMELDET = json.loads(
    (Path(__file__).parent / "daten" / "biowin_ungemeldet.json").read_text(encoding="utf-8")
)


async def _erkennen_ungemeldet(client_module, monkeypatch, levels=("info", "operate")):
    """Erkennung an einem Knoten, der nur seinen LON-Adressraum meldet."""
    c = _anlage(client_module, levels)
    gelesen: list[str] = []

    async def fetch(url, semaphore=None):
        return [
            {
                "nodeId": 60,
                "neuronId": "0000BIOWIN01",
                "name": "BioWIN",
                "device": {"id": 1},
                # Genau das ist der Fall: nur die Netzwerkvariablen.
                "functions": [{"fctId": 32, "fctType": -1, "lock": False, "name": "NV's"}],
            }
        ]

    async def read_function_menus(prefix, fct_type):
        gelesen.append(prefix)
        return dict(UNGEMELDET["datenpunkte"]) if prefix == UNGEMELDET["praefix"] else {}

    async def statische_adressen():
        return set()

    async def get(url, semaphore=None):
        # Der LON-Adressraum ist hier nicht der Gegenstand: Geprüft wird, ob
        # der Kessel darunter gefunden wird. Er antwortet deshalb nicht.
        return None, 404

    monkeypatch.setattr(c, "fetch", fetch)
    monkeypatch.setattr(c, "_get", get)
    monkeypatch.setattr(c, "_read_function_menus", read_function_menus)
    monkeypatch.setattr(c, "_statische_adressen", statische_adressen)
    monkeypatch.setattr(c, "_lade_geraetetexte", keine_geraetetexte)
    await c._discover()
    return c, gelesen


async def test_ein_nicht_gemeldeter_kessel_wird_gefunden(client_module, monkeypatch):
    """Ohne diesen Griff bliebe die Anlage ein Kessel ohne einen einzigen Wert."""
    c, _ = await _erkennen_ungemeldet(client_module, monkeypatch)
    assert c.devices, "der Kessel blieb unsichtbar"
    assert {d["fct_type"] for d in c.devices} == {9}


async def test_der_typ_kommt_aus_den_datenpunkten(client_module, monkeypatch):
    """Die Struktur nennt keinen `fctType` – die Adressen sind kennzeichnend genug."""
    from custom_components.heatnexus.const import BIOWIN_ENTITIES

    c, _ = await _erkennen_ungemeldet(
        client_module, monkeypatch, levels=("info", "operate", "service", "oem")
    )
    erkannt = {d["oid"] for d in c.devices}
    kuratiert = {
        f"{UNGEMELDET['praefix']}{e['oid']}" for e in BIOWIN_ENTITIES if not e.get("node_level")
    }
    fehlend = sorted(kuratiert - erkannt)
    assert fehlend == [], f"kuratierte Adressen fehlen: {fehlend}"

    # Und die Ebenenzuordnung greift: `0/96` steht in keiner kuratierten
    # Tabelle, führt die Geräte-Datenbank aber als Infoebene des Typs 9. Ohne
    # aufgelösten Typ wäre die Adresse als Werksebene herausgefallen.
    assert f"{UNGEMELDET['praefix']}/0/96/0" in erkannt


async def test_die_funktion_wird_nur_einmal_gelesen(client_module, monkeypatch):
    """Der Typ stammt aus denselben Datenpunkten – ein zweiter Abruf wäre umsonst."""
    _, gelesen = await _erkennen_ungemeldet(client_module, monkeypatch)
    assert gelesen.count(UNGEMELDET["praefix"]) == 1


async def test_ein_knoten_mit_gemeldeter_funktion_wird_nicht_geraten(client_module, monkeypatch):
    """Wo die Struktur eine Funktion nennt, wird nichts dazuerfunden."""
    c = _anlage(client_module)
    gelesen: list[str] = []

    async def fetch(url, semaphore=None):
        return [
            {
                "nodeId": 60,
                "neuronId": "0000BIOWIN01",
                "name": "BioWIN",
                "functions": [
                    {"fctId": 0, "fctType": 9, "lock": False, "name": "BioWIN"},
                    {"fctId": 32, "fctType": -1, "lock": False, "name": "NV's"},
                ],
            }
        ]

    async def read_function_menus(prefix, fct_type):
        gelesen.append(prefix)
        return dict(MENUE_DATEN)

    async def statische_adressen():
        return set()

    async def get(url, semaphore=None):
        return None, 404

    monkeypatch.setattr(c, "fetch", fetch)
    monkeypatch.setattr(c, "_get", get)
    monkeypatch.setattr(c, "_read_function_menus", read_function_menus)
    monkeypatch.setattr(c, "_statische_adressen", statische_adressen)
    monkeypatch.setattr(c, "_lade_geraetetexte", keine_geraetetexte)
    await c._discover()

    assert gelesen == ["/1/60/0"], f"zusätzlich abgefragt: {gelesen}"
