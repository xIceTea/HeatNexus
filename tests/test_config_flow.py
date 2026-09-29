"""Einrichtungsdialog: Adressbereinigung und Optionsprüfung."""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def flow():
    from custom_components.heatnexus import config_flow

    return config_flow


@pytest.fixture(scope="module")
def formulare():
    from custom_components.heatnexus import formulare

    return formulare


@pytest.fixture(scope="module")
def quellenflow():
    from custom_components.heatnexus import waermequelle_flow

    return waermequelle_flow


@pytest.mark.parametrize(
    ("eingabe", "erwartet"),
    [
        ("192.0.2.10", "192.0.2.10"),
        (" 192.0.2.10 ", "192.0.2.10"),
        ("http://192.0.2.10/", "192.0.2.10"),
        ("https://192.0.2.10:8080/api", "192.0.2.10"),
        ("192.0.2.10/api/1.0", "192.0.2.10"),
    ],
)
def test_clean_host(formulare, eingabe, erwartet):
    assert formulare.clean_host(eingabe) == erwartet


def test_info_und_betreiberebene_sind_pflicht(formulare):
    from custom_components.heatnexus.const import (
        CONF_LEVELS,
        LEVEL_INFO,
        LEVEL_OPERATE,
    )

    options = formulare.normalize_options({CONF_LEVELS: ["service"]})
    assert LEVEL_INFO in options[CONF_LEVELS]
    assert LEVEL_OPERATE in options[CONF_LEVELS]


def test_unbekannte_ebene_wird_verworfen(formulare):
    from custom_components.heatnexus.const import CONF_LEVELS

    options = formulare.normalize_options({CONF_LEVELS: ["info", "quatsch", "oem"]})
    assert options[CONF_LEVELS] == ["info", "operate", "oem"]


def test_anlagenkennung_kommt_aus_der_seriennummer(formulare):
    """Die Kennung darf nicht an der Adresse hängen."""
    struktur = [
        {"nodeId": 60, "neuronId": "0702bb000002"},
        {"nodeId": 14, "neuronId": "0702cc000003"},
        {"nodeId": 15, "neuronId": "0702aa000001"},
    ]
    # Immer die kleinste Seriennummer – unabhängig von der Reihenfolge, in der
    # die Anlage ihre Knoten meldet.
    assert formulare.anlagenkennung(struktur) == "0702aa000001"
    assert formulare.anlagenkennung(list(reversed(struktur))) == "0702aa000001"


def test_anlagenkennung_ohne_seriennummer(formulare):
    assert formulare.anlagenkennung([{"nodeId": 1}]) == ""
    assert formulare.anlagenkennung([]) == ""


def test_menueschritt_fuer_jede_anlage(flow):
    """Auch die siebte Anlage muss einen Schritt bekommen."""
    optionen = flow.WindhagerOptionsFlow()
    assert callable(optionen.async_step_anlage_0)
    assert callable(optionen.async_step_anlage_9)
    for unbekannt in ("async_step_anlage_x", "irgendwas_anderes"):
        with pytest.raises(AttributeError):
            getattr(optionen, unbekannt)


def test_schalter_und_intervall_werden_uebernommen(formulare):
    from custom_components.heatnexus.const import (
        CONF_ENABLE_ADVANCED,
        CONF_UPDATE_INTERVAL,
        CONF_WRITABLE_ADVANCED,
    )

    options = formulare.normalize_options(
        {
            CONF_ENABLE_ADVANCED: True,
            CONF_WRITABLE_ADVANCED: True,
            CONF_UPDATE_INTERVAL: 45.0,
        }
    )
    assert options[CONF_ENABLE_ADVANCED] is True
    assert options[CONF_WRITABLE_ADVANCED] is True
    assert options[CONF_UPDATE_INTERVAL] == 45


