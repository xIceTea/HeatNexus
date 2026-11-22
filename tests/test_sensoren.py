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

import asyncio

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
# Zeitprogramm-Sensor – Schaltprogramme tragen Ein und Aus, keine Grad
# ---------------------------------------------------------------------------
def test_schaltprogramm_zeigt_ein_und_aus(sensoren):
    bloecke = [{"switchPoints": [{"time": "00:00", "value": 0}, {"time": "05:00", "value": 1}]}]
    klasse = sensoren.WindhagerTimeProgramSensor
    assert klasse._schaltet(bloecke) is True
    assert klasse._fmt_points(bloecke[0]["switchPoints"], "de", True) == "00:00→Aus, 05:00→Ein"
    assert klasse._fmt_points(bloecke[0]["switchPoints"], "en", True) == "00:00→Off, 05:00→On"
    assert klasse._fmt_points(bloecke[0]["switchPoints"], "nl", True) == "00:00→Uit, 05:00→Aan"


def test_temperaturprogramm_bleibt_in_grad(sensoren):
    punkte = [{"time": "06:00", "value": 21}, {"time": "22:00", "value": 0}]
    klasse = sensoren.WindhagerTimeProgramSensor
    assert klasse._schaltet([{"switchPoints": punkte}]) is False
    assert klasse._fmt_points(punkte) == "06:00→21 °C, 22:00→0 °C"


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


def test_enum_sensor_listet_werte_ohne_text_nicht_als_zustand(sensoren):
    """Ein gemeldeter Wertebereich über die Tabelle hinaus füllt die Liste nicht mit Platzhaltern."""
    entity, _ = _entitaet(
        sensoren.WindhagerEnumSensor,
        {"/1/60/0/9/75/0": "1"},
        type="enum_sensor",
        enum="2/9",
        allowed=[*range(32)],
    )
    assert not [o for o in entity.options if o.startswith("Unbekannt")]


def test_enum_sensor_nennt_unbekannte_werte_in_seiner_sprache(sensoren):
    entity, _ = _entitaet(
        sensoren.WindhagerEnumSensor,
        {"/1/60/0/9/75/0": "99"},
        type="enum_sensor",
        enum="2/9",
        sprache="en",
    )
    assert entity.native_value == "Unknown (99)"
    assert entity.native_value in entity.options


def test_enum_sensor_ohne_wert_bleibt_leer(sensoren):
    entity, _ = _entitaet(sensoren.WindhagerEnumSensor, {}, type="enum_sensor", enum="2/9")
    assert entity.native_value is None


