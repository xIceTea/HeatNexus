"""`set_time_program` hält das Raster der Anlage ein: 15 min, 0,5 und die Grenzen je Programm."""

from __future__ import annotations

import pytest

from .conftest import requires_ha
from .test_plattformen import _entitaet

pytestmark = requires_ha()


class _Client:
    def __init__(self, oid: str) -> None:
        self.objekt = {"OID": oid, "typeId": 30, "subtypeId": 14, "value": []}
        self.objekte: list[dict] = []
        self.sprache = "de"

    async def fetch_object(self, oid: str):
        return dict(self.objekt), 200

    async def write_object(self, oid: str, payload: dict) -> None:
        self.objekte.append(payload)

    async def refresh_object(self, oid: str):
        return None


def _programm(adresse: str):
    from custom_components.heatnexus import sensor

    oid = f"/1/15/0/{adresse}/0"
    entity, koordinator = _entitaet(
        sensor.WindhagerTimeProgramSensor, {}, type="time_program", oid=oid
    )
    koordinator.client = _Client(oid)
    return entity, koordinator.client


async def _geschrieben(adresse: str, punkte: list[dict]) -> list[dict]:
    entity, client = _programm(adresse)
    await entity.async_set_time_program(switch_points=punkte)
    return client.objekte[0]["value"][0]["switchPoints"]


async def _abgelehnt(adresse: str, punkte: list[dict]) -> str:
    from homeassistant.exceptions import ServiceValidationError

    entity, client = _programm(adresse)
    with pytest.raises(ServiceValidationError) as fehler:
        await entity.async_set_time_program(switch_points=punkte)
    assert client.objekte == []
    return fehler.value.translation_key


async def test_zeiten_runden_auf_viertelstunden():
    punkte = [
        {"time": "06:07", "value": 21},
        {"time": "08:08", "value": 20},
        {"time": "23:53", "value": 18},
    ]
    assert [p["time"] for p in await _geschrieben("3/61", punkte)] == ["06:00", "08:15", "23:45"]


async def test_temperaturen_runden_auf_halbe_grad():
    punkte = [
        {"time": "06:00", "value": 21.3},
        {"time": "12:00", "value": 20.2},
        {"time": "18:00", "value": 19.25},
    ]
    assert [p["value"] for p in await _geschrieben("3/61", punkte)] == [21.5, 20, 19.5]


async def test_mehr_als_sechs_schaltpunkte_werden_abgewiesen():
    punkte = [{"time": f"{stunde:02d}:00", "value": 20} for stunde in range(7)]
    assert await _abgelehnt("3/61", punkte) == "zu_viele_schaltpunkte"


@pytest.mark.parametrize(
    ("adresse", "wert"),
    [("3/61", 30.5), ("3/61", 4.5), ("5/61", 76), ("5/61", 9.5), ("54/15", 61), ("9/99", 128)],
)
async def test_werte_ausserhalb_der_grenzen_werden_abgewiesen(adresse, wert):
    assert await _abgelehnt(adresse, [{"time": "06:00", "value": wert}]) == "wert_ausserhalb"


@pytest.mark.parametrize(
    ("adresse", "wert"), [("3/61", 30), ("3/61", 5), ("4/82", 0), ("58/78", 90)]
)
async def test_die_grenzen_selbst_sind_erlaubt(adresse, wert):
    assert (await _geschrieben(adresse, [{"time": "06:00", "value": wert}]))[0]["value"] == wert


async def test_zwei_zeiten_in_derselben_viertelstunde_werden_abgewiesen():
    punkte = [{"time": "06:01", "value": 21}, {"time": "06:05", "value": 19}]
    assert await _abgelehnt("3/61", punkte) == "schaltzeit_doppelt"


def test_neue_fehlertexte_stehen_in_allen_sprachen():
    import json
    from pathlib import Path

    wurzel = Path(__file__).resolve().parents[1] / "custom_components" / "heatnexus"
    for datei in (
        "strings.json",
        "translations/de.json",
        "translations/en.json",
        "translations/nl.json",
    ):
        texte = json.loads((wurzel / datei).read_text(encoding="utf-8"))["exceptions"]
        for schluessel in ("wert_ausserhalb", "schaltzeit_doppelt"):
            assert texte[schluessel]["message"], (datei, schluessel)


