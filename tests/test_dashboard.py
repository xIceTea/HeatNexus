"""Aufbau des mitgelieferten Dashboards.

Geprüft werden die Bausteine, die die Reihenfolge und die Kartenwahl
bestimmen – ohne laufende Home-Assistant-Instanz.
"""

from __future__ import annotations

import re

import pytest

from .conftest import auf_englisch, requires_ha, zurueck_auf_deutsch

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
def details(dashboard):
    from custom_components.heatnexus.dashboard import details as modul

    return modul


@pytest.fixture(scope="module")
def auswahl(dashboard):
    from custom_components.heatnexus.dashboard import auswahl as modul

    return modul


@pytest.fixture(scope="module")
def karten(dashboard):
    from custom_components.heatnexus.dashboard import karten as modul

    return modul


@pytest.fixture(scope="module")
def anlagenseite(dashboard):
    from custom_components.heatnexus.dashboard import anlage as modul

    return modul


@pytest.fixture(scope="module")
def uebersichtsseite(dashboard):
    from custom_components.heatnexus.dashboard import uebersicht as modul

    return modul


@pytest.fixture(scope="module")
def badges(dashboard):
    from custom_components.heatnexus.dashboard import badges as modul

    return modul


@pytest.fixture(scope="module")
def wartungsseite(dashboard):
    from custom_components.heatnexus.dashboard import wartung as modul

    return modul


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


def test_thermostat_bekommt_eigene_karte(karten):
    eintrag = {"entity_id": "climate.heizkreis", "name": "Heizkreis", "bereich": "climate"}
    assert karten.kachel(eintrag)["type"] == "thermostat"


def test_leerer_abschnitt_entfaellt(karten):
    assert karten.abschnitt("Messwerte", []) == []
    abschnitt = karten.abschnitt("Messwerte", [{"type": "tile"}])
    assert abschnitt[0]["cards"][0]["heading"] == "Messwerte"


def test_skala_rundet_auf_hunderter(anlagen):
    assert anlagen.skala(None) == 100
    assert anlagen.skala(0) == 100
    assert anlagen.skala(37) == 100
    assert anlagen.skala(101) == 200
    assert anlagen.skala(1180) == 1200


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


def test_gefaehrliche_taste_bekommt_bestaetigung(karten):
    eintrag = {
        "entity_id": "button.serviceausbrand",
        "name": "Serviceausbrand",
        "bereich": "button",
    }
    karte = karten.kachel(eintrag)
    aktion = karte["icon_tap_action"]
    assert aktion["perform_action"] == "button.press"
    assert aktion["confirmation"]["text"]
    # Das Tippen auf die Kachel selbst bleibt die Detailansicht.
    assert "tap_action" not in karte


def test_schalter_wird_umgeschaltet_statt_ausgeloest(karten):
    eintrag = {"entity_id": "switch.estrich", "name": "Estrichprogramm", "bereich": "switch"}
    assert karten.kachel(eintrag)["icon_tap_action"]["action"] == "toggle"


def test_harmlose_kachel_bleibt_unveraendert(karten):
    eintrag = {
        "entity_id": "sensor.kesseltemperatur_ist",
        "name": "Kesseltemperatur Ist",
        "bereich": "sensor",
    }
    assert "icon_tap_action" not in karten.kachel(eintrag)


def test_ohne_schaltbare_plattform_keine_bestaetigung(karten):
    """Ein Anzeigewert mit brenzligem Namen bekommt keine Schaltaktion."""
    eintrag = {
        "entity_id": "sensor.serviceausbrand_zaehler",
        "name": "Serviceausbrand Zähler",
        "bereich": "sensor",
    }
    assert "icon_tap_action" not in karten.kachel(eintrag)


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
        "teile": [
            {
                "name": "PuroWIN",
                "id": "teil-1",
                "fct_type": 25,
                "symbol": "mdi:fire",
                "rang": 0,
                "entitaeten": [
                    {
                        "entity_id": "sensor.purowin_betriebsphase",
                        "name": "Betriebsphase",
                        "bereich": "sensor",
                        "hat_wert": True,
                        "kategorie": None,
                        "state_class": None,
                        "abgeleitet": False,
                    },
                    {
                        "entity_id": "sensor.purowin_kesseltemperatur_ist",
                        "name": "Kesseltemperatur Ist",
                        "bereich": "sensor",
                        "hat_wert": True,
                        "kategorie": None,
                        "state_class": None,
                        "abgeleitet": False,
                    },
                ],
            }
        ],
    }


def test_der_text_zum_kopieren_setzt_die_eigene_karte(anlagenseite):
    """Nur als Karte lässt sich das Schaubild im Editor bearbeiten."""
    ansicht = anlagenseite.arbeitsseite(_anlage_mit_teilen(), als_karte=True, mit_schaubild=True)
    karten = [k for abschnitt in ansicht["sections"] for k in abschnitt["cards"]]
    schaubild = [k for k in karten if k.get("type", "").startswith("custom:")]
    assert len(schaubild) == 1
    assert schaubild[0]["anlage"] == "anlage-1"
    assert schaubild[0]["liste"] == "rechts"
    assert "sensor.purowin_betriebsphase" in schaubild[0]["zusatzwerte"]


@pytest.mark.parametrize(("sprache", "erwartet"), [("en", "State"), ("nl", "Toestand")])
def test_die_ueberschrift_der_schaubildkarte_wird_uebersetzt(anlagenseite, sprache, erwartet):
    from custom_components.heatnexus.texte import LOVELACE_FELDER, Woerterbuch, uebersetze_baum

    ansicht = anlagenseite.arbeitsseite(_anlage_mit_teilen(), als_karte=True, mit_schaubild=True)
    fertig = uebersetze_baum(ansicht, Woerterbuch(sprache), LOVELACE_FELDER)
    karten = [k for a in fertig["sections"] for k in a["cards"]]
    [schaubild] = [k for k in karten if k.get("type", "").startswith("custom:")]
    assert schaubild["titel_liste"] == erwartet


