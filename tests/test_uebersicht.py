"""Übersicht des Dashboards: je Anlage Schaubild und Karten nach Rolle, Kopfzeile mit Badges."""

from __future__ import annotations

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def uebersicht():
    from custom_components.heatnexus.dashboard import uebersicht as modul

    return modul


@pytest.fixture(scope="module")
def badges():
    from custom_components.heatnexus.dashboard import badges as modul

    return modul


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
        "adresse": None,
        "optionen": {},
        "wert": 70.0,
        **rest,
    }


PHASEN = {0: "Brenner gesperrt", 6: "Zündphase", 8: "Modulation", 17: "Ausbrand"}
VORRAT = {
    0: "Fehler Vorratsbehälter",
    1: "Vorratsbehälter leer",
    2: "Vorratsbehälter teilgefüllt",
    3: "Vorratsbehälter voll",
}


def _kessel(name: str = "PuroWIN", kennung: str = "kessel0123456789", p: str = "k") -> dict:
    return {
        "name": name,
        "id": kennung,
        "fct_type": 25,
        "rang": 10,
        "entitaeten": [
            _e(f"sensor.{p}_phase", "Betriebsphase", schluessel="operating_phase", adresse="2/1")
            | {"optionen": PHASEN},
            _e(f"sensor.{p}_ist", "Kesseltemperatur Ist", schluessel="boiler_temperature"),
            _e(f"sensor.{p}_leistung", "Kesselleistung", schluessel="boiler_power"),
            _e(f"sensor.{p}_abgas", "Abgastemperatur", schluessel="flue_gas_temperature"),
            _e(f"sensor.{p}_kammer", "Brennkammer", schluessel="combustion_chamber_temperature"),
            _e(f"sensor.{p}_starts", "Brennerstarts", schluessel="burner_starts"),
            _e(f"sensor.{p}_stunden", "Betriebsstunden", schluessel="operating_hours"),
            _e(f"sensor.{p}_asche", "Laufzeit bis Asche", schluessel="maintenance_ash_hours"),
            _e(f"sensor.{p}_vorrat", "Vorratsbehälter", schluessel="fuel_storage_status")
            | {"optionen": VORRAT},
            _e(f"button.{p}_abfragen", "Werte jetzt abfragen"),
            _e(f"sensor.{p}_text", "Meldung", kategorie="diagnostic", meldungsart="fe01text"),
            _e(
                f"binary_sensor.{p}_stoerung",
                "Störung",
                kategorie="diagnostic",
                meldungsart="fe01stoerung",
            ),
        ],
    }


def _puffer() -> dict:
    return {
        "name": "Puffer",
        "id": "puffer0123456789",
        "fct_type": 16,
        "rang": 20,
        "entitaeten": [
            _e("sensor.puffer_oben", "Puffer oben", schluessel="buffer_top"),
            _e("sensor.puffer_unten", "Puffer unten", schluessel="buffer_bottom"),
            _e("sensor.puffer_pumpe", "Pufferladepumpe", schluessel="buffer_charge_pump"),
            _e("sensor.puffer_kessel", "Kesseltemperatur", schluessel="boiler_temperature"),
        ],
    }


def _heizkreis(kennung: str = "hk1", name: str = "Heizkreis 1", ww: bool = False) -> dict:
    werte = [
        _e(f"climate.{kennung}", name),
        _e(f"sensor.{kennung}_vorlauf", "Vorlauf Ist", schluessel="flow_temperature"),
        _e(f"sensor.{kennung}_soll", "Vorlauf Soll", schluessel="flow_temperature_target"),
        _e(f"sensor.{kennung}_raum", "Raum", schluessel="room_temperature", hat_wert=False),
        _e(f"sensor.{kennung}_mischer", "Mischer", schluessel="mixer_position"),
        _e(f"binary_sensor.{kennung}_pumpe", "Pumpe", schluessel="circuit_pump"),
    ]
    if ww:
        werte.append(_e(f"sensor.{kennung}_ww", "Warmwasser", schluessel="dhw_temperature"))
    return {
        "name": name,
        "id": f"{kennung}0123456789",
        "fct_type": 14,
        "rang": 30,
        "entitaeten": werte,
    }


