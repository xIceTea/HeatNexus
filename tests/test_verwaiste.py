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
    platzhalter = formular["description_placeholders"]
    assert platzhalter["anzahl"] == "1"
    assert platzhalter["liste_anfang"] == "<details><summary>"
    assert platzhalter["liste_ende"].startswith("</summary>\n\n")
    assert f"- `{verwaist}`" in platzhalter["liste_ende"]
    assert platzhalter["liste_ende"].endswith("\n\n</details>")

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
    from custom_components.heatnexus import stilllegung

    eintrag, _entitaet = _eintrag_mit_entitaet(hass)
    koordinatoren = {"a": _koordinator(["ein-anderer"])}

    stilllegung.abgewaehlte_entitaeten_stilllegen(hass, eintrag, koordinatoren)

    hinweis = _hinweis(hass, eintrag, modul)
    assert hinweis is not None
    assert hinweis.translation_placeholders == {"anzahl": "1"}


def test_der_hinweis_geht_zurueck_wenn_der_datenpunkt_wiederkommt(hass, modul):
    """Über den echten Weg, nicht über den direkten Aufruf."""
    from custom_components.heatnexus import stilllegung

    eintrag, _entitaet = _eintrag_mit_entitaet(hass)
    stilllegung.abgewaehlte_entitaeten_stilllegen(hass, eintrag, {"a": _koordinator(["fremd"])})
    assert _hinweis(hass, eintrag, modul) is not None

    stilllegung.abgewaehlte_entitaeten_stilllegen(
        hass, eintrag, {"a": _koordinator(["SN1-0-0-7-0"])}
    )

    assert _hinweis(hass, eintrag, modul) is None


def test_ein_abruf_ohne_daten_nimmt_den_hinweis_zurueck(hass, modul):
    """Eine Zahl, die niemand nachrechnen kann, bleibt nicht stehen."""
    from custom_components.heatnexus import stilllegung

    eintrag, _entitaet = _eintrag_mit_entitaet(hass)
    stilllegung.abgewaehlte_entitaeten_stilllegen(hass, eintrag, {"a": _koordinator(["fremd"])})
    assert _hinweis(hass, eintrag, modul) is not None

    stumm = SimpleNamespace(data=None, client=SimpleNamespace(_vollstaendig=True))
    stilllegung.abgewaehlte_entitaeten_stilllegen(hass, eintrag, {"a": stumm})

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


# Wechselt ein Datenpunkt die Plattform, bleibt die Zeile der alten Domäne
# liegen: Die Kennung steht weiter im Bestand, nur unter `switch.` statt
# `sensor.`. Ohne Domänenvergleich sieht der Reparatureintrag sie nie.
def test_eine_zeile_der_falschen_domaene_gilt_als_verwaist(modul, hass):
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.const import DOMAIN
    from custom_components.heatnexus.entity import TYP_DOMAENE

    # Die Zuordnung ist Modulzustand; ohne Aufräumen wirkte sie in jeden
    # folgenden Test hinein.
    vorher = dict(TYP_DOMAENE)
    TYP_DOMAENE["sensor"] = "sensor"
    eintrag = MockConfigEntry(domain=DOMAIN, title="HeatNexus", data={}, options={})
    eintrag.add_to_hass(hass)
    registry = er.async_get(hass)
    alt = registry.async_get_or_create("switch", DOMAIN, "SN1-0-0-9-90-0", config_entry=eintrag)
    neu = registry.async_get_or_create("sensor", DOMAIN, "SN1-0-0-9-90-0", config_entry=eintrag)

    koordinator = SimpleNamespace(
        data={"devices": [{"id": "SN1-0-0-9-90-0", "type": "sensor", "enabled_default": True}]},
        client=SimpleNamespace(_vollstaendig=True),
    )
    gefunden = [e.entity_id for e in modul.finden(hass, eintrag, {"a": koordinator})]

    TYP_DOMAENE.clear()
    TYP_DOMAENE.update(vorher)

    assert alt.entity_id in gefunden
    assert neu.entity_id not in gefunden


