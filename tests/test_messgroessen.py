"""Einheiten, Geräteklassen, Statistik und Poll-Takt.

Vor 1.1.0 bekam nur ein °C-Wert eine Geräteklasse; alles andere lief als
namenloser Zahlensensor ohne Langzeitverlauf. Und der Poll-Takt stimmte nur
beim voreingestellten Intervall von 30 Sekunden.
"""

from __future__ import annotations

import pytest


def _sensor(**felder):
    beschreibung = {"type": "sensor", "name": "Wert", "unit": None}
    beschreibung.update(felder)
    return beschreibung


# ---------------------------------------------------------------------------
# Einheiten
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("geraet", "erwartet"),
    [
        ("m^3/h", "m³/h"),
        ("U/min", "rpm"),
        ("°C", "°C"),
        ("%", "%"),
        ("h", "h"),
    ],
)
def test_einheit_wird_auf_ha_schreibweise_gebracht(helpers, geraet, erwartet):
    assert helpers.messgroesse(_sensor(unit=geraet))["unit"] == erwartet


def test_ziffernfolge_ist_keine_einheit(helpers):
    """Die Anlage meldet für Datum und Uhrzeit die Formatkennungen 20 und 21."""
    assert helpers.messgroesse(_sensor(unit="20"))["unit"] is None


def test_unbekannte_einheit_bleibt_stehen(helpers):
    """Lieber die Angabe der Anlage als gar keine."""
    beschreibung = helpers.messgroesse(_sensor(unit="Impulse"))
    assert beschreibung["unit"] == "Impulse"
    assert beschreibung.get("device_class") is None


# ---------------------------------------------------------------------------
# Geräteklasse und Statistik
# ---------------------------------------------------------------------------
def test_leistung_bekommt_geraeteklasse_und_statistik(helpers):
    beschreibung = helpers.messgroesse(_sensor(name="Kesselleistung", unit="kW"))
    assert beschreibung["device_class"] == "power"
    assert beschreibung["state_class"] == "measurement"


def test_kelvin_ist_keine_temperatur(helpers):
    """K steht hier für eine Überhöhung, nicht für eine absolute Temperatur."""
    beschreibung = helpers.messgroesse(_sensor(name="WW-Überhöhung", unit="K"))
    assert beschreibung["device_class"] is None
    assert beschreibung["state_class"] == "measurement"


def test_zaehler_wird_zur_summe(helpers):
    beschreibung = helpers.messgroesse(_sensor(name="Betriebsstunden gesamt", unit="h"))
    assert beschreibung["state_class"] == "total_increasing"


def test_restlaufzeit_bleibt_messwert(helpers):
    """Sie zählt herunter – als Summe wäre ihr Verlauf unbrauchbar."""
    beschreibung = helpers.messgroesse(_sensor(name="Laufzeit bis Ascheentleerung", unit="h"))
    assert beschreibung["state_class"] == "measurement"


def test_kuratierte_angabe_hat_vorrang(helpers):
    beschreibung = helpers.messgroesse(
        _sensor(name="Brennstoffverbrauch", unit="h", state_class="total")
    )
    assert beschreibung["state_class"] == "total"


def test_zahlenfeld_bekommt_keine_statistik(helpers):
    """Ein bedienbares Feld ist kein Messwert."""
    beschreibung = helpers.messgroesse(
        {"type": "number", "name": "Sollwert", "unit": "°C", "step": 0.5}
    )
    assert beschreibung["device_class"] == "temperature"
    assert beschreibung.get("state_class") is None


def test_enum_bleibt_unberuehrt(helpers):
    beschreibung = helpers.messgroesse({"type": "enum_sensor", "name": "Betriebsart", "unit": "%"})
    assert beschreibung["unit"] == "%"
    assert beschreibung.get("device_class") is None


# ---------------------------------------------------------------------------
# Anzeigegenauigkeit
# ---------------------------------------------------------------------------
def test_genauigkeit_folgt_der_schrittweite(helpers):
    beschreibung = helpers.messgroesse(_sensor(name="Strom", unit="A", step="0.01"))
    assert beschreibung["precision"] == 2


def test_genauigkeit_ohne_schrittweite_aus_der_tabelle(helpers):
    assert helpers.messgroesse(_sensor(name="Drehzahl", unit="U/min"))["precision"] == 0


# ---------------------------------------------------------------------------
# Schreibschutz
# ---------------------------------------------------------------------------
def test_schreibgeschuetzte_temperatur_bleibt_temperatur(helpers):
    """Der häufigste Fall: Die Anlage meldet fast alles als Zahlenbereich."""
    assert helpers.lesetyp("number", "°C") == "temperature"


def test_schreibgeschuetzte_zahl_wird_sensor(helpers):
    assert helpers.lesetyp("number", "%") == "sensor"
    assert helpers.lesetyp("number", None) == "sensor"


def test_schalter_mit_einheit_ist_ein_zaehler(helpers):
    assert helpers.lesetyp("switch", "min") == "sensor"
    assert helpers.lesetyp("switch", None) == "binary_sensor"


@pytest.mark.parametrize(
    ("typ", "erwartet"),
    [("select", "enum_sensor"), ("time", "string_sensor")],
)
def test_uebrige_ruecksstufungen(helpers, typ, erwartet):
    assert helpers.lesetyp(typ, None) == erwartet


# ---------------------------------------------------------------------------
# Poll-Takt
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("intervall", "schnell", "normal", "langsam"),
    [
        (30, 1, 4, 30),  # Voreinstellung: 30 s, 2 min, 15 min
        (15, 2, 8, 60),
        (60, 1, 2, 15),
        (300, 1, 1, 3),  # nicht 30 – das wären zweieinhalb Stunden gewesen
    ],
)
def test_poll_takt_haengt_am_intervall(helpers, intervall, schnell, normal, langsam):
    takte = helpers.poll_takte(intervall)
    assert (takte["fast"], takte["normal"], takte["slow"]) == (schnell, normal, langsam)


def test_poll_takt_ohne_angabe_nutzt_die_voreinstellung(helpers):
    assert helpers.poll_takte(None) == helpers.poll_takte(30)


@pytest.mark.parametrize("intervall", [15, 30, 60, 120, 300])
def test_langsame_klasse_bleibt_unter_einer_stunde(helpers, intervall):
    """Egal wie eingestellt: Ein träger Wert darf nicht veralten."""
    assert helpers.poll_takte(intervall)["slow"] * intervall <= 3600
