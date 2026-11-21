"""Nur Warmwasser (`3/50`) läuft an der Steuerung nicht ab: Rücknahme nach dem Start, beim Ausschalten und Entfernen."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from . import test_automatik_ha as ha
from .conftest import requires_ha

pytestmark = requires_ha()

anlage = ha.anlage
szenario = ha.szenario
HEIZKREIS = ha.HEIZKREIS
BETRIEBSWAHL = f"{ha.PREFIX}/3/50/0"
HOST = "192.0.2.10"


def _nur_ww(laufzeit, vorher: int = 2) -> None:
    """Die Automatik hat `3/50` = 6 geschrieben und sich die Betriebswahl davor gemerkt."""
    from custom_components.heatnexus.automatik import regel

    seit = ha._jetzt() - timedelta(hours=1)
    laufzeit.gedaechtnis = regel.Gedaechtnis(
        saison=regel.NUR_WW, saison_seit=seit, saison_soll=21.0
    )
    stand = laufzeit.steller.stand
    laufzeit.steller.stand = replace(stand, betriebswahl_vorher=vorher, erwartet=6)


async def _neu_gestartet(hass, sz, zustand):
    sz.geschrieben.clear()
    laufzeit = await sz.neu_starten(zustand)
    await hass.async_block_till_done(wait_background_tasks=True)
    return laufzeit


@pytest.mark.parametrize(("steht", "geschrieben"), [("6", [(BETRIEBSWAHL, "2")]), ("3", [])])
async def test_ausgeschaltet_nach_dem_start_kommt_die_betriebswahl_zurueck(
    hass, szenario, steht, geschrieben
):
    """Nur eine Betriebswahl, die noch auf dem eigenen Wert steht, wird zurückgestellt."""
    from custom_components.heatnexus.automatik import regel

    sz = await szenario(ws=False, modus="schalten")
    await sz.verwaltung.einstellen(HEIZKREIS, {"aktiv": False})
    _nur_ww(sz.laufzeit)
    sz.oids[BETRIEBSWAHL] = steht

    laufzeit = await _neu_gestartet(hass, sz, sz.laufzeit.als_dict())

    assert sz.geschrieben == geschrieben
    assert laufzeit.gedaechtnis.saison == regel.HEIZEN


async def test_nach_dem_start_endet_nur_ww_sofort_wenn_die_regel_nicht_mehr_gilt(hass, szenario):
    """Seit einer Stunde unter der Einschaltschwelle: Der erste Lauf stellt zurück, ohne Takte zu zählen."""
    sz = await szenario(ws=False, modus="schalten")
    _nur_ww(sz.laufzeit)
    sz.oids[BETRIEBSWAHL] = "6"
    zustand = sz.laufzeit.als_dict()
    stunde = str(ha._jetzt().hour - 1)
    zustand["verlauf"] = {
        "datum": ha._jetzt().date().isoformat(),
        "stunden": {stunde: {"at": 11.0}},
    }

    await _neu_gestartet(hass, sz, zustand)

    assert sz.geschrieben == [(BETRIEBSWAHL, "2")]


@pytest.mark.parametrize(("steht", "geschrieben"), [("6", [(BETRIEBSWAHL, "2")]), ("3", [])])
async def test_ausschalten_stellt_nur_die_eigene_betriebswahl_zurueck(szenario, steht, geschrieben):
    from custom_components.heatnexus.automatik import regel

    sz = await szenario(ws=False, modus="schalten")
    _nur_ww(sz.laufzeit)
    sz.oids[BETRIEBSWAHL] = steht
    sz.geschrieben.clear()

    await sz.verwaltung.einstellen(HEIZKREIS, {"aktiv": False})

    assert sz.geschrieben == geschrieben
    assert sz.laufzeit.gedaechtnis.saison == regel.HEIZEN
    assert sz.laufzeit.steller.stand.erwartet is None


@pytest.mark.parametrize(
    ("deaktiviert", "geschrieben"), [(True, [(BETRIEBSWAHL, "2")]), (False, [])]
)
async def test_deaktivieren_des_eintrags_stellt_nur_ww_zurueck(szenario, deaktiviert, geschrieben):
    """Ein Entladen beim Neustart lässt nur Warmwasser stehen; das Deaktivieren nicht."""
    from homeassistant.config_entries import ConfigEntryDisabler

    sz = await szenario(ws=False, modus="schalten")
    _nur_ww(sz.laufzeit)
    sz.oids[BETRIEBSWAHL] = "6"
    sz.geschrieben.clear()
    if deaktiviert:
        object.__setattr__(sz.eintrag, "disabled_by", ConfigEntryDisabler.USER)

    await sz.verwaltung.eintrag_stoppen(sz.eintrag)

    assert sz.geschrieben == geschrieben


class _Anlage:
    """Eine eigene Verbindung zur Steuerung, wie sie das Entfernen des Eintrags aufbaut."""

    def __init__(self, steht: str) -> None:
        self.werte = {BETRIEBSWAHL: steht}
        self.geschrieben: list[tuple[str, str]] = []
        self.geschlossen = False

    async def fetch_oids(self, oids) -> dict:
        return {oid: self.werte.get(oid) for oid in oids}

    async def update(self, oid: str, wert: str) -> None:
        self.geschrieben.append((oid, wert))

    async def close(self) -> None:
        self.geschlossen = True


@pytest.mark.parametrize(("steht", "geschrieben"), [("6", [(BETRIEBSWAHL, "2")]), ("3", [])])
async def test_entfernen_des_eintrags_stellt_nur_ww_zurueck(
    hass, szenario, monkeypatch, steht, geschrieben
):
    from custom_components.heatnexus.automatik import ruecknahme

    sz = await szenario(ws=False, modus="schalten")
    sz.coordinator.host = HOST
    hass.config_entries.async_update_entry(
        sz.eintrag, data={"systems": [{"host": HOST, "password": "geheim"}]}
    )
    _nur_ww(sz.laufzeit)
    verbindung = _Anlage(steht)
    zugaenge = []

    def bauen(host, passwort, benutzer):
        zugaenge.append((host, passwort, benutzer))
        return verbindung

    monkeypatch.setattr(ruecknahme, "_verbindung", bauen)
    await sz.verwaltung.eintrag_stoppen(sz.eintrag)

    await sz.verwaltung.eintrag_entfernt(sz.eintrag)

    assert zugaenge == [(HOST, "geheim", "USER")]
    assert verbindung.geschrieben == geschrieben
    assert verbindung.geschlossen
    assert sz.verwaltung.konfig(HEIZKREIS) is None


async def test_entfernen_ohne_eigenes_nur_ww_baut_keine_verbindung_auf(hass, szenario, monkeypatch):
    from custom_components.heatnexus.automatik import ruecknahme

    sz = await szenario(ws=False, modus="schalten")
    sz.coordinator.host = HOST
    monkeypatch.setattr(ruecknahme, "_verbindung", pytest.fail)
    await sz.verwaltung.eintrag_stoppen(sz.eintrag)

    await sz.verwaltung.eintrag_entfernt(sz.eintrag)

    assert sz.verwaltung.konfig(HEIZKREIS) is None