def test_zeitwerte_sind_abwaehlbar_und_standardmaessig_aus(formulare):
    """Uhrzeiten und Datumsfelder sind Einstellwerte, keine Messwerte.

    Wer sie doch alle haben will, setzt den Haken einmal, statt jede Entität
    einzeln in Home Assistant einzuschalten.
    """
    from custom_components.heatnexus.const import CONF_ZEITWERTE

    assert formulare.normalize_options({})[CONF_ZEITWERTE] is False
    assert formulare.normalize_options({CONF_ZEITWERTE: True})[CONF_ZEITWERTE] is True


def test_zeitwerte_aendern_den_umfang():
    """Sie entscheiden, was abgefragt wird – der Erkennungsstand gilt dann nicht mehr."""
    from custom_components.heatnexus.erkennungsstand import umfang_fingerprint

    umfang = {
        "levels": ["info", "operate"],
        "enable_advanced": False,
        "writable_advanced": False,
        "username": "USER",
    }
    assert umfang_fingerprint(umfang) != umfang_fingerprint({**umfang, "zeitwerte": True})


def test_kesselart_wird_uebernommen_und_geprueft(formulare):
    """Die Kesselart wirkt nur auf das Schaubild – aber sie muss ankommen."""
    from custom_components.heatnexus.const import CONF_KESSELART, KESSELART_AUTO

    assert formulare.normalize_options({CONF_KESSELART: "pellets"})[CONF_KESSELART] == "pellets"
    # Fehlt sie oder ist sie unbekannt, wird automatisch erkannt.
    assert formulare.normalize_options({})[CONF_KESSELART] == KESSELART_AUTO
    assert formulare.normalize_options({CONF_KESSELART: "dampfmaschine"})[CONF_KESSELART] == (
        KESSELART_AUTO
    )


def test_kesselart_aendert_den_umfang_nicht():
    """Eine andere Zeichnung darf die Anlage nicht neu einlesen lassen.

    Der Erkennungsstand hängt am Umfang. Käme die Kesselart darin vor, kostete
    jede Umstellung einen vollen Neuabzug von 30–120 s.
    """
    from custom_components.heatnexus.erkennungsstand import umfang_fingerprint

    umfang = {
        "levels": ["info", "operate"],
        "enable_advanced": False,
        "writable_advanced": False,
        "username": "USER",
    }
    assert umfang_fingerprint(umfang) == umfang_fingerprint({**umfang, "kesselart": "pellets"})


async def test_allgemeine_einstellungen_auch_bei_einer_anlage(flow, monkeypatch):
    """Sonst wären sie nach der Einrichtung nie wieder erreichbar.

    Bei einer einzigen Anlage sprang der Dialog direkt zu deren Ebenen – und
    damit an Sprache, Dashboard, Panel, Erklärungen und Abfrageintervall
    vorbei.
    """
    from homeassistant.const import CONF_HOST

    optionen = flow.WindhagerOptionsFlow()
    monkeypatch.setattr(optionen, "_systeme", lambda: [{CONF_HOST: "192.0.2.10"}])

    ergebnis = await optionen.async_step_init()

    assert "allgemein" in ergebnis["menu_options"]
    assert "anlage_0" in ergebnis["menu_options"]


async def test_die_vorlagen_werden_ausserhalb_der_ereignisschleife_gelesen(flow, monkeypatch):
    """Home Assistant meldet einen Dateizugriff in der Ereignisschleife als blockierend."""
    from types import SimpleNamespace

    aufgerufen = []

    async def im_executor(funktion, *argumente):
        aufgerufen.append(funktion)
        return funktion(*argumente)

    optionen = flow.WindhagerOptionsFlow()
    optionen.hass = SimpleNamespace(
        async_add_executor_job=im_executor,
        config_entries=SimpleNamespace(async_entries=lambda _domain: []),
    )
    monkeypatch.setattr(
        type(optionen), "config_entry", property(lambda _self: SimpleNamespace(options={}))
    )

    ergebnis = await optionen.async_step_allgemein()

    assert aufgerufen == [flow.verfuegbare_vorlagen]
    assert ergebnis["step_id"] == "allgemein"


