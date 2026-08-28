"""Einrichtungsdialog: Adressbereinigung und Optionsprüfung."""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def flow():
    from custom_components.heatnexus import config_flow

    return config_flow


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
def test_clean_host(flow, eingabe, erwartet):
    assert flow.clean_host(eingabe) == erwartet


def test_info_und_betreiberebene_sind_pflicht(flow):
    from custom_components.heatnexus.const import (
        CONF_LEVELS,
        LEVEL_INFO,
        LEVEL_OPERATE,
    )

    options = flow.normalize_options({CONF_LEVELS: ["service"]})
    assert LEVEL_INFO in options[CONF_LEVELS]
    assert LEVEL_OPERATE in options[CONF_LEVELS]


def test_unbekannte_ebene_wird_verworfen(flow):
    from custom_components.heatnexus.const import CONF_LEVELS

    options = flow.normalize_options({CONF_LEVELS: ["info", "quatsch", "oem"]})
    assert options[CONF_LEVELS] == ["info", "operate", "oem"]


def test_anlagenkennung_kommt_aus_der_seriennummer(flow):
    """Die Kennung darf nicht an der Adresse hängen."""
    struktur = [
        {"nodeId": 60, "neuronId": "0702bb000002"},
        {"nodeId": 14, "neuronId": "0702cc000003"},
        {"nodeId": 15, "neuronId": "0702aa000001"},
    ]
    # Immer die kleinste Seriennummer – unabhängig von der Reihenfolge, in der
    # die Anlage ihre Knoten meldet.
    assert flow.anlagenkennung(struktur) == "0702aa000001"
    assert flow.anlagenkennung(list(reversed(struktur))) == "0702aa000001"


def test_anlagenkennung_ohne_seriennummer(flow):
    assert flow.anlagenkennung([{"nodeId": 1}]) == ""
    assert flow.anlagenkennung([]) == ""


def test_menueschritt_fuer_jede_anlage(flow):
    """Auch die siebte Anlage muss einen Schritt bekommen."""
    optionen = flow.WindhagerOptionsFlow()
    assert callable(optionen.async_step_anlage_0)
    assert callable(optionen.async_step_anlage_9)
    for unbekannt in ("async_step_anlage_x", "irgendwas_anderes"):
        with pytest.raises(AttributeError):
            getattr(optionen, unbekannt)


def test_schalter_und_intervall_werden_uebernommen(flow):
    from custom_components.heatnexus.const import (
        CONF_ENABLE_ADVANCED,
        CONF_UPDATE_INTERVAL,
        CONF_WRITABLE_ADVANCED,
    )

    options = flow.normalize_options(
        {
            CONF_ENABLE_ADVANCED: True,
            CONF_WRITABLE_ADVANCED: True,
            CONF_UPDATE_INTERVAL: 45.0,
        }
    )
    assert options[CONF_ENABLE_ADVANCED] is True
    assert options[CONF_WRITABLE_ADVANCED] is True
    assert options[CONF_UPDATE_INTERVAL] == 45


def test_zeitwerte_sind_abwaehlbar_und_standardmaessig_aus(flow):
    """Uhrzeiten und Datumsfelder sind Einstellwerte, keine Messwerte.

    Wer sie doch alle haben will, setzt den Haken einmal, statt jede Entität
    einzeln in Home Assistant einzuschalten.
    """
    from custom_components.heatnexus.const import CONF_ZEITWERTE

    assert flow.normalize_options({})[CONF_ZEITWERTE] is False
    assert flow.normalize_options({CONF_ZEITWERTE: True})[CONF_ZEITWERTE] is True


def test_zeitwerte_aendern_den_umfang(flow):
    """Sie entscheiden, was abgefragt wird – der Erkennungsstand gilt dann nicht mehr."""
    from custom_components.heatnexus import _scope_fingerprint

    umfang = {
        "levels": ["info", "operate"],
        "enable_advanced": False,
        "writable_advanced": False,
        "username": "USER",
    }
    assert _scope_fingerprint(umfang) != _scope_fingerprint({**umfang, "zeitwerte": True})


