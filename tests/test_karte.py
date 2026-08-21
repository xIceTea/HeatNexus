"""Nutzdaten des Schaubilds – gemeinsame Grundlage von Oberfläche und Karte."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from .conftest import load_standalone

KARTE_JS = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "heatnexus"
    / "frontend"
    / "heatnexus-schaubild-karte.js"
)
DURCHLAUF = Path(__file__).resolve().parent / "js" / "karte-durchlauf.mjs"


@pytest.fixture(scope="module")
def schema():
    """Das Modul kommt ohne Home Assistant aus und wird direkt geladen."""
    return load_standalone("schema")


def _teil(name: str, fct: int, werte: list[tuple[str, str]]) -> dict:
    return {
        "name": name,
        "fct_type": fct,
        "entitaeten": [
            {
                "entity_id": eid,
                "name": n,
                "hat_wert": True,
                "bereich": eid.split(".")[0],
            }
            for eid, n in werte
        ],
    }


@pytest.fixture
def anlage():
    return {
        "id": "anlage-1",
        "name": "Heizhaus",
        "teile": [
            _teil(
                "PuroWIN",
                25,
                [
                    ("sensor.kessel_ist", "Kesseltemperatur Ist"),
                    ("sensor.leistung", "Kesselleistung"),
                ],
            ),
            _teil(
                "B-PLMi PUFFER",
                16,
                [
                    ("sensor.tpe", "Puffer oben Temperatur (TPE)"),
                    ("sensor.tpa", "Puffer unten Temperatur (TPA)"),
                ],
            ),
        ],
    }


FELDER = (
    "schema_svg",
    "schema_farben",
    "schema_werte",
    "schema_pumpen",
    "schema_leitungen",
    "schema_brenner",
    "schema_anforderung",
    "schema_mischer",
    "schema_heizkoerper",
    "schema_schichtung",
    "schema_lampen",
    "schema_speicher",
)


def test_nutzdaten_fuehren_alle_felder(schema, anlage):
    """Die Karte bekommt dieselben Felder wie die Oberfläche."""
    nutzdaten = schema.schaubild_nutzdaten(anlage)
    for feld in FELDER:
        assert feld in nutzdaten, feld


def test_die_zeichnung_geht_einmal_hinaus(schema, anlage):
    """Welcher Farbsatz gilt, weiß erst der Browser – er stellt selbst um."""
    nutzdaten = schema.schaubild_nutzdaten(anlage)
    assert nutzdaten["schema_svg"].startswith("<svg")
    assert set(nutzdaten["schema_farben"]) == {"hell", "terrakotta", "petrol", "pflaume"}


def test_werte_tragen_entitaet_und_lage(schema, anlage):
    """Ohne Lage kann die Karte die Beschriftung nicht setzen."""
    werte = schema.schaubild_nutzdaten(anlage)["schema_werte"]
    assert werte
    for eintrag in werte:
        assert eintrag["entity"]
        assert eintrag["left"].endswith("%")
        assert eintrag["top"].endswith("%")


def test_kartendaten_nennen_jede_anlage(schema, anlage):
    """Die Karte wählt ihre Anlage über die Kennung, nicht über die Reihenfolge."""
    zweite = {"id": "anlage-2", "name": "Wohnhaus", "teile": anlage["teile"]}
    daten = schema.schaubild_daten([anlage, zweite])
    assert [a["id"] for a in daten] == ["anlage-1", "anlage-2"]
    assert [a["name"] for a in daten] == ["Heizhaus", "Wohnhaus"]
    assert all(a["schema_svg"] for a in daten)


def test_kartendaten_ohne_anlage_bleiben_leer(schema):
    assert schema.schaubild_daten([]) == []


def test_anlage_ohne_messwert_bleibt_leer(schema):
    """Ein Bild aus leeren Kästen hilft niemandem."""
    leer = {"id": "anlage-2", "name": "Wohnhaus", "teile": [_teil("PuroWIN", 25, [])]}
    nutzdaten = schema.schaubild_nutzdaten(leer)
    assert nutzdaten["schema_svg"] is None
    assert nutzdaten["schema_werte"] == []
    assert nutzdaten["schema_leitungen"] is None


# ---------------------------------------------------------------------------
# Die Karte im Browser
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def durchlauf(schema, tmp_path_factory):
    """Die Karte einmal in Node aufbauen und die Bilanz zurückgeben."""
    if shutil.which("node") is None:
        pytest.skip("node nicht vorhanden")
    teile = [
        _teil(
            "PuroWIN",
            25,
            [("sensor.kessel", "Kesseltemperatur Ist"), ("sensor.leistung", "Kesselleistung")],
        ),
        _teil(
            "B-PLMi PUFFER",
            16,
            [
                ("sensor.tpe", "Puffer oben Temperatur (TPE)"),
                ("sensor.tpa", "Puffer unten Temperatur (TPA)"),
                ("switch.pufferladepumpe", "Pufferladepumpe"),
            ],
        ),
        _teil(
            "UML Heizkreis",
            14,
            [
                ("sensor.vorlauf", "Vorlauftemperatur Ist"),
                ("switch.heizkreispumpe", "Heizkreispumpe"),
                ("sensor.mischer", "Mischer Stellwert"),
            ],
        ),
    ]
    anlagen = schema.schaubild_daten(
        [
            {"id": "anlage-1", "name": "Heizhaus", "teile": teile},
            {"id": "anlage-2", "name": "Wohnhaus", "teile": teile},
        ]
    )
    daten = tmp_path_factory.mktemp("karte") / "anlagen.json"
    daten.write_text(json.dumps(anlagen), encoding="utf-8")
    ausgabe = subprocess.run(
        ["node", str(DURCHLAUF), KARTE_JS.as_uri(), str(daten)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert ausgabe.returncode == 0, ausgabe.stderr
    return json.loads(ausgabe.stdout)


def test_die_karte_meldet_sich_beim_laden_an(durchlauf):
    """Home Assistant wartet nicht: Das Element muss sofort dastehen."""
    assert durchlauf["sofortRegistriert"] is True
    assert durchlauf["inKartenauswahl"] is True


def test_die_karte_bringt_eine_erstkonfiguration_mit(durchlauf):
    assert durchlauf["stubHatTyp"] is True


def test_der_editor_stellt_die_anlagen_zur_auswahl(durchlauf):
    """Ein Textfeld zwang zum Abtippen und meldete bei jedem Buchstaben Unsinn."""
    assert durchlauf["editorElement"] == "heatnexus-schaubild-editor"
    assert durchlauf["editorFelder"] == [
        "anlage",
        "allgemein",
        "darstellung",
        "liste_ab",
        "eigene_ab",
        "zeilen_ab",
        "bild_ab",
    ]
    assert durchlauf["editorAnlagen"][1:] == ["Heizhaus", "Wohnhaus"]


def test_die_zeile_nennt_zuerst_den_datenpunkt(durchlauf):
    """Links der Datenpunkt, rechts der Wert, das Anlagenteil klein darunter."""
    assert durchlauf["nameLinks"] == "Kesseltemperatur Ist"
    assert durchlauf["teilAmWert"] == "PuroWIN"
    assert durchlauf["zeileMitSymbol"] is True


def test_der_alte_aufbau_bleibt_waehlbar(durchlauf):
    assert durchlauf["altTeilLinks"] == "PuroWIN"
    assert durchlauf["altNameAmWert"] == "Kesseltemperatur Ist"


def test_je_wert_eigener_name_und_abgewaehltes_anlagenteil(durchlauf):
    assert durchlauf["eigenerName"] == "Leistung oben"
    assert durchlauf["teilAbgewaehlt"] is True


def test_die_liste_nimmt_auch_fremde_entitaeten(durchlauf):
    """Was nicht von der Anlage kommt, behält Namen und Symbol aus dem Zustand."""
    assert durchlauf["zeilenAnzahl"] == 3
    assert durchlauf["fremdeEntitaet"] == "Solarertrag"


def test_das_anlagenteil_laesst_sich_selbst_beschriften(durchlauf):
    """Ein fremder Fühler hängt trotzdem an einem Anlagenteil."""
    assert durchlauf["eigeneBeschriftung"] == "Heizhaus"


def test_ueberschriften_und_pumpen_lassen_sich_abschalten(durchlauf):
    assert durchlauf["ueberschriften"] == ["Meine Werte"]
    assert durchlauf["ohnePumpenmarke"] is True


def test_einheit_farbe_und_klick_je_zeile(durchlauf):
    """Ohne Einheit bleibt die Zahl, ohne Klick bleibt die Detailansicht zu."""
    assert durchlauf["ohneEinheit"] == "68"
    assert durchlauf["ohneKlick"] is True
    assert durchlauf["symbolfarbe"] == "var(--red-color)"


def test_umsortieren_behaelt_die_eigenen_angaben(durchlauf):
    assert durchlauf["umsortiert"] == ["sensor.leistung", "sensor.kessel"]
    assert durchlauf["umsortiertName"] == "Leistung"


def test_zeichnung_je_anlagenteil_waehlbar(durchlauf):
    """Wer am Hackgutkessel die Pelletszeichnung will, bekommt sie."""
    assert durchlauf["zeichnungGefragt"] == "kessel-pellets"
    assert durchlauf["zeichenbareTeile"] == ["PuroWIN", "B-PLMi PUFFER", "UML Heizkreis"]
    assert durchlauf["zeichnungenZurWahl"] > 10


def test_mischer_laesst_sich_abwaehlen(durchlauf):
    assert durchlauf["ohneMischermarke"] is True


def test_groesse_kommt_ohne_hass_aus(durchlauf):
    """`getCardSize` und `getGridOptions` laufen vor dem ersten `hass`."""
    assert durchlauf["groesseOhneHass"] > 0
    # Volle Breite des Rasters: Auf halber Spur bleibt für die Werteliste
    # neben dem Bild nur eine schmale Spalte.
    assert durchlauf["rasterOhneHass"]["columns"] == 24
    assert durchlauf["rasterOhneHass"]["min_columns"] == 12
    assert durchlauf["rasterOhneHass"]["rows"] == "auto"


def test_die_karte_zeigt_das_schaubild(durchlauf):
    assert durchlauf["bildVorhanden"] is True
    assert durchlauf["bildAdresse"].startswith("data:image/svg+xml")


def test_die_ueberlagerungen_haengen_am_massstab_der_zeichnung(durchlauf):
    """Sonst bleibt die Schrift in der schmalen Vorschau so groß wie im Dashboard."""
    assert durchlauf["einheitGesetzt"] is True


def test_das_laufrad_ist_eine_eigene_zeichnung(durchlauf):
    """Der Kasten aus HTML trägt die Drehung, das SVG die Zeichnung."""
    assert durchlauf["laufradIstZeichnung"] is True


def test_die_schriftgroesse_der_marken_ist_einstellbar(durchlauf):
    """Ein Maßstab passt nicht jeder Kartenbreite; der Faktor gehört dem Nutzer."""
    assert durchlauf["schriftmass"] == "1.25"


def test_ein_unbekanntes_schriftmass_wird_abgewiesen(durchlauf):
    """Sonst stünde eine falsche Angabe still auf dem Normalmaß."""
    assert durchlauf["unbekanntesMassWirft"] is True


def test_die_gewaehlte_anlage_gilt(durchlauf):
    assert durchlauf["zweiteAnlageAnders"] is True


def test_ein_unbekannter_farbsatz_wird_abgewiesen(durchlauf):
    """Erst der Fehler lässt Home Assistant auf den YAML-Editor zurückfallen."""
    assert durchlauf["unbekannterSatzWirft"] is True


def test_ohne_anlage_steht_ein_hinweis(durchlauf):
    assert durchlauf["hinweisOhneAnlage"] is True


def test_die_bewegung_laesst_sich_abschalten(durchlauf):
    """Wer es ruhig will, behält trotzdem alle Zustände."""
    assert durchlauf["ohneAnimationRuhig"] is True
    assert durchlauf["mitAnimationBewegt"] is True


def test_die_stichleitungen_kehren_beim_entnehmen_um(durchlauf):
    """Beim Entladen verlässt die Wärme den Speicher oben, nicht andersherum."""
    assert durchlauf["senkrechteVorhanden"] > 0
    assert durchlauf["beimEntnehmenRueckwaerts"] is True
    assert durchlauf["beimLadenVorwaerts"] is True


def test_der_waermeerzeuger_stroemt_nach_oben(durchlauf):
    """Kaltes Wasser kommt von unten herauf, heißes verlässt den Kessel oben.

    Ein Verbraucher macht es umgekehrt: Bei ihm laufen beide Stichleitungen
    abwärts, von der Vorlaufleitung hinein und unten in den Rücklauf.
    """
    assert durchlauf["kesselImmerAufwaerts"] is True
    assert durchlauf["verbraucherAbwaerts"] is True


def test_die_ueberlagerungen_folgen_dem_farbsatz(durchlauf):
    """Mischer, Heizkörper und Schichtung liegen über dem Bild, nicht darin.

    Warm und kalt gehen mit dem Satz; Vor- und Rücklauf bleiben, wo sie sind.
    """
    assert durchlauf["grundfarbenMitgeliefert"] == 4
    assert durchlauf["stutzenVorhanden"] is True
    assert durchlauf["stutzenMitLeitungsfarben"] is True
    assert durchlauf["schichtungOhneDunkelwert"] is True


# ---------------------------------------------------------------------------
# Eigene Werteauswahl
# ---------------------------------------------------------------------------
def test_waehlbare_werte_nennen_was_die_anlage_fuehrt(schema, anlage):
    """Die Liste kommt aus der Erkennung, nicht aus einer gepflegten Tabelle."""
    teile = schema.waehlbare_werte(anlage["teile"])
    assert [t["titel"] for t in teile] == ["PuroWIN", "B-PLMi PUFFER"]
    kessel = teile[0]
    assert {w["entity"] for w in kessel["werte"]} == {"sensor.kessel_ist", "sensor.leistung"}
    assert all(w["name"] for w in kessel["werte"])
    assert kessel["id"]


def test_jeder_teil_nennt_seine_vorgabe(schema, anlage):
    """Ohne eigene Auswahl gilt, was das Schaubild bisher gezeigt hat."""
    teile = schema.waehlbare_werte(anlage["teile"])
    assert teile[0]["vorgabe"]
    assert set(teile[0]["vorgabe"]) <= {w["entity"] for w in teile[0]["werte"]}


def test_die_auswahl_bestimmt_die_beschriftungen(schema, anlage):
    """Gewählt heißt gezeichnet – und nichts anderes."""
    teile = schema.waehlbare_werte(anlage["teile"])
    auswahl = {teile[0]["id"]: ["sensor.leistung"]}
    bild = schema.anlagenschema(anlage["teile"], auswahl=auswahl)
    kessel = [e for e in bild["elements"] if e["entity"].startswith("sensor.kessel")]
    assert not kessel
    assert any(e["entity"] == "sensor.leistung" for e in bild["elements"])


def test_ein_abgewaehlter_anlagenteil_verschwindet(schema, anlage):
    teile = schema.waehlbare_werte(anlage["teile"])
    bild = schema.anlagenschema(anlage["teile"], teile_aus=[teile[1]["id"]])
    assert not any(e["entity"].startswith("sensor.tp") for e in bild["elements"])


def test_ohne_auswahl_bleibt_alles_wie_bisher(schema, anlage):
    """Der Gleichstand: Wer nichts einstellt, merkt von alledem nichts."""
    assert schema.anlagenschema(anlage["teile"]) == schema.anlagenschema(
        anlage["teile"], auswahl={}, teile_aus=[]
    )


def test_der_editor_gliedert_nach_anlagenteilen(durchlauf):
    """Überkategorien wie bei den Flusskarten: Abschnitt je Anlagenteil."""
    assert durchlauf["abschnitteJeTeil"] == ["PuroWIN", "B-PLMi PUFFER", "UML Heizkreis"]
    assert durchlauf["werteAuswaehlbar"] is True
    assert durchlauf["vorbelegt"] is True


def test_die_liste_zieht_aus_der_ganzen_anlage(durchlauf):
    """Die Liste behauptet nichts über Rohre – dort darf frei gewählt werden."""
    assert durchlauf["zusatzwerteVorrat"] >= 6


def test_alle_anlagen_stehen_zur_wahl(durchlauf):
    assert durchlauf["editorAnlagen"][0] == "Alle Anlagen"


def test_die_ladung_zaehlt_gegen_den_unteren_fuehler(durchlauf):
    """Im Nachlauf ist der obere Bereich wärmer als der Kessel – geladen wird trotzdem."""
    assert durchlauf["laedtImNachlauf"] is True


def test_ein_kalter_kessel_laedt_nicht(durchlauf):
    assert durchlauf["kalterKesselLaedtNicht"] is True
