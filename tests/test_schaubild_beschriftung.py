"""Am Heizkreis tragen Vorlauf und Raum ihre kurze Beschriftung im Schaubild."""

from __future__ import annotations

from custom_components.heatnexus.schema.zeichnung import beschriftungen


def _modul(art: str, werte: list[tuple[str, str]]) -> dict:
    return {"art": art, "werte": [{"entity_id": e, "beschriftung": b} for e, b in werte]}


def test_heizkreis_nennt_vorlauf_und_raum():
    modul = _modul("heizkreis", [("sensor.vl", "Vorlauf"), ("sensor.raum", "Raum")])
    englisch = {"Vorlauf": "Flow", "Raum": "Room"}.get
    assert [e["prefix"] for e in beschriftungen(0, modul, 400, englisch)] == ["Flow ", "Room "]


def test_selbst_gewaehlte_und_andere_werte_bleiben_ohne():
    heizkreis = _modul("heizkreis", [("sensor.x", "Heizkreis Pumpe Drehzahl")])
    kessel = _modul("kessel", [("sensor.k", "Kessel"), ("sensor.l", "Leistung")])
    assert [e["prefix"] for e in beschriftungen(0, heizkreis, 400)] == [""]
    assert [e["prefix"] for e in beschriftungen(0, kessel, 400)] == ["", ""]


def test_die_leistungszahl_traegt_ihren_namen():
    waermepumpe = _modul("kessel", [("sensor.vl", "Vorlauf"), ("sensor.cop", "COP")])
    assert [e["prefix"] for e in beschriftungen(0, waermepumpe, 400)] == ["", "COP "]


def _quelle(werte: list[tuple[str, str]]) -> dict:
    return {**_modul("solar", werte), "quelle": True}


def test_drei_werte_einer_quelle_stehen_beschriftet_untereinander():
    modul = _quelle(
        [("sensor.k", "Kollektor"), ("sensor.vl", "Vorlauf"), ("sensor.rl", "Rücklauf")]
    )

    marken = beschriftungen(0, modul, 400)

    assert [e["prefix"] for e in marken] == ["Kollektor ", "Vorlauf ", "Rücklauf "]
    hoehen = [float(e["style"]["top"].rstrip("%")) for e in marken]
    assert hoehen == sorted(set(hoehen))


def test_ein_einzelner_wert_der_quelle_bleibt_ohne_namen():
    marken = beschriftungen(0, _quelle([("sensor.k", "Kollektor")]), 400)

    assert [e["prefix"] for e in marken] == [""]
