"""Die Temperaturen, bei denen die Anlage schaltet.

Sollwert und Hysterese führt die Steuerung getrennt; der Schaltpunkt ergibt
sich erst aus beiden. Die Ladung beginnt, wenn die Puffertemperatur oben
unter ``Sollwert − halbe Hysterese`` fällt.
"""

from __future__ import annotations

import pytest

from .conftest import requires_ha
from .test_plattformen import _entitaet

pytestmark = requires_ha()

SOLLWERT = "/1/16/1/1/15/0"
HYSTERESE = "/1/16/1/9/35/0"
TPE = "/1/16/1/21/65/0"


@pytest.fixture(scope="module")
def sensoren():
    from custom_components.heatnexus import sensor

    return sensor


def _schaltpunkt(sensoren, werte, **felder):
    return _entitaet(
        sensoren.WindhagerSchaltpunktSensor,
        werte,
        oid=SOLLWERT,
        name="Ladung ab",
        type="schaltpunkt",
        ausloeser_oid=HYSTERESE,
        anteil=-0.5,
        unit="°C",
        **felder,
    )


def test_die_ladung_beginnt_bei_sollwert_minus_halber_hysterese(sensoren):
    """Unter dieser Schwelle beginnt die Ladung."""
    entity, _ = _schaltpunkt(sensoren, {SOLLWERT: "59.5", HYSTERESE: "16"})

    assert entity.native_value == 51.5


def test_die_liefernde_seite_rechnet_mit_voller_hysterese(sensoren):
    """Derselbe Parameter, andere Rolle: Der Kessel bekommt Sollwert plus Hysterese."""
    entity, _ = _entitaet(
        sensoren.WindhagerSchaltpunktSensor,
        {SOLLWERT: "57", HYSTERESE: "17"},
        oid=SOLLWERT,
        name="Anforderungstemperatur",
        type="schaltpunkt",
        ausloeser_oid=HYSTERESE,
        anteil=1.0,
        unit="°C",
    )

    assert entity.native_value == 74.0


def test_ohne_anforderung_gibt_es_keinen_schaltpunkt(sensoren):
    """`1/15` steht nur an, solange geladen wird. Eine 0 wäre irreführend."""
    entity, _ = _schaltpunkt(sensoren, {SOLLWERT: "0", HYSTERESE: "16"})

    assert entity.native_value is None


# Der Schaltpunkt sagt, wo geschaltet wird. Für eine Automation zählt, wie
# weit es noch dahin ist.
def _abstand(sensoren, werte, **felder):
    return _entitaet(
        sensoren.WindhagerSchaltpunktAbstandSensor,
        werte,
        oid=TPE,
        name="Einschaltpunkt Delta",
        type="schaltpunkt_abstand",
        bezugs_oid=SOLLWERT,
        ausloeser_oid=HYSTERESE,
        anteil=-0.5,
        unit="K",
        **felder,
    )


def test_der_abstand_zaehlt_bis_zum_einschaltpunkt_herunter(sensoren):
    """Schwelle 51,5 °C, gemessen 54,7 °C – es fehlen 3,2 K."""
    entity, _ = _abstand(sensoren, {TPE: "54.7", SOLLWERT: "59.5", HYSTERESE: "16"})

    assert entity.native_value == 3.2


def test_unter_der_schwelle_wird_der_abstand_negativ(sensoren):
    """Läuft die Ladung bereits, ist die Schwelle überschritten."""
    entity, _ = _abstand(sensoren, {TPE: "51.3", SOLLWERT: "59.5", HYSTERESE: "16"})

    assert entity.native_value == -0.2


def test_ohne_anforderung_gibt_es_keinen_abstand(sensoren):
    """Ohne Sollwert gibt es keine Schwelle, zu der ein Abstand bestünde."""
    entity, _ = _abstand(sensoren, {TPE: "54.7", SOLLWERT: "0", HYSTERESE: "16"})

    assert entity.native_value is None


# Der Kaminkehrer meldet eine Restlaufzeit, keinen Schaltzustand. Als Schalter
# deklariert verlor er bei der Herabstufung seine Einheit und zeigte „0.0“.
def test_der_kaminkehrer_ist_ein_minutenwert(sensoren):
    """`9/90` meldet min mit `typeId 4`, schreibgeschützt."""
    from custom_components.heatnexus.const import PUROWIN_ENTITIES

    eintrag = next(d for d in PUROWIN_ENTITIES if d["oid"] == "/9/90/0")

    assert eintrag["platform"] == "sensor"
    assert eintrag["unit"] == "min"
    assert eintrag["device_class"] == "duration"


WW_IST = "/1/14/0/0/4/0"
WW_SOLL = "/1/14/0/1/4/0"
WW_HYST = "/1/14/0/5/0/0"
WW_PUMPE = "/1/14/0/1/66/0"


def _ww_abstand(sensoren, werte, **felder):
    return _entitaet(
        sensoren.WindhagerWarmwasserAbstandSensor,
        werte,
        oid=WW_IST,
        name="WW-Einschaltpunkt Delta",
        type="ww_abstand",
        soll_oid=WW_SOLL,
        hysterese_oid=WW_HYST,
        zustand_oid=WW_PUMPE,
        unit="K",
        **felder,
    )


