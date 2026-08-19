"""Die schreibenden Plattformen.

**Warum es diese Datei gibt.** Bis 1.5.0-beta.1 hatte keine einzige Plattform,
die auf die Heizung *schreibt*, einen Test: `select`, `number`, `switch`,
`time`, `date` und `button` standen bei null Prozent Abdeckung. Bei einer
Integration, die einen Kessel steuert, ist das die falsche Stelle für eine
Lücke – geprüft war ausgerechnet das Ungefährliche (Schaubild 96 %,
Hilfsfunktionen 98 %).

Geprüft wird hier die **Umrechnung zwischen Home Assistant und der Anlage**:
Welche Zeichenkette geht an das Gerät, und was macht die Entität aus dem, was
zurückkommt. Das ist der Teil, an dem ein Fehler still bleibt und trotzdem
etwas verstellt.

Nicht geprüft wird die Home-Assistant-Verdrahtung (Plattform-Setup,
Entity-Registry) – dafür bräuchte es eine laufende Instanz, und die deckt
`test_client` bereits ab.
"""

from __future__ import annotations

import asyncio
from datetime import date as dt_date
from datetime import time as dt_time

import pytest

from .conftest import requires_ha

pytestmark = requires_ha()


class FakeClient:
    """Merkt sich, was geschrieben wurde – mehr braucht es nicht."""

    def __init__(self) -> None:
        """Leere Aufzeichnung anlegen."""
        self.geschrieben: list[tuple[str, str]] = []
        self.angemeldet: list[str] = []

    async def update(self, oid: str, wert: str) -> None:
        self.geschrieben.append((oid, wert))

    def steuerung_kennung(self) -> str:
        """Die Kennung aus den Seriennummern, wie sie der echte Client bildet."""
        return "SN1"

    def register_poll_oid(self, oid: str) -> None:
        self.angemeldet.append(oid)

    def unregister_poll_oid(self, oid: str) -> None:
        self.angemeldet.remove(oid)


class FakeCoordinator:
    """Das Nötigste, damit `CoordinatorEntity` und `geraet_info` laufen."""

    def __init__(self, werte: dict[str, str | None] | None = None) -> None:
        """Koordinator mit einem festen Satz Rohwerte."""
        self.client = FakeClient()
        self.data = {"oids": dict(werte or {}), "devices": [], "objects": {}, "status": {}}
        self.label = "Heizhaus"
        self.host = "192.0.2.10"
        self.neuron_id = "SN1"

    def async_add_listener(self, *_args, **_kwargs):
        return lambda: None

    async def async_request_refresh(self) -> None:
        return None


def _beschreibung(**felder) -> dict:
    grund = {
        "id": "SN1-3-0-9-75-0",
        "oid": "/1/60/0/9/75/0",
        "name": "Prüfwert",
        "device_id": "SN1-3-0",
        "device_name": "PuroWIN",
    }
    grund.update(felder)
    return grund


def _entitaet(klasse, werte=None, **felder):
    koordinator = FakeCoordinator(werte)
    objekt = klasse(koordinator, _beschreibung(**felder))
    return objekt, koordinator


# ---------------------------------------------------------------------------
# select – Enums mit Lücken
# ---------------------------------------------------------------------------
@pytest.fixture
def select_klasse():
    from custom_components.heatnexus.select import WindhagerSelect

    return WindhagerSelect


def test_select_schreibt_die_zahl_nicht_die_beschriftung(select_klasse):
    """An das Gerät geht der Zahlenwert, nicht der Text der Auswahlliste."""
    entity, koordinator = _entitaet(
        select_klasse,
        {"/1/60/0/9/75/0": "1"},
        type="select",
        enum="3/50",
    )
    asyncio.run(entity.async_select_option("Standby"))
    assert koordinator.client.geschrieben == [("/1/60/0/9/75/0", "0")]


def test_select_haelt_die_luecken_im_enum_aus(select_klasse):
    """Betriebswahl Puffer (20/15) kennt keinen Wert 5.

    Deshalb ist die Zuordnung ein Wörterbuch und keine Liste – über den Index
    gelesen wäre „Handbetrieb" (6) zu „Auto mit Zeitprogramm" (4) geworden.
    """
    entity, koordinator = _entitaet(
        select_klasse,
        {"/1/60/0/9/75/0": "6"},
        type="select",
        enum="20/15",
    )
    assert entity.current_option == "Handbetrieb"
    assert "Handbetrieb" in entity.options

    asyncio.run(entity.async_select_option("Pufferbetrieb"))
    assert koordinator.client.geschrieben == [("/1/60/0/9/75/0", "3")]


