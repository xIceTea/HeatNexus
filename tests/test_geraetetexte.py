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
        # Ohne ausdrückliche Wahl bleibt es bei Deutsch, gleich welche Sprache
        # Home Assistant führt: Die Kartenmuster der Oberfläche erkennen einen
        # Datenpunkt am deutschen Namen und fänden ihn sonst nicht mehr.
        (None, "fr", "de"),
        ("auto", "en-GB", "de"),
        ("auto", "es", "de"),
        ("auto", None, "de"),
        # Die ausdrückliche Wahl gilt weiterhin.
        ("it", "de", "it"),
        ("en", "de", "en"),
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


LISTING = """<html><head><title>Index of /res/xml</title></head><body>
<a href="../">Parent</a>
<a href="VarIdentTexte_en.xml">VarIdentTexte_en.xml</a>
<a href="ErrorTexte_en.xml">ErrorTexte_en.xml</a>
<a href="StaticNav.xml">StaticNav.xml</a>
</body></html>
"""


def test_dateinamen_aus_dem_verzeichnislisting(geraetetexte):
    namen = geraetetexte.dateinamen_lesen(LISTING)

    assert "VarIdentTexte_en.xml" in namen
    assert "../" not in namen


def test_kein_listing_ergibt_leere_menge(geraetetexte):
    assert geraetetexte.dateinamen_lesen("") == set()


async def test_abweichende_dateinamen_werden_aufgelistet(geraetetexte):
    # Eine Steuerung, die ihre Textdateien mit Baureihen-Vorsatz führt: Der
    # erwartete Name läuft ins Leere, das Verzeichnis nennt den richtigen.
    listing = '<a href="../">up</a><a href="PW_VarIdentTexte_en.xml">x</a>'
    inhalte = {"xml/": listing, "xml/PW_VarIdentTexte_en.xml": VARIDENT}

    async def hole(pfad):
        return inhalte.get(pfad)

    texte = await geraetetexte.laden(hole, "en")

    assert texte.namen["0/7"] == "Boiler temperature"


async def test_ohne_listing_bleibt_es_beim_leeren_ergebnis(geraetetexte):
    async def hole(pfad):
        return None

    assert not await geraetetexte.laden(hole, "en")


# Zwei Schreibweisen sind belegt; welche kommt, hängt an der Fassung der
# Steuerung. Beide müssen dasselbe ergeben.
FEHLER_ALS_INHALT = """<?xml version="1.0" encoding="UTF-8"?>
<ErrorTexte lang="de">
  <err id="1">Primärluftklappe blockiert.</err>
  <err id="15">Netzspannung nicht vorhanden</err>
</ErrorTexte>
"""

AUFZAEHL_ALS_VAL = """<?xml version="1.0" encoding="UTF-8"?>
<AufzaehlTexte lang="de">
  <gn id="2"><mn id="1">
    <val id="0">Aus</val>
    <val id="8">Automatik</val>
  </mn></gn>
</AufzaehlTexte>
"""


def test_stoerungstexte_auch_als_elementinhalt(geraetetexte):
    texte = geraetetexte.stoerungen_lesen(FEHLER_ALS_INHALT)

    assert texte[15] == "Netzspannung nicht vorhanden"
    assert texte[1].startswith("Primärluftklappe")


def test_aufzaehltexte_unabhaengig_vom_elementnamen(geraetetexte):
    assert geraetetexte.enums_lesen(AUFZAEHL_ALS_VAL)["2/1"] == {0: "Aus", 8: "Automatik"}