def test_ohne_kartenmodul_bleibt_die_zeichnung(anlagenseite):
    """Der Rückfall setzt kein Modul im Browser voraus."""
    ansicht = anlagenseite.arbeitsseite(_anlage_mit_teilen(), als_karte=False, mit_schaubild=True)
    karten = [k for abschnitt in ansicht["sections"] for k in abschnitt["cards"]]
    assert not [k for k in karten if str(k.get("type", "")).startswith("custom:")]
    assert [k for k in karten if k.get("type") == "picture-elements"]


def _kartentypen(konfiguration: dict) -> list[str]:
    return [
        str(karte.get("type", ""))
        for ansicht in konfiguration["views"]
        for abschnitt in ansicht.get("sections", [])
        for karte in abschnitt.get("cards", [])
    ]


async def test_das_dashboard_nimmt_die_karte_sobald_das_modul_angemeldet_ist(
    dashboard, hass, monkeypatch
):
    """Sonst bliebe das mitgelieferte Dashboard ohne Animation und ohne Editor."""
    monkeypatch.setattr(dashboard, "anlagen_lesen", lambda _hass: [_anlage_mit_teilen()])
    hass.data["heatnexus_karte_js"] = True

    typen = _kartentypen(dashboard.dashboard_konfiguration(hass))

    assert "custom:heatnexus-schaubild" in typen
    assert "picture-elements" not in typen


async def test_ohne_angemeldetes_modul_baut_das_dashboard_die_zeichnung(
    dashboard, hass, monkeypatch
):
    """Schlägt die Anmeldung fehl, zeigt die Ansicht ein Bild statt eines Fehlers."""
    monkeypatch.setattr(dashboard, "anlagen_lesen", lambda _hass: [_anlage_mit_teilen()])
    hass.data.pop("heatnexus_karte_js", None)

    typen = _kartentypen(dashboard.dashboard_konfiguration(hass))

    assert "picture-elements" in typen
    assert "custom:heatnexus-schaubild" not in typen


def test_das_schaubild_bekommt_zwei_spalten(anlagenseite):
    """Neben dem Bild steht die Werteliste – in einer Spalte wird beides eng."""
    ansicht = anlagenseite.arbeitsseite(_anlage_mit_teilen(), als_karte=True, mit_schaubild=True)
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


async def test_das_geraet_einer_quelle_steht_in_der_anlage(hass, anlagen):
    """Die Quelle hängt nur an ihrem Subeintrag und zählt als eigenes Gerät."""
    from types import SimpleNamespace

    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er
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
                data={},
                client=SimpleNamespace(steuerung_kennung=lambda: "SN1"),
            )
        }
    }
    [sub] = eintrag.subentries.values()
    geraet = dr.async_get(hass).async_get_or_create(
        config_entry_id=eintrag.entry_id,
        config_subentry_id=sub.subentry_id,
        identifiers={(DOMAIN, "SN1-waermequelle-q1")},
        name="Anlage 1 · Solaranlage",
    )
    er.async_get(hass).async_get_or_create(
        "binary_sensor",
        DOMAIN,
        "SN1-waermequelle-q1",
        config_entry=eintrag,
        config_subentry_id=sub.subentry_id,
        device_id=geraet.id,
    )

    [anlage] = anlagen.anlagen_lesen(hass)
    [teil] = anlage["teile"]
    assert (teil["name"], teil["art"], teil["quellenpumpe"]) == ("Solaranlage", "solar", True)


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


async def test_die_bezeichnung_eines_programms_kommt_mit(hass, anlagen):
    """Der Name bleibt der des Geräts; die Bezeichnung steht daneben."""
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.const import DOMAIN

    eigen = MockConfigEntry(domain=DOMAIN)
    eigen.add_to_hass(hass)
    kreis = dr.async_get(hass).async_get_or_create(
        config_entry_id=eigen.entry_id, identifiers={(DOMAIN, "SN1-0")}, name="Heizkreis"
    )
    register = er.async_get(hass)
    programm = register.async_get_or_create(
        "sensor",
        DOMAIN,
        "SN1-0-3-62-0",
        config_entry=eigen,
        device_id=kreis.id,
        original_name="Heizprogramm 2",
    )
    register.async_update_entity_options(
        programm.entity_id, DOMAIN, {"bezeichnung": "Übergangszeit"}
    )

    [anlage] = anlagen.anlagen_lesen(hass)
    [eintrag] = anlage["teile"][0]["entitaeten"]
    assert eintrag["name"] == "Heizprogramm 2"
    assert eintrag["bezeichnung"] == "Übergangszeit"


def test_meldungen_zeigen_text_und_abhilfe(uebersichtsseite):
    """Die Abhilfe steht nur im Attribut; die Kachel zeigte sie nicht."""
    seite = uebersichtsseite.uebersicht([_anlage(_kessel())], als_karte=False, badges=[])
    karten = [
        karte
        for abschnitt in seite["sections"]
        for karte in abschnitt["cards"]
        if karte.get("type") == "markdown"
    ]
    assert len(karten) == 1
    inhalt = karten[0]["content"]
    assert "state_attr('sensor.klartext', 'meldungen')" in inhalt
    assert "e.text" in inhalt and "e.info" in inhalt
    # Zwei Anlagen melden dieselben Teile; der Titel sagt, welches.
    assert karten[0]["title"] == "Kesselhaus · PuroWIN"