def _warmwasser() -> dict:
    return {
        "name": "Speicher",
        "id": "wasser0123456789",
        "fct_type": 2,
        "rang": 42,
        "entitaeten": [
            _e("sensor.ww_ist", "WW Ist", schluessel="dhw_temperature"),
            _e("sensor.ww_soll", "WW Soll", schluessel="dhw_temperature_target"),
            _e("binary_sensor.ww_lade", "Ladepumpe", schluessel="dhw_charge_pump"),
            _e("binary_sensor.ww_zirk", "Zirkulation", schluessel="dhw_circulation_pump"),
        ],
    }


def _zsp() -> dict:
    return {
        "name": "ZSP",
        "id": "zsp00123456789",
        "fct_type": 20,
        "rang": 50,
        "entitaeten": [
            _e("sensor.zsp_kessel", "Kesseltemperatur", schluessel="boiler_temperature")
        ],
    }


def _anlage(*teile: dict, name: str = "Kesselhaus", kennung: str = "anlage0123456789") -> dict:
    return {"id": kennung, "name": name, "teile": list(teile)}


def _abschnitt(seite: dict, titel: str) -> list[dict]:
    return next(s["cards"] for s in seite["sections"] if s["cards"][0].get("heading") == titel)


def _typen(karten: list[dict]) -> list[str]:
    return [str(k["type"]).removeprefix("custom:heatnexus-") for k in karten]


def _zwei_anlagen() -> list[dict]:
    return [
        _anlage(_heizkreis(ww=True), _zsp(), _warmwasser(), _puffer(), _kessel()),
        _anlage(
            _kessel("BioWIN", "bio00123456789", "b"), name="Werkstatt", kennung="werkst0123456789"
        ),
    ]


def test_karten_folgen_der_rolle(uebersicht):
    seite = uebersicht.uebersicht(_zwei_anlagen(), als_karte=True, badges=[])
    karten = _abschnitt(seite, "Kesselhaus")
    assert _typen(karten) == [
        "heading",
        "schaubild",
        "leitwert",
        "kennwerte",
        "puffer",
        "tile",
        "kennwerte",
        "kennwerte",
    ]
    # Tasten und Kernwert-Kacheln der bisherigen Übersicht entfallen.
    assert "button.k_abfragen" not in str(karten)


def test_ueberschrift_fuehrt_zur_anlage_und_das_bild_steht_ohne_liste(uebersicht):
    karten = _abschnitt(uebersicht.uebersicht(_zwei_anlagen(), True, []), "Kesselhaus")
    kopf, bild = karten[0], karten[1]
    assert kopf["icon"] == "mdi:fire"
    assert kopf["tap_action"]["navigation_path"] == "/heatnexus/anlage-anlage01"
    assert bild["liste"] == "aus" and "zusatzwerte" not in bild
    assert bild["grid_options"] == {"columns": 12, "rows": "auto"}


def test_ohne_kartenmodul_steht_die_zeichnung(uebersicht):
    karten = _abschnitt(uebersicht.uebersicht(_zwei_anlagen(), False, []), "Kesselhaus")
    assert karten[1]["type"] == "picture-elements"


def test_leitwert_des_kessels(uebersicht):
    karten = _abschnitt(uebersicht.uebersicht(_zwei_anlagen(), True, []), "Kesselhaus")
    leitwert = karten[2]
    assert leitwert["ueberschrift"] == "PuroWIN"
    assert (leitwert["zustand"], leitwert["gross"]) == ("sensor.k_phase", "sensor.k_ist")
    assert leitwert["gross_name"] == "Kessel"
    # Hervorgehoben wird ein laufender Brenner, erkannt am Zahlencode der Phase.
    assert leitwert["aktiv"] == ["Zündphase", "Modulation", "Ausbrand"]
    assert [(n["name"], n["entity"]) for n in leitwert["neben"]] == [
        ("Leistung", "sensor.k_leistung"),
        ("Abgas", "sensor.k_abgas"),
    ]