def test_der_dialog_nennt_die_werte_die_nur_der_bus_hergibt(flow, monkeypatch):
    """Sonst steht dort eine Sammelaussage, die je Baureihe stimmt oder nicht."""
    from types import SimpleNamespace

    optionen = flow.WindhagerOptionsFlow()
    koordinator = SimpleNamespace(client=SimpleNamespace(devices=[{"fct_type": 9}]))
    monkeypatch.setattr(
        type(optionen),
        "config_entry",
        property(
            lambda _self: SimpleNamespace(
                runtime_data={"coordinators": {"192.0.2.10": koordinator}}
            )
        ),
    )

    assert "Brennkammertemperatur" in optionen._bus_hinweis("192.0.2.10")


def test_ohne_eigene_busbegriffe_bleibt_der_hinweis_leer(flow, monkeypatch):
    """Am PuroWIN trägt der Bus nichts bei, was nicht schon Datenpunkt wäre."""
    from types import SimpleNamespace

    optionen = flow.WindhagerOptionsFlow()
    koordinator = SimpleNamespace(client=SimpleNamespace(devices=[{"fct_type": 25}]))
    monkeypatch.setattr(
        type(optionen),
        "config_entry",
        property(
            lambda _self: SimpleNamespace(
                runtime_data={"coordinators": {"192.0.2.10": koordinator}}
            )
        ),
    )

    assert optionen._bus_hinweis("192.0.2.10") == ""


def test_labels_stehen_bei_der_anlage(formulare):
    """Gespeichert wird die Id des Labels, nicht sein Name.

    Ein umbenanntes Label behielte sonst seine Karte nicht.
    """
    from custom_components.heatnexus.const import CONF_MARKEN

    optionen = formulare.normalize_options({CONF_MARKEN: ["abc123", "def456"]})

    assert optionen[CONF_MARKEN] == ["abc123", "def456"]


def test_zugeordnet_gilt_nur_was_gezeigt_wird(formulare):
    """Ein Label im Systemstatus, das gar nicht gewählt ist, hätte keine Wirkung."""
    from custom_components.heatnexus.const import CONF_MARKEN, CONF_MARKEN_STATUS

    optionen = formulare.normalize_options(
        {CONF_MARKEN: ["abc123"], CONF_MARKEN_STATUS: ["abc123", "fremd"]}
    )

    assert optionen[CONF_MARKEN_STATUS] == ["abc123"]


def test_mehr_labels_als_karten_werden_abgeschnitten(formulare):
    """Die Auswahl darf den Abzug nicht beliebig aufblähen."""
    from custom_components.heatnexus.const import CONF_MARKEN, MARKEN_MAX_KARTEN

    optionen = formulare.normalize_options(
        {CONF_MARKEN: [f"label{n}" for n in range(MARKEN_MAX_KARTEN + 4)]}
    )

    assert len(optionen[CONF_MARKEN]) == MARKEN_MAX_KARTEN


async def test_ohne_kandidaten_bleibt_die_auswahl_stehen(flow, monkeypatch):
    """Der schwerste Fall: Das Feld fehlt, die Auswahl steht in den Optionen.

    Während des Einlesens gibt es keine Kandidaten, das Feld erscheint nicht —
    und ein Bestätigen ohne dieses Feld löschte bisher die gespeicherte Wahl.
    """
    from types import SimpleNamespace

    from custom_components.heatnexus.const import CONF_ZUSATZWERTE

    gespeichert = {}
    optionen = flow.WindhagerOptionsFlow()
    optionen._host = "192.0.2.10"
    monkeypatch.setattr(
        type(optionen),
        "config_entry",
        property(
            lambda _self: SimpleNamespace(
                options={"192.0.2.10": {CONF_ZUSATZWERTE: ["wert-a", "wert-b"]}},
                data={},
            )
        ),
    )
    monkeypatch.setattr(type(optionen), "_systeme", lambda _self: [{"host": "192.0.2.10"}])
    monkeypatch.setattr(type(optionen), "_zusatzkandidaten", lambda _self, host: [])
    monkeypatch.setattr(type(optionen), "_zugang_uebernehmen", lambda _self, host, benutzer: None)
    monkeypatch.setattr(
        type(optionen), "async_create_entry", lambda _self, data: gespeichert.update(data) or {}
    )

    await optionen.async_step_system({"levels": ["info", "operate"]})

    assert gespeichert["192.0.2.10"][CONF_ZUSATZWERTE] == ["wert-a", "wert-b"]