async def test_die_automatik_ist_keine_anlage(hass, anlagen):
    """System- und Kreisgerät der Automatik erscheinen weder als Anlage noch als Teil."""
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.const import DOMAIN
    from custom_components.heatnexus.registrierung import uebergeordnet

    eintrag = MockConfigEntry(domain=DOMAIN, data={})
    eintrag.add_to_hass(hass)
    geraete, register = dr.async_get(hass), er.async_get(hass)
    system = geraete.async_get_or_create(
        config_entry_id=eintrag.entry_id,
        identifiers={(DOMAIN, f"{eintrag.entry_id}-automatik")},
        name="HeatNexus Automatik",
    )
    kreis = geraete.async_get_or_create(
        config_entry_id=eintrag.entry_id,
        identifiers={(DOMAIN, "SN1-2-0-automatik")},
        name="Automatik Heizkreis",
        **uebergeordnet(hass, f"{eintrag.entry_id}-automatik", eintrag.entry_id),
    )
    for geraet, kennung in (
        (system, "e1-automatik-system-status"),
        (kreis, "SN1-2-0-automatik-zustand"),
    ):
        register.async_get_or_create(
            "sensor", DOMAIN, kennung, config_entry=eintrag, device_id=geraet.id
        )

    assert anlagen.anlagen_lesen(hass) == []


async def test_der_deutsche_name_kommt_aus_dem_deskriptor(hass, anlagen):
    """Gesucht wird am Datenpunkt, nicht an einem selbst vergebenen Namen."""
    from types import SimpleNamespace

    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.const import DOMAIN

    eigen = MockConfigEntry(domain=DOMAIN)
    eigen.add_to_hass(hass)
    eigen.runtime_data = {
        "coordinators": {
            "192.0.2.10": SimpleNamespace(
                data={
                    "devices": [
                        {
                            "id": "SN1-0-0-7-0",
                            "name": "Boiler temp. current value",
                            "name_de": "Kesseltemperatur Ist",
                        }
                    ]
                }
            )
        }
    }
    kessel = dr.async_get(hass).async_get_or_create(
        config_entry_id=eigen.entry_id, identifiers={(DOMAIN, "SN1-0")}, name="Kessel"
    )
    register = er.async_get(hass)
    for kennung, name in (
        ("SN1-0-0-7-0", "Boiler temp. current value"),
        ("SN1-0-3-62-0", "Heizprogramm 2"),
    ):
        eintrag = register.async_get_or_create(
            "sensor", DOMAIN, kennung, config_entry=eigen, device_id=kessel.id, original_name=name
        )
        register.async_update_entity(eintrag.entity_id, name=f"Eigener Name {kennung}")

    [anlage] = anlagen.anlagen_lesen(hass)
    muster = {e["name"]: e["name_de"] for e in anlage["teile"][0]["entitaeten"]}
    assert muster == {
        "Eigener Name SN1-0-0-7-0": "Kesseltemperatur Ist",
        "Eigener Name SN1-0-3-62-0": "Heizprogramm 2",
    }


def _dashboard_anlage():
    def eintrag(entity_id: str, name: str, **rest):
        return {
            "entity_id": entity_id,
            "name": name,
            "bereich": entity_id.split(".")[0],
            "hat_wert": True,
            "kategorie": None,
            "state_class": None,
            "abgeleitet": False,
            "schluessel": None,
            "meldungsart": None,
            "wert": 70.0,
            **rest,
        }

    anlage = _anlage_mit_teilen()
    anlage["teile"][0]["entitaeten"] = [
        # Alphabetisch: Die Ersatznamen sortieren dann wie die deutschen.
        eintrag("sensor.betriebsphase", "Betriebsphase"),
        eintrag("sensor.brennerstarts", "Brennerstarts", state_class="total_increasing"),
        eintrag("sensor.kesseltemperatur_ist", "Kesseltemperatur Ist"),
        eintrag(
            "sensor.meldung_klartext",
            "Meldung Klartext",
            kategorie="diagnostic",
            meldungsart="fe01text",
        ),
        eintrag(
            "binary_sensor.stoerung",
            "Störung gemeldet",
            kategorie="diagnostic",
            meldungsart="fe01stoerung",
        ),
        eintrag("sensor.nachstellzeit", "Nachstellzeit"),
        eintrag("button.serviceausbrand", "Serviceausbrand"),
    ]
    return anlage


def _alle_ansichten(anlage, teil, uebersichtsseite, anlagenseite, wartungsseite, details):
    """Alle Ansichten einer Anlage; fehlende (`None`) entfallen."""
    ansichten = [
        uebersichtsseite.uebersicht([anlage], als_karte=False, badges=[]),
        anlagenseite.arbeitsseite(anlage, als_karte=False, mit_schaubild=True),
        wartungsseite.wartung([anlage]),
        wartungsseite.auswertung([anlage]),
        details.unteransicht(anlage, teil),
    ]
    return [a for a in ansichten if a]


def test_englische_namen_ergeben_dasselbe_dashboard(
    uebersichtsseite, anlagenseite, wartungsseite, details
):
    """Zeigerinstrument, Reihenfolge, Rückfrage und Meldungen folgen dem deutschen Namen."""
    deutsch = _dashboard_anlage()
    teile, namen = auf_englisch(deutsch["teile"])
    englisch = {**deutsch, "teile": teile}

    def ansichten_von(anlage):
        [teil] = anlage["teile"]
        return _alle_ansichten(anlage, teil, uebersichtsseite, anlagenseite, wartungsseite, details)

    assert zurueck_auf_deutsch(ansichten_von(englisch), namen) == ansichten_von(deutsch)
    kacheln = [k for a in ansichten_von(deutsch) for s in a["sections"] for k in s["cards"]]
    assert any(k.get("icon_tap_action") for k in kacheln)
    assert any(k.get("type") == "markdown" for k in kacheln)


# Merkmale deutscher Texte: Umlaute und häufige kurze Wörter.
DEUTSCH = re.compile(
    r"[äöüÄÖÜß]|\b(und|der|die|das|nicht|bis|von|mit|keine|seit|oder|für|zum|zur|Uhr|heute|"
    r"Wert|Zähler|Anlage|Heizung|Monat|dieser)\b"
)
SICHTBAR = frozenset(
    {
        "title",
        "name",
        "heading",
        "content",
        "confirmation_text",
        "text",
        "titel_bild",
        "titel_liste",
    }
)