def test_kennwerte_des_kessels_mit_warnschwelle(uebersicht):
    karten = _abschnitt(uebersicht.uebersicht(_zwei_anlagen(), True, []), "Kesselhaus")
    werte = karten[3]["werte"]
    assert [w["name"] for w in werte] == [
        "Brennkammer",
        "Brennerstarts",
        "Betriebsstunden",
        "Asche",
    ]
    assert werte[-1]["warnung_unter"] == 20


def test_puffer_mit_fuehlern_und_ladepumpe(uebersicht):
    puffer = _abschnitt(uebersicht.uebersicht(_zwei_anlagen(), True, []), "Kesselhaus")[4]
    assert (puffer["titel"], puffer["oben"], puffer["mitte"], puffer["unten"]) == (
        "Puffer",
        "sensor.puffer_oben",
        None,
        "sensor.puffer_unten",
    )
    assert puffer["neben"] == [{"name": "Ladepumpe", "entity": "sensor.puffer_pumpe"}]


def test_heizkreis_mit_programmauswahl_und_kennwerten(uebersicht):
    karten = _abschnitt(uebersicht.uebersicht(_zwei_anlagen(), True, []), "Kesselhaus")
    kachel, werte = karten[5], karten[6]["werte"]
    assert kachel["entity"] == "climate.hk1"
    assert kachel["features"] == [{"type": "climate-preset-modes", "style": "dropdown"}]
    # Ohne Raumfühler steht kein Raumwert da.
    assert [w["name"] for w in werte] == [
        "Vorlauf",
        "Vorlauf Soll",
        "Mischer",
        "Pumpe",
        "Warmwasser",
    ]
    pumpe = werte[3]
    assert (pumpe["art"], pumpe["an"], pumpe["aus"]) == ("schalter", "läuft", "aus")


def test_warmwasser_mit_eigenem_titel(uebersicht):
    wasser = _abschnitt(uebersicht.uebersicht(_zwei_anlagen(), True, []), "Kesselhaus")[7]
    assert wasser["titel"] == "Speicher"
    assert [w["name"] for w in wasser["werte"]] == [
        "Warmwasser",
        "Soll",
        "Ladepumpe",
        "Zirkulation",
    ]


def _ohne_wert(teil: dict) -> dict:
    return {**teil, "entitaeten": [{**e, "hat_wert": False} for e in teil["entitaeten"]]}


def test_kessel_ohne_aktuelle_werte_behaelt_seine_karte(uebersicht):
    anlage = _anlage(_ohne_wert(_kessel()))
    karten = _abschnitt(uebersicht.uebersicht([anlage], True, []), "Kesselhaus")
    [leitwert] = [k for k in karten if k["type"] == "custom:heatnexus-leitwert"]
    assert (leitwert["zustand"], leitwert["gross"]) == ("sensor.k_phase", "sensor.k_ist")


def test_puffer_mit_unbekanntem_oberem_fuehler_behaelt_seine_karte(uebersicht):
    puffer = _puffer()
    puffer["entitaeten"][0]["hat_wert"] = False
    karten = _abschnitt(uebersicht.uebersicht([_anlage(puffer)], True, []), "Kesselhaus")
    [karte] = [k for k in karten if k["type"] == "custom:heatnexus-puffer"]
    assert (karte["oben"], karte["unten"]) == ("sensor.puffer_oben", "sensor.puffer_unten")


