"""Die Oberfläche einmal wirklich aufbauen, nicht nur laden.

**Der Anlass steht in `ordnung.js`.** Beim Schnitt der Panel-Datei in
ES-Module blieben zwei Zeitkonstanten ohne `export` zurück, während die
Oberfläche sie weiter benutzte. Laden ließ sich alles; erst beim Aufräumen
einer Rückmeldung flog ein `ReferenceError`, und „wird ausgeführt …" blieb am
Gerät für immer stehen. Ein Ladetest fängt so etwas nicht – nur ein Durchlauf.

Gefahren wird der Durchlauf in Node gegen eine schmale DOM-Attrappe
(`js/dom-attrappe.mjs`). Die Aufteilung kommt aus der echten Serverseite
(`panel/daten.py`), damit beide Seiten gegeneinander geprüft sind: Was Python
liefert, muss der Browser auch verarbeiten.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from .conftest import requires_ha

pytestmark = [
    requires_ha(),
    pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden"),
]

WURZEL = Path(__file__).resolve().parents[1]
PANEL_JS = WURZEL / "custom_components" / "heatnexus" / "frontend" / "heatnexus-panel.js"
DURCHLAUF = Path(__file__).parent / "js" / "oberflaeche-durchlauf.mjs"


def _entitaet(entity_id: str, name: str, **rest):
    eintrag = {
        "entity_id": entity_id,
        "name": name,
        "kategorie": None,
        "bereich": entity_id.split(".")[0],
        "hat_wert": True,
        "wert": 21.5,
        "text": "21.5",
        "state_class": None,
    }
    eintrag.update(rest)
    return eintrag


def _teil(name: str, fct_type: int, entitaeten: list):
    return {
        "name": name,
        "id": f"geraet_{name}",
        "anlage_id": "steuerung",
        "fct_type": fct_type,
        "rang": 0,
        "symbol": "mdi:fire",
        "entitaeten": entitaeten,
    }


@pytest.fixture(scope="module")
def aufteilung() -> dict:
    """Eine Anlage mit allem, was die Oberfläche zeichnen kann."""
    from custom_components.heatnexus import panel as modul

    kessel = _teil(
        "PuroWIN",
        25,
        [
            _entitaet("sensor.kesseltemperatur_ist", "Kesseltemperatur Ist"),
            _entitaet("sensor.betriebsphase", "Betriebsphase"),
            _entitaet("sensor.kesselleistung", "Kesselleistung"),
            _entitaet("sensor.vorratsbehaelter", "Vorratsbehälter"),
            _entitaet("sensor.laufzeit_asche", "Laufzeit bis Ascheentleerung"),
            _entitaet("sensor.betriebsstunden", "Betriebsstunden", state_class="total_increasing"),
            _entitaet("button.serviceausbrand", "Serviceausbrand"),
            _entitaet("button.lagerraumbefuellung", "Lagerraumbefüllung anfordern"),
            _entitaet("select.gewaehlter_brennstoff", "Gewählter Brennstoff"),
            _entitaet("switch.kaminkehrer", "Kaminkehrer"),
            _entitaet("sensor.meldung_klartext", "Meldung Klartext", kategorie="diagnostic"),
        ],
    )
    heizkreis = _teil(
        "UMLZ HEIZKREIS",
        14,
        [
            _entitaet("climate.umlz_heizkreis", "UMLZ HEIZKREIS"),
            _entitaet("sensor.aussentemperatur", "Außentemperatur"),
            _entitaet("sensor.raumtemperatur_ist", "Raumtemperatur Ist"),
            _entitaet("sensor.vorlauftemperatur_ist", "Vorlauftemperatur Ist"),
            _entitaet("sensor.warmwasser_ist", "Warmwasser Ist-Temperatur"),
            _entitaet("sensor.programm_1", "Programm 1"),
            _entitaet("sensor.ww_programm", "WW-Programm"),
            _entitaet("select.betriebswahl", "Betriebswahl"),
            _entitaet("number.behaglichkeitskorrektur", "Behaglichkeitskorrektur"),
            _entitaet("number.dauer", "Dauer"),
            _entitaet("number.temperatur", "Temperatur"),
            _entitaet("switch.ww_einmalladung", "WW Einmalladung"),
        ],
    )
    puffer = _teil(
        "B-PLMi PUFFER",
        16,
        [
            _entitaet("sensor.puffer_oben", "Puffer oben"),
            _entitaet("sensor.puffer_unten", "Puffer unten"),
            _entitaet("select.betriebswahl_puffer", "Betriebswahl"),
        ],
    )
    # Das Pumpen-/Relaismodul: Sein Leitwert ist die Wärmeanforderung, und die
    # gibt es an einer Anlage, die das Modul nur als Relais benutzt, nie.
    zsp = _teil(
        "ZSP-PWA",
        20,
        [
            _entitaet("sensor.analog_sollwert", "Analog-Sollwert", wert=0.0, text="0"),
            _entitaet("sensor.pumpendrehzahl", "Pumpendrehzahl"),
        ],
    )
    return {
        "anlagen": [
            modul._anlage_daten({"name": "Heizhaus", "teile": [kessel, heizkreis, puffer, zsp]})
        ],
        "uebersteuerung": {
            "eco": {"temperatur": 18, "dauer": 120},
            "comfort": {"temperatur": 22, "dauer": 180},
        },
        "aussentemperatur": "sensor.aussentemperatur",
    }


@pytest.fixture(scope="module")
def durchlauf(aufteilung, tmp_path_factory) -> dict:
    datei = tmp_path_factory.mktemp("oberflaeche") / "daten.json"
    datei.write_text(json.dumps(aufteilung), encoding="utf-8")
    ergebnis = subprocess.run(
        ["node", str(DURCHLAUF), str(PANEL_JS), str(datei)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert ergebnis.returncode == 0, (
        f"Die Oberfläche ist beim Aufbau gescheitert:\n{ergebnis.stderr[:2000]}"
    )
    return json.loads(ergebnis.stdout)


# ---------------------------------------------------------------------------
# Jeder Reiter muss sich aufbauen lassen
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "reiter", ["uebersicht", "steuerung", "wartung", "verlauf", "zeitprogramme"]
)
def test_jeder_reiter_baut_karten(durchlauf, reiter):
    """Ein leerer Reiter hieße: Die Aufteilung kommt im Browser nicht an."""
    assert durchlauf[reiter]["karten"] > 0, f"Reiter {reiter} bleibt leer"


def test_karten_haengen_am_zustand(durchlauf):
    """Ohne Bindungen stünden die Karten still, sobald sich ein Wert ändert."""
    assert durchlauf["uebersicht"]["bindungen"] > 0


def test_anordnen_gibt_jeder_karte_einen_griff(durchlauf):
    assert durchlauf["anordnen"]["griffe"] > 0


def test_ohne_waermeanforderung_verschwindet_die_zeile(durchlauf):
    """Das Pumpen-/Relaismodul steht nicht mit einem „–" in der Übersicht.

    Wo das Modul nur ein Relais schaltet, kommt nie eine Wärmeanforderung. Der
    Server markiert den Wert deshalb als „nur über null"; bis 1.5.0 reichte die
    Oberfläche die Markierung nicht durch und zeigte eine Zeile, die nie einen
    Wert bekam.
    """
    assert durchlauf["uebersicht"]["versteckteZeilen"] > 0


# ---------------------------------------------------------------------------
# Bedienen: übertragen, bestätigen, aufräumen
# ---------------------------------------------------------------------------
def test_der_dienst_wird_wirklich_gerufen(durchlauf):
    assert "climate.set_temperature" in durchlauf["bedienen"]["dienste"]


def test_die_rueckmeldung_durchlaeuft_ihre_drei_stufen(durchlauf):
    """Und räumt am Ende auf.

    Der letzte Schritt ist der, der am Gerät gefehlt hat: Ohne ihn bleibt
    „übernommen ✓" stehen, und die Karte zeigt nie wieder ihren Zustand.
    """
    bedienen = durchlauf["bedienen"]
    assert bedienen["waehrend"] == "wird ausgeführt …"
    assert bedienen["bestaetigt"] == "übernommen ✓"
    assert bedienen["aufgeraeumt"] == ""
