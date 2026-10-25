"""Kesselzustand: welche Entitäten und Werte den Kopf der Übersicht bestimmen."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

SPRACHEN = Path(__file__).resolve().parents[1] / "custom_components" / "heatnexus" / "sprachen"

BETRIEBSART = {0: "Ausgeschaltet", 1: "Abschaltvorgang", 5: "Kessel-Temperatur", 8: "Handbetrieb",
               9: "Kaminkehrerfunktion", 10: "Aktorentest", 11: "Installationsvorgang aktiv",
               13: "Inbetriebnahme", 14: "Lagerraum befüllen", 15: "Lagerraum befüllen",
               16: "Grundeinstellungen"}
WAHL = {0: "AUS", 1: "EIN", 6: "Serviceausbrand"}
PHASE = {0: "Brenner gesperrt", 3: "Standby", 9: "Gerät gesperrt"}


def _e(entity_id, adresse, optionen=None, bereich="sensor"):
    return {"entity_id": entity_id, "name": entity_id, "bereich": bereich, "adresse": adresse,
            "optionen": optionen or {}, "hat_wert": True, "kategorie": None}


def _anlage(*teile):
    return {"name": "Testanlage", "teile": list(teile)}


def _teil(name, fct_type, *entitaeten):
    return {"name": name, "fct_type": fct_type, "entitaeten": list(entitaeten)}


@pytest.fixture
def kz():
    from custom_components.heatnexus.dashboard import kesselzustand

    return kesselzustand


def _purowin():
    return _teil("PuroWIN", 25,
                 _e("sensor.art", "2/59", BETRIEBSART),
                 _e("sensor.wahl", "9/75", WAHL),
                 _e("sensor.phase", "2/1", PHASE))


def test_purowin_nennt_alle_regeln(kz):
    b = kz.kesselzustand(_anlage(_purowin()))
    assert (b["bezug"], b["betriebsart"], b["betriebswahl"], b["phase"]) == (
        "sensor.art", "sensor.art", "sensor.wahl", "sensor.phase")
    assert b["serviceausbrand"] == ["Serviceausbrand"]
    texte = [r["text"] for r in b["regeln"]]
    assert texte[:4] == ["Serviceausbrand läuft", "Kessel aus nach Serviceausbrand",
                         "Kaminkehrer aktiv", "Lagerraum befüllen"]
    assert texte[-1] is None and b["regeln"][-1]["quelle"] == "phase"
    assert b["regeln"][-1]["wenn"] == ["Brenner gesperrt", "Gerät gesperrt"]
    service = next(r for r in b["regeln"] if r["text"] is None and r["quelle"] == "betriebsart")
    assert service["wenn"] == ["Handbetrieb", "Aktorentest", "Installationsvorgang aktiv",
                               "Inbetriebnahme", "Grundeinstellungen"]
    assert "Kessel-Temperatur" not in {t for r in b["regeln"] for t in r["wenn"]}


def test_ohne_betriebswahl_entfallen_die_serviceausbrand_regeln(kz):
    teil = _teil("BioWIN", 9, _e("sensor.art", "2/59", BETRIEBSART), _e("sensor.phase", "2/1", PHASE))
    b = kz.kesselzustand(_anlage(teil))
    assert b["betriebswahl"] is None and b["serviceausbrand"] == []
    assert all(r["serviceausbrand"] is not True for r in b["regeln"])
    assert "Kessel ausgeschaltet" in [r["text"] for r in b["regeln"]]


def test_anlage_ohne_kessel_kennt_nur_die_erreichbarkeit(kz):
    kreis = _teil("Heizkreis", 14, _e("sensor.betriebsart_hk", "2/9", {3: "WW-Ladung"}))
    b = kz.kesselzustand(_anlage(kreis))
    assert b["bezug"] == "sensor.betriebsart_hk"
    assert b["betriebsart"] is None and b["regeln"] == []


def test_ohne_bezug_gibt_es_keine_beschreibung(kz):
    assert kz.kesselzustand(_anlage(_teil("Puffer", 16))) is None


def test_englische_anlage_liefert_englische_zustandstexte(kz):
    teil = _teil("PuroWIN", 25,
                 _e("sensor.art", "2/59", {0: "Switched off", 1: "Shutdown", 9: "Chimney sweep function"}),
                 _e("sensor.wahl", "9/75", {6: "Service burn-out"}))
    b = kz.kesselzustand(_anlage(teil))
    assert b["serviceausbrand"] == ["Service burn-out"]
    assert b["regeln"][0]["wenn"] == ["Shutdown"]


def test_jeder_feste_text_ist_uebersetzt(kz):
    for sprache in ("en", "nl"):
        buch = json.loads((SPRACHEN / f"{sprache}.json").read_text(encoding="utf-8"))
        fehlt = [t for t in kz.TEXTE if t not in buch]
        assert not fehlt, f"{sprache}: {fehlt}"
