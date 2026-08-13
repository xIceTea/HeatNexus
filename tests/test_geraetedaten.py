"""Was auf der Geräteseite in Home Assistant steht.

Modell, Software- und Hardwarestand und Seriennummer liefert die Anlage selbst;
die Seriennummer bildet ohnehin schon jede Entitätskennung. Als Modell darf
deshalb nicht der von Hand vergebene Name stehen, sondern die Art des Geräts.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from .conftest import ha_fehlt, requires_ha

pytestmark = requires_ha()

if not ha_fehlt():
    from custom_components.heatnexus.entity import geraet_info, steuerung_info

PREFIX = "/1/15/0"


def _coordinator(oids: dict | None = None, neuronen: dict | None = None):
    coordinator = MagicMock()
    coordinator.label = "Heizhaus"
    coordinator.data = {"oids": oids or {}}
    coordinator.client.neuron_by_node = neuronen or {}
    coordinator.client.steuerung_kennung = lambda: "steuerung-0702"
    return coordinator


def _beschreibung(**rest):
    eintrag = {
        "device_id": "0702-15-0",
        "device_name": "Nebengebäude",
        "prefix": PREFIX,
        "fct_type": 14,
    }
    eintrag.update(rest)
    return eintrag


def test_modell_sagt_was_das_geraet_ist():
    """Nicht, wie der Nutzer es genannt hat – das steht schon im Namen."""
    info = geraet_info(_coordinator(), _beschreibung())
    assert info["model"] == "Heizkreis (UML/UMLZ)"
    assert info["name"] == "Heizhaus · Nebengebäude"


def test_unbekannter_funktionstyp_nimmt_die_werksbezeichnung():
    """Was die Anlage über den Baustein sagt, schlägt jeden vergebenen Namen.

    Für Baureihen, die hier nicht stehen, ist das die einzige belastbare
    Angabe – die kuratierte Tabelle kennt sie nicht.
    """
    coordinator = _coordinator()
    coordinator.client.werksbezeichnung = {"15": "UMUMLZ"}
    assert geraet_info(coordinator, _beschreibung(fct_type=99))["model"] == "UMUMLZ"


def test_ohne_werksbezeichnung_bleibt_der_anlagenname():
    coordinator = _coordinator()
    coordinator.client.werksbezeichnung = {}
    assert geraet_info(coordinator, _beschreibung(fct_type=99))["model"] == "Nebengebäude"


def test_die_kuratierte_bezeichnung_geht_vor():
    """Sie sagt, was das Gerät *tut*; die Werksbezeichnung nur, wie es heißt."""
    coordinator = _coordinator()
    coordinator.client.werksbezeichnung = {"15": "UMUMLZ"}
    assert geraet_info(coordinator, _beschreibung())["model"] == "Heizkreis (UML/UMLZ)"


def test_seriennummer_kommt_vom_knoten():
    info = geraet_info(_coordinator(neuronen={"15": "0702ab12cd34"}), _beschreibung())
    assert info["serial_number"] == "0702ab12cd34"


def test_die_seriennummer_steht_an_jedem_geraet():
    """Nicht nur an Heizkreisen.

    Das Feld ``prefix`` führt nur die Thermostat-Beschreibung; alle übrigen
    tragen ihre Adresse allein in der OID. Ohne den Rückgriff darauf bliebe die
    Geräteseite von Kessel, Puffer und Modulen leer.
    """
    beschreibung = _beschreibung(oid="/1/15/0/0/7/0")
    beschreibung.pop("prefix")
    info = geraet_info(_coordinator(neuronen={"15": "0702ab12cd34"}), beschreibung)
    assert info["serial_number"] == "0702ab12cd34"


def test_der_softwarestand_steht_an_jedem_geraet():
    coordinator = _coordinator(oids={f"{PREFIX}/4/92/0": "V 1.11"})
    beschreibung = _beschreibung(oid=f"{PREFIX}/0/7/0")
    beschreibung.pop("prefix")
    assert geraet_info(coordinator, beschreibung)["sw_version"] == "V 1.11"


def test_software_und_hardwarestand_stehen_am_geraet():
    coordinator = _coordinator(
        oids={f"{PREFIX}/4/92/0": "V 1.11", f"{PREFIX}/4/93/0": "E1"},
    )
    info = geraet_info(coordinator, _beschreibung())
    assert info["sw_version"] == "V 1.11"
    assert info["hw_version"] == "E1"


@pytest.mark.parametrize("wert", [None, "", "   "])
def test_ohne_wert_bleibt_das_feld_leer(wert):
    """Ein leeres Feld ist ehrlich; „unbekannt" wäre eine Behauptung.

    Beim ersten Start ist die Anlage noch nicht fertig eingelesen – dann gibt
    es die Stände schlicht noch nicht.
    """
    coordinator = _coordinator(oids={f"{PREFIX}/4/92/0": wert})
    assert "sw_version" not in geraet_info(coordinator, _beschreibung())


# ---------------------------------------------------------------------------
# Die Steuerung selbst
# ---------------------------------------------------------------------------
def test_steuerung_nennt_modell_und_firmwarestand():
    """Die Steuerung kennt sich selbst – sie muss nur gefragt werden."""
    coordinator = _coordinator()
    coordinator.client.geraeteinfo = {
        "device": "MB6621",
        "version": "0.10.1",
        "serialnumber": "00100918030106159",
    }
    info = steuerung_info(coordinator)
    assert info["model"] == "MB6621"
    assert info["sw_version"] == "0.10.1"


def test_steuerung_zeigt_keine_seriennummer():
    """Die Seriennummer bleibt von der Geräteseite fern.

    Sie identifiziert die Anlage, und von dieser Seite wandern Bildschirmabzüge
    in Fehlerberichte.
    """
    coordinator = _coordinator()
    coordinator.client.geraeteinfo = {"device": "MB6621", "serialnumber": "00100918030106159"}
    assert "serial_number" not in steuerung_info(coordinator)


def test_steuerung_ohne_auskunft_bleibt_benutzbar():
    """Ältere Steuerungen beantworten den Endpunkt nicht."""
    coordinator = _coordinator()
    coordinator.client.geraeteinfo = {}
    info = steuerung_info(coordinator)
    assert info["model"] == "Steuerung"
    assert "sw_version" not in info