def _sichtbare_texte(wert, schluessel=None) -> list[str]:
    if isinstance(wert, dict):
        return [t for k, v in wert.items() for t in _sichtbare_texte(v, k)]
    if isinstance(wert, list):
        return [t for v in wert for t in _sichtbare_texte(v, schluessel)]
    if isinstance(wert, str) and schluessel in SICHTBAR and "{%" not in wert:
        return [wert]
    return []


@pytest.mark.parametrize("sprache", ["en", "nl"])
def test_in_fremder_sprache_bleibt_im_dashboard_nichts_deutsch(
    sprache, uebersichtsseite, anlagenseite, wartungsseite, details, badges
):
    """Jede Überschrift, jeder Kartenname und jede Rückfrage erscheint übersetzt."""
    from custom_components.heatnexus.texte import LOVELACE_FELDER, Woerterbuch, uebersetze_baum

    anlage = _dashboard_anlage()
    anlage["teile"][0]["entitaeten"].append(
        {
            **anlage["teile"][0]["entitaeten"][0],
            "entity_id": "sensor.laufzeit_bis_reinigung",
            "name": "Laufzeit bis Reinigung",
        }
    )
    teile, _namen = auf_englisch(anlage["teile"])
    englisch = {**anlage, "teile": teile}
    [teil] = englisch["teile"]
    fertig = uebersetze_baum(
        _alle_ansichten(englisch, teil, uebersichtsseite, anlagenseite, wartungsseite, details),
        Woerterbuch(sprache),
        LOVELACE_FELDER,
    )
    eigene = {anlage["name"], teil["name"]}
    fremd = _anlage(
        {
            **_kessel(),
            "entitaeten": [
                _e("sensor.phase", "Operating phase", schluessel="operating_phase"),
                _e("sensor.vorrat", "Fuel storage", schluessel="fuel_storage_status"),
                _e("sensor.asche", "Ash", schluessel="maintenance_ash_hours"),
                _e("sensor.reinigung", "Cleaning", schluessel="maintenance_cleaning_hours"),
                _e("sensor.haupt", "Main", schluessel="maintenance_main_cleaning_hours"),
                _e("sensor.service", "Service", schluessel="maintenance_service_hours"),
            ],
        }
    )
    zweite = _anlage(
        {**fremd["teile"][0], "id": "zweiter0123456789"},
        name="Werkstatt",
        kennung="werkst0123456789",
    )
    kopf = [
        badges.badge("sensor.x", "Außen"),
        badges.badge("sensor.y", "Automatik"),
    ]
    woerter = Woerterbuch(sprache)
    liste = [*badges.anlagenbadges([fremd, zweite], uebersetze=woerter), *kopf]
    uebersetzt = uebersetze_baum({"badges": liste}, woerter, LOVELACE_FELDER)
    kurz = {b["name"].split(" · ")[-1] for b in uebersetzt["badges"]}
    feste = ("Kessel", "Vorrat", "Asche", "Reinigung", "Hauptreinigung", "Wartung")
    deutsch = sorted(kurz & {*feste, "Außen", "Automatik"})
    assert not deutsch, f"{sprache}: Badges ohne Übersetzung: {deutsch}"
    assert {woerter(n) for n in feste} <= kurz
    fertig = {"ansichten": fertig, "badges": uebersetzt}

    def ohne_eigene(text: str) -> str:
        for name in eigene:
            text = text.replace(name, "")
        return text

    reste = sorted({t for t in _sichtbare_texte(fertig) if DEUTSCH.search(ohne_eigene(t))})
    assert not reste, f"{sprache}: noch deutsch: {reste}"


def _e(entity_id: str, name: str, **rest) -> dict:
    return {
        "entity_id": entity_id,
        "name": name,
        "bereich": entity_id.split(".")[0],
        "hat_wert": True,
        "kategorie": None,
        "state_class": None,
        "abgeleitet": False,
        "schluessel": None,
        "meldungsart": None,
        "wert": 70.0,
        **rest,
    }


def _kessel() -> dict:
    return {
        "name": "PuroWIN",
        "id": "kessel0123456789",
        "fct_type": 25,
        "symbol": "mdi:fire",
        "rang": 10,
        "entitaeten": [
            _e("sensor.betriebsphase", "Betriebsphase", schluessel="operating_phase"),
            _e("sensor.kessel_ist", "Kesseltemperatur Ist", schluessel="boiler_temperature"),
            _e("sensor.leistung", "Kesselleistung", schluessel="boiler_power"),
            _e("sensor.abgas", "Abgastemperatur", schluessel="flue_gas_temperature"),
            _e("select.betriebswahl", "Betriebswahl", schluessel="mode_selection"),
            _e("button.serviceausbrand", "Serviceausbrand"),
            _e("number.kurve", "Heizkurve", kategorie="config"),
            _e("sensor.software", "Softwareversion", kategorie="diagnostic"),
            _e(
                "sensor.klartext",
                "Meldung Klartext",
                kategorie="diagnostic",
                meldungsart="fe01text",
            ),
            _e(
                "binary_sensor.stoerung",
                "Störung gemeldet",
                kategorie="diagnostic",
                meldungsart="fe01stoerung",
            ),
        ],
    }


def test_ansicht_traegt_titel_und_kein_symbol(karten):
    ansicht = karten.ansicht("Wartung", "wartung", [])
    assert ansicht["title"] == "Wartung"
    assert "icon" not in ansicht
    assert ansicht["type"] == "sections"