def test_kesselart_wird_uebernommen_und_geprueft(flow):
    """Die Kesselart wirkt nur auf das Schaubild – aber sie muss ankommen."""
    from custom_components.heatnexus.const import CONF_KESSELART, KESSELART_AUTO

    assert flow.normalize_options({CONF_KESSELART: "pellets"})[CONF_KESSELART] == "pellets"
    # Fehlt sie oder ist sie unbekannt, wird automatisch erkannt.
    assert flow.normalize_options({})[CONF_KESSELART] == KESSELART_AUTO
    assert flow.normalize_options({CONF_KESSELART: "dampfmaschine"})[CONF_KESSELART] == (
        KESSELART_AUTO
    )


def test_kesselart_aendert_den_umfang_nicht(flow):
    """Eine andere Zeichnung darf die Anlage nicht neu einlesen lassen.

    Der Erkennungsstand hängt am Umfang. Käme die Kesselart darin vor, kostete
    jede Umstellung einen vollen Neuabzug von 30–120 s.
    """
    from custom_components.heatnexus import _scope_fingerprint

    umfang = {
        "levels": ["info", "operate"],
        "enable_advanced": False,
        "writable_advanced": False,
        "username": "USER",
    }
    assert _scope_fingerprint(umfang) == _scope_fingerprint({**umfang, "kesselart": "pellets"})


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


def test_labels_stehen_bei_der_anlage(flow):
    """Gespeichert wird die Id des Labels, nicht sein Name.

    Ein umbenanntes Label behielte sonst seine Karte nicht.
    """
    from custom_components.heatnexus.const import CONF_MARKEN

    optionen = flow.normalize_options({CONF_MARKEN: ["abc123", "def456"]})

    assert optionen[CONF_MARKEN] == ["abc123", "def456"]


def test_zugeordnet_gilt_nur_was_gezeigt_wird(flow):
    """Ein Label im Systemstatus, das gar nicht gewählt ist, hätte keine Wirkung."""
    from custom_components.heatnexus.const import CONF_MARKEN, CONF_MARKEN_STATUS

    optionen = flow.normalize_options(
        {CONF_MARKEN: ["abc123"], CONF_MARKEN_STATUS: ["abc123", "fremd"]}
    )

    assert optionen[CONF_MARKEN_STATUS] == ["abc123"]


