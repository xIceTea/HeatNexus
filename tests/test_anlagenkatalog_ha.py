"""Jede bekannte Anlage durch die volle Einrichtung bis zur fertigen Oberfläche.

Der Client spielt eine Testanlage aus `daten/anlagen/` nach; alles darüber ist
echt: Einrichtung, Vollabzug, Entitäten, Panel, Dashboard, Diagnose und der
Aufbau der Seite im Browser-Nachbau.
"""

from __future__ import annotations

from datetime import timedelta
from functools import partial
import json
import logging
from pathlib import Path
import shutil
import subprocess
from unittest.mock import patch

import pytest

from .anlagenkatalog import HOST, Nachspiel, anlagen
from .conftest import ha_fehlt, requires_frontend, requires_ha, requires_moderne_ha

pytestmark = [requires_ha(), requires_frontend(), requires_moderne_ha()]

if not ha_fehlt():  # pragma: no branch - ohne HA wird die Datei übersprungen
    from custom_components.heatnexus import WindhagerHttpClient
    from custom_components.heatnexus.const import (
        CONF_ENABLE_ADVANCED,
        CONF_LEVELS,
        CONF_PANEL,
        CONF_SYSTEMS,
        CONF_WRITABLE_ADVANCED,
        DOMAIN,
    )

WURZEL = Path(__file__).parent.parent
PANEL_JS = WURZEL / "custom_components" / "heatnexus" / "frontend" / "heatnexus-panel.js"
AUFBAU = Path(__file__).parent / "js" / "oberflaeche-aufbau.mjs"
UMFAENGE = {
    "betreiber": {"levels": ["info", "operate"]},
    "alles": {"levels": ["info", "operate", "service", "oem"], "advanced": True},
}
FAELLE = [(a, u) for a in anlagen() for u in UMFAENGE]
BEREICHE = ("sensor", "binary_sensor", "switch", "select", "number", "button", "climate", "time")


@pytest.fixture(autouse=True)
def _eigene_integration(enable_custom_integrations):
    """Die Testumgebung lädt eigene Integrationen nur auf ausdrücklichen Wunsch."""
    return enable_custom_integrations


def _optionen(umfang: str) -> dict:
    wahl = UMFAENGE[umfang]
    je_anlage = {CONF_LEVELS: wahl["levels"]}
    if wahl.get("advanced"):
        je_anlage |= {CONF_ENABLE_ADVANCED: True, CONF_WRITABLE_ADVANCED: True}
    return {HOST: je_anlage, CONF_PANEL: True}


def _client_fuer(anlage: str):
    class NachspielClient(WindhagerHttpClient):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            Nachspiel(anlage).einsetzen(self)

    return NachspielClient


async def _einrichten(hass, anlage: str, umfang: str):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    eintrag = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title="Anlage",
        data={
            "name": "Anlage",
            CONF_SYSTEMS: [{"host": HOST, "password": "x", "label": "Anlage"}],
        },
        options=_optionen(umfang),
    )
    eintrag.add_to_hass(hass)
    with patch("custom_components.heatnexus.WindhagerHttpClient", _client_fuer(anlage)):
        assert await hass.config_entries.async_setup(eintrag.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    return eintrag


async def _abbauen(hass, eintrag) -> None:
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    from custom_components.heatnexus.einlesen import MELDUNG_VERZOEGERUNG

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=MELDUNG_VERZOEGERUNG + 1))
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(eintrag.entry_id)
    await hass.async_block_till_done()


def _entitaeten_in(wert, gefunden: set[str]) -> set[str]:
    if isinstance(wert, dict):
        for inhalt in wert.values():
            _entitaeten_in(inhalt, gefunden)
    elif isinstance(wert, list):
        for inhalt in wert:
            _entitaeten_in(inhalt, gefunden)
    elif (
        isinstance(wert, str)
        and wert.count(".") == 1
        and wert.split(".")[0] in BEREICHE
        and " " not in wert
    ):
        gefunden.add(wert)
    return gefunden


