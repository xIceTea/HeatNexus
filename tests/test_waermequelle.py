"""Wärmequellen, die nicht an der Steuerung hängen.

Jede steht in einem eigenen Subeintrag und liest fremde Entitäten. Geprüft
wird, dass ihre Kennung stabil bleibt und dass die Anzeige nur behauptet, was
gemessen wurde.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

SOLAR = {
    "id": "q1",
    "name": "Solaranlage",
    "art": "solar",
    "bedingung": {
        "art": "differenz",
        "quelle": "sensor.kollektor",
        "gegen": "sensor.puffer",
        "ein": 8,
        "aus": 3,
    },
}


@pytest.fixture(autouse=True)
def eigene_integration(enable_custom_integrations):
    """Ohne diese Freigabe findet Home Assistant den Ablauf der Quelle nicht."""
    return None


@pytest.fixture(scope="module")
def modul():
    from custom_components.heatnexus import waermequelle

    return waermequelle


def _koordinator(host="192.0.2.10", label="Anlage 1"):
    """Ein Koordinator, dessen Steuerung ihre Seriennummer kennt."""
    return SimpleNamespace(
        host=host,
        label=label,
        client=SimpleNamespace(steuerung_kennung=lambda: "SN1"),
    )


def _eintrag(quellen, host="192.0.2.10"):
    """Ein Eintrag, dessen Quellen als Subeinträge daranhängen."""
    from custom_components.heatnexus.const import SUBEINTRAG_QUELLE

    subeintraege = {
        f"sub{i}": SimpleNamespace(
            subentry_id=f"sub{i}",
            subentry_type=SUBEINTRAG_QUELLE,
            title=q["name"],
            data={
                "host": host,
                "id": q["id"],
                "art": q["art"],
                "pumpe": q.get("pumpe", False),
                "bedingung": q["bedingung"],
            },
        )
        for i, q in enumerate(quellen)
    }
    return SimpleNamespace(subentries=subeintraege, options={})


def test_jede_quelle_wird_zu_einer_beschreibung(modul):
    beschreibungen = modul.beschreibungen(_eintrag([SOLAR]), _koordinator())

    assert len(beschreibungen) == 1
    assert beschreibungen[0]["id"] == "SN1-waermequelle-q1"
    assert beschreibungen[0]["name"] == "Solaranlage"
    assert beschreibungen[0]["bedingung"]["ein"] == 8


def test_die_beschreibung_traegt_die_wahl_zum_laufrad(modul):
    """Ob die Quelle eine Pumpe zeichnet, steht in ihrem Subeintrag."""
    mit = modul.beschreibungen(_eintrag([{**SOLAR, "pumpe": True}]), _koordinator())
    ohne = modul.beschreibungen(_eintrag([SOLAR]), _koordinator())

    assert mit[0]["pumpe"] is True
    assert ohne[0]["pumpe"] is False


def test_eine_quelle_unbekannter_bauart_wird_nicht_gebaut(modul):
    beschreibungen = modul.beschreibungen(
        _eintrag([{**SOLAR, "art": "kernfusion"}]), _koordinator()
    )

    assert beschreibungen == []


def test_quellen_einer_anderen_anlage_bleiben_dort(modul):
    beschreibungen = modul.beschreibungen(_eintrag([SOLAR]), _koordinator(host="192.0.2.99"))

    assert beschreibungen == []


def test_die_quelle_haengt_unter_ihrer_steuerung(modul):
    from custom_components.heatnexus.const import DOMAIN

    beschreibung = modul.beschreibungen(_eintrag([SOLAR]), _koordinator())[0]

    info = modul.geraet_info(_koordinator(), beschreibung)

    assert info["identifiers"] == {(DOMAIN, "SN1-waermequelle-q1")}
    assert info["name"] == "Anlage 1 · Solaranlage"
    assert info["via_device"] == (DOMAIN, "SN1")


def test_die_beschreibung_nennt_ihren_subeintrag(modul):
    """Ohne ihn hinge die Entität am Eintrag statt am Gerät der Quelle."""
    beschreibung = modul.beschreibungen(_eintrag([SOLAR]), _koordinator())[0]

    assert beschreibung["subentry_id"] == "sub0"


def test_alle_kennungen_zaehlen_zum_bestand(modul):
    kennungen = modul.kennungen(_eintrag([SOLAR]), {"192.0.2.10": _koordinator()})

    assert kennungen == {"SN1-waermequelle-q1"}


# ---------------------------------------------------------------------------
# Die Entität
# ---------------------------------------------------------------------------
def _sensor(hass, beschreibung=None):
    from custom_components.heatnexus.binary_sensor import WaermequelleBinarySensor
    from custom_components.heatnexus.waermequelle import beschreibungen

    beschreibung = beschreibung or beschreibungen(_eintrag([SOLAR]), _koordinator())[0]
    entitaet = WaermequelleBinarySensor(_koordinator(), beschreibung)
    entitaet.hass = hass
    return entitaet


async def test_die_quelle_liefert_waerme_ueber_der_einschaltschwelle(hass):
    hass.states.async_set("sensor.kollektor", "70")
    hass.states.async_set("sensor.puffer", "50")
    entitaet = _sensor(hass)

    entitaet._auswerten()

    assert entitaet.is_on is True


async def test_zwischen_den_schwellen_bleibt_es_beim_bisherigen_ergebnis(hass):
    """Ohne den Zwischenbereich flattert die Anzeige an der Grenze."""
    hass.states.async_set("sensor.kollektor", "55")
    hass.states.async_set("sensor.puffer", "50")
    entitaet = _sensor(hass)
    entitaet._laeuft = True

    entitaet._auswerten()

    assert entitaet.is_on is True


async def test_unter_der_ausschaltschwelle_endet_die_lieferung(hass):
    hass.states.async_set("sensor.kollektor", "51")
    hass.states.async_set("sensor.puffer", "50")
    entitaet = _sensor(hass)
    entitaet._laeuft = True

    entitaet._auswerten()

    assert entitaet.is_on is False


async def test_ohne_messwert_wird_keine_lieferung_behauptet(hass):
    """Eine fehlende Entität darf keine Wärme vortäuschen."""
    hass.states.async_set("sensor.kollektor", "70")
    entitaet = _sensor(hass)
    entitaet._laeuft = True

    entitaet._auswerten()

    assert entitaet.is_on is False


async def test_ein_zustand_als_bedingung_braucht_keine_schwelle(hass):
    from custom_components.heatnexus.waermequelle import beschreibungen

    heizstab = {
        "id": "q2",
        "name": "Heizstab",
        "art": "heizstab",
        "bedingung": {"art": "zustand", "quelle": "switch.heizstab"},
    }
    hass.states.async_set("switch.heizstab", "on")
    entitaet = _sensor(hass, beschreibungen(_eintrag([heizstab]), _koordinator())[0])

    entitaet._auswerten()
    assert entitaet.is_on is True

    hass.states.async_set("switch.heizstab", "off")
    entitaet._auswerten()
    assert entitaet.is_on is False


# ---------------------------------------------------------------------------
# Vom Optionseintrag zum Subeintrag
# ---------------------------------------------------------------------------
def _mock_eintrag(hass, optionen):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.const import CONF_SYSTEMS, DOMAIN

    eintrag = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=1,
        data={CONF_SYSTEMS: [{"host": "192.0.2.10", "label": "Anlage 1"}]},
        options=optionen,
    )
    eintrag.add_to_hass(hass)
    return eintrag


async def test_die_alte_auswahl_wandert_in_einen_subeintrag(hass):
    """Die Kennung wandert mit; an ihr hängt die vorhandene Entität."""
    from custom_components.heatnexus import async_migrate_entry
    from custom_components.heatnexus.const import CONF_QUELLEN, SUBEINTRAG_QUELLE

    eintrag = _mock_eintrag(hass, {"192.0.2.10": {CONF_QUELLEN: [SOLAR], "modulpumpe": True}})

    assert await async_migrate_entry(hass, eintrag) is True

    quellen = [s for s in eintrag.subentries.values() if s.subentry_type == SUBEINTRAG_QUELLE]
    assert len(quellen) == 1
    assert quellen[0].title == "Solaranlage"
    assert quellen[0].data["id"] == "q1"
    assert quellen[0].data["host"] == "192.0.2.10"
    assert quellen[0].data["bedingung"]["ein"] == 8
    assert CONF_QUELLEN not in eintrag.options["192.0.2.10"]
    assert eintrag.options["192.0.2.10"]["modulpumpe"] is True
    assert eintrag.minor_version == 2


async def test_ein_zweiter_lauf_legt_nichts_doppelt_an(hass):
    from custom_components.heatnexus import async_migrate_entry
    from custom_components.heatnexus.const import CONF_QUELLEN, SUBEINTRAG_QUELLE

    eintrag = _mock_eintrag(hass, {"192.0.2.10": {CONF_QUELLEN: [SOLAR]}})
    await async_migrate_entry(hass, eintrag)

    assert await async_migrate_entry(hass, eintrag) is True

    quellen = [s for s in eintrag.subentries.values() if s.subentry_type == SUBEINTRAG_QUELLE]
    assert len(quellen) == 1


async def test_eine_neue_quelle_entsteht_als_subeintrag(hass):
    from homeassistant.data_entry_flow import FlowResultType

    from custom_components.heatnexus.const import SUBEINTRAG_QUELLE

    eintrag = _mock_eintrag(hass, {})
    ablauf = await hass.config_entries.subentries.async_init(
        (eintrag.entry_id, SUBEINTRAG_QUELLE), context={"source": "user"}
    )

    regel = await hass.config_entries.subentries.async_configure(
        ablauf["flow_id"],
        {
            "name": "Fernwärme",
            "art": "fremdquelle",
            "bedingung_art": "zustand",
            "quelle": "binary_sensor.uebergabe",
        },
    )
    assert regel["step_id"] == "regel"

    ergebnis = await hass.config_entries.subentries.async_configure(ablauf["flow_id"], {})

    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    assert ergebnis["title"] == "Fernwärme"
    assert ergebnis["data"]["id"] == "q1"
    assert ergebnis["data"]["host"] == "192.0.2.10"


async def test_ein_zustand_im_klartext_wird_zum_schaltpunkt(hass):
    """Ein Sensor mit Klartext liefert nur bei den gewählten Zuständen."""
    from custom_components.heatnexus.const import SUBEINTRAG_QUELLE

    hass.states.async_set("sensor.solarstatus", "Solaranlage inaktiv")
    eintrag = _mock_eintrag(hass, {})
    ablauf = await hass.config_entries.subentries.async_init(
        (eintrag.entry_id, SUBEINTRAG_QUELLE), context={"source": "user"}
    )

    await hass.config_entries.subentries.async_configure(
        ablauf["flow_id"],
        {
            "name": "Solaranlage",
            "art": "solar",
            "bedingung_art": "zustand",
            "quelle": "sensor.solarstatus",
        },
    )
    ergebnis = await hass.config_entries.subentries.async_configure(
        ablauf["flow_id"], {"zustaende": ["Solaranlage aktiv"]}
    )

    assert ergebnis["data"]["bedingung"] == {
        "art": "zustand",
        "quelle": "sensor.solarstatus",
        "zustaende": ["Solaranlage aktiv"],
    }


async def test_eine_schwelle_traegt_keine_zustaende(hass):
    """Der Wechsel der Bedingungsart lässt nichts von der vorigen stehen."""
    from custom_components.heatnexus.const import SUBEINTRAG_QUELLE

    eintrag = _mock_eintrag(hass, {})
    ablauf = await hass.config_entries.subentries.async_init(
        (eintrag.entry_id, SUBEINTRAG_QUELLE), context={"source": "user"}
    )

    await hass.config_entries.subentries.async_configure(
        ablauf["flow_id"],
        {
            "name": "Heizstab",
            "art": "heizstab",
            "bedingung_art": "schwelle",
            "quelle": "sensor.leistung",
        },
    )
    ergebnis = await hass.config_entries.subentries.async_configure(
        ablauf["flow_id"], {"ein": 500, "aus": 200}
    )

    assert ergebnis["data"]["bedingung"] == {
        "art": "schwelle",
        "quelle": "sensor.leistung",
        "ein": 500.0,
        "aus": 200.0,
    }


async def test_das_geraet_einer_quelle_haengt_nur_am_subeintrag(hass):
    """Zwei Zuordnungen zeigen dasselbe Gerät zweimal in der Übersicht."""
    from homeassistant.helpers import device_registry as dr

    from custom_components.heatnexus import async_migrate_entry, waermequelle
    from custom_components.heatnexus.const import CONF_QUELLEN, DOMAIN, SUBEINTRAG_QUELLE

    eintrag = _mock_eintrag(hass, {"192.0.2.10": {CONF_QUELLEN: [SOLAR]}})
    await async_migrate_entry(hass, eintrag)
    sub = next(s for s in eintrag.subentries.values() if s.subentry_type == SUBEINTRAG_QUELLE)

    registrierung = dr.async_get(hass)
    geraet = registrierung.async_get_or_create(
        config_entry_id=eintrag.entry_id,
        identifiers={(DOMAIN, "SN1-waermequelle-q1")},
        name="Anlage 1 · Solaranlage",
    )
    registrierung.async_update_device(
        geraet.id,
        add_config_entry_id=eintrag.entry_id,
        add_config_subentry_id=sub.subentry_id,
    )

    assert waermequelle.geraete_entflechten(registrierung, eintrag) == 1

    zuordnung = registrierung.async_get(geraet.id).config_entries_subentries[eintrag.entry_id]
    assert zuordnung == {sub.subentry_id}


async def test_ein_geraet_der_anlage_bleibt_am_haupteintrag(hass):
    """Nur Geräte einer Quelle werden gelöst, nicht die der Anlage."""
    from homeassistant.helpers import device_registry as dr

    from custom_components.heatnexus import async_migrate_entry, waermequelle
    from custom_components.heatnexus.const import CONF_QUELLEN, DOMAIN

    eintrag = _mock_eintrag(hass, {"192.0.2.10": {CONF_QUELLEN: [SOLAR]}})
    await async_migrate_entry(hass, eintrag)

    registrierung = dr.async_get(hass)
    geraet = registrierung.async_get_or_create(
        config_entry_id=eintrag.entry_id,
        identifiers={(DOMAIN, "SN1-0")},
        name="Anlage 1 · PuroWIN",
    )

    assert waermequelle.geraete_entflechten(registrierung, eintrag) == 0
    assert registrierung.async_get(geraet.id) is not None


async def test_das_geraet_einer_entfernten_quelle_verschwindet(hass):
    """Ohne Subeintrag bliebe ein Gerät ohne Entitäten in der Übersicht."""
    from homeassistant.helpers import device_registry as dr

    from custom_components.heatnexus import waermequelle
    from custom_components.heatnexus.const import DOMAIN

    eintrag = _mock_eintrag(hass, {"192.0.2.10": {}})

    registrierung = dr.async_get(hass)
    geraet = registrierung.async_get_or_create(
        config_entry_id=eintrag.entry_id,
        identifiers={(DOMAIN, "SN1-waermequelle-q1")},
        name="Anlage 1 · Solaranlage",
    )

    assert waermequelle.geraete_entflechten(registrierung, eintrag) == 1
    assert registrierung.async_get(geraet.id) is None


async def test_ohne_wechsel_schreibt_die_quelle_keinen_zustand(hass, monkeypatch):
    """Ein Melder im Sekundentakt gehört nicht in den Verlauf."""
    hass.states.async_set("sensor.kollektor", "70")
    hass.states.async_set("sensor.puffer", "50")
    entitaet = _sensor(hass)
    entitaet._laeuft = True
    geschrieben = []
    monkeypatch.setattr(entitaet, "async_write_ha_state", lambda: geschrieben.append(True))

    entitaet._quelle_geaendert(None)

    assert geschrieben == []


async def test_ein_echter_wechsel_schreibt_den_zustand(hass, monkeypatch):
    hass.states.async_set("sensor.kollektor", "70")
    hass.states.async_set("sensor.puffer", "50")
    entitaet = _sensor(hass)
    geschrieben = []
    monkeypatch.setattr(entitaet, "async_write_ha_state", lambda: geschrieben.append(True))

    entitaet._quelle_geaendert(None)

    assert geschrieben == [True]
    assert entitaet.is_on is True


async def test_die_quelle_haengt_an_ereignissen_statt_am_takt(hass):
    """Abgefragt gäbe es nichts zu holen; der Takt schriebe nur fort."""
    assert _sensor(hass).should_poll is False


KLARTEXT = {
    "id": "q1",
    "name": "Solaranlage",
    "art": "solar",
    "pumpe": True,
    "bedingung": {
        "art": "zustand",
        "quelle": "sensor.solarstatus",
        "zustaende": ["Solaranlage aktiv"],
    },
}


def _vorbelegung(schema, feld):
    """Was das Formular in einem Feld anbietet - Vorschlag oder Vorgabe."""
    import voluptuous as vol

    for marker in schema.schema:
        if marker != feld:
            continue
        vorschlag = (marker.description or {}).get("suggested_value")
        if vorschlag is not None:
            return vorschlag
        if marker.default is vol.UNDEFINED:
            return None
        return marker.default()
    raise AssertionError(f"Das Formular kennt kein Feld {feld}.")


async def _aenderung_beginnen(hass, quelle):
    """Eine vorhandene Quelle anlegen und ihren Änderungsablauf starten."""
    from custom_components.heatnexus import async_migrate_entry
    from custom_components.heatnexus.const import CONF_QUELLEN, SUBEINTRAG_QUELLE

    eintrag = _mock_eintrag(hass, {"192.0.2.10": {CONF_QUELLEN: [quelle]}})
    await async_migrate_entry(hass, eintrag)
    sub = next(s for s in eintrag.subentries.values() if s.subentry_type == SUBEINTRAG_QUELLE)
    ablauf = await hass.config_entries.subentries.async_init(
        (eintrag.entry_id, SUBEINTRAG_QUELLE),
        context={"source": "reconfigure", "subentry_id": sub.subentry_id},
    )
    return eintrag, sub, ablauf


async def test_beim_aendern_steht_die_quelle_schon_im_formular(hass):
    """Der erste Schritt zeigt, was gespeichert ist, statt leerer Felder."""
    _, _, ablauf = await _aenderung_beginnen(hass, SOLAR)

    assert ablauf["step_id"] == "quelle"
    schema = ablauf["data_schema"]
    assert _vorbelegung(schema, "name") == "Solaranlage"
    assert _vorbelegung(schema, "art") == "solar"
    assert _vorbelegung(schema, "bedingung_art") == "differenz"
    assert _vorbelegung(schema, "quelle") == "sensor.kollektor"


async def test_beim_aendern_stehen_die_grenzen_im_zweiten_schritt(hass):
    """Der erste Schritt fragt die Grenzen nicht ab und darf sie nicht leeren."""
    _, _, ablauf = await _aenderung_beginnen(hass, SOLAR)

    regel = await hass.config_entries.subentries.async_configure(
        ablauf["flow_id"],
        {
            "name": "Solaranlage",
            "art": "solar",
            "pumpe": False,
            "bedingung_art": "differenz",
            "quelle": "sensor.kollektor",
        },
    )

    assert regel["step_id"] == "regel"
    assert _vorbelegung(regel["data_schema"], "gegen") == "sensor.puffer"
    assert _vorbelegung(regel["data_schema"], "ein") == 8
    assert _vorbelegung(regel["data_schema"], "aus") == 3


async def test_beim_aendern_stehen_die_zustaende_zur_wahl(hass):
    """Eine Klartext-Quelle behält ihre gewählten Zustände im zweiten Schritt."""
    hass.states.async_set("sensor.solarstatus", "Solaranlage inaktiv")
    _, _, ablauf = await _aenderung_beginnen(hass, KLARTEXT)

    assert _vorbelegung(ablauf["data_schema"], "pumpe") is True
    regel = await hass.config_entries.subentries.async_configure(
        ablauf["flow_id"],
        {
            "name": "Solaranlage",
            "art": "solar",
            "pumpe": True,
            "bedingung_art": "zustand",
            "quelle": "sensor.solarstatus",
        },
    )

    assert _vorbelegung(regel["data_schema"], "zustaende") == ["Solaranlage aktiv"]


async def test_beim_aendern_bleibt_die_kennung_der_quelle(hass):
    """Eine neue Kennung ließe Verlauf und Entitäts-ID der Quelle zurück."""
    from homeassistant.data_entry_flow import FlowResultType

    hass.states.async_set("sensor.solarstatus", "Solaranlage aktiv")
    eintrag, sub, ablauf = await _aenderung_beginnen(hass, KLARTEXT)

    await hass.config_entries.subentries.async_configure(
        ablauf["flow_id"],
        {
            "name": "Solar Dach",
            "art": "solar",
            "pumpe": False,
            "bedingung_art": "zustand",
            "quelle": "sensor.solarstatus",
        },
    )
    ergebnis = await hass.config_entries.subentries.async_configure(
        ablauf["flow_id"], {"zustaende": ["Solaranlage aktiv"]}
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.ABORT
    geaendert = eintrag.subentries[sub.subentry_id]
    assert geaendert.title == "Solar Dach"
    assert geaendert.data["id"] == "q1"
    assert geaendert.data["host"] == "192.0.2.10"
    assert geaendert.data["pumpe"] is False
    assert geaendert.data["bedingung"]["zustaende"] == ["Solaranlage aktiv"]


async def test_ein_ersatzzustand_steht_nicht_zur_wahl(hass):
    """Eine nicht erreichbare Entität bietet keinen Zustand an."""
    from custom_components.heatnexus.waermequelle_flow import zustandsvorschlaege

    hass.states.async_set("binary_sensor.solarpumpe", "unavailable")

    assert zustandsvorschlaege(hass, "binary_sensor.solarpumpe") == []


async def test_die_liste_nennt_die_zustaende_der_entitaet(hass):
    """Die gemeldeten Zustände stehen zur Wahl, der Ersatzzustand nicht."""
    from custom_components.heatnexus.waermequelle_flow import zustandsvorschlaege

    hass.states.async_set(
        "sensor.solarstatus",
        "unknown",
        {"options": ["Solaranlage aktiv", "Solaranlage inaktiv"]},
    )

    assert zustandsvorschlaege(hass, "sensor.solarstatus") == [
        "Solaranlage aktiv",
        "Solaranlage inaktiv",
    ]


async def test_ohne_erreichbare_entitaet_bleibt_die_wahl_freiwillig(hass):
    """Ohne Vorschlag gilt die Entität nicht als Klartext und wird nicht erzwungen."""
    import voluptuous as vol

    from custom_components.heatnexus.waermequelle_flow import regel_schema

    schema = regel_schema("zustand", {"bedingung": {"art": "zustand"}}, [])
    marker = next(m for m in schema.schema if m == "zustaende")

    assert isinstance(marker, vol.Optional)
