"""Einrichtung eines Eintrags und der Vollabzug im Hintergrund.

`async_setup_entry` und `_vollabzug` waren die beiden größten ungeprüften
Abläufe der Integration – und zugleich die, an denen die schwersten Fehler
hingen: Die v0.5.0-Regression „verbunden, aber keine Daten" entstand genau
hier, weil die Erkennung im Zeitfenster des Abrufs lief.

Geprüft wird deshalb der Ablauf, nicht die Anlage: Der Client ist eine
Attrappe. Was zählt, ist die Reihenfolge – schneller Start aus den
Grunddaten, Vollabzug im Hintergrund, Erkennungsstand hinterher auf Platte.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest

from .conftest import ha_fehlt, requires_frontend, requires_ha, requires_moderne_ha

pytestmark = [requires_ha(), requires_frontend(), requires_moderne_ha()]

# **Vor der ersten `hass`-Fixture importieren.** Die Testumgebung blendet
# `custom_components` aus, sobald sie eine Home-Assistant-Instanz aufgebaut hat;
# ein Import aus dem Test heraus scheitert dann mit `ModuleNotFoundError`. Beim
# Einsammeln der Datei läuft noch keine Instanz – hier geht er.
if not ha_fehlt():  # pragma: no branch - ohne HA wird die Datei übersprungen
    from custom_components.heatnexus import _nur_anzeige_geaendert
    from custom_components.heatnexus.const import (
        CONF_KESSELART,
        CONF_LEVELS,
        CONF_MODULPUMPE,
        CONF_SYSTEMS,
        DOMAIN,
    )


DESKRIPTOREN = [
    {
        "oid": "/1/15/0/0/7/0",
        "name": "Kesseltemperatur Ist",
        "type": "temperature",
        "device_id": "0000ABCD1234-0",
        "device_name": "PuroWIN",
        "id": "0000ABCD1234-0-0-7-0",
        "fct_type": 25,
        "enabled_default": True,
    }
]

# Was der Vollabzug zusätzlich findet – der Sinn des Hintergrundlaufs.
ZUSAETZLICH = [
    *DESKRIPTOREN,
    {
        "oid": "/1/15/0/2/1/0",
        "name": "Betriebsphase",
        "type": "enum_sensor",
        "device_id": "0000ABCD1234-0",
        "device_name": "PuroWIN",
        "id": "0000ABCD1234-0-2-1-0",
        "fct_type": 25,
        "enabled_default": True,
    },
]


class AttrappenClient:
    """Ein Client, der nie ins Netz geht.

    Er zählt mit, was aufgerufen wurde – daran hängt die eigentliche Frage
    dieser Tests: Läuft der Vollabzug wirklich erst *nach* der Einrichtung?
    """

    letzte: AttrappenClient | None = None

    def __init__(self, **kwargs: Any) -> None:
        """Die Anlagenangaben nimmt sie entgegen und legt sie beiseite."""
        self.host = kwargs.get("host")
        self.auth_errors = 0
        self.request_count = 3
        self.devices = list(DESKRIPTOREN)
        self.basic_aufgerufen = 0
        self.init_aufgerufen = 0
        self.geschlossen = False
        self.gepollt: set[str] = set()
        self.exportiert = {"devices": DESKRIPTOREN}
        # Was die Steuerung über sich selbst sagt. Ein aus dem Zwischenspeicher
        # wiederhergestellter Stand holt beides nach; ohne die Felder liefe die
        # Einrichtung hier in einen AttributeError.
        self.geraeteinfo: dict[str, Any] = {}
        self.werksbezeichnung: dict[str, str] = {}
        self.geraeteinfo_abrufe = 0
        # Die Sprache wandert in den gespeicherten Stand; fehlt sie, scheitert
        # der Hintergrundlauf und der Eintrag lässt sich nicht mehr entladen.
        self.sprache = kwargs.get("sprache", "de")
        AttrappenClient.letzte = self

    async def _lese_geraeteinfo(self) -> None:
        self.geraeteinfo_abrufe += 1
        self.geraeteinfo = {"device": "MB66xx", "version": "1.0"}

    async def _lese_knotendaten(self) -> None:
        self.werksbezeichnung = {"15": "UMUMLZ"}

    async def async_init_basic(self) -> None:
        self.basic_aufgerufen += 1

    async def async_init(self, erzwingen: bool = False) -> None:
        self.init_aufgerufen += 1
        self.devices = list(ZUSAETZLICH)
        self.exportiert = {"devices": ZUSAETZLICH}

    async def fetch_all(self, budget: float | None = None) -> dict[str, Any]:
        return {
            "devices": self.devices,
            "oids": {"/1/15/0/0/7/0": "63.5"},
            "objects": {},
            "status": {},
        }

    def export_discovery(self) -> dict[str, Any]:
        return self.exportiert

    def restore_discovery(self, daten: dict[str, Any]) -> None:
        self.devices = list(daten.get("devices") or [])

    def steuerung_kennung(self) -> str:
        return "0000ABCD1234"

    def register_poll_oid(self, oid: str) -> None:
        self.gepollt.add(oid)

    def unregister_poll_oid(self, oid: str) -> None:
        self.gepollt.discard(oid)

    async def close(self) -> None:
        self.geschlossen = True


@pytest.fixture(autouse=True)
def _eigene_integration(enable_custom_integrations):
    """Ohne diesen Schalter legt die Testumgebung eigene Integrationen nicht vor."""
    return enable_custom_integrations


@pytest.fixture(autouse=True)
async def _aufraeumen(hass):
    """Nach jedem Test die Uhr vorstellen und den Eintrag entladen.

    Zwei Zeitgeber bleiben sonst stehen und die Testumgebung schlägt Alarm:
    der Takt des Koordinators und die verzögerte Erfolgsmeldung des
    Vollabzugs. Beides gehört zum Ablauf – hier wird es nur sauber beendet.
    """
    yield

    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    from custom_components.heatnexus import MELDUNG_VERZOEGERUNG

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=MELDUNG_VERZOEGERUNG + 1))
    await hass.async_block_till_done()
    for geladen in hass.config_entries.async_entries(DOMAIN):
        if geladen.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(geladen.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def eintrag(hass):
    """Ein Konfigurationseintrag mit genau einer Anlage."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    eintrag = MockConfigEntry(
        domain=DOMAIN,
        # Der Config-Flow steht auf Fassung 2; ein Eintrag mit der Vorgabe 1
        # ginge in die Migration statt in die Einrichtung.
        version=2,
        title="Heizhaus",
        data={
            "name": "Heizhaus",
            CONF_SYSTEMS: [
                {"host": "192.0.2.10", "password": "geheim", "label": "Heizhaus"},
            ],
        },
        options={},
    )
    eintrag.add_to_hass(hass)
    return eintrag


