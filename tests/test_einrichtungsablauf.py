"""Einrichtungsdialog, Neu konfigurieren und Neu anmelden im laufenden Home Assistant.

Der Client ist die Attrappe aus `test_einrichtung.py`; geprüft wird, was die
Abläufe am Eintrag hinterlassen.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from .conftest import ha_fehlt, requires_frontend, requires_ha, requires_moderne_ha
from .test_einrichtung import AttrappenClient

pytestmark = [requires_ha(), requires_frontend(), requires_moderne_ha()]

if not ha_fehlt():  # pragma: no branch - ohne HA wird die Datei übersprungen
    from custom_components.heatnexus.const import (
        CONF_SPRACHE,
        CONF_SPRACHE_ANLAGE,
        CONF_SYSTEMS,
        DOMAIN,
        SPRACHE_WIE_HEATNEXUS,
    )

ALT = "192.0.2.10"
NEU = "192.0.2.20"
KENNUNG = "0000ABCD1234"
STRUKTUR = [{"nodeId": 15, "neuronId": KENNUNG, "functions": []}]


@pytest.fixture(autouse=True)
def _eigene_integration(enable_custom_integrations):
    """Ohne diesen Schalter legt die Testumgebung eigene Integrationen nicht vor."""
    return enable_custom_integrations


@pytest.fixture(autouse=True)
async def _aufraeumen(hass):
    """Zeitgeber ablaufen lassen und jeden geladenen Eintrag entladen."""
    yield

    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    from custom_components.heatnexus.einlesen import MELDUNG_VERZOEGERUNG

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=MELDUNG_VERZOEGERUNG + 1))
    await hass.async_block_till_done()
    for geladen in hass.config_entries.async_entries(DOMAIN):
        if geladen.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(geladen.entry_id)
    await hass.async_block_till_done()


def _verbindung(struktur: list | None = None, fehler: Exception | None = None) -> AsyncMock:
    """Die Prüfung der Verbindung, ohne ins Netz zu gehen."""
    if fehler is not None:
        return AsyncMock(side_effect=fehler)
    return AsyncMock(return_value=STRUKTUR if struktur is None else struktur)


@pytest.fixture
def eintrag(hass):
    """Ein Eintrag mit einer Steuerung, wie ihn der Dialog anlegt."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    eintrag = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=2,
        title="Heizhaus",
        unique_id=KENNUNG,
        data={
            "name": "Heizhaus",
            CONF_SYSTEMS: [
                {"host": ALT, "password": "geheim", "label": "Heizhaus", "username": "USER"}
            ],
        },
        options={ALT: {"levels": ["info", "operate"]}, CONF_SPRACHE: "auto"},
    )
    eintrag.add_to_hass(hass)
    return eintrag


async def _einrichten(hass, eintrag) -> None:
    with patch("custom_components.heatnexus.WindhagerHttpClient", AttrappenClient):
        assert await hass.config_entries.async_setup(eintrag.entry_id) is True
        await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# Neue Einrichtung
# ---------------------------------------------------------------------------
async def _neu_einrichten(hass) -> Any:
    """Den Einrichtungsdialog einmal ganz durchlaufen."""
    with (
        patch("custom_components.heatnexus.config_flow.validate_connection", _verbindung()),
        patch("custom_components.heatnexus.WindhagerHttpClient", AttrappenClient),
    ):
        ablauf = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        ablauf = await hass.config_entries.flow.async_configure(
            ablauf["flow_id"], {"name": "Heizhaus", "count": 1}
        )
        ablauf = await hass.config_entries.flow.async_configure(
            ablauf["flow_id"],
            {"label": "Heizhaus", "host": ALT, "username": "USER", "password": "geheim"},
        )
        ablauf = await hass.config_entries.flow.async_configure(ablauf["flow_id"], {})
        await hass.async_block_till_done()
    return ablauf["result"]


@pytest.mark.parametrize("ha_sprache", ["en", "nl"])
async def test_ein_frischer_eintrag_folgt_der_sprache_von_home_assistant(hass, ha_sprache):
    """Die Umstellung alter Einträge darf einen neuen nicht auf Deutsch festlegen."""
    from custom_components.heatnexus.texte import sprache_des_eintrags

    hass.config.language = ha_sprache

    eintrag = await _neu_einrichten(hass)

    assert eintrag.options[CONF_SPRACHE_ANLAGE] == SPRACHE_WIE_HEATNEXUS
    assert sprache_des_eintrags(hass, eintrag) == ha_sprache


