"""Das Probe-Werkzeug an Adressen außerhalb der Menü-Ebenen.

Die Menüs einer Anlage zeigen nicht alles, was die Herstellerdaten für ihren
Funktionstyp kennen, und nicht die Zusatzadressen, die die Integration einzeln
liest. Der Einzelabruf fragt genau diese Adressen ab.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

WERKZEUG = Path(__file__).parent.parent / "tools" / "heatnexus_probe.py"
PRAEFIX = "/1/16/0"


@pytest.fixture(scope="module")
def probe_modul():
    spec = importlib.util.spec_from_file_location("heatnexus_probe_einzeln", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _menus(fct_type: int, gefunden: list[str]) -> dict:
    return {
        "functions": [
            {
                "prefix": PRAEFIX,
                "fct_type": fct_type,
                "name": "Puffer",
                "datapoints": {f"{PRAEFIX}/{gnmn}/0": {} for gnmn in gefunden},
            }
        ]
    }


class SteuerungAttrappe:
    """Kennt nur die untere Puffertemperatur."""

    def __init__(self) -> None:
        """Ohne gestellte Anfragen beginnen."""
        self.gefragt: list[str] = []

    def lookup(self, pfad):
        self.gefragt.append(pfad)
        if pfad == f"{PRAEFIX}/0/16/0":
            return {"OID": pfad, "value": "41.5"}, 200
        return {"code": 404}, 404

    def map(self, ruf, eintraege):
        return [ruf(eintrag) for eintrag in eintraege]


def test_einzelziele_nennen_die_herstelleradressen_ausserhalb_der_menues(probe_modul):
    ziele = probe_modul.einzelziele(_menus(15, ["0/7"]))
    quellen = {z["oid"]: z["quelle"] for z in ziele}
    assert quellen[f"{PRAEFIX}/0/16/0"] == "hersteller"
    assert f"{PRAEFIX}/0/7/0" not in quellen, (
        "was das Menü schon liefert, wird nicht erneut gelesen"
    )


def test_einzelziele_nennen_die_zusatzadressen_der_integration(probe_modul):
    zusatz = probe_modul._zusatz(16)
    assert zusatz, "der Pufferspeicher führt Zusatzadressen"
    quellen = {z["oid"]: z["quelle"] for z in probe_modul.einzelziele(_menus(16, []))}
    for gnmn in zusatz:
        assert quellen[f"{PRAEFIX}/{gnmn}/0"] == "zusatz"


def test_einzelziele_ueberspringen_die_lon_variablen(probe_modul):
    assert probe_modul.einzelziele(_menus(-1, [])) == []


def test_einzelabruf_haelt_wert_und_status_je_adresse_fest(probe_modul):
    steuerung = SteuerungAttrappe()
    ziele = [
        {"oid": f"{PRAEFIX}/0/16/0", "quelle": "hersteller"},
        {"oid": f"{PRAEFIX}/59/24/0", "quelle": "zusatz"},
    ]
    ergebnis = probe_modul.hole_einzelwerte(steuerung, ziele)
    assert steuerung.gefragt == [f"{PRAEFIX}/0/16/0", f"{PRAEFIX}/59/24/0"]
    assert ergebnis["angefragt"] == 2
    assert ergebnis["lesbar"] == 1
    assert ergebnis["werte"][f"{PRAEFIX}/0/16/0"]["status"] == 200
    assert ergebnis["werte"][f"{PRAEFIX}/0/16/0"]["data"]["value"] == "41.5"
    assert ergebnis["werte"][f"{PRAEFIX}/59/24/0"]["status"] == 404


def test_einzelabruf_gehoert_zum_vollen_lauf(probe_modul):
    assert "einzeln" in {name for name, _ in probe_modul.ACTIONS.values()}


@pytest.mark.parametrize(
    "pfad",
    [
        "/WsFUP7030/api/1.0/info/LONApp",
        "/WsAdmin/api/1.0/systemtime",
        "/InfoWinFehlerlog/api/1.0/fehlerlog",
        "/InfoWinHeartbeat/api/1.0/heartbeat",
        "/WsFUP7030/api/1.0/windyndata",
        "/info/api/1.0/gui/version",
    ],
)
def test_endpunktsuche_kennt_die_pfade_der_integration(probe_modul, pfad):
    pfade = {b + k for b in probe_modul.ENDPUNKT_BASEN for k in probe_modul.ENDPUNKT_KANDIDATEN}
    assert pfad in pfade
