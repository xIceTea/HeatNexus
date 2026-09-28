"""Automatik in Home Assistant: Einrichten, Beobachten, Schalten, Rechte.

Die Anlage ist eine Attrappe; geprüft wird, was an ihren Client geschrieben
wird und was nicht.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

PREFIX = "/1/15/0"
HEIZKREIS = "SN1-2-0"
ANLAGE = "Anlage A"
# 08:00 in der Zeitzone der Testumgebung; erst nach der Anmeldung setzen, sonst gilt das Token nicht.
MORGEN = "2026-09-27 15:00:00+00:00"


class Client:
    def __init__(self) -> None:
        """Merkt sich jeden Schreibvorgang; mit `ablehnen` scheitert jeder."""
        self.geschrieben: list[tuple[str, str]] = []
        self.ablehnen = False

    async def update(self, oid: str, wert: str) -> None:
        if self.ablehnen:
            raise RuntimeError("abgelehnt")
        self.geschrieben.append((oid, wert))

    def register_poll_oid(self, oid: str) -> None:
        pass

    def unregister_poll_oid(self, oid: str) -> None:
        pass


class Coordinator:
    label = ANLAGE

    def __init__(self) -> None:
        """Ein Heizkreis mit Sollwert 21 °C in Programm 1."""
        self.client = Client()
        self.data = {
            "devices": [
                {
                    "type": "climate",
                    "id": f"{HEIZKREIS}-thermostat",
                    "device_id": HEIZKREIS,
                    "prefix": PREFIX,
                    "device_name": "Heizkreis",
                    "preset_allowed": [0, 1, 2, 3, 4, 5, 6, 7],
                }
            ],
            "oids": {
                f"{PREFIX}/1/1/0": "21.0",
                f"{PREFIX}/3/50/0": "1",
                f"{PREFIX}/2/10/0": "0",
                f"{PREFIX}/0/0/0": "12.0",
                f"{PREFIX}/2/9/0": "1",
                f"{PREFIX}/3/21/0": "18.0",
                f"{PREFIX}/3/2/0": "5.0",
            },
        }

    def async_add_listener(self, _rueckruf):
        return lambda: None


@pytest.fixture
async def anlage(hass):
    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.core import SupportsResponse
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.automatik.verwaltung import verwaltung_holen
    from custom_components.heatnexus.automatik.websocket import async_register_automatik
    from custom_components.heatnexus.const import DOMAIN

    hass.states.async_set("sensor.wohnzimmer", "21.4", {"device_class": "temperature"})
    hass.states.async_set("weather.home", "sunny")

    async def prognose(call):
        heute = dt_util.now().replace(minute=0, second=0, microsecond=0)
        if call.data["type"] == "hourly":
            stunden = [heute.replace(hour=h) for h in range(24)]
            eintraege = [{"datetime": s.isoformat(), "cloud_coverage": 10} for s in stunden]
        else:
            eintraege = [{"datetime": heute.isoformat(), "temperature": 14, "templow": 6}]
        return {"weather.home": {"forecast": eintraege}}

    hass.services.async_register(
        "weather", "get_forecasts", prognose, supports_response=SupportsResponse.ONLY
    )
    eintrag = MockConfigEntry(domain=DOMAIN, state=ConfigEntryState.LOADED)
    eintrag.add_to_hass(hass)
    from homeassistant.helpers import entity_registry as er

    er.async_get(hass).async_get_or_create(
        "climate", DOMAIN, f"{HEIZKREIS}-thermostat", config_entry=eintrag
    )
    coordinator = Coordinator()
    eintrag.runtime_data = {"coordinators": {"192.0.2.10": coordinator}}
    async_register_automatik(hass)
    verwaltung = verwaltung_holen(hass)
    await verwaltung.eintrag_starten(eintrag)
    yield verwaltung, coordinator
    await verwaltung.eintrag_stoppen(eintrag)


async def _senden(client, **nachricht) -> dict:
    await client.send_json_auto_id(nachricht)
    return await client.receive_json()


async def _einrichten(client) -> dict:
    return await _senden(
        client,
        type="heatnexus/automatik/einrichten",
        heizkreis=HEIZKREIS,
        heizflaechen="gemischt",
        raeume=["sensor.wohnzimmer"],
        wetter="weather.home",
    )


async def _schalten(client) -> None:
    antwort = await _senden(
        client, type="heatnexus/automatik/einstellen", heizkreis=HEIZKREIS, modus="schalten"
    )
    assert antwort["success"], antwort


async def test_einrichten_startet_im_beobachtungsmodus(hass, hass_ws_client, anlage, freezer):
    verwaltung, coordinator = anlage
    client = await hass_ws_client(hass)
    freezer.move_to(MORGEN)

    antwort = await _einrichten(client)

    assert antwort["success"], antwort
    assert antwort["result"]["modus"] == "beobachten"
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    await laufzeit.auswerten(entscheidungszeit=True)
    assert coordinator.client.geschrieben == []
    assert laufzeit.steller.stand.protokoll[0]["art"] == "haette"


async def test_lesen_zeigt_den_heizkreis(hass, hass_ws_client, anlage):
    client = await hass_ws_client(hass)
    await _einrichten(client)

    antwort = await _senden(client, type="heatnexus/automatik")

    assert antwort["success"], antwort
    (kreis,) = antwort["result"]["heizkreise"]
    assert kreis["eingerichtet"] is True
    assert kreis["anlage"] == ANLAGE
    assert kreis["kennwerte"]["raum"] == 21.4
    assert kreis["kennwerte"]["eigene_ziele"] is False
    assert kreis["kennwerte"]["raum_bezug"] == 21.0
    assert antwort["result"]["darf_aendern"] is True


async def test_schalten_schreibt_zur_entscheidungszeit(hass, hass_ws_client, anlage, freezer):
    verwaltung, coordinator = anlage
    client = await hass_ws_client(hass)
    freezer.move_to(MORGEN)
    await _einrichten(client)
    await _schalten(client)

    await verwaltung.laufzeiten[HEIZKREIS].auswerten(entscheidungszeit=True)

    assert coordinator.client.geschrieben == [
        (f"{PREFIX}/3/4/0", "19.5"),
        (f"{PREFIX}/2/10/0", "400"),
    ]


async def test_ausschalten_nimmt_die_absenkung_zurueck(hass, hass_ws_client, anlage, freezer):
    verwaltung, coordinator = anlage
    client = await hass_ws_client(hass)
    freezer.move_to(MORGEN)
    await _einrichten(client)
    await _schalten(client)
    await verwaltung.laufzeiten[HEIZKREIS].auswerten(entscheidungszeit=True)

    await _senden(client, type="heatnexus/automatik/einstellen", heizkreis=HEIZKREIS, aktiv=False)

    assert coordinator.client.geschrieben[-1] == (f"{PREFIX}/2/10/0", "0")


async def test_ausschalten_nimmt_trotz_sperre_zurueck(hass, hass_ws_client, anlage, freezer):
    from dataclasses import replace
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    verwaltung, coordinator = anlage
    client = await hass_ws_client(hass)
    freezer.move_to(MORGEN)
    await _einrichten(client)
    await _schalten(client)
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    await laufzeit.auswerten(entscheidungszeit=True)
    bis = (dt_util.now() + timedelta(hours=1)).isoformat()
    laufzeit.steller.stand = replace(laufzeit.steller.stand, gesperrt_bis=bis)

    await _senden(client, type="heatnexus/automatik/einstellen", heizkreis=HEIZKREIS, aktiv=False)

    assert coordinator.client.geschrieben[-1] == (f"{PREFIX}/2/10/0", "0")


async def test_abgelehnte_ruecknahme_meldet_sich(hass, hass_ws_client, anlage, freezer):
    from homeassistant.helpers import issue_registry as ir

    from custom_components.heatnexus.const import DOMAIN

    verwaltung, coordinator = anlage
    client = await hass_ws_client(hass)
    freezer.move_to(MORGEN)
    await _einrichten(client)
    await _schalten(client)
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    await laufzeit.auswerten(entscheidungszeit=True)
    coordinator.client.ablehnen = True

    await _senden(client, type="heatnexus/automatik/einstellen", heizkreis=HEIZKREIS, aktiv=False)

    kennung = f"automatik_ruecknahme_{HEIZKREIS}"
    assert ir.async_get(hass).async_get_issue(DOMAIN, kennung) is not None
    assert laufzeit.gedaechtnis.absenkung_art is not None


async def test_wiedereinschalten_behaelt_die_nicht_zurueckgenommene_absenkung(
    hass, hass_ws_client, anlage, freezer
):
    verwaltung, coordinator = anlage
    client = await hass_ws_client(hass)
    freezer.move_to(MORGEN)
    await _einrichten(client)
    await _schalten(client)
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    await laufzeit.auswerten(entscheidungszeit=True)
    coordinator.client.ablehnen = True
    await _senden(client, type="heatnexus/automatik/einstellen", heizkreis=HEIZKREIS, aktiv=False)
    coordinator.client.ablehnen = False

    await _senden(client, type="heatnexus/automatik/einstellen", heizkreis=HEIZKREIS, aktiv=True)

    assert laufzeit.gedaechtnis.absenkung_art is not None


async def test_sicherheit_meldet_sich_erst_nach_der_wiederholung(
    hass, hass_ws_client, anlage, freezer
):
    from homeassistant.helpers import issue_registry as ir

    from custom_components.heatnexus.automatik import regel
    from custom_components.heatnexus.const import DOMAIN

    verwaltung, coordinator = anlage
    client = await hass_ws_client(hass)
    freezer.move_to(MORGEN)
    await _einrichten(client)
    await _schalten(client)
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    laufzeit.gedaechtnis = regel.Gedaechtnis(saison=regel.NUR_WW, saison_soll=21.0)
    coordinator.data["oids"][f"{PREFIX}/3/50/0"] = "6"
    hass.states.async_set("sensor.wohnzimmer", "15.0", {"device_class": "temperature"})
    coordinator.client.ablehnen = True

    await laufzeit.auswerten()
    await laufzeit.auswerten()

    kennung = f"automatik_sicherheit_{HEIZKREIS}"
    assert ir.async_get(hass).async_get_issue(DOMAIN, kennung) is None


async def test_nur_administratoren_richten_ein(
    hass, hass_ws_client, hass_read_only_access_token, anlage
):
    client = await hass_ws_client(hass, hass_read_only_access_token)

    antwort = await _einrichten(client)

    assert not antwort["success"]
    assert antwort["error"]["code"] == "unauthorized"


async def test_unbekannter_heizkreis_wird_abgewiesen(hass, hass_ws_client, anlage):
    client = await hass_ws_client(hass)

    antwort = await _senden(
        client,
        type="heatnexus/automatik/einrichten",
        heizkreis="gibt-es-nicht",
        raeume=["sensor.wohnzimmer"],
        wetter="weather.home",
    )

    assert not antwort["success"]


async def test_entfernen_raeumt_ab(hass, hass_ws_client, anlage):
    verwaltung, _ = anlage
    client = await hass_ws_client(hass)
    await _einrichten(client)

    antwort = await _senden(client, type="heatnexus/automatik/entfernen", heizkreis=HEIZKREIS)

    assert antwort["success"], antwort
    assert HEIZKREIS not in verwaltung.laufzeiten
    assert verwaltung.konfig(HEIZKREIS) is None


async def test_gedaempfte_at_beginnt_beim_tagesmittel(hass, hass_ws_client, anlage):
    """Nachmittags läge der Messwert weit über dem Mittel des Tages."""
    verwaltung, _ = anlage
    client = await hass_ws_client(hass)
    await _einrichten(client)

    stufen = verwaltung.laufzeiten[HEIZKREIS].stufen

    assert stufen is not None
    assert stufen[1] == pytest.approx(10.0, abs=0.1)  # (14 + 6) / 2 aus der Tagesprognose


async def test_einrichtung_laesst_sich_nachtraeglich_aendern(hass, hass_ws_client, anlage):
    verwaltung, _ = anlage
    hass.states.async_set("sensor.kueche", "20.8", {"device_class": "temperature"})
    client = await hass_ws_client(hass)
    await _einrichten(client)

    antwort = await _senden(
        client,
        type="heatnexus/automatik/einstellen",
        heizkreis=HEIZKREIS,
        raeume=["sensor.wohnzimmer", "sensor.kueche"],
        raum_art="minimum",
        heizflaechen="flaeche",
        profil="traege",
        eigene={},
    )

    assert antwort["success"], antwort
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    assert laufzeit.konfig["raeume"] == ["sensor.wohnzimmer", "sensor.kueche"]
    assert laufzeit.konfig["profil"] == "traege"
    await laufzeit.auswerten()
    assert laufzeit.lage.raum == 20.8


async def test_lesen_liefert_stundenraster_und_korrektur(hass, hass_ws_client, anlage):
    client = await hass_ws_client(hass)
    await _einrichten(client)

    antwort = await _senden(client, type="heatnexus/automatik")

    (kreis,) = antwort["result"]["heizkreise"]
    assert len(kreis["tag"]["stunden"]) == 24
    assert {"korrigiert", "wolken", "aktion"} <= set(kreis["tag"]["stunden"][12])
    assert kreis["korrektur"]["fenster"] == 14
    assert kreis["korrektur"]["noetig"] == 7
    assert kreis["korrektur"]["temperatur"]["versatz"] is None
    assert kreis["korrektur"]["sonne"]["aktiv"] is False


async def test_gespeicherter_restwert_sensor_wird_beim_laden_verworfen(hass, hass_storage):
    from custom_components.heatnexus.automatik.verwaltung import STORE_KEY, Verwaltung

    hass_storage[STORE_KEY] = {
        "version": 1,
        "data": {
            "heizkreise": {
                HEIZKREIS: {
                    "konfig": {
                        "heizkreis": HEIZKREIS,
                        "raeume": ["sensor.wohnzimmer"],
                        "wetter": "weather.home",
                        "pv": "sensor.energy_production_today_remaining",
                    },
                    "zustand": {},
                }
            }
        },
    }
    verwaltung = Verwaltung(hass)

    await verwaltung.laden()

    assert verwaltung.konfig(HEIZKREIS)["pv"] is None


async def test_vergangene_stunden_behalten_ihre_prognose(hass, hass_ws_client, anlage):
    from homeassistant.util import dt as dt_util

    verwaltung, _ = anlage
    client = await hass_ws_client(hass)
    await _einrichten(client)
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    heute = dt_util.now().date()
    laufzeit.stunden = [
        e for e in laufzeit.stunden if not e["datetime"].startswith(heute.isoformat() + "T0")
    ]

    prognose = laufzeit.stundenprognose(heute)

    assert len(prognose) == 24
    assert prognose[3]["wolken"] == 10


async def test_lesen_liefert_vorschau_und_einzelne_raeume(hass, hass_ws_client, anlage, freezer):
    client = await hass_ws_client(hass)
    freezer.move_to(MORGEN)
    await _einrichten(client)

    antwort = await _senden(client, type="heatnexus/automatik")

    (kreis,) = antwort["result"]["heizkreise"]
    assert [tag["titel"] for tag in kreis["vorschau"]] == ["Morgen", "Übermorgen"]
    assert kreis["vorschau"][0]["begruendung"]
    assert kreis["kennwerte"]["at"] == 12.0
    assert kreis["kennwerte"]["raeume"][0]["wert"] == 21.4


async def test_vorschau_rechnet_die_sonnenquote_wie_der_betrieb(
    hass, hass_ws_client, anlage, freezer
):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    verwaltung, _ = anlage
    client = await hass_ws_client(hass)
    freezer.move_to(MORGEN)
    einheit = {"unit_of_measurement": "kWh", "device_class": "energy"}
    hass.states.async_set("sensor.energy_production_today", "20.0", einheit)
    hass.states.async_set("sensor.energy_production_tomorrow", "5.0", einheit)
    await _senden(
        client,
        type="heatnexus/automatik/einrichten",
        heizkreis=HEIZKREIS,
        raeume=["sensor.wohnzimmer"],
        wetter="weather.home",
        pv="sensor.energy_production_today",
    )
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    heute = dt_util.now().date()
    laufzeit.pv_tage = {(heute - timedelta(days=t)).isoformat(): 20.0 for t in range(1, 8)}

    antwort = await _senden(client, type="heatnexus/automatik")

    (kreis,) = antwort["result"]["heizkreise"]
    assert kreis["vorschau"][0]["sonnenquote"] == 25.0


async def test_heute_wird_aus_der_aufzeichnung_nachgetragen(hass, anlage, monkeypatch, freezer):
    from datetime import timedelta

    from homeassistant.core import State
    from homeassistant.util import dt as dt_util

    from custom_components.heatnexus.automatik import nachladen

    verwaltung, _ = anlage
    freezer.move_to(MORGEN)
    anfang = dt_util.start_of_local_day()
    zustaende = {
        "weather.home": [
            State(
                "weather.home",
                "sunny",
                {"temperature": 6.5, "cloud_coverage": 20},
                last_updated=anfang + timedelta(hours=2, minutes=50),
            ),
        ],
        "sensor.wohnzimmer": [
            State("sensor.wohnzimmer", "20.5", last_updated=anfang + timedelta(hours=1)),
        ],
    }

    class Instanz:
        async def async_add_executor_job(self, aufgabe):
            return zustaende

    import homeassistant.components.recorder as recorder

    monkeypatch.setattr(recorder, "get_instance", lambda _hass: Instanz(), raising=False)
    hass.config.components.add("recorder")
    await verwaltung.einrichten(
        hass.config_entries.async_entries("heatnexus")[0],
        {"heizkreis": HEIZKREIS, "raeume": ["sensor.wohnzimmer"], "wetter": "weather.home"},
    )
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    await nachladen.heute_nachtragen(hass, laufzeit)

    stunden = laufzeit.verlauf["stunden"]
    assert stunden["3"]["prognose"] == 6.5
    assert stunden["3"]["wolken"] == 10  # schon aus der Prognose gemerkt; Vorhandenes bleibt
    assert stunden["2"]["raum"] == 20.5


async def test_veralteter_raumfuehler_zaehlt_nicht(hass, hass_ws_client, anlage, freezer):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    verwaltung, _ = anlage
    client = await hass_ws_client(hass)
    hass.states.async_set("sensor.alt", "29.7", {"device_class": "temperature"})
    freezer.move_to(dt_util.utcnow() + timedelta(hours=13))
    hass.states.async_set(
        "sensor.wohnzimmer", "21.0", {"device_class": "temperature"}, force_update=True
    )
    antwort = await _senden(
        client,
        type="heatnexus/automatik/einrichten",
        heizkreis=HEIZKREIS,
        raeume=["sensor.wohnzimmer", "sensor.alt"],
        wetter="weather.home",
    )
    assert antwort["success"], antwort
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]

    await laufzeit.auswerten()

    assert laufzeit.lage.raum == 21.0
    raeume = {
        r["entity_id"]: r
        for r in (await _senden(client, type="heatnexus/automatik"))["result"]["heizkreise"][0][
            "kennwerte"
        ]["raeume"]
    }
    assert raeume["sensor.alt"]["veraltet"] is True
    assert raeume["sensor.wohnzimmer"]["veraltet"] is False


async def test_nachgerechnete_gedaempfte_at_ersetzt_einen_frischen_startwert(
    hass, anlage, monkeypatch, freezer
):
    from datetime import timedelta

    from homeassistant.core import State
    from homeassistant.util import dt as dt_util

    from custom_components.heatnexus.automatik import nachladen

    verwaltung, _ = anlage
    freezer.move_to(MORGEN)
    anfang = dt_util.start_of_local_day()
    hass.states.async_set("sensor.aussen", "8.0", {"device_class": "temperature"})
    reihe = [State("sensor.aussen", "8.0", last_updated=anfang - timedelta(minutes=10))]

    class Instanz:
        async def async_add_executor_job(self, aufgabe):
            return {"sensor.aussen": reihe}

    import homeassistant.components.recorder as recorder

    monkeypatch.setattr(recorder, "get_instance", lambda _hass: Instanz(), raising=False)
    hass.config.components.add("recorder")
    await verwaltung.einrichten(
        hass.config_entries.async_entries("heatnexus")[0],
        {
            "heizkreis": HEIZKREIS,
            "raeume": ["sensor.wohnzimmer"],
            "wetter": "weather.home",
            "aussen": "sensor.aussen",
        },
    )
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    laufzeit.stufen = (20.4, 20.4)  # Startwert vom Nachmittag
    laufzeit.stufen_start = dt_util.now()  # eben geschätzt

    await nachladen.heute_nachtragen(hass, laufzeit)

    assert laufzeit.stufen[1] == pytest.approx(8.0, abs=0.01)
    assert laufzeit.verlauf["stunden"]["5"]["gedaempft"] == pytest.approx(8.0, abs=0.01)


async def test_eingefrorener_fuehler_wird_aus_dem_verlauf_erkannt(
    hass, anlage, monkeypatch, freezer
):
    """Ein ausgefallenes Gerät meldet weiter denselben Wert; der Verlauf verrät es."""
    from datetime import timedelta

    from homeassistant.core import State
    from homeassistant.util import dt as dt_util

    from custom_components.heatnexus.automatik import nachladen

    verwaltung, _ = anlage
    freezer.move_to(MORGEN)
    jetzt = dt_util.now()
    hass.states.async_set("sensor.alt", "29.7", {"device_class": "temperature"})
    zustaende = {
        "sensor.alt": [
            State("sensor.alt", "29.7", last_updated=jetzt - timedelta(hours=30)),
            State("sensor.alt", "29.7", last_updated=jetzt - timedelta(hours=2)),
        ],
        "sensor.wohnzimmer": [
            State("sensor.wohnzimmer", "21.0", last_updated=jetzt - timedelta(hours=20)),
            State("sensor.wohnzimmer", "21.4", last_updated=jetzt - timedelta(hours=1)),
        ],
    }

    class Instanz:
        async def async_add_executor_job(self, aufgabe):
            return zustaende

    import homeassistant.components.recorder as recorder

    monkeypatch.setattr(recorder, "get_instance", lambda _hass: Instanz(), raising=False)
    hass.config.components.add("recorder")
    await verwaltung.einrichten(
        hass.config_entries.async_entries("heatnexus")[0],
        {
            "heizkreis": HEIZKREIS,
            "raeume": ["sensor.wohnzimmer", "sensor.alt"],
            "wetter": "weather.home",
        },
    )
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    await nachladen.heute_nachtragen(hass, laufzeit)

    assert laufzeit.veraltet("sensor.alt") is True
    assert laufzeit.veraltet("sensor.wohnzimmer") is False
    await laufzeit.auswerten()
    assert laufzeit.lage.raum == 21.4


async def test_ohne_anpassen_gilt_die_rohe_prognose(hass, hass_ws_client, anlage):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    verwaltung, _ = anlage
    client = await hass_ws_client(hass)
    await _einrichten(client)
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    heute = dt_util.now().date()
    for tag in range(1, 8):
        datum = (heute - timedelta(days=tag)).isoformat()
        for stunde in range(24):
            laufzeit.temperatur._fehler.append((datum, stunde, -2.0))
    roh = 10.0  # (14 + 6) / 2 aus der Tagesprognose
    assert laufzeit.tagesmittel(heute) == pytest.approx(roh - 2.0)

    await _senden(
        client,
        type="heatnexus/automatik/einstellen",
        heizkreis=HEIZKREIS,
        eigene={"anpassen": False},
    )

    assert laufzeit.tagesmittel(heute) == pytest.approx(roh)
    antwort = await _senden(client, type="heatnexus/automatik")
    assert antwort["result"]["heizkreise"][0]["korrektur"]["an"] is False


async def test_ein_seit_zwoelf_stunden_gleicher_wert_ist_noch_nicht_eingefroren(hass):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    from custom_components.heatnexus.automatik import nachladen

    jetzt = dt_util.now()
    reihen = {
        "sensor.selten": [(jetzt - timedelta(hours=14), 21.5)],
        "sensor.defekt": [(jetzt - timedelta(days=12), 29.7)],
    }

    assert set(nachladen.eingefroren(reihen, jetzt)) == {"sensor.defekt"}


def _thermostat(hass, entity_id: str, ist: float, ziel: float, aktion: str = "idle") -> None:
    attribute = {"current_temperature": ist, "temperature": ziel, "hvac_action": aktion}
    hass.states.async_set(entity_id, "heat", attribute)


async def test_thermostat_zaehlt_gegen_sein_eigenes_ziel(hass, hass_ws_client, anlage):
    verwaltung, _ = anlage
    client = await hass_ws_client(hass)
    _thermostat(hass, "climate.bad", 20.4, 20.5)
    antwort = await _senden(
        client,
        type="heatnexus/automatik/einrichten",
        heizkreis=HEIZKREIS,
        raeume=["climate.bad"],
        wetter="weather.home",
    )
    assert antwort["success"], antwort
    assert antwort["result"]["eigene"] == {"sonnentag": False}
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]

    await laufzeit.auswerten()

    assert laufzeit.lage.raeume == ((20.4, 20.5),)
    assert laufzeit.lage.raum == 20.4
    kennwerte = (await _senden(client, type="heatnexus/automatik"))["result"]["heizkreise"][0][
        "kennwerte"
    ]
    assert kennwerte["abweichung"] == pytest.approx(-0.1)
    assert kennwerte["eigene_ziele"] is True
    assert kennwerte["raum_bezug"] is None
    assert kennwerte["raeume"][0]["ziel"] == 20.5
    assert kennwerte["raeume"][0]["heizt"] is False


async def test_raeume_gelten_erst_nach_zwei_stunden_ohne_anforderung_als_ruhig(
    hass, anlage, freezer
):
    from datetime import timedelta

    verwaltung, _ = anlage
    freezer.move_to(MORGEN)
    _thermostat(hass, "climate.bad", 20.6, 20.5)
    await verwaltung.einrichten(
        hass.config_entries.async_entries("heatnexus")[0],
        {"heizkreis": HEIZKREIS, "raeume": ["climate.bad"], "wetter": "weather.home"},
    )
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    assert laufzeit.lage.ruhig is False

    freezer.tick(timedelta(hours=2, minutes=1))
    await laufzeit.auswerten()
    assert laufzeit.lage.ruhig is True

    _thermostat(hass, "climate.bad", 20.3, 20.5, "heating")
    await hass.async_block_till_done()
    _thermostat(hass, "climate.bad", 20.4, 20.5)
    freezer.tick(timedelta(minutes=30))
    await laufzeit.auswerten()
    assert laufzeit.lage.ruhig is False


async def test_ohne_thermostat_gibt_es_keine_anforderung(hass, anlage):
    verwaltung, _ = anlage
    await verwaltung.einrichten(
        hass.config_entries.async_entries("heatnexus")[0],
        {"heizkreis": HEIZKREIS, "raeume": ["sensor.wohnzimmer"], "wetter": "weather.home"},
    )
    assert verwaltung.laufzeiten[HEIZKREIS].lage.ruhig is None


async def test_wunschtemperatur_gilt_fuer_temperaturfuehler(hass, anlage):
    verwaltung, _ = anlage
    await verwaltung.einrichten(
        hass.config_entries.async_entries("heatnexus")[0],
        {
            "heizkreis": HEIZKREIS,
            "raeume": ["sensor.wohnzimmer"],
            "wetter": "weather.home",
            "raum_ziel": 20.0,
        },
    )
    assert verwaltung.laufzeiten[HEIZKREIS].lage.raeume == ((21.4, 20.0),)


async def test_thermostate_stehen_zur_wahl_der_eigene_heizkreis_nicht(hass, hass_ws_client, anlage):
    from homeassistant.helpers import entity_registry as er

    from custom_components.heatnexus.const import DOMAIN

    client = await hass_ws_client(hass)
    _thermostat(hass, "climate.bad", 20.4, 20.5)
    eigener = er.async_get(hass).async_get_entity_id("climate", DOMAIN, f"{HEIZKREIS}-thermostat")
    _thermostat(hass, eigener, 20.0, 21.0)

    antwort = await _senden(client, type="heatnexus/automatik/kandidaten")

    kennungen = {e["entity_id"]: e for e in antwort["result"]["temperatur"]}
    assert kennungen["climate.bad"]["art"] == "thermostat"
    assert eigener not in kennungen


async def test_eingefrorenes_thermostat_wird_aus_dem_verlauf_erkannt(
    hass, anlage, monkeypatch, freezer
):
    from datetime import timedelta

    from homeassistant.core import State
    from homeassistant.util import dt as dt_util

    from custom_components.heatnexus.automatik import nachladen

    verwaltung, _ = anlage
    freezer.move_to(MORGEN)
    jetzt = dt_util.now()
    _thermostat(hass, "climate.ess", 29.7, 21.0)
    _thermostat(hass, "climate.bad", 20.4, 20.5)
    attribute = {"current_temperature": 29.7, "temperature": 21.0}
    zustaende = {
        "climate.ess": [
            State("climate.ess", "auto", attribute, last_updated=jetzt - timedelta(hours=30)),
            State("climate.ess", "heat", attribute, last_updated=jetzt - timedelta(hours=2)),
        ],
        "climate.bad": [
            State(
                "climate.bad",
                "heat",
                {"current_temperature": 20.1},
                last_updated=jetzt - timedelta(hours=20),
            ),
            State(
                "climate.bad",
                "heat",
                {"current_temperature": 20.4},
                last_updated=jetzt - timedelta(hours=1),
            ),
        ],
    }

    class Instanz:
        async def async_add_executor_job(self, aufgabe):
            return zustaende

    import homeassistant.components.recorder as recorder

    monkeypatch.setattr(recorder, "get_instance", lambda _hass: Instanz(), raising=False)
    hass.config.components.add("recorder")
    await verwaltung.einrichten(
        hass.config_entries.async_entries("heatnexus")[0],
        {
            "heizkreis": HEIZKREIS,
            "raeume": ["climate.bad", "climate.ess"],
            "wetter": "weather.home",
        },
    )
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    await nachladen.heute_nachtragen(hass, laufzeit)

    assert laufzeit.veraltet("climate.ess") is True
    assert laufzeit.veraltet("climate.bad") is False
    await laufzeit.auswerten()
    assert laufzeit.lage.raeume == ((20.4, 20.5),)


def _quelle(hass, zustand: str = "on") -> str:
    """Eine Wärmequelle von HeatNexus, wie sie `binary_sensor` anlegt."""
    from homeassistant.helpers import entity_registry as er

    from custom_components.heatnexus.const import DOMAIN

    eintrag = er.async_get(hass).async_get_or_create(
        "binary_sensor", DOMAIN, "SN1-waermequelle-q1", suggested_object_id="solaranlage"
    )
    hass.states.async_set(eintrag.entity_id, zustand, {"friendly_name": "Solaranlage"})
    return eintrag.entity_id


async def test_waermequellen_stehen_als_vorrang_zur_wahl(hass, hass_ws_client, anlage):
    client = await hass_ws_client(hass)
    quelle = _quelle(hass)
    hass.states.async_set("binary_sensor.tuer", "off", {"device_class": "door"})

    antwort = await _senden(client, type="heatnexus/automatik/kandidaten")

    assert [e["entity_id"] for e in antwort["result"]["vorrang"]] == [quelle]


async def test_vorrangquelle_zaehlt_ihre_minuten(hass, hass_ws_client, anlage, freezer):
    from datetime import timedelta

    verwaltung, _ = anlage
    client = await hass_ws_client(hass)
    freezer.move_to(MORGEN)
    quelle = _quelle(hass)
    antwort = await _senden(
        client,
        type="heatnexus/automatik/einrichten",
        heizkreis=HEIZKREIS,
        raeume=["sensor.wohnzimmer"],
        wetter="weather.home",
        vorrang=[quelle],
    )
    assert antwort["success"], antwort
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    assert laufzeit.lage.vorrang_laeuft is True
    assert laufzeit.lage.vorrang_name == "Solaranlage"

    freezer.tick(timedelta(minutes=30))
    hass.states.async_set(quelle, "off", {"friendly_name": "Solaranlage"})
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=30))
    await laufzeit.auswerten()

    assert laufzeit.lage.vorrang_laeuft is False
    assert laufzeit.lage.vorrang_minuten == pytest.approx(30)
    kreis = (await _senden(client, type="heatnexus/automatik"))["result"]["heizkreise"][0]
    assert kreis["kennwerte"]["vorrang"] == {"laeuft": False, "minuten": 30}
    stunde = next(s for s in kreis["tag"]["stunden"] if s["stunde"] == 8)
    assert stunde["vorrang"] is True


async def test_ohne_vorrangquelle_keine_angabe(hass, hass_ws_client, anlage):
    client = await hass_ws_client(hass)
    await _einrichten(client)
    kreis = (await _senden(client, type="heatnexus/automatik"))["result"]["heizkreise"][0]
    assert kreis["kennwerte"]["vorrang"] is None
    assert kreis["konfig"]["vorrang"] == []


async def test_lieferbeginn_einer_vorrangquelle_loest_eine_entscheidung_aus(
    hass, hass_ws_client, anlage, freezer
):
    """Einmal am Tag; ein zweiter Lieferbeginn entscheidet nicht erneut."""
    from datetime import timedelta

    verwaltung, _ = anlage
    freezer.move_to(MORGEN)
    quelle = _quelle(hass, "off")
    await verwaltung.einrichten(
        hass.config_entries.async_entries("heatnexus")[0],
        {
            "heizkreis": HEIZKREIS,
            "raeume": ["sensor.wohnzimmer"],
            "wetter": "weather.home",
            "vorrang": [quelle],
        },
    )
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    vorher = len(laufzeit.steller.stand.protokoll)

    hass.states.async_set(quelle, "on", {"friendly_name": "Solaranlage"})
    await hass.async_block_till_done()

    eintraege = laufzeit.steller.stand.protokoll
    assert len(eintraege) == vorher + 1
    assert eintraege[0]["text"].startswith("Solaranlage liefert")

    for zustand in ("off", "on"):
        freezer.tick(timedelta(minutes=10))
        hass.states.async_set(quelle, zustand, {"friendly_name": "Solaranlage"})
        await hass.async_block_till_done()
    assert len(laufzeit.steller.stand.protokoll) == vorher + 1


async def test_ausgeschaltete_thermostate_sind_raeume_ohne_bedarf(hass, anlage):
    verwaltung, _ = anlage
    for kennung, ist in (("climate.bad", 20.1), ("climate.kueche", 19.5)):
        hass.states.async_set(
            kennung,
            "off",
            {"current_temperature": ist, "temperature": None, "hvac_action": "off"},
        )
    await verwaltung.einrichten(
        hass.config_entries.async_entries("heatnexus")[0],
        {
            "heizkreis": HEIZKREIS,
            "raeume": ["climate.bad", "climate.kueche"],
            "wetter": "weather.home",
        },
    )
    lage = verwaltung.laufzeiten[HEIZKREIS].lage
    assert lage.raeume == ()
    assert lage.aus == (20.1, 19.5)
    assert lage.raum == pytest.approx(19.8)
    assert verwaltung.laufzeiten[HEIZKREIS].zustand.value != "keine_daten"


async def test_stundenraster_zeigt_was_je_stunde_galt(hass, anlage, freezer):
    """Vergangene Stunden behalten ihre Aktion; kommende zeigen den Plan."""
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    from custom_components.heatnexus.automatik import regel, tagesansicht

    verwaltung, _ = anlage
    freezer.move_to(MORGEN)
    await verwaltung.einrichten(
        hass.config_entries.async_entries("heatnexus")[0],
        {"heizkreis": HEIZKREIS, "raeume": ["sensor.wohnzimmer"], "wetter": "weather.home"},
    )
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    await laufzeit.auswerten(entscheidungszeit=True)
    assert laufzeit.zustand == regel.Zustand.SONNENTAG

    freezer.tick(timedelta(hours=3))
    laufzeit.gedaechtnis = regel.Gedaechtnis(
        saison=regel.NUR_WW, saison_seit=dt_util.now(), saison_soll=21.0
    )
    await laufzeit.auswerten()

    aktionen = {
        s["stunde"]: s["aktion"] for s in tagesansicht.heute(laufzeit, dt_util.now())["stunden"]
    }
    assert aktionen[8] == "absenkung"
    assert aktionen[11] == "nur_ww"
    assert aktionen[15] == "nur_ww"
    assert aktionen[5] == "programm"


async def test_ausrichtung_ist_eine_auswahl_entitaet(hass, anlage):
    from custom_components.heatnexus.automatik.entitaeten import KLASSEN
    from custom_components.heatnexus.automatik.verwaltung import DOMAENE_JE_ART

    verwaltung, _ = anlage
    await verwaltung.einrichten(
        hass.config_entries.async_entries("heatnexus")[0],
        {"heizkreis": HEIZKREIS, "raeume": ["sensor.wohnzimmer"], "wetter": "weather.home"},
    )
    auswahl = KLASSEN["ausrichtung"](verwaltung, HEIZKREIS)
    assert DOMAENE_JE_ART["ausrichtung"] == "select"
    assert auswahl.options == ["eco", "ausgewogen", "komfort"]
    assert auswahl.current_option == "ausgewogen"

    await auswahl.async_select_option("eco")

    assert verwaltung.konfig(HEIZKREIS)["ausrichtung"] == "eco"
    assert auswahl.current_option == "eco"


async def _eingerichtet(hass, verwaltung):
    await verwaltung.einrichten(
        hass.config_entries.async_entries("heatnexus")[0],
        {"heizkreis": HEIZKREIS, "raeume": ["sensor.wohnzimmer"], "wetter": "weather.home"},
    )
    return verwaltung.laufzeiten[HEIZKREIS]


async def test_automatik_bekommt_ein_eigenes_geraet(hass, anlage):
    from custom_components.heatnexus.automatik.entitaeten import KLASSEN
    from custom_components.heatnexus.const import DOMAIN

    verwaltung, _ = anlage
    await _eingerichtet(hass, verwaltung)
    for art in ("schalter", "zustand", "gedaempft"):
        geraet = KLASSEN[art](verwaltung, HEIZKREIS).device_info
        assert geraet["identifiers"] == {(DOMAIN, f"{HEIZKREIS}-automatik")}
        assert geraet["name"] == f"{ANLAGE} · Automatik Heizkreis"
        assert geraet["model"] == "Automatik"


async def test_sensoren_der_automatik(hass, anlage, freezer):
    from datetime import datetime

    from homeassistant.util import dt as dt_util

    from custom_components.heatnexus.automatik.entitaeten import KLASSEN

    verwaltung, _ = anlage
    freezer.move_to(MORGEN)
    laufzeit = await _eingerichtet(hass, verwaltung)
    await verwaltung.einstellen(HEIZKREIS, {"modus": "schalten"})
    await laufzeit.auswerten(entscheidungszeit=True)

    def wert(art):
        return KLASSEN[art](verwaltung, HEIZKREIS).native_value

    assert wert("gedaempft") == round(laufzeit.lage.at_gedaempft, 1)
    assert laufzeit.lage.grenze_steuerung == 18.0
    assert wert("heizgrenze") == 18.0
    assert wert("abweichung") == pytest.approx(0.4)
    assert wert("sonnenquote") == round(laufzeit.lage.sonnenquote)
    assert wert("eingriffe") == 1
    assert wert("letzter_eingriff") == datetime.fromisoformat(
        laufzeit.steller.stand.protokoll[0]["zeit"]
    )
    naechste = wert("naechste_entscheidung")
    assert naechste > dt_util.now()
    assert (naechste.hour, naechste.minute) == (7, 0)


async def test_stoerung_meldet_eine_gesperrte_steuerung(hass, anlage, freezer):
    from dataclasses import replace
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    from custom_components.heatnexus.automatik.entitaeten import KLASSEN

    verwaltung, _ = anlage
    freezer.move_to(MORGEN)
    laufzeit = await _eingerichtet(hass, verwaltung)
    stoerung = KLASSEN["stoerung"](verwaltung, HEIZKREIS)
    assert stoerung.is_on is False

    bis = (dt_util.now() + timedelta(hours=1)).isoformat()
    laufzeit.steller.stand = replace(laufzeit.steller.stand, gesperrt_bis=bis)
    assert stoerung.is_on is True


async def test_kennwerte_nennen_die_grenzen_der_steuerung(hass, hass_ws_client, anlage):
    client = await hass_ws_client(hass)
    await _senden(
        client,
        type="heatnexus/automatik/einrichten",
        heizkreis=HEIZKREIS,
        raeume=["sensor.wohnzimmer"],
        wetter="weather.home",
        ausrichtung="eco",
    )
    kennwerte = (await _senden(client, type="heatnexus/automatik"))["result"]["heizkreise"][0][
        "kennwerte"
    ]
    assert kennwerte["grenze_steuerung"] == 18.0
    assert kennwerte["grenze_absenk"] == 5.0
    assert kennwerte["versatz"] == -2.0
    assert kennwerte["heizgrenze"] == 16.0
    assert kennwerte["hysterese"] == 1.0
    assert kennwerte["sonne_schwelle"] == 45.0
    assert kennwerte["stark_quote"] == 80.0


async def test_heizgrenzen_der_steuerung_lassen_sich_setzen(hass, hass_ws_client, anlage):
    """Eine Handeinstellung: geschrieben an die Steuerung, ohne Budget der Automatik."""
    verwaltung, coordinator = anlage
    client = await hass_ws_client(hass)
    await _einrichten(client)

    antwort = await _senden(
        client,
        type="heatnexus/automatik/heizgrenzen",
        heizkreis=HEIZKREIS,
        heizbetrieb=17.5,
        absenkbetrieb=4.0,
    )

    assert antwort["success"], antwort
    assert coordinator.client.geschrieben == [
        (f"{PREFIX}/3/21/0", "17.5"),
        (f"{PREFIX}/3/2/0", "4.0"),
    ]
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    assert laufzeit.steller.stand.protokoll[0]["art"] == "einstellung"
    assert laufzeit.steller.stand.eingriffe == 0


@pytest.mark.parametrize("felder", [{"heizbetrieb": 35.0}, {"absenkbetrieb": -12.0}, {}])
async def test_heizgrenzen_ausserhalb_des_bereichs_werden_abgewiesen(
    hass, hass_ws_client, anlage, felder
):
    _, coordinator = anlage
    client = await hass_ws_client(hass)
    await _einrichten(client)
    antwort = await _senden(
        client, type="heatnexus/automatik/heizgrenzen", heizkreis=HEIZKREIS, **felder
    )
    assert not antwort["success"]
    assert coordinator.client.geschrieben == []


async def test_nur_administratoren_setzen_heizgrenzen(
    hass, hass_ws_client, hass_read_only_access_token, anlage
):
    client = await hass_ws_client(hass, hass_read_only_access_token)
    antwort = await _senden(
        client, type="heatnexus/automatik/heizgrenzen", heizkreis=HEIZKREIS, heizbetrieb=18.0
    )
    assert antwort["error"]["code"] == "unauthorized"


async def test_system_geraet_buendelt_die_automatiken(hass, anlage, freezer):
    from homeassistant.helpers import device_registry as dr

    from custom_components.heatnexus.automatik import system
    from custom_components.heatnexus.automatik.entitaeten import KLASSEN
    from custom_components.heatnexus.const import DOMAIN

    verwaltung, _ = anlage
    freezer.move_to(MORGEN)
    entry = hass.config_entries.async_entries("heatnexus")[0]
    laufzeit = await _eingerichtet(hass, verwaltung)

    geraet = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, system.system_kennung(entry.entry_id))}
    )
    assert geraet is not None
    assert geraet.name == "HeatNexus Automatik"
    kreis = KLASSEN["schalter"](verwaltung, HEIZKREIS).device_info
    assert kreis.get("via_device_id") == geraet.id or kreis.get("via_device") == (
        DOMAIN,
        system.system_kennung(entry.entry_id),
    )

    def wert(art):
        entitaet = system.KLASSEN[art](verwaltung, entry.entry_id)
        return entitaet.is_on if art in system.BINAER_ARTEN else entitaet.native_value

    assert wert("status") == "beobachten"
    assert wert("automatiken") == 1
    assert wert("stoerung") is False
    assert wert("prognose") is True

    await verwaltung.einstellen(HEIZKREIS, {"modus": "schalten"})
    await laufzeit.auswerten(entscheidungszeit=True)
    assert wert("status") == "eingriff"
    assert wert("eingriffe") == 1
    assert wert("letzter_eingriff") is not None
    assert wert("naechste_entscheidung") is not None

    await verwaltung.entfernen(HEIZKREIS)
    assert (
        dr.async_get(hass).async_get_device(
            identifiers={(DOMAIN, system.system_kennung(entry.entry_id))}
        )
        is None
    )


async def test_system_kennungen_gelten_als_bekannt(hass, anlage):
    from custom_components.heatnexus.automatik import system

    verwaltung, _ = anlage
    entry = hass.config_entries.async_entries("heatnexus")[0]
    await _eingerichtet(hass, verwaltung)
    kennungen = verwaltung.kennungen(entry.entry_id)
    assert system.system_unique_id(entry.entry_id, "status") in kennungen


async def test_diagnose_enthaelt_die_automatik(hass, anlage, freezer):
    """Ohne den Stand der Automatik lässt sich ein gemeldeter Eingriff nicht nachvollziehen."""
    from custom_components.heatnexus import diagnostics

    verwaltung, _ = anlage
    freezer.move_to(MORGEN)
    laufzeit = await _eingerichtet(hass, verwaltung)
    await laufzeit.auswerten(entscheidungszeit=True)
    entry = hass.config_entries.async_entries("heatnexus")[0]

    automatik = diagnostics.automatik_auszug(hass, entry)
    assert automatik["system"] == {"automatiken": 1, "status": "beobachten"}
    (auszug,) = automatik["heizkreise"]
    assert auszug["zustand"] == "sonnentag"
    assert auszug["lage"]["grenze_steuerung"] == 18.0
    assert auszug["grenze"] == 18.0
    assert auszug["werte"]["grenze_versatz"] == 0.0
    assert auszug["protokoll"][0]["art"] == "haette"
    for schluessel in ("konfig", "gedaechtnis", "steller", "vorrang", "verlauf", "korrektur"):
        assert schluessel in auszug


async def test_teilweise_gesetzte_heizgrenzen_stehen_im_protokoll(hass, hass_ws_client, anlage):
    """Lehnt die Steuerung den zweiten Wert ab, bleibt der erste nachvollziehbar."""
    verwaltung, coordinator = anlage
    client = await hass_ws_client(hass)
    await _einrichten(client)
    geschrieben = []

    async def update(oid: str, wert: str) -> None:
        if oid.endswith("/3/2/0"):
            raise RuntimeError("abgelehnt")
        geschrieben.append((oid, wert))

    coordinator.client.update = update
    antwort = await _senden(
        client,
        type="heatnexus/automatik/heizgrenzen",
        heizkreis=HEIZKREIS,
        heizbetrieb=17.5,
        absenkbetrieb=4.0,
    )

    assert not antwort["success"]
    assert "Absenkbetrieb" in antwort["error"]["message"]
    assert geschrieben == [(f"{PREFIX}/3/21/0", "17.5")]
    eintrag = verwaltung.laufzeiten[HEIZKREIS].steller.stand.protokoll[0]
    assert eintrag["art"] == "einstellung"
    assert "Heizbetrieb 17,5 °C" in eintrag["text"]


async def test_die_volle_stunde_vermerkt_den_modus(hass, hass_ws_client, anlage, freezer):
    """Der Stundentakt trägt Aktion und Modus-Laufzeiten nach, auch ohne Ereignis."""
    from datetime import timedelta

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    verwaltung, _coordinator = anlage
    client = await hass_ws_client(hass)
    # MORGEN liegt nicht an der Tagesgrenze, damit +1 h nicht in den nächsten Tag rutscht.
    freezer.move_to(MORGEN)
    await _einrichten(client)
    laufzeit = verwaltung.laufzeiten[HEIZKREIS]
    naechste = (dt_util.now() + timedelta(hours=1)).replace(minute=0, second=5, microsecond=0)
    freezer.move_to(naechste)
    async_fire_time_changed(hass, naechste)
    await hass.async_block_till_done()
    assert laufzeit.verlauf["stunden"][str(naechste.hour)]["aktion"] == "programm"
    assert set(laufzeit.als_dict()["modus_lauf"]) == {"absenkung", "nur_ww"}


async def test_das_system_hat_die_neuen_sensoren(hass, hass_ws_client, anlage):
    """`anmelden` legt für jede neue Art eine Entität mit der Systemkennung an."""
    from custom_components.heatnexus.automatik import system as system_modul
    from custom_components.heatnexus.const import DOMAIN

    client = await hass_ws_client(hass)
    await _einrichten(client)
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    for art in (
        "sonnentag_heute",
        "nur_ww_heute",
        "modus_seit",
        "prognose_mittel",
        "ueber_heizgrenze",
    ):
        erstellt: list = []
        system_modul.anmelden(hass, entry, erstellt.extend, art)
        assert erstellt, art
        assert erstellt[0].unique_id.endswith(f"-automatik-system-{art}")