def test_select_beschraenkt_sich_auf_die_gemeldeten_werte(select_klasse):
    """Meldet die Anlage `allowed`, gilt nur das – der Rest existiert dort nicht."""
    entity, _ = _entitaet(
        select_klasse,
        {"/1/60/0/9/75/0": "0"},
        type="select",
        enum="3/50",
        allowed=[0, 1, 4],
    )
    assert entity.options == ["Standby", "Programm 1", "Heizbetrieb"]
    assert "WW-Betrieb" not in entity.options


def test_select_schreibt_nichts_bei_unbekannter_option(select_klasse):
    """Eine Option, die es nicht gibt, darf nichts an die Anlage schicken."""
    entity, koordinator = _entitaet(
        select_klasse,
        {"/1/60/0/9/75/0": "0"},
        type="select",
        enum="3/50",
    )
    asyncio.run(entity.async_select_option("Gibt es nicht"))
    assert koordinator.client.geschrieben == []


def test_select_ohne_wert_meldet_keine_auswahl(select_klasse):
    """Solange die Anlage schweigt, steht dort nichts – nicht der erste Eintrag."""
    entity, _ = _entitaet(select_klasse, {}, type="select", enum="3/50")
    assert entity.current_option is None


# ---------------------------------------------------------------------------
# number – Grenzen und Zahlenformat
# ---------------------------------------------------------------------------
@pytest.fixture
def number_klasse():
    from custom_components.heatnexus.number import WindhagerNumber

    return WindhagerNumber


def test_number_schreibt_ganze_zahlen_ohne_komma(number_klasse):
    """Schrittweite 1 heißt: „180", nicht „180.0".

    Die Anlage nimmt beides an, aber im Verlauf von Home Assistant stünde
    sonst ein anderer Text als der, den das Bediengerät zeigt.
    """
    entity, koordinator = _entitaet(
        number_klasse, {}, type="number", min=0, max=400, step=1, unit="min"
    )
    asyncio.run(entity.async_set_native_value(180.0))
    assert koordinator.client.geschrieben == [("/1/60/0/9/75/0", "180")]


def test_number_haelt_die_nachkommastelle_bei_feiner_schrittweite(number_klasse):
    """Behaglichkeit geht in 0,1 K – da darf nicht gerundet werden."""
    entity, koordinator = _entitaet(
        number_klasse, {}, type="number", min=-3, max=3, step=0.1, unit="K"
    )
    asyncio.run(entity.async_set_native_value(-1.5))
    assert koordinator.client.geschrieben == [("/1/60/0/9/75/0", "-1.5")]


@pytest.mark.parametrize(
    ("eingabe", "erwartet"),
    [(999.0, "400"), (-50.0, "0"), (400.0, "400"), (0.0, "0")],
)
def test_number_beschneidet_auf_die_grenzen_der_anlage(number_klasse, eingabe, erwartet):
    """Über die Grenze hinaus wird nicht geschrieben, sondern gekappt.

    Die Oberfläche hält sie zwar ein, ein Dienstaufruf aus einer Automation
    aber nicht – und die Anlage quittiert einen Wert außerhalb ihres Bereichs
    mit einem Fehler, nicht mit einer Korrektur.
    """
    entity, koordinator = _entitaet(number_klasse, {}, type="number", min=0, max=400, step=1)
    asyncio.run(entity.async_set_native_value(eingabe))
    assert koordinator.client.geschrieben == [("/1/60/0/9/75/0", erwartet)]


def test_number_ohne_grenzen_der_anlage_bleibt_benutzbar(number_klasse):
    """Fehlen min/max/step, stehen sie als None im Deskriptor.

    `float(None)` würde beim Anlegen abbrechen und die ganze Plattform
    mitreißen – deshalb die Vorgabewerte.
    """
    entity, _ = _entitaet(number_klasse, {}, type="number", min=None, max=None, step=None)
    assert entity.native_min_value == 0
    assert entity.native_max_value == 100
    assert entity.native_step == 1


# ---------------------------------------------------------------------------
# switch, button
# ---------------------------------------------------------------------------
def test_switch_schreibt_eins_und_null():
    from custom_components.heatnexus.switch import WindhagerSwitch

    entity, koordinator = _entitaet(WindhagerSwitch, {"/1/60/0/9/75/0": "0"}, type="switch")
    assert entity.is_on is False
    asyncio.run(entity.async_turn_on())
    asyncio.run(entity.async_turn_off())
    assert koordinator.client.geschrieben == [
        ("/1/60/0/9/75/0", "1"),
        ("/1/60/0/9/75/0", "0"),
    ]