async def _einrichten(hass, eintrag) -> bool:
    """Den Eintrag mit der Attrappe einrichten und alles abwarten."""
    with patch("custom_components.heatnexus.WindhagerHttpClient", AttrappenClient):
        erfolg = await hass.config_entries.async_setup(eintrag.entry_id)
        await hass.async_block_till_done()
    return erfolg


# ---------------------------------------------------------------------------
# Einrichtung
# ---------------------------------------------------------------------------
async def test_die_einrichtung_gelingt_und_legt_die_geraete_an(hass, eintrag):
    """Anlage, Steuerung und Funktion – drei Ebenen, wie die Anlage gebaut ist."""
    from homeassistant.helpers import device_registry as dr

    assert await _einrichten(hass, eintrag) is True

    registry = dr.async_get(hass)
    kennungen = {
        wert
        for geraet in registry.devices.values()
        for bereich, wert in geraet.identifiers
        if bereich == DOMAIN
    }
    # Die Heizungsanlage selbst, die Steuerung unter ihrer Seriennummer und
    # die Funktion darunter.
    assert eintrag.entry_id in kennungen
    assert "0000ABCD1234" in kennungen
    assert "0000ABCD1234-0" in kennungen


async def test_ohne_anlage_im_eintrag_wird_nicht_eingerichtet(hass):
    """Ein Eintrag ohne Anlage ist kein Grund, halb zu starten."""
    from homeassistant.config_entries import ConfigEntryState
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    leer = MockConfigEntry(domain=DOMAIN, version=2, title="Leer", data={}, options={})
    leer.add_to_hass(hass)

    await hass.config_entries.async_setup(leer.entry_id)
    await hass.async_block_till_done()

    assert leer.state is ConfigEntryState.SETUP_RETRY