def test_mehr_labels_als_karten_werden_abgeschnitten(flow):
    """Die Auswahl darf den Abzug nicht beliebig aufblähen."""
    from custom_components.heatnexus.const import CONF_MARKEN, MARKEN_MAX_KARTEN

    optionen = flow.normalize_options(
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

    assert waermequelle.quellen_pruefen([SOLAR]) == [SOLAR]


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


def test_die_bedingung_traegt_nur_bekannte_felder(flow):
    regel = flow.bedingung_pruefen(
        {
            "art": "schwelle",
            "quelle": "sensor.kollektor",
            "ein": "60",
            "aus": "",
            "erfunden": "weg damit",
        }
    )

    assert regel == {"art": "schwelle", "quelle": "sensor.kollektor", "ein": 60.0}


def test_eine_entfernte_kennung_wird_nicht_neu_vergeben(flow):
    """Die Kennung hängt an der Entität; eine zweite Quelle darf sie nie erben."""
    quellen = [{**SOLAR, "id": "q1"}, {**SOLAR, "id": "q3"}]

    assert flow.quelle_id(quellen) == "q2"
    assert flow.quelle_id([*quellen, {**SOLAR, "id": "q2"}]) == "q4"


def test_das_formular_fragt_nur_die_felder_seiner_bedingung(flow):
    zustand = flow.regel_schema("zustand", {}, ["Solaranlage aktiv"])
    schwelle = flow.regel_schema("schwelle", {}, [])
    differenz = flow.regel_schema("differenz", {}, [])

    assert [str(feld) for feld in zustand.schema] == ["zustaende"]
    assert [str(feld) for feld in schwelle.schema] == ["ein", "aus"]
    assert [str(feld) for feld in differenz.schema] == ["gegen", "ein", "aus"]


def test_ein_zustand_im_klartext_ist_pflicht(flow):
    """Ohne Auswahl gälte jeder Text als an, auch einer, der aus bedeutet."""
    import voluptuous as vol

    klartext = flow.regel_schema("zustand", {}, ["Solaranlage inaktiv"])
    binaer = flow.regel_schema("zustand", {}, ["on"])

    with pytest.raises(vol.Invalid):
        klartext({})
    assert binaer({}) == {}


def _dialog(flow, monkeypatch, quellen=(), gespeichert=None):
    """Ein Optionsdialog mit einer Anlage und den übergebenen Quellen."""
    from types import SimpleNamespace

    from custom_components.heatnexus.const import CONF_QUELLEN

    optionen = flow.WindhagerOptionsFlow()
    monkeypatch.setattr(
        type(optionen),
        "config_entry",
        property(
            lambda _self: SimpleNamespace(
                options={"192.0.2.10": {CONF_QUELLEN: list(quellen)}}, data={}
            )
        ),
    )
    monkeypatch.setattr(
        type(optionen),
        "_systeme",
        lambda _self: [{"host": "192.0.2.10", "label": "Anlage 1"}],
    )
    monkeypatch.setattr(
        type(optionen), "async_show_menu", lambda _self, step_id, menu_options: menu_options
    )
    monkeypatch.setattr(
        type(optionen),
        "async_show_form",
        lambda _self, step_id, **rest: {"step_id": step_id, **rest},
    )
    if gespeichert is not None:
        monkeypatch.setattr(
            type(optionen),
            "async_create_entry",
            lambda _self, data: gespeichert.update(data) or {},
        )
    return optionen


async def test_das_menue_fuehrt_je_anlage_eine_zeile_fuer_quellen(flow, monkeypatch):
    optionen = _dialog(flow, monkeypatch)

    auswahl = await optionen.async_step_init()

    assert "anlage_0" in auswahl
    assert auswahl["quellen_0"].startswith("Anlage 1")


async def test_das_quellenmenue_zeigt_jede_quelle_und_den_weg_zur_neuen(flow, monkeypatch):
    optionen = _dialog(flow, monkeypatch, quellen=[SOLAR])

    auswahl = await optionen.async_step_quellen_0()

    assert auswahl["bearbeiten_0"].startswith("Solaranlage")
    assert "neu" in auswahl


async def test_jedes_menue_nennt_einen_schritt_den_es_gibt(flow, monkeypatch):
    """Home Assistant weist ein Menü ab, dessen Schritt keine Methode hat."""
    optionen = _dialog(flow, monkeypatch, quellen=[SOLAR])
    gezeigt: list[str] = []
    monkeypatch.setattr(
        type(optionen),
        "async_show_menu",
        lambda _self, step_id, menu_options: gezeigt.append(step_id) or menu_options,
    )

    await optionen.async_step_init()
    await optionen.async_step_quellen_0()

    assert gezeigt == ["init", "quellen"]
    for schritt in gezeigt:
        assert callable(getattr(optionen, f"async_step_{schritt}", None))


async def test_ohne_platz_entfaellt_der_weg_zur_neuen_quelle(flow, monkeypatch):
    from custom_components.heatnexus.const import QUELLEN_MAX

    voll = [{**SOLAR, "id": f"q{i}"} for i in range(QUELLEN_MAX)]
    optionen = _dialog(flow, monkeypatch, quellen=voll)

    auswahl = await optionen.async_step_quellen_0()

    assert "neu" not in auswahl


async def test_das_abgesendete_formular_trifft_dieselbe_quelle(flow, monkeypatch):
    """Home Assistant ruft nach dem Absenden den Schritt, nicht den Menüeintrag."""
    from custom_components.heatnexus.const import CONF_QUELLEN

    gespeichert = {}
    optionen = _dialog(flow, monkeypatch, quellen=[SOLAR], gespeichert=gespeichert)

    formular = await optionen.async_step_quellen_0()
    assert "bearbeiten_0" in formular
    await optionen.async_step_bearbeiten_0()
    await optionen.async_step_quelle(
        {
            "name": "Solar Dach",
            "art": "solar",
            "bedingung_art": "zustand",
            "quelle": "switch.solar",
        }
    )

    quellen = gespeichert["192.0.2.10"][CONF_QUELLEN]
    assert [q["id"] for q in quellen] == ["q1"]
    assert quellen[0]["name"] == "Solar Dach"


def test_menueschritt_fuer_jede_quelle(flow):
    optionen = flow.WindhagerOptionsFlow()

    assert callable(optionen.async_step_quellen_0)
    assert callable(optionen.async_step_bearbeiten_7)
    for unbekannt in ("async_step_quellen_x", "async_step_bearbeiten_", "async_step_quelle_0"):
        with pytest.raises(AttributeError):
            getattr(optionen, unbekannt)


def test_eine_neue_quelle_kommt_an_die_liste(flow):
    optionen = flow.WindhagerOptionsFlow()

    neue, fehler = optionen._quelle_uebernehmen(
        [SOLAR],
        {},
        {
            "name": "Heizstab",
            "art": "heizstab",
            "bedingung_art": "zustand",
            "quelle": "switch.heizstab",
        },
    )

    assert fehler == {}
    assert [q["id"] for q in neue] == ["q1", "q2"]
    assert neue[1]["bedingung"] == {"art": "zustand", "quelle": "switch.heizstab"}


def test_eine_geaenderte_quelle_behaelt_ihre_kennung(flow):
    optionen = flow.WindhagerOptionsFlow()

    neue, fehler = optionen._quelle_uebernehmen(
        [SOLAR],
        SOLAR,
        {
            "name": "Solar Dach",
            "art": "solar",
            "bedingung_art": "schwelle",
            "quelle": "sensor.kollektor",
            "ein": 60,
            "aus": 50,
        },
    )

    assert fehler == {}
    assert len(neue) == 1
    assert neue[0]["id"] == "q1"
    assert neue[0]["name"] == "Solar Dach"
    assert neue[0]["bedingung"]["aus"] == 50


def test_entfernen_nimmt_nur_die_gewaehlte_quelle(flow):
    optionen = flow.WindhagerOptionsFlow()
    zweite = {**SOLAR, "id": "q2", "name": "Heizstab"}

    neue, fehler = optionen._quelle_uebernehmen([SOLAR, zweite], zweite, {"entfernen": True})

    assert fehler == {}
    assert [q["id"] for q in neue] == ["q1"]


def test_ohne_namen_bleibt_die_liste_stehen(flow):
    optionen = flow.WindhagerOptionsFlow()

    neue, fehler = optionen._quelle_uebernehmen(
        [SOLAR],
        {},
        {"name": "  ", "art": "solar", "bedingung_art": "zustand", "quelle": "switch.x"},
    )

    assert fehler == {"name": "name_fehlt"}
    assert neue == [SOLAR]


def test_eine_unvollstaendige_eingabe_wird_gemeldet(flow):
    """Ohne Einschaltwert lässt sich eine Schwelle nicht auswerten."""
    optionen = flow.WindhagerOptionsFlow()

    neue, fehler = optionen._quelle_uebernehmen(
        [], {}, {"name": "Solar", "art": "solar", "bedingung_art": "schwelle", "quelle": "sensor.k"}
    )

    assert fehler == {"base": "bedingung_unvollstaendig"}
    assert neue == []
