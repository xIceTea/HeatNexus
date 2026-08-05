"""Wann der gespeicherte Erkennungsstand noch gilt.

Ein voller Erkennungslauf kostet 30 bis 120 Sekunden, in denen kaum etwas
dasteht. Die Regeln, wann er wiederholt werden muss, sind deshalb keine
Nebensache – und sie sind einmal falsch gewesen: Bis 1.1.0-beta.2 verwarf jede
neue Fassung der Integration den Stand, also lief nach *jeder* Aktualisierung
ein voller Abzug.

Ebenfalls hier: die Unterscheidung zwischen „der Nutzer hat etwas abgewählt"
und „die Anlage liefert etwas nicht mehr". Nur das erste ist eine Entscheidung
und rechtfertigt, Entitäten samt Namen, Bereich und Verlauf zu löschen.
"""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

HOST = "192.168.178.100"


@pytest.fixture(scope="module")
def modul():
    import custom_components.heatnexus as heatnexus

    return heatnexus


@pytest.fixture(scope="module")
def const():
    from custom_components.heatnexus import const

    return const


def _eintrag(modul, const, optionen=None, systeme=None):
    return SimpleNamespace(
        entry_id="eintrag1",
        title="HeatNexus",
        data={const.CONF_SYSTEMS: systeme if systeme is not None else [{modul.CONF_HOST: HOST}]},
        options=optionen or {},
    )


def _stand(modul, const, **abweichend):
    from homeassistant.util import dt as dt_util

    stand = {
        "data": {"devices": []},
        "host": HOST,
        "scope": modul._scope_fingerprint(modul._scope(_eintrag(modul, const), HOST)),
        "saved": dt_util.utcnow().isoformat(),
        "version": "1.5.0",
    }
    stand.update(abweichend)
    return stand


# ---------------------------------------------------------------------------
# Umfang
# ---------------------------------------------------------------------------
def test_ohne_optionen_gilt_die_voreinstellung(modul, const):
    umfang = modul._scope(_eintrag(modul, const), HOST)
    assert umfang["levels"] == list(const.DEFAULT_LEVELS)
    assert umfang["enable_advanced"] is False
    assert umfang["username"] == const.DEFAULT_USERNAME


def test_die_optionen_haengen_an_der_anlage_nicht_am_eintrag(modul, const):
    """Zwei Anlagen in einem Eintrag: Was für die eine gilt, gilt nicht für die andere."""
    eintrag = _eintrag(
        modul,
        const,
        optionen={HOST: {const.CONF_LEVELS: ["info"], const.CONF_ENABLE_ADVANCED: True}},
        systeme=[{modul.CONF_HOST: HOST}, {modul.CONF_HOST: "192.168.178.102"}],
    )
    assert modul._scope(eintrag, HOST)["levels"] == ["info"]
    assert modul._scope(eintrag, "192.168.178.102")["levels"] == list(const.DEFAULT_LEVELS)


def test_der_zugang_gehoert_zum_umfang(modul, const):
    """„Service" sieht Datenpunkte, die „USER" gar nicht erst geliefert bekommt."""
    eintrag = _eintrag(
        modul, const, systeme=[{modul.CONF_HOST: HOST, modul.CONF_USERNAME: "Service"}]
    )
    assert modul._scope(eintrag, HOST)["username"] == "Service"
    assert "Service" in modul._scope_fingerprint(modul._scope(eintrag, HOST))


def test_ein_anderer_zugang_ergibt_eine_andere_kennung(modul, const):
    mit_user = modul._scope_fingerprint(modul._scope(_eintrag(modul, const), HOST))
    mit_service = modul._scope_fingerprint(
        modul._scope(
            _eintrag(modul, const, systeme=[{modul.CONF_HOST: HOST, "username": "Service"}]), HOST
        )
    )
    assert mit_user != mit_service


# ---------------------------------------------------------------------------
# Gültigkeit des gespeicherten Stands
# ---------------------------------------------------------------------------
def test_ein_frischer_stand_derselben_anlage_gilt(modul, const):
    kennung = modul._scope_fingerprint(modul._scope(_eintrag(modul, const), HOST))
    assert modul._discovery_cache_valid(_stand(modul, const), HOST, kennung)


