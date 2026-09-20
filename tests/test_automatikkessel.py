"""Die kuratierte Tabelle für den Automatik-/Zusatzkessel (fctType 10).

Diese Baureihe führt ihre Kesseltemperatur in keiner Bedienebene. Die Tabelle
holt genau das nach, was der Hersteller auf die Titelseite legt und sonst
nirgends zeigt; die Tests halten sie gegen dieselbe Quelle.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import load_standalone

KOMPONENTE = Path(__file__).parent.parent / "custom_components" / "heatnexus"
FCT_AUTOMATIKKESSEL = "10"


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


def test_der_automatikkessel_hat_eine_tabelle(geraete):
    """Ohne sie bliebe die Kesseltemperatur in der Serviceebene liegen."""
    assert geraete.ENTITAETEN.get(int(FCT_AUTOMATIKKESSEL)), "fctType 10 ohne kuratierte Tabelle"


def test_jede_adresse_steht_in_der_geraete_datenbank(geraete, db):
    """Eine erfundene Adresse fiele hier auf, nicht erst an der Anlage."""
    fehlend = [a for a in _adressen(geraete.automatikkessel.ENTITAETEN) if a not in db["names"]]
    assert fehlend == [], f"nicht in device_db.json: {fehlend}"


def test_die_kesseltemperatur_steht_darin(geraete):
    """`0/7` trägt den Kessel im Schaubild.

    Das Schaubild zeichnet einen Anlagenteil nur, wenn er einen seiner Werte
    liefert. Fehlt die Kesseltemperatur, fällt der ganze Kessel aus dem Bild.
    """
    assert "0/7" in _adressen(geraete.automatikkessel.ENTITAETEN)


def test_was_der_hersteller_zeigt_aber_nicht_bedienen_laesst(geraete, db):
    """Die Regel dieser Tabelle, gegen die Herstellerdatei gehalten.

    Was in der Übersichtsebene steht und in keiner Bedienebene, erreicht ohne
    Eintrag hier niemanden: Es zählt als Werksebene und bleibt abgeschaltet.
    """
    ebenen = db["layers"][FCT_AUTOMATIKKESSEL]
    bedienbar = set(ebenen["info"]) | set(ebenen["operate"])
    noetig = set(ebenen["overview"]) - bedienbar
    fehlend = sorted(noetig - set(_adressen(geraete.automatikkessel.ENTITAETEN)))
    assert fehlend == [], f"nur in der Übersichtsebene, aber nicht kuratiert: {fehlend}"


def test_nichts_steht_darin_das_der_hersteller_nicht_nennt(geraete, db):
    """Die Gegenrichtung: keine Adresse ohne Beleg im eigenen Funktionstyp."""
    ebenen = db["layers"][FCT_AUTOMATIKKESSEL]
    belegt = set(ebenen["overview"]) | set(ebenen["info"]) | set(ebenen["operate"])
    ueberzaehlig = sorted(set(_adressen(geraete.automatikkessel.ENTITAETEN)) - belegt)
    assert ueberzaehlig == [], f"ohne Beleg in den Ebenen des fctType 10: {ueberzaehlig}"


def test_jeder_eintrag_nennt_eine_plattform(geraete):
    """Ohne Plattform legt der Client keine Entität an."""
    for eintrag in geraete.automatikkessel.ENTITAETEN:
        assert eintrag.get("platform"), eintrag
        assert eintrag.get("name"), eintrag


def test_die_genannten_auswahltabellen_gibt_es(geraete, db):
    """`enum` zeigt auf eine Tabelle – zeigt sie ins Leere, bleibt die Zahl."""
    for eintrag in geraete.automatikkessel.ENTITAETEN:
        if schluessel := eintrag.get("enum"):
            assert schluessel in db["enums"], f"{schluessel} fehlt in der Geräte-Datenbank"


def test_keine_adresse_steht_zweimal(geraete):
    """Zwei Entitäten auf derselben Adresse brauchten einen Namenszusatz."""
    adressen = _adressen(geraete.automatikkessel.ENTITAETEN)
    doppelt = sorted({a for a in adressen if adressen.count(a) > 1})
    assert doppelt == [], f"doppelt: {doppelt}"
