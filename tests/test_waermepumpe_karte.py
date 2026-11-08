"""Wärmepumpe: Karte mit Silentmode in der Steuerung."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from .conftest import requires_ha

WAERMEPUMPE_JS = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "heatnexus"
    / "frontend"
    / "teile"
    / "waermepumpe.js"
)


def _e(entity_id: str, name: str) -> dict:
    return {
        "entity_id": entity_id,
        "name": name,
        "bereich": entity_id.split(".")[0],
        "hat_wert": True,
        "schluessel": None,
        "kategorie": None,
    }


def _teil(name: str, fct: int, *entitaeten: dict) -> dict:
    return {"id": f"geraet-{name}", "name": name, "fct_type": fct, "entitaeten": list(entitaeten)}


@requires_ha()
def test_waermepumpe_mit_silentmode_bekommt_eine_karte():
    from custom_components.heatnexus.panel.steuerung import steuerung

    anlage = {
        "teile": [
            _teil(
                "AeroWIN",
                7,
                _e("select.silent", "Silentmode"),
                _e("number.faktor", "Silentmode Faktor"),
                _e("sensor.silent_programm", "Zeitprogramm Silentmode"),
                _e("sensor.cop", "COP aktuell"),
            ),
            _teil("BioWIN", 9, _e("sensor.kl", "Kesselleistung")),
        ]
    }

    karten = steuerung(anlage)["waermepumpen"]

    assert len(karten) == 1
    karte = karten[0]
    assert karte["id"] == "geraet-AeroWIN"
    assert karte["titel"] == "AeroWIN"
    assert karte["silentmode"] == "select.silent"
    assert karte["faktor"] == "number.faktor"
    assert karte["programm"] == "sensor.silent_programm"
    assert "Mode 2" in karte["silentmode_hilfe"]


@requires_ha()
def test_ohne_silentmode_keine_karte():
    from custom_components.heatnexus.panel.steuerung import steuerung

    anlage = {
        "teile": [
            # Nur als Sensor (ohne Schreibrecht) ist der Silentmode keine Bedienung.
            _teil("AeroWIN", 7, _e("sensor.silent", "Silentmode")),
            _teil("BioWIN", 9, _e("sensor.kl", "Kesselleistung")),
        ]
    }

    assert steuerung(anlage)["waermepumpen"] == []


@requires_ha()
def test_faktor_und_programm_sind_freiwillig():
    from custom_components.heatnexus.panel.steuerung import steuerung

    anlage = {"teile": [_teil("AeroWIN", 7, _e("select.silent", "Silentmode"))]}

    karte = steuerung(anlage)["waermepumpen"][0]

    assert karte["faktor"] is None
    assert karte["programm"] is None


TAEGLICH = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
# Blöcke wie aus `bloeckeLesen`: Zeiten in Minuten, 1 = Silentmode ein.
FENSTER = [
    ("kein Ein", [{"tage": TAEGLICH, "punkte": [{"zeit": 480, "wert": 0}]}], "kein Zeitfenster"),
    (
        "über Mitternacht",
        [{"tage": TAEGLICH, "punkte": [{"zeit": 360, "wert": 0}, {"zeit": 1320, "wert": 1}]}],
        "täglich 22:00–06:00",
    ),
    (
        "innerhalb des Tages",
        [{"tage": ["Sa", "Su"], "punkte": [{"zeit": 780, "wert": 1}, {"zeit": 900, "wert": 0}]}],
        "Sa, So 13:00–15:00",
    ),
    ("ganzer Tag", [{"tage": ["Mo"], "punkte": [{"zeit": 0, "wert": 1}]}], "Mo ganztägig"),
    ("ohne Blöcke", [], "kein Zeitfenster"),
]


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")
@pytest.mark.parametrize(("fall", "bloecke", "erwartet"), FENSTER, ids=[f[0] for f in FENSTER])
def test_zeitfenster_als_text(tmp_path, fall, bloecke, erwartet):
    skript = tmp_path / "fenster.mjs"
    skript.write_text(
        f'import {{ zeitfensterText }} from "{WAERMEPUMPE_JS.as_uri()}";\n'
        "console.log(zeitfensterText(JSON.parse(process.argv[2])));\n",
        encoding="utf-8",
    )
    ausgabe = subprocess.run(
        ["node", str(skript), json.dumps(bloecke)], capture_output=True, text=True, check=True
    )
    assert ausgabe.stdout.strip() == erwartet
