"""Automatik zur Laufzeit: Start, Nebenläufigkeit, Speichern und Ausfälle in Home Assistant."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest

from . import test_automatik_ha as ha
from .conftest import requires_ha

pytestmark = requires_ha()

anlage = ha.anlage
szenario = ha.szenario
HEIZKREIS = ha.HEIZKREIS


async def _schaltend(hass, szenario) -> ha.Szenario:
    """Eine eingerichtete Automatik, die an die Steuerung schreibt."""
    sz = await szenario(ws=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    sz.laufzeit.konfig = {**sz.laufzeit.konfig, "modus": "schalten"}
    return sz


async def _scheitert(*_a, **_k):
    raise RuntimeError("Start gescheitert")


# --- Halb geschriebene Absenkung --------------------------------------------
def _laufende_pause(sz: ha.Szenario, soll: float = 17.0):
    """Eine eigene Heizpause, wie die Steuerung sie zeigt."""
    from homeassistant.util import dt as dt_util

    from custom_components.heatnexus.automatik import regel

    jetzt = dt_util.now()
    sz.laufzeit.gedaechtnis = regel.Gedaechtnis(
        absenkung_art=regel.PAUSE,
        absenkung_von=jetzt - timedelta(hours=1),
        absenkung_bis=jetzt + timedelta(hours=2),
        absenkung_basis=21.0,
        absenkung_soll=soll,
    )
    sz.oids[f"{ha.PREFIX}/1/1/0"] = f"{soll:.1f}"
    sz.oids[f"{ha.PREFIX}/2/10/0"] = "120"
    return sz.laufzeit.gedaechtnis


def _entscheidung_festlegen(monkeypatch, *aktionen):
    """Die Regel entscheidet immer gleich: eine erneuerte Pause mit 18 °C."""
    from custom_components.heatnexus.automatik import regel

    def entscheiden(lage, g, _werte):
        neu = replace(g, absenkung_soll=18.0)
        return regel.Entscheidung(regel.Zustand.HEIZPAUSE, aktionen, "Heizpause.", neu)

    monkeypatch.setattr(regel, "entscheiden", entscheiden)


def _ablehnen(sz: ha.Szenario, *adressen: str, ab: int = 0):
    """Die Steuerung des Stellers lehnt die Adressen ab, `3/4` erst nach `ab` Schreibvorgängen."""
    temperatur = []

    async def update(oid: str, wert: str) -> None:
        if oid.endswith("/3/4/0"):
            temperatur.append(wert)
            if len(temperatur) > ab and "/3/4/0" in adressen:
                raise RuntimeError("abgelehnt")
        elif any(oid.endswith(a) for a in adressen):
            raise RuntimeError("abgelehnt")
        sz.geschrieben.append((oid, wert))

    sz.laufzeit.steller._schreiben = update


@pytest.mark.parametrize(
    ("abgelehnt", "ab", "raumsoll", "soll"),
    [(("/2/10/0",), 0, ["18.0", "17.0"], 17.0), (("/2/10/0", "/3/4/0"), 1, ["18.0"], 18.0)],
    ids=["zurueckgestellt", "stehen_geblieben"],
)
async def test_halb_geschriebene_pause_hinterlaesst_einen_bekannten_raumsoll(
    hass, szenario, monkeypatch, abgelehnt, ab, raumsoll, soll
):
    """Scheitert `2/10`, stellt die Automatik `3/4` zurück; bleibt der neue Wert stehen, kennt sie ihn."""
    from custom_components.heatnexus.automatik import regel

    sz = await _schaltend(hass, szenario)
    vorher = _laufende_pause(sz)
    _entscheidung_festlegen(
        monkeypatch, regel.Aktion("pause", soll=18.0, minuten=400, erneuern=True)
    )
    _ablehnen(sz, *abgelehnt, ab=ab)
    sz.geschrieben.clear()

    await sz.laufzeit.auswerten()

    assert [w for oid, w in sz.geschrieben if oid.endswith("/3/4/0")] == raumsoll
    assert sz.laufzeit.gedaechtnis == replace(vorher, absenkung_soll=soll)
    assert regel.absenkung_laeuft(sz.laufzeit.gedaechtnis, sz.laufzeit.lage.jetzt)


# --- Läufe nacheinander -----------------------------------------------------
def _absenkung_festlegen(monkeypatch) -> list[bool]:
    """Die Regel beginnt immer eine Absenkung auf 19 °C für drei Stunden, ohne Zählung.

    Zurück kommt die Liste, ob ein Lauf als Takt kam.
    """
    from homeassistant.util import dt as dt_util

    from custom_components.heatnexus.automatik import dynamik, regel

    takte: list[bool] = []

    def durchreichen(kandidat, _alt, verlauf, _lage, _w, *, takt, erzwingen=False):
        takte.append(takt)
        return dynamik.Ergebnis(kandidat, verlauf)

    monkeypatch.setattr(dynamik, "stabilisieren", durchreichen)

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
    return takte


def _aufhalten(laufzeit):
    """Der nächste Schreibvorgang wartet, bis das zurückgegebene Ereignis gesetzt ist."""
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


async def _aufgehalten(hass, szenario, monkeypatch):
    """Eine schaltende Automatik ohne Absenkung; ihr nächster Schreibvorgang wartet."""
    from custom_components.heatnexus.automatik import regel

    sz = await _schaltend(hass, szenario)
    sz.laufzeit.gedaechtnis = regel.Gedaechtnis()
    takte = _absenkung_festlegen(monkeypatch)
    weiter, gestartet = _aufhalten(sz.laufzeit)
    return sz, takte, weiter, gestartet


async def test_zuruecknehmen_wartet_auf_den_laufenden_lauf(hass, szenario, monkeypatch):
    from custom_components.heatnexus.automatik import regel

    sz, _, weiter, gestartet = await _aufgehalten(hass, szenario, monkeypatch)
    sz.geschrieben.clear()

    lauf = asyncio.ensure_future(sz.laufzeit.auswerten())
    await asyncio.wait_for(gestartet.wait(), 5)
    ruecknahme = asyncio.ensure_future(sz.laufzeit.zuruecknehmen())
    await asyncio.sleep(0)
    weiter.set()
    await asyncio.wait_for(asyncio.gather(lauf, ruecknahme), 5)

    assert sz.laufzeit.gedaechtnis == regel.Gedaechtnis()
    assert sz.geschrieben[-1] == ha.ENDE


async def test_ein_takt_waehrend_eines_laufs_geht_nicht_verloren(hass, szenario, monkeypatch):
    sz, takte, weiter, gestartet = await _aufgehalten(hass, szenario, monkeypatch)

    lauf = asyncio.ensure_future(sz.laufzeit.auswerten())
    await asyncio.wait_for(gestartet.wait(), 5)
    entscheidung = asyncio.ensure_future(sz.laufzeit.auswerten(takt=True))
    await asyncio.sleep(0)
    weiter.set()
    await asyncio.wait_for(asyncio.gather(lauf, entscheidung), 5)

    assert takte[-1] is True


async def test_ein_takt_waehrend_einer_auswertung_geht_nicht_verloren(hass, szenario):
    laufzeit = (await szenario(modus="schalten")).laufzeit

    await laufzeit._sperre.acquire()
    aufgabe = hass.async_create_task(laufzeit._takt(None))
    laufzeit._sperre.release()
    await aufgabe

    assert laufzeit.anstehend.zaehler == 1


async def test_bestaetigung_waehrend_einer_auswertung_geht_nicht_verloren(hass, szenario):
    sz = await szenario(modus="empfehlen", takte=True)
    laufzeit = sz.laufzeit
    lauf = laufzeit._auswerten

    async def bestaetigen_waehrend() -> None:
        laufzeit._auswerten = lauf
        await lauf()
        hass.async_create_task(sz.verwaltung.empfehlung_uebernehmen(HEIZKREIS))

    laufzeit._auswerten = bestaetigen_waehrend
    await laufzeit.auswerten()
    await hass.async_block_till_done()

    assert sz.geschrieben == ha.ABSENKUNG


async def test_gleichzeitige_einstellungen_gehen_beide_ein(szenario):
    """Panel und Auswahl „Modus“ zugleich: Keine der beiden Änderungen geht verloren."""
    sz = await szenario(zeit=None, ws=False)

    async def laeuft_noch():
        # Ein laufender Durchgang: `abwarten` gibt die Schleife frei.
        await asyncio.sleep(0.01)

    sz.laufzeit.abwarten = laeuft_noch
    await asyncio.gather(
        sz.verwaltung.einstellen(HEIZKREIS, {"modus": "empfehlen"}),
        sz.verwaltung.einstellen(HEIZKREIS, {"aktiv": False}),
    )

    konfig = sz.verwaltung.konfig(HEIZKREIS)
    assert (konfig["modus"], konfig["aktiv"]) == ("empfehlen", False)


async def test_entladen_wartet_auf_den_lauf_und_danach_schreibt_nichts_mehr(
    hass, szenario, monkeypatch
):
    from custom_components.heatnexus.automatik import regel

    sz, _, weiter, gestartet = await _aufgehalten(hass, szenario, monkeypatch)
    laufzeit = sz.laufzeit

    lauf = asyncio.ensure_future(laufzeit.auswerten())
    await asyncio.wait_for(gestartet.wait(), 5)
    stoppen = asyncio.ensure_future(sz.verwaltung.eintrag_stoppen(sz.eintrag))
    for _ in range(10):
        await asyncio.sleep(0)
    wartet = not stoppen.done()
    weiter.set()
    await asyncio.wait_for(asyncio.gather(lauf, stoppen), 5)

    assert wartet
    gespeichert = sz.verwaltung._daten["heizkreise"][HEIZKREIS]["zustand"]
    assert gespeichert["gedaechtnis"]["absenkung_soll"] == 19.0
    laufzeit.gedaechtnis = regel.Gedaechtnis()
    sz.geschrieben.clear()
    laufzeit._lieferbeginn()
    await laufzeit.auswerten()
    await hass.async_block_till_done()
    assert sz.geschrieben == []


# --- Start ------------------------------------------------------------------
def _kaputt(_entry):
    raise RuntimeError("Geräteregister gesperrt")


@pytest.mark.parametrize("ursache", ["system", "start", "zustand"])
async def test_ein_gescheiterter_start_reisst_den_eintrag_nicht_mit(
    hass, szenario, monkeypatch, caplog, ursache
):
    """Gesperrtes Geräteregister, Fehler beim Start, unlesbarer Zustand: Log und Meldung, kein Abbruch."""
    from custom_components.heatnexus.automatik.laufzeit import Laufzeit

    sz = await szenario(ws=False)
    zustand = sz.laufzeit.als_dict()
    starten = Laufzeit.starten

    async def startet_und_scheitert(self, *args, **kw):
        await starten(self, *args, **kw)
        raise RuntimeError("kaputt")

    if ursache == "system":
        monkeypatch.setattr(sz.verwaltung, "_system_anlegen", _kaputt)
    elif ursache == "start":
        monkeypatch.setattr(Laufzeit, "starten", startet_und_scheitert)
    else:
        zustand = {"stufen": ["x", "y"]}

    # Abgemeldete Auslöser: Ein übrig gebliebener Zeitgeber ließe den Test scheitern.
    assert await sz.neu_starten(zustand) is None
    assert ha._issue(hass, "automatik_start") is not None
    assert "Start gescheitert" in caplog.text


@pytest.mark.parametrize(
    ("aenderung", "verworfen"),
    [({"modus": "empfehlen"}, []), ({"wetter": "weather.andere"}, [True])],
    ids=["modus", "wetter"],
)
async def test_ein_gescheiterter_neustart_behaelt_die_neuen_einstellungen(
    szenario, aenderung, verworfen
):
    """Die Laufzeit rechnet schon mit der neuen Konfiguration; ein zweiter Versuch sähe keinen Unterschied."""
    sz = await szenario(zeit=None, ws=False)
    laufzeit = sz.laufzeit
    echt = laufzeit.starten
    neu_lernen: list = []
    laufzeit.modell_neu_lernen = lambda: neu_lernen.append(True)
    laufzeit.starten = _scheitert
    with pytest.raises(RuntimeError):
        await sz.verwaltung.einstellen(HEIZKREIS, aenderung)
    laufzeit.starten = echt

    assert neu_lernen == verworfen
    ((schluessel, wert),) = aenderung.items()
    assert laufzeit.konfig[schluessel] == wert
    assert sz.verwaltung.konfig(HEIZKREIS)[schluessel] == wert


async def test_ein_gescheitertes_einrichten_hinterlaesst_nichts(hass, szenario, monkeypatch):
    """Ohne Automatik bleiben weder System-Gerät noch Untereintrag „HeatNexus Automatik“."""
    from custom_components.heatnexus.automatik.laufzeit import Laufzeit

    sz = await szenario(zeit=None, ws=False, einrichten=False)
    monkeypatch.setattr(Laufzeit, "starten", _scheitert)
    with pytest.raises(ValueError):
        await sz.einrichten()
    await hass.async_block_till_done()

    assert sz.verwaltung.subeintrag(sz.eintrag) is None
    assert ha._automatik_geraete(hass, sz.eintrag) == []


async def test_der_erste_lauf_nach_dem_start_wartet_nicht_auf_die_prognose(hass, szenario):
    from homeassistant.core import SupportsResponse

    sz = await szenario(ws=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    weiter = asyncio.Event()

    async def langsam(call):
        await weiter.wait()
        return {"weather.home": {"forecast": []}}

    hass.services.async_register(
        "weather", "get_forecasts", langsam, supports_response=SupportsResponse.ONLY
    )
    sz.verwaltung._prognosen.clear()

    neu = await sz.neu_starten(sz.laufzeit.als_dict())
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


@pytest.mark.parametrize(
    ("aenderung", "neu"),
    [
        ({"modus": "empfehlen"}, False),
        ({"ausrichtung": "eco"}, False),
        ({"raeume": ["sensor.wohnzimmer", "sensor.kueche"]}, True),
        ({"raum_art": "minimum"}, True),
        ({"wetter": "weather.zweites"}, True),
    ],
    ids=["modus", "ausrichtung", "raeume", "raum_art", "wetter"],
)
async def test_nur_geaenderte_raeume_oder_wetter_lernen_das_hausmodell_neu(
    hass, szenario, monkeypatch, aenderung, neu
):
    hass.states.async_set("sensor.kueche", "20.5", {"device_class": "temperature"})
    hass.states.async_set("weather.zweites", "sunny")
    aufrufe = _zaehlen(monkeypatch)
    sz = await szenario(ws=False)
    laufzeit = sz.laufzeit
    await hass.async_block_till_done(wait_background_tasks=True)
    modell = ha._modell(1, tage=6)
    laufzeit.hausmodell = modell
    assert aufrufe == {"lernen": 1, "nachtragen": 1}

    await sz.verwaltung.einstellen(HEIZKREIS, aenderung)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert aufrufe == {"lernen": 1 + neu, "nachtragen": 1}
    assert laufzeit.hausmodell == (None if neu else modell)


async def _lernt_wieder(hass, szenario, monkeypatch, entfernen):
    """Nach `hausmodell_neu` mit dem gegebenen Löschen: Der nächste Lernlauf legt wieder ab."""
    from custom_components.heatnexus.automatik import lernablage

    laufzeit = (await szenario(ws=False)).laufzeit
    await hass.async_block_till_done()
    monkeypatch.setattr(lernablage, "entfernen", entfernen)
    ha._lerndaten_festlegen(monkeypatch, laufzeit, "vorlauf", ha._lernstunden(7))
    laufzeit.hausmodell_neu()
    return laufzeit


async def test_ein_abgebrochener_lernlauf_sperrt_die_ablage_nicht(
    hass, hass_storage, szenario, monkeypatch
):
    """Wird der Lernlauf abgebrochen, während er aufs Löschen wartet, lernt der nächste trotzdem."""
    frei = asyncio.Event()

    async def entfernen(_hass, _device_id):
        await frei.wait()

    laufzeit = await _lernt_wieder(hass, szenario, monkeypatch, entfernen)
    lauf = hass.async_create_task(laufzeit.hausmodell_lernen())
    await asyncio.sleep(0)
    lauf.cancel()
    with pytest.raises(asyncio.CancelledError):
        await lauf
    frei.set()

    await laufzeit.hausmodell_lernen()
    assert f"heatnexus.hausmodell_{HEIZKREIS}" in hass_storage


async def test_ein_gescheitertes_loeschen_sperrt_die_ablage_nicht(
    hass, hass_storage, szenario, monkeypatch
):
    async def entfernen(_hass, _device_id):
        raise OSError("Datei gesperrt")

    laufzeit = await _lernt_wieder(hass, szenario, monkeypatch, entfernen)
    await laufzeit.hausmodell_lernen()
    await laufzeit.hausmodell_lernen()
    assert f"heatnexus.hausmodell_{HEIZKREIS}" in hass_storage


async def test_stoppen_bricht_das_lernen_ab(szenario, monkeypatch):
    laufzeit = (await szenario()).laufzeit
    gestartet = asyncio.Event()

    async def lerndaten():
        gestartet.set()
        await asyncio.sleep(3600)

    monkeypatch.setattr(laufzeit, "_lerndaten", lerndaten)
    await laufzeit._hausmodell_takt(None)
    await gestartet.wait()
    aufgabe = laufzeit._lernaufgabe
    assert not aufgabe.done()

    laufzeit.stoppen()
    await asyncio.sleep(0)
    assert aufgabe.cancelled()


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


async def test_ein_lauf_ohne_neuen_zustand_speichert_gedrosselt(hass, szenario):
    from custom_components.heatnexus.automatik import verwaltung as modul

    sz = await szenario(ws=False)
    await sz.laufzeit.auswerten()
    await hass.async_block_till_done(wait_background_tasks=True)
    sz.verwaltung._abzug()
    plan = _speicherplan(sz.verwaltung)

    for _ in range(3):
        await sz.laufzeit.auswerten()

    assert plan == [modul.SPEICHER_RUHIG_S]


async def test_ein_neuer_zustand_speichert_bald(hass, szenario, monkeypatch):
    from custom_components.heatnexus.automatik import regel
    from custom_components.heatnexus.automatik import verwaltung as modul

    sz = await _schaltend(hass, szenario)
    sz.laufzeit.gedaechtnis = regel.Gedaechtnis()
    await sz.laufzeit.auswerten()
    sz.verwaltung._abzug()
    plan = _speicherplan(sz.verwaltung)
    _absenkung_festlegen(monkeypatch)

    await sz.laufzeit.auswerten()

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
    await verwaltung.eintrag_entfernt(SimpleNamespace(entry_id="e2", data={}))


async def test_gespeicherter_restwert_sensor_wird_beim_laden_verworfen(hass, hass_storage):
    from custom_components.heatnexus.automatik.verwaltung import STORE_KEY, Verwaltung

    konfig = {
        "heizkreis": HEIZKREIS,
        "raeume": ["sensor.wohnzimmer"],
        "wetter": "weather.home",
        "pv": "sensor.energy_production_today_remaining",
    }
    hass_storage[STORE_KEY] = {
        "version": 1,
        "data": {"heizkreise": {HEIZKREIS: {"konfig": konfig, "zustand": {}}}},
    }
    verwaltung = Verwaltung(hass)

    await verwaltung.laden()

    assert verwaltung.konfig(HEIZKREIS)["pv"] is None


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


async def test_unlesbare_eintraege_der_prognoseablage_fallen_weg(hass, hass_storage):
    from custom_components.heatnexus.automatik import prognoseablage

    gut = {
        "wetter": "weather.home",
        "art": "hourly",
        "zeit": "2026-01-01T08:00:00+00:00",
        "daten": [{"a": 1}],
    }
    hass_storage[prognoseablage.SCHLUESSEL] = {
        "version": prognoseablage.FASSUNG,
        "key": prognoseablage.SCHLUESSEL,
        "data": {
            "prognosen": [
                gut,
                "kaputt",
                {**gut, "zeit": "gestern"},
                {**gut, "art": "daily", "daten": []},
                {**gut, "art": "daily", "daten": "nein"},
            ]
        },
    }

    prognosen = await prognoseablage.laden(prognoseablage.ablage(hass))

    assert list(prognosen) == [("weather.home", "hourly")]


def test_tageswerte_verwerfen_unbrauchbare_zahlen():
    from custom_components.heatnexus.automatik.quellen import tageswerte

    eintraege = [{"datetime": "2026-10-13T00:00:00+02:00", "temperature": "x", "templow": 4}]

    assert tageswerte(eintraege)[0][1:] == (None, 4.0)