def test_warmwasser_ohne_aktuelle_werte_behaelt_seine_karte(uebersicht):
    anlage = _anlage(_ohne_wert(_warmwasser()))
    karten = _abschnitt(uebersicht.uebersicht([anlage], True, []), "Kesselhaus")
    [wasser] = [k for k in karten if k.get("titel") == "Speicher"]
    assert [w["entity"] for w in wasser["werte"]] == ["sensor.ww_ist"]


def test_unter_gleichen_schluesseln_gewinnt_die_entitaet_mit_wert():
    from custom_components.heatnexus.dashboard import kacheln

    leer = _e("sensor.alt", "Alt", schluessel="boiler_temperature", hat_wert=False)
    voll = _e("sensor.neu", "Neu", schluessel="boiler_temperature")
    teil = {"entitaeten": [leer, voll]}
    assert kacheln.entitaeten_je_schluessel(teil)["boiler_temperature"] is voll
    teil = {"entitaeten": [leer, {**voll, "hat_wert": False}]}
    assert kacheln.entitaeten_je_schluessel(teil)["boiler_temperature"] is leer


# ---------------------------------------------------------------------------
# Kopfzeile
# ---------------------------------------------------------------------------
def test_badges_der_uebersicht(badges):
    zwei = _anlage(
        _kessel(),
        _kessel("LogWIN", "log00123456789", "l"),
        name="Werkstatt",
        kennung="werkst0123456789",
    )
    liste = badges.uebersicht_anlagenbadges([_anlage(_kessel(p="a")), zwei])
    phasen = [b for b in liste if b.get("icon") == "mdi:fire"]
    assert [b["name"] for b in phasen] == [
        "Kesselhaus",
        "Werkstatt · PuroWIN",
        "Werkstatt · LogWIN",
    ]
    assert all(b["color"] == "deep-orange" and b["show_state"] for b in phasen)
    # Phasen zuerst, dann Hinweise je Anlage, der Vorrat zuletzt.
    assert liste[:3] == phasen
    [asche] = [b for b in liste if b["entity"] == "sensor.a_asche"]
    assert asche["name"] == "Kesselhaus · Asche" and asche["color"] == "orange"
    assert asche["visibility"][0]["below"] == 50
    [stoerung] = [b for b in liste if b["entity"] == "binary_sensor.a_stoerung"]
    assert stoerung["color"] == "red" and stoerung["visibility"][0]["state"] == "on"
    vorraete = [b for b in liste if b.get("icon") == "mdi:silo"]
    assert liste[-len(vorraete) :] == vorraete
    assert vorraete[0]["name"] == "Kesselhaus · Vorrat"
    assert vorraete[0]["visibility"] == [
        {
            "condition": "state",
            "entity": "sensor.a_vorrat",
            "state": ["Fehler Vorratsbehälter", "Vorratsbehälter leer"],
        }
    ]


def test_phase_ohne_aktuellen_wert_bleibt_in_der_kopfzeile(badges):
    liste = badges.uebersicht_anlagenbadges([_anlage(_ohne_wert(_kessel()))])
    assert [b["entity"] for b in liste if b.get("icon") == "mdi:fire"] == ["sensor.k_phase"]


def test_vorrat_ohne_auswahltexte_bleibt_ohne_badge(badges):
    kessel = _kessel()
    for e in kessel["entitaeten"]:
        if e["schluessel"] == "fuel_storage_status":
            e["optionen"] = {}
    liste = badges.uebersicht_anlagenbadges([_anlage(kessel), _anlage(_puffer(), name="B")])
    assert not [b for b in liste if b.get("icon") == "mdi:silo"]


def test_puffer_und_vorlauf_sind_keine_badges(badges):
    liste = badges.uebersicht_anlagenbadges(_zwei_anlagen())
    assert not {"sensor.puffer_oben", "sensor.hk1_vorlauf", "sensor.ww_ist"} & {
        b["entity"] for b in liste
    }


