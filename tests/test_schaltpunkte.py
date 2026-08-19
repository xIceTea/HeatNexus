"""Die Temperaturen, bei denen die Anlage schaltet.

Die Steuerung führt Sollwert und Hysterese getrennt; wann tatsächlich
geschaltet wird, ergibt sich erst aus beiden. Belegt am Rekorder beider
Anlagen: Die Ladung beginnt, wenn die Puffertemperatur oben unter
``Sollwert − halbe Hysterese`` fällt.

Die Zahlen hier stammen aus einer echten Anforderung: Sollwert 59,5 °C,
Hysterese 16 K, Ladung ab 51,5 °C.
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
    """Vier Pumpenstarts an zwei Anlagen treffen diese Schwelle auf ein Zehntel."""
    entity, _ = _schaltpunkt(sensoren, {SOLLWERT: "59.5", HYSTERESE: "16"})

    assert entity.native_value == 51.5


def test_die_liefernde_seite_rechnet_mit_voller_hysterese(sensoren):
    """Derselbe Parameter, andere Rolle: Der Kessel bekommt Sollwert plus Hysterese."""
    entity, _ = _entitaet(
        sensoren.WindhagerSchaltpunktSensor,
        {SOLLWERT: "57", HYSTERESE: "17"},
        oid=SOLLWERT,
        name="Anforderung liefert",
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
        name="Abstand bis Ladung",
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
    """Beim gemessenen Pumpenstart stand TPE auf 51,3 – knapp darunter."""
    entity, _ = _abstand(sensoren, {TPE: "51.3", SOLLWERT: "59.5", HYSTERESE: "16"})

    assert entity.native_value == -0.2


def test_ohne_anforderung_gibt_es_keinen_abstand(sensoren):
    """Ohne Sollwert gibt es keine Schwelle, zu der ein Abstand bestünde."""
    entity, _ = _abstand(sensoren, {TPE: "54.7", SOLLWERT: "0", HYSTERESE: "16"})

    assert entity.native_value is None