def test_unteransicht_fuehrt_zurueck(karten):
    ansicht = karten.ansicht("Kesselhaus · PuroWIN", "teil-abc", [], zurueck="anlage-xyz")
    assert ansicht["subview"] is True
    assert ansicht["back_path"] == "/heatnexus/anlage-xyz"


def test_ueberschrift_mit_ziel_navigiert(karten):
    karte = karten.ueberschrift("PuroWIN", ziel="teil-abc")
    assert karte["tap_action"] == {"action": "navigate", "navigation_path": "/heatnexus/teil-abc"}


def test_auswahl_trennt_messwert_bedienung_einstellung_diagnose(auswahl):
    teil = _kessel()
    assert [e["entity_id"] for e in auswahl.bedienung(teil)] == [
        "select.betriebswahl",
        "button.serviceausbrand",
    ]
    assert "sensor.abgas" in [e["entity_id"] for e in auswahl.messwerte(teil)]
    assert [e["entity_id"] for e in auswahl.einstellungen(teil)] == ["number.kurve"]
    assert "sensor.software" in [e["entity_id"] for e in auswahl.diagnose(teil)]


def test_kernwerte_kommen_aus_dem_modul(auswahl):
    assert [e["entity_id"] for e in auswahl.kernwerte(_kessel())] == [
        "sensor.betriebsphase",
        "sensor.kessel_ist",
    ]


def test_baureihe_ohne_eintrag_nimmt_die_ersten_messwerte(auswahl):
    teil = {**_kessel(), "fct_type": 999}
    assert len(auswahl.kernwerte(teil)) == 2
    assert auswahl.zeigerinstrumente(teil) == []


def test_moduleintrag_ohne_treffer_nimmt_die_ersten_messwerte(auswahl):
    teil = {
        **_kessel(),
        "entitaeten": [{**e, "schluessel": None} for e in _kessel()["entitaeten"]],
    }
    assert [e["entity_id"] for e in auswahl.kernwerte(teil)] == [
        e["entity_id"] for e in auswahl.messwerte(teil)[: auswahl.KERNWERTE_RUECKFALL]
    ]
    assert auswahl.kernwerte(teil)


def test_zeitprogramme_stehen_nicht_unter_einstellungen(auswahl):
    teil = {
        **_kessel(),
        "entitaeten": [
            *_kessel()["entitaeten"],
            _e("sensor.heizprogramm_1", "Programm 1", kategorie="config"),
        ],
    }
    assert "sensor.heizprogramm_1" not in [e["entity_id"] for e in auswahl.einstellungen(teil)]
    assert "sensor.heizprogramm_1" in [e["entity_id"] for e in auswahl.zeitprogramme(teil)]


def test_zeigerinstrumente_nach_modul(auswahl):
    paare = auswahl.zeigerinstrumente(_kessel())
    assert [e["entity_id"] for e, _ in paare] == ["sensor.kessel_ist", "sensor.leistung"]
    assert paare[0][1]["max"] == 95


def test_meldungskarte_erscheint_nur_bei_stoerung(karten, auswahl):
    teil = _kessel()
    karte = karten.meldungskarte(auswahl.klartext(teil), "PuroWIN", auswahl.stoerung(teil))
    assert karte["visibility"] == [
        {"condition": "state", "entity": "binary_sensor.stoerung", "state": "on"}
    ]
    assert "state_attr('sensor.klartext', 'meldungen')" in karte["content"]


def test_auswahl_und_zahl_bekommen_bedienfelder(karten):
    auswahlkachel = karten.kachel(_e("select.betriebswahl", "Betriebswahl"))
    zahl = karten.kachel(_e("number.korrektur", "Komfortkorrektur"))
    assert auswahlkachel["features"] == [{"type": "select-options"}]
    assert zahl["features"] == [{"type": "numeric-input", "style": "buttons"}]


def _anlage(*teile: dict, name: str = "Kesselhaus", kennung: str = "anlage0123456789") -> dict:
    return {"id": kennung, "name": name, "teile": list(teile)}


def test_unteransicht_gliedert_nach_zweck(details):
    ansicht = details.unteransicht(_anlage(_kessel()), _kessel())
    titel = [s["cards"][0]["heading"] for s in ansicht["sections"]]
    assert titel == ["Bedienung", "Messwerte", "Einstellungen", "Diagnose"]
    assert ansicht["title"] == "Kesselhaus · PuroWIN"
    assert ansicht["path"] == "teil-kessel01"
    assert ansicht["back_path"] == "/heatnexus/anlage-anlage01"


def test_teil_ohne_werte_hat_keine_unteransicht(details):
    leer = {**_kessel(), "entitaeten": []}
    assert details.unteransicht(_anlage(leer), leer) is None


def test_unteransicht_zeigt_zeitprogramme(details):
    """Zeitprogramme erscheinen in eigener Sektion zwischen Messwerte und Einstellungen."""
    teil_mit_zeitprogramm = {
        **_kessel(),
        "entitaeten": [
            *_kessel()["entitaeten"],
            _e("sensor.heizprogramm_1", "Programm 1", schluessel="heating_program_1"),
        ],
    }
    ansicht = details.unteransicht(_anlage(teil_mit_zeitprogramm), teil_mit_zeitprogramm)
    titel = [s["cards"][0]["heading"] for s in ansicht["sections"]]
    assert titel == ["Bedienung", "Messwerte", "Zeitprogramme", "Einstellungen", "Diagnose"]
    # Programm 1 erscheint unter Zeitprogramme (Index 2), nicht unter Messwerte (Index 1)
    zeitprogramme_section = ansicht["sections"][2]
    entity_ids = [c.get("entity") for c in zeitprogramme_section["cards"]]
    assert "sensor.heizprogramm_1" in entity_ids


def _karten(ansicht: dict) -> list[dict]:
    return [k for s in ansicht["sections"] for k in s["cards"]]


