"""Textwerk der Steuerung: Einlesen der vier XML-Formen."""

from __future__ import annotations

import pytest

VARIDENT = """<?xml version="1.0" encoding="UTF-8"?>
<VarIdentTexte lang="en">
  <gn id="0"><mn id="1">Actual</mn><mn id="7">Boiler temperature</mn></gn>
  <gn id="2"><mn id="1">Operating phase</mn><mn id="9"> </mn></gn>
</VarIdentTexte>
"""

AUFZAEHL = """<?xml version="1.0" encoding="UTF-8"?>
<AufzaehlTexte lang="en">
  <gn id="2"><mn id="1">
    <enum id="0">Burner locked</enum>
    <enum id="4">Burner OFF </enum>
  </mn></gn>
</AufzaehlTexte>
"""

EBENEN = """<?xml version="1.0" encoding="UTF-8"?>
<EbenenTexte lang="en">
  <fcttyp id="14"><ebene id="97">Operating mode</ebene></fcttyp>
  <fcttyp id="0"></fcttyp>
</EbenenTexte>
"""

FEHLER = """<?xml version="1.0" encoding="UTF-8"?>
<ErrorTexte lang="en">
  <error code="1" text="Primary air flap blocked."/>
  <error code="15" text="No mains voltage"/>
</ErrorTexte>
"""


def test_namen_werden_je_gruppe_und_position_geschluesselt(geraetetexte):
    namen = geraetetexte.namen_lesen(VARIDENT)

    assert namen["0/7"] == "Boiler temperature"
    assert namen["2/1"] == "Operating phase"


def test_leerer_name_wird_uebergangen(geraetetexte):
    # Die Herstellerdateien führen einzelne Positionen mit reinem Leerraum.
    # Als Entitätsname wäre das unbrauchbar.
    assert "2/9" not in geraetetexte.namen_lesen(VARIDENT)


def test_aufzaehltexte_werden_je_wert_geschluesselt(geraetetexte):
    enums = geraetetexte.enums_lesen(AUFZAEHL)

    assert enums["2/1"] == {0: "Burner locked", 4: "Burner OFF"}


def test_ebenen_werden_je_funktionsart_geschluesselt(geraetetexte):
    ebenen = geraetetexte.ebenen_lesen(EBENEN)

    assert ebenen["14/97"] == "Operating mode"
    assert len(ebenen) == 1


def test_stoerungstexte_werden_nach_code_geschluesselt(geraetetexte):
    assert geraetetexte.stoerungen_lesen(FEHLER)[15] == "No mains voltage"


@pytest.mark.parametrize("kaputt", ["", "kein XML", "<VarIdentTexte lang="])
def test_unlesbares_xml_ergibt_leeres_ergebnis(geraetetexte, kaputt):
    # Eine abweichende Fassung darf den ganzen Erkennungslauf nicht kosten.
    assert geraetetexte.namen_lesen(kaputt) == {}
    assert geraetetexte.enums_lesen(kaputt) == {}
    assert geraetetexte.ebenen_lesen(kaputt) == {}
    assert geraetetexte.stoerungen_lesen(kaputt) == {}


@pytest.mark.parametrize(
    ("gewaehlt", "ha", "erwartet"),
    [
        (None, "fr", "fr"),
        ("auto", "en-GB", "en"),
        ("auto", "es", "de"),
        ("auto", None, "de"),
        ("it", "de", "it"),
        ("klingonisch", "fr", "de"),
    ],
)
def test_sprache_aufloesen(geraetetexte, gewaehlt, ha, erwartet):
    assert geraetetexte.sprache_aufloesen(gewaehlt, ha) == erwartet


async def test_deutsch_holt_nur_die_namensdatei(geraetetexte):
    # Aufzählungs-, Ebenen- und Störungstexte stehen auf Deutsch bereits in
    # der mitgelieferten Datenbank. Ein Abruf dafür trüge nichts bei.
    geholt = []

    async def hole(pfad):
        geholt.append(pfad)
        return VARIDENT

    texte = await geraetetexte.laden(hole, "de")

    assert geholt == ["xml/VarIdentTexte_de.xml"]
    assert texte.namen["0/7"] == "Boiler temperature"
    assert texte.enums == {}


async def test_fremde_sprache_holt_alle_vier(geraetetexte):
    inhalte = {
        "xml/VarIdentTexte_fr.xml": VARIDENT,
        "xml/AufzaehlTexte_fr.xml": AUFZAEHL,
        "xml/EbenenTexte_fr.xml": EBENEN,
        "xml/ErrorTexte_fr.xml": FEHLER,
    }

    async def hole(pfad):
        return inhalte.get(pfad)

    texte = await geraetetexte.laden(hole, "fr")

    assert texte.namen and texte.enums and texte.ebenen and texte.stoerungen


async def test_fehlende_datei_kostet_nur_ihren_teil(geraetetexte):
    async def hole(pfad):
        return VARIDENT if pfad.startswith("xml/VarIdent") else None

    texte = await geraetetexte.laden(hole, "en")

    assert texte.namen
    assert texte.enums == {}
    assert texte.stoerungen == {}


async def test_abruffehler_ergibt_leeres_ergebnis(geraetetexte):
    async def hole(pfad):
        raise OSError("Netz weg")

    texte = await geraetetexte.laden(hole, "en")

    assert not texte
