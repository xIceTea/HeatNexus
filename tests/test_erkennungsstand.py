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

HOST = "192.0.2.10"


@pytest.fixture(scope="module")
def modul():
    import custom_components.heatnexus as heatnexus

    return heatnexus


@pytest.fixture(scope="module")
def const():
    from custom_components.heatnexus import const

    return const


def _hass(sprache: str = "de"):
    """Home Assistant nur so weit, wie der Umfang davon braucht."""
    return SimpleNamespace(config=SimpleNamespace(language=sprache))


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
        "scope": modul._scope_fingerprint(modul._scope(_hass(), _eintrag(modul, const), HOST)),
        "saved": dt_util.utcnow().isoformat(),
        "version": "1.5.0",
        "sprache": "de",
    }
    stand.update(abweichend)
    return stand


# ---------------------------------------------------------------------------
# Umfang
# ---------------------------------------------------------------------------
def test_ohne_optionen_gilt_die_voreinstellung(modul, const):
    umfang = modul._scope(_hass(), _eintrag(modul, const), HOST)
    assert umfang["levels"] == list(const.DEFAULT_LEVELS)
    assert umfang["enable_advanced"] is False
    assert umfang["username"] == const.DEFAULT_USERNAME


def test_die_optionen_haengen_an_der_anlage_nicht_am_eintrag(modul, const):
    """Zwei Anlagen in einem Eintrag: Was für die eine gilt, gilt nicht für die andere."""
    eintrag = _eintrag(
        modul,
        const,
        optionen={HOST: {const.CONF_LEVELS: ["info"], const.CONF_ENABLE_ADVANCED: True}},
        systeme=[{modul.CONF_HOST: HOST}, {modul.CONF_HOST: "192.0.2.11"}],
    )
    assert modul._scope(_hass(), eintrag, HOST)["levels"] == ["info"]
    assert modul._scope(_hass(), eintrag, "192.0.2.11")["levels"] == list(const.DEFAULT_LEVELS)


def test_der_zugang_gehoert_zum_umfang(modul, const):
    """„Service" sieht Datenpunkte, die „USER" gar nicht erst geliefert bekommt."""
    eintrag = _eintrag(
        modul, const, systeme=[{modul.CONF_HOST: HOST, modul.CONF_USERNAME: "Service"}]
    )
    assert modul._scope(_hass(), eintrag, HOST)["username"] == "Service"
    assert "Service" in modul._scope_fingerprint(modul._scope(_hass(), eintrag, HOST))


def test_ein_anderer_zugang_ergibt_eine_andere_kennung(modul, const):
    mit_user = modul._scope_fingerprint(modul._scope(_hass(), _eintrag(modul, const), HOST))
    mit_service = modul._scope_fingerprint(
        modul._scope(
            _hass(),
            _eintrag(modul, const, systeme=[{modul.CONF_HOST: HOST, "username": "Service"}]),
            HOST,
        )
    )
    assert mit_user != mit_service


def test_eine_andere_sprache_verwirft_den_stand_nicht(modul, const):
    """Sie ändert Bezeichnungen, nicht den Bestand an Datenpunkten.

    Stünde sie im Fingerabdruck, läse jede Anlage bei der Umstellung minutenlang
    neu ein – genau das Verhalten, das seit 1.1.0-beta.2 abgeschafft ist.
    """
    deutsch = modul._scope_fingerprint(modul._scope(_hass("de"), _eintrag(modul, const), HOST))
    franzoesisch = modul._scope_fingerprint(modul._scope(_hass("fr"), _eintrag(modul, const), HOST))
    assert deutsch == franzoesisch


def test_eine_andere_sprache_loest_den_abgleich_aus(modul, const):
    """Sofort da sein und nachziehen – wie bei einem Fassungswechsel."""
    stand = _stand(modul, const, sprache="de")

    assert modul._abgleich_noetig(stand, "1.5.0", "fr")
    assert not modul._abgleich_noetig(stand, "1.5.0", "de")


def test_ein_stand_ohne_sprache_gilt_als_deutsch(modul, const):
    """Stände aus einer Fassung vor der Sprachwahl tragen den Schlüssel nicht."""
    ohne = _stand(modul, const)
    ohne.pop("sprache", None)

    assert not modul._abgleich_noetig(ohne, "1.5.0", "de")
    assert modul._abgleich_noetig(ohne, "1.5.0", "en")


def test_die_gewaehlte_sprache_schlaegt_die_von_home_assistant(modul, const):
    eintrag = _eintrag(modul, const, optionen={const.CONF_SPRACHE: "it"})
    assert modul._scope(_hass("fr"), eintrag, HOST)["sprache"] == "it"


