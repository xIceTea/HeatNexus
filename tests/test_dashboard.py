"""Aufbau des mitgelieferten Dashboards.

Geprüft werden die Bausteine, die die Reihenfolge und die Kartenwahl
bestimmen – ohne laufende Home-Assistant-Instanz.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def dashboard():
    from custom_components.heatnexus import dashboard as modul

    return modul


@pytest.fixture(scope="module")
def muster(dashboard):
    return dashboard.muster


@pytest.fixture(scope="module")
def anlagen(dashboard):
    return dashboard.anlagen


@pytest.fixture(scope="module")
def ansichten(dashboard):
    return dashboard.ansichten


def test_kurzname_entfernt_steuerungspraefix(anlagen):
    assert anlagen.kurzname("Kesselhaus · PuroWIN") == "PuroWIN"
    assert anlagen.kurzname("PuroWIN") == "PuroWIN"
    assert anlagen.kurzname(None) == ""


def test_kessel_steht_vor_puffer_und_heizkreis(anlagen):
    kessel = anlagen.rang(25)
    puffer = anlagen.rang(16)
    heizkreis = anlagen.rang(14)
    zirkulation = anlagen.rang(20)
    assert kessel < puffer < heizkreis < zirkulation


def test_unbekannter_funktionstyp_kommt_zuletzt(muster, anlagen):
    assert anlagen.rang(None) == muster.RANG_UNBEKANNT
    assert anlagen.rang("keine Zahl") == muster.RANG_UNBEKANNT
    assert anlagen.rang(999) == muster.RANG_UNBEKANNT
    assert anlagen.rang(25) < anlagen.rang(999)


def test_betriebsphase_steht_vor_beliebigem_wert(anlagen):
    assert anlagen.vorrang({"name": "Betriebsphase"}) < anlagen.vorrang({"name": "Nachstellzeit"})


def test_der_vorrang_gilt_auch_ohne_deutschen_namen(anlagen):
    """Sonst rutschte die Betriebsphase in einer fremden Sprache ans Ende."""
    fremd = {"name": "Operating phase", "schluessel": "operating_phase"}
    assert anlagen.vorrang(fremd) < anlagen.vorrang({"name": "Nachstellzeit"})


def test_thermostat_bekommt_eigene_karte(ansichten):
    eintrag = {"entity_id": "climate.heizkreis", "name": "Heizkreis", "bereich": "climate"}
    assert ansichten.kachel(eintrag)["type"] == "thermostat"


def test_kesseltemperatur_wird_rundinstrument(ansichten):
    eintrag = {
        "entity_id": "sensor.kesseltemperatur_ist",
        "name": "Kesseltemperatur Ist",
        "bereich": "sensor",
    }
    karte = ansichten.kachel(eintrag, rundinstrument=True)
    assert karte["type"] == "gauge"
    # Ohne ausdrückliche Anforderung bleibt es eine schlichte Kachel.
    assert ansichten.kachel(eintrag)["type"] == "tile"


def test_leerer_abschnitt_entfaellt(ansichten):
    assert ansichten.abschnitt("Messwerte", []) == []
    abschnitt = ansichten.abschnitt("Messwerte", [{"type": "tile"}])
    assert abschnitt[0]["cards"][0]["heading"] == "Messwerte"


def test_skala_rundet_auf_hunderter(anlagen):
    assert anlagen.skala(None) == 100
    assert anlagen.skala(0) == 100
    assert anlagen.skala(37) == 100
    assert anlagen.skala(101) == 200
    assert anlagen.skala(1180) == 1200


def test_gleichnamige_anlagenteile_werden_erkannt(anlagen):
    teile = [
        {"name": "Kesselhaus", "teile": [{"name": "B-PLMi PUFFER"}, {"name": "PuroWIN"}]},
        {"name": "Werkstatt", "teile": [{"name": "B-PLMi PUFFER"}]},
    ]
    assert anlagen.mehrfach_vergebene_namen(teile) == {"B-PLMi PUFFER"}


def test_anlage_steht_vor_dem_anlagenteil(anlagen):
    anlage = {"name": "Kesselhaus"}
    assert anlagen.voller_name(anlage, {"name": "PuroWIN"}) == "Kesselhaus · PuroWIN"
    assert anlagen.voller_name({"name": ""}, {"name": "PuroWIN"}) == "PuroWIN"


def test_symbol_je_anlagenteil(anlagen):
    assert anlagen.symbol(25) == "mdi:fire"
    assert anlagen.symbol(16) == "mdi:storage-tank"
    assert anlagen.symbol(None) == "mdi:heating-coil"


# ---------------------------------------------------------------------------
# Rückfragen vor Eingriffen
# ---------------------------------------------------------------------------
def test_rueckfrage_nur_bei_eingriffen(muster):
    assert muster.rueckfrage("Serviceausbrand")
    assert muster.rueckfrage("Reinigung bestätigt")
    assert muster.rueckfrage("Gewählter Brennstoff")
    # Harmlose Werte bleiben ohne Nachfrage – sonst klickt man sie blind weg.
    assert muster.rueckfrage("WW Einmalladung") == ""
    assert muster.rueckfrage("Kesseltemperatur Ist") == ""


def test_gefaehrliche_taste_bekommt_bestaetigung(ansichten):
    eintrag = {
        "entity_id": "button.serviceausbrand",
        "name": "Serviceausbrand",
        "bereich": "button",
    }
    karte = ansichten.kachel(eintrag)
    aktion = karte["icon_tap_action"]
    assert aktion["perform_action"] == "button.press"
    assert aktion["confirmation"]["text"]
    # Das Tippen auf die Kachel selbst bleibt die Detailansicht.
    assert "tap_action" not in karte


def test_schalter_wird_umgeschaltet_statt_ausgeloest(ansichten):
    eintrag = {"entity_id": "switch.estrich", "name": "Estrichprogramm", "bereich": "switch"}
    assert ansichten.kachel(eintrag)["icon_tap_action"]["action"] == "toggle"


def test_harmlose_kachel_bleibt_unveraendert(ansichten):
    eintrag = {
        "entity_id": "sensor.kesseltemperatur_ist",
        "name": "Kesseltemperatur Ist",
        "bereich": "sensor",
    }
    assert "icon_tap_action" not in ansichten.kachel(eintrag)


def test_ohne_schaltbare_plattform_keine_bestaetigung(ansichten):
    """Ein Anzeigewert mit brenzligem Namen bekommt keine Schaltaktion."""
    eintrag = {
        "entity_id": "sensor.serviceausbrand_zaehler",
        "name": "Serviceausbrand Zähler",
        "bereich": "sensor",
    }
    assert "icon_tap_action" not in ansichten.kachel(eintrag)


# ---------------------------------------------------------------------------
# Export: das erzeugte Dashboard zum Selberbauen
# ---------------------------------------------------------------------------
def test_der_export_ist_gueltiges_yaml():
    """Der Text muss sich unverändert wieder einlesen lassen."""
    import yaml

    from custom_components.heatnexus.dashboard import als_yaml

    konfiguration = {
        "title": "Heizung",
        "views": [
            {"title": "Übersicht", "path": "uebersicht", "cards": [{"type": "tile"}]},
        ],
    }
    text = als_yaml(konfiguration)
    assert yaml.safe_load(text) == konfiguration


def test_der_export_behaelt_die_reihenfolge():
    """Alphabetisch sortiert stünde `views` vor `title` – schlecht zu lesen."""
    from custom_components.heatnexus.dashboard import als_yaml

    text = als_yaml({"title": "Heizung", "views": []})
    assert text.index("title:") < text.index("views:")


def test_der_export_schreibt_umlaute_aus():
    """Entwichene Zeichen wären im Rohkonfigurations-Editor unlesbar."""
    from custom_components.heatnexus.dashboard import als_yaml

    assert "Übersicht" in als_yaml({"title": "Übersicht"})


def _anlage_mit_teilen():
    return {
        "id": "anlage-1",
        "name": "Kesselhaus",
        "kesselart": "hackgut",
        "teile": [
            {
                "name": "PuroWIN",
                "id": "teil-1",
                "fct_type": 25,
                "entitaeten": [
                    {
                        "entity_id": "sensor.purowin_betriebsphase",
                        "name": "Betriebsphase",
                        "bereich": "sensor",
                        "hat_wert": True,
                    },
                    {
                        "entity_id": "sensor.purowin_kesseltemperatur_ist",
                        "name": "Kesseltemperatur Ist",
                        "bereich": "sensor",
                        "hat_wert": True,
                    },
                ],
            }
        ],
    }


def test_der_text_zum_kopieren_setzt_die_eigene_karte(ansichten):
    """Nur als Karte lässt sich das Schaubild im Editor bearbeiten."""
    ansicht = ansichten.anlagenbild([_anlage_mit_teilen()], als_karte=True)
    karten = [k for abschnitt in ansicht["sections"] for k in abschnitt["cards"]]
    schaubild = [k for k in karten if k.get("type", "").startswith("custom:")]
    assert len(schaubild) == 1
    assert schaubild[0]["anlage"] == "anlage-1"
    assert schaubild[0]["liste"] == "rechts"
    assert "sensor.purowin_betriebsphase" in schaubild[0]["zusatzwerte"]


def test_das_mitgelieferte_dashboard_bleibt_bei_der_zeichnung(ansichten):
    """Es darf kein Modul im Browser voraussetzen."""
    ansicht = ansichten.anlagenbild([_anlage_mit_teilen()])
    karten = [k for abschnitt in ansicht["sections"] for k in abschnitt["cards"]]
    assert not [k for k in karten if str(k.get("type", "")).startswith("custom:")]
    assert [k for k in karten if k.get("type") == "picture-elements"]


def test_das_schaubild_bekommt_zwei_spalten(ansichten):
    """Neben dem Bild steht die Werteliste – in einer Spalte wird beides eng."""
    ansicht = ansichten.anlagenbild([_anlage_mit_teilen()], als_karte=True)
    assert ansicht["sections"][0]["column_span"] == 2


async def test_das_geraet_einer_quelle_traegt_ihre_bauart(hass, anlagen):
    """Ohne die Bauart zeichnete das Schaubild die Quelle wie einen Anlagenteil."""
    from types import SimpleNamespace

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus import async_migrate_entry
    from custom_components.heatnexus.const import CONF_QUELLEN, CONF_SYSTEMS, DOMAIN

    quelle = {
        "id": "q1",
        "name": "Solaranlage",
        "art": "solar",
        "pumpe": True,
        "bedingung": {"art": "zustand", "quelle": "binary_sensor.solar"},
    }
    eintrag = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=1,
        data={CONF_SYSTEMS: [{"host": "192.0.2.10", "label": "Anlage 1"}]},
        options={"192.0.2.10": {CONF_QUELLEN: [quelle]}},
    )
    eintrag.add_to_hass(hass)
    await async_migrate_entry(hass, eintrag)
    eintrag.runtime_data = {
        "coordinators": {
            "192.0.2.10": SimpleNamespace(
                host="192.0.2.10",
                label="Anlage 1",
                client=SimpleNamespace(steuerung_kennung=lambda: "SN1"),
            )
        }
    }

    zuordnung = anlagen.quellen_nach_geraet(hass)

    assert zuordnung["SN1-waermequelle-q1"] == {"art": "solar", "pumpe": True}


@pytest.mark.parametrize("kennungen", [{("fremd", "a", "b")}, {("fremd",)}, {"fremd", "abc"}])
async def test_fremde_geraetekennung_ohne_paarform_stoert_nicht(hass, anlagen, kennungen):
    """Home Assistant prüft die Form fremder Gerätekennungen nicht nach."""
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.const import DOMAIN

    geraete = dr.async_get(hass)
    fremd = MockConfigEntry(domain="fremd")
    fremd.add_to_hass(hass)
    geraete.async_get_or_create(config_entry_id=fremd.entry_id, identifiers=kennungen)
    eigen = MockConfigEntry(domain=DOMAIN)
    eigen.add_to_hass(hass)
    kessel = geraete.async_get_or_create(
        config_entry_id=eigen.entry_id, identifiers={(DOMAIN, "SN1-0")}, name="Kessel"
    )
    er.async_get(hass).async_get_or_create(
        "sensor", DOMAIN, "SN1-0-0-1-0", config_entry=eigen, device_id=kessel.id
    )

    [anlage] = anlagen.anlagen_lesen(hass)
    assert [teil["name"] for teil in anlage["teile"]] == ["Kessel"]