def test_ein_unbekannter_typ_gilt_nicht_als_verwaist(modul, hass):
    """Ist die Plattform noch nicht angelegt, wird nichts unterstellt."""
    from custom_components.heatnexus.entity import TYP_DOMAENE

    TYP_DOMAENE.pop("kuenftig", None)
    eintrag, _entitaet = _eintrag_mit_entitaet(hass, "SN1-0-0-7-0")
    koordinator = SimpleNamespace(
        data={"devices": [{"id": "SN1-0-0-7-0", "type": "kuenftig", "enabled_default": True}]},
        client=SimpleNamespace(_vollstaendig=True),
    )

    assert not modul.finden(hass, eintrag, {"a": koordinator})


def test_die_stilllegung_zaehlt_die_falsche_domaene_mit(hass, modul):
    """Sonst meldet der Hinweis null, während die alte Zeile stehen bleibt."""
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus import stilllegung
    from custom_components.heatnexus.const import DOMAIN
    from custom_components.heatnexus.entity import TYP_DOMAENE

    vorher = dict(TYP_DOMAENE)
    TYP_DOMAENE["sensor"] = "sensor"
    eintrag = MockConfigEntry(domain=DOMAIN, title="HeatNexus", data={}, options={})
    eintrag.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create("switch", DOMAIN, "SN1-0-0-9-90-0", config_entry=eintrag)
    registry.async_get_or_create("sensor", DOMAIN, "SN1-0-0-9-90-0", config_entry=eintrag)
    koordinator = SimpleNamespace(
        data={"devices": [{"id": "SN1-0-0-9-90-0", "type": "sensor", "enabled_default": True}]},
        client=SimpleNamespace(_vollstaendig=True),
    )

    stilllegung.abgewaehlte_entitaeten_stilllegen(hass, eintrag, {"a": koordinator})

    TYP_DOMAENE.clear()
    TYP_DOMAENE.update(vorher)
    hinweis = _hinweis(hass, eintrag, modul)
    assert hinweis is not None
    assert hinweis.translation_placeholders == {"anzahl": "1"}


def test_ein_wieder_eingeschalteter_wert_wird_sofort_gemeldet(hass):
    """Sonst entstünde er erst beim nächsten Laden des Eintrags."""
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.dispatcher import async_dispatcher_connect
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus import stilllegung
    from custom_components.heatnexus.const import DOMAIN, SIGNAL_NEUE_ENTITAETEN

    eintrag = MockConfigEntry(domain=DOMAIN, title="HeatNexus", data={}, options={})
    eintrag.add_to_hass(hass)
    registry = er.async_get(hass)
    entitaet = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "SN1-0-2-1-0-laufzeit",
        config_entry=eintrag,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    koordinator = SimpleNamespace(
        data={
            "devices": [{"id": "SN1-0-2-1-0-laufzeit", "type": "laufzeit", "enabled_default": True}]
        },
        client=SimpleNamespace(_vollstaendig=True),
    )

    gerufen = []
    async_dispatcher_connect(
        hass, SIGNAL_NEUE_ENTITAETEN.format(eintrag.entry_id), lambda: gerufen.append(1)
    )
    stilllegung.abgewaehlte_entitaeten_stilllegen(hass, eintrag, {"a": koordinator})

    assert registry.async_get(entitaet.entity_id).disabled_by is None
    assert gerufen, "Die Plattformen wurden nicht benachrichtigt"


async def test_die_entitaeten_einer_automatik_sind_nicht_verwaist(modul, hass):
    """Sie hängen an keinem Datenpunkt, sondern an einer eingerichteten Automatik."""
    from homeassistant.helpers import entity_registry as er

    from custom_components.heatnexus.automatik.verwaltung import verwaltung_holen
    from custom_components.heatnexus.const import DOMAIN

    eintrag, _ = _eintrag_mit_entitaet(hass)
    verwaltung = verwaltung_holen(hass)
    await verwaltung.laden()
    verwaltung._daten["heizkreise"]["SN1-2-0"] = {
        "konfig": {"entry_id": eintrag.entry_id},
        "zustand": {},
    }
    register = er.async_get(hass)
    for domaene, art in (("select", "modus"), ("sensor", "zustand")):
        register.async_get_or_create(
            domaene, DOMAIN, f"SN1-2-0-automatik-{art}", config_entry=eintrag
        )

    gefunden = modul.finden(hass, eintrag, {"a": _koordinator(["SN1-0-0-7-0"])})

    assert gefunden == []
    assert modul.bekannte_kennungen(eintrag, {"a": _koordinator([])}, hass)[
        "SN1-2-0-automatik-zustand"
    ]


