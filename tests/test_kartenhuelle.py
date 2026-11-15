"""Die Karten über ein Update hinweg: Hülle unter festem Namen, Umsetzung je Fassung."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

PAKET = Path(__file__).resolve().parents[1] / "custom_components" / "heatnexus"
FRONTEND = PAKET / "frontend"
DURCHLAUF = Path(__file__).resolve().parent / "js" / "kartenhuelle-durchlauf.mjs"
NAMEN = ["heatnexus-schaubild", "heatnexus-leitwert", "heatnexus-kennwerte", "heatnexus-puffer"]
KARTE = "heatnexus-schaubild-karte.js"


@pytest.fixture(scope="module")
def bilanz(tmp_path_factory) -> dict:
    if shutil.which("node") is None:
        pytest.skip("node nicht vorhanden")
    seite = tmp_path_factory.mktemp("seite")
    # Zwei Fassungen nebeneinander, wie der Server sie unter ihrem Pfad anbietet.
    for fassung in ("a", "b"):
        shutil.copytree(FRONTEND, seite / f"heatnexus-karte-{fassung}")
    # Fassung b zeichnet erkennbar anders: Ein fehlender Wert steht als Wort da.
    kacheln = seite / "heatnexus-karte-b" / "heatnexus-kacheln.js"
    quelle = kacheln.read_text(encoding="utf-8")
    assert 'const LEER = "–";' in quelle
    kacheln.write_text(quelle.replace('const LEER = "–";', 'const LEER = "neu";'), encoding="utf-8")
    lauf = subprocess.run(
        [
            "node",
            str(DURCHLAUF),
            (seite / "heatnexus-karte-a" / KARTE).as_uri(),
            (seite / "heatnexus-karte-b" / KARTE).as_uri(),
            (seite / "heatnexus-karte-c" / KARTE).as_uri(),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr
    return json.loads(lauf.stdout)


def test_die_fassung_steht_im_ordner_des_moduls(bilanz):
    """Nur der Ordner einer Fassung zählt; ein Arbeitsordner mit ähnlichem Namen nicht."""
    assert bilanz["fassungAus"] == ["1-16-0-ab12cd34", "1-16-0-ab12cd34", None, None]


def test_unter_dem_festen_namen_steht_eine_huelle(bilanz):
    assert bilanz["festeNamen"] == NAMEN
    assert bilanz["umsetzungenA"] == NAMEN
    assert bilanz["huelleIstNichtDieUmsetzung"] is True
    assert bilanz["inKartenauswahl"] == NAMEN


def test_die_huelle_reicht_editor_und_erstkonfiguration_durch(bilanz):
    assert bilanz["stub"] == "custom:heatnexus-puffer"
    assert bilanz["formular"] is True
    assert bilanz["editorA"] == "heatnexus-schaubild-editor-a"
    assert bilanz["editorFormularFehlt"] is True


def test_die_huelle_zeichnet_mit_der_geladenen_fassung(bilanz):
    start = bilanz["start"]
    assert start["innen"] == [
        "heatnexus-puffer-a",
        "heatnexus-kennwerte-a",
        "heatnexus-schaubild-a",
    ]
    assert "68,0 °C" in start["text"] and "–" in start["text"]
    assert start["hassGereicht"] is True and start["layoutGereicht"] == "grid"
    assert start["hinweis"] == 0
    assert bilanz["groesseOhneHass"] == [2, 12, 6]


def test_alle_huellen_fragen_gemeinsam_einmal(bilanz):
    assert bilanz["start"]["fragen"] == 1


def test_waehrend_home_assistant_startet_wird_nicht_gefragt(bilanz):
    assert bilanz["startetNochKeineFrage"] == 1


def test_eine_neue_fassung_des_servers_wird_nachgeladen(bilanz):
    nach = bilanz["nachWechsel"]
    assert bilanz["getauscht"] is True
    assert nach["innen"] == ["heatnexus-puffer-b", "heatnexus-kennwerte-b", "heatnexus-schaubild-b"]
    assert "68,0 °C" in nach["text"] and "neu" in nach["text"]
    assert nach["hassGereicht"] is True and nach["layoutGereicht"] == "grid"
    assert nach["schaubildNeuGefragt"] is True
    assert nach["hinweis"] == 0 and nach["warnungen"] == 0


def test_die_alte_umsetzung_verlaesst_die_huelle(bilanz):
    """Stil, Platz für den Hinweis und genau ein inneres Element."""
    assert bilanz["nachWechsel"]["kinder"] == [3, 3, 3]


def test_nach_dem_wechsel_wird_nicht_erneut_gefragt(bilanz):
    assert bilanz["nachWechsel"]["fragen"] == 2


def test_neue_und_wieder_eingehaengte_karten_folgen_der_neuen_fassung(bilanz):
    nach = bilanz["nachWechsel"]
    assert nach["neueKarte"] == "heatnexus-leitwert-b"
    assert nach["abgehaengtVorher"] == "heatnexus-puffer-a"
    assert nach["abgehaengtNachher"] == "heatnexus-puffer-b"
    assert nach["editor"] == "heatnexus-schaubild-editor-b"


def test_ein_gescheitertes_nachladen_zeigt_den_hinweis(bilanz):
    fehlschlag = bilanz["fehlschlag"]
    assert bilanz["hinweisErschienen"] is True
    assert fehlschlag["text"] == "HeatNexus wurde aktualisiert.Neu laden"
    assert fehlschlag["taste"] == "button" and fehlschlag["neuGeladen"] == 1
    assert fehlschlag["neueKarteMitHinweis"] == 2
    # Die geladene Fassung zeichnet weiter.
    assert fehlschlag["innen"] == [
        "heatnexus-puffer-b",
        "heatnexus-kennwerte-b",
        "heatnexus-schaubild-b",
    ]


def test_ein_gescheitertes_modul_wird_nicht_erneut_geladen(bilanz):
    assert bilanz["fehlschlag"]["erneutGefragt"] == 1
    assert bilanz["fehlschlag"]["warnungen"] == 1


def test_der_hinweis_verschwindet_mit_einer_ladbaren_fassung(bilanz):
    assert bilanz["hinweisWieder_weg"] is True


def test_ein_neuerer_vertrag_fuehrt_zum_hinweis_statt_zum_laden(bilanz):
    assert bilanz["vertrag"] == {"hinweis": True, "innen": "heatnexus-puffer-b", "warnungen": 1}


def test_eine_schon_geladene_fassung_gilt_ohne_neues_laden(bilanz):
    assert bilanz["zurueck"] == {"getauscht": True, "hinweis": 0}


def test_eine_abgelehnte_frage_wird_nach_einer_wartezeit_wiederholt(bilanz):
    assert bilanz["startphase"] == {"sofort": 1, "nachWartezeit": True, "fragen": 2}


def test_jeder_elementname_wird_genau_einmal_vergeben(bilanz):
    """Auch dann, wenn dieselbe Fassung über eine zweite Adresse geladen wird."""
    assert bilanz["zweiteAdresse"] is True
    erwartet = {f"{name}{zusatz}" for name in NAMEN for zusatz in ("", "-a", "-b")}
    erwartet |= {"heatnexus-schaubild-editor-a", "heatnexus-schaubild-editor-b"}
    assert bilanz["anmeldungen"] == dict.fromkeys(sorted(erwartet), 1)


def test_server_und_huelle_nennen_denselben_vertrag():
    """`const.KARTE_VERTRAG` und `VERTRAG` der Hülle gehören zusammen."""
    huelle = (FRONTEND / "kartenhuelle.js").read_text(encoding="utf-8")
    server = (PAKET / "const.py").read_text(encoding="utf-8")
    im_browser = re.search(r"^const VERTRAG = (\d+);", huelle, re.M).group(1)
    am_server = re.search(r"^KARTE_VERTRAG = (\d+)$", server, re.M).group(1)
    assert im_browser == am_server


@pytest.mark.parametrize("sprache", ["en", "nl"])
def test_der_hinweis_steht_in_jeder_sprache(sprache):
    woerter = json.loads((PAKET / "sprachen" / f"{sprache}.json").read_text(encoding="utf-8"))
    assert {"HeatNexus wurde aktualisiert.", "Neu laden"} <= set(woerter)