async def test_die_bezeichnung_der_anlage_laesst_sich_aendern(flow, monkeypatch):
    """Sie steht vor jedem Gerätenamen; der Zugang bleibt dabei unverändert."""
    from types import SimpleNamespace

    from custom_components.heatnexus.const import CONF_LABEL, CONF_SYSTEMS

    geschrieben = {}
    eintrag = SimpleNamespace(
        options={},
        data={CONF_SYSTEMS: [{"host": "192.0.2.10", CONF_LABEL: "Anlage 1", "username": "USER"}]},
    )
    optionen = flow.WindhagerOptionsFlow()
    optionen._host = "192.0.2.10"
    optionen.hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_update_entry=lambda _eintrag, data: geschrieben.update(data)
        )
    )
    monkeypatch.setattr(type(optionen), "config_entry", property(lambda _self: eintrag))
    monkeypatch.setattr(type(optionen), "_zusatzkandidaten", lambda _self, host: [])
    monkeypatch.setattr(type(optionen), "async_create_entry", lambda _self, data: {})

    await optionen.async_step_system(
        {CONF_LABEL: " Kesselhaus ", "username": "USER", "levels": ["info"]}
    )

    assert geschrieben[CONF_SYSTEMS] == [
        {"host": "192.0.2.10", CONF_LABEL: "Kesselhaus", "username": "USER"}
    ]


# ---------------------------------------------------------------------------
# Steuerungen nachträglich hinzufügen und entfernen
# ---------------------------------------------------------------------------
A, B, C = "192.0.2.10", "192.0.2.20", "192.0.2.30"


def _optionen_mit(flow, monkeypatch, systeme, geschrieben):
    """Ein Optionsdialog mit Eintrag, ohne laufendes Home Assistant."""
    from types import SimpleNamespace

    from custom_components.heatnexus.const import CONF_SYSTEMS

    eintrag = SimpleNamespace(
        entry_id="e1",
        data={CONF_SYSTEMS: systeme},
        options={A: {"levels": ["info", "operate"], "marken": ["x"]}, "sprache": "de"},
        runtime_data={},
    )
    optionen = flow.WindhagerOptionsFlow()
    optionen.hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_entries=lambda _domain: [],
            async_update_entry=lambda _e, **felder: geschrieben.update(felder),
        )
    )
    monkeypatch.setattr(type(optionen), "config_entry", property(lambda _self: eintrag))
    monkeypatch.setattr(
        type(optionen),
        "async_abort",
        lambda _self, *, reason, description_placeholders=None: {"type": "abort", "reason": reason},
    )
    return optionen


async def test_das_menue_bietet_hinzufuegen_und_entfernen_nur_bei_mehreren(flow, monkeypatch):
    einzeln = _optionen_mit(flow, monkeypatch, [{"host": A, "label": "Kesselhaus"}], {})
    menue_einzeln = (await einzeln.async_step_init())["menu_options"]
    mehrere = _optionen_mit(
        flow, monkeypatch, [{"host": A, "label": "Kesselhaus"}, {"host": B, "label": "Stall"}], {}
    )
    menue_mehrere = (await mehrere.async_step_init())["menu_options"]

    assert "steuerung_neu" in menue_einzeln and "steuerung_entfernen" not in menue_einzeln
    assert "steuerung_entfernen" in menue_mehrere


