"""Automatik zur Laufzeit: Start, Nebenläufigkeit, Speichern und Ausfälle in Home Assistant."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

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