@pytest.mark.parametrize(
    ("adresse", "bereich"), [("3/61", [5, 30]), ("5/61", [10, 75]), ("54/15", [0, 60])]
)
def test_das_panel_nennt_den_bereich_eines_programms(adresse, bereich):
    from custom_components.heatnexus import panel

    from .test_panel import anlage, entitaet, teil

    kreis = teil("Heizkreis", 14, [entitaet("sensor.programm", "Zeitprogramm", adresse=adresse)])
    (karte,) = panel.anlage_daten(anlage(kreis))["zeitprogramme"]

    assert karte["bereich"] == bereich


async def test_mehr_als_sieben_bloecke_werden_abgewiesen():
    from homeassistant.exceptions import ServiceValidationError

    entity, client = _programm("3/61")
    bloecke = [{"weekdays": ["Mo"], "switch_points": [{"time": "06:00", "value": 20}]}] * 8
    with pytest.raises(ServiceValidationError) as fehler:
        await entity.async_set_time_program(blocks=bloecke)
    assert fehler.value.translation_key == "zu_viele_bloecke"
    assert client.objekte == []


@pytest.mark.parametrize("antwort", [(None, 0), (None, 503), ([], 200)])
async def test_ohne_gelesenes_objekt_wird_nichts_geschrieben(antwort):
    from homeassistant.exceptions import HomeAssistantError

    entity, client = _programm("3/61")

    async def lesen(oid: str):
        return antwort

    client.fetch_object = lesen
    with pytest.raises(HomeAssistantError) as fehler:
        await entity.async_set_time_program(switch_points=[{"time": "06:00", "value": 21}])
    assert fehler.value.translation_key == "zeitprogramm_nicht_lesbar"
    assert client.objekte == []


@pytest.mark.parametrize(
    ("sprache", "adresse", "wert", "erwartet"),
    [
        ("de", "3/61", 30.3, {"wert": "30,3 °C", "min": "5 °C", "max": "30 °C"}),
        ("en", "3/61", 30.3, {"wert": "30.3 °C", "min": "5 °C", "max": "30 °C"}),
        ("nl", "54/15", 60.8, {"wert": "60,8 °C", "min": "0 °C", "max": "60 °C"}),
    ],
)
async def test_ein_wert_ausserhalb_steht_wie_die_uebrigen_werte_da(
    sprache, adresse, wert, erwartet
):
    from homeassistant.exceptions import ServiceValidationError

    entity, client = _programm(adresse)
    client.sprache = sprache
    with pytest.raises(ServiceValidationError) as fehler:
        await entity.async_set_time_program(switch_points=[{"time": "06:00", "value": wert}])
    assert fehler.value.translation_placeholders == erwartet


def test_die_fehlertexte_der_aktion_stehen_in_allen_sprachen():
    import json
    from pathlib import Path

    wurzel = Path(__file__).resolve().parents[1] / "custom_components" / "heatnexus"
    for datei in (
        "strings.json",
        "translations/de.json",
        "translations/en.json",
        "translations/nl.json",
    ):
        texte = json.loads((wurzel / datei).read_text(encoding="utf-8"))["exceptions"]
        for schluessel in ("zu_viele_bloecke", "zeitprogramm_nicht_lesbar", "wochentag_doppelt"):
            assert texte[schluessel]["message"], (datei, schluessel)


@pytest.mark.parametrize(
    ("sprache", "tage"),
    [("de", "Mo, Mi"), ("en", "Mo, We"), ("nl", "Ma, Wo")],
)
async def test_ein_wochentag_in_zwei_bloecken_wird_abgewiesen(sprache, tage):
    from homeassistant.exceptions import ServiceValidationError

    entity, client = _programm("3/61")
    client.sprache = sprache
    punkte = [{"time": "06:00", "value": 20}]
    bloecke = [
        {"weekdays": ["Mo", "Tu", "We"], "switch_points": punkte},
        {"weekdays": ["Mo", "We", "Fr"], "switch_points": punkte},
    ]
    with pytest.raises(ServiceValidationError) as fehler:
        await entity.async_set_time_program(blocks=bloecke)
    assert fehler.value.translation_key == "wochentag_doppelt"
    assert fehler.value.translation_placeholders == {"tage": tage}
    assert client.objekte == []
