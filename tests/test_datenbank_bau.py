"""Der Generator der Geräte-Datenbank: Zusammenführen der Namenslisten.

Drei Listen liefern Datenpunktnamen, geordnet nach Verlässlichkeit. Geprüft
wird die Regel, nach der sie sich überlagern — ein leerer Eintrag der
verlässlicheren Liste darf einen vorhandenen Namen nicht verdrängen.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest

WERKZEUG = Path(__file__).resolve().parents[1] / "tools" / "build_device_db.py"


@pytest.fixture(scope="module")
def generator() -> ModuleType:
    """Den Generator ohne Netzzugriff aus der Datei laden."""
    spec = importlib.util.spec_from_file_location("heatnexus_datenbankbau", WERKZEUG)
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


def test_ein_leerer_name_verdraengt_keinen_vorhandenen(generator):
    """Die reguläre Liste hat Vorrang – aber nur, wo sie etwas zu sagen hat."""
    namen = generator.sammle_namen(
        {"oids": {"52/113": "", "0/7": "Kesseltemperatur"}},
        {"oids_oem": {"52/113": "TerraWIN Heat Circuit Use Excess Energy"}},
    )
    assert namen["52/113"] == "TerraWIN Heat Circuit Use Excess Energy"
    assert namen["0/7"] == "Kesseltemperatur"


def test_die_regulaere_liste_gewinnt_wo_sie_etwas_sagt(generator):
    """Dort steht der Name, der auch am Bedienteil erscheint."""
    namen = generator.sammle_namen(
        {"oids": {"0/7": "Kesseltemperatur Ist"}},
        {"oids_oem": {"0/7": "Boiler temperature"}},
    )
    assert namen["0/7"] == "Kesseltemperatur Ist"


def test_nur_leerzeichen_zaehlt_als_leer(generator):
    namen = generator.sammle_namen(
        {"oids": {"52/0": "   "}},
        {"oids_oem": {"52/0": "AEW Evo Actual power consumtion"}},
    )
    assert namen["52/0"] == "AEW Evo Actual power consumtion"


# Eine Ebenendatei in der Form des Herstellers: Datenpunkte einzeln oder in
# Gruppen, die Merkmale am Eintrag, eine Geräteklasse neben `default`.
EBENEN_MIT_MERKMALEN = {
    "default/9": {
        "info": [
            {"oid": "4/92", "endpoint": "object"},
            {"oid": "23/100", "type": "reset", "reset": "0.00"},
        ],
        "service": [{"group_name": "G", "parameters": [{"oid": "42/18", "restart": True}]}],
    },
    "1415/9": {"operate": [{"oid": "4/93", "endpoint": "object"}]},
}


def test_objekt_datenpunkte_kommen_aus_allen_klassen(generator):
    """Ob ein Datenpunkt ein Objekt ist, hängt an ihm, nicht an der Klasse."""
    ebenen = generator.sammle_ebenen(EBENEN_MIT_MERKMALEN, {})
    assert ebenen["9"]["objekte"] == ["4/92", "4/93"]


def test_ruecksetzwerte_werden_uebernommen(generator):
    ebenen = generator.sammle_ebenen(EBENEN_MIT_MERKMALEN, {})
    assert ebenen["9"]["ruecksetzen"] == {"23/100": "0.00"}


def test_neustart_merkmal_wird_auch_in_gruppen_gefunden(generator):
    ebenen = generator.sammle_ebenen(EBENEN_MIT_MERKMALEN, {})
    assert ebenen["9"]["neustart"] == ["42/18"]


def test_fremdsprache_nimmt_namen_und_auswahltexte_der_herstellerdatei(generator):
    sprache = generator.sammle_sprache(
        {"oids": {"0/0": "Outside temperature", "0/1": " "}, "enums": {"9/75": {"1": "On"}}},
        {"0/1": "Room temperature"},
        "en",
    )
    assert sprache["names"] == {"0/0": "Outside temperature", "0/1": "Room temperature"}
    assert sprache["enums"] == {"9/75": {"1": "On"}}


def test_standby_an_der_heizgrenze_hat_einen_eigenen_text(generator):
    datei = {"enums": {"2/9": {"0": "Standby", "8": "Standby"}}}

    assert generator.sammle_enums(datei)["2/9"] == {"0": "Standby", "8": "Standby Heizgrenze"}
    englisch = generator.sammle_enums({"enums": {"2/9": {"8": "Stand-by"}}}, "en")
    assert englisch["2/9"]["8"] == "Stand-by heating limit"
    niederlaendisch = generator.sammle_enums({"enums": {"2/9": {"8": "Standby"}}}, "nl")
    assert niederlaendisch["2/9"]["8"] == "Standby verwarmingsgrens"


def test_die_geraetedatei_der_fremdsprache_liegt_neben_der_deutschen(generator, tmp_path):
    deutsch = tmp_path / "PW_VarIdentTexte_de.xml"
    englisch = tmp_path / "PW_VarIdentTexte_en.xml"
    englisch.write_text(
        '<VarIdentTexte lang="en"><gn id="0"><mn id="1">Actual</mn></gn></VarIdentTexte>',
        encoding="utf-8",
    )
    assert generator.geraetetexte_fuer(deutsch, "en") == englisch
    assert generator.geraetetexte_fuer(deutsch, "it") is None
    assert generator.geraetetexte_fuer(None, "en") is None


def test_jede_erzeugte_stoerungstabelle_wird_gelesen(generator, error_texts):
    assert set(error_texts.SPRACHEN) == {"de", *generator.FREMDSPRACHEN}


def test_die_englischen_stoerungstexte_decken_die_deutschen_ab(error_texts):
    assert set(error_texts._table("en")) == set(error_texts._table("de"))


def test_eine_ergaenzte_stoerung_steht_in_allen_sprachen(generator):
    for sprache in ("de", *generator.FREMDSPRACHEN):
        tabelle: dict = {}
        generator.ergaenze_stoerungen(tabelle, sprache)
        assert set(tabelle["FE242"]) == {"text", "info"}


def test_ein_herstellertext_hat_vorrang_vor_der_ergaenzung(generator):
    tabelle = {"FE242": {"text": "vom Hersteller"}}
    generator.ergaenze_stoerungen(tabelle, "de")
    assert tabelle["FE242"] == {"text": "vom Hersteller"}


# Hebungen über die Herstellerebene, für die noch keine Quelle verzeichnet ist.
# Die Liste darf nur schrumpfen: Wer einen Beleg in BELEGE einträgt, nimmt die
# Adresse hier heraus; eine neue Hebung ohne Beleg lässt den Test scheitern.
OHNE_BELEG: frozenset[str] = frozenset(
    {"10:2/0", "10:58/12", "10:58/115"}
    | {f"16:{a}" for a in ("1/7", "1/15", "1/22", "1/100", "22/75", "9/0", "5/1")}
)


def _hebungen(generator) -> set[str]:
    return {
        f"{fct}:{adresse}"
        for fct, je_ebene in generator.UEBERSTEUERUNG.items()
        for adressen in je_ebene.values()
        for adresse in adressen
    }


def _belegt(generator) -> set[str]:
    return {
        f"{fct}:{adresse}"
        for fct, quellen in generator.BELEGE.items()
        for adressen in quellen.values()
        for adresse in adressen
    }


def test_jede_hebung_ueber_die_herstellerebene_hat_einen_beleg(generator):
    unbelegt = _hebungen(generator) - _belegt(generator)
    assert sorted(unbelegt - OHNE_BELEG) == [], "neue Hebung ohne Eintrag in BELEGE"


def test_die_ausnahmeliste_enthaelt_nur_hebungen_ohne_beleg(generator):
    assert sorted(OHNE_BELEG & _belegt(generator)) == [], "belegt: aus OHNE_BELEG streichen"
    assert sorted(OHNE_BELEG - _hebungen(generator)) == [], "keine Hebung mehr: streichen"


def test_kein_beleg_ohne_hebung(generator):
    assert sorted(_belegt(generator) - _hebungen(generator)) == []