def test_switch_ohne_wert_ist_weder_an_noch_aus():
    """Write-only-Datenpunkte melden nichts zurück – dann ist der Zustand offen."""
    from custom_components.heatnexus.switch import WindhagerSwitch

    entity, _ = _entitaet(WindhagerSwitch, {}, type="switch")
    assert entity.is_on is None


def test_button_schreibt_seinen_festen_wert():
    """Die Lagerraumbefüllung schreibt 7 auf 9/75, der Serviceausbrand 6.

    Beide hängen an derselben Adresse – verwechselte Werte hießen: statt zu
    befüllen brennt der Kessel eine Stunde lang aus.
    """
    from custom_components.heatnexus.button import WindhagerButton

    entity, koordinator = _entitaet(WindhagerButton, {}, type="button", press_value="7")
    asyncio.run(entity.async_press())
    assert koordinator.client.geschrieben == [("/1/60/0/9/75/0", "7")]


def test_button_ohne_angabe_schreibt_eins():
    from custom_components.heatnexus.button import WindhagerButton

    entity, koordinator = _entitaet(WindhagerButton, {}, type="button")
    asyncio.run(entity.async_press())
    assert koordinator.client.geschrieben == [("/1/60/0/9/75/0", "1")]


# ---------------------------------------------------------------------------
# time, date – die Formate der Anlage
# ---------------------------------------------------------------------------
def test_zeit_wird_als_hhmm_geschrieben_und_gelesen():
    from custom_components.heatnexus.time import WindhagerTime, parse_time

    assert parse_time("07:00") == dt_time(7, 0)
    assert parse_time("07:00:30") == dt_time(7, 0)
    assert parse_time("Unfug") is None
    assert parse_time(None) is None

    entity, koordinator = _entitaet(WindhagerTime, {"/1/60/0/9/75/0": "22:00"}, type="time")
    assert entity.native_value == dt_time(22, 0)

    asyncio.run(entity.async_set_value(dt_time(6, 30)))
    assert koordinator.client.geschrieben == [("/1/60/0/9/75/0", "06:30")]


def test_datum_haelt_das_format_der_anlage():
    """Die Anlage schreibt TT.MM.JJJJ – nicht ISO.

    Ein ISO-Datum nimmt sie stillschweigend nicht an; das Urlaubsprogramm
    bliebe dann auf dem alten Stand.
    """
    from custom_components.heatnexus.date import WindhagerDate, parse_date

    assert parse_date("04.08.2026") == dt_date(2026, 8, 4)
    assert parse_date("2026-08-04") is None
    assert parse_date("-") is None
    assert parse_date(None) is None

    entity, koordinator = _entitaet(WindhagerDate, {"/1/60/0/9/75/0": "04.08.2026"}, type="date")
    assert entity.native_value == dt_date(2026, 8, 4)

    asyncio.run(entity.async_set_value(dt_date(2026, 12, 24)))
    assert koordinator.client.geschrieben == [("/1/60/0/9/75/0", "24.12.2026")]


# ---------------------------------------------------------------------------
# binary_sensor – Drehzahl statt Zustand
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("wert", "erwartet"),
    [("0", False), ("1", True), ("100", True), ("42", True), (None, None)],
)
def test_binaersensor_zaehlt_jeden_wert_ueber_null_als_an(wert, erwartet):
    """Pumpen melden ihre Drehzahl, nicht 1 – „100" heißt läuft."""
    from custom_components.heatnexus.binary_sensor import WindhagerBinarySensor

    werte = {"/1/60/0/9/75/0": wert} if wert is not None else {}
    entity, _ = _entitaet(WindhagerBinarySensor, werte, type="binary_sensor")
    assert entity.is_on is erwartet


# ---------------------------------------------------------------------------
# Störungssensor – daran hängt die Automationsvorlage
# ---------------------------------------------------------------------------
def _stoerung(roh: str | None):
    from custom_components.heatnexus.binary_sensor import WindhagerStoerungBinarySensor

    entity, koordinator = _entitaet(
        WindhagerStoerungBinarySensor, {}, type="stoerung", node_id="60"
    )
    koordinator.data["status"] = {"60": roh}
    koordinator.last_update_success = True
    return entity


@pytest.mark.parametrize(
    ("roh", "an", "anzahl"),
    [("PUR 09  OK", False, 0), ("PUR 09E346", True, 1), (None, None, None)],
)
def test_stoerungssensor_folgt_der_meldung_der_anlage(roh, an, anzahl):
    """Kein FE01msg heißt: nichts wissen, nicht „keine Störung"."""
    entity = _stoerung(roh)
    assert entity.is_on is an
    assert (entity.extra_state_attributes or {}).get("anzahl") == anzahl


