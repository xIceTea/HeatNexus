"""Die kuratierte Tabelle für den BioWIN – ohne einen BioWIN.

**Hier steht ein Sonderfall.** Alle anderen kuratierten Tabellen sind an der
echten Anlage entstanden; diese nicht, denn es ist keine da. Sie stützt sich
auf zwei voneinander unabhängige Quellen:

* die `overview`-Ebene, die Windhager in `parameterLayer.json` selbst für
  `default/9` führt und die als `layers["9"]["overview"]` in
  `device_db.json` landet,
* ein öffentliches BioWIN-II-Projekt, das an einer laufenden Anlage genau
  diese Adressen abfragt.

Was diese Tests halten, ist deshalb nicht „stimmt der Wert", sondern: **weicht
die Tabelle von den Quellen ab, fällt es auf.** Ohne das wäre sie eine
Behauptung, die niemand nachprüft, bis sich der erste BioWIN-Nutzer über leere
Zeilen wundert.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import load_standalone

KOMPONENTE = Path(__file__).parent.parent / "custom_components" / "heatnexus"
FCT_BIOWIN = "9"


@pytest.fixture(scope="module")
def geraete():
    """Die Gerätemodule kommen ohne Home Assistant aus."""
    return load_standalone("geraete")


@pytest.fixture(scope="module")
def db():
    return json.loads((KOMPONENTE / "device_db.json").read_text(encoding="utf-8"))


def _adressen(eintraege) -> list[str]:
    """`/gn/mn/idx` -> `gn/mn`, die Form der Geräte-Datenbank."""
    adressen = []
    for eintrag in eintraege:
        teile = eintrag["oid"].strip("/").split("/")
        adressen.append(f"{teile[0]}/{teile[1]}")
    return adressen


def test_der_biowin_hat_ueberhaupt_eine_tabelle(geraete):
    """Ohne sie fiele der Kessel auf die reine Menü-Erkennung zurück."""
    assert geraete.ENTITAETEN.get(int(FCT_BIOWIN)), "fctType 9 ohne kuratierte Tabelle"


def test_jede_adresse_steht_in_der_geraete_datenbank(geraete, db):
    """Eine erfundene Adresse fiele hier auf, nicht erst an der Anlage."""
    fehlend = [a for a in _adressen(geraete.biowin.ENTITAETEN) if a not in db["names"]]
    assert fehlend == [], f"nicht in device_db.json: {fehlend}"


def test_die_tabelle_deckt_die_uebersicht_des_herstellers_ab(geraete, db):
    """Was Windhager selbst auf die Titelseite legt, muss vorkommen.

    Die `overview`-Ebene ist die Herstellerantwort auf „was gehört auf die
    Übersicht". Fehlt daraus etwas, ist die Tabelle unvollständig – und zwar
    nachweisbar, nicht nach Gefühl.
    """
    uebersicht = set(db["layers"][FCT_BIOWIN]["overview"])
    vorhanden = set(_adressen(geraete.biowin.ENTITAETEN))
    fehlend = sorted(uebersicht - vorhanden)
    assert fehlend == [], f"aus der Übersichtsebene nicht abgedeckt: {fehlend}"


def test_nichts_steht_darin_das_der_hersteller_nicht_nennt(geraete, db):
    """Die Gegenrichtung: keine Adresse ohne Beleg.

    Erlaubt ist, was in der Übersichts-, Info- oder Betreiberebene des
    Funktionstyps steht. Alles andere wäre von einem anderen Kessel
    abgeschrieben.
    """
    ebenen = db["layers"][FCT_BIOWIN]
    belegt = set(ebenen["overview"]) | set(ebenen["info"]) | set(ebenen["operate"])
    ueberzaehlig = sorted(set(_adressen(geraete.biowin.ENTITAETEN)) - belegt)
    assert ueberzaehlig == [], f"ohne Beleg in den Ebenen des fctType 9: {ueberzaehlig}"


def test_die_wartungszaehler_sind_die_des_biowin(geraete):
    """Der häufigste Fehlgriff: die PuroWIN-Adressen übernehmen.

    BioWIN zählt unter `20/61..20/63`, PuroWIN unter `39/91..39/93`. Beide
    heißen „Laufzeit bis …". Wer sie verwechselt, bekommt an der einen Anlage
    leere Zeilen und an der anderen keine Wartungsansicht.
    """
    adressen = set(_adressen(geraete.biowin.ENTITAETEN))
    assert {"20/61", "20/62", "20/63"} <= adressen
    assert not adressen & {"39/91", "39/92", "39/93"}


def test_der_purowin_behaelt_seine_eigenen_zaehler(geraete):
    """Gegenprobe – die Trennung muss in beide Richtungen halten."""
    adressen = set(_adressen(geraete.purowin.ENTITAETEN))
    assert {"39/91", "39/92", "39/93"} <= adressen
    assert not adressen & {"20/61", "20/62", "20/63"}


def test_jeder_eintrag_nennt_eine_plattform(geraete):
    """Ohne Plattform legt der Client keine Entität an."""
    for eintrag in geraete.biowin.ENTITAETEN:
        assert eintrag.get("platform"), eintrag
        assert eintrag.get("name"), eintrag


def test_die_genannten_auswahltabellen_gibt_es(geraete, db):
    """`enum` zeigt auf eine Tabelle – zeigt sie ins Leere, bleibt die Zahl."""
    for eintrag in geraete.biowin.ENTITAETEN:
        if schluessel := eintrag.get("enum"):
            assert schluessel in db["enums"], f"{schluessel} fehlt in der Geräte-Datenbank"


def test_keine_adresse_steht_zweimal(geraete):
    """Zwei Entitäten auf derselben Adresse brauchten einen Namenszusatz."""
    adressen = _adressen(geraete.biowin.ENTITAETEN)
    doppelt = sorted({a for a in adressen if adressen.count(a) > 1})
    assert doppelt == [], f"doppelt: {doppelt}"


@pytest.fixture(scope="module")
def anlagen():
    """Metadaten zweier BioWIN-Anlagen, je Geräteklasse."""
    pfad = Path(__file__).parent / "daten" / "biowin_metadaten.json"
    return json.loads(pfad.read_text(encoding="utf-8"))["klassen"]


def _schreibbar(anlagen, adresse: str) -> bool:
    return any(klasse.get(adresse, {}).get("writeProt") is False for klasse in anlagen.values())


def test_jede_auswahl_nennt_ihre_texte(geraete, db):
    """Ohne `enum` zeigt die Entität die nackte Zahl."""
    for eintrag, adresse in zip(
        geraete.biowin.ENTITAETEN, _adressen(geraete.biowin.ENTITAETEN), strict=True
    ):
        if eintrag["platform"] in ("select", "enum_sensor") and adresse in db["enums"]:
            assert eintrag.get("enum") == adresse, adresse


def test_eine_auswahl_folgt_dem_schreibrecht_der_anlage(geraete, anlagen):
    """Was die Anlage verstellen lässt, ist eine Auswahl, sonst eine Anzeige."""
    for eintrag, adresse in zip(
        geraete.biowin.ENTITAETEN, _adressen(geraete.biowin.ENTITAETEN), strict=True
    ):
        if eintrag["platform"] not in ("select", "enum_sensor"):
            continue
        erwartet = "select" if _schreibbar(anlagen, adresse) else "enum_sensor"
        assert eintrag["platform"] == erwartet, adresse


def test_ein_zaehler_bleibt_anzeige_auch_wenn_er_schreibbar_ist(geraete, anlagen):
    """Ohne Tabelle entstünde aus einem schreibbaren Zähler ein Eingabefeld."""
    zaehler = {"2/80", "2/81", "20/63", "23/100", "23/103"}
    assert all(_schreibbar(anlagen, a) for a in zaehler)
    plattform = {
        adresse: eintrag["platform"]
        for eintrag, adresse in zip(
            geraete.biowin.ENTITAETEN, _adressen(geraete.biowin.ENTITAETEN), strict=True
        )
    }
    assert {plattform[a] for a in zaehler} == {"sensor"}


def test_jede_adresse_meldet_eine_anlage_ausser_der_pumpe(geraete, anlagen):
    """`0/22` stammt nur aus der Übersicht von `default/9`; keine Anlage meldet sie."""
    gemeldet = set().union(*(set(klasse) for klasse in anlagen.values()))
    fehlend = sorted(set(_adressen(geraete.biowin.ENTITAETEN)) - gemeldet)
    assert fehlend == ["0/22"]


def test_der_alarmcode_steht_unter_diagnose(geraete):
    """Als Messwert stünde der Code in der Übersicht, ohne Text."""
    eintrag = next(e for e in geraete.biowin.ENTITAETEN if e["oid"] == "/2/0/0")
    assert eintrag["category"] == "diagnostic"
