"""Die einmalige Umstellung auf dauerhafte Kennungen.

`migration.py` ist der gefährlichste Code des Projekts: Er schreibt die
Entity-Registry von Home Assistant um. Geht dabei etwas schief, verliert der
Nutzer eigene Namen, Bereichszuordnung, Verlauf und Automationen – und merkt
es erst Wochen später.

Bis heute stand die Datei bei 19 % Abdeckung. Geprüft wird deshalb vor allem,
was **nicht** passieren darf:

* nichts anlegen, nichts löschen – nur umbenennen,
* eine bereits umgestellte Anlage nicht ein zweites Mal anfassen,
* eine vom Nutzer selbst benannte Entität in Ruhe lassen,
* bei belegtem Zielnamen lieber nichts tun als einen Zähler anhängen.

Gearbeitet wird mit den echten Registries von Home Assistant, nicht mit
Attrappen: Eine nachgebaute Registry würde genau die Eigenschaften nicht
haben, um die es hier geht.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture
def migration():
    """Das Modul – es zieht Home Assistant nach."""
    from custom_components.heatnexus import migration as modul

    return modul


def _beschreibung(alt_geraet, neu_geraet, alt_id, neu_id) -> dict:
    return {
        "alt_device_id": alt_geraet,
        "device_id": neu_geraet,
        "alt_id": alt_id,
        "id": neu_id,
        "name": "Kesseltemperatur Ist",
        "device_name": "PuroWIN",
    }


class FakeCoordinator:
    """Nur die Beschreibungen, mehr liest die Umstellung nicht."""

    def __init__(self, beschreibungen):
        """Beschreibungen bereitstellen."""
        self.data = {"devices": list(beschreibungen)}


# ---------------------------------------------------------------------------
# Beschreibungen einsammeln
# ---------------------------------------------------------------------------
def test_ohne_beschreibungen_passiert_nichts(migration, hass):
    """Solange die Anlage nicht gelesen ist, wird nichts umgestellt.

    Sonst liefe die Umstellung auf einem halb gefüllten Stand und ließe die
    Hälfte der Entitäten mit der alten Kennung zurück.
    """
    eintrag = _config_entry(hass)
    migration.async_kennungen_umstellen(hass, eintrag, {"a": FakeCoordinator([])})
    # Kein Absturz, keine Änderung – mehr ist hier nicht zu prüfen.


def test_beschreibungen_kommen_aus_allen_koordinatoren(migration):
    """Zwei Anlagen, zwei Koordinatoren – beide zählen."""
    a = FakeCoordinator([_beschreibung("alt1", "neu1", "e_alt1", "e_neu1")])
    b = FakeCoordinator([_beschreibung("alt2", "neu2", "e_alt2", "e_neu2")])
    alle = migration._beschreibungen({"a": a, "b": b})
    assert len(alle) == 2


def test_koordinator_ohne_daten_wird_uebergangen(migration):
    """`data` ist None, solange der erste Abruf läuft."""

    class Leer:
        data = None

    assert migration._beschreibungen({"a": Leer()}) == []


# ---------------------------------------------------------------------------
# Geräte
# ---------------------------------------------------------------------------
def _config_entry(hass):
    """Ein Konfigurationseintrag, wie Home Assistant ihn anlegt.

    Bewusst `MockConfigEntry` statt `ConfigEntry` von Hand: Dessen Signatur
    ändert sich mit fast jeder Home-Assistant-Fassung (zuletzt kam
    `subentries_data` dazu), und ein Test, der daran zerbricht, prüft nichts
    über HeatNexus.
    """
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.const import DOMAIN

    eintrag = MockConfigEntry(domain=DOMAIN, title="PuroWin40", data={}, options={})
    eintrag.add_to_hass(hass)
    return eintrag


def test_geraet_wird_umbenannt_nicht_neu_angelegt(migration, hass):
    """Die Kennung wechselt, das Gerät bleibt dasselbe.

    Daran hängt alles: Ein neu angelegtes Gerät hätte weder die Zuordnung zum
    Bereich noch die eigenen Namen des Nutzers.
    """
    from homeassistant.helpers import device_registry as dr

    from custom_components.heatnexus.const import DOMAIN

    eintrag = _config_entry(hass)
    registry = dr.async_get(hass)
    geraet = registry.async_get_or_create(
        config_entry_id=eintrag.entry_id,
        identifiers={(DOMAIN, "192-168-178-100-1-60-0")},
        name="PuroWIN",
    )
    vorher = geraet.id

    anzahl = migration._geraete_umstellen(
        hass, [_beschreibung("192-168-178-100-1-60-0", "SN1-3-0", "x", "y")]
    )

    assert anzahl == 1
    nachher = registry.async_get_device(identifiers={(DOMAIN, "SN1-3-0")})
    assert nachher is not None
    assert nachher.id == vorher, "Das Gerät wurde ersetzt statt umbenannt"
    assert registry.async_get_device(identifiers={(DOMAIN, "192-168-178-100-1-60-0")}) is None


def test_zweiter_lauf_stellt_nichts_mehr_um(migration, hass):
    """Die Umstellung läuft bei jedem Start – danach findet sie nichts mehr."""
    from homeassistant.helpers import device_registry as dr

    from custom_components.heatnexus.const import DOMAIN

    eintrag = _config_entry(hass)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=eintrag.entry_id,
        identifiers={(DOMAIN, "192-168-178-100-1-60-0")},
        name="PuroWIN",
    )
    beschreibungen = [_beschreibung("192-168-178-100-1-60-0", "SN1-3-0", "x", "y")]

    assert migration._geraete_umstellen(hass, beschreibungen) == 1
    assert migration._geraete_umstellen(hass, beschreibungen) == 0


def test_belegtes_ziel_bleibt_unangetastet(migration, hass):
    """Gibt es die neue Kennung schon, ist die Umstellung gelaufen.

    Beide zusammenzuführen wäre gefährlich – dabei ginge eines der beiden
    Geräte samt seiner Zuordnungen verloren.
    """
    from homeassistant.helpers import device_registry as dr

    from custom_components.heatnexus.const import DOMAIN

    eintrag = _config_entry(hass)
    registry = dr.async_get(hass)
    registry.async_get_or_create(
        config_entry_id=eintrag.entry_id,
        identifiers={(DOMAIN, "192-168-178-100-1-60-0")},
        name="alt",
    )
    registry.async_get_or_create(
        config_entry_id=eintrag.entry_id,
        identifiers={(DOMAIN, "SN1-3-0")},
        name="neu",
    )

    assert (
        migration._geraete_umstellen(
            hass, [_beschreibung("192-168-178-100-1-60-0", "SN1-3-0", "x", "y")]
        )
        == 0
    )
    assert registry.async_get_device(identifiers={(DOMAIN, "192-168-178-100-1-60-0")}) is not None


def test_gleiche_kennung_ist_kein_paar(migration, hass):
    """Alt und neu identisch heißt: nichts zu tun."""
    assert migration._geraete_umstellen(hass, [_beschreibung("SN1-3-0", "SN1-3-0", "x", "y")]) == 0


# ---------------------------------------------------------------------------
# Entitäten
# ---------------------------------------------------------------------------
def test_entitaet_behaelt_ihre_id_beim_kennungswechsel(migration, hass):
    """Die `unique_id` wechselt, die `entity_id` bleibt.

    Wechselte auch die `entity_id`, zeigten alle Automationen ins Leere.
    """
    from homeassistant.helpers import entity_registry as er

    from custom_components.heatnexus.const import DOMAIN

    eintrag = _config_entry(hass)
    registry = er.async_get(hass)
    entitaet = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "192-168-178-100-1-60-0-0-7-0",
        config_entry=eintrag,
        suggested_object_id="purowin_kesseltemperatur_ist",
    )
    vorher = entitaet.entity_id

    anzahl = migration._entitaeten_umstellen(
        hass,
        eintrag,
        [_beschreibung("a", "b", "192-168-178-100-1-60-0-0-7-0", "SN1-3-0-0-7-0")],
    )

    assert anzahl == 1
    nachher = registry.async_get(vorher)
    assert nachher is not None, "Die entity_id hat sich geändert"
    assert nachher.unique_id == "SN1-3-0-0-7-0"


def test_entitaet_mit_belegter_zielkennung_bleibt(migration, hass):
    """Zwei Entitäten dürfen nie dieselbe `unique_id` bekommen."""
    from homeassistant.helpers import entity_registry as er

    from custom_components.heatnexus.const import DOMAIN

    eintrag = _config_entry(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create("sensor", DOMAIN, "alt", config_entry=eintrag)
    registry.async_get_or_create("sensor", DOMAIN, "neu", config_entry=eintrag)

    assert (
        migration._entitaeten_umstellen(hass, eintrag, [_beschreibung("a", "b", "alt", "neu")]) == 0
    )


# ---------------------------------------------------------------------------
# Entitäts-IDs
# ---------------------------------------------------------------------------
def test_selbst_benannte_entitaet_wird_nicht_umbenannt(migration, hass):
    """Ein eigener Name ist eine Entscheidung, keine Altlast."""
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    from custom_components.heatnexus.const import DOMAIN

    eintrag = _config_entry(hass)
    geraet = dr.async_get(hass).async_get_or_create(
        config_entry_id=eintrag.entry_id,
        identifiers={(DOMAIN, "SN1-3-0")},
        name="Heizhaus · PuroWIN",
    )
    registry = er.async_get(hass)
    entitaet = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "SN1-3-0-0-7-0",
        config_entry=eintrag,
        device_id=geraet.id,
        original_name="Kesseltemperatur Ist",
        suggested_object_id="irgendwas_altes",
    )
    registry.async_update_entity(entitaet.entity_id, name="Mein Kessel")

    assert migration._entity_ids_umstellen(hass, eintrag) == 0
    assert registry.async_get(entitaet.entity_id) is not None


def test_entitaet_ohne_geraet_wird_uebergangen(migration, hass):
    """Ohne Gerät gibt es keinen Namen, aus dem sich eine ID bilden ließe."""
    from homeassistant.helpers import entity_registry as er

    from custom_components.heatnexus.const import DOMAIN

    eintrag = _config_entry(hass)
    er.async_get(hass).async_get_or_create("sensor", DOMAIN, "SN1-3-0-0-7-0", config_entry=eintrag)
    assert migration._entity_ids_umstellen(hass, eintrag) == 0


def test_die_angleichung_laeuft_auch_ohne_die_neuere_funktion(migration, hass, monkeypatch):
    """Ältere Fassungen kennen die eigene Kennung nicht als Ausnahme."""
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    from custom_components.heatnexus.const import DOMAIN

    eintrag = _config_entry(hass)
    geraet = dr.async_get(hass).async_get_or_create(
        config_entry_id=eintrag.entry_id,
        identifiers={(DOMAIN, "SN1-3-0")},
        name="Beispielhaus · Musterkessel",
    )
    registry = er.async_get(hass)
    entitaet = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "SN1-3-0-0-7-0",
        config_entry=eintrag,
        device_id=geraet.id,
        original_name="Kesseltemperatur Ist",
        suggested_object_id="irgendwas_altes",
    )

    monkeypatch.delattr(type(registry), "async_get_available_entity_id", raising=False)

    assert migration._entity_ids_umstellen(hass, eintrag) == 1
    assert registry.async_get("sensor.beispielhaus_musterkessel_kesseltemperatur_ist") is not None
    assert registry.async_get(entitaet.entity_id) is None


def test_die_laufzeit_behaelt_ihre_entity_id(migration, hass):
    """Sie steckt in fremden Automationen und darf nicht wandern."""
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    from custom_components.heatnexus.const import DOMAIN

    eintrag = _config_entry(hass)
    geraet = dr.async_get(hass).async_get_or_create(
        config_entry_id=eintrag.entry_id,
        identifiers={(DOMAIN, "SN1-3-0")},
        name="Beispielhaus · Musterkessel",
    )
    registry = er.async_get(hass)
    entitaet = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "SN1-3-0-2-1-0-laufzeit",
        config_entry=eintrag,
        device_id=geraet.id,
        original_name="Laufzeit Zyklus",
        suggested_object_id="beispielhaus_musterkessel_laufzeit",
    )

    assert migration._entity_ids_umstellen(hass, eintrag) == 0
    assert registry.async_get(entitaet.entity_id) is not None
