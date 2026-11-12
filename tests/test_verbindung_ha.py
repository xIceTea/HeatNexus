"""Verbindung je Steuerung: Bewertung nach dem Abruf, Reparatureintrag, Speicher, Sensoren."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from .conftest import ha_fehlt, requires_ha

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
    coordinator._verbindung_bewerten()
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


async def test_die_fehlerquote_erscheint_als_ganze_zahl(hass):
    uhr = Uhr()
    reihe = Messreihe(uhr=uhr)
    lauf = lauf_bauen(hass, ruhige_stunden())
    gestoert_bis_gemeldet(hass, lauf, reihe, uhr)
    assert eintrag(hass).translation_placeholders["fehlerquote"] == "50"