def test_stoerungssensor_nennt_den_klartext_im_attribut():
    """Die Vorlage schickt `stoerungstext` in die Benachrichtigung."""
    assert (
        _stoerung("PUR 09E346").extra_state_attributes["stoerungstext"] == "Verkleidungstür offen"
    )


def test_stoerungssensor_traegt_die_geraeteklasse_problem():
    """Nur damit lässt sich die Auswahl in der Vorlage darauf einschränken."""
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass

    assert _stoerung("PUR 09  OK").device_class is BinarySensorDeviceClass.PROBLEM


def test_stoerungssensor_wird_nicht_gepollt():
    """Die Quelle ist die /1-Discovery; eine OID hat dieser Wert nicht."""
    from custom_components.heatnexus.binary_sensor import WindhagerStoerungBinarySensor

    assert WindhagerStoerungBinarySensor._register_poll_oid is False


# ---------------------------------------------------------------------------
# Gemeinsames Verhalten aller schreibenden Plattformen
# ---------------------------------------------------------------------------
def test_schreiben_stoesst_immer_einen_abruf_an():
    """Nach jedem Schreiben wird nachgelesen.

    Ohne das stünde bis zum nächsten Takt – bis zu 30 Sekunden – der alte
    Wert da, und die Bedienung wirkte folgenlos.
    """
    from custom_components.heatnexus.switch import WindhagerSwitch

    entity, koordinator = _entitaet(WindhagerSwitch, {}, type="switch")
    gerufen: list[str] = []
    koordinator.async_request_refresh = _merker(gerufen)

    asyncio.run(entity.async_turn_on())
    assert gerufen == ["refresh"]


def _merker(liste: list[str]):
    async def _ruf() -> None:
        liste.append("refresh")

    return _ruf


def test_bedienbare_entitaeten_stellen_keinen_alten_wert_wieder_her():
    """Ein wiederhergestellter Sollwert wäre schlimmer als ein leeres Feld.

    Er sähe aus wie der Stand der Anlage, wäre aber der von vor dem Neustart.
    """
    from custom_components.heatnexus.number import WindhagerNumber
    from custom_components.heatnexus.select import WindhagerSelect
    from custom_components.heatnexus.switch import WindhagerSwitch

    for klasse in (WindhagerNumber, WindhagerSelect, WindhagerSwitch):
        assert klasse._wiederherstellbar is False, klasse.__name__


def test_bedienbare_entitaeten_bleiben_ohne_rueckmeldung_verfuegbar():
    """Write-only-Datenpunkte antworten beim Lesen mit 409.

    Wären sie deshalb „nicht verfügbar", ließe sich die Lagerraumbefüllung
    nie auslösen.
    """
    from custom_components.heatnexus.button import WindhagerButton
    from custom_components.heatnexus.number import WindhagerNumber
    from custom_components.heatnexus.select import WindhagerSelect
    from custom_components.heatnexus.switch import WindhagerSwitch

    for klasse in (WindhagerButton, WindhagerNumber, WindhagerSelect, WindhagerSwitch):
        assert klasse._require_value_for_available is False, klasse.__name__


def test_select_nimmt_die_zustandstexte_der_anlage(select_klasse):
    """Bei fremder Sprache benennt die Steuerung ihre Zustände selbst."""
    entity, _ = _entitaet(
        select_klasse,
        {"/1/60/0/9/75/0": "6"},
        type="select",
        enum="20/15",
        enum_texte={4: "Auto with timer", 6: "Manual"},
    )
    assert entity.current_option == "Manual"


def test_zustandstexte_ueberstehen_den_erkennungsstand(select_klasse):
    """Nach dem Ablegen als JSON sind die Schlüssel Text, nicht Zahl."""
    entity, _ = _entitaet(
        select_klasse,
        {"/1/60/0/9/75/0": "6"},
        type="select",
        enum="20/15",
        enum_texte={"4": "Auto with timer", "6": "Manual"},
    )
    assert entity.current_option == "Manual"


def test_der_kaminkehrer_schreibt_drei_auf_die_betriebswahl():
    """Betriebswahl 3 startet die Funktion; 6 und 7 sind andere Vorgänge."""
    from custom_components.heatnexus.button import WindhagerButton

    entity, koordinator = _entitaet(WindhagerButton, {}, type="button", press_value="3")
    asyncio.run(entity.async_press())
    assert koordinator.client.geschrieben == [("/1/60/0/9/75/0", "3")]
