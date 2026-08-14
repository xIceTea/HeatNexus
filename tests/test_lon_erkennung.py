"""Die Erkennung des LON-Adressraums.

Ein Knoten meldet neben seiner Funktion einen zweiten Bereich `NV's` ohne
Funktionstyp. Er fiel bisher durch den Filter der Erkennung – mitsamt dem
Bedienteil, das *nur* diesen Bereich hat. Was hier steht, hält den Weg fest,
den eine fremde Baureihe nimmt, für die es keine Adresstabelle gibt.

Die Antworten haben die Form, die eine BioWIN geliefert hat; Adresse und
Seriennummer sind erfunden.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

PRAEFIX_NV = "/1/60/32"
PRAEFIX_FKT = "/1/60/0"

# Drei Einträge, die zusammen die drei Fälle abdecken: kuratiert und ohne
# Entsprechung im OID-Raum, kuratiert mit Entsprechung, unbekannt.
NV_EINTRAEGE = [
    {"nvIndex": 28, "nvName": "PMX_eeBetrStd", "unit": "Std", "value": "14203", "typeId": 13},
    {"nvIndex": 7, "nvName": "WET_nvoTist", "unit": "°C", "value": "78.27", "typeId": 13},
    {"nvIndex": 3, "nvName": "nvoFileDirectory", "unit": "", "value": "16744", "typeId": 13},
]

# Der Kessel führt die Kesseltemperatur als gewöhnlichen Datenpunkt.
MENUE_DATEN = {f"{PRAEFIX_FKT}/0/7/0": {"writeProt": True, "unit": "°C", "value": "76.4"}}


async def keine_geraetetexte():
    from custom_components.heatnexus import geraetetexte

    return geraetetexte.Texte()


@pytest.fixture(scope="module")
def client_module():
    from custom_components.heatnexus import client

    return client


async def _erkennen(client_module, monkeypatch, nv_eintraege=None, oid_werte=None):
    c = client_module.WindhagerHttpClient(
        "192.0.2.10", "geheim", levels=["info", "operate"], lon=True
    )
    c.geraeteinfo = {"device": "MB66xx", "version": "1.0"}
    c.werksbezeichnung = {"60": "BioWIN"}

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

    async def get(url, semaphore=None):
        if url.endswith(f"lookup{PRAEFIX_NV}"):
            return [{"id": 0, "count": 3}], 200
        if f"lookup{PRAEFIX_NV}/0" in url:
            return list(NV_EINTRAEGE if nv_eintraege is None else nv_eintraege), 200
        return None, 404

    async def read_function_menus(prefix, fct_type):
        return dict(MENUE_DATEN)

    async def statische_adressen():
        return set()

    monkeypatch.setattr(c, "fetch", fetch)
    monkeypatch.setattr(c, "_get", get)
    monkeypatch.setattr(c, "_read_function_menus", read_function_menus)
    monkeypatch.setattr(c, "_statische_adressen", statische_adressen)
    monkeypatch.setattr(c, "_lade_geraetetexte", keine_geraetetexte)

    async def fetch_oids(oids):
        # Der Einzelabruf, mit dem die Erkennung prüft, ob ein Fühler hängt.
        return {o: (oid_werte or {}).get(o, "0.0") for o in oids}

    monkeypatch.setattr(c, "fetch_oids", fetch_oids)
    await c._discover()
    # Erst danach steht fest, welche Datenpunkte die Anlage wirklich führt –
    # und damit, welcher LON-Wert eine Entsprechung hat.
    await c._apply_metadata()
    return c


def _nv(c, nv_name: str) -> dict:
    return next(d for d in c.devices if d.get("nv_name") == nv_name)


async def test_netzwerkvariablen_werden_ueberhaupt_erkannt(client_module, monkeypatch):
    """Ohne diesen Weg fehlt der ganze Adressraum – und Knoten 90 mit ihm."""
    c = await _erkennen(client_module, monkeypatch)

    assert len([d for d in c.devices if d.get("nv_name")]) == 3


async def test_kuratierter_name_ersetzt_den_rohnamen(client_module, monkeypatch):
    c = await _erkennen(client_module, monkeypatch)

    eintrag = _nv(c, "PMX_eeBetrStd")
    assert eintrag["name"] == "Betriebsstunden"
    assert eintrag["enabled_default"] is True
    assert eintrag["oid"] == f"{PRAEFIX_NV}/0/28/0"


async def test_unbekannter_name_kommt_deaktiviert_mit_rohnamen(client_module, monkeypatch):
    """Nichts geht verloren, aber die Liste bleibt sauber."""
    c = await _erkennen(client_module, monkeypatch)

    eintrag = _nv(c, "nvoFileDirectory")
    assert eintrag["name"] == "nvoFileDirectory"
    assert eintrag["enabled_default"] is False


async def test_doppelter_begriff_bleibt_deaktiviert(client_module, monkeypatch):
    """Die Kesseltemperatur gibt es schon als Datenpunkt – einmal reicht."""
    c = await _erkennen(client_module, monkeypatch)

    assert _nv(c, "WET_nvoTist")["enabled_default"] is False


async def test_netzwerkvariablen_laufen_im_langsamen_takt(client_module, monkeypatch):
    """Ohne eigene Regel gälte eine LON-Temperatur als laufender Betriebswert.

    `_poll_klasse` stuft nach Typ und Name ein: „Temperatur" und „Pumpe"
    bedeuten dort den schnellen Takt, also 120 Anfragen je Stunde und Wert.
    Für die zweite Quelle wäre das verschwendet.
    """
    c = await _erkennen(client_module, monkeypatch)

    assert client_module.WindhagerHttpClient._poll_klasse(_nv(c, "WET_nvoTist")) == "slow"


async def test_bus_eingaenge_kommen_deaktiviert(client_module, monkeypatch):
    """`WET_nviTist` und `WET_nvoTist` standen im Abzug auf demselben Wert."""
    c = await _erkennen(
        client_module,
        monkeypatch,
        nv_eintraege=[
            {"nvIndex": 6, "nvName": "WET_nviTist", "unit": "°C", "value": "78.27", "typeId": 13},
            {"nvIndex": 28, "nvName": "PMX_eeBetrStd", "unit": "Std", "value": "14203"},
        ],
    )

    assert _nv(c, "WET_nviTist")["enabled_default"] is False
    assert _nv(c, "PMX_eeBetrStd")["enabled_default"] is True


async def test_ohne_fuehler_entsteht_keine_entitaet(client_module, monkeypatch):
    """Vier von siebzehn standen an der eigenen Anlage dauerhaft auf 327,67.

    Die Menü-Ebene sagt das nicht — sie liefert für Netzwerkvariablen keinen
    Wert. Erst der Einzelabruf zeigt, ob ein Fühler daranhängt.
    """
    c = await _erkennen(
        client_module,
        monkeypatch,
        nv_eintraege=[
            {"nvIndex": 22, "nvName": "WVF_nvoTPO", "unit": "°C", "value": "-"},
            {"nvIndex": 28, "nvName": "PMX_eeBetrStd", "unit": "Std", "value": "-"},
        ],
        oid_werte={
            f"{PRAEFIX_NV}/0/22/0": "327.67",
            f"{PRAEFIX_NV}/0/28/0": "14203",
        },
    )

    namen = [d["nv_name"] for d in c.devices if d.get("nv_name")]
    assert namen == ["PMX_eeBetrStd"]


async def test_verwaltung_des_bus_wird_nicht_angelegt(client_module, monkeypatch):
    """Ein Dateiverzeichnis ist kein Messwert, auch nicht deaktiviert."""
    c = await _erkennen(
        client_module,
        monkeypatch,
        nv_eintraege=[
            {
                "nvIndex": 3,
                "nvName": "nvoFileDirectory",
                "snvtName": "SNVT_address",
                "value": "16744",
            },
            {"nvIndex": 28, "nvName": "PMX_eeBetrStd", "unit": "Std", "value": "14203"},
        ],
    )

    assert [d["nv_name"] for d in c.devices if d.get("nv_name")] == ["PMX_eeBetrStd"]


async def test_der_typ_kommt_aus_dem_standard(client_module, monkeypatch):
    """Ohne Namen in der Tabelle trägt der LonMark-Typ die Größe.

    Genau das macht eine Baureihe erschließbar, die hier nie stand: Die
    Anlage nennt den Typ, auch wenn niemand den Namen kennt.
    """
    c = await _erkennen(
        client_module,
        monkeypatch,
        nv_eintraege=[
            # Unbenannt, ohne Einheit von der Anlage – der Typ sagt beides.
            {"nvIndex": 41, "nvName": "RUE_cntError", "snvtName": "SNVT_count", "value": "3"},
            {"nvIndex": 9, "nvName": "FA_nvoTk", "snvtName": "SNVT_temp_p", "value": "44.5"},
        ],
    )

    zaehler = _nv(c, "RUE_cntError")
    assert zaehler["state_class"] == "total_increasing"
    # Ohne den Typ wäre das ein Zahlensensor ohne Geräteklasse gewesen; die
    # Anlage nennt für diesen Eintrag keine Einheit.
    assert _nv(c, "FA_nvoTk")["type"] == "temperature"


async def test_zustandsbericht_bleibt_als_diagnose(client_module, monkeypatch):
    """Das Bedienteil trägt nur ihn – ohne ihn verschwände auch das Gerät."""
    c = await _erkennen(
        client_module,
        monkeypatch,
        nv_eintraege=[
            {"nvIndex": 3, "nvName": "nvoStatus", "snvtName": "SNVT_obj_status", "value": "0"}
        ],
    )

    bericht = _nv(c, "nvoStatus")
    assert bericht["category"] == "diagnostic"
    assert bericht["enabled_default"] is False


async def test_herkunft_steht_am_deskriptor(client_module, monkeypatch):
    """Die Diagnose zählt nach Ebene – ohne eigene stünden sie unter `null`.

    Und eine der vorhandenen Ebenen zu behaupten wäre falsch: Der
    LON-Adressraum ist keine Bedienebene der Anlage.
    """
    c = await _erkennen(client_module, monkeypatch)

    assert {d["level"] for d in c.devices if d.get("nv_name")} == {"lon"}


async def test_netzwerkvariablen_werden_nie_geschrieben(client_module, monkeypatch):
    """`nvi`-Variablen sind Eingänge der Regelung zwischen den Knoten."""
    c = await _erkennen(client_module, monkeypatch)

    assert all(d["write_prot"] is True for d in c.devices if d.get("nv_name"))


async def test_kennung_wird_nicht_als_datenpunktadresse_gelesen(client_module, monkeypatch):
    """Aus `…-32-0-7-0` würde sonst `0/7` – eine Adresse, die hier nichts meint.

    Der Begriff kommt bei Netzwerkvariablen aus dem Namen, nicht aus der
    Adresse. Beides zusammen wäre gefährlich: Der Index einer Variablen sähe
    aus wie eine Datenpunktadresse und träfe zufällig einen fremden Begriff.
    """
    from custom_components.heatnexus.kanonisch import gnmn, schluessel

    c = await _erkennen(client_module, monkeypatch)
    kennung = _nv(c, "WET_nvoTist")["id"]

    assert gnmn(kennung) is None
    # Über den Namen dagegen trägt der Begriff – dafür ist er da.
    assert schluessel(kennung) == "boiler_temperature"


async def test_werte_eines_kessels_haengen_an_seinem_geraet(client_module, monkeypatch):
    """Sonst stünde neben dem Kessel ein zweites Gerät namens „NV's"."""
    c = await _erkennen(client_module, monkeypatch)

    kessel = next(d for d in c.devices if d.get("oid") == f"{PRAEFIX_FKT}/0/7/0")
    assert _nv(c, "PMX_eeBetrStd")["device_id"] == kessel["device_id"]