async def test_eine_unerreichbare_anlage_meldet_nicht_bereit(hass, eintrag):
    """`ConfigEntryNotReady` statt eines halb eingerichteten Eintrags.

    Und die Verbindung wird dabei geschlossen – sonst bliebe bei jedem
    Wiederholungsversuch eine Sitzung liegen.
    """
    from homeassistant.config_entries import ConfigEntryState

    class Unerreichbar(AttrappenClient):
        async def async_init_basic(self) -> None:
            raise OSError("Netzwerk nicht erreichbar")

    with patch("custom_components.heatnexus.WindhagerHttpClient", Unerreichbar):
        await hass.config_entries.async_setup(eintrag.entry_id)
        await hass.async_block_till_done()

    assert eintrag.state is ConfigEntryState.SETUP_RETRY
    assert AttrappenClient.letzte.geschlossen is True


async def test_eine_zeitueberschreitung_beim_verbinden_gilt_als_nicht_bereit(hass, eintrag):
    """Der Erstabruf hat ein eigenes, großzügiges Zeitfenster – reißt es, ist Schluss."""
    from homeassistant.config_entries import ConfigEntryState

    class Langsam(AttrappenClient):
        async def async_init_basic(self) -> None:
            raise TimeoutError

    with patch("custom_components.heatnexus.WindhagerHttpClient", Langsam):
        await hass.config_entries.async_setup(eintrag.entry_id)
        await hass.async_block_till_done()

    assert eintrag.state is ConfigEntryState.SETUP_RETRY


async def test_der_eintrag_laesst_sich_wieder_entladen(hass, eintrag):
    """Entladen muss gehen, sonst braucht jede Änderung einen Neustart."""
    from homeassistant.config_entries import ConfigEntryState

    assert await _einrichten(hass, eintrag) is True

    assert await hass.config_entries.async_unload(eintrag.entry_id) is True
    await hass.async_block_till_done()

    assert eintrag.state is ConfigEntryState.NOT_LOADED


async def test_beim_entladen_bleiben_keine_laufzeitdaten_stehen(hass, eintrag):
    """Ein entladener Eintrag darf nirgends mehr mitgezählt werden.

    An den Laufzeitdaten hängen der Zeitgeber der Einlese-Meldung und die
    Geräteliste des Dashboards. Bleiben sie stehen, meldet HeatNexus eine
    Anlage als bereit, die es nicht mehr gibt.
    """
    import custom_components.heatnexus as modul

    assert await _einrichten(hass, eintrag) is True
    assert modul.laufzeitdaten(eintrag) is not None

    assert await hass.config_entries.async_unload(eintrag.entry_id) is True
    await hass.async_block_till_done()

    assert modul.laufzeitdaten(eintrag) is None


# ---------------------------------------------------------------------------
# Vollabzug
# ---------------------------------------------------------------------------
async def test_der_vollabzug_laeuft_nach_der_einrichtung(hass, eintrag):
    """Die Reihenfolge, an der v0.5.0 scheiterte.

    Eingerichtet wird aus den Grunddaten; der vollständige Lauf kommt
    hinterher als Hintergrundaufgabe. Liefe er davor, stünde er im
    Zeitfenster des Abrufs und die Einrichtung fiele in die
    Zeitüberschreitung.
    """
    assert await _einrichten(hass, eintrag) is True

    client = AttrappenClient.letzte
    assert client.basic_aufgerufen == 1
    assert client.init_aufgerufen == 1
    # Und er hat wirklich etwas dazugefunden.
    assert len(client.devices) == len(ZUSAETZLICH)


async def test_der_vollabzug_legt_den_erkennungsstand_ab(hass, eintrag):
    """Sonst müsste die Anlage nach jedem Neustart 30 bis 120 s neu gelesen werden."""
    assert await _einrichten(hass, eintrag) is True

    gespeichert = hass.data[DOMAIN]["_discovery_cache"]
    assert gespeichert, "kein Erkennungsstand im Arbeitsspeicher"
    stand = next(iter(gespeichert.values()))
    assert len(stand["devices"]) == len(ZUSAETZLICH)