@pytest.mark.parametrize(("anlage", "umfang"), FAELLE)
async def test_die_volle_kette_steht(hass, caplog, tmp_path, anlage, umfang):
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    from custom_components.heatnexus.dashboard import dashboard_konfiguration
    from custom_components.heatnexus.diagnostics import async_get_config_entry_diagnostics
    from custom_components.heatnexus.panel import panel_daten

    caplog.set_level(logging.WARNING)
    eintrag = await _einrichten(hass, anlage, umfang)
    try:
        register = er.async_get(hass)
        eintraege = er.async_entries_for_config_entry(register, eintrag.entry_id)
        assert eintraege, "keine Entität angelegt"

        # Jede eingeschaltete Entität hat einen Zustand; eine Auswahl steht auf einer ihrer Optionen.
        ohne_zustand, falsche_auswahl = [], []
        for e in eintraege:
            if e.disabled_by:
                continue
            zustand = hass.states.get(e.entity_id)
            if zustand is None:
                ohne_zustand.append(e.entity_id)
            elif (
                e.domain == "select"
                and zustand.state not in ("unknown", "unavailable")
                and zustand.state not in zustand.attributes.get("options", [])
            ):
                falsche_auswahl.append(f"{e.entity_id}={zustand.state}")
        assert not ohne_zustand, ohne_zustand[:10]
        assert not falsche_auswahl, falsche_auswahl[:10]

        # Panel: Jede genannte Entität existiert; eine Ladetaste liest den Teil ihres Auslösers.
        daten = panel_daten(hass)
        assert daten["anlagen"], "das Panel kennt keine Anlage"
        bekannt = {e.entity_id for e in eintraege} | set(hass.states.async_entity_ids())
        fremd = sorted(_entitaeten_in(daten, set()) - bekannt)
        assert not fremd, fremd[:10]
        geraet = {e.entity_id: e.device_id for e in eintraege}
        for a in daten["anlagen"]:
            tasten = list(a.get("schnellzugriff") or [])
            ww = (a.get("steuerung") or {}).get("warmwasser") or {}
            if ww.get("taste"):
                tasten.append(ww["taste"])
            for taste in tasten:
                if taste.get("zustand_wenn") is None:
                    continue
                for quelle in ("zustand_an", "zustand_pumpe", "betriebswahl"):
                    if taste.get(quelle):
                        assert geraet.get(taste[quelle]) == geraet.get(taste["entity"]), (
                            taste["titel"],
                            quelle,
                            taste[quelle],
                        )
                if taste["entity"].startswith("select."):
                    assert taste.get("ein_option") and taste.get("aus_option"), taste

        # Dashboard und Diagnose bauen sich auf.
        konfiguration = dashboard_konfiguration(hass)
        assert konfiguration.get("views"), "das Dashboard hat keine Ansicht"
        fremd = sorted(_entitaeten_in(konfiguration, set()) - bekannt)
        assert not fremd, fremd[:10]
        assert await async_get_config_entry_diagnostics(hass, eintrag)
        assert len(dr.async_entries_for_config_entry(dr.async_get(hass), eintrag.entry_id)) >= 2

        # Die Seite baut sich im Browser-Nachbau mit genau diesen Daten auf.
        if shutil.which("node"):
            datei = tmp_path / "daten.json"
            zustaende = {
                z.entity_id: {
                    "entity_id": z.entity_id,
                    "state": z.state,
                    "attributes": dict(z.attributes),
                }
                for z in hass.states.async_all()
            }
            eingabe = {"daten": daten, "states": zustaende}
            datei.write_text(json.dumps(eingabe, default=str), encoding="utf-8")
            lauf = await hass.async_add_executor_job(
                partial(
                    subprocess.run,
                    ["node", str(AUFBAU), str(PANEL_JS), str(datei)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
            )
            assert lauf.returncode == 0, lauf.stderr[-3000:]
            seite = json.loads(lauf.stdout)
            assert seite["uebersicht"]["karten"] > 0
            assert seite["steuerung"]["karten"] > 0

        meldungen = [
            f"{r.name}: {r.getMessage()[:200]}"
            for r in caplog.records
            if r.levelno >= logging.WARNING and ("heatnexus" in r.name or "entity" in r.name)
        ]
        assert not meldungen, meldungen[:10]
    finally:
        await _abbauen(hass, eintrag)
