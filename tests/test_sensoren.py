"""Die lesenden Sensoren.

`sensor.py` ist mit 265 Anweisungen die größte Plattformdatei und stand bei
null Prozent Abdeckung. Anders als bei den schreibenden Plattformen kann hier
nichts an der Heizung verstellt werden – falsch ist trotzdem falsch: Die
Störungsmeldung, an der die Automationsvorlage hängt, entsteht genau hier.

Geprüft wird, was die Sensoren aus den Rohdaten der Anlage machen. Die
Rohdaten stammen aus den echten Diagnose-Exporten beider Anlagen, nicht aus
der Fantasie.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha
from .test_plattformen import _beschreibung, _entitaet

pytestmark = requires_ha()


@pytest.fixture(scope="module")
def sensoren():
    """Die Plattform einmal laden."""
    from custom_components.heatnexus import sensor

    return sensor


# ---------------------------------------------------------------------------
# Enum-Sensor – die Tabelle ist die Anzeige, nicht die Auswahl
# ---------------------------------------------------------------------------
def test_enum_sensor_zeigt_auch_werte_die_nicht_waehlbar_sind(sensoren):
    """Der Puffer meldet „Pufferspeicher", wählbar wäre nur „Standby".

    Richtete sich die Anzeige nach `allowed`, stünde dort dauerhaft
    „Unbekannt". Angezeigt wird deshalb aus der vollen Tabelle.
    """
    entity, _ = _entitaet(
        sensoren.WindhagerEnumSensor,
        {"/1/60/0/9/75/0": "16"},
        type="enum_sensor",
        enum="2/9",
        allowed=[0],
    )
    assert entity.native_value == "Pufferspeicher"


def test_enum_sensor_nennt_unbekannte_werte_beim_namen(sensoren):
    """Ein Wert außerhalb der Tabelle darf den Zustand nicht verwerfen.

    Die Geräteklasse ENUM verlangt, dass der Zustand in `options` steht –
    sonst weist Home Assistant ihn mit einer Fehlermeldung zurück.
    """
    entity, _ = _entitaet(
        sensoren.WindhagerEnumSensor,
        {"/1/60/0/9/75/0": "99"},
        type="enum_sensor",
        enum="2/9",
    )
    assert entity.native_value == "Unbekannt (99)"
    assert entity.native_value in entity.options


def test_enum_sensor_ohne_wert_bleibt_leer(sensoren):
    entity, _ = _entitaet(sensoren.WindhagerEnumSensor, {}, type="enum_sensor", enum="2/9")
    assert entity.native_value is None


# ---------------------------------------------------------------------------
# Störungsmeldung – daran hängt die Automationsvorlage
# ---------------------------------------------------------------------------
def _meldung(sensoren, roh: str | None):
    koordinator_werte = {}
    entity, koordinator = _entitaet(
        sensoren.WindhagerMessageTextSensor,
        koordinator_werte,
        type="message_text",
        node_id="60",
        oid=None,
    )
    koordinator.data["status"] = {"60": roh} if roh is not None else {}
    koordinator.last_update_success = True
    return entity


def test_ohne_stoerung_steht_keine_stoerung_da(sensoren):
    """„PUR 09  OK" ist der Normalfall beider Anlagen."""
    entity = _meldung(sensoren, "PUR 09  OK")
    assert entity.native_value == "Keine Störung"
    assert entity.extra_state_attributes["stoerung_aktiv"] is False
    assert entity.extra_state_attributes["anzahl"] == 0


def test_eine_echte_stoerung_erscheint_im_klartext(sensoren):
    """Der Fall aus dem Betrieb: geöffnete Verkleidungstür, Fehler 346.

    Das Format ist `PUR 09E346` – der Buchstabe steht **unmittelbar** vor der
    Nummer (E = Fehler, A = Alarm, I = Info). Ein Rohwert mit Leerzeichen
    dazwischen ergibt keine Meldung; genau daran war ein früherer Entwurf
    dieses Tests grün, ohne den Parser überhaupt zu berühren.
    """
    entity = _meldung(sensoren, "PUR 09E346")
    assert entity.native_value == "Verkleidungstür offen"

    attr = entity.extra_state_attributes
    assert attr["stoerung_aktiv"] is True
    assert attr["anzahl"] == 1
    meldung = attr["meldungen"][0]
    assert meldung["code"] == 346
    assert meldung["kind"] == "Fehler"
    assert "Verkleidungstür schließen" in meldung["info"]


def test_mehrere_stoerungen_werden_aneinandergereiht(sensoren):
    """Mehrere Codes im selben Feld, Dubletten fallen weg."""
    entity = _meldung(sensoren, "PUR 09E346E346E239")
    attr = entity.extra_state_attributes
    assert attr["anzahl"] == 2
    assert " | " in entity.native_value


def test_die_automationsvorlage_haengt_am_attribut_nicht_am_text(sensoren):
    """`stoerung_aktiv` ist die Wahrheit, der angezeigte Text nur Anzeige.

    Die mitgelieferte Vorlage wertet ausdrücklich das Attribut aus – sonst
    hinge sie an einer Formulierung, die sich mit jeder Baureihe ändert.
    """
    entity = _meldung(sensoren, "PUR 09  OK")
    assert "stoerung_aktiv" in entity.extra_state_attributes
    assert entity.extra_state_attributes["rohwert"] == "PUR 09  OK"


def test_ohne_daten_ist_die_meldung_nicht_verfuegbar(sensoren):
    """Kein FE01msg heißt: nichts wissen, nicht „keine Störung"."""
    entity = _meldung(sensoren, None)
    assert entity.available is False
    assert entity.native_value is None
    assert entity.extra_state_attributes is None