# ---------------------------------------------------------------------------
# Sprache
# ---------------------------------------------------------------------------
BESCHRIFTUNGEN = (
    "name",
    "gross_name",
    "name_oben",
    "name_mitte",
    "name_unten",
    "an",
    "aus",
    "heading",
    "titel_liste",
)


def _beschriftungen(wert, schluessel=None) -> set[str]:
    if isinstance(wert, dict):
        return {t for k, v in wert.items() for t in _beschriftungen(v, k)}
    if isinstance(wert, list):
        return {t for v in wert for t in _beschriftungen(v, schluessel)}
    return {wert} if isinstance(wert, str) and schluessel in BESCHRIFTUNGEN else set()


def _anlagenteil_namen(anlagen: list[dict]) -> set[str]:
    return {a["name"] for a in anlagen} | {t["name"] for a in anlagen for t in a["teile"]}


@pytest.mark.parametrize("sprache", ["en", "nl"])
def test_in_fremder_sprache_bleibt_keine_beschriftung_deutsch(uebersicht, sprache):
    from custom_components.heatnexus.texte import Woerterbuch

    anlagen = _zwei_anlagen()
    deutsch = Woerterbuch("de")
    fremd = Woerterbuch(sprache)
    vorlage = uebersicht.uebersicht(anlagen, True, [], deutsch, [deutsch, deutsch])
    seite = uebersicht.uebersicht(anlagen, True, [], fremd, [fremd, fremd])
    eigene = _anlagenteil_namen(anlagen)
    deutsche = _beschriftungen(vorlage) - eigene
    reste = sorted(_beschriftungen(seite) & deutsche)
    assert deutsche and not reste, f"{sprache}: noch deutsch: {reste}"
    assert seite["title"] == fremd("Übersicht")


def test_jede_anlage_in_ihrer_sprache_der_rahmen_gemeinsam(uebersicht):
    from custom_components.heatnexus.texte import Woerterbuch

    deutsch, niederlaendisch = Woerterbuch("de"), Woerterbuch("nl")
    seite = uebersicht.uebersicht(_zwei_anlagen(), True, [], deutsch, [deutsch, niederlaendisch])
    assert seite["title"] == "Übersicht"
    kesselhaus = _beschriftungen(_abschnitt(seite, "Kesselhaus"))
    werkstatt = _beschriftungen(_abschnitt(seite, "Werkstatt"))
    assert {"Kessel", "Leistung"} <= kesselhaus
    assert {niederlaendisch("Kessel"), niederlaendisch("Leistung")} <= werkstatt
    assert not {"Kessel", "Leistung"} & werkstatt


async def test_das_dashboard_baut_die_uebersicht_je_anlage_in_ihrer_sprache(hass, monkeypatch):
    from custom_components.heatnexus import dashboard, texte

    hass.config.language = "de"
    monkeypatch.setattr(
        texte,
        "woerterbuch_des_eintrags",
        lambda _hass, eintrag: texte.Woerterbuch("nl" if eintrag == "nl" else "de"),
    )
    kesselhaus, werkstatt = _zwei_anlagen()
    werkstatt["eintrag"] = "nl"
    monkeypatch.setattr(dashboard, "anlagen_lesen", lambda _hass: [kesselhaus, werkstatt])
    hass.data["heatnexus_karte_js"] = True

    [seite, *_] = dashboard.dashboard_konfiguration(hass)["views"]

    assert seite["path"] == "uebersicht" and seite["title"] == "Übersicht"
    werkstatt_texte = _beschriftungen(_abschnitt(seite, "Werkstatt"))
    assert texte.Woerterbuch("nl")("Kessel") in werkstatt_texte
    assert "Kessel" in _beschriftungen(_abschnitt(seite, "Kesselhaus"))
    assert [b["name"] for b in seite["badges"] if b.get("icon") == "mdi:fire"] == [
        "Kesselhaus",
        "Werkstatt",
    ]
