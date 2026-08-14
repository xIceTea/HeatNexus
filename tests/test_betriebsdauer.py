"""Betriebsdauer: wie lange der Kessel läuft, gemessen an der Betriebsphase.

Der Stundenzähler der Anlage steht in ganzen Stunden und wird träge gelesen –
für einen Brand von vierzig Minuten taugt er nicht. Gemessen wird deshalb an
der Phase, und verglichen werden ihre Zahlencodes.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from .conftest import requires_ha
from .test_plattformen import _entitaet

pytestmark = requires_ha()

PHASE = "/1/60/0/2/1/0"
# 8 = Modulation (Lauf), 3 = Standby (Ruhe).
LAUF = "8"
RUHE = "3"


@pytest.fixture(scope="module")
def sensoren():
    from custom_components.heatnexus import sensor

    return sensor


def _betriebsdauer(sensoren, wert, typ="betriebsdauer"):
    entity, koordinator = _entitaet(
        sensoren.WindhagerBetriebsdauerSensor,
        {PHASE: wert},
        oid=PHASE,
        type=typ,
        name="Aktuelle Betriebsdauer",
        laufphasen=[5, 6, 7, 8, 15, 16, 17],
    )
    return entity, koordinator


def _phase(entity, koordinator, wert):
    koordinator.data["oids"][PHASE] = wert
    entity._fortschreiben()


def _vorspulen(entity, minuten):
    """Den Beginn zurückdatieren – schneller als zu warten."""
    entity._beginn = entity._beginn - timedelta(minutes=minuten)


def test_ohne_phase_gibt_es_keine_dauer(sensoren):
    entity, _ = _betriebsdauer(sensoren, None)
    entity._fortschreiben()
    assert entity.native_value is None


def test_im_stillstand_beginnt_nichts(sensoren):
    entity, _ = _betriebsdauer(sensoren, RUHE)
    entity._fortschreiben()
    assert entity.native_value == 0
    assert entity.extra_state_attributes["laeuft"] is False


def test_der_lauf_beginnt_beim_verlassen_der_ruhe(sensoren):
    entity, koordinator = _betriebsdauer(sensoren, RUHE)
    entity._fortschreiben()
    _phase(entity, koordinator, LAUF)
    _vorspulen(entity, 40)
    assert entity.native_value == pytest.approx(40, abs=0.2)
    assert entity.extra_state_attributes["laeuft"] is True


def test_die_rueckkehr_in_die_ruhe_setzt_den_laufenden_wert_auf_null(sensoren):
    """Im Verlauf entsteht so eine lesbare Sägezahnkurve."""
    entity, koordinator = _betriebsdauer(sensoren, RUHE)
    entity._fortschreiben()
    _phase(entity, koordinator, LAUF)
    _vorspulen(entity, 40)
    _phase(entity, koordinator, RUHE)
    assert entity.native_value == 0
    assert entity.extra_state_attributes["laeuft"] is False


def test_der_letzte_brand_bleibt_stehen(sensoren):
    """Die eigene Entität dafür beantwortet „wie lange lief er zuletzt"."""
    entity, koordinator = _betriebsdauer(sensoren, RUHE, typ="betriebsdauer_letzte")
    entity._fortschreiben()
    assert entity.native_value == 0
    _phase(entity, koordinator, LAUF)
    _vorspulen(entity, 40)
    # Solange er läuft, steht dort noch der Brand davor.
    assert entity.native_value == 0
    _phase(entity, koordinator, RUHE)
    assert entity.native_value == pytest.approx(40, abs=0.2)


def test_ausbrand_zaehlt_noch_zum_brand(sensoren):
    """17 ist Ausbrand – die Anlage arbeitet, also läuft die Uhr weiter."""
    entity, koordinator = _betriebsdauer(sensoren, LAUF)
    entity._fortschreiben()
    beginn = entity._beginn
    _phase(entity, koordinator, "17")
    assert entity._beginn == beginn


