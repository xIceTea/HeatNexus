"""Das Probe-Werkzeug an den LON-Netzwerkvariablen.

Zwei Dinge stehen hier unter Test, beide an fremder Hardware aufgefallen:

* **Die Adressform des Einzelabrufs ist nicht überall dieselbe.** Es gibt sie
  mit abschließendem `/0` und ohne, letztere mit `?count=&offset=`. Antwortet
  eine Steuerung nur auf eine davon, muss der Lauf sie finden, statt eine
  komplett leere Datei zu schreiben.
* **An einer NV-Funktion darf die Namenstabelle nicht greifen.** Dort ist
  `gn/mn` Gruppe und nvIndex, kein Datenpunkt; `0/0` wäre sonst
  „Aussentemperatur", obwohl der Eintrag `nviRequest` heißt.

Das Werkzeug wird per Dateipfad geladen und braucht kein Home Assistant.
"""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

WERKZEUG = Path(__file__).parent.parent / "tools" / "heatnexus_probe.py"

PRAEFIX_NV = "/1/60/32"
PRAEFIX_FKT = "/1/15/0"


@pytest.fixture(scope="module")
def probe_modul():
    spec = importlib.util.spec_from_file_location("heatnexus_probe", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class SteuerungAttrappe:
    """Antwortet nur auf die eine Adressform, die ihr mitgegeben wurde."""

    def __init__(self, antwortet_auf: str | None, *, als_liste: bool = False):
        """`antwortet_auf`: "lang", "kurz" oder None für „gar keine"."""
        self.antwortet_auf = antwortet_auf
        self.als_liste = als_liste
        self.pfade: list[str] = []

    def lookup(self, pfad: str):
        self.pfade.append(pfad)
        passt = self.antwortet_auf is not None and (
            pfad.endswith("?count=10&offset=0")
            if self.antwortet_auf == "kurz"
            else not pfad.endswith("?count=10&offset=0")
        )
        if not passt:
            return {"value": "-"}, 200
        daten = {"value": "42.5", "nvName": "PMX_avgTb_Tk"}
        return ([daten] if self.als_liste else daten), 200


def _menue_mit_einer_nv(nv_name: str = "PMX_eeBetrStd", snvt: str = "SNVT_time_hour") -> dict:
    return {
        "host": "192.0.2.10",
        "functions": [
            {
                "prefix": PRAEFIX_NV,
                "fct_type": -1,
                "name": "NV's",
                "datapoints": {
                    f"{PRAEFIX_NV}/0/28": {
                        "nvIndex": 28,
                        "nvName": nv_name,
                        "snvtName": snvt,
                        "unit": "Std",
                        "value": "-",
                    }
                },
            }
        ],
    }


def test_lange_adressform_wird_genommen_wenn_sie_traegt(probe_modul):
    """Die bisherige Form bleibt die erste Wahl."""
    steuerung = SteuerungAttrappe("lang")

    form = probe_modul._nv_form_bestimmen(steuerung, PRAEFIX_NV, 28)

    assert form == probe_modul.NV_ADRESSFORMEN[0]
    assert steuerung.pfade[0] == f"{PRAEFIX_NV}/0/28/0"


def test_kurze_adressform_wird_gefunden(probe_modul):
    """Antwortet die Steuerung nur ohne `/0`, muss der Lauf umschwenken."""
    steuerung = SteuerungAttrappe("kurz")

    form = probe_modul._nv_form_bestimmen(steuerung, PRAEFIX_NV, 28)

    assert form == probe_modul.NV_ADRESSFORMEN[1]
    assert steuerung.pfade[-1] == f"{PRAEFIX_NV}/0/28?count=10&offset=0"


def test_ohne_antwort_bleibt_es_bei_der_ersten_form(probe_modul):
    """Ein leeres Ergebnis wird nicht durch eine stille Umschaltung verdeckt."""
    steuerung = SteuerungAttrappe(None)

    assert (
        probe_modul._nv_form_bestimmen(steuerung, PRAEFIX_NV, 28) == probe_modul.NV_ADRESSFORMEN[0]
    )


def test_einelementiges_array_wird_ausgepackt(probe_modul):
    """Manche Firmware antwortet mit einer Liste statt mit dem Objekt."""
    steuerung = SteuerungAttrappe("kurz", als_liste=True)

    _, status, wert = probe_modul._nv_lesen(
        steuerung, PRAEFIX_NV, 28, probe_modul.NV_ADRESSFORMEN[1]
    )

    assert (status, wert) == (200, "42.5")


def test_adressform_wird_je_funktion_einmal_bestimmt(probe_modul):
    """Sonst kostet jeder Eintrag einen zusätzlichen Fehlversuch."""
    steuerung = SteuerungAttrappe("kurz")
    menus = _menue_mit_einer_nv()
    menus["functions"][0]["datapoints"][f"{PRAEFIX_NV}/0/29"] = {
        "nvIndex": 29,
        "nvName": "PMX_eeNbrAnhz",
        "snvtName": "SNVT_count",
        "unit": "",
        "value": "-",
    }

    ergebnis = probe_modul.suche_nv_werte(steuerung, menus)

    assert ergebnis["adressformen"] == {PRAEFIX_NV: probe_modul.NV_ADRESSFORMEN[1]}
    # Zwei Einträge: einmal die Formsuche (zwei Anfragen), danach je eine.
    assert len(steuerung.pfade) == 4


def test_csv_nennt_bei_netzwerkvariablen_den_nv_namen(probe_modul, tmp_path):
    """`0/0` ist an einer NV-Funktion kein Datenpunkt, sondern ein Index."""
    ziel = tmp_path / "datenpunkte.csv"

    probe_modul.write_csv(ziel, _menue_mit_einer_nv(nv_name="PMX_eeBetrStd"))

    zeile = next(iter(csv.DictReader(ziel.open(encoding="utf-8-sig"), delimiter=";")))
    assert zeile["name_db"] == "PMX_eeBetrStd"
    assert zeile["schreibbar"] == ""


class EbeneOhneOid:
    """Eine Menü-Ebene, deren Einträge nur einen `nvIndex` führen."""

    base = "http://192.0.2.10"

    def __init__(self, anzahl: int = 12):
        self.eintraege = [
            {"nvIndex": i, "nvName": f"WET_nv{i}", "value": "0.0"} for i in range(anzahl)
        ]

    def get(self, _url: str):
        return self.eintraege, 200


def _menus_mit_grosser_nv_ebene(anzahl: int = 12) -> dict:
    return {
        "functions": [
            {"prefix": PRAEFIX_NV, "fct_type": -1, "name": "NV's", "menus": {"0": anzahl}}
        ]
    }


def test_diagnose_uebersteht_ebene_ohne_datenpunktadresse(probe_modul):
    """Die größte Ebene ist an einer BioWIN die der Netzwerkvariablen.

    Deren Einträge führen keine `OID`. Ohne Rückfall auf den Index steht die
    Ebene für jeden Vergleich leer da – und der Lauf brach an der Stelle ab,
    an der er den ersten Eintrag nennen wollte.
    """
    ergebnis = probe_modul.run_diagnose(EbeneOhneOid(), _menus_mit_grosser_nv_ebene())

    assert ergebnis["grundabruf"] == 12
    assert ergebnis["ebene"] == f"{PRAEFIX_NV}/0"


def test_schluessel_faellt_auf_den_index_zurueck(probe_modul):
    """Ohne Schlüssel zählt jede Seite als neu und das Nachladen läuft leer."""
    eintraege = [{"nvIndex": 7, "nvName": "WET_nvoTist"}, {"OID": "/1/60/0/0/7/0"}]

    assert probe_modul._oids_of(eintraege) == ["nv/7", "/1/60/0/0/7/0"]


def test_knoten_ohne_funktion_bekommt_kandidaten(probe_modul):
    """Ein Kessel, der nur seinen LON-Adressraum meldet, wird trotzdem gefragt."""
    knoten = {"nodeId": 60, "functions": [{"fctId": 32, "fctType": -1, "name": "NV's"}]}

    funktionen = probe_modul._funktionen_eines_knotens(knoten)

    assert [f["fctId"] for f in funktionen] == [32, 0]
    assert funktionen[-1]["_ungemeldet"] is True


def test_gemeldete_funktion_verhindert_das_raten(probe_modul):
    """Wo die Struktur eine Funktion nennt, wird nichts dazuerfunden."""
    knoten = {
        "nodeId": 15,
        "functions": [
            {"fctId": 0, "fctType": 14, "name": "Heizkreis"},
            {"fctId": 32, "fctType": -1, "name": "NV's"},
        ],
    }

    funktionen = probe_modul._funktionen_eines_knotens(knoten)

    assert [f["fctId"] for f in funktionen] == [0, 32]
    assert not any(f.get("_ungemeldet") for f in funktionen)


def test_gesperrte_funktion_bleibt_draussen(probe_modul):
    """Eine gesperrte Funktion zählt nicht als vorhanden."""
    knoten = {
        "nodeId": 60,
        "functions": [
            {"fctId": 0, "fctType": 9, "name": "Kessel", "lock": True},
            {"fctId": 32, "fctType": -1, "name": "NV's"},
        ],
    }

    funktionen = probe_modul._funktionen_eines_knotens(knoten)

    assert [f["fctId"] for f in funktionen] == [32, 0]


def test_csv_laesst_echte_datenpunkte_unveraendert(probe_modul, tmp_path):
    """Die Namenstabelle gilt weiterhin überall dort, wo sie zuständig ist."""
    ziel = tmp_path / "datenpunkte.csv"
    menus = {
        "host": "192.0.2.10",
        "functions": [
            {
                "prefix": PRAEFIX_FKT,
                "fct_type": 14,
                "name": "Heizkreis",
                "datapoints": {
                    f"{PRAEFIX_FKT}/0/0/0": {"value": "6.4", "unit": "°C", "writeProt": True}
                },
            }
        ],
    }

    probe_modul.write_csv(ziel, menus)

    zeile = next(iter(csv.DictReader(ziel.open(encoding="utf-8-sig"), delimiter=";")))
    assert zeile["name_db"] == probe_modul.db_name("0/0")
    assert zeile["schreibbar"] == "nein"
