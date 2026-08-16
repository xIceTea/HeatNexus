"""Geräte-Datenbank: Namen, Enums und Ebenen-Listen je Funktionstyp."""

from __future__ import annotations

import pytest

# Funktionstypen, die mindestens abgedeckt sein müssen
FCT_HEIZKREIS = 14
FCT_PUFFER = 16
FCT_PUROWIN = 25
FCT_BIOWIN = 9
FCT_ZUSATZKESSEL = 10  # LogWIN und andere Automatikkessel


def test_names_resolve(device_db):
    assert device_db.get_name("0/0") == "Aussentemperatur"


def test_unknown_name_is_none(device_db):
    assert device_db.get_name("999/999") is None


def test_enum_keys_are_ints(device_db):
    enum = device_db.get_enum("3/50")
    assert enum
    assert all(isinstance(k, int) for k in enum)


# Die dreizehn Tabellen, die bis 1.5.0 zusätzlich von Hand in `const.ENUMS`
# standen. Sie sind dort entfernt worden – die Geräte-Datenbank muss sie also
# liefern, sonst stünden Betriebsphase, Betriebswahl und Brennstoff plötzlich
# als nackte Zahlen da.
FRUEHER_KURATIERT = (
    "2/1",
    "2/9",
    "2/59",
    "3/50",
    "20/15",
    "7/12",
    "14/19",
    "38/126",
    "38/127",
    "39/94",
    "43/34",
    "9/75",
    "39/76",
)


@pytest.mark.parametrize("gnmn", FRUEHER_KURATIERT)
def test_die_frueher_kuratierten_tabellen_kommen_aus_der_datenbank(device_db, gnmn):
    """Was aus `const.ENUMS` verschwunden ist, muss hier ankommen."""
    tabelle = device_db.get_enum(gnmn)
    assert tabelle, f"{gnmn} liefert keine Auswahlwerte mehr"
    assert all(isinstance(k, int) for k in tabelle)
    assert all(v.strip() for v in tabelle.values())


def test_enum_texte_tragen_keine_leerzeichen(device_db):
    """In der Herstellerdatei hängt an einzelnen Texten ein Leerzeichen.

    `39/76` „Fehler Vorratsbehälter " ist der bekannte Fall. Als Zustand einer
    Entität wäre das sichtbar, und ein Vergleich in einer Automation ginge
    daneben, ohne dass jemand sieht warum.
    """
    for wert in device_db.get_enum("39/76").values():
        assert wert == wert.strip(), repr(wert)


def test_die_kuratierte_tabelle_wiederholt_die_erzeugte_nicht():
    """`const.ENUMS` ist für Abweichungen da, nicht für Kopien.

    Bis 1.5.0 standen dort dreizehn Tabellen, die Wort für Wort schon in der
    Geräte-Datenbank standen. Zwei Quellen für dieselbe Auskunft laufen
    auseinander; welche dann gilt, sieht man dem Code nicht an. Wer hier
    einträgt, muss also wirklich abweichen.
    """
    import importlib.util
    import json
    from pathlib import Path

    wurzel = Path(__file__).parent.parent / "custom_components" / "heatnexus"
    spec = importlib.util.spec_from_file_location("const_pruef", wurzel / "const.py")
    const = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(const)
    erzeugt = json.loads((wurzel / "device_db.json").read_text(encoding="utf-8"))["enums"]

    doppelt = [
        schluessel
        for schluessel, tabelle in const.ENUMS.items()
        if tabelle == {int(k): str(v).strip() for k, v in (erzeugt.get(schluessel) or {}).items()}
    ]
    assert doppelt == [], f"identisch zur Geräte-Datenbank, gehört gelöscht: {doppelt}"


@pytest.mark.parametrize(
    "fct", [FCT_HEIZKREIS, FCT_PUFFER, FCT_PUROWIN, FCT_BIOWIN, FCT_ZUSATZKESSEL]
)
def test_layers_present(device_db, fct):
    layers = device_db.get_layers(fct)
    assert layers, f"Funktionstyp {fct} fehlt in der Geräte-DB"
    assert layers.get("info"), f"Funktionstyp {fct} ohne Infoebene"


def test_layer_entries_are_gn_mn(device_db):
    for gnmn in device_db.get_layers(FCT_PUROWIN)["operate"]:
        gn, _, mn = gnmn.partition("/")
        assert gn.isdigit() and mn.isdigit(), gnmn


# ---------------------------------------------------------------------------
# Erzeugte Referenz
#
# `docs/_includes/DATAPOINTS.md` und `docs/_includes/ENUMS.md` werden aus `device_db.json` erzeugt.
# Ohne diesen Test fällt niemandem auf, dass sie nach einem neuen Datenbestand
# veraltet sind – und eine veraltete Referenz ist schlimmer als keine.
# ---------------------------------------------------------------------------
def test_datenpunkt_referenz_ist_aktuell():
    import importlib.util
    import json
    from pathlib import Path

    wurzel = Path(__file__).parent.parent
    pfad = wurzel / "tools" / "build_datenpunkte_doku.py"
    spec = importlib.util.spec_from_file_location("doku", pfad)
    doku = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(doku)

    db = json.loads(doku.DB.read_text(encoding="utf-8"))
    for ziel, erzeugt in (
        (doku.ZIEL_DATENPUNKTE, doku.datenpunkte(db)),
        (doku.ZIEL_ENUMS, doku.enums(db)),
    ):
        assert ziel.exists(), f"{ziel.name} fehlt"
        assert ziel.read_text(encoding="utf-8") == erzeugt, (
            f"{ziel.name} passt nicht zur Geräte-Datenbank. "
            "Abhilfe: python tools/build_datenpunkte_doku.py"
        )


def test_jeder_funktionstyp_hat_einen_namen():
    """Ein Funktionstyp ohne Namen steht als „unbekannt" in der Referenz."""
    import importlib.util
    import json
    from pathlib import Path

    pfad = Path(__file__).parent.parent / "tools" / "build_datenpunkte_doku.py"
    spec = importlib.util.spec_from_file_location("doku", pfad)
    doku = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(doku)

    db = json.loads(doku.DB.read_text(encoding="utf-8"))
    ohne = sorted(set(db["layers"]) - set(doku.FUNKTIONEN), key=int)
    assert not ohne, f"Funktionstypen ohne Namen: {ohne}"


def test_der_zusatzkessel_kann_bedient_werden(device_db):
    """Die Betriebswahl steht in keiner Ebenenliste des Herstellers.

    Ohne Eintrag zählt sie als Werksebene und ist damit unsichtbar – der
    Schalter, mit dem der Kessel überhaupt bedient wird.
    """
    ebenen = device_db.get_layers(FCT_ZUSATZKESSEL)

    assert "9/75" in ebenen["operate"]
    assert "2/0" in ebenen["info"]