def test_automatisch_auf_dieselbe_sprache_aendert_die_kennung_nicht(modul, const):
    # „auto" wird aufgelöst gespeichert. Wer von „auto" auf genau die Sprache
    # umstellt, die ohnehin galt, soll keinen Neuabzug auslösen.
    automatisch = modul._scope_fingerprint(modul._scope(_hass("fr"), _eintrag(modul, const), HOST))
    ausdruecklich = modul._scope_fingerprint(
        modul._scope(_hass("fr"), _eintrag(modul, const, optionen={const.CONF_SPRACHE: "fr"}), HOST)
    )
    assert automatisch == ausdruecklich


# ---------------------------------------------------------------------------
# Gültigkeit des gespeicherten Stands
# ---------------------------------------------------------------------------
def test_ein_frischer_stand_derselben_anlage_gilt(modul, const):
    kennung = modul._scope_fingerprint(modul._scope(_hass(), _eintrag(modul, const), HOST))
    assert modul._discovery_cache_valid(_stand(modul, const), HOST, kennung)


def test_eine_neue_fassung_verwirft_den_stand_nicht(modul, const):
    """Sonst läge die Anlage nach jeder Aktualisierung minutenlang brach."""
    kennung = modul._scope_fingerprint(modul._scope(_hass(), _eintrag(modul, const), HOST))
    alt = _stand(modul, const, version="0.9.0")
    assert modul._discovery_cache_valid(alt, HOST, kennung)
    # Sie löst aber einen Abgleich im Hintergrund aus.
    assert modul._abgleich_noetig(alt, "1.5.0", "de")
    assert not modul._abgleich_noetig(_stand(modul, const), "1.5.0", "de")


def test_eine_andere_anlage_verwirft_den_stand(modul, const):
    kennung = modul._scope_fingerprint(modul._scope(_hass(), _eintrag(modul, const), HOST))
    assert not modul._discovery_cache_valid(_stand(modul, const), "192.0.2.11", kennung)


def test_ein_geaenderter_umfang_verwirft_den_stand(modul, const):
    assert not modul._discovery_cache_valid(_stand(modul, const), HOST, "ganz anders")


def test_ein_zu_alter_stand_verwirft_sich_selbst(modul, const):
    from homeassistant.util import dt as dt_util

    kennung = modul._scope_fingerprint(modul._scope(_hass(), _eintrag(modul, const), HOST))
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
def _umfang(levels, **schalter):
    """Umfang in der Form, die `_scope` liefert.

    Die Schalter stehen vollständig da, auch wenn ein Test nur einen davon
    verstellt: Die Prüfung leitet die Abwahl aus dem Umfang selbst ab, und ein
    fehlender Schlüssel wäre etwas anderes als ein abgeschalteter.
    """
    umfang = {
        "levels": levels,
        "enable_advanced": False,
        "writable_advanced": False,
        "zeitwerte": False,
        "lon": False,
        "update_interval": 30,
        "username": "USER",
        "sprache": "de",
    }
    umfang.update(schalter)
    return umfang


def test_eine_abgewaehlte_ebene_ist_eine_entscheidung(modul):
    alt = {HOST: _umfang(["info", "operate", "service"])}
    neu = {HOST: _umfang(["info", "operate"])}
    assert modul._umfang_verkleinert(alt, neu)


def test_eine_zusaetzliche_ebene_ist_keine_abwahl(modul):
    alt = {HOST: _umfang(["info"])}
    neu = {HOST: _umfang(["info", "operate"])}
    assert not modul._umfang_verkleinert(alt, neu)


@pytest.mark.parametrize(
    "schalter", ["enable_advanced", "writable_advanced", "zeitwerte", "lon", "kuenftige_option"]
)
def test_ein_abgeschalteter_schalter_zaehlt_als_abwahl(modul, schalter):
    """Jeder Schalter zählt, auch einer, den der Umfang hier noch nicht führt."""
    alt = {HOST: _umfang(["info"], **{schalter: True})}
    neu = {HOST: _umfang(["info"], **{schalter: False})}
    assert modul._umfang_verkleinert(alt, neu)


@pytest.mark.parametrize("schalter", ["enable_advanced", "writable_advanced", "zeitwerte", "lon"])
def test_ein_eingeschalteter_schalter_ist_keine_abwahl(modul, schalter):
    alt = {HOST: _umfang(["info"], **{schalter: False})}
    neu = {HOST: _umfang(["info"], **{schalter: True})}
    assert not modul._umfang_verkleinert(alt, neu)