async def test_knoten_ohne_funktion_wird_zum_bedienteil(client_module, monkeypatch):
    """Das Bedienteil meldet nur seinen LON-Adressraum – sonst gäbe es es nicht."""
    c = client_module.WindhagerHttpClient(
        "192.0.2.10", "geheim", levels=["info", "operate"], lon=True
    )
    c.geraeteinfo = {"device": "MB66xx", "version": "1.0"}
    c.werksbezeichnung = {"90": "MB6611 LOP"}

    async def fetch(url, semaphore=None):
        return [
            {
                "nodeId": 90,
                "neuronId": "0000BEDIEN01",
                "name": "n.a.",
                "functions": [{"fctId": 32, "fctType": -1, "lock": False, "name": "NV's"}],
            }
        ]

    async def get(url, semaphore=None):
        if url.endswith("lookup/1/90/32"):
            return [{"id": 0, "count": 1}], 200
        if "lookup/1/90/32/0" in url:
            return [{"nvIndex": 3, "nvName": "nvoStatus", "unit": "", "value": "0"}], 200
        return None, 404

    async def read_function_menus(prefix, fct_type):
        return {}

    async def statische_adressen():
        return set()

    monkeypatch.setattr(c, "fetch", fetch)
    monkeypatch.setattr(c, "_get", get)
    monkeypatch.setattr(c, "_read_function_menus", read_function_menus)
    monkeypatch.setattr(c, "_statische_adressen", statische_adressen)
    monkeypatch.setattr(c, "_lade_geraetetexte", keine_geraetetexte)
    await c._discover()

    bedienteil = _nv(c, "nvoStatus")
    assert bedienteil["device_name"] == "MB6611 LOP"
    assert bedienteil["device_id"] == c._geraetekennung("/1/90/32")


