"""Ein Modul je Baureihe – und was der Zusammenbau daraus macht.

Geprüft wird, dass jede Datei im Ordner mitgezählt wird, dass kein
Funktionstyp doppelt vergeben ist und dass die Angaben zueinander passen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .conftest import load_standalone

ORDNER = Path(__file__).parent.parent / "custom_components" / "heatnexus" / "geraete"

# Bauteile, die das Schaubild zeichnen kann.
ARTEN = {"kessel", "puffer", "heizkreis", "wasser", "solar", "pumpenmodul", "umschaltung"}


@pytest.fixture(scope="module")
def geraete():
    """Die Gerätemodule kommen ohne Home Assistant aus."""
    return load_standalone("geraete")


def test_jede_datei_im_ordner_wird_mitgezaehlt(geraete):
    """Ein vergessenes Modul bliebe sonst still ohne Wirkung."""
    dateien = {p.stem for p in ORDNER.glob("*.py") if p.stem != "__init__"}
    gezaehlt = {m.__name__.rsplit(".", 1)[-1] for m in geraete.MODULE}
    assert dateien == gezaehlt


def test_kein_funktionstyp_ist_doppelt_vergeben(geraete):
    """Zwei Module auf derselben Nummer überschreiben einander im Zusammenbau."""
    typen = [m.FCT_TYPE for m in geraete.MODULE]
    assert len(typen) == len(set(typen))


def test_jedes_modul_nennt_die_gleichen_felder(geraete):
    """Der Zusammenbau greift auf jedes Feld zu, auch bei leeren Baureihen."""
    for modul in geraete.MODULE:
        for feld in geraete.PFLICHTFELDER:
            assert hasattr(modul, feld), f"{modul.__name__} ohne {feld}"
        assert isinstance(modul.ENTITAETEN, list)


def test_das_schaubild_kennt_jede_genannte_art(geraete):
    """Eine erfundene Art zeichnete das Schaubild als Ersatzbauteil."""
    assert set(geraete.SCHAUBILD_ARTEN.values()) <= ARTEN


def test_wer_eine_tabelle_fuehrt_traegt_auch_namen_und_rang(geraete):
    """Sonst stünde die Baureihe im Dashboard ohne Überschrift hinten."""
    for fct_type in geraete.ENTITAETEN:
        assert fct_type in geraete.MODELLE
        assert fct_type in geraete.RANG
        assert fct_type in geraete.SYMBOLE


def test_keine_kennung_steht_in_einer_tabelle_zweimal(geraete):
    """Eine Adresse darf mehrfach vorkommen, ihre Kennung nicht.

    Mehrere Tasten schreiben denselben Datenpunkt; erst der Zusatz trennt sie.
    """
    for fct_type, eintraege in geraete.ENTITAETEN.items():
        kennungen = [(e["oid"], e.get("key_suffix")) for e in eintraege]
        doppelt = {k for k in kennungen if kennungen.count(k) > 1}
        assert not doppelt, f"fctType {fct_type}: {sorted(doppelt)}"


def test_zusatzadressen_stehen_ohne_fuehrenden_schraegstrich(geraete):
    """Der Client hängt sie an das Präfix an; ein Strich zu viel bricht sie."""
    for eintraege in geraete.EXTRA_OIDS.values():
        assert all(not a.startswith("/") for a in eintraege)


def test_schaltpunkte_nennen_ihren_funktionstyp(geraete):
    """Ohne ihn fände der Client die Funktion nicht, an der er rechnet."""
    typen = {m.FCT_TYPE for m in geraete.MODULE}
    for eintrag in geraete.SCHALTPUNKTE + geraete.VERBRAUCHER_ABSTAND:
        assert eintrag["fct_type"] in typen


def test_die_kesselart_gilt_nur_fuer_waermeerzeuger(geraete):
    """Ein Puffer mit Kesselart zeichnete das falsche Bauteil."""
    for fct_type in geraete.KESSELARTEN:
        assert geraete.SCHAUBILD_ARTEN.get(fct_type) == "kessel"


def test_uebersteuerte_namen_gehoeren_zu_einer_baureihe(geraete):
    """Ohne Funktionstyp gehört ein Name in die flache Tabelle des Clients."""
    typen = {m.FCT_TYPE for m in geraete.MODULE}
    for fct_type, namen in geraete.NAMEN.items():
        assert fct_type in typen
        assert all("/" in adresse for adresse in namen)


def test_kein_modul_fuehrt_ein_unbekanntes_feld(geraete):
    """Ein Tippfehler im Feldnamen bliebe sonst ohne Wirkung und ohne Meldung."""
    erlaubt = set(geraete.PFLICHTFELDER) | set(geraete.KANNFELDER)
    for modul in geraete.MODULE:
        eigene = {n for n in vars(modul) if n.isupper()}
        assert eigene <= erlaubt, f"{modul.__name__}: {sorted(eigene - erlaubt)}"
