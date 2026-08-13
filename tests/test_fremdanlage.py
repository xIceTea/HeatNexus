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

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


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