def test_vor_der_anforderung_bleibt_der_abstand_positiv(sensoren):
    """Das Wasser muss erst unter Soll minus Hysterese fallen."""
    entity, _ = _ww_abstand(
        sensoren, {WW_IST: "50.2", WW_SOLL: "47.0", WW_HYST: "1.0", WW_PUMPE: "off"}
    )

    assert entity.native_value == 4.2


def test_waehrend_der_anforderung_zaehlt_er_positiv(sensoren):
    """Bis zum Sollwert fehlt die Differenz."""
    entity, _ = _ww_abstand(
        sensoren, {WW_IST: "48.1", WW_SOLL: "49.5", WW_HYST: "1.0", WW_PUMPE: "on"}
    )

    assert entity.native_value == 1.4


def test_am_ende_der_ladung_wird_er_negativ(sensoren):
    """Der Sollwert ist überschritten, und das soll man sehen."""
    entity, _ = _ww_abstand(
        sensoren, {WW_IST: "49.6", WW_SOLL: "49.5", WW_HYST: "1.0", WW_PUMPE: "on"}
    )

    assert entity.native_value == -0.1


def test_vor_dem_anlauf_der_pumpe_wird_er_negativ(sensoren):
    """Zwischen Unterschreiten und Anlauf liegt ein Abrufintervall."""
    entity, _ = _ww_abstand(
        sensoren, {WW_IST: "45.5", WW_SOLL: "47.0", WW_HYST: "1.0", WW_PUMPE: "off"}
    )

    assert entity.native_value == -0.5


def test_ohne_sollwert_bleibt_er_leer(sensoren):
    entity, _ = _ww_abstand(sensoren, {WW_IST: "50.2", WW_HYST: "1.0", WW_PUMPE: "off"})

    assert entity.native_value is None


def test_ohne_pumpenwert_gilt_die_wartende_phase(sensoren):
    """Die harmlosere Annahme: Es wird nicht geladen."""
    entity, _ = _ww_abstand(sensoren, {WW_IST: "50.2", WW_SOLL: "47.0", WW_HYST: "1.0"})

    assert entity.native_value == 4.2


def test_die_pumpe_wird_als_rohwert_gelesen(sensoren):
    """Die Anlage meldet 0/1; als Zahl gelesen passte der Vergleich nie."""
    entity, _ = _ww_abstand(
        sensoren, {WW_IST: "48.1", WW_SOLL: "49.5", WW_HYST: "1.0", WW_PUMPE: "1"}
    )

    assert entity.native_value == 1.4


# ---------------------------------------------------------------------------
# Der Bezug bleibt stehen, wenn nichts angefordert wird
# ---------------------------------------------------------------------------
def test_der_einschaltpunkt_bleibt_ohne_anforderung_stehen(sensoren):
    """Ohne Anforderung meldet die Anlage null; der letzte Punkt gilt weiter."""
    entity, koordinator = _schaltpunkt(sensoren, {SOLLWERT: "59.5", HYSTERESE: "16"})
    entity._bezug_merken()
    koordinator.data["oids"][SOLLWERT] = "0"
    entity._bezug_merken()

    assert entity.native_value == 51.5
    assert entity.extra_state_attributes["gehalten"] is True


def test_ohne_je_gesehenen_bezug_bleibt_der_einschaltpunkt_leer(sensoren):
    """Eine erfundene Null behauptete, die Schwelle sei jetzt erreicht."""
    entity, _ = _schaltpunkt(sensoren, {SOLLWERT: "0", HYSTERESE: "16"})
    entity._bezug_merken()

    assert entity.native_value is None
    assert entity.extra_state_attributes["gehalten"] is False


def test_ein_neuer_bezug_setzt_den_zeitpunkt_neu(sensoren):
    """Wann der Punkt zuletzt anstand, gehört zum Wert dazu."""
    entity, koordinator = _schaltpunkt(sensoren, {SOLLWERT: "59.5", HYSTERESE: "16"})
    entity._bezug_merken()
    erster = entity.extra_state_attributes["seit"]
    koordinator.data["oids"][SOLLWERT] = "57.0"
    entity._bezug_merken()

    assert entity.extra_state_attributes["seit"] >= erster
    assert entity.native_value == 49.0


def test_der_abstand_haelt_seinen_bezug_selbst(sensoren):
    """Er greift nicht auf die Nachbarentität zu – sie kann abgeschaltet sein."""
    entity, koordinator = _abstand(sensoren, {TPE: "70.0", SOLLWERT: "59.5", HYSTERESE: "16"})
    entity._bezug_merken()
    koordinator.data["oids"][SOLLWERT] = "0"
    entity._bezug_merken()

    assert entity.native_value == 18.5
    assert entity.extra_state_attributes["gehalten"] is True


def test_beide_abstaende_zaehlen_gleich_herum(sensoren):
    """Eine Automationsregel muss auf beide passen."""
    puffer, _ = _abstand(sensoren, {TPE: "54.7", SOLLWERT: "59.5", HYSTERESE: "16"})
    wasser, _ = _ww_abstand(
        sensoren, {WW_IST: "50.7", WW_SOLL: "49.5", WW_HYST: "1.0", WW_PUMPE: "off"}
    )

    assert puffer.native_value > 0
    assert wasser.native_value > 0
