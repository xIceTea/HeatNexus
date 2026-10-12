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