# ---------------------------------------------------------------------------
# Neu konfigurieren
# ---------------------------------------------------------------------------
async def _neu_konfigurieren(hass, eintrag, host: str = NEU, verbindung=None) -> dict:
    """Die Adresse der Steuerung im Dialog ändern; zurück kommt das Ergebnis des Schritts."""
    with (
        patch(
            "custom_components.heatnexus.config_flow.validate_connection",
            verbindung or _verbindung(),
        ),
        patch("custom_components.heatnexus.WindhagerHttpClient", AttrappenClient),
    ):
        ablauf = await eintrag.start_reconfigure_flow(hass)
        ergebnis = await hass.config_entries.flow.async_configure(
            ablauf["flow_id"], {"anlage": ALT, "host": host, "username": "USER"}
        )
        await hass.async_block_till_done()
    return ergebnis


def _neuladen_zaehlen(hass) -> list[str]:
    """Jedes Neuladen eines Eintrags mitschreiben, ohne es zu verhindern."""
    aufrufe: list[str] = []
    original = hass.config_entries.async_reload

    async def zaehlen(entry_id: str) -> bool:
        aufrufe.append(entry_id)
        return await original(entry_id)

    hass.config_entries.async_reload = zaehlen
    return aufrufe


async def test_neu_konfigurieren_zieht_mit_adresse_und_optionen_um(hass, eintrag):
    await _einrichten(hass, eintrag)

    ergebnis = await _neu_konfigurieren(hass, eintrag)

    assert ergebnis["type"] == "abort"
    assert ergebnis["reason"] == "reconfigure_successful"
    assert [s["host"] for s in eintrag.data[CONF_SYSTEMS]] == [NEU]
    assert NEU in eintrag.options and ALT not in eintrag.options


async def test_neu_konfigurieren_laedt_den_eintrag_einmal(hass, eintrag):
    """Der Update-Listener lädt neu; ein zweites Neuladen aus dem Ablauf kostet einen Abruf."""
    await _einrichten(hass, eintrag)
    aufrufe = _neuladen_zaehlen(hass)

    await _neu_konfigurieren(hass, eintrag)

    assert aufrufe == [eintrag.entry_id]


async def test_neu_konfigurieren_gilt_nicht_als_abwahl(hass, eintrag):
    """Eine neue Adresse wählt nichts ab; verwaiste Entitäten werden nur stillgelegt."""
    await _einrichten(hass, eintrag)
    abwahl: list[bool] = []

    def merken(_hass, _entry) -> None:
        abwahl.append(True)

    with patch("custom_components.heatnexus.abwahl_vormerken", merken):
        await _neu_konfigurieren(hass, eintrag)

    assert not abwahl


async def test_neu_konfigurieren_lehnt_eine_andere_steuerung_ab(hass, eintrag):
    fremd = [{"nodeId": 15, "neuronId": "0000FFFF0000", "functions": []}]
    ergebnis = await _neu_konfigurieren(hass, eintrag, verbindung=_verbindung(fremd))

    assert ergebnis["type"] == "form"
    assert ergebnis["errors"] == {"base": "andere_steuerung"}
    assert [s["host"] for s in eintrag.data[CONF_SYSTEMS]] == [ALT]


async def test_neu_konfigurieren_lehnt_eine_vergebene_adresse_ab(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    zwei = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=2,
        title="Zwei",
        unique_id=f"{KENNUNG}-0000BBBB0000",
        data={
            "name": "Zwei",
            CONF_SYSTEMS: [
                {"host": ALT, "password": "geheim", "label": "Haus A"},
                {"host": NEU, "password": "geheim", "label": "Haus B"},
            ],
        },
        options={},
    )
    zwei.add_to_hass(hass)

    ergebnis = await _neu_konfigurieren(hass, zwei)

    assert ergebnis["errors"] == {"base": "already_configured"}
    assert [s["host"] for s in zwei.data[CONF_SYSTEMS]] == [ALT, NEU]