def test_eine_ebene_getauscht_bleibt_eine_abwahl(modul):
    """Gleichzeitig abwählen und hinzunehmen ist trotzdem eine Abwahl."""
    alt = {HOST: _umfang(["info", "operate"])}
    neu = {HOST: _umfang(["operate", "service"])}
    assert modul._umfang_verkleinert(alt, neu)


@pytest.mark.parametrize(
    ("feld", "wert"), [("update_interval", 120), ("username", "Service"), ("sprache", "en")]
)
def test_was_keinen_datenpunkt_entfernt_ist_keine_abwahl(modul, feld, wert):
    """Intervall, Zugang und Sprache ändern den Bestand nicht.

    Sie stehen im selben Umfang und dürfen die Ableitung nicht auslösen –
    sonst löschte ein Sprachwechsel die Anlage.
    """
    alt = {HOST: _umfang(["info"])}
    neu = {HOST: _umfang(["info"], **{feld: wert})}
    assert not modul._umfang_verkleinert(alt, neu)


def test_eine_entfernte_anlage_zaehlt_als_abwahl(modul):
    assert modul._umfang_verkleinert({HOST: _umfang(["info"])}, {})


def test_die_vormerkung_gilt_genau_einmal(modul, const, hass):
    """Sonst räumte auch der übernächste Ladevorgang noch auf."""
    eintrag = _eintrag(modul, const)
    assert not modul._abwahl_abholen(hass, eintrag)
    modul._abwahl_vormerken(hass, eintrag)
    assert modul._abwahl_abholen(hass, eintrag)
    assert not modul._abwahl_abholen(hass, eintrag)


def _eintrag_in_hass(hass):
    """Ein Eintrag mit einer Entität in der Registry."""
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.const import DOMAIN

    eintrag = MockConfigEntry(domain=DOMAIN, title="PuroWin40", data={}, options={})
    eintrag.add_to_hass(hass)
    entitaet = er.async_get(hass).async_get_or_create(
        "sensor", DOMAIN, "SN1-0-0-7-0", config_entry=eintrag
    )
    return eintrag, entitaet.entity_id


def _koordinator(daten):
    """Ein Koordinator, dessen Anlage vollständig eingelesen ist."""
    return SimpleNamespace(data=daten, client=SimpleNamespace(_vollstaendig=True))


def test_ein_abruf_ohne_daten_legt_nichts_still(modul, hass):
    """Eine Zeitüberschreitung ist kein weggefallener Datenpunkt.

    Der Erkennungsstand kommt aus dem Zwischenspeicher, die Anlage gilt damit
    als vollständig eingelesen – aber der erste Abruf lief in die
    Zeitüberschreitung und ``coordinator.data`` blieb leer. Die Liste der
    bekannten Datenpunkte war dann leer, und **jede** Entität des Eintrags
    galt als abgewählt: In 1.5.0-beta.9 lagen danach 285 Entitäten still und
    kein einziger Wert stand mehr da.
    """
    from homeassistant.helpers import entity_registry as er

    eintrag, entitaet = _eintrag_in_hass(hass)

    modul._abgewaehlte_entitaeten_stilllegen(hass, eintrag, {"a": _koordinator(None)})

    assert er.async_get(hass).async_get(entitaet).disabled_by is None


def test_eine_anlage_ohne_daten_schuetzt_auch_die_andere(modul, hass):
    """Zwei Anlagen: Antwortet eine nicht, wird für keine aufgeräumt.

    Die Deskriptoren beider Anlagen landen in derselben Liste. Fehlt die eine,
    fehlt in der Liste die Hälfte – und die Entitäten der stummen Anlage
    stünden als abgewählt da, obwohl niemand etwas abgewählt hat.
    """
    from homeassistant.helpers import entity_registry as er

    eintrag, entitaet = _eintrag_in_hass(hass)
    koordinatoren = {
        "a": _koordinator({"devices": [{"id": "irgendwas", "enabled_default": True}]}),
        "b": _koordinator(None),
    }

    modul._abgewaehlte_entitaeten_stilllegen(hass, eintrag, koordinatoren)

    assert er.async_get(hass).async_get(entitaet).disabled_by is None


def test_ein_wirklich_weggefallener_datenpunkt_wird_stillgelegt(modul, hass):
    """Die Gegenprobe: Antwortet die Anlage und fehlt der Datenpunkt, gilt er als weg."""
    from homeassistant.helpers import entity_registry as er

    eintrag, entitaet = _eintrag_in_hass(hass)
    koordinator = _koordinator({"devices": [{"id": "ein-anderer", "enabled_default": True}]})

    modul._abgewaehlte_entitaeten_stilllegen(hass, eintrag, {"a": koordinator})

    assert (
        er.async_get(hass).async_get(entitaet).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    )


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
    assert modul._store_key(eintrag, HOST) != modul._store_key(eintrag, "192.0.2.11")
    assert "192_0_2_10" in modul._store_key(eintrag, HOST)


