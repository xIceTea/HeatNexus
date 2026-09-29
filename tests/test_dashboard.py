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
def ansichten(dashboard):
    return dashboard.ansichten


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


def test_der_text_zum_kopieren_setzt_die_eigene_karte(ansichten):
    """Nur als Karte lässt sich das Schaubild im Editor bearbeiten."""
    ansicht = ansichten.anlagenbild([_anlage_mit_teilen()], als_karte=True)
    karten = [k for abschnitt in ansicht["sections"] for k in abschnitt["cards"]]
    schaubild = [k for k in karten if k.get("type", "").startswith("custom:")]
    assert len(schaubild) == 1
    assert schaubild[0]["anlage"] == "anlage-1"
    assert schaubild[0]["liste"] == "rechts"
    assert "sensor.purowin_betriebsphase" in schaubild[0]["zusatzwerte"]


def test_ohne_kartenmodul_bleibt_die_zeichnung(ansichten):
    """Der Rückfall setzt kein Modul im Browser voraus."""
    ansicht = ansichten.anlagenbild([_anlage_mit_teilen()])
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


def test_meldungen_zeigen_text_und_abhilfe(ansichten):
    """Die Abhilfe steht nur im Attribut; die Kachel zeigte sie nicht."""
    anlage = _anlage_mit_teilen()
    anlage["teile"][0]["entitaeten"].append(
        {
            "entity_id": "sensor.purowin_meldung_klartext",
            "name": "PuroWIN Meldung Klartext",
            "bereich": "sensor",
            "hat_wert": True,
            "kategorie": "diagnostic",
            "state_class": None,
            "abgeleitet": False,
        }
    )
    karten = [
        karte
        for abschnitt in ansichten.uebersicht([anlage])["sections"]
        for karte in abschnitt["cards"]
        if karte.get("type") == "markdown"
    ]
    assert len(karten) == 1
    inhalt = karten[0]["content"]
    assert "state_attr('sensor.purowin_meldung_klartext', 'meldungen')" in inhalt
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
            "wert": 70.0,
            **rest,
        }

    anlage = _anlage_mit_teilen()
    anlage["teile"][0]["entitaeten"] = [
        # Alphabetisch: Die Ersatznamen sortieren dann wie die deutschen.
        eintrag("sensor.betriebsphase", "Betriebsphase"),
        eintrag("sensor.brennerstarts", "Brennerstarts", state_class="total_increasing"),
        eintrag("sensor.kesseltemperatur_ist", "Kesseltemperatur Ist"),
        eintrag("sensor.meldung_klartext", "Meldung Klartext", kategorie="diagnostic"),
        eintrag("sensor.nachstellzeit", "Nachstellzeit"),
        eintrag("button.serviceausbrand", "Serviceausbrand"),
    ]
    return anlage


def test_englische_namen_ergeben_dasselbe_dashboard(ansichten):
    """Rundinstrument, Reihenfolge, Rückfrage und Meldungen folgen dem deutschen Namen."""
    deutsch = _dashboard_anlage()
    teile, namen = auf_englisch(deutsch["teile"])
    englisch = {**deutsch, "teile": teile}

    def ansichten_von(anlage):
        [teil] = anlage["teile"]
        return [
            ansichten.uebersicht([anlage]),
            ansichten.anlagenbild([anlage]),
            ansichten.wartung([anlage]),
            ansichten.auswertung([anlage]),
            ansichten.geraeteansicht(anlage, teil, set()),
        ]

    assert zurueck_auf_deutsch(ansichten_von(englisch), namen) == ansichten_von(deutsch)
    kacheln = [k for a in ansichten_von(deutsch) for s in a["sections"] for k in s["cards"]]
    assert any(k.get("icon_tap_action") for k in kacheln)
    assert any(k.get("type") == "markdown" for k in kacheln)


# Merkmale deutscher Texte: Umlaute und häufige kurze Wörter.
DEUTSCH = re.compile(
    r"[äöüÄÖÜß]|\b(und|der|die|das|nicht|bis|von|mit|keine|seit|oder|für|zum|zur|Uhr|heute|"
    r"Wert|Zähler|Anlage|Heizung|Monat|dieser)\b"
)
SICHTBAR = frozenset({"title", "name", "heading", "content", "confirmation_text", "text"})


def _sichtbare_texte(wert, schluessel=None) -> list[str]:
    if isinstance(wert, dict):
        return [t for k, v in wert.items() for t in _sichtbare_texte(v, k)]
    if isinstance(wert, list):
        return [t for v in wert for t in _sichtbare_texte(v, schluessel)]
    if isinstance(wert, str) and schluessel in SICHTBAR and "{%" not in wert:
        return [wert]
    return []


def test_auf_englisch_bleibt_im_dashboard_nichts_deutsch(ansichten):
    """Jede Überschrift, jeder Kartenname und jede Rückfrage erscheint auf Englisch."""
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
        [
            ansichten.uebersicht([englisch]),
            ansichten.anlagenbild([englisch]),
            ansichten.wartung([englisch]),
            ansichten.auswertung([englisch]),
            ansichten.geraeteansicht(englisch, teil, set()),
        ],
        Woerterbuch("en"),
        LOVELACE_FELDER,
    )
    eigene = {anlage["name"], teil["name"]}

    def ohne_eigene(text: str) -> str:
        for name in eigene:
            text = text.replace(name, "")
        return text

    reste = sorted({t for t in _sichtbare_texte(fertig) if DEUTSCH.search(ohne_eigene(t))})
    assert not reste, f"auf Englisch noch deutsch: {reste}"


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
