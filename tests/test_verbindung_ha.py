"""Verbindung je Steuerung: Bewertung nach dem Abruf, Reparatureintrag, Speicher, Sensoren."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from .conftest import COMPONENT_DIR, ha_fehlt, requires_ha

pytestmark = requires_ha()

if not ha_fehlt():
    from homeassistant.helpers import issue_registry as ir

    from custom_components.heatnexus import verbindung as vb
    from custom_components.heatnexus.client.antwortzeit import IM_ABRUF, Messreihe
    from custom_components.heatnexus.const import DOMAIN
    from custom_components.heatnexus.coordinator import WindhagerDataUpdateCoordinator
    from custom_components.heatnexus.verbindung_lauf import (
        DAUER_MELDUNG_S,
        STORE_VERSION,
        VerbindungLauf,
        issue_key,
        store_key,
    )

HOST = "192.0.2.1"


class Uhr:
    """Eine Uhr, die nur auf Anweisung weiterläuft."""

    def __init__(self) -> None:  # noqa: D107
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def ruhige_stunden(anzahl=24, ms=100.0):
    return [vb.Stunde(f"2026-11-01T{i % 24:02d}", ms, 120, True) for i in range(anzahl)]


def lauf_bauen(hass, stunden=(), stunde=lambda: "2026-11-12T06"):
    store = MagicMock()
    store.async_save = AsyncMock()
    return VerbindungLauf(hass, "abc123", HOST, "Heizhaus", store, list(stunden), stunde=stunde)


def abruf(reihe, uhr, dauer_s=0.1, anzahl=30, fehler=0, schritt=30.0):
    """Ein Abruf: Uhr weiter, Antworten und Fehlantworten in die Reihe."""
    uhr.t += schritt
    token = IM_ABRUF.set(True)
    try:
        for _ in range(anzahl):
            reihe.antwort(dauer_s)
        for _ in range(fehler):
            reihe.fehler()
    finally:
        IM_ABRUF.reset(token)


async def test_ohne_bezug_sammelt_der_lauf(hass):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass)
    abruf(reihe, uhr)
    lauf.nach_abruf(reihe, 0)
    assert lauf.stand.zustand == vb.SAMMELT
    assert lauf.fenster.median_ms == pytest.approx(100.0)


async def test_mit_bezug_wird_eine_langsame_steuerung_traege(hass):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass, ruhige_stunden())
    abruf(reihe, uhr, dauer_s=0.1)
    lauf.nach_abruf(reihe, 0)
    assert lauf.stand.zustand == vb.STABIL
    for _ in range(40):
        abruf(reihe, uhr, dauer_s=0.5)
        lauf.nach_abruf(reihe, 0)
    assert lauf.stand.zustand == vb.TRAEGE
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_key("abc123", HOST)) is None


async def test_dauerhaft_gestoert_meldet_nach_dreissig_minuten(hass):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass, ruhige_stunden())
    abruf(reihe, uhr, anzahl=10, fehler=10)
    lauf.nach_abruf(reihe, 0)
    assert lauf.stand.zustand == vb.GESTOERT
    for _ in range(int(DAUER_MELDUNG_S / 30) - 1):
        abruf(reihe, uhr, anzahl=10, fehler=10)
        lauf.nach_abruf(reihe, 0)
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_key("abc123", HOST)) is None
    abruf(reihe, uhr, anzahl=10, fehler=10)
    lauf.nach_abruf(reihe, 0)
    eintrag = ir.async_get(hass).async_get_issue(DOMAIN, issue_key("abc123", HOST))
    assert eintrag is not None
    assert eintrag.translation_key == "verbindung_gestoert"
    assert eintrag.translation_placeholders["anlage"] == "Heizhaus"
    assert eintrag.severity == ir.IssueSeverity.WARNING


async def test_der_eintrag_verschwindet_bei_erholung_und_beim_entladen(hass):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass, ruhige_stunden())
    schritte = int(DAUER_MELDUNG_S / 30) + 2 + vb.GRENZE_LIEGEN + vb.BESTAETIGUNG
    for _ in range(schritte):
        abruf(reihe, uhr)
        lauf.nach_abruf(reihe, 9)
    assert lauf.stand.zustand == vb.UEBERLASTET
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_key("abc123", HOST)) is not None
    for _ in range(vb.BESTAETIGUNG):
        abruf(reihe, uhr)
        lauf.nach_abruf(reihe, 0)
    assert lauf.stand.zustand == vb.STABIL
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_key("abc123", HOST)) is None
    await lauf.async_entladen()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_key("abc123", HOST)) is None


async def test_stunde_wird_abgeschlossen_und_gespeichert(hass):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    stunde = ["2026-11-12T06"]
    lauf = lauf_bauen(hass, stunde=lambda: stunde[0])
    for _ in range(3):
        abruf(reihe, uhr, anzahl=30)
        lauf.nach_abruf(reihe, 0)
    stunde[0] = "2026-11-12T07"
    abruf(reihe, uhr)
    lauf.nach_abruf(reihe, 0)
    daten = lauf._store.async_delay_save.call_args.args[0]()
    # Die Antworten des Abrufs, der die Stunde abschließt, zählen noch zur alten Stunde.
    assert daten["stunden"][-1] == ["2026-11-12T06", 100.0, 120, True]


async def test_gespeicherte_stunden_ergeben_den_bezug(hass, hass_storage):
    hass_storage[store_key("abc123", HOST)] = {
        "version": STORE_VERSION,
        "key": store_key("abc123", HOST),
        "data": {
            "stunden": [[f"2026-11-01T{i:02d}", 200.0, 120, True] for i in range(24)]
            + [["2099-01-01T00", 1.0, 120, True], ["kaputt"]]
            + [["2026-11-01T00", "viel", 120, True], ["2026-11-01T00", 1.0, "x", True]]
            + [["2026-11-01T00", 1.0, None, True], ["2026-11-01T00", True, 120, True]]
        },
    }
    lauf = await VerbindungLauf.laden(hass, "abc123", HOST, "Heizhaus")
    assert lauf.bezug_ms == 200.0
    assert lauf.attribute()["gueltige_stunden"] == 24


async def test_stunden_ueberstehen_entladen_und_neues_laden(hass, hass_storage):
    from datetime import datetime, timedelta

    from homeassistant.helpers.storage import Store

    beginn = datetime(2026, 11, 1)
    stunden = [
        vb.Stunde((beginn + timedelta(hours=i)).strftime("%Y-%m-%dT%H"), 100.0 + i, 120, i % 5 != 0)
        for i in range(30)
    ] + [vb.Stunde("2026-11-02T06", None, 0, False)]
    store = Store(hass, STORE_VERSION, store_key("abc123", HOST))
    lauf = VerbindungLauf(hass, "abc123", HOST, "Heizhaus", store, stunden)
    await lauf.async_entladen()
    assert store_key("abc123", HOST) in hass_storage

    neu = await VerbindungLauf.laden(hass, "abc123", HOST, "Heizhaus")
    assert neu.diagnose()["stunden"] == lauf.diagnose()["stunden"]
    assert lauf.bezug_ms is not None
    assert neu.bezug_ms == lauf.bezug_ms
    assert neu.attribute()["gueltige_stunden"] == 24


@pytest.mark.parametrize("daten", [{"stunden": 5}, [["2026-11-01T00", 200.0, 120, True]]])
async def test_ein_kaputter_speicher_startet_leer(hass, hass_storage, caplog, daten):
    hass_storage[store_key("abc123", HOST)] = {
        "version": STORE_VERSION,
        "key": store_key("abc123", HOST),
        "data": daten,
    }
    lauf = await VerbindungLauf.laden(hass, "abc123", HOST, "Heizhaus")
    assert lauf.bezug_ms is None
    assert lauf.diagnose()["stunden"] == []
    assert "nicht lesbar" in caplog.text


async def test_koordinator_meldet_ob_der_abruf_gelang(hass):
    uhr = Uhr()
    coordinator, _ = ablauf_koordinator(hass, uhr)
    lauf = coordinator.verbindung
    lauf.nach_abruf = MagicMock(wraps=lauf.nach_abruf)
    await coordinator.async_refresh()
    assert lauf.nach_abruf.call_args.args[2] is True

    async def scheitert(budget=None):
        uhr.t += 30.0
        for _ in range(7):
            coordinator.client.messreihe.fehler()
        raise RuntimeError("keine Antwort")

    coordinator.client.fetch_all.side_effect = scheitert
    await coordinator.async_refresh()
    # Der erste Fehlschlag liefert die alten Werte; gelungen ist der Abruf trotzdem nicht.
    assert coordinator.last_update_success
    assert lauf.nach_abruf.call_args.args[2] is False
    assert lauf.fenster.fehler == 7


async def test_ein_gescheiterter_erster_abruf_zaehlt_seine_fehlantworten(hass):
    uhr = Uhr()
    coordinator, _ = ablauf_koordinator(hass, uhr)

    async def scheitert(budget=None):
        for _ in range(7):
            coordinator.client.messreihe.fehler()
        raise RuntimeError("keine Antwort")

    coordinator.client.fetch_all.side_effect = scheitert
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert coordinator.verbindung.fenster.fehler == 7


async def test_koordinator_bewertet_nach_jedem_abruf(hass):
    eintrag = MagicMock()
    eintrag.entry_id = "abc123"
    uhr = Uhr()
    client = MagicMock()
    client.auth_errors = 0
    client.erster_abruf = False
    client.noch_offen = 0
    client.messreihe = Messreihe(uhr=uhr)

    async def fetch_all(budget=None):
        uhr.t += 30.0
        for _ in range(25):
            client.messreihe.antwort(0.1)
        return {"oids": {}, "devices": []}

    client.fetch_all = AsyncMock(side_effect=fetch_all)
    coordinator = WindhagerDataUpdateCoordinator(hass, client, eintrag, HOST, "Heizhaus", 30)
    coordinator.verbindung = lauf_bauen(hass)
    await coordinator._async_update_data()
    assert coordinator.verbindung.fenster.antworten == 25
    assert IM_ABRUF.get() is False


async def test_diagnose_enthaelt_stunden(hass):
    lauf = lauf_bauen(hass, ruhige_stunden(2))
    daten = lauf.diagnose()
    assert daten["zustand"] == vb.SAMMELT
    assert len(daten["stunden"]) == 2


async def test_nur_der_abruf_selbst_zaehlt_fuer_die_antwortzeit(hass):
    eintrag = MagicMock()
    eintrag.entry_id = "abc123"
    client = MagicMock()
    client.auth_errors = 0
    client.erster_abruf = False
    client.strukturaenderung_abholen.return_value = True
    gesehen = {}

    async def fetch_all(budget=None):
        gesehen["abruf"] = IM_ABRUF.get()
        return {"oids": {}, "devices": []}

    client.fetch_all = AsyncMock(side_effect=fetch_all)
    coordinator = WindhagerDataUpdateCoordinator(hass, client, eintrag, HOST, "Heizhaus", 30)
    coordinator.bei_strukturaenderung = lambda: gesehen.setdefault("danach", IM_ABRUF.get())
    await coordinator._async_update_data()
    assert gesehen == {"abruf": True, "danach": False}


def eintrag(hass):
    return ir.async_get(hass).async_get_issue(DOMAIN, issue_key("abc123", HOST))


def nach_plan(monkeypatch, plan):
    """Die Regel liefert der Reihe nach die Zustände aus `plan`."""
    folge = iter(plan)
    monkeypatch.setattr(vb, "regel", lambda *_: next(folge))


def gestoert_bis_gemeldet(hass, lauf, reihe, uhr):
    for _ in range(int(DAUER_MELDUNG_S / 30) + 1):
        abruf(reihe, uhr, anzahl=10, fehler=10)
        lauf.nach_abruf(reihe, 0)
    assert eintrag(hass) is not None


async def test_entladen_nimmt_den_eintrag_zurueck_und_beendet_die_bewertung(hass):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass, ruhige_stunden())
    gestoert_bis_gemeldet(hass, lauf, reihe, uhr)
    await lauf.async_entladen()
    assert eintrag(hass) is None
    lauf._store.async_save.assert_awaited_once()
    gestoert_nach_entladen = int(DAUER_MELDUNG_S / 30) + 5
    for _ in range(gestoert_nach_entladen):
        abruf(reihe, uhr, anzahl=10, fehler=10)
        lauf.nach_abruf(reihe, 0)
    assert eintrag(hass) is None


async def test_abbruch_nach_dem_entladen_meldet_nichts(hass):
    uhr = Uhr()
    client = MagicMock()
    client.noch_offen = 0
    client.messreihe = Messreihe(uhr=uhr)
    coordinator = WindhagerDataUpdateCoordinator(hass, client, MagicMock(), HOST, "Heizhaus", 30)
    lauf = coordinator.verbindung = lauf_bauen(hass, ruhige_stunden())
    gestoert_bis_gemeldet(hass, lauf, client.messreihe, uhr)
    await lauf.async_entladen()
    abruf(client.messreihe, uhr, anzahl=10, fehler=10)
    coordinator._verbindung_bewerten(True)
    assert eintrag(hass) is None


async def test_ein_neuer_lauf_raeumt_einen_alten_eintrag_ab(hass):
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_key("abc123", HOST),
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="verbindung_gestoert",
    )
    lauf_bauen(hass)
    assert eintrag(hass) is None


async def test_ein_wechsel_ersetzt_den_eintrag_sofort(hass, monkeypatch):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass)
    schritte = int(DAUER_MELDUNG_S / 30) + 1
    nach_plan(monkeypatch, [vb.UEBERLASTET] * schritte + [vb.GESTOERT] * vb.BESTAETIGUNG)
    for _ in range(schritte):
        abruf(reihe, uhr)
        lauf.nach_abruf(reihe, 0)
    assert eintrag(hass).translation_key == "verbindung_ueberlastet"
    for _ in range(vb.BESTAETIGUNG):
        abruf(reihe, uhr)
        lauf.nach_abruf(reihe, 0)
    assert lauf.stand.zustand == vb.GESTOERT
    assert eintrag(hass).translation_key == "verbindung_gestoert"


async def test_wechselnde_probleme_melden_nach_dreissig_minuten(hass, monkeypatch):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass)
    block = [vb.UEBERLASTET] * 6 + [vb.GESTOERT] * 6
    nach_plan(monkeypatch, block * 10)
    schritte = int(DAUER_MELDUNG_S / 30)
    for _ in range(schritte):
        abruf(reihe, uhr)
        lauf.nach_abruf(reihe, 0)
    assert eintrag(hass) is None
    abruf(reihe, uhr)
    lauf.nach_abruf(reihe, 0)
    assert eintrag(hass) is not None


@pytest.mark.parametrize("sprache", ["de", "en", "nl"])
@pytest.mark.parametrize("schluessel", ["verbindung_ueberlastet", "verbindung_gestoert"])
async def test_reparaturtext_ohne_bezug_hat_keine_luecke(hass, sprache, schluessel):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass)
    abruf(reihe, uhr)
    lauf.nach_abruf(reihe, 0)
    datei = COMPONENT_DIR / "translations" / f"{sprache}.json"
    text = json.loads(datei.read_text(encoding="utf-8"))["issues"][schluessel]
    gefuellt = (text["title"] + text["description"]).format(**lauf._platzhalter())
    assert "–" not in gefuellt


def ausfall(lauf, reihe, uhr, abrufe):
    """Abrufe, die als Ganzes scheitern: nur Fehlantworten."""
    for _ in range(abrufe):
        abruf(reihe, uhr, anzahl=0, fehler=20)
        lauf.nach_abruf(reihe, 0, erfolgreich=False)


async def test_ein_ausfall_meldet_keine_gestoerte_verbindung(hass):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass, ruhige_stunden())
    ausfall(lauf, reihe, uhr, int(DAUER_MELDUNG_S / 30) + 10)
    assert lauf.stand.zustand == vb.GESTOERT
    assert eintrag(hass) is None
    # Nach der Rückkehr zählen nur die gelungenen Abrufe zur halben Stunde.
    for _ in range(int(DAUER_MELDUNG_S / 30) - 1):
        abruf(reihe, uhr, anzahl=10, fehler=10)
        lauf.nach_abruf(reihe, 0)
    assert eintrag(hass) is None
    abruf(reihe, uhr, anzahl=10, fehler=10)
    lauf.nach_abruf(reihe, 0)
    assert eintrag(hass) is not None


async def test_ein_ausfall_laesst_einen_bestehenden_eintrag_unveraendert(hass, monkeypatch):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass)
    schritte = int(DAUER_MELDUNG_S / 30) + 1
    nach_plan(monkeypatch, [vb.UEBERLASTET] * schritte + [vb.GESTOERT] * 10)
    for _ in range(schritte):
        abruf(reihe, uhr)
        lauf.nach_abruf(reihe, 0)
    ausfall(lauf, reihe, uhr, 10)
    assert lauf.stand.zustand == vb.GESTOERT
    assert eintrag(hass).translation_key == "verbindung_ueberlastet"


async def test_die_fehlerquote_erscheint_als_ganze_zahl(hass):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass, ruhige_stunden())
    gestoert_bis_gemeldet(hass, lauf, reihe, uhr)
    assert eintrag(hass).translation_placeholders["fehlerquote"] == "50"


def sensor_koordinator(lauf):
    """Ein Koordinator mit Kennung der Steuerung und diesem Lauf."""
    from types import SimpleNamespace

    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.client = SimpleNamespace(steuerung_kennung=lambda: "steuerung-SN1")
    coordinator.verbindung = lauf
    return coordinator


async def test_sensoren_am_geraet_steuerung(hass):
    from homeassistant.const import EntityCategory, UnitOfTime

    from custom_components.heatnexus.entity import steuerung_kennung
    from custom_components.heatnexus.sensor.verbindung import AntwortzeitSensor, VerbindungSensor

    coordinator = sensor_koordinator(lauf_bauen(hass, ruhige_stunden()))
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    abruf(reihe, uhr, dauer_s=0.12)
    coordinator.verbindung.nach_abruf(reihe, 0)

    zustand = VerbindungSensor(coordinator)
    zeit = AntwortzeitSensor(coordinator)
    kennung = steuerung_kennung(coordinator)
    assert kennung == "steuerung-SN1"
    assert zustand.unique_id == f"{kennung}-verbindung"
    assert zeit.unique_id == f"{kennung}-antwortzeit"
    assert zustand.options == list(vb.ZUSTAENDE)
    assert zustand.native_value == vb.STABIL
    assert zustand.extra_state_attributes["bezug_ms"] == 100
    assert zeit.native_value == 120
    assert zeit.native_unit_of_measurement == UnitOfTime.MILLISECONDS
    assert zustand.entity_category == EntityCategory.DIAGNOSTIC


async def test_antwortzeit_zeigt_den_letzten_abruf_die_bewertung_das_fenster(hass):
    from custom_components.heatnexus.sensor.verbindung import AntwortzeitSensor, VerbindungSensor

    coordinator = sensor_koordinator(lauf_bauen(hass, ruhige_stunden()))
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    abruf(reihe, uhr, dauer_s=0.1)
    coordinator.verbindung.nach_abruf(reihe, 0)
    abruf(reihe, uhr, dauer_s=0.3)
    coordinator.verbindung.nach_abruf(reihe, 0)

    attribute = VerbindungSensor(coordinator).extra_state_attributes
    assert AntwortzeitSensor(coordinator).native_value == 300
    assert attribute["abruf_ms"] == 300
    assert attribute["median_ms"] == 200


async def test_ein_abruf_ohne_antwort_hat_keine_antwortzeit(hass):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass)
    abruf(reihe, uhr)
    lauf.nach_abruf(reihe, 0)
    abruf(reihe, uhr, anzahl=0, fehler=5)
    lauf.nach_abruf(reihe, 0, erfolgreich=False)
    assert lauf.abruf_ms is None
    assert lauf.attribute()["abruf_ms"] is None


async def test_antwortzeit_ohne_genug_antworten_ist_leer(hass):
    from custom_components.heatnexus.sensor.verbindung import AntwortzeitSensor

    coordinator = sensor_koordinator(lauf_bauen(hass))
    assert AntwortzeitSensor(coordinator).native_value is None


async def test_nach_dem_entladen_behalten_die_sensoren_ihren_wert(hass):
    from custom_components.heatnexus.sensor.verbindung import AntwortzeitSensor, VerbindungSensor

    coordinator = sensor_koordinator(lauf_bauen(hass, ruhige_stunden()))
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    abruf(reihe, uhr, dauer_s=0.12)
    coordinator.verbindung.nach_abruf(reihe, 0)
    zustand, zeit = VerbindungSensor(coordinator), AntwortzeitSensor(coordinator)

    coordinator.verbindung = None
    zustand._auswerten()
    zeit._auswerten()
    assert zustand.native_value == vb.STABIL
    assert zeit.native_value == 120


def ablauf_koordinator(hass, uhr):
    """Ein echter Koordinator; jeder Abruf liefert dieselben Daten und 25 Antworten."""
    client = MagicMock()
    client.auth_errors = 0
    client.erster_abruf = False
    client.noch_offen = 0
    client.messreihe = Messreihe(uhr=uhr)
    client.steuerung_kennung = lambda: "steuerung-SN1"

    async def fetch_all(budget=None):
        uhr.t += 30.0
        for _ in range(25):
            client.messreihe.antwort(0.1)
        return {"oids": {}, "devices": []}

    client.fetch_all = AsyncMock(side_effect=fetch_all)
    eintrag = MagicMock()
    eintrag.entry_id = "abc123"
    coordinator = WindhagerDataUpdateCoordinator(hass, client, eintrag, HOST, "Heizhaus", 30)
    coordinator.verbindung = lauf_bauen(hass)
    return coordinator, fetch_all


async def sensoren_einbinden(hass, coordinator):
    """Beide Sensoren über eine Plattform in Home Assistant; zurück kommen Plattform und IDs."""
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry, MockEntityPlatform

    from custom_components.heatnexus.sensor.verbindung import AntwortzeitSensor, VerbindungSensor

    plattform = MockEntityPlatform(hass, domain="sensor", platform_name=DOMAIN)
    # Ein Gerät gehört in Home Assistant immer zu einem Config-Eintrag.
    eintrag = MockConfigEntry(domain=DOMAIN)
    eintrag.add_to_hass(hass)
    plattform.config_entry = eintrag
    await plattform.async_add_entities(
        [VerbindungSensor(coordinator), AntwortzeitSensor(coordinator)]
    )
    await hass.async_block_till_done()
    reg = er.async_get(hass)
    ids = [
        reg.async_get_entity_id("sensor", DOMAIN, f"steuerung-SN1-{endung}")
        for endung in ("verbindung", "antwortzeit")
    ]
    return plattform, *ids


async def test_sensoren_folgen_jedem_abruf_auch_bei_gleichen_daten(hass):
    uhr = Uhr()
    coordinator, _ = ablauf_koordinator(hass, uhr)
    _, verbindung, antwortzeit = await sensoren_einbinden(hass, coordinator)
    for runde in range(1, 4):
        await coordinator.async_refresh()
        assert hass.states.get(verbindung).attributes["antworten"] == 25 * runde
    assert float(hass.states.get(antwortzeit).state) == 100
    assert hass.states.get(verbindung).state == vb.SAMMELT


async def test_sensoren_folgen_der_verfuegbarkeit_und_melden_sich_ab(hass):
    uhr = Uhr()
    coordinator, fetch_all = ablauf_koordinator(hass, uhr)
    plattform, verbindung, antwortzeit = await sensoren_einbinden(hass, coordinator)
    await coordinator.async_refresh()
    assert hass.states.get(verbindung).state == vb.SAMMELT
    coordinator.client.fetch_all.side_effect = RuntimeError("keine Antwort")
    for _ in range(3):
        await coordinator.async_refresh()
    assert hass.states.get(verbindung).state == "unavailable"
    assert hass.states.get(antwortzeit).state == "unavailable"
    coordinator.client.fetch_all.side_effect = fetch_all
    await coordinator.async_refresh()
    assert hass.states.get(verbindung).state == vb.SAMMELT

    await plattform.async_reset()
    assert not coordinator.verbindung._zuhoerer


def test_die_sensoren_der_verbindung_gelten_nicht_als_verwaist():
    from types import SimpleNamespace

    from custom_components.heatnexus import verwaiste

    client = SimpleNamespace(steuerung_kennung=lambda: "steuerung-SN1", _vollstaendig=True)
    koordinatoren = {"a": SimpleNamespace(data={"devices": []}, client=client)}
    eintrag = SimpleNamespace(entry_id="abc123", options={}, data={}, subentries={})
    domaenen = verwaiste.erwartete_domaenen(eintrag, koordinatoren)
    bekannt = verwaiste.bekannte_kennungen(eintrag, koordinatoren)
    for kennung in ("steuerung-SN1-verbindung", "steuerung-SN1-antwortzeit"):
        assert domaenen[kennung] == "sensor"
        assert bekannt[kennung] is True


def test_diagnose_ohne_lauf_ist_leer():
    from custom_components.heatnexus.diagnostics import _verbindung

    coordinator = MagicMock()
    coordinator.verbindung = None
    assert _verbindung(coordinator) == {}


async def test_ein_gescheiterter_abruf_unterbricht_die_ueberlastung_nicht(hass):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass, ruhige_stunden())
    for _ in range(4):
        abruf(reihe, uhr)
        lauf.nach_abruf(reihe, 3)
    abruf(reihe, uhr, anzahl=0, fehler=5)
    lauf.nach_abruf(reihe, 0, erfolgreich=False)
    abruf(reihe, uhr)
    lauf.nach_abruf(reihe, 3)
    assert lauf.abrufe_mit_rest == 5


async def test_der_text_nennt_die_letzte_bekannte_antwortzeit(hass):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass)
    abruf(reihe, uhr, dauer_s=0.1)
    lauf.nach_abruf(reihe, 0)
    abruf(reihe, uhr, anzahl=10, schritt=1000.0)
    lauf.nach_abruf(reihe, 0)
    assert lauf.fenster.median_ms is None
    assert lauf._platzhalter()["median"] == "100"


async def test_ohne_gespeicherten_bezug_gilt_nach_einer_viertelstunde_ein_vorlaeufiger(hass):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass)
    abruf(reihe, uhr, dauer_s=0.1)
    lauf.nach_abruf(reihe, 0)
    assert lauf.stand.zustand == vb.SAMMELT
    for _ in range(int(vb.FENSTER_S / 30)):
        abruf(reihe, uhr, dauer_s=0.1)
        lauf.nach_abruf(reihe, 0)
    assert lauf.stand.zustand == vb.STABIL
    assert lauf.attribute()["bezug_ms"] == 100
    assert lauf.attribute()["bezug_vorlaeufig"] is True
    for _ in range(40):
        abruf(reihe, uhr, dauer_s=0.5)
        lauf.nach_abruf(reihe, 0)
    assert lauf.stand.zustand == vb.TRAEGE


async def test_ein_gespeicherter_bezug_gilt_sofort_und_nicht_vorlaeufig(hass):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass, ruhige_stunden())
    abruf(reihe, uhr, dauer_s=0.1)
    lauf.nach_abruf(reihe, 0)
    assert lauf.stand.zustand == vb.STABIL
    assert lauf.attribute()["bezug_vorlaeufig"] is False


async def test_der_vorlaeufige_bezug_uebersteht_einen_neustart(hass, hass_storage):
    from homeassistant.helpers.storage import Store

    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    store = Store(hass, STORE_VERSION, store_key("abc123", HOST))
    lauf = VerbindungLauf(hass, "abc123", HOST, "Heizhaus", store, [])
    for _ in range(int(vb.FENSTER_S / 30) + 1):
        abruf(reihe, uhr, dauer_s=0.1)
        lauf.nach_abruf(reihe, 0)
    assert lauf.attribute()["bezug_vorlaeufig"] is True
    await lauf.async_entladen()

    neu = await VerbindungLauf.laden(hass, "abc123", HOST, "Heizhaus")
    uhr2 = Uhr()
    reihe2 = Messreihe(uhr=uhr2)
    abruf(reihe2, uhr2, dauer_s=0.1)
    neu.nach_abruf(reihe2, 0)
    assert neu.stand.zustand == vb.STABIL
    assert neu.attribute()["bezug_ms"] == 100


@pytest.mark.parametrize("wert", [True, "x", -5, 0, None])
async def test_ein_unbrauchbarer_vorlaeufiger_bezug_zaehlt_nicht(hass, hass_storage, wert):
    hass_storage[store_key("abc123", HOST)] = {
        "version": STORE_VERSION,
        "key": store_key("abc123", HOST),
        "data": {"stunden": [], "vorlaeufig": wert},
    }
    lauf = await VerbindungLauf.laden(hass, "abc123", HOST, "Heizhaus")
    assert lauf.wirksamer_bezug is None