def test_die_anlagen_kommen_aus_den_eintragsdaten(modul, const):
    assert modul._systems(_eintrag(modul, const)) == [{modul.CONF_HOST: HOST}]
    assert modul._systems(_eintrag(modul, const, systeme=[])) == []


# ---------------------------------------------------------------------------
# Hinweis auf den nötigen Neustart
# ---------------------------------------------------------------------------
def test_der_neustart_hinweis_kommt_und_geht(modul, monkeypatch):
    """Er erscheint beim Sprachwechsel und löst sich beim nächsten Start auf.

    Ein Entitätsname entsteht bei der Erzeugung; der Abgleich im Hintergrund
    schreibt ihn nur in den Erkennungsstand.
    """
    angelegt: list[str] = []
    geloescht: list[str] = []
    monkeypatch.setattr(
        modul.ir,
        "async_create_issue",
        lambda hass, bereich, kennung, **rest: angelegt.append(kennung),
    )
    monkeypatch.setattr(
        modul.ir, "async_delete_issue", lambda hass, bereich, kennung: geloescht.append(kennung)
    )
    eintrag = SimpleNamespace(entry_id="eintrag1")

    modul._neustart_hinweis(None, eintrag, HOST, True)
    modul._neustart_hinweis(None, eintrag, HOST, False)

    assert angelegt == [f"sprache_neustart_eintrag1_{HOST}"]
    assert geloescht == [f"sprache_neustart_eintrag1_{HOST}"]


# ---------------------------------------------------------------------------
# Abwahl über den Neustart hinaus
# ---------------------------------------------------------------------------
def test_ein_stand_mit_groesserem_umfang_zeigt_die_abwahl(modul):
    """Der Vergleich im Arbeitsspeicher kennt nur den Moment der Änderung.

    Nach einem Neustart entscheidet der Stand auf der Platte – sonst blieben
    die Entitäten der abgewählten Option für immer abgeschaltet stehen.
    """
    stand = {"umfang": _umfang(["info", "operate"], lon=True)}
    assert modul._abwahl_im_stand(stand, _umfang(["info", "operate"], lon=False))
    assert modul._abwahl_im_stand(stand, _umfang(["info"], lon=True))


def test_ein_stand_mit_kleinerem_umfang_ist_keine_abwahl(modul):
    stand = {"umfang": _umfang(["info"])}
    assert not modul._abwahl_im_stand(stand, _umfang(["info", "operate"]))
    assert not modul._abwahl_im_stand(stand, _umfang(["info"]))


@pytest.mark.parametrize("stand", [None, {}, {"umfang": "kein Wörterbuch"}, "kaputt"])
def test_ein_stand_ohne_umfang_loest_nichts_aus(modul, stand):
    """Stände aus einer Fassung vor dieser Prüfung beweisen nichts."""
    assert not modul._abwahl_im_stand(stand, _umfang(["info"]))


# ---------------------------------------------------------------------------
# Waisen einer abgeschalteten Quelle
# ---------------------------------------------------------------------------
def test_netzwerkvariablen_bei_abgeschaltetem_bus_gelten_als_abgewaehlt(modul):
    umfaenge = {HOST: _umfang(["info"], lon=False)}
    assert modul._quelle_abgeschaltet("070269ad1601-nv-0-1-nvostatus", umfaenge)


def test_netzwerkvariablen_bei_eingeschaltetem_bus_bleiben(modul):
    """Sie fehlen dann aus einem anderen Grund und behalten Name und Verlauf."""
    umfaenge = {HOST: _umfang(["info"], lon=True)}
    assert not modul._quelle_abgeschaltet("070269ad1601-nv-0-1-nvostatus", umfaenge)


def test_eine_zweite_anlage_mit_bus_schuetzt_die_kennungen(modul):
    umfaenge = {HOST: _umfang(["info"], lon=False), "192.0.2.11": _umfang(["info"], lon=True)}
    assert not modul._quelle_abgeschaltet("070269ad1601-nv-0-1-nvostatus", umfaenge)


@pytest.mark.parametrize("kennung", [None, "", "070269ad1601-0-39-91-0"])
def test_ein_gewoehnlicher_datenpunkt_wird_nur_stillgelegt(modul, kennung):
    """Kein Bus-Wert – über ihn entscheidet allein der Umfangsvergleich."""
    assert not modul._quelle_abgeschaltet(kennung, {HOST: _umfang(["info"], lon=False)})
