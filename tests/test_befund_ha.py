"""Befund in Home Assistant: sammelt ohne Automatik, speichert je Anlage, liefert den Stand."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

PREFIX = "/1/15/0"
KESSEL = "/1/15/1"
HEIZKREIS = "SN1-2-0"


class Coordinator:
    label = "Anlage A"
    host = "192.0.2.10"
    client = SimpleNamespace(steuerung_kennung=lambda: "steuerung-SN1")

    def __init__(self) -> None:
        """Ein Heizkreis und ein Kessel mit Zählern."""
        self.data = {
            "devices": [
                {
                    "type": "climate",
                    "id": f"{HEIZKREIS}-thermostat",
                    "device_id": HEIZKREIS,
                    "prefix": PREFIX,
                    "device_name": "Heizkreis",
                },
                {
                    "type": "sensor",
                    "id": "SN1-1-0-2-80-0",
                    "device_id": "SN1-1-0",
                    "oid": f"{KESSEL}/2/80/0",
                },
            ],
            "oids": {
                f"{PREFIX}/0/0/0": "8.5",
                f"{PREFIX}/1/2/0": "45.0",
                f"{PREFIX}/0/2/0": "44.0",
                f"{PREFIX}/1/1/0": "21.0",
                f"{PREFIX}/2/10/0": "0",
                f"{PREFIX}/3/21/0": "18.0",
                f"{KESSEL}/2/80/0": "6585",
                f"{KESSEL}/2/81/0": "18201",
                f"{KESSEL}/0/9/0": "50",
                f"{KESSEL}/11/2/0": "40",
            },
        }

    def async_add_listener(self, _rueckruf):
        return lambda: None


@pytest.fixture
async def anlage(hass):
    from homeassistant.config_entries import ConfigEntryState
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.befund.laufzeit import befund_holen
    from custom_components.heatnexus.const import DOMAIN

    eintrag = MockConfigEntry(domain=DOMAIN, state=ConfigEntryState.LOADED)
    eintrag.add_to_hass(hass)
    eintrag.runtime_data = {"coordinators": {"192.0.2.10": Coordinator()}}
    verwaltung = befund_holen(hass)
    await verwaltung.eintrag_starten(eintrag)
    yield verwaltung, eintrag
    await verwaltung.eintrag_stoppen(eintrag)


async def test_sammelt_ohne_automatik_und_liefert_stand(hass, anlage):
    from homeassistant.util import dt as dt_util

    verwaltung, _ = anlage
    anlage_id = verwaltung.anlagen()[0]
    sammler = verwaltung.sammler[anlage_id]
    jetzt = dt_util.now().replace(minute=0, second=0, microsecond=0)
    for m in range(0, 65, 5):
        await sammler.messen(jetzt + timedelta(minutes=m))
    stunde = sammler.archiv.stunden(HEIZKREIS)[0]
    assert stunde["at"] == 8.5
    assert stunde["eingriff"] is False
    stand = verwaltung.stand(anlage_id)
    assert [a["art"] for a in stand["abschnitte"]] == ["haus", "heizkreis", "kessel"]
    kessel = stand["abschnitte"][2]["befunde"][0]
    assert kessel["angaben"]["gesamt_h_je_start"] == pytest.approx(2.76, abs=0.01)


async def test_kesselleistung_in_kw(hass, anlage):
    from homeassistant.util import dt as dt_util

    verwaltung, _ = anlage
    sammler = next(iter(verwaltung.sammler.values()))
    jetzt = dt_util.now().replace(minute=0, second=0, microsecond=0)
    await sammler.messen(jetzt)
    await sammler.messen(jetzt + timedelta(hours=1))
    stunde = next(iter(sammler.archiv.stunden_k[KESSEL].values()))
    assert stunde["kwh"] == pytest.approx(20.0)


async def test_nachrechnen_ohne_recorder_ist_leer(hass, anlage):
    verwaltung, _ = anlage
    sammler = next(iter(verwaltung.sammler.values()))
    assert await sammler.nachrechnen() == 0


async def test_stoppen_speichert_und_entfernt(hass, anlage):
    verwaltung, eintrag = anlage
    await verwaltung.eintrag_stoppen(eintrag)
    assert verwaltung.anlagen() == []


async def test_websocket_liefert_anlagen(hass, hass_ws_client, anlage):
    from custom_components.heatnexus.befund.websocket import async_register_befund

    async_register_befund(hass)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "heatnexus/befund"})
    antwort = await client.receive_json()
    assert antwort["success"]
    stand = next(iter(antwort["result"]["anlagen"].values()))
    assert {"lage", "abschnitte", "anlage", "stand"} <= set(stand)


async def test_entfernen_verwirft_das_archiv(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.befund.laufzeit import eintrag_entfernt, speicher
    from custom_components.heatnexus.const import DOMAIN

    eintrag = MockConfigEntry(domain=DOMAIN, data={"systems": [{"host": "192.0.2.10"}]})
    await speicher(hass, eintrag.entry_id, "192.0.2.10").async_save({"fassung": 1})
    await eintrag_entfernt(hass, eintrag)
    assert await speicher(hass, eintrag.entry_id, "192.0.2.10").async_load() is None


async def test_sensoren_je_heizkreis_und_kessel(hass, anlage):
    from custom_components.heatnexus.befund.entitaeten import anmelden

    _, eintrag = anlage
    angelegt = []
    anmelden(hass, eintrag, angelegt.extend)
    kennungen = sorted(s.unique_id for s in angelegt)
    assert kennungen == sorted(
        [
            f"{HEIZKREIS}-befund-{art}"
            for art in ("waermespeicher", "heizgrenze", "raeume", "naechte", "vorlauf")
        ]
        + [f"SN1-1-0-befund-{art}" for art in ("laufzeit", "starts", "energie")]
    )
    for sensor in angelegt:
        sensor.hass = hass
        assert sensor.extra_state_attributes["status"] is not None, sensor.unique_id


async def test_ein_spaeter_bekannter_kessel_bekommt_seine_sensoren(hass, anlage):
    from homeassistant.helpers.dispatcher import async_dispatcher_send

    from custom_components.heatnexus.befund.entitaeten import anmelden
    from custom_components.heatnexus.const import SIGNAL_NEUE_ENTITAETEN

    _, eintrag = anlage
    koordinator = eintrag.runtime_data["coordinators"]["192.0.2.10"]
    kessel = koordinator.data["devices"].pop()
    angelegt = []
    anmelden(hass, eintrag, angelegt.extend)
    assert not any("SN1-1-0-befund" in s.unique_id for s in angelegt)

    koordinator.data["devices"].append(kessel)
    async_dispatcher_send(hass, SIGNAL_NEUE_ENTITAETEN.format(eintrag.entry_id))
    assert "SN1-1-0-befund-starts" in {s.unique_id for s in angelegt}


async def test_befund_sensoren_gelten_nicht_als_verwaist(hass, anlage):
    from custom_components.heatnexus import verwaiste

    _, eintrag = anlage
    bekannt = verwaiste.bekannte_kennungen(eintrag, eintrag.runtime_data["coordinators"])
    assert bekannt[f"{HEIZKREIS}-befund-heizgrenze"] is True
    assert bekannt["SN1-1-0-befund-energie"] is True


async def test_hinweis_erscheint_in_der_seitenleiste_wenn_gewuenscht(hass, anlage, monkeypatch):
    from homeassistant.components import persistent_notification

    from custom_components.heatnexus.automatik.verwaltung import Verwaltung

    verwaltung, _ = anlage
    sammler = next(iter(verwaltung.sammler.values()))
    hinweis = {"art": "raeume", "status": "hinweis"}
    sammler.letzter = {"abschnitte": [{"kennung": HEIZKREIS, "befunde": [hinweis]}]}
    gewuenscht = {"befund_melden": False}
    monkeypatch.setattr(Verwaltung, "konfig", lambda _self, _kreis: gewuenscht)

    sammler.melden()
    assert persistent_notification._async_get_or_create_notifications(hass) == {}
    gewuenscht["befund_melden"] = True
    sammler.melden()
    meldungen = persistent_notification._async_get_or_create_notifications(hass)
    assert list(meldungen) == [f"heatnexus_befund_{HEIZKREIS}"]
    hinweis["status"] = "unauffaellig"
    sammler.melden()
    assert persistent_notification._async_get_or_create_notifications(hass) == {}


def purowin_zaehler(sammler, rest="140"):
    """Die Fixture-Anlage bekommt am Kessel einen PuroWIN-Restzähler für die Hauptreinigung."""
    daten = sammler.coordinator.data
    daten["devices"].append(
        {
            "type": "sensor",
            "id": "SN1-1-1-39-92-0",
            "device_id": "SN1-1-0",
            "prefix": KESSEL,
            "oid": f"{KESSEL}/39/92/0",
            "fct_type": 25,
            "device_name": "PuroWIN",
        }
    )
    daten["oids"][f"{KESSEL}/39/92/0"] = rest


async def test_pflege_wird_fortgeschrieben_und_erscheint(hass, anlage):
    """Ein Restwert im Takt landet im Archiv und als Abschnitt der Auswertung."""
    from datetime import date

    from custom_components.heatnexus.befund import pflegelauf

    verwaltung, _ = anlage
    sammler = next(iter(verwaltung.sammler.values()))
    purowin_zaehler(sammler)
    pflegelauf.messen(sammler.coordinator, sammler.archiv, date(2026, 11, 20))
    assert sammler.archiv.pflege_eintrag(KESSEL, "hauptreinigung")["rest"] == 140.0
    assert any(a["art"] == "pflege" for a in sammler.stand()["abschnitte"])


async def test_pflege_entitaeten_gelten_nicht_als_verwaist(hass, anlage):
    from custom_components.heatnexus import verwaiste

    verwaltung, eintrag = anlage
    purowin_zaehler(next(iter(verwaltung.sammler.values())))
    domaenen = verwaiste.erwartete_domaenen(eintrag, eintrag.runtime_data["coordinators"])
    assert domaenen["SN1-1-0-befund-pflege-hauptreinigung"] == "sensor"
    assert domaenen["SN1-1-0-pflege-hauptreinigung-zuletzt"] == "date"


def logwin(sammler):
    """Die Fixture-Anlage bekommt einen LogWIN (Funktionstyp 10, Geräteklasse 2009)."""
    sammler.coordinator.data["devices"].append(
        {
            "type": "sensor",
            "id": "SN1-65-0-0-11-0",
            "device_id": "SN1-65-0",
            "prefix": "/1/65/0",
            "oid": "/1/65/0/0/11/0",
            "fct_type": 10,
            "device_name": "LogWIN",
        }
    )
    sammler.coordinator.client = SimpleNamespace(
        steuerung_kennung=lambda: "steuerung-SN1", geraeteklasse={"65": "2009"}
    )


async def test_logwin_taste_traegt_heute_ein(hass, anlage):
    """Am LogWIN entstehen Termin, Datum und Taste; die Taste trägt heute ein."""
    from homeassistant.util import dt as dt_util

    from custom_components.heatnexus.befund import pflege_entitaeten as pe

    verwaltung, eintrag = anlage
    sammler = next(iter(verwaltung.sammler.values()))
    logwin(sammler)
    tasten, daten, termine = [], [], []
    pe.anmelden_taste(hass, eintrag, tasten.extend)
    pe.anmelden_datum(hass, eintrag, daten.extend)
    pe.anmelden_sensor(hass, eintrag, termine.extend)
    assert {t.unique_id for t in tasten} == {
        "SN1-65-0-pflege-asche-erledigt",
        "SN1-65-0-pflege-jahresreinigung-erledigt",
    }
    asche = next(t for t in tasten if "asche" in t.unique_id)
    asche.hass = hass
    await asche.async_press()
    datum = next(d for d in daten if d.unique_id == "SN1-65-0-pflege-asche-zuletzt")
    datum.hass = hass
    assert datum.native_value == dt_util.now().date()
    termin = next(s for s in termine if s.unique_id == "SN1-65-0-befund-pflege-asche")
    termin.hass = hass
    assert termin.native_value is not None


async def test_purowin_bekommt_keine_taste(hass, anlage):
    from custom_components.heatnexus.befund import pflege_entitaeten as pe

    verwaltung, eintrag = anlage
    purowin_zaehler(next(iter(verwaltung.sammler.values())))
    tasten = []
    pe.anmelden_taste(hass, eintrag, tasten.extend)
    assert tasten == []


def purowin_abgas(sammler, phase="8"):
    """Die Fixture-Anlage bekommt am Kessel Abgas, Phase und O2 einer PuroWIN."""
    daten = sammler.coordinator.data
    for gnmn in ("0/11", "0/42"):
        daten["devices"].append(
            {
                "type": "sensor",
                "id": f"SN1-1-1-{gnmn.replace('/', '-')}-0",
                "device_id": "SN1-1-0",
                "oid": f"{KESSEL}/{gnmn}/0",
                "fct_type": 25,
                "device_name": "PuroWIN",
            }
        )
    daten["oids"] |= {
        f"{KESSEL}/0/11/0": "120",
        f"{KESSEL}/0/7/0": "70",
        f"{KESSEL}/2/1/0": phase,
        f"{KESSEL}/0/42/0": "7",
    }


async def test_abgas_sammelt_im_ruhigen_betrieb(hass, anlage):
    """Nach 15 Minuten Modulation landet je Takt eine Messung in den Tagessummen."""
    from homeassistant.util import dt as dt_util

    verwaltung, _ = anlage
    sammler = next(iter(verwaltung.sammler.values()))
    purowin_abgas(sammler)
    jetzt = dt_util.now().replace(minute=0, second=0, microsecond=0)
    for minute in range(0, 25, 5):
        await sammler.messen(jetzt + timedelta(minutes=minute))
    tage = sammler.archiv.abgas_tage(KESSEL)
    summe = next(iter(tage.values()))["50"]
    assert summe[1] == 2
    assert summe[0] == 100.0
    teil = next(a for a in sammler.stand()["abschnitte"] if a["art"] == "abgas")
    assert [b["art"] for b in teil["befunde"]] == ["abgas", "abgasverlust"]


async def test_abgas_sensoren_entstehen(hass, anlage):
    from custom_components.heatnexus.befund.entitaeten import anmelden

    verwaltung, eintrag = anlage
    purowin_abgas(next(iter(verwaltung.sammler.values())))
    angelegt = []
    anmelden(hass, eintrag, angelegt.extend)
    kennungen = {s.unique_id for s in angelegt}
    assert {"SN1-1-0-befund-abgas", "SN1-1-0-befund-abgasverlust"} <= kennungen


async def test_brennstoff_vorrat_lieferung_und_reichweite(hass, anlage):
    """Vorrat setzen, Lieferung mit Rest eintragen; die Reichweite folgt aus dem Verbrauch."""
    from datetime import date, timedelta

    from custom_components.heatnexus.befund import brennstoff_entitaeten as be

    verwaltung, eintrag = anlage
    sammler = next(iter(verwaltung.sammler.values()))
    purowin_abgas(sammler)
    heute = date.today()
    sammler.archiv.tage_k[KESSEL] = {
        (heute - timedelta(days=i)).isoformat(): {"kwh": 120.0} for i in range(1, 15)
    }
    zahlen, sensoren = [], []
    be.anmelden_number(hass, eintrag, zahlen.extend)
    be.anmelden_sensor(hass, eintrag, sensoren.extend)
    assert {z.unique_id for z in zahlen} == {
        "SN1-1-0-brennstoffvorrat",
        "SN1-1-0-brennstoff-heizwert",
    }
    vorrat = next(z for z in zahlen if z.unique_id.endswith("vorrat"))
    vorrat.hass = hass
    await vorrat.async_set_native_value(10.0)
    assert vorrat.native_unit_of_measurement == "Srm"
    assert vorrat.native_value == 10.0
    reichweite = sensoren[0]
    reichweite.hass = hass
    assert reichweite.native_value == heute + timedelta(days=56)
    await vorrat.async_geliefert(menge=20.0, rest=5.0)
    assert vorrat.native_value == 25.0


async def test_brennstoff_entitaeten_gelten_nicht_als_verwaist(hass, anlage):
    from custom_components.heatnexus import verwaiste

    verwaltung, eintrag = anlage
    purowin_abgas(next(iter(verwaltung.sammler.values())))
    domaenen = verwaiste.erwartete_domaenen(eintrag, eintrag.runtime_data["coordinators"])
    assert domaenen["SN1-1-0-brennstoffvorrat"] == "number"
    assert domaenen["SN1-1-0-befund-brennstoff"] == "sensor"
