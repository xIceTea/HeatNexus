"""Marken aus Home Assistant als Karten der Oberfläche.

Den Wert schickt der Server nicht mit: Die Oberfläche bindet ihn im Browser an
`hass.states`. Geprüft wird deshalb, welche Adressen mit welchem Namen und
Symbol in welcher Karte landen — und welche nicht.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def marken():
    from custom_components.heatnexus.panel import marken as modul

    return modul


def _marke(hass, name: str) -> str:
    from homeassistant.helpers import label_registry as lr

    return lr.async_get(hass).async_create(name).label_id


def _entitaet(hass, kennung: str, objekt: str, name: str | None = None) -> str:
    """Eine fremde Entität mit dieser Marke anlegen."""
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    eintrag = registry.async_get_or_create("sensor", "demo", objekt, original_name=name)
    registry.async_update_entity(eintrag.entity_id, labels={kennung})
    return eintrag.entity_id


class OhneRecht:
    """Ein Benutzer, dem Home Assistant jede Adresse verwehrt."""

    class permissions:
        """Die Rechte, die Home Assistant an jedem Benutzer führt."""

        @staticmethod
        def check_entity(entity_id: str, schluessel: str) -> bool:
            return False


async def test_je_marke_eine_karte(hass, marken):
    """Die Überschrift ist der Name der Marke, die Kennung ihre Id."""
    kennung = _marke(hass, "Solarthermie")
    adresse = _entitaet(hass, kennung, "kollektor", "Kollektor")
    hass.states.async_set(adresse, "62", {"friendly_name": "Kollektor"})

    ergebnis = marken.karten(hass, [kennung])

    assert [k["id"] for k in ergebnis] == [f"marke:{kennung}"]
    assert ergebnis[0]["titel"] == "Solarthermie"
    assert ergebnis[0]["zeilen"][0]["entity"] == adresse
    assert ergebnis[0]["zeilen"][0]["titel"] == "Kollektor"


async def test_der_server_schickt_keinen_wert(hass, marken):
    """Den holt die Oberfläche selbst, sonst stünde er beim nächsten Takt still."""
    kennung = _marke(hass, "Zähler")
    adresse = _entitaet(hass, kennung, "zaehlerstand", "Zählerstand")
    hass.states.async_set(adresse, "1234")

    zeile = marken.karten(hass, [kennung])[0]["zeilen"][0]

    assert set(zeile) == {"entity", "titel", "symbol"}


async def test_unbekannte_marke_wird_uebergangen(hass, marken):
    """Eine gelöschte Marke steht noch in den Optionen."""
    assert marken.karten(hass, ["gibtesnicht"]) == []


async def test_ohne_freigabe_entsteht_keine_karte(hass, marken):
    """Ab Werk ist die Funktion aus und kostet nichts."""
    assert marken.karten(hass, []) == []


async def test_marke_ohne_entitaeten_entfaellt(hass, marken):
    """Eine leere Karte wäre nur eine Überschrift."""
    kennung = _marke(hass, "Leer")

    assert marken.karten(hass, [kennung]) == []


async def test_zeilen_stehen_nach_namen(hass, marken):
    """Sonst richtete sich die Reihenfolge nach der Adresse."""
    kennung = _marke(hass, "Garten")
    _entitaet(hass, kennung, "a_wert", "Zisterne")
    _entitaet(hass, kennung, "b_wert", "Bodenfeuchte")

    namen = [z["titel"] for z in marken.karten(hass, [kennung])[0]["zeilen"]]

    assert namen == ["Bodenfeuchte", "Zisterne"]


async def test_ohne_leserecht_faellt_die_zeile_weg(hass, marken):
    """Die Oberfläche darf keine Werte zeigen, die Home Assistant verbirgt."""
    kennung = _marke(hass, "Privat")
    adresse = _entitaet(hass, kennung, "verborgen", "Verborgen")
    hass.states.async_set(adresse, "1")

    assert marken.karten(hass, [kennung], OhneRecht()) == []


async def test_mehr_karten_als_erlaubt_werden_abgeschnitten(hass, marken):
    """Die Decke schützt den Abzug, nicht die Auswahl."""
    from custom_components.heatnexus.const import MARKEN_MAX_KARTEN

    kennungen = []
    for nummer in range(MARKEN_MAX_KARTEN + 3):
        kennung = _marke(hass, f"Marke {nummer}")
        _entitaet(hass, kennung, f"wert{nummer}", f"Wert {nummer}")
        kennungen.append(kennung)

    assert len(marken.karten(hass, kennungen)) == MARKEN_MAX_KARTEN


async def test_mehr_zeilen_als_erlaubt_werden_abgeschnitten(hass, marken):
    """Dieselbe Art Deckel wie bei Warmwasser und Verlauf."""
    from custom_components.heatnexus.const import MARKEN_MAX_ZEILEN

    kennung = _marke(hass, "Viele")
    for nummer in range(MARKEN_MAX_ZEILEN + 5):
        _entitaet(hass, kennung, f"viele{nummer}", f"Wert {nummer:03d}")

    assert len(marken.karten(hass, [kennung])[0]["zeilen"]) == MARKEN_MAX_ZEILEN


async def test_zugeordnete_labels_werden_zu_zeilen(hass, marken):
    """Ein zugeordnetes Label bekommt keine Karte, sondern Zeilen."""
    kennung = _marke(hass, "Strom")
    adresse = _entitaet(hass, kennung, "zaehler", "Stromzähler")
    hass.states.async_set(adresse, "7", {"friendly_name": "Stromzähler"})

    zeilen = marken.zeilen(hass, [kennung])

    assert [z["entity"] for z in zeilen] == [adresse]
    assert set(zeilen[0]) == {"entity", "titel", "symbol"}


async def test_dieselbe_adresse_erscheint_einmal(hass, marken):
    """Trägt eine Entität zwei zugeordnete Labels, bleibt es eine Zeile."""
    eins = _marke(hass, "Haus")
    zwei = _marke(hass, "Keller")
    adresse = _entitaet(hass, eins, "doppelt", "Doppelt")
    from homeassistant.helpers import entity_registry as er

    er.async_get(hass).async_update_entity(adresse, labels={eins, zwei})
    hass.states.async_set(adresse, "1")

    assert len(marken.zeilen(hass, [eins, zwei])) == 1


async def test_ohne_leserecht_bleibt_die_zeile_weg(hass, marken):
    """Dieselbe Schranke wie bei den Karten."""
    kennung = _marke(hass, "Geheim")
    adresse = _entitaet(hass, kennung, "geheim", "Geheim")
    hass.states.async_set(adresse, "1")

    assert marken.zeilen(hass, [kennung], OhneRecht()) == []


# ---------------------------------------------------------------------------
# Übernahme einer früher gemeinsamen Auswahl
# ---------------------------------------------------------------------------
def _eintrag(hass, optionen: dict):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    eintrag = MockConfigEntry(
        domain="heatnexus", version=2, title="Heizhaus", data={}, options=optionen
    )
    eintrag.add_to_hass(hass)
    return eintrag


async def test_die_gemeinsame_auswahl_wandert_in_die_anlage(hass, marken):
    """Ohne die Übernahme verlöre jede vorhandene Anlage ihre Labelkarten."""
    from custom_components.heatnexus import _marken_je_anlage_uebernehmen
    from custom_components.heatnexus.const import CONF_MARKEN

    eintrag = _eintrag(hass, {CONF_MARKEN: ["abc123"]})

    _marken_je_anlage_uebernehmen(hass, eintrag, [{"host": "192.0.2.10"}])

    assert eintrag.options["192.0.2.10"][CONF_MARKEN] == ["abc123"]
    assert CONF_MARKEN not in eintrag.options


async def test_eine_auswahl_bei_der_anlage_bleibt_stehen(hass, marken):
    """Was bei der Anlage steht, ist die jüngere Entscheidung."""
    from custom_components.heatnexus import _marken_je_anlage_uebernehmen
    from custom_components.heatnexus.const import CONF_MARKEN

    eintrag = _eintrag(hass, {CONF_MARKEN: ["abc123"], "192.0.2.10": {CONF_MARKEN: ["def456"]}})

    _marken_je_anlage_uebernehmen(hass, eintrag, [{"host": "192.0.2.10"}])

    assert eintrag.options["192.0.2.10"][CONF_MARKEN] == ["def456"]


async def test_ohne_gemeinsame_auswahl_bleibt_der_eintrag_unberührt(hass, marken):
    """Der Normalfall darf den Eintrag bei jeder Einrichtung nicht anfassen."""
    from custom_components.heatnexus import _marken_je_anlage_uebernehmen

    eintrag = _eintrag(hass, {"192.0.2.10": {}})

    _marken_je_anlage_uebernehmen(hass, eintrag, [{"host": "192.0.2.10"}])

    assert eintrag.options == {"192.0.2.10": {}}