# ---------------------------------------------------------------------------
# Störungsmeldung – daran hängt die Automationsvorlage
# ---------------------------------------------------------------------------
def _meldung(sensoren, roh: str | None, **felder):
    koordinator_werte = {}
    entity, koordinator = _entitaet(
        sensoren.WindhagerMessageTextSensor,
        koordinator_werte,
        type="message_text",
        node_id="60",
        **felder,
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


def test_meldungen_folgen_der_sprache_der_datenpunkte(sensoren):
    """Zustand und Art der Meldung erscheinen in der gewählten Sprache."""
    ruhig = _meldung(sensoren, "PUR 09  OK", sprache="en")
    gestoert = _meldung(sensoren, "PUR 09E346", sprache="en")

    assert ruhig.native_value == "No fault"
    assert gestoert.extra_state_attributes["meldungen"][0]["kind"] == "Error"


@pytest.mark.parametrize(
    ("sprache", "code", "erwartet"),
    [
        ("de", 0, "Keine Störung"),
        ("en", 0, "No fault"),
        ("en", 1, "1: Primary airflap defective"),
        ("en", 9998, "Unknown code 9998"),
        ("nl", 0, "Geen storing"),
        ("nl", 9998, "Onbekende code 9998"),
    ],
)
def test_alarmcode_folgt_der_sprache_der_datenpunkte(sensoren, sprache, code, erwartet):
    """Der Alarmcode des PuroWIN nimmt den Text aus der Tabelle der Sprache."""
    entity, koordinator = _entitaet(
        sensoren.WindhagerErrorTextSensor,
        {"/1/15/0/0/97/0": str(code)},
        type="sensor",
        oid="/1/15/0/0/97/0",
    )
    koordinator.client.sprache = sprache

    assert entity.native_value == erwartet


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


def test_englische_stoerung_ohne_texte_der_steuerung(sensoren):
    entity, koordinator = _entitaet(
        sensoren.WindhagerMessageTextSensor,
        {},
        type="message_text",
        node_id="60",
        oid=None,
        sprache="en",
    )
    koordinator.data["status"] = {"60": "PUR 09E346"}
    koordinator.last_update_success = True

    assert entity.native_value == "Cladding door open"
    assert entity.extra_state_attributes["meldungen"][0]["info"].startswith("Close")


def test_mehrere_stoerungen_werden_aneinandergereiht(sensoren):
    """Mehrere Codes im selben Feld, Dubletten fallen weg."""
    entity = _meldung(sensoren, "PUR 09E346E346E239")
    attr = entity.extra_state_attributes
    assert attr["anzahl"] == 2
    assert " | " in entity.native_value


# ---------------------------------------------------------------------------
# Meldungsliste – unsere eigene, weil die Anlage ihre nicht hergibt
# ---------------------------------------------------------------------------
def _liste(sensoren):
    entity, koordinator = _entitaet(
        sensoren.WindhagerMessageListSensor, {}, type="message_list", node_id="60", oid=None
    )
    koordinator.last_update_success = True
    return entity, koordinator


def _melden(entity, koordinator, roh):
    koordinator.data["status"] = {"60": roh}
    entity._aufnehmen()


def test_meldungsliste_behaelt_was_wieder_verschwindet(sensoren):
    """Der Fall, für den es die Liste überhaupt gibt.

    Verkleidungstür auf, Meldung da; Tür zu, Meldung weg. `FE01msg` zeigt
    danach wieder „OK", und ohne Liste stünde nirgends, dass etwas war.
    """
    entity, koordinator = _liste(sensoren)
    _melden(entity, koordinator, "PUR 09E346")
    _melden(entity, koordinator, "PUR 09  OK")

    assert entity.native_value == 1
    eintrag = entity.extra_state_attributes["meldungen"][0]
    assert eintrag["code"] == 346
    assert eintrag["text"] == "Verkleidungstür offen"
    assert eintrag["zuerst"] and eintrag["zuletzt"]


def test_meldungsliste_aendert_geschriebene_attribute_nicht_nachtraeglich(sensoren):
    """Home Assistant schreibt nur, wenn sich die Attribute vom letzten Stand unterscheiden."""
    entity, koordinator = _liste(sensoren)
    _melden(entity, koordinator, "PUR 09E346")
    geschrieben = entity.extra_state_attributes
    _melden(entity, koordinator, "PUR 09  OK")

    assert geschrieben["meldungen"][0]["aktiv"] is True
    assert entity.extra_state_attributes != geschrieben


def test_meldungsliste_zaehlt_dieselbe_meldung_nicht_hoch(sensoren):
    """Eine offene Tür über zehn Abrufe ist ein Ereignis, nicht zehn.

    Ohne diese Prüfung liefe der Zähler alle 30 Sekunden weiter, und nach
    einer Stunde stünden 120 „Meldungen" in der Liste.
    """
    entity, koordinator = _liste(sensoren)
    for _ in range(10):
        _melden(entity, koordinator, "PUR 09E346")

    assert entity.native_value == 1
    assert len(entity.extra_state_attributes["meldungen"]) == 1


def test_meldungsliste_zaehlt_eine_wiederkehrende_meldung(sensoren):
    """Tür auf, zu, wieder auf: zwei Ereignisse."""
    entity, koordinator = _liste(sensoren)
    for roh in ("PUR 09E346", "PUR 09  OK", "PUR 09E346", "PUR 09E346"):
        _melden(entity, koordinator, roh)

    [eintrag] = entity.extra_state_attributes["meldungen"]
    assert eintrag["anzahl"] == 2


def test_meldungsliste_zaehlt_nach_dem_neustart_nicht_doppelt(sensoren):
    """Eine über den Neustart anstehende Meldung bleibt ein Ereignis."""
    entity, koordinator = _liste(sensoren)
    _melden(entity, koordinator, "PUR 09E346")
    gespeichert = entity.extra_state_attributes["meldungen"]

    neu, koordinator = _liste(sensoren)
    neu._eintraege = {int(e["code"]): dict(e) for e in gespeichert}
    _melden(neu, koordinator, "PUR 09E346")

    assert neu.extra_state_attributes["meldungen"][0]["anzahl"] == 1


def test_meldungsliste_hat_keine_einheit_und_keine_liste_im_verlauf(sensoren):
    """Eine Einheit „Meldungen" stünde auch in Englisch so da; die Liste belastet den Rekorder."""
    entity, _ = _liste(sensoren)
    assert entity.native_unit_of_measurement is None
    assert "meldungen" in entity._unrecorded_attributes


def test_meldungsliste_sammelt_verschiedene_codes(sensoren):
    entity, koordinator = _liste(sensoren)
    _melden(entity, koordinator, "PUR 09E346")
    _melden(entity, koordinator, "PUR 09E239")
    assert entity.native_value == 2
    codes = {e["code"] for e in entity.extra_state_attributes["meldungen"]}
    assert codes == {346, 239}


def test_meldungsliste_laesst_sich_leeren(sensoren):
    entity, koordinator = _liste(sensoren)
    _melden(entity, koordinator, "PUR 09E346")
    asyncio.run(entity.leeren())
    assert entity.native_value == 0
    assert entity.extra_state_attributes["meldungen"] == []


def test_meldungsliste_sagt_dass_sie_unsere_ist(sensoren):
    """Eine geleerte Liste ist kein quittierter Fehler.

    Das Attribut macht die Unterscheidung maschinenlesbar; die Beschreibung
    des Dienstes sagt dasselbe in Worten.
    """
    entity, _ = _liste(sensoren)
    assert entity.extra_state_attributes["eigene_liste"] is True


def test_meldungsliste_ohne_daten_bleibt_leer(sensoren):
    """Kein FE01msg heißt: nichts aufnehmen, nicht abstürzen."""
    entity, koordinator = _liste(sensoren)
    koordinator.data["status"] = {}
    entity._aufnehmen()
    assert entity.native_value == 0


def test_meldungsliste_wird_nicht_gepollt(sensoren):
    assert sensoren.WindhagerMessageListSensor._register_poll_oid is False


def test_meldungsliste_ist_verfuegbar_ohne_eigenen_datenpunkt(sensoren):
    """Ihr Zustand ist die Länge der Liste, nicht ein Wert der Anlage.

    Als wertlose Entität gälte sie dauerhaft als nicht verfügbar und zeigte
    ihre Einträge nie an.
    """
    entity, koordinator = _liste(sensoren)
    koordinator.last_update_success = True
    assert entity.available is True


def test_der_zustand_steht_im_attribut_nicht_im_text(sensoren):
    """`stoerung_aktiv` ist die Wahrheit, der angezeigte Text nur Anzeige.

    Die Oberfläche wertet das Attribut aus – sonst hinge sie an einer
    Formulierung, die sich mit jeder Baureihe ändert.
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


@pytest.mark.parametrize(("roh", "erwartet"), [("245", 245), ("12.5", 12.5), ("0.0", 0.0)])
def test_ganzzahl_bleibt_ganzzahl(sensoren, roh, erwartet):
    """Ein Code wie 245 erscheint ohne Nachkommastelle, wie am Bediengerät."""
    entity, _ = _entitaet(sensoren.WindhagerGenericSensor, {"/1/60/0/9/75/0": roh}, type="sensor")
    assert entity.native_value == erwartet
    assert type(entity.native_value) is type(erwartet)


def test_ein_wert_ueber_dem_hoechstwert_gilt_als_unbekannt(sensoren):
    """Der Alarmcode meldet 65535 bei einem Bereich bis 65534: Das ist keine Meldung."""
    entity, _ = _entitaet(
        sensoren.WindhagerGenericSensor, {"/1/60/0/9/75/0": "65535"}, type="sensor", max=65534
    )
    assert entity.native_value is None


def test_ein_wert_im_bereich_bleibt_stehen(sensoren):
    entity, _ = _entitaet(
        sensoren.WindhagerGenericSensor, {"/1/60/0/9/75/0": "245"}, type="sensor", max=65534
    )
    assert entity.native_value == 245


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


@pytest.mark.parametrize(
    ("sprache", "erwartet"),
    [
        ("de", "Mo, Di: 06:00→21 °C | täglich: keine Schaltpunkte"),
        ("en", "Mo, Tu: 06:00→21 °C | daily: no switch points"),
        ("nl", "Ma, Di: 06:00→21 °C | dagelijks: geen schakelpunten"),
    ],
)
def test_zeitprogramm_folgt_der_sprache_der_datenpunkte(sensoren, sprache, erwartet):
    """Wochentage und Füllwörter erscheinen in der gewählten Sprache."""
    entity = _zeitprogramm(
        sensoren,
        [
            {"weekdays": ["Mo", "Tu"], "switchPoints": [{"time": "06:00", "value": 21}]},
            {"weekdays": ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"], "switchPoints": []},
        ],
    )
    entity.coordinator.client.sprache = sprache

    assert entity.native_value == erwartet


@pytest.mark.parametrize(
    ("eingabe", "erwartet"),
    [
        (["Ma", "Wo", "Vr", "Za", "Zo"], ["Mo", "We", "Fr", "Sa", "Su"]),
        (["Monday", "tuesday", "Sunday"], ["Mo", "Tu", "Su"]),
        (["Montag", "Mittwoch"], ["Mo", "We"]),
        (["maandag", "donderdag"], ["Mo", "Th"]),
    ],
)
def test_wochentage_werden_in_jeder_sprache_angenommen(sensoren, eingabe, erwartet):
    """Angezeigt wird niederländisch; dieselben Kürzel muss der Dienst annehmen."""
    assert sensoren.WindhagerTimeProgramSensor._norm_days(eingabe) == erwartet


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


def _tarifprogramm(sensoren):
    entity, koordinator = _entitaet(
        sensoren.WindhagerTimeProgramSensor, {}, type="time_program", oid="/1/60/2/54/7/0"
    )
    koordinator.data["objects"] = {
        "/1/60/2/54/7/0": [
            {
                "weekdays": ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"],
                "switchPoints": [{"time": "06:00", "value": 0}, {"time": "22:00", "value": 4}],
            }
        ]
    }
    koordinator.last_update_success = True
    return entity


@pytest.mark.parametrize(
    ("sprache", "erwartet"),
    [
        ("de", "täglich: 06:00→Tarif 1, 22:00→Tarif 5"),
        ("en", "daily: 06:00→Tariff 1, 22:00→Tariff 5"),
        ("nl", "dagelijks: 06:00→Tarief 1, 22:00→Tarief 5"),
    ],
)
def test_stromtarifprogramm_nennt_tarife_statt_grad(sensoren, sprache, erwartet):
    """`54/7` führt die Werte 0–4 für Tarif 1–5, keine Temperaturen und kein Ein/Aus."""
    entity = _tarifprogramm(sensoren)
    entity.coordinator.client.sprache = sprache

    assert entity.native_value == erwartet


async def test_stromtarifprogramm_lehnt_das_schreiben_ab(sensoren):
    """Das Tarifprogramm ist nur lesbar; der Dienst meldet das, statt Temperaturen zu schreiben."""
    from homeassistant.exceptions import ServiceValidationError

    entity = _tarifprogramm(sensoren)
    with pytest.raises(ServiceValidationError) as fehler:
        await entity.async_set_time_program(switch_points=[{"time": "06:00", "value": 1}])

    assert fehler.value.translation_key == "zeitprogramm_nicht_aenderbar"
    assert not entity.coordinator.client.geschrieben


@pytest.mark.parametrize(
    ("sprache", "erwartet"),
    [
        ("de", "Mo–Fr: 06:00→27,5 °C, 22:00→25,5 °C | Sa, So: 07:00→21 °C"),
        ("en", "Mo–Fr: 06:00→27.5 °C, 22:00→25.5 °C | Sa, Su: 07:00→21 °C"),
        ("nl", "Ma–Vr: 06:00→27,5 °C, 22:00→25,5 °C | Za, Zo: 07:00→21 °C"),
    ],
)
def test_zustand_fasst_tage_zusammen_und_schreibt_zahlen_der_sprache(sensoren, sprache, erwartet):
    """Drei Nachbartage stehen als Spanne; Dezimalzeichen und Einheit folgen der Sprache."""
    entity = _zeitprogramm(
        sensoren,
        [
            {
                "weekdays": ["Mo", "Tu", "We", "Th", "Fr"],
                "switchPoints": [
                    {"time": "06:00", "value": 27.5},
                    {"time": "22:00", "value": 25.5},
                ],
            },
            {"weekdays": ["Sa", "Su"], "switchPoints": [{"time": "07:00", "value": 21}]},
        ],
    )
    entity.coordinator.client.sprache = sprache

    assert entity.native_value == erwartet


FENSTER_BLOECKE = [
    {
        "weekdays": ["Mo", "Tu", "We", "Th", "Fr"],
        "values": [
            {"start": "05:00", "stop": "08:00"},
            {"start": "15:00", "stop": "22:00"},
            {"start": "00:00", "stop": "00:00"},
        ],
    },
    {
        "weekdays": ["Sa"],
        "values": [
            {"start": "22:00", "stop": "00:00"},
            {"start": "00:00", "stop": "00:00"},
            {"start": "00:00", "stop": "00:00"},
        ],
    },
    {
        "weekdays": ["Su"],
        "values": [{"start": "00:00", "stop": "00:00"}] * 3,
    },
]


@pytest.mark.parametrize(
    ("sprache", "erwartet"),
    [
        ("de", "Mo–Fr: 05:00–08:00, 15:00–22:00 | Sa: 22:00–24:00 | So: kein Zeitfenster"),
        ("en", "Mo–Fr: 05:00–08:00, 15:00–22:00 | Sa: 22:00–24:00 | Su: no time window"),
        ("nl", "Ma–Vr: 05:00–08:00, 15:00–22:00 | Za: 22:00–24:00 | Zo: geen tijdvenster"),
    ],
)
def test_ein_fensterprogramm_nennt_seine_zeitfenster(sensoren, sprache, erwartet):
    """Untertyp 7 führt je Tag bis zu drei Fenster; 00:00–00:00 ist unbenutzt, Ende 00:00 heißt 24:00."""
    entity = _zeitprogramm(sensoren, FENSTER_BLOECKE)
    entity.coordinator.client.sprache = sprache

    assert entity.native_value == erwartet


def _programm_an(sensoren, oid, punkte):
    entity, koordinator = _entitaet(
        sensoren.WindhagerTimeProgramSensor, {}, type="time_program", oid=oid
    )
    koordinator.data["objects"] = {oid: [{"weekdays": ["Mo"], "switchPoints": punkte}]}
    koordinator.last_update_success = True
    return entity


def test_das_pufferprogramm_des_hybridmanagers_zeigt_auch_null_in_grad(sensoren):
    """`54/15` führt 0–60 °C; eine 0 ist dort kein „Aus“."""
    entity = _programm_an(sensoren, "/1/60/2/54/15/0", [{"time": "06:00", "value": 0}])

    assert entity.native_value == "Mo: 06:00→0 °C"


@pytest.mark.parametrize("oid", ["/1/60/1/50/14/0", "/1/60/1/59/95/0", "/1/15/0/5/65/0"])
@pytest.mark.parametrize("wert", [21, 2, -1])
async def test_ein_schaltprogramm_nimmt_nur_null_und_eins(sensoren, oid, wert):
    from homeassistant.exceptions import ServiceValidationError

    entity = _programm_an(sensoren, oid, [{"time": "06:00", "value": 0}])
    with pytest.raises(ServiceValidationError) as fehler:
        await entity.async_set_time_program(switch_points=[{"time": "06:00", "value": wert}])

    assert fehler.value.translation_key == "schaltwert_ungueltig"


class _ObjektClient:
    """Liest ein festes Objekt und merkt sich, was geschrieben würde."""

    def __init__(self, objekt: dict) -> None:
        self.objekt = objekt
        self.objekte: list[tuple[str, dict]] = []
        self.sprache = "de"

    async def fetch_object(self, oid: str):
        return dict(self.objekt), 200

    async def write_object(self, oid: str, payload: dict) -> None:
        self.objekte.append((oid, payload))

    async def refresh_object(self, oid: str):
        return None


FENSTERPROGRAMM = {
    "OID": "/1/60/0/51/107/0",
    "typeId": 30,
    "subtypeId": 7,
    "value": [{"weekdays": ["Mo"], "values": [{"start": "06:00", "stop": "22:00"}]}],
}


@pytest.mark.parametrize(
    ("deskriptor", "gelesen"),
    [(7, 7), (14, 7)],
    ids=["untertyp_im_deskriptor", "untertyp_im_gelesenen_objekt"],
)
async def test_ein_programm_ohne_schaltpunkte_wird_nicht_geschrieben(sensoren, deskriptor, gelesen):
    """Nur Untertyp 14 trägt Schaltpunkte; ein Fensterprogramm ginge beim Schreiben verloren."""
    from homeassistant.exceptions import ServiceValidationError

    entity, koordinator = _entitaet(
        sensoren.WindhagerTimeProgramSensor,
        {},
        type="time_program",
        oid="/1/60/0/51/107/0",
        subtypeId=deskriptor,
    )
    koordinator.client = _ObjektClient({**FENSTERPROGRAMM, "subtypeId": gelesen})
    with pytest.raises(ServiceValidationError) as fehler:
        await entity.async_set_time_program(switch_points=[{"time": "06:00", "value": 21}])

    assert fehler.value.translation_key == "zeitprogramm_nicht_aenderbar"
    assert koordinator.client.objekte == []


async def test_ein_falscher_wochentag_ist_ein_hinweis_kein_absturz(sensoren):
    """Eine Fehleingabe am Dienst ist keine Störung der Integration.

    Home Assistant zeigt `ServiceValidationError` als Hinweis am Dienst an,
    statt einen Stapelauszug ins Protokoll zu schreiben.
    """
    from homeassistant.exceptions import ServiceValidationError

    entity = _zeitprogramm(sensoren, [{"weekdays": ["Mo"], "switchPoints": []}])
    with pytest.raises(ServiceValidationError):
        await entity.async_set_time_program(weekdays=["Montag"], switch_points=[])


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


# ---------------------------------------------------------------------------
# Rekorder – was in die Datenbank geht und was nicht
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("klasse", "felder", "werte", "behalten"),
    [
        ("WindhagerAbleitungSensor", {"type": "ableitung"}, {}, {"last_reset"}),
        ("WindhagerLaufzeitSensor", {"type": "laufzeit"}, {}, set()),
        ("WindhagerSchaltpunktSensor", {"type": "schaltpunkt"}, {}, set()),
        ("WindhagerSchaltpunktAbstandSensor", {"type": "schaltpunkt_abstand"}, {}, set()),
    ],
)
def test_nur_der_neustartstand_bleibt_aus_dem_rekorder(sensoren, klasse, felder, werte, behalten):
    """Die Namen der Attribute und die Ausnahmeliste dürfen nicht auseinanderlaufen.

    Ein umbenanntes Attribut liefe sonst still wieder in die Datenbank.
    """
    entity, _ = _entitaet(getattr(sensoren, klasse), werte, **felder)
    # `last_reset` setzt erst `async_added_to_hass`; hier zählt allein der Name.
    entity._attr_last_reset = None
    vorhanden = set(entity.extra_state_attributes)
    assert vorhanden - entity._unrecorded_attributes == behalten


def test_meldungsliste_waechst_nicht_ohne_grenze(sensoren):
    """Die Liste geht ganz in den Zustand für den Neustart und an die Oberfläche.

    Fällt etwas weg, dann die erledigten Meldungen, die am längsten zurückliegen.
    """
    from custom_components.heatnexus.sensor import meldungen

    entity, koordinator = _liste(sensoren)
    grenze = meldungen.MELDUNGEN_MAX
    for code in range(100, 100 + grenze + 10):
        _melden(entity, koordinator, f"PUR 09E{code}")

    codes = [m["code"] for m in entity.extra_state_attributes["meldungen"]]
    assert len(codes) == grenze
    assert 100 + grenze + 9 in codes  # die anstehende bleibt
    assert 100 not in codes  # die älteste erledigte geht


# ---------------------------------------------------------------------------
# Aktionen am Sensor treffen nur Sensoren mit der passenden Methode
# ---------------------------------------------------------------------------
class _Plattform:
    def __init__(self) -> None:
        self.dienste: dict[str, tuple[str, object]] = {}

    def async_register_entity_service(self, name, schema, methode, required_features=None):
        self.dienste[name] = (methode, required_features)


def _erreicht(entity, merkmale) -> bool:
    """Der Filter von Home Assistant: Ohne passendes Merkmal wird die Methode nicht aufgerufen."""
    if merkmale is None:
        return True
    eigene = entity.supported_features
    return eigene is not None and any(eigene & m == m for m in merkmale)


def test_aktionen_erreichen_nur_sensoren_mit_der_methode(sensoren):
    from custom_components.heatnexus.sensor.stoerspeicher import StoerspeicherSensor

    from .test_stoerspeicher import _koordinator

    plattform = _Plattform()
    sensoren.dienste_anmelden(plattform)
    temperatur, _ = _entitaet(sensoren.WindhagerTemperatureSensor, {}, type="temperature")
    alle = [
        temperatur,
        _zeitprogramm(sensoren, []),
        _liste(sensoren)[0],
        StoerspeicherSensor(_koordinator(None)),
    ]
    assert set(plattform.dienste) == {
        "meldungen_loeschen",
        "stoerung_quittieren",
        "stoerung_zuruecksetzen",
        "stoerung_loeschen",
        "set_time_program",
    }
    for name, (methode, merkmale) in plattform.dienste.items():
        for entity in alle:
            assert _erreicht(entity, merkmale) == hasattr(entity, methode), (
                name,
                type(entity).__name__,
            )