async def test_neu_konfigurieren_meldet_einen_unerwarteten_fehler(hass, eintrag):
    ergebnis = await _neu_konfigurieren(
        hass, eintrag, verbindung=_verbindung(fehler=RuntimeError("kaputt"))
    )

    assert ergebnis["type"] == "form"
    assert ergebnis["errors"] == {"base": "unknown"}


async def test_neu_konfigurieren_raeumt_hinweise_und_erkennungsstand_der_alten_adresse_ab(
    hass, eintrag
):
    from homeassistant.helpers import issue_registry as ir
    from homeassistant.helpers.storage import Store

    from custom_components.heatnexus.const import DISCOVERY_STORE_VERSION
    from custom_components.heatnexus.erkennungsstand import store_key

    await _einrichten(hass, eintrag)
    for praefix in ("nicht_erreichbar", "sprache_neustart"):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{praefix}_{eintrag.entry_id}_{ALT}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=praefix,
        )
    alter_stand = Store(hass, DISCOVERY_STORE_VERSION, store_key(eintrag, ALT))
    await alter_stand.async_save({"data": {}})

    await _neu_konfigurieren(hass, eintrag)

    offen = [k for (domaene, k) in ir.async_get(hass).issues if domaene == DOMAIN]
    assert not [k for k in offen if k.endswith(f"_{ALT}")]
    assert await alter_stand.async_load() is None


# ---------------------------------------------------------------------------
# Neu anmelden
# ---------------------------------------------------------------------------
async def _neu_anmelden(hass, eintrag, verbindung=None) -> dict:
    with (
        patch(
            "custom_components.heatnexus.config_flow.validate_connection",
            verbindung or _verbindung(),
        ),
        patch("custom_components.heatnexus.WindhagerHttpClient", AttrappenClient),
    ):
        ablauf = await eintrag.start_reauth_flow(hass)
        ergebnis = await hass.config_entries.flow.async_configure(
            ablauf["flow_id"], {"host": ALT, "username": "USER", "password": "neu"}
        )
        await hass.async_block_till_done()
    return ergebnis


async def test_neu_anmelden_laedt_den_eintrag_einmal(hass, eintrag):
    await _einrichten(hass, eintrag)
    aufrufe = _neuladen_zaehlen(hass)

    ergebnis = await _neu_anmelden(hass, eintrag)

    assert ergebnis["reason"] == "reauth_successful"
    assert eintrag.data[CONF_SYSTEMS][0]["password"] == "neu"
    assert aufrufe == [eintrag.entry_id]


async def test_neu_anmelden_laedt_einen_nicht_geladenen_eintrag(hass, eintrag):
    """Ohne geladenen Eintrag gibt es keinen Update-Listener; der Ablauf lädt selbst."""
    aufrufe = _neuladen_zaehlen(hass)

    await _neu_anmelden(hass, eintrag)

    assert aufrufe == [eintrag.entry_id]


async def test_neu_anmelden_meldet_einen_unerwarteten_fehler(hass, eintrag):
    ergebnis = await _neu_anmelden(
        hass, eintrag, verbindung=_verbindung(fehler=RuntimeError("kaputt"))
    )

    assert ergebnis["errors"] == {"base": "unknown"}


# ---------------------------------------------------------------------------
# Entfernen
# ---------------------------------------------------------------------------
async def test_entfernen_raeumt_die_hinweise_des_eintrags_ab(hass, eintrag):
    from homeassistant.helpers import issue_registry as ir

    await _einrichten(hass, eintrag)
    for kennung in (
        f"nicht_erreichbar_{eintrag.entry_id}_{ALT}",
        f"sprache_neustart_{eintrag.entry_id}_{ALT}",
        # Eine Adresse, die der Eintrag nicht mehr führt.
        f"nicht_erreichbar_{eintrag.entry_id}_192.0.2.99",
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            kennung,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="nicht_erreichbar",
        )

    await hass.config_entries.async_remove(eintrag.entry_id)
    await hass.async_block_till_done()

    offen = [k for (domaene, k) in ir.async_get(hass).issues if domaene == DOMAIN]
    assert not [k for k in offen if eintrag.entry_id in k]
