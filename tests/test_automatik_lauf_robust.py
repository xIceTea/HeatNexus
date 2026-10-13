"""Automatik zur Laufzeit: Start, Nebenläufigkeit, Speichern und Ausfälle in Home Assistant."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from . import test_automatik_ha as ha
from .conftest import requires_ha

pytestmark = requires_ha()

anlage = ha.anlage


async def _schaltend(hass, verwaltung, freezer):
    """Eine eingerichtete Automatik, die an die Steuerung schreibt."""
    freezer.move_to(ha.MORGEN)
    laufzeit = await ha._eingerichtet(hass, verwaltung)
    await hass.async_block_till_done(wait_background_tasks=True)
    laufzeit.konfig = {**laufzeit.konfig, "modus": "schalten"}
    return laufzeit


def _laufende_pause(laufzeit, coordinator, soll: float = 17.0):
    """Eine eigene Heizpause, wie die Steuerung sie zeigt."""
    from homeassistant.util import dt as dt_util

    from custom_components.heatnexus.automatik import regel

    jetzt = dt_util.now()
    laufzeit.gedaechtnis = regel.Gedaechtnis(
        absenkung_art=regel.PAUSE,
        absenkung_von=jetzt - timedelta(hours=1),
        absenkung_bis=jetzt + timedelta(hours=2),
        absenkung_basis=21.0,
        absenkung_soll=soll,
    )
    coordinator.data["oids"][f"{ha.PREFIX}/1/1/0"] = f"{soll:.1f}"
    coordinator.data["oids"][f"{ha.PREFIX}/2/10/0"] = "120"
    return laufzeit.gedaechtnis


def _entscheidung_festlegen(monkeypatch, *aktionen):
    """Die Regel entscheidet immer gleich: eine erneuerte Pause mit 18 °C."""
    from custom_components.heatnexus.automatik import regel

    def entscheiden(lage, g, _werte):
        neu = replace(g, absenkung_soll=18.0)
        return regel.Entscheidung(regel.Zustand.HEIZPAUSE, aktionen, "Heizpause.", neu)

    monkeypatch.setattr(regel, "entscheiden", entscheiden)


def _ablehnen(laufzeit, coordinator, *adressen: str, ab: int = 0):
    """Die Steuerung des Stellers lehnt die Adressen ab, `3/4` erst nach `ab` Schreibvorgängen."""
    client = coordinator.client
    temperatur = []

    async def update(oid: str, wert: str) -> None:
        if oid.endswith("/3/4/0"):
            temperatur.append(wert)
            if len(temperatur) > ab and "/3/4/0" in adressen:
                raise RuntimeError("abgelehnt")
        elif any(oid.endswith(a) for a in adressen):
            raise RuntimeError("abgelehnt")
        client.geschrieben.append((oid, wert))

    laufzeit.steller._schreiben = update


# --- Halb geschriebene Absenkung --------------------------------------------
async def test_halb_geschriebene_pause_stellt_den_raumsoll_zurueck(
    hass, anlage, freezer, monkeypatch
):
    from custom_components.heatnexus.automatik import regel

    verwaltung, coordinator = anlage
    laufzeit = await _schaltend(hass, verwaltung, freezer)
    vorher = _laufende_pause(laufzeit, coordinator)
    aktion = regel.Aktion("pause", soll=18.0, minuten=400, erneuern=True)
    _entscheidung_festlegen(monkeypatch, aktion)
    _ablehnen(laufzeit, coordinator, "/2/10/0")
    coordinator.client.geschrieben.clear()

    await laufzeit.auswerten()

    temperatur = [w for oid, w in coordinator.client.geschrieben if oid.endswith("/3/4/0")]
    assert temperatur == ["18.0", "17.0"]
    assert laufzeit.gedaechtnis == vorher


async def test_bleibt_der_neue_raumsoll_stehen_kennt_ihn_das_gedaechtnis(
    hass, anlage, freezer, monkeypatch
):
    from custom_components.heatnexus.automatik import regel

    verwaltung, coordinator = anlage
    laufzeit = await _schaltend(hass, verwaltung, freezer)
    _laufende_pause(laufzeit, coordinator)
    aktion = regel.Aktion("pause", soll=18.0, minuten=400, erneuern=True)
    _entscheidung_festlegen(monkeypatch, aktion)
    _ablehnen(laufzeit, coordinator, "/2/10/0", "/3/4/0", ab=1)

    await laufzeit.auswerten()

    assert laufzeit.gedaechtnis.absenkung_soll == 18.0
    assert regel.absenkung_laeuft(laufzeit.gedaechtnis, laufzeit.lage.jetzt)


# --- Läufe nacheinander -----------------------------------------------------
def _absenkung_festlegen(monkeypatch):
    """Die Regel beginnt immer eine Absenkung auf 19 °C für drei Stunden."""
    from homeassistant.util import dt as dt_util

    from custom_components.heatnexus.automatik import regel

    def entscheiden(lage, g, _werte):
        if regel.absenkung_laeuft(g, lage.jetzt):
            return regel.Entscheidung(regel.Zustand.SONNENTAG, (), "Sonnentag.", g)
        jetzt = dt_util.now()
        neu = regel.Gedaechtnis(
            absenkung_art=regel.SONNE,
            absenkung_von=jetzt,
            absenkung_bis=jetzt + timedelta(hours=3),
            absenkung_basis=21.0,
            absenkung_soll=19.0,
        )
        aktion = regel.Aktion("absenken", soll=19.0, minuten=180)
        return regel.Entscheidung(regel.Zustand.SONNENTAG, (aktion,), "Sonnentag.", neu)

    monkeypatch.setattr(regel, "entscheiden", entscheiden)


def _aufhalten(laufzeit):
    """Der nächste Schreibvorgang wartet, bis das zurückgegebene Ereignis gesetzt ist."""
    import asyncio

    weiter = asyncio.Event()
    schreiben = laufzeit.steller._schreiben
    gestartet = asyncio.Event()

    async def langsam(oid: str, wert: str) -> None:
        if not weiter.is_set():
            gestartet.set()
            await weiter.wait()
        await schreiben(oid, wert)

    laufzeit.steller._schreiben = langsam
    return weiter, gestartet


async def test_zuruecknehmen_wartet_auf_den_laufenden_lauf(hass, anlage, freezer, monkeypatch):
    import asyncio

    from custom_components.heatnexus.automatik import regel

    verwaltung, coordinator = anlage
    laufzeit = await _schaltend(hass, verwaltung, freezer)
    laufzeit.gedaechtnis = regel.Gedaechtnis()
    _absenkung_festlegen(monkeypatch)
    weiter, gestartet = _aufhalten(laufzeit)
    coordinator.client.geschrieben.clear()

    lauf = asyncio.ensure_future(laufzeit.auswerten())
    await asyncio.wait_for(gestartet.wait(), 5)
    ruecknahme = asyncio.ensure_future(laufzeit.zuruecknehmen())
    await asyncio.sleep(0)
    weiter.set()
    await asyncio.wait_for(asyncio.gather(lauf, ruecknahme), 5)

    assert laufzeit.gedaechtnis == regel.Gedaechtnis()
    assert coordinator.client.geschrieben[-1] == (f"{ha.PREFIX}/2/10/0", "0")


async def test_eine_entscheidungszeit_waehrend_eines_laufs_geht_nicht_verloren(
    hass, anlage, freezer, monkeypatch
):
    import asyncio

    from custom_components.heatnexus.automatik import regel

    verwaltung, _ = anlage
    laufzeit = await _schaltend(hass, verwaltung, freezer)
    laufzeit.gedaechtnis = regel.Gedaechtnis()
    _absenkung_festlegen(monkeypatch)
    weiter, gestartet = _aufhalten(laufzeit)

    lauf = asyncio.ensure_future(laufzeit.auswerten())
    await asyncio.wait_for(gestartet.wait(), 5)
    entscheidung = asyncio.ensure_future(laufzeit.auswerten(entscheidungszeit=True))
    await asyncio.sleep(0)
    weiter.set()
    await asyncio.wait_for(asyncio.gather(lauf, entscheidung), 5)

    assert laufzeit.lage.entscheidungszeit is True


async def test_entladen_wartet_auf_den_lauf_und_danach_schreibt_nichts_mehr(
    hass, anlage, freezer, monkeypatch
):
    import asyncio

    from custom_components.heatnexus.automatik import regel

    verwaltung, coordinator = anlage
    laufzeit = await _schaltend(hass, verwaltung, freezer)
    laufzeit.gedaechtnis = regel.Gedaechtnis()
    _absenkung_festlegen(monkeypatch)
    weiter, gestartet = _aufhalten(laufzeit)
    eintrag = hass.config_entries.async_entries("heatnexus")[0]

    lauf = asyncio.ensure_future(laufzeit.auswerten())
    await asyncio.wait_for(gestartet.wait(), 5)
    stoppen = asyncio.ensure_future(verwaltung.eintrag_stoppen(eintrag))
    for _ in range(10):
        await asyncio.sleep(0)
    wartet = not stoppen.done()
    weiter.set()
    await asyncio.wait_for(asyncio.gather(lauf, stoppen), 5)

    assert wartet
    gespeichert = verwaltung._daten["heizkreise"][ha.HEIZKREIS]["zustand"]
    assert gespeichert["gedaechtnis"]["absenkung_soll"] == 19.0
    laufzeit.gedaechtnis = regel.Gedaechtnis()
    coordinator.client.geschrieben.clear()
    laufzeit._lieferbeginn()
    await laufzeit.auswerten()
    await hass.async_block_till_done()
    assert coordinator.client.geschrieben == []


# --- Start ------------------------------------------------------------------
def _eintrag(hass):
    return hass.config_entries.async_entries("heatnexus")[0]


async def _neu_laden(verwaltung, hass, zustand=None):
    """Die Automatik wie nach einem Neustart von Home Assistant aus dem Store starten."""
    alt = verwaltung.laufzeiten.pop(ha.HEIZKREIS)
    alt.stoppen()
    eintrag = verwaltung._daten["heizkreise"][ha.HEIZKREIS]
    eintrag["zustand"] = alt.als_dict() if zustand is None else zustand
    await verwaltung._nachholen(_eintrag(hass))


async def test_ein_gescheiterter_start_reisst_den_eintrag_nicht_mit(
    hass, anlage, freezer, monkeypatch
):
    from homeassistant.helpers import issue_registry as ir

    from custom_components.heatnexus.automatik.laufzeit import Laufzeit
    from custom_components.heatnexus.const import DOMAIN

    verwaltung, _ = anlage
    freezer.move_to(ha.MORGEN)
    await ha._eingerichtet(hass, verwaltung)
    starten = Laufzeit.starten

    async def scheitern(self, *args, **kw):
        await starten(self, *args, **kw)
        raise RuntimeError("kaputt")

    monkeypatch.setattr(Laufzeit, "starten", scheitern)

    await _neu_laden(verwaltung, hass)

    # Abgemeldete Auslöser: Ein übrig gebliebener Zeitgeber ließe den Test scheitern.
    assert ha.HEIZKREIS not in verwaltung.laufzeiten
    kennung = f"automatik_start_{ha.HEIZKREIS}"
    assert ir.async_get(hass).async_get_issue(DOMAIN, kennung) is not None


async def test_ein_unlesbarer_zustand_reisst_den_eintrag_nicht_mit(hass, anlage, freezer):
    verwaltung, _ = anlage
    freezer.move_to(ha.MORGEN)
    await ha._eingerichtet(hass, verwaltung)

    await _neu_laden(verwaltung, hass, zustand={"stufen": ["x", "y"]})

    assert ha.HEIZKREIS not in verwaltung.laufzeiten


async def test_der_erste_lauf_nach_dem_start_wartet_nicht_auf_die_prognose(hass, anlage, freezer):
    import asyncio

    from homeassistant.core import SupportsResponse

    verwaltung, _ = anlage
    freezer.move_to(ha.MORGEN)
    await ha._eingerichtet(hass, verwaltung)
    await hass.async_block_till_done(wait_background_tasks=True)
    weiter = asyncio.Event()

    async def langsam(call):
        await weiter.wait()
        return {"weather.home": {"forecast": []}}

    hass.services.async_register(
        "weather", "get_forecasts", langsam, supports_response=SupportsResponse.ONLY
    )
    verwaltung._prognosen.clear()

    await _neu_laden(verwaltung, hass)
    neu = verwaltung.laufzeiten[ha.HEIZKREIS]
    assert neu.lage is None

    weiter.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert neu.lage is not None


# --- Lernen und Nachtragen ---------------------------------------------------
def _zaehlen(monkeypatch):
    """Zählt, wie oft Hausmodell gelernt und der Tag nachgetragen wird."""
    from custom_components.heatnexus.automatik import laufzeit as modul
    from custom_components.heatnexus.automatik.laufzeit import Laufzeit

    aufrufe = {"lernen": 0, "nachtragen": 0}

    async def lernen(self):
        aufrufe["lernen"] += 1

    async def nachtragen(_hass, _laufzeit):
        aufrufe["nachtragen"] += 1

    monkeypatch.setattr(Laufzeit, "hausmodell_lernen", lernen)
    monkeypatch.setattr(modul.nachladen, "heute_nachtragen", nachtragen)
    return aufrufe


async def _einstellen(verwaltung, hass, **aenderung):
    await verwaltung.einstellen(ha.HEIZKREIS, aenderung)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_eine_einstellung_lernt_und_traegt_nicht_erneut_nach(
    hass, anlage, freezer, monkeypatch
):
    from custom_components.heatnexus.automatik import hausmodell

    verwaltung, _ = anlage
    aufrufe = _zaehlen(monkeypatch)
    freezer.move_to(ha.MORGEN)
    laufzeit = await ha._eingerichtet(hass, verwaltung)
    await hass.async_block_till_done(wait_background_tasks=True)
    modell = hausmodell.Modell(40.0, 0.0, 0.6, 0.03, "vorlauf", 6, (0.3,), 0.0, (0.5,))
    laufzeit.hausmodell = modell
    assert aufrufe == {"lernen": 1, "nachtragen": 1}

    await _einstellen(verwaltung, hass, modus="empfehlen")
    await _einstellen(verwaltung, hass, ausrichtung="eco")

    assert aufrufe == {"lernen": 1, "nachtragen": 1}
    assert laufzeit.hausmodell == modell


@pytest.mark.parametrize(
    "aenderung",
    [
        {"raeume": ["sensor.wohnzimmer", "sensor.kueche"]},
        {"raum_art": "minimum"},
        {"wetter": "weather.zweites"},
    ],
)
async def test_geaenderte_raeume_oder_wetter_lernen_das_hausmodell_neu(
    hass, anlage, freezer, monkeypatch, aenderung
):
    from custom_components.heatnexus.automatik import hausmodell

    verwaltung, _ = anlage
    hass.states.async_set("sensor.kueche", "20.5", {"device_class": "temperature"})
    hass.states.async_set("weather.zweites", "sunny")
    aufrufe = _zaehlen(monkeypatch)
    freezer.move_to(ha.MORGEN)
    laufzeit = await ha._eingerichtet(hass, verwaltung)
    await hass.async_block_till_done(wait_background_tasks=True)
    laufzeit.hausmodell = hausmodell.Modell(40.0, 0.0, 0.6, 0.03, "vorlauf", 6, (0.3,), 0.0, (0.5,))

    await _einstellen(verwaltung, hass, **aenderung)

    assert laufzeit.hausmodell is None
    assert aufrufe["lernen"] == 2


# --- Speichern -------------------------------------------------------------
def _speicherplan(verwaltung):
    """Die Verzögerung jedes geplanten Schreibvorgangs des Stores."""
    plan: list[float] = []
    original = verwaltung._store.async_delay_save

    def merken(daten, verzoegerung=0):
        plan.append(verzoegerung)
        original(daten, verzoegerung)

    verwaltung._store.async_delay_save = merken
    return plan


async def test_ein_lauf_ohne_neuen_zustand_speichert_gedrosselt(hass, anlage, freezer):
    from custom_components.heatnexus.automatik import verwaltung as modul

    verwaltung, _ = anlage
    freezer.move_to(ha.MORGEN)
    laufzeit = await ha._eingerichtet(hass, verwaltung)
    await laufzeit.auswerten()
    await hass.async_block_till_done(wait_background_tasks=True)
    verwaltung._abzug()
    plan = _speicherplan(verwaltung)

    for _ in range(3):
        await laufzeit.auswerten()

    assert plan == [modul.SPEICHER_RUHIG_S]


async def test_ein_neuer_zustand_speichert_bald(hass, anlage, freezer, monkeypatch):
    from custom_components.heatnexus.automatik import regel
    from custom_components.heatnexus.automatik import verwaltung as modul

    verwaltung, _ = anlage
    laufzeit = await _schaltend(hass, verwaltung, freezer)
    laufzeit.gedaechtnis = regel.Gedaechtnis()
    await laufzeit.auswerten()
    verwaltung._abzug()
    plan = _speicherplan(verwaltung)
    _absenkung_festlegen(monkeypatch)

    await laufzeit.auswerten()

    assert plan[-1] == modul.SPEICHER_VERZOEGERUNG_S


# --- Store laden -------------------------------------------------------------
def _verwaltung(hass, monkeypatch, laden):
    from custom_components.heatnexus.automatik.verwaltung import Verwaltung

    verwaltung = Verwaltung(hass)
    monkeypatch.setattr(verwaltung._store, "async_load", laden)
    return verwaltung


async def test_fremde_eintraege_im_store_fallen_weg(hass, monkeypatch):
    gueltig = {"konfig": {"entry_id": "e1"}, "zustand": "kaputt"}

    async def laden():
        return {"heizkreise": {"a": "x", "b": {"konfig": [1]}, "c": None, "d": gueltig}}

    verwaltung = _verwaltung(hass, monkeypatch, laden)
    await verwaltung.laden()

    assert verwaltung._daten == {"heizkreise": {"d": {"konfig": {"entry_id": "e1"}, "zustand": {}}}}
    assert verwaltung.eingerichtet("e1") == ["d"]
    assert verwaltung.kennungen("e2") == {}
    await verwaltung.eintrag_entfernt("e2")


def _datei_anlegen(pfad: str) -> None:
    from pathlib import Path

    datei = Path(pfad)
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text('{"version": 9}', encoding="utf-8")


def _gesichert(pfad: str) -> list[str]:
    from pathlib import Path

    datei = Path(pfad)
    return [g.read_text(encoding="utf-8") for g in datei.parent.glob(f"{datei.name}.kaputt-*")]


async def test_ein_unlesbarer_store_wird_gesichert_und_leer_begonnen(hass, monkeypatch, tmp_path):
    async def laden():
        raise RuntimeError("Fassung unbekannt")

    verwaltung = _verwaltung(hass, monkeypatch, laden)
    pfad = str(tmp_path / ".storage" / "heatnexus.automatik")
    # Nicht im gemeinsamen Konfigurationsordner der Tests schreiben.
    verwaltung._store.__dict__["path"] = pfad
    await hass.async_add_executor_job(_datei_anlegen, pfad)

    await verwaltung.laden()

    assert verwaltung._daten == {"heizkreise": {}}
    assert await hass.async_add_executor_job(_gesichert, pfad) == ['{"version": 9}']


async def test_zwei_eintraege_lesen_den_store_einmal(hass, monkeypatch):
    import asyncio

    aufrufe = []
    weiter = asyncio.Event()

    async def laden():
        aufrufe.append(1)
        await weiter.wait()
        return {"heizkreise": {}}

    verwaltung = _verwaltung(hass, monkeypatch, laden)
    erster = asyncio.ensure_future(verwaltung.laden())
    zweiter = asyncio.ensure_future(verwaltung.laden())
    for _ in range(5):
        await asyncio.sleep(0)
    weiter.set()
    await asyncio.gather(erster, zweiter)

    assert aufrufe == [1]


async def test_eine_aeltere_fassung_geht_durch_dieselbe_pruefung(hass):
    from custom_components.heatnexus.automatik.verwaltung import Verwaltung

    store = Verwaltung(hass)._store
    daten = await store._async_migrate_func(1, 0, {"heizkreise": {"a": 1, "b": {"konfig": {}}}})

    assert daten == {"heizkreise": {"b": {"konfig": {}, "zustand": {}}}}