def test_arbeitsseite_zeigt_zeiger_zustand_bedienung(anlagenseite):
    seite = anlagenseite.arbeitsseite(_anlage(_kessel()), als_karte=False, mit_schaubild=False)
    karten = _karten(seite)
    kopf = karten[0]
    assert kopf["heading"] == "PuroWIN"
    assert kopf["tap_action"]["navigation_path"] == "/heatnexus/teil-kessel01"
    assert [k["entity"] for k in karten if k["type"] == "gauge"] == [
        "sensor.kessel_ist",
        "sensor.leistung",
    ]
    unter = [k["heading"] for k in karten if k.get("heading_style") == "subtitle"]
    assert unter == ["Zustand", "Bedienung"]
    # Was als Zeiger steht, steht nicht noch einmal als Kachel.
    kacheln = [k["entity"] for k in karten if k["type"] == "tile"]
    assert "sensor.kessel_ist" not in kacheln and "sensor.abgas" in kacheln
    assert "icon" not in seite and seite["path"] == "anlage-anlage01"


def test_arbeitsseite_mit_schaubild_bei_einer_anlage(anlagenseite):
    seite = anlagenseite.arbeitsseite(_anlage(_kessel()), als_karte=True, mit_schaubild=True)
    # Nach den Meldungen steht das Schaubild als erster Abschnitt.
    erste = seite["sections"][1]["cards"]
    assert any(str(k.get("type", "")).startswith("custom:") for k in erste)


def test_einzelanlage_zeigt_die_meldung_oben(anlagenseite):
    seite = anlagenseite.arbeitsseite(_anlage(_kessel()), als_karte=True, mit_schaubild=True)
    erste = seite["sections"][0]
    kopf, meldung = erste["cards"][0], erste["cards"][1]
    bedingung = [{"condition": "state", "entity": "binary_sensor.stoerung", "state": "on"}]
    assert kopf["heading"] == "Meldungen" and kopf["visibility"] == bedingung
    assert meldung["type"] == "markdown" and meldung["visibility"] == bedingung
    assert erste["column_span"] == 3


def test_arbeitsseite_neben_der_uebersicht_ohne_meldung(anlagenseite):
    seite = anlagenseite.arbeitsseite(_anlage(_kessel()), als_karte=True, mit_schaubild=False)
    assert not [k for k in _karten(seite) if k.get("type") == "markdown"]
    assert "badges" not in seite


async def test_einzelanlage_traegt_die_badges(dashboard, hass, monkeypatch):
    monkeypatch.setattr(dashboard, "anlagen_lesen", lambda _hass: [_anlage(_kessel())])
    seite = dashboard.dashboard_konfiguration(hass)["views"][0]
    stoerung = [b for b in seite["badges"] if b["entity"] == "binary_sensor.stoerung"]
    assert stoerung and stoerung[0]["visibility"][0]["state"] == "on"


def _automatikstatus(hass, eintrag, **rest):
    from homeassistant.helpers import entity_registry as er

    from custom_components.heatnexus.automatik.verwaltung import system_unique_id

    return er.async_get(hass).async_get_or_create(
        "sensor",
        "heatnexus",
        system_unique_id(eintrag.entry_id, "status"),
        config_entry=eintrag,
        **rest,
    )


