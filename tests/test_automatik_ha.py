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
        """Merkt sich jeden Schreibvorgang."""
        self.geschrieben: list[tuple[str, str]] = []

    async def update(self, oid: str, wert: str) -> None:
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


async def test_einrichten_startet_im_beobachtungsmodus(hass, hass_ws_client, anlage):
    verwaltung, coordinator = anlage
    client = await hass_ws_client(hass)

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
