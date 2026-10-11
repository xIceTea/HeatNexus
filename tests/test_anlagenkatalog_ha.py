"""Jede bekannte Anlage durch die volle Einrichtung bis zur fertigen Oberfläche.

Der Client spielt eine Testanlage aus `daten/anlagen/` nach; alles darüber ist
echt: Einrichtung, Vollabzug, Entitäten, Panel, Dashboard, Diagnose und der
Aufbau der Seite im Browser-Nachbau.
"""

from __future__ import annotations

import base64
from datetime import timedelta
from functools import partial
import json
import logging
from pathlib import Path
import re
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
        CONF_SPRACHE_ANLAGE,
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
# Dienstnamen haben dieselbe Form wie Entitäts-IDs, sind aber keine.
DIENSTE = {
    "press",
    "turn_on",
    "turn_off",
    "toggle",
    "select_option",
    "set_value",
    "set_temperature",
}


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


async def _einrichten(hass, anlage: str, umfang: str, sprache: str | None = None):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    optionen = _optionen(umfang) | ({CONF_SPRACHE_ANLAGE: sprache} if sprache else {})
    eintrag = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title="Anlage",
        data={
            "name": "Anlage",
            CONF_SYSTEMS: [{"host": HOST, "password": "x", "label": "Anlage"}],
        },
        options=optionen,
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
        and wert.split(".")[1] not in DIENSTE
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


# Karten der Übersicht je Testanlage, in der Reihenfolge Kessel, Puffer, Heizkreis, Warmwasser.
UEBERSICHT_ERWARTET = {
    "biowin-1403": ["leitwert", "kennwerte", *["tile", "kennwerte"] * 3],
    "biowin-1415-puffer": ["leitwert", "kennwerte", "puffer", "tile", "kennwerte"],
    "biowin-1415-touch2": ["leitwert", "kennwerte", "tile", "kennwerte"],
    "duowin": [
        *["leitwert", "kennwerte"] * 2,
        "puffer",
        *["tile", "kennwerte"] * 2,
        "kennwerte",
    ],
    "purowin-uml-puffer": ["leitwert", "kennwerte", "puffer", "tile", "kennwerte"],
    "uml-puffer": ["puffer", "tile", "kennwerte"],
}


@pytest.mark.parametrize("anlage", anlagen())
async def test_die_uebersicht_zeigt_jede_testanlage_nach_rollen(hass, anlage):
    from custom_components.heatnexus.dashboard import uebersicht
    from custom_components.heatnexus.dashboard.anlagen import anlagen_lesen

    eintrag = await _einrichten(hass, anlage, "betreiber")
    try:
        [gelesen] = anlagen_lesen(hass)
        zweite = {**gelesen, "id": "zweite0123456789", "name": "Zweite"}
        seite = uebersicht.uebersicht([gelesen, zweite], als_karte=True, badges=[])
        [abschnitt, *_] = [s for s in seite["sections"] if s["cards"][0].get("heading") == "Anlage"]
        typen = [str(k["type"]).removeprefix("custom:heatnexus-") for k in abschnitt["cards"]]
        assert typen[:2] == ["heading", "schaubild"]
        assert typen[2:] == UEBERSICHT_ERWARTET[anlage]
        fremd = sorted(_entitaeten_in(abschnitt, set()) - set(hass.states.async_entity_ids()))
        assert not fremd, fremd[:10]
    finally:
        await _abbauen(hass, eintrag)


async def test_die_uebersicht_steht_bei_einer_anlage_vorn(hass):
    from custom_components.heatnexus.dashboard import dashboard_konfiguration
    from custom_components.heatnexus.dashboard.anlagen import anlagen_lesen
    from custom_components.heatnexus.dashboard.karten import pfad_anlage

    eintrag = await _einrichten(hass, "purowin-uml-puffer", "betreiber")
    try:
        [gelesen] = anlagen_lesen(hass)
        erste, zweite, *_ = dashboard_konfiguration(hass, als_karte=True)["views"]
        assert erste["path"] == "uebersicht"
        koepfe = [s["cards"][0].get("heading") for s in erste["sections"]]
        assert gelesen["name"] in koepfe
        assert erste["badges"]
        assert zweite["path"] == pfad_anlage(gelesen)
    finally:
        await _abbauen(hass, eintrag)


def _texte_im_bild(svg: str) -> list[str]:
    return re.findall(r"<text[^>]*>([^<]*)</text>", svg)


def _bild_aus_adresse(adresse: str) -> str:
    return base64.b64decode(adresse.split(",", 1)[1]).decode("utf-8")


def _schaubilder(hass) -> list[str]:
    """Jedes Schaubild-SVG: Karte, Oberfläche und festes Bild der Übersicht."""
    from custom_components.heatnexus.dashboard import dashboard_konfiguration
    from custom_components.heatnexus.karte import kartendaten
    from custom_components.heatnexus.panel import panel_daten

    bilder = [a["schema_svg"] for a in kartendaten(hass)]
    bilder += [a["schema_svg"] for a in panel_daten(hass)["anlagen"]]
    fest = json.dumps(dashboard_konfiguration(hass, als_karte=False))
    bilder += [_bild_aus_adresse(a) for a in re.findall(r'"dark_mode_image": "([^"]+)"', fest)]
    return [b for b in bilder if b]


async def _werksnamen_deutsch(hass, eintrag, buch) -> None:
    """Gerätenamen auf den deutschen Werksnamen zurücksetzen, wie nach einem Sprachwechsel."""
    from homeassistant.helpers import device_registry as dr

    deutsch = {fremd: de for de, fremd in buch.fuer_frontend.items()}
    register = dr.async_get(hass)
    for geraet in dr.async_entries_for_config_entry(register, eintrag.entry_id):
        if (name := deutsch.get(geraet.name or "")) is not None:
            register.async_update_device(geraet.id, name=name)


# Wörter deutscher Werksnamen, die in keiner anderen Sprache im Bild stehen dürfen.
WERKSDEUTSCH = re.compile(r"Warmwasser|Pelletskessel|Puffer|Kessel|Heizkreis|Zirkulation")


@pytest.mark.parametrize(("anlage", "sprache"), [("biowin-1403", "en"), ("duowin", "nl")])
async def test_das_schaubild_beschriftet_in_der_sprache_der_anlage(hass, anlage, sprache):
    """Kein deutscher Werksname bleibt im Bild einer Anlage mit eigener Sprache."""
    from custom_components.heatnexus.texte import Woerterbuch

    hass.config.language = "de"
    buch = Woerterbuch(sprache)
    eintrag = await _einrichten(hass, anlage, "betreiber", sprache)
    try:
        await _werksnamen_deutsch(hass, eintrag, buch)
        bilder = _schaubilder(hass)
        assert len(bilder) >= 3
        for svg in bilder:
            texte = _texte_im_bild(svg)
            assert texte
            deutsch = [t for t in texte if buch(t) != t or WERKSDEUTSCH.search(t)]
            assert not deutsch, deutsch
    finally:
        await _abbauen(hass, eintrag)
