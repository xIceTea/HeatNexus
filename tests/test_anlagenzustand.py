"""Der Sensor „Anlagenzustand“: Meldungsstufe, Sonderzustände des Kessels, Erreichbarkeit."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()

KESSEL = "/1/60/0"
BESCHREIBUNGEN = [
    {"oid": f"{KESSEL}/2/59/0", "type": "enum_sensor", "fct_type": 25},
    {"oid": f"{KESSEL}/9/75/0", "type": "select", "fct_type": 25},
    {"oid": f"{KESSEL}/2/1/0", "type": "enum_sensor", "fct_type": 25},
    {"oid": "/1/15/0/2/9/0", "type": "enum_sensor", "fct_type": 14},
]


@pytest.fixture(scope="module")
def modul():
    from custom_components.heatnexus.sensor import anlagenzustand

    return anlagenzustand


def _daten(art=3, wahl=1, phase=8, status=None, speicher=None):
    return {
        "oids": {
            f"{KESSEL}/2/59/0": None if art is None else str(art),
            f"{KESSEL}/9/75/0": str(wahl),
            f"{KESSEL}/2/1/0": str(phase),
        },
        "status": status or {"60": "PUR 09  OK"},
        "stoerspeicher": speicher,
    }


def test_ohne_besonderes_ist_die_anlage_in_ordnung(modul):
    assert modul.ermitteln(_daten(), BESCHREIBUNGEN, True)[0] == "in_ordnung"


def test_eine_stumme_steuerung_ist_nicht_erreichbar(modul):
    zustand, symbol, _ = modul.ermitteln(_daten(), BESCHREIBUNGEN, False)
    assert zustand == "nicht_erreichbar"
    assert symbol == "mdi:lan-disconnect"


def test_ohne_daten_ist_der_zustand_unbekannt(modul):
    assert modul.ermitteln(None, BESCHREIBUNGEN, True)[0] is None


@pytest.mark.parametrize(
    ("art", "wahl", "erwartet"),
    [
        (1, 6, "serviceausbrand"),
        (0, 6, "nach_serviceausbrand"),
        (9, 1, "kaminkehrer"),
        (14, 1, "lagerraum"),
        (11, 1, "sonderbetrieb"),
        (1, 1, "schaltet_ab"),
        (0, 1, "kessel_aus"),
    ],
)
def test_die_kesselregeln_gelten_in_ihrer_reihenfolge(modul, art, wahl, erwartet):
    assert modul.ermitteln(_daten(art=art, wahl=wahl), BESCHREIBUNGEN, True)[0] == erwartet


def test_ein_gesperrter_brenner_zaehlt_nach_der_betriebsart(modul):
    assert modul.ermitteln(_daten(phase=0), BESCHREIBUNGEN, True)[0] == "brenner_gesperrt"
    assert modul.ermitteln(_daten(art=9, phase=0), BESCHREIBUNGEN, True)[0] == "kaminkehrer"


@pytest.mark.parametrize(
    ("meldung", "erwartet"),
    [("PUR 09E346", "fehler"), ("PUR 09A101", "alarm"), ("PUR 09I012", "fehler")],
)
def test_eine_geraetemeldung_ohne_stoerspeicher(modul, meldung, erwartet):
    """Wie im Panel: Ohne Eintrag im Störspeicher zählt jede Gerätemeldung als Fehler, Alarm als Alarm."""
    daten = _daten(status={"60": meldung})
    assert modul.ermitteln(daten, BESCHREIBUNGEN, True)[0] == erwartet


def test_der_stoerspeicher_bestimmt_die_art(modul):
    speicher = [{"code": 12, "aktiv": True, "symbol": "I"}]
    daten = _daten(status={"60": "PUR 09I012"}, speicher=speicher)
    assert modul.meldungsstufe(daten) == "info"
    assert modul.ermitteln(daten, BESCHREIBUNGEN, True)[0] == "info"


def test_ein_info_eintrag_deckt_keinen_fehler_mit_gleichem_code(modul):
    speicher = [{"code": 12, "aktiv": True, "symbol": "I"}]
    daten = _daten(status={"60": "PUR 09E012"}, speicher=speicher)
    assert modul.meldungsstufe(daten) == "fehler"


def test_erledigte_eintraege_zaehlen_nicht(modul):
    speicher = [{"code": 346, "aktiv": False, "symbol": "E"}]
    assert modul.meldungsstufe(_daten(speicher=speicher)) == "ok"


def test_ein_fehler_geht_dem_kesselzustand_vor(modul):
    daten = _daten(art=9, status={"60": "PUR 09E346"})
    zustand, _, attribute = modul.ermitteln(daten, BESCHREIBUNGEN, True)
    assert zustand == "fehler"
    assert attribute["kesselzustand"] == "kaminkehrer"


def test_der_kesselzustand_geht_einer_info_vor(modul):
    speicher = [{"code": 12, "aktiv": True, "symbol": "I"}]
    daten = _daten(art=9, status={"60": "PUR 09I012"}, speicher=speicher)
    assert modul.ermitteln(daten, BESCHREIBUNGEN, True)[0] == "kaminkehrer"


def test_ohne_kessel_zaehlen_nur_die_meldungen(modul):
    ohne = [b for b in BESCHREIBUNGEN if b["fct_type"] != 25]
    assert modul.ermitteln(_daten(art=9), ohne, True)[0] == "in_ordnung"


def test_ein_unlesbarer_wert_ist_kein_sonderzustand(modul):
    assert modul.ermitteln(_daten(art=None), BESCHREIBUNGEN, True)[0] == "in_ordnung"


def test_eine_nicht_abgefragte_adresse_ist_kein_absturz(modul):
    """Eine Betriebswahl, die im Abruf fehlt, zählt als kein Serviceausbrand."""
    daten = _daten(art=0)
    del daten["oids"][f"{KESSEL}/9/75/0"]
    assert modul.ermitteln(daten, BESCHREIBUNGEN, True)[0] == "kessel_aus"


def test_jeder_zustand_hat_eine_uebersetzung(modul):
    import json
    from pathlib import Path

    wurzel = Path(modul.__file__).parent.parent
    for datei in ("strings.json", *sorted((wurzel / "translations").glob("*.json"))):
        texte = json.loads((wurzel / datei).read_text(encoding="utf-8"))
        zustaende = texte["entity"]["sensor"]["anlagenzustand"]["state"]
        assert set(zustaende) == set(modul.ZUSTAENDE), datei


def test_der_sensor_bleibt_verfuegbar_wenn_die_steuerung_schweigt(modul):
    client = SimpleNamespace(devices=BESCHREIBUNGEN, steuerung_kennung=lambda: "steuerung-SN1")
    coordinator = SimpleNamespace(
        data=_daten(), last_update_success=False, client=client, async_add_listener=None
    )
    sensor = modul.AnlagenzustandSensor(coordinator)

    assert sensor.available is True
    assert sensor.native_value == "nicht_erreichbar"
    assert sensor.unique_id == "steuerung-SN1-anlagenzustand"