def test_der_tageswert_summiert_die_braende(sensoren):
    entity, koordinator = _betriebsdauer(sensoren, RUHE, typ="betriebsdauer_heute")
    entity._fortschreiben()
    for minuten in (40, 20):
        _phase(entity, koordinator, LAUF)
        _vorspulen(entity, minuten)
        _phase(entity, koordinator, RUHE)
    assert entity.native_value == pytest.approx(60, abs=0.4)


def test_der_laufende_brand_zaehlt_im_tageswert_mit(sensoren):
    entity, koordinator = _betriebsdauer(sensoren, RUHE, typ="betriebsdauer_heute")
    entity._fortschreiben()
    _phase(entity, koordinator, LAUF)
    _vorspulen(entity, 15)
    _phase(entity, koordinator, RUHE)
    _phase(entity, koordinator, LAUF)
    _vorspulen(entity, 5)
    assert entity.native_value == pytest.approx(20, abs=0.3)


def test_ein_neuer_tag_beginnt_bei_null(sensoren):
    entity, koordinator = _betriebsdauer(sensoren, RUHE, typ="betriebsdauer_heute")
    entity._fortschreiben()
    _phase(entity, koordinator, LAUF)
    _vorspulen(entity, 40)
    _phase(entity, koordinator, RUHE)
    entity._tag = "2020-01-01"
    _phase(entity, koordinator, RUHE)
    assert entity.native_value == 0


def test_der_stand_steht_im_zustand(sensoren):
    """Nur so übersteht ein angefangener Brand den Neustart."""
    entity, koordinator = _betriebsdauer(sensoren, RUHE)
    entity._fortschreiben()
    _phase(entity, koordinator, LAUF)
    attribute = entity.extra_state_attributes
    assert attribute["beginn"]
    assert attribute["tag"]


# ---------------------------------------------------------------------------
# Was der Client daraus anlegt
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    from custom_components.heatnexus import client as modul

    c = modul.WindhagerHttpClient("192.0.2.10", "geheim")
    c.devices = [
        {
            "id": "SN1-phase",
            "oid": PHASE,
            "name": "Betriebsphase",
            "enum": "2/1",
            "type": "enum_sensor",
            "device_id": "SN1-3-0",
        },
        {"id": "SN1-kessel", "oid": "/1/60/0/0/7/0", "name": "Kesseltemperatur", "unit": "°C"},
    ]
    return c


def test_die_betriebsphase_bekommt_drei_dauern(client):
    client._betriebsdauer()
    neue = {
        d["id"]: d for d in client.devices if str(d.get("type", "")).startswith("betriebsdauer")
    }
    assert set(neue) == {
        "SN1-phase-betriebsdauer",
        "SN1-phase-betriebsdauer-letzte",
        "SN1-phase-betriebsdauer-heute",
    }
    assert neue["SN1-phase-betriebsdauer"]["laufphasen"] == [5, 6, 7, 8, 15, 16, 17]
    assert all(d["enabled_default"] is False for d in neue.values())


def test_ohne_bekannte_laufphasen_entsteht_nichts(client):
    """Eine unbekannte Tabelle wird nicht geraten."""
    client.devices[0]["enum"] = "99/99"
    client._betriebsdauer()
    assert not any(str(d.get("type", "")).startswith("betriebsdauer") for d in client.devices)


def test_auch_die_waermepumpe_bekommt_ihre_dauer(client):
    """Ihre Zustandstabelle ist `50/6`: Heizen, Kühlen, Abtauen, Silentmode."""
    client.devices[0]["enum"] = "50/6"
    client._betriebsdauer()
    neue = [d for d in client.devices if str(d.get("type", "")).startswith("betriebsdauer")]
    assert len(neue) == 3
    assert neue[0]["laufphasen"] == [4, 5, 6, 7, 8, 9]