async def test_kennwerte_nehmen_die_gewaehlte_aussentemperatur(badges, hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.const import CONF_AUSSENTEMPERATUR

    MockConfigEntry(domain="heatnexus", data={}).add_to_hass(hass)
    gewaehlt = MockConfigEntry(
        domain="heatnexus", data={}, options={CONF_AUSSENTEMPERATUR: "sensor.wetter"}
    )
    gewaehlt.add_to_hass(hass)
    status = _automatikstatus(hass, gewaehlt)
    liste = badges.allgemein(hass, [_anlage(_kessel())])
    assert [b["entity"] for b in liste] == ["sensor.wetter", status.entity_id]
    assert [b["name"] for b in liste] == ["Außen", "Automatik"]


async def test_kennwerte_ohne_abgeschaltete_automatik(badges, hass):
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    eintrag = MockConfigEntry(domain="heatnexus", data={})
    eintrag.add_to_hass(hass)
    _automatikstatus(hass, eintrag, disabled_by=er.RegistryEntryDisabler.USER)
    assert badges.allgemein(hass, [_anlage(_kessel())]) == []


async def test_zwei_anlagen_melden_nur_in_der_uebersicht(dashboard, hass, monkeypatch):
    zweite = _anlage(
        {**_kessel(), "id": "zweiter0123456789"}, name="Werkstatt", kennung="werkst0123456789"
    )
    monkeypatch.setattr(dashboard, "anlagen_lesen", lambda _hass: [_anlage(_kessel()), zweite])
    views = dashboard.dashboard_konfiguration(hass)["views"]
    for seite in (v for v in views if v["path"].startswith("anlage-")):
        assert not [k for k in _karten(seite) if k.get("type") == "markdown"]
        assert "badges" not in seite


def _abschnitt_mit(seite: dict, titel: str) -> list[dict]:
    return next(s["cards"] for s in seite["sections"] if s["cards"][0].get("heading") == titel)


def test_uebersicht_je_anlage_schaubild_kernwerte_navigation(uebersichtsseite):
    zweite = {**_kessel(), "id": "zweiter0123456789"}
    anlagen = [_anlage(_kessel()), _anlage(zweite, name="Werkstatt", kennung="werkst0123456789")]
    seite = uebersichtsseite.uebersicht(anlagen, als_karte=True, badges=[])
    koepfe = [s["cards"][0] for s in seite["sections"] if "tap_action" in s["cards"][0]]
    assert [k["heading"] for k in koepfe] == ["Kesselhaus", "Werkstatt"]
    assert koepfe[0]["tap_action"]["navigation_path"] == "/heatnexus/anlage-anlage01"
    erste = _abschnitt_mit(seite, "Kesselhaus")
    bild = [k for k in erste if str(k.get("type", "")).startswith("custom:")]
    assert bild and "zusatzwerte" not in bild[0]
    kacheln = [k["entity"] for k in erste if k.get("type") == "tile"]
    assert kacheln[:2] == ["sensor.betriebsphase", "sensor.kessel_ist"]


def _heizkreis(kennung: str, name: str) -> dict:
    return {
        "name": name,
        "id": kennung,
        "fct_type": 14,
        "symbol": "mdi:radiator",
        "rang": 30,
        "entitaeten": [
            _e(f"sensor.{kennung}_vorlauf", "Vorlauftemperatur", schluessel="flow_temperature"),
            _e(f"button.{kennung}_abfragen", "Werte jetzt abfragen"),
        ],
    }


def test_tasten_fuer_die_uebersicht(auswahl):
    teil = {
        **_kessel(),
        "entitaeten": [
            *_kessel()["entitaeten"],
            _e("button.abfragen", "Werte jetzt abfragen"),
            _e("button.einmalladung", "WW Einmalladung"),
        ],
    }
    assert [e["entity_id"] for e in auswahl.tasten(teil)] == [
        "button.abfragen",
        "button.einmalladung",
    ]


def test_uebersicht_zeigt_die_abfragetaste_einmal_je_anlage(uebersichtsseite):
    kessel = {
        **_kessel(),
        "entitaeten": [*_kessel()["entitaeten"], _e("button.k", "Werte jetzt abfragen")],
    }
    hk1, hk2 = _heizkreis("hk1", "Heizkreis 1"), _heizkreis("hk2", "Heizkreis 2")
    for kreis in (hk1, hk2):
        kreis["entitaeten"].append(_e(f"button.{kreis['id']}_ww", "WW Einmalladung"))
    anlage = _anlage(kessel, hk1, hk2)
    einzeln = _anlage(kessel, name="Werkstatt", kennung="werkst0123456789")
    seite = uebersichtsseite.uebersicht([anlage, einzeln], False, [])
    kacheln = [k for k in _abschnitt_mit(seite, "Kesselhaus") if k.get("type") == "tile"]
    abfragen = [k for k in kacheln if k["entity"].endswith("abfragen") or k["entity"] == "button.k"]
    # Die Taste liest nur ihren Anlagenteil; der Name sagt, welchen.
    assert [(k["entity"], k["name"]) for k in abfragen] == [
        ("button.k", "PuroWIN · Werte jetzt abfragen")
    ]
    # Mit nur einem Anlagenteil bleibt der Name, wie er ist.
    werkstatt = [k for k in _abschnitt_mit(seite, "Werkstatt") if k.get("type") == "tile"]
    assert [k["name"] for k in werkstatt if k["entity"] == "button.k"] == ["Werte jetzt abfragen"]
    ladungen = [k["entity"] for k in kacheln if k["name"] == "WW Einmalladung"]
    assert ladungen == ["button.hk1_ww", "button.hk2_ww"]


def test_kernwerte_mehrerer_teile_tragen_den_teilnamen(uebersichtsseite):
    anlage = _anlage(_kessel(), _heizkreis("hk1", "Heizkreis 1"), _heizkreis("hk2", "Heizkreis 2"))
    seite = uebersichtsseite.uebersicht([anlage, _anlage(_kessel(), name="Werkstatt")], False, [])
    namen = {k["entity"]: k["name"] for k in _abschnitt_mit(seite, "Kesselhaus") if "name" in k}
    assert namen["sensor.hk1_vorlauf"] == "Heizkreis 1 · Vorlauftemperatur"
    assert namen["sensor.hk2_vorlauf"] == "Heizkreis 2 · Vorlauftemperatur"
    assert namen["sensor.kessel_ist"] == "PuroWIN · Kesseltemperatur Ist"
    # Mit nur einem Teil bleibt der Name, wie er ist.
    einzeln = _abschnitt_mit(seite, "Werkstatt")
    assert "Kesseltemperatur Ist" in [k.get("name") for k in einzeln]


def test_zusammengesetzte_namen_bleiben_beim_uebersetzen_stehen():
    from custom_components.heatnexus.texte import LOVELACE_FELDER, Woerterbuch, uebersetze_baum

    karte = {"type": "tile", "name": "Heating circuit 1 · Flow temperature"}
    for sprache in ("en", "nl"):
        assert uebersetze_baum(karte, Woerterbuch(sprache), LOVELACE_FELDER) == karte


def test_meldung_steht_nur_bei_stoerung_oben(uebersichtsseite):
    seite = uebersichtsseite.uebersicht([_anlage(_kessel())], als_karte=False, badges=[])
    erste = seite["sections"][0]
    kopf, meldung = erste["cards"][0], erste["cards"][1]
    assert kopf["heading"] == "Meldungen"
    assert meldung["type"] == "markdown"
    bedingung = [{"condition": "state", "entity": "binary_sensor.stoerung", "state": "on"}]
    assert meldung["visibility"] == bedingung
    # Die Überschrift verschwindet mit der Meldung.
    assert kopf["visibility"] == bedingung
    assert erste["column_span"] == 3


def _kessel_mit_wartung() -> dict:
    teil = _kessel()
    teil["entitaeten"] = [
        *teil["entitaeten"],
        _e("sensor.vorrat", "Vorratsbehälter", schluessel="fuel_storage_status"),
        _e(
            "sensor.bis_reinigung",
            "Laufzeit bis Reinigung",
            schluessel="maintenance_cleaning_hours",
            wert=120.0,
        ),
        _e(
            "sensor.bis_asche",
            "Laufzeit bis Asche",
            schluessel="maintenance_ash_hours",
            hat_wert=False,
        ),
    ]
    return teil


def test_jede_badge_traegt_einen_namen(badges):
    liste = badges.anlagenbadges([_anlage(_kessel_mit_wartung())])
    assert [(b["entity"], b["name"]) for b in liste] == [
        ("sensor.betriebsphase", "Kessel"),
        ("sensor.vorrat", "Vorrat"),
        ("sensor.bis_reinigung", "Reinigung"),
        ("binary_sensor.stoerung", "PuroWIN"),
    ]
    assert all(b["show_name"] is True and b["type"] == "entity" for b in liste)


def test_wartung_erscheint_erst_unter_der_grenze(badges):
    liste = badges.anlagenbadges([_anlage(_kessel_mit_wartung())])
    [reinigung] = [b for b in liste if b["name"] == "Reinigung"]
    assert reinigung["visibility"] == [
        {"condition": "numeric_state", "entity": "sensor.bis_reinigung", "below": 50}
    ]


def test_stoerungsbadge_nur_solange_eine_anliegt(badges):
    liste = badges.anlagenbadges([_anlage(_kessel())])
    [stoerung] = [b for b in liste if b["entity"] == "binary_sensor.stoerung"]
    assert stoerung["visibility"] == [
        {"condition": "state", "entity": "binary_sensor.stoerung", "state": "on"}
    ]


def test_ohne_vorratsbehaelter_keine_vorrat_badge(badges):
    assert "Vorrat" not in [b["name"] for b in badges.anlagenbadges([_anlage(_kessel())])]


def test_bei_zwei_anlagen_steht_der_anlagenname_davor(badges):
    zweite = _anlage(
        {**_kessel(), "id": "zweiter0123456789"}, name="Werkstatt", kennung="werkst0123456789"
    )
    namen = [b["name"] for b in badges.anlagenbadges([_anlage(_kessel()), zweite])]
    assert "Kesselhaus · Kessel" in namen and "Werkstatt · PuroWIN" in namen
    assert "Kessel" not in namen


async def test_kopfzeile_uebersetzt_die_namen_mehrerer_anlagen(badges, hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.heatnexus.const import CONF_SPRACHE

    MockConfigEntry(domain="heatnexus", data={}, options={CONF_SPRACHE: "en"}).add_to_hass(hass)
    zweite = _anlage(
        {**_kessel(), "id": "zweiter0123456789"}, name="Werkstatt", kennung="werkst0123456789"
    )
    namen = [b["name"] for b in badges.kopfzeile(hass, [_anlage(_kessel()), zweite])]
    assert "Kesselhaus · Boiler" in namen
    assert not [n for n in namen if n.endswith("· Kessel")]


async def test_kopfzeile_nennt_jede_entitaet_einmal(badges, hass):
    liste = badges.kopfzeile(hass, [_anlage(_kessel())])
    entitaeten = [b["entity"] for b in liste]
    assert len(entitaeten) == len(set(entitaeten))


async def test_eine_anlage_ohne_reiter_uebersicht(dashboard, hass, monkeypatch):
    monkeypatch.setattr(dashboard, "anlagen_lesen", lambda _hass: [_anlage(_kessel())])
    hass.data["heatnexus_karte_js"] = True
    views = dashboard.dashboard_konfiguration(hass)["views"]
    assert views[0]["path"] == "anlage-anlage01"
    assert not [v for v in views if v["path"] == "uebersicht"]
    assert all("icon" not in v for v in views)


async def test_zwei_anlagen_uebersicht_zuerst_ohne_bild_im_anlagenreiter(
    dashboard, hass, monkeypatch
):
    zweite = _anlage(
        {**_kessel(), "id": "zweiter0123456789"}, name="Werkstatt", kennung="werkst0123456789"
    )
    monkeypatch.setattr(dashboard, "anlagen_lesen", lambda _hass: [_anlage(_kessel()), zweite])
    hass.data["heatnexus_karte_js"] = True
    views = dashboard.dashboard_konfiguration(hass)["views"]
    assert [v["path"] for v in views][:3] == ["uebersicht", "anlage-anlage01", "anlage-werkst01"]
    anlagenreiter = views[1]
    assert not [
        k
        for s in anlagenreiter["sections"]
        for k in s["cards"]
        if str(k.get("type", "")).startswith("custom:")
    ]


async def test_jedes_ziel_ist_eine_ansicht(dashboard, hass, monkeypatch):
    monkeypatch.setattr(dashboard, "anlagen_lesen", lambda _hass: [_anlage(_kessel())])
    views = dashboard.dashboard_konfiguration(hass)["views"]
    pfade = {f"/heatnexus/{v['path']}" for v in views}
    ziele = {
        k["tap_action"]["navigation_path"]
        for v in views
        for s in v.get("sections", [])
        for k in s["cards"]
        if k.get("tap_action", {}).get("action") == "navigate"
    } | {v["back_path"] for v in views if v.get("subview")}
    assert ziele and ziele <= pfade


def test_wartung_je_anlage_gegliedert(wartungsseite):
    teil = {**_kessel()}
    teil["entitaeten"] = [
        *teil["entitaeten"],
        _e(
            "sensor.bis_reinigung",
            "Laufzeit bis Reinigung",
            schluessel="maintenance_cleaning_hours",
            wert=120.0,
        ),
    ]
    ansicht = wartungsseite.wartung([_anlage(teil)])
    assert "icon" not in ansicht
    assert ansicht["sections"][0]["cards"][0]["heading"] == "Kesselhaus · PuroWIN"


async def test_die_vorlage_enthaelt_die_unteransichten(dashboard, hass, monkeypatch):
    """Wer das Dashboard kopiert, bekommt auch die Details je Anlagenteil."""
    import yaml

    monkeypatch.setattr(dashboard, "anlagen_lesen", lambda _hass: [_anlage(_kessel())])
    views = yaml.safe_load(dashboard.dashboard_als_yaml(hass))["views"]
    assert [v["path"] for v in views if v.get("subview")] == ["teil-kessel01"]