def test_der_stoerspeicher_der_steuerung_ist_nicht_verwaist(modul, hass):
    """Er hängt an der Steuerung, nicht an einem Datenpunkt eines Geräts."""
    eintrag, entitaet = _eintrag_mit_entitaet(hass, "steuerung-SN1-stoerspeicher")
    koordinator = _koordinator(["SN1-0-0-7-0"])
    koordinator.data["stoerspeicher"] = []
    koordinator.client.steuerung_kennung = lambda: "steuerung-SN1"

    assert modul.finden(hass, eintrag, {"a": koordinator}) == []

    koordinator.data["stoerspeicher"] = None
    assert [e.entity_id for e in modul.finden(hass, eintrag, {"a": koordinator})] == [entitaet]


@pytest.mark.parametrize("kennung", ["SN1-0-9-75-0", "SN1-0-39-94-0"])
def test_eine_bewusst_entfallene_auswahl_wird_geloescht(hass, modul, kennung):
    """`9/75` und `39/94` bietet HeatNexus nicht als Auswahl an; das ist kein Fall für den Hinweis."""
    from homeassistant.helpers import entity_registry as er

    from custom_components.heatnexus import stilllegung
    from custom_components.heatnexus.const import DOMAIN

    eintrag, messwert = _eintrag_mit_entitaet(hass)
    registry = er.async_get(hass)
    auswahl = registry.async_get_or_create(
        "select", DOMAIN, kennung, config_entry=eintrag
    ).entity_id

    stilllegung.abgewaehlte_entitaeten_stilllegen(hass, eintrag, {"a": _koordinator(["fremd"])})

    assert registry.async_get(auswahl) is None
    assert registry.async_get(messwert).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert _hinweis(hass, eintrag, modul).translation_placeholders == {"anzahl": "1"}


def _registereintrag(domaene, adresse):
    return SimpleNamespace(domain=domaene, unique_id=f"SN1-25-{adresse.replace('/', '-')}-0")


@pytest.mark.parametrize(
    ("domaene", "adresse", "erwartet"),
    [
        ("select", "9/75", True),
        ("number", "43/42", True),
        ("number", "43/78", True),
        ("button", "9/75", False),
        ("switch", "9/75", False),
        ("sensor", "43/42", False),
    ],
)
def test_bewusst_entfallene_zeilen_werden_nur_in_ihrer_domaene_geloescht(
    domaene, adresse, erwartet
):
    from custom_components.heatnexus import stilllegung

    assert stilllegung.endgueltig_weg(_registereintrag(domaene, adresse), {}) is erwartet


@pytest.mark.parametrize(
    ("domaene", "kennung", "erwartet"),
    [
        ("switch", "SN1-2-0-automatik-schalter", True),
        ("switch", "SN1-25-9-75-0-kaminkehrer", True),
        ("switch", "SN1-25-9-75-0-befuellen", True),
        ("button", "SN1-25-9-75-0-kaminkehrer", False),
        ("switch", "SN1-25-9-75-0-ein_aus", False),
        ("select", "SN1-2-0-automatik-modus", False),
        ("sensor", "SN1-2-0-automatik-schalter", False),
    ],
)
def test_ein_ersetzter_eintrag_wird_geloescht(domaene, kennung, erwartet):
    """Ersetzte Schalter sind kein Fall für den Hinweis; ihr Nachfolger bleibt."""
    from custom_components.heatnexus import stilllegung

    eintrag = SimpleNamespace(domain=domaene, unique_id=kennung)
    assert stilllegung.endgueltig_weg(eintrag, {}) is erwartet


def test_die_liste_nennt_jede_entitaet_mit_namen(modul):
    eintraege = [
        SimpleNamespace(entity_id="sensor.b", name=None, original_name="Vorlauf"),
        SimpleNamespace(entity_id="sensor.a", name="Eigener Name", original_name="Rücklauf"),
        SimpleNamespace(entity_id="switch.c", name=None, original_name=None),
    ]

    assert modul.liste(eintraege) == "- `sensor.a` – Eigener Name\n- `sensor.b` – Vorlauf\n- `switch.c`"


def test_die_liste_zeigt_sonderzeichen_im_namen_als_text(modul):
    eintrag = SimpleNamespace(entity_id="sensor.p", name="Puffer *oben* [alt] <3", original_name=None)

    assert modul.liste([eintrag]) == r"- `sensor.p` – Puffer \*oben\* \[alt\] \<3"