async def test_eine_steuerung_kommt_nachtraeglich_dazu(flow, monkeypatch):
    from custom_components.heatnexus.const import CONF_SYSTEMS

    geschrieben = {}
    optionen = _optionen_mit(
        flow, monkeypatch, [{"host": A, "label": "Kesselhaus", "kennung": "k-a"}], geschrieben
    )

    async def verbinden(host, passwort, benutzer):
        return [{"neuronId": "k-c", "functions": []}]

    monkeypatch.setattr(flow, "validate_connection", verbinden)
    ergebnis = await optionen.async_step_steuerung_neu(
        {"label": "Werkstatt", "host": " 192.0.2.30 ", "username": "USER", "password": "geheim"}
    )

    assert ergebnis == {"type": "abort", "reason": "steuerung_hinzugefuegt"}
    assert geschrieben["data"][CONF_SYSTEMS][-1] == {
        "label": "Werkstatt",
        "host": C,
        "username": "USER",
        "password": "geheim",
        "kennung": "k-c",
    }
    assert geschrieben["options"][C] == {"levels": ["info", "operate"]}
    assert geschrieben["options"]["sprache"] == "de"
    assert geschrieben["unique_id"] == "k-a-k-c"


async def test_eine_vorhandene_adresse_kommt_nicht_doppelt(flow, monkeypatch):
    geschrieben = {}
    optionen = _optionen_mit(flow, monkeypatch, [{"host": A, "label": "Kesselhaus"}], geschrieben)

    ergebnis = await optionen.async_step_steuerung_neu(
        {"label": "Doppelt", "host": A, "username": "USER", "password": "x"}
    )

    assert ergebnis["errors"] == {"base": "already_configured"}
    assert not geschrieben


async def test_ohne_verbindung_kommt_keine_steuerung_dazu(flow, monkeypatch):
    from custom_components.heatnexus.exceptions import CannotConnect

    geschrieben = {}
    optionen = _optionen_mit(flow, monkeypatch, [{"host": A, "label": "Kesselhaus"}], geschrieben)

    async def verbinden(host, passwort, benutzer):
        raise CannotConnect

    monkeypatch.setattr(flow, "validate_connection", verbinden)
    ergebnis = await optionen.async_step_steuerung_neu(
        {"label": "Werkstatt", "host": C, "username": "USER", "password": "x"}
    )

    assert ergebnis["errors"] == {"base": "cannot_connect"}
    assert not geschrieben


async def test_die_letzte_steuerung_laesst_sich_nicht_entfernen(flow, monkeypatch):
    optionen = _optionen_mit(flow, monkeypatch, [{"host": A, "label": "Kesselhaus"}], {})

    assert await optionen.async_step_steuerung_entfernen() == {
        "type": "abort",
        "reason": "letzte_steuerung",
    }


async def test_das_entfernen_nennt_die_folgen_und_verlangt_den_haken(flow, monkeypatch):
    from custom_components.heatnexus.steuerungen import Folgen

    optionen = _optionen_mit(
        flow, monkeypatch, [{"host": A, "label": "Kesselhaus"}, {"host": B, "label": "Stall"}], {}
    )
    entfernt = []
    monkeypatch.setattr(
        flow.steuerungen,
        "folgen",
        lambda _hass, _eintrag, host: Folgen(3, ["Heizkreis 1"], ["Solaranlage"]),
    )

    async def entfernen(_hass, _eintrag, host):
        entfernt.append(host)

    monkeypatch.setattr(flow.steuerungen, "entfernen", entfernen)

    auswahl = await optionen.async_step_steuerung_entfernen()
    frage = await optionen.async_step_steuerung_entfernen({"host": B})
    ohne_haken = await optionen.async_step_steuerung_entfernen_bestaetigen({"verstanden": False})
    ende = await optionen.async_step_steuerung_entfernen_bestaetigen({"verstanden": True})

    assert auswahl["step_id"] == "steuerung_entfernen"
    assert frage["step_id"] == "steuerung_entfernen_bestaetigen"
    assert frage["description_placeholders"] == {
        "anlage": "Stall (192.0.2.20)",
        "geraete": "3",
        "automatiken": "Heizkreis 1",
        "quellen": "Solaranlage",
    }
    assert ohne_haken["errors"] == {"base": "bestaetigung_fehlt"}
    assert ende == {"type": "abort", "reason": "steuerung_entfernt"}
    assert entfernt == [B]