def test_eine_neue_fassung_verwirft_den_stand_nicht(modul, const):
    """Sonst läge die Anlage nach jeder Aktualisierung minutenlang brach."""
    kennung = modul._scope_fingerprint(modul._scope(_eintrag(modul, const), HOST))
    alt = _stand(modul, const, version="0.9.0")
    assert modul._discovery_cache_valid(alt, HOST, kennung)
    # Sie löst aber einen Abgleich im Hintergrund aus.
    assert modul._veraltet(alt, "1.5.0")
    assert not modul._veraltet(_stand(modul, const), "1.5.0")


def test_eine_andere_anlage_verwirft_den_stand(modul, const):
    kennung = modul._scope_fingerprint(modul._scope(_eintrag(modul, const), HOST))
    assert not modul._discovery_cache_valid(_stand(modul, const), "192.168.178.102", kennung)


def test_ein_geaenderter_umfang_verwirft_den_stand(modul, const):
    assert not modul._discovery_cache_valid(_stand(modul, const), HOST, "ganz anders")


def test_ein_zu_alter_stand_verwirft_sich_selbst(modul, const):
    from homeassistant.util import dt as dt_util

    kennung = modul._scope_fingerprint(modul._scope(_eintrag(modul, const), HOST))
    zu_alt = dt_util.utcnow() - timedelta(days=const.DISCOVERY_MAX_AGE_DAYS + 1)
    assert not modul._discovery_cache_valid(
        _stand(modul, const, saved=zu_alt.isoformat()), HOST, kennung
    )


@pytest.mark.parametrize(
    "kaputt",
    [None, "kein Wörterbuch", {}, {"data": {}, "host": HOST, "scope": "x", "saved": "gestern"}],
)
def test_ein_unbrauchbarer_stand_gilt_nicht(modul, kaputt):
    """Lieber neu einlesen als auf halben Daten aufbauen."""
    assert not modul._discovery_cache_valid(kaputt, HOST, "x")


# ---------------------------------------------------------------------------
# Abwahl: löschen oder nur stilllegen
# ---------------------------------------------------------------------------
def _umfang(levels, erweitert=False):
    return {"levels": levels, "enable_advanced": erweitert, "writable_advanced": False}


def test_eine_abgewaehlte_ebene_ist_eine_entscheidung(modul):
    alt = {HOST: _umfang(["info", "operate", "service"])}
    neu = {HOST: _umfang(["info", "operate"])}
    assert modul._umfang_verkleinert(alt, neu)


def test_eine_zusaetzliche_ebene_ist_keine_abwahl(modul):
    alt = {HOST: _umfang(["info"])}
    neu = {HOST: _umfang(["info", "operate"])}
    assert not modul._umfang_verkleinert(alt, neu)


def test_abgeschaltete_fachparameter_zaehlen_als_abwahl(modul):
    alt = {HOST: _umfang(["info"], erweitert=True)}
    neu = {HOST: _umfang(["info"])}
    assert modul._umfang_verkleinert(alt, neu)


def test_eine_entfernte_anlage_zaehlt_als_abwahl(modul):
    assert modul._umfang_verkleinert({HOST: _umfang(["info"])}, {})


def test_die_vormerkung_gilt_genau_einmal(modul, const, hass):
    """Sonst räumte auch der übernächste Ladevorgang noch auf."""
    eintrag = _eintrag(modul, const)
    assert not modul._abwahl_abholen(hass, eintrag)
    modul._abwahl_vormerken(hass, eintrag)
    assert modul._abwahl_abholen(hass, eintrag)
    assert not modul._abwahl_abholen(hass, eintrag)


# ---------------------------------------------------------------------------
# Meldungen
# ---------------------------------------------------------------------------
def test_beide_einlesemeldungen_haengen_an_derselben_option(modul, const):
    """Sonst erschiene die Abschlussmeldung aus dem Nichts – der Fehler aus 1.2.0-beta.4."""
    assert not modul.meldung_erwuenscht(None)
    assert not modul.meldung_erwuenscht({})
    assert modul.meldung_erwuenscht({const.CONF_MELDUNG_EINLESEN: True})


def test_jeder_eintrag_hat_seinen_eigenen_ablageort(modul, const):
    """Die Adresse steckt mit drin: Ein Eintrag kann mehrere Anlagen führen."""
    eintrag = _eintrag(modul, const)
    assert modul._store_key(eintrag, HOST) != modul._store_key(eintrag, "192.168.178.102")
    assert "192_168_178_100" in modul._store_key(eintrag, HOST)


def test_die_anlagen_kommen_aus_den_eintragsdaten(modul, const):
    assert modul._systems(_eintrag(modul, const)) == [{modul.CONF_HOST: HOST}]
    assert modul._systems(_eintrag(modul, const, systeme=[])) == []