# ---------------------------------------------------------------------------
# Gerätestatus
# ---------------------------------------------------------------------------
def test_geraetestatus_erkennt_ok_am_ende(sensoren):
    entity, koordinator = _entitaet(
        sensoren.WindhagerDeviceStatusSensor, {}, type="device_status", node_id="14", oid=None
    )
    koordinator.data["status"] = {"14": "PCM 20  OK"}
    koordinator.last_update_success = True
    assert entity.native_value == "PCM 20  OK"
    assert entity.extra_state_attributes["ok"] is True


def test_geraetestatus_meldet_eine_stoerung_als_nicht_ok(sensoren):
    entity, koordinator = _entitaet(
        sensoren.WindhagerDeviceStatusSensor, {}, type="device_status", node_id="60", oid=None
    )
    koordinator.data["status"] = {"60": "PUR 09E346"}
    koordinator.last_update_success = True
    assert entity.native_value == "PUR 09E346"
    assert entity.extra_state_attributes["ok"] is False


def test_status_und_meldung_werden_nicht_gepollt(sensoren):
    """Beide kommen aus der /1-Discovery, nicht aus dem OID-Abruf.

    Meldeten sie eine OID zum Polling an, liefe eine Anfrage je Takt ins
    Leere – sie haben gar keine.
    """
    assert sensoren.WindhagerDeviceStatusSensor._register_poll_oid is False
    assert sensoren.WindhagerMessageTextSensor._register_poll_oid is False


# ---------------------------------------------------------------------------
# Temperatur und Zahlenwerte
# ---------------------------------------------------------------------------
def test_temperatur_behaelt_ihre_nachkommastelle(sensoren):
    """Ein früherer Stand rechnete Werte über `str(int(float(v)))` um.

    Damit war jede Nachkommastelle weg – aus 58,9 °C wurden 58.
    """
    entity, _ = _entitaet(
        sensoren.WindhagerTemperatureSensor, {"/1/60/0/9/75/0": "58.9"}, type="temperature"
    )
    assert entity.native_value == pytest.approx(58.9)


def test_fehlender_messwert_ist_none_und_nicht_null(sensoren):
    """Null Grad und „kein Messwert" sind zwei verschiedene Dinge."""
    entity, _ = _entitaet(sensoren.WindhagerTemperatureSensor, {}, type="temperature")
    assert entity.native_value is None


@pytest.mark.parametrize("roh", ["-", "-.-", "", "Unfug"])
def test_unlesbare_werte_werden_nicht_zu_zahlen(sensoren, roh):
    """Die Anlage meldet fehlende Fühler als „-.-", nicht als Zahl."""
    entity, _ = _entitaet(
        sensoren.WindhagerTemperatureSensor, {"/1/60/0/9/75/0": roh}, type="temperature"
    )
    assert entity.native_value is None


def test_allgemeiner_sensor_uebernimmt_einheit_und_klasse(sensoren):
    entity, _ = _entitaet(
        sensoren.WindhagerGenericSensor,
        {"/1/60/0/9/75/0": "18116"},
        type="sensor",
        unit="h",
        state_class="total_increasing",
        precision=0,
    )
    assert entity.native_value == pytest.approx(18116)
    assert entity.native_unit_of_measurement == "h"
    assert entity.suggested_display_precision == 0


# ---------------------------------------------------------------------------
# Zeitprogramm
# ---------------------------------------------------------------------------
def _zeitprogramm(sensoren, bloecke):
    entity, koordinator = _entitaet(
        sensoren.WindhagerTimeProgramSensor,
        {},
        type="time_program",
        oid="/1/15/0/3/61/0",
    )
    koordinator.data["objects"] = {"/1/15/0/3/61/0": bloecke}
    koordinator.last_update_success = True
    return entity


def test_zeitprogramm_fasst_wochentage_und_schaltpunkte_zusammen(sensoren):
    """So, wie es das Bediengerät zeigt: Tagesblock, dann die Schaltzeiten."""
    entity = _zeitprogramm(
        sensoren,
        [
            {
                "weekdays": ["Mo", "Di", "Mi", "Do", "Fr"],
                "switchPoints": [
                    {"time": "06:00", "value": 21},
                    {"time": "22:00", "value": 18},
                ],
            }
        ],
    )
    zustand = entity.native_value
    assert zustand is not None
    assert "06:00" in zustand
    assert entity.available is True


def test_zeitprogramm_ohne_daten_ist_nicht_verfuegbar(sensoren):
    """Zeitprogramme kommen über den object-Endpunkt; fehlt er, fehlt alles."""
    entity, koordinator = _entitaet(
        sensoren.WindhagerTimeProgramSensor, {}, type="time_program", oid="/1/15/0/3/61/0"
    )
    koordinator.data["objects"] = {}
    koordinator.last_update_success = True
    assert entity.available is False


def test_zeitprogramm_meldet_keine_oid_zum_polling(sensoren):
    """Es wird über den object-Endpunkt gelesen, nicht über das OID-Polling."""
    assert sensoren.WindhagerTimeProgramSensor._register_poll_oid is False


# ---------------------------------------------------------------------------
# Zeichenketten
# ---------------------------------------------------------------------------
def test_zeichenkettensensor_gibt_den_rohwert_weiter(sensoren):
    """Uhrzeit und Datum der Anlage sind Texte, keine Zahlen."""
    entity, _ = _entitaet(
        sensoren.WindhagerStringSensor, {"/1/60/0/9/75/0": "20:36"}, type="string_sensor"
    )
    assert entity.native_value == "20:36"


def test_beschreibung_ist_gemeinsam_nutzbar():
    """Die Hilfsfunktion aus test_plattformen trägt die Pflichtfelder."""
    grund = _beschreibung()
    for feld in ("id", "oid", "name", "device_id", "device_name"):
        assert feld in grund