async def test_alle_deskriptoren_haben_dieselbe_form(client_module, monkeypatch):
    """Kuratierte Tabelle, Menü-Erkennung und LON bauen dieselbe Beschreibung.

    Sie liefen auseinander: Die eine Stelle führte `level` und
    `enabled_default`, die andere nicht — und wer ein Feld hinzufügte, musste
    an drei Stellen daran denken.
    """
    from custom_components.heatnexus.client import DESKRIPTOR_VORGABE

    c = await _erkennen(client_module, monkeypatch)
    datenpunkte = [d for d in c.devices if d.get("oid") and d["type"] != "climate"]

    assert datenpunkte
    for d in datenpunkte:
        fehlend = set(DESKRIPTOR_VORGABE) - set(d)
        assert fehlend == set(), f"{d['name']}: {sorted(fehlend)}"


async def test_der_kurzdurchlauf_liest_keine_netzwerkvariablen(client_module, monkeypatch):
    """Die Einrichtung darf davon nicht länger werden."""
    c = client_module.WindhagerHttpClient("192.0.2.10", "geheim", levels=["info"], lon=True)
    c.geraeteinfo = {"device": "MB66xx", "version": "1.0"}
    c.werksbezeichnung = {"60": "BioWIN"}
    gefragt = []

    async def fetch(url, semaphore=None):
        return [
            {
                "nodeId": 60,
                "neuronId": "0000BIOWIN01",
                "name": "BioWIN",
                "functions": [{"fctId": 32, "fctType": -1, "lock": False, "name": "NV's"}],
            }
        ]

    async def get(url, semaphore=None):
        gefragt.append(url)
        return None, 404

    monkeypatch.setattr(c, "fetch", fetch)
    monkeypatch.setattr(c, "_get", get)
    monkeypatch.setattr(c, "_lade_geraetetexte", keine_geraetetexte)
    await c._discover(nur_kern=True)

    assert not [u for u in gefragt if PRAEFIX_NV in u]