async def test_ein_gescheiterter_vollabzug_laesst_die_anlage_laufen(hass, eintrag):
    """Was schon eingelesen ist, bleibt nutzbar.

    Der Hintergrundlauf ist eine Ergänzung, keine Voraussetzung. Fällt er aus,
    darf er nicht den eingerichteten Eintrag mitnehmen.
    """
    from homeassistant.config_entries import ConfigEntryState

    class HalbKaputt(AttrappenClient):
        async def async_init(self, erzwingen: bool = False) -> None:
            self.init_aufgerufen += 1
            raise OSError("Verbindung abgebrochen")

    with patch("custom_components.heatnexus.WindhagerHttpClient", HalbKaputt):
        assert await hass.config_entries.async_setup(eintrag.entry_id) is True
        await hass.async_block_till_done()

    assert eintrag.state is ConfigEntryState.LOADED
    assert AttrappenClient.letzte.init_aufgerufen == 1


async def test_ein_abgebrochener_vollabzug_wird_nicht_als_fehler_gemeldet(hass, eintrag):
    """Beim Entladen wird die Hintergrundaufgabe abgebrochen – das ist normal."""

    class Abgebrochen(AttrappenClient):
        async def async_init(self, erzwingen: bool = False) -> None:
            self.init_aufgerufen += 1
            raise asyncio.CancelledError

    with patch("custom_components.heatnexus.WindhagerHttpClient", Abgebrochen):
        assert await hass.config_entries.async_setup(eintrag.entry_id) is True
        await hass.async_block_till_done()

    assert AttrappenClient.letzte.init_aufgerufen == 1


async def test_ein_bekannter_erkennungsstand_spart_das_neue_einlesen(hass, eintrag):
    """Zweite Einrichtung aus dem Arbeitsspeicher: kein Grundabruf, kein Vollabzug.

    Genau dafür gibt es den Zwischenspeicher – das Aktivieren einer einzelnen
    abgeschalteten Entität lädt den Eintrag neu, und das darf die Anlage nicht
    jedes Mal 30 bis 120 Sekunden lang beschäftigen.
    """
    assert await _einrichten(hass, eintrag) is True
    assert await hass.config_entries.async_unload(eintrag.entry_id) is True
    await hass.async_block_till_done()

    assert await _einrichten(hass, eintrag) is True

    zweiter = AttrappenClient.letzte
    assert zweiter.basic_aufgerufen == 0
    assert zweiter.init_aufgerufen == 0
    # Die Entitäten stehen trotzdem sofort bereit.
    assert len(zweiter.devices) == len(ZUSAETZLICH)


def test_eine_schaubildoption_allein_laedt_nicht_neu():
    """Ein Neuladen risse jeden Verlauf für einen Takt auf „nicht verfügbar"."""
    alt = {"192.0.2.10": {CONF_LEVELS: ["info"], CONF_MODULPUMPE: False}}
    neu = {"192.0.2.10": {CONF_LEVELS: ["info"], CONF_MODULPUMPE: True}}
    assert _nur_anzeige_geaendert(alt, neu) is True


def test_ein_geaenderter_umfang_laedt_neu():
    alt = {"192.0.2.10": {CONF_LEVELS: ["info"], CONF_KESSELART: "auto"}}
    neu = {"192.0.2.10": {CONF_LEVELS: ["info", "service"], CONF_KESSELART: "hackgut"}}
    assert _nur_anzeige_geaendert(alt, neu) is False


def test_ohne_bekannten_vorzustand_wird_neu_geladen():
    assert _nur_anzeige_geaendert({}, {"192.0.2.10": {CONF_MODULPUMPE: True}}) is False


def test_eine_neue_anlage_laedt_neu():
    alt = {"192.0.2.10": {CONF_MODULPUMPE: True}}
    neu = dict(alt, **{"192.0.2.11": {CONF_MODULPUMPE: True}})
    assert _nur_anzeige_geaendert(alt, neu) is False
