"""Registrierte Entitäten, zu denen es keinen Datenpunkt mehr gibt.

Stillgelegt werden sie von selbst – niemand hat sie abgewählt, also bleiben
Name, Bereich und Verlauf erhalten. Entfernt werden sie erst, wenn der Nutzer
den Reparatureintrag bestätigt.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def modul():
    from custom_components.heatnexus import verwaiste

    return verwaiste


def _koordinator(kennungen):
    """Ein vollständig eingelesener Koordinator mit diesen Kennungen."""
    devices = [{"id": kennung, "enabled_default": True} for kennung in kennungen]
    return SimpleNamespace(data={"devices": devices}, client=SimpleNamespace(_vollstaendig=True))


def _eintrag_mit_entitaet(hass, kennung="SN1-0-0-7-0"):
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.const import DOMAIN

    eintrag = MockConfigEntry(domain=DOMAIN, title="HeatNexus", data={}, options={})
    eintrag.add_to_hass(hass)
    entitaet = er.async_get(hass).async_get_or_create(
        "sensor", DOMAIN, kennung, config_entry=eintrag
    )
    return eintrag, entitaet.entity_id


def _hinweis(hass, eintrag, modul):
    from homeassistant.helpers import issue_registry as ir

    from custom_components.heatnexus.const import DOMAIN

    return ir.async_get(hass).async_get_issue(
        DOMAIN, modul.HINWEIS.format(entry_id=eintrag.entry_id)
    )


def test_ein_fehlender_datenpunkt_gilt_als_verwaist(modul, hass):
    eintrag, entitaet = _eintrag_mit_entitaet(hass)

    gefunden = modul.finden(hass, eintrag, {"a": _koordinator(["ein-anderer"])})

    assert [e.entity_id for e in gefunden] == [entitaet]


def test_ein_vorhandener_datenpunkt_zaehlt_nicht(modul, hass):
    eintrag, _ = _eintrag_mit_entitaet(hass)

    assert not modul.finden(hass, eintrag, {"a": _koordinator(["SN1-0-0-7-0"])})


def test_ohne_vollstaendigen_abzug_wird_nichts_gemeldet(modul, hass):
    """Ein Abruf ohne Daten heißt nicht, dass es keine Datenpunkte gibt."""
    eintrag, _ = _eintrag_mit_entitaet(hass)
    unfertig = SimpleNamespace(data=None, client=SimpleNamespace(_vollstaendig=True))

    assert not modul.finden(hass, eintrag, {"a": unfertig})


def test_eine_stumme_anlage_schuetzt_die_andere(modul, hass):
    """Beide Anlagen füllen dieselbe Liste; fehlt eine, fehlt die Hälfte."""
    eintrag, _ = _eintrag_mit_entitaet(hass)
    koordinatoren = {
        "a": _koordinator(["ein-anderer"]),
        "b": SimpleNamespace(data=None, client=SimpleNamespace(_vollstaendig=True)),
    }

    assert not modul.finden(hass, eintrag, koordinatoren)


def test_der_hinweis_kommt_und_geht(modul, hass):
    eintrag, _ = _eintrag_mit_entitaet(hass)

    modul.hinweis_pflegen(hass, eintrag, 3)
    hinweis = _hinweis(hass, eintrag, modul)
    assert hinweis is not None
    assert hinweis.translation_placeholders == {"anzahl": "3"}
    assert hinweis.is_fixable

    modul.hinweis_pflegen(hass, eintrag, 0)
    assert _hinweis(hass, eintrag, modul) is None


def test_entfernen_loescht_nur_die_verwaiste(modul, hass):
    from homeassistant.helpers import entity_registry as er

    eintrag, verwaist = _eintrag_mit_entitaet(hass)
    registry = er.async_get(hass)
    from custom_components.heatnexus.const import DOMAIN

    bleibt = registry.async_get_or_create(
        "sensor", DOMAIN, "SN1-0-0-8-0", config_entry=eintrag
    ).entity_id
    modul.hinweis_pflegen(hass, eintrag, 1)

    assert modul.entfernen(hass, eintrag, {"a": _koordinator(["SN1-0-0-8-0"])}) == 1

    assert registry.async_get(verwaist) is None
    assert registry.async_get(bleibt) is not None
    assert _hinweis(hass, eintrag, modul) is None


def test_entfernen_ohne_bestand_ruehrt_nichts_an(modul, hass):
    """Kommt der Klick, während keine Anlage antwortet, bleibt alles stehen."""
    from homeassistant.helpers import entity_registry as er

    eintrag, entitaet = _eintrag_mit_entitaet(hass)
    unfertig = SimpleNamespace(data=None, client=SimpleNamespace(_vollstaendig=True))

    assert modul.entfernen(hass, eintrag, {"a": unfertig}) == 0
    assert er.async_get(hass).async_get(entitaet) is not None


async def test_der_reparaturablauf_entfernt_nach_bestaetigung(hass):
    from homeassistant.data_entry_flow import FlowResultType
    from homeassistant.helpers import entity_registry as er

    from custom_components.heatnexus import repairs, verwaiste

    eintrag, verwaist = _eintrag_mit_entitaet(hass)
    eintrag.runtime_data = {"coordinators": {"a": _koordinator(["ein-anderer"])}}
    ablauf = await repairs.async_create_fix_flow(
        hass, verwaiste.HINWEIS.format(entry_id=eintrag.entry_id), {"entry_id": eintrag.entry_id}
    )
    ablauf.hass = hass

    formular = await ablauf.async_step_init()
    assert formular["step_id"] == "confirm"
    assert formular["description_placeholders"] == {"anzahl": "1"}

    ergebnis = await ablauf.async_step_confirm({})
    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    assert er.async_get(hass).async_get(verwaist) is None


async def test_der_ablauf_bricht_ab_wenn_der_eintrag_nicht_geladen_ist(hass):
    from homeassistant.data_entry_flow import FlowResultType

    from custom_components.heatnexus import repairs, verwaiste

    eintrag, _ = _eintrag_mit_entitaet(hass)
    ablauf = await repairs.async_create_fix_flow(
        hass, verwaiste.HINWEIS.format(entry_id=eintrag.entry_id), {"entry_id": eintrag.entry_id}
    )
    ablauf.hass = hass

    ergebnis = await ablauf.async_step_init()
    assert ergebnis["type"] is FlowResultType.ABORT
    assert ergebnis["reason"] == "nicht_geladen"


def test_die_stilllegung_meldet_den_hinweis(hass, modul):
    """Der Weg, den der Nutzer wirklich geht: Abgleich beim Laden."""
    import custom_components.heatnexus as heatnexus

    eintrag, _entitaet = _eintrag_mit_entitaet(hass)
    koordinatoren = {"a": _koordinator(["ein-anderer"])}

    heatnexus._abgewaehlte_entitaeten_stilllegen(hass, eintrag, koordinatoren)

    hinweis = _hinweis(hass, eintrag, modul)
    assert hinweis is not None
    assert hinweis.translation_placeholders == {"anzahl": "1"}


def test_der_hinweis_geht_zurueck_wenn_der_datenpunkt_wiederkommt(hass, modul):
    """Über den echten Weg, nicht über den direkten Aufruf."""
    import custom_components.heatnexus as heatnexus

    eintrag, _entitaet = _eintrag_mit_entitaet(hass)
    heatnexus._abgewaehlte_entitaeten_stilllegen(hass, eintrag, {"a": _koordinator(["fremd"])})
    assert _hinweis(hass, eintrag, modul) is not None

    heatnexus._abgewaehlte_entitaeten_stilllegen(
        hass, eintrag, {"a": _koordinator(["SN1-0-0-7-0"])}
    )

    assert _hinweis(hass, eintrag, modul) is None


def test_ein_abruf_ohne_daten_nimmt_den_hinweis_zurueck(hass, modul):
    """Eine Zahl, die niemand nachrechnen kann, bleibt nicht stehen."""
    import custom_components.heatnexus as heatnexus

    eintrag, _entitaet = _eintrag_mit_entitaet(hass)
    heatnexus._abgewaehlte_entitaeten_stilllegen(hass, eintrag, {"a": _koordinator(["fremd"])})
    assert _hinweis(hass, eintrag, modul) is not None

    stumm = SimpleNamespace(data=None, client=SimpleNamespace(_vollstaendig=True))
    heatnexus._abgewaehlte_entitaeten_stilllegen(hass, eintrag, {"a": stumm})

    assert _hinweis(hass, eintrag, modul) is None


def test_eine_von_hand_abgeschaltete_entitaet_zaehlt_mit(modul, hass):
    """Ohne Datenpunkt ist sie verwaist, gleich wer sie abgeschaltet hat."""
    from homeassistant.helpers import entity_registry as er

    eintrag, entitaet = _eintrag_mit_entitaet(hass)
    registry = er.async_get(hass)
    registry.async_update_entity(entitaet, disabled_by=er.RegistryEntryDisabler.USER)

    gefunden = modul.finden(hass, eintrag, {"a": _koordinator(["fremd"])})

    assert [e.entity_id for e in gefunden] == [entitaet]


async def test_eine_fremde_kennung_bekommt_keinen_ablauf(hass):
    """Sonst löschte ein künftiger zweiter Hinweis Entitäten."""
    import pytest as _pytest

    from custom_components.heatnexus import repairs

    with _pytest.raises(ValueError):
        await repairs.async_create_fix_flow(hass, "irgendein_anderer_hinweis", {})