# ---------------------------------------------------------------------------
# Wärmequellen ohne Anschluss an die Steuerung
# ---------------------------------------------------------------------------
SOLAR = {
    "id": "q1",
    "name": "Solaranlage",
    "art": "solar",
    "bedingung": {
        "art": "differenz",
        "quelle": "sensor.kollektor",
        "gegen": "sensor.puffer",
        "ein": 8,
    },
}


def test_eine_vollstaendige_quelle_bleibt_erhalten():
    from custom_components.heatnexus import waermequelle

    assert waermequelle.quellen_pruefen([SOLAR]) == [{**SOLAR, "pumpe": False}]


@pytest.mark.parametrize(
    "abweichung",
    [
        {"id": ""},
        {"name": " "},
        {"art": "waermepumpe"},
        {"bedingung": {"art": "differenz", "quelle": "sensor.kollektor", "ein": 8}},
        {"bedingung": {"art": "schwelle", "quelle": "sensor.kollektor"}},
        {"bedingung": {"art": "unfug", "quelle": "sensor.kollektor", "ein": 8}},
    ],
)
def test_eine_unvollstaendige_quelle_faellt_weg(abweichung):
    """Eine Quelle ohne auswertbare Bedingung ergäbe eine Entität, die nie an ist."""
    from custom_components.heatnexus import waermequelle

    assert waermequelle.quellen_pruefen([{**SOLAR, **abweichung}]) == []


def test_mehr_quellen_als_das_schaubild_fasst_werden_abgeschnitten():
    from custom_components.heatnexus import waermequelle
    from custom_components.heatnexus.const import QUELLEN_MAX

    viele = [{**SOLAR, "id": f"q{i}"} for i in range(QUELLEN_MAX + 3)]

    assert len(waermequelle.quellen_pruefen(viele)) == QUELLEN_MAX


def test_die_bedingung_traegt_nur_bekannte_felder():
    from custom_components.heatnexus import waermequelle

    regel = waermequelle.bedingung_pruefen(
        {
            "art": "schwelle",
            "quelle": "sensor.kollektor",
            "ein": "60",
            "aus": "",
            "erfunden": "weg damit",
        }
    )

    assert regel == {"art": "schwelle", "quelle": "sensor.kollektor", "ein": 60.0}


def test_eine_entfernte_kennung_wird_nicht_neu_vergeben():
    """Die Kennung hängt an der Entität; eine zweite Quelle darf sie nie erben."""
    from custom_components.heatnexus import waermequelle

    quellen = [{**SOLAR, "id": "q1"}, {**SOLAR, "id": "q3"}]

    assert waermequelle.quelle_id(quellen) == "q2"
    assert waermequelle.quelle_id([*quellen, {**SOLAR, "id": "q2"}]) == "q4"


def test_das_formular_fragt_nur_die_felder_seiner_bedingung(quellenflow):
    zustand = quellenflow.regel_schema("zustand", {}, ["Solaranlage aktiv"])
    schwelle = quellenflow.regel_schema("schwelle", {}, [])
    differenz = quellenflow.regel_schema("differenz", {}, [])

    assert [str(feld) for feld in zustand.schema] == ["zustaende"]
    assert [str(feld) for feld in schwelle.schema] == ["ein", "aus"]
    assert [str(feld) for feld in differenz.schema] == ["gegen", "ein", "aus"]


def test_ein_zustand_im_klartext_ist_pflicht(quellenflow):
    """Ohne Auswahl gälte jeder Text als an, auch einer, der aus bedeutet."""
    import voluptuous as vol

    klartext = quellenflow.regel_schema("zustand", {}, ["Solaranlage inaktiv"])
    binaer = quellenflow.regel_schema("zustand", {}, ["on"])

    with pytest.raises(vol.Invalid):
        klartext({})
    assert binaer({}) == {}
