"""Anlagenschaubild: Aufbau der Grafik und Lage der Beschriftungen."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import unquote
from xml.etree import ElementTree

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def schema():
    """Das Modul kommt ohne Home Assistant aus und wird direkt geladen."""
    return load_standalone("schema")


@pytest.fixture(scope="module")
def farben(schema):
    return schema.farben


@pytest.fixture(scope="module")
def werte(schema):
    return schema.werte


@pytest.fixture(scope="module")
def bauteile(schema):
    return schema.bauteile


@pytest.fixture(scope="module")
def zeichnung(schema):
    return schema.zeichnung


@pytest.fixture(scope="module")
def karte(schema):
    return schema.karte


def _teil(name: str, fct: int, werte: list[tuple[str, str]]) -> dict:
    return {
        "name": name,
        "fct_type": fct,
        "entitaeten": [
            {
                "entity_id": eid,
                "name": n,
                "hat_wert": True,
                "bereich": eid.split(".")[0],
            }
            for eid, n in werte
        ],
    }


@pytest.fixture
def anlage():
    return [
        _teil(
            "PuroWIN",
            25,
            [("sensor.kessel_ist", "Kesseltemperatur Ist"), ("sensor.leistung", "Kesselleistung")],
        ),
        _teil(
            "B-PLMi PUFFER",
            16,
            [
                ("sensor.tpe", "Puffer oben Temperatur (TPE)"),
                ("sensor.tpa", "Puffer unten Temperatur (TPA)"),
            ],
        ),
    ]


def test_das_beispielbild_im_readme_ist_aktuell():
    """Das Bild in `assets/` muss zur heutigen Zeichnung passen.

    Es war einmal von Hand zusammengesetzt worden und stand danach vier
    Fassungen lang unverändert im README, während sich die Zeichnung
    weiterentwickelte. Wer es aufschlug, sah einen Stand, den die Integration
    längst nicht mehr ausliefert – und niemandem fiel es auf.
    """
    import importlib.util
    from pathlib import Path

    pfad = Path(__file__).parent.parent / "tools" / "build_schaubild_beispiel.py"
    spec = importlib.util.spec_from_file_location("schaubild_beispiel", pfad)
    werkzeug = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(werkzeug)

    karte = werkzeug._schema().anlagenschema(werkzeug.BEISPIEL)
    for ziel, farbsatz in (
        (werkzeug.ZIEL_DUNKEL, "dunkel"),
        (werkzeug.ZIEL_HELL, "hell"),
    ):
        assert ziel.exists(), f"{ziel.name} fehlt"
        assert ziel.read_text(encoding="utf-8") == werkzeug.bild(karte, farbsatz), (
            f"{ziel.name} passt nicht zur heutigen Zeichnung. "
            "Abhilfe: python tools/build_schaubild_beispiel.py"
        )


def test_der_mischer_laesst_sich_aus_der_zeichnung_nehmen(karte):
    """Das Stellglied steckt in der Zeichnung, nicht in einer Überlagerung."""
    teil = _teil(
        "UML Heizkreis",
        14,
        [("sensor.vorlauf", "Vorlauftemperatur Ist"), ("sensor.mischer", "Mischer Stellwert")],
    )
    mit = karte.anlagenschema([teil])
    ohne = karte.anlagenschema([teil], mischer=False)
    assert "M 86 104" in mit["svg"]
    assert "M 86 104" not in ohne["svg"]


def test_das_schaubild_entsteht_auch_ohne_deutsche_namen(karte):
    """Der Zweck der kanonischen Schlüssel, hier fürs Schaubild.

    Liefert die Anlage englische Namen, greift kein Muster mehr – das Bild
    hätte dann Kästen ohne Werte. Die Adresse bleibt dieselbe, also muss sie
    allein genügen.
    """

    def fremd(eid: str, name: str, schluessel: str) -> dict:
        return {
            "entity_id": eid,
            "name": name,
            "hat_wert": True,
            "bereich": eid.split(".")[0],
            "schluessel": schluessel,
        }

    teile = [
        {
            "name": "PuroWIN",
            "fct_type": 25,
            "entitaeten": [
                fremd("sensor.boiler_temperature", "Boiler temperature", "boiler_temperature"),
                fremd("sensor.boiler_power", "Boiler output", "boiler_power"),
            ],
        },
        {
            "name": "Buffer",
            "fct_type": 16,
            "entitaeten": [
                fremd("sensor.buffer_top", "Buffer top", "buffer_top"),
                fremd("sensor.buffer_bottom", "Buffer bottom", "buffer_bottom"),
            ],
        },
    ]

    karte = karte.anlagenschema(teile)

    assert {e["entity"] for e in karte["elements"]} == {
        "sensor.boiler_temperature",
        "sensor.boiler_power",
        "sensor.buffer_top",
        "sensor.buffer_bottom",
    }


def test_karte_ist_ein_bild_mit_beschriftungen(karte, anlage):
    karte = karte.anlagenschema(anlage)
    assert karte["type"] == "picture-elements"
    assert karte["image"].startswith("data:image/svg+xml;base64,")
    assert karte["dark_mode_image"].startswith("data:image/svg+xml;base64,")
    # Je Anlagenteil zwei Werte.
    assert len(karte["elements"]) == 4
    assert {e["entity"] for e in karte["elements"]} == {
        "sensor.kessel_ist",
        "sensor.leistung",
        "sensor.tpe",
        "sensor.tpa",
    }


def test_bild_enthaelt_die_namen(karte, anlage):
    karte = karte.anlagenschema(anlage)
    svg = base64.b64decode(karte["dark_mode_image"].split(",", 1)[1]).decode("utf-8")
    assert svg.startswith("<svg")
    assert "PuroWIN" in svg
    assert "B-PLMi PUFFER" in svg
    assert "</svg>" in svg


def test_beschriftungen_liegen_im_bild(karte, anlage):
    for element in karte.anlagenschema(anlage)["elements"]:
        for achse in ("top", "left"):
            anteil = float(element["style"][achse].rstrip("%"))
            assert 0 < anteil < 100


def test_ohne_messwerte_kein_schaubild(karte):
    assert karte.anlagenschema([]) is None
    ohne = [_teil("ZSP-1", 20, [("sensor.x", "Pumpendrehzahl")])]
    assert karte.anlagenschema(ohne) is None


def test_spitze_klammern_im_namen_zerlegen_das_bild_nicht(karte):
    teil = _teil("Kessel <b>", 25, [("sensor.k", "Kesseltemperatur Ist")])
    karte = karte.anlagenschema([teil])
    svg = base64.b64decode(karte["dark_mode_image"].split(",", 1)[1]).decode("utf-8")
    assert "<b>" not in svg
    assert "&lt;b&gt;" in svg


def test_schaubild_entsteht_auch_ohne_werte(karte, anlage):
    """Beim ersten Aufbau ist die Anlage noch nicht eingelesen.

    Verlangte das Schaubild einen vorhandenen Wert, bliebe der Reiter „Anlage"
    dauerhaft leer – der Fehler aus 1.0.0.
    """
    for teil in anlage:
        for eintrag in teil["entitaeten"]:
            eintrag["hat_wert"] = False

    bild = karte.anlagenschema(anlage)
    assert bild is not None
    assert len(bild["elements"]) == 4


def test_anlagenteil_ohne_passenden_messwert_faellt_weg(karte):
    """Ein leerer Kasten hilft niemandem."""
    ohne = [{"name": "Rätsel", "fct_type": 99, "entitaeten": []}]
    assert karte.anlagenschema(ohne) is None


# ---------------------------------------------------------------------------
# Warmwasser als eigener Anlagenteil
#
# In 1.1.0-beta.6/7 fehlte der Warmwasserbehälter im Schaubild, obwohl die
# Anlage ihn liefert. Grund war ein Steuerzeichen im Suchmuster: Beim Erzeugen
# der Datei war aus der Wortgrenze `\b` ein echtes Backspace-Zeichen geworden.
# Im Quelltext war das nicht zu sehen – nur im Verhalten.
# ---------------------------------------------------------------------------
def test_muster_enthalten_keine_steuerzeichen(werte):
    """Ein Suchmuster darf nie ein Steuerzeichen enthalten."""
    muster = [werte.WARMWASSER_IST, werte.ZIRKULATION_IST]
    muster += [m for eintraege in werte.WERTE_JE_ART.values() for m, _, _ in eintraege]
    muster += [m for m, _ in werte.PUMPE_JE_ART.values()]
    muster += [m for m, _ in werte.MODUL_AUFGABE]
    for einzeln in muster:
        assert not any(ord(z) < 32 for z in einzeln), f"Steuerzeichen in {einzeln!r}"


def test_warmwasser_wird_eigener_anlagenteil(werte):
    heizkreis = _teil(
        "UMLZ HEIZKREIS",
        14,
        [
            ("sensor.vorlauf", "Vorlauftemperatur Ist"),
            ("sensor.raum", "Raumtemperatur Ist"),
            ("sensor.ww_ist", "Warmwasser Ist-Temperatur"),
            ("sensor.ww_soll", "Warmwasser Soll-Temperatur"),
            ("binary_sensor.ww_ladepumpe", "WW-Ladepumpe"),
        ],
    )
    arten = [m["art"] for m in werte.zeichenbare_module([heizkreis])]
    assert "wasser" in arten, "Warmwasser fehlt im Schaubild"


def test_ohne_warmwasser_kein_eigener_anlagenteil(werte):
    heizkreis = _teil(
        "Suedbau",
        14,
        [("sensor.vorlauf", "Vorlauftemperatur Ist"), ("sensor.raum", "Raumtemperatur Ist")],
    )
    arten = [m["art"] for m in werte.zeichenbare_module([heizkreis])]
    assert "wasser" not in arten


def test_pumpe_je_anlagenteil(werte):
    heizkreis = _teil(
        "UMLZ HEIZKREIS",
        14,
        [
            ("sensor.raum", "Raumtemperatur Ist"),
            ("sensor.vorlauf", "Vorlauftemperatur Ist"),
            ("binary_sensor.hkp", "Heizkreispumpe"),
        ],
    )
    module = werte.zeichenbare_module([heizkreis])
    assert module[0]["pumpe"] == "binary_sensor.hkp"


@pytest.mark.parametrize(
    ("fct", "messwert", "name", "schluessel"),
    [
        (16, "buffer_top", "Buffer charge pump speed", "buffer_charge_pump"),
        (9, "boiler_temperature", "Heat generator pump", "boiler_pump"),
        (5, "collector_temperature", "Solar pump speed", "pump_speed"),
    ],
)
def test_die_pumpe_wird_auch_ohne_deutschen_namen_gefunden(werte, fct, messwert, name, schluessel):
    """Kessel-, Puffer- und Solarpumpe tragen einen Schlüssel; der Name genügt nicht."""
    teil = {
        "name": "Teil",
        "fct_type": fct,
        "entitaeten": [
            {
                "entity_id": "sensor.t",
                "name": "Temperature",
                "hat_wert": True,
                "bereich": "sensor",
                "schluessel": messwert,
            },
            {
                "entity_id": "sensor.pumpe",
                "name": name,
                "hat_wert": True,
                "bereich": "sensor",
                "schluessel": schluessel,
            },
        ],
    }
    module = werte.zeichenbare_module([teil], modulpumpe=True)
    assert module and module[0]["pumpe"] == "sensor.pumpe"


def _pumpenmodul():
    return _teil(
        "ZSP",
        20,
        [
            ("sensor.zsp_drehzahl", "Pumpendrehzahl"),
            ("sensor.zsp_anforderung", "Ext. Wärmeanforderung"),
        ],
    )


def test_modulpumpe_bleibt_ohne_angabe_weg(schema, werte):
    """Ohne bestätigte Pumpe bleibt das Modul im Bild, seine Pumpenmarke nicht."""
    module = werte.zeichenbare_module([_pumpenmodul()])
    assert module[0]["art"] == "pumpenmodul"
    assert module[0]["pumpe"] is None


def test_bestaetigte_modulpumpe_steht_im_bild(schema, werte):
    module = werte.zeichenbare_module([_pumpenmodul()], modulpumpe=True)
    assert module[0]["pumpe"] == "sensor.zsp_drehzahl"


def test_abwahl_trifft_nur_das_pumpenmodul(schema, werte):
    heizkreis = _teil(
        "UMLZ HEIZKREIS",
        14,
        [
            ("sensor.raum", "Raumtemperatur Ist"),
            ("binary_sensor.hkp", "Heizkreispumpe"),
        ],
    )
    module = werte.zeichenbare_module([heizkreis, _pumpenmodul()], modulpumpe=False)
    assert module[0]["pumpe"] == "binary_sensor.hkp"
    assert module[1]["pumpe"] is None


# ---------------------------------------------------------------------------
# Bauteildateien
#
# Die Anlagenteile werden aus SVG-Dateien in `anlagenteile/` zusammengesetzt.
# Zwei Dinge dürfen dabei nie passieren: ein stehengebliebener Farbplatzhalter
# (dann steht `{{korpus}}` als Farbe im Bild und der Browser zeichnet gar
# nichts) und doppelte Kennungen (dann teilen sich zwei Puffer denselben
# Verlauf und einer bleibt leer).
# ---------------------------------------------------------------------------
def _svg_von(karte, teile, kesselart=None) -> str:
    """Die dunkle Fassung – sie ist die gezeichnete, die helle entsteht daraus."""
    karte = karte.anlagenschema(teile, kesselart)
    return base64.b64decode(karte["dark_mode_image"].split(",", 1)[1]).decode("utf-8")


def test_jedes_bauteil_hat_eine_datei(werte, bauteile):
    """Für jede gezeichnete Art gibt es eine Datei – sonst greift der Rückfall."""
    for art in werte.ALLE_ARTEN:
        assert bauteile.bauteil(f"{art}.svg") is not None, f"anlagenteile/{art}.svg fehlt"


def test_bauteildateien_sind_bruchstuecke_ohne_platzhalterreste(farben, bauteile):
    for pfad in sorted(bauteile.TEILE_ORDNER.glob("*.svg")):
        inhalt = pfad.read_text(encoding="utf-8")
        assert "<svg" not in inhalt, f"{pfad.name} ist ein ganzes Bild, kein Bruchstück"
        assert "<image" not in inhalt, f"{pfad.name} verweist auf eine fremde Datei"
        assert "<script" not in inhalt, f"{pfad.name} enthält ein Script"
        # Erlaubt sind nur Weiß und Schwarz: Sie liegen mit kleiner Deckkraft
        # als Licht und Schatten über einer Form und sind damit unabhängig von
        # der Farbe darunter. Alles andere gehört als Platzhalter in FARBEN.
        feste = set(re.findall(r"#[0-9a-fA-F]{3,8}\b", inhalt)) - {"#ffffff", "#000000"}
        assert not feste, f"{pfad.name} enthält feste Farben statt Platzhaltern: {feste}"
        offen = re.findall(r"\{\{(\w+)\}\}", inhalt)
        # Neben den Farben gibt es Platzhalter, die vom Zustand der Anlage
        # abhängen und deshalb je Bauteil eingesetzt werden. Sie sind in
        # `ZUSATZ_PLATZHALTER` benannt – alles andere ist ein Tippfehler.
        unbekannt = set(offen) - set(farben.FARBEN) - bauteile.ZUSATZ_PLATZHALTER
        assert not unbekannt, f"{pfad.name} nutzt unbekannte Platzhalter: {unbekannt}"


def test_bild_ist_wohlgeformt_und_ohne_platzhalter(schema, anlage):
    svg = _svg_von(schema, anlage)
    ElementTree.fromstring(svg)
    assert "{{" not in svg


def test_kennungen_bleiben_eindeutig(schema):
    """Zwei Puffer im selben Bild dürfen sich keinen Verlauf teilen."""
    zwei = [
        _teil("Puffer A", 16, [("sensor.a1", "Puffer oben"), ("sensor.a2", "Puffer unten")]),
        _teil("Puffer B", 16, [("sensor.b1", "Puffer oben"), ("sensor.b2", "Puffer unten")]),
    ]
    # Und verschiedene Bauteile, die dieselben Namen mitbringen: `puffer.svg`
    # und `wasser.svg` führen beide `glanz` und `innen`. Ohne Präfix griffe
    # der Boiler auf den Beschnitt des Puffers zu – und stünde als Rechteck
    # im Bild statt als Oval.
    gemischt = [
        _teil("Puffer", 16, [("sensor.o", "Puffer oben"), ("sensor.u", "Puffer unten")]),
        _teil(
            "Heizkreis",
            14,
            [
                ("sensor.vl", "Vorlauftemperatur Ist"),
                ("sensor.raum", "Raumtemperatur Ist"),
                ("sensor.ww", "Warmwasser Ist-Temperatur"),
            ],
        ),
    ]
    for teile in (zwei, gemischt):
        svg = _svg_von(schema, teile)
        kennungen = re.findall(r'id="([^"]+)"', svg)
        assert kennungen, "keine Kennungen im Bild – Bauteildateien nicht geladen?"
        assert len(kennungen) == len(set(kennungen)), "doppelte Kennung im Bild"
        # Und jeder Verweis zeigt auf eine Kennung, die es auch gibt. Das
        # schließt `clip-path="url(#…)"` ein.
        for verweis in re.findall(r"url\(#([^)]+)\)", svg):
            assert verweis in kennungen


def test_fehlende_bauteildatei_zerreisst_das_bild_nicht(schema, bauteile, anlage, monkeypatch):
    monkeypatch.setattr(bauteile, "bauteil", lambda dateiname: None)
    svg = _svg_von(schema, anlage)
    ElementTree.fromstring(svg)
    assert "PuroWIN" in svg


# ---------------------------------------------------------------------------
# Kesselart
# ---------------------------------------------------------------------------
def test_kesselart_kommt_aus_dem_gemeldeten_brennstoff(werte):
    kessel = _teil("Kessel", 25, [("sensor.k", "Kesseltemperatur Ist")])
    kessel["entitaeten"].append(
        {
            "entity_id": "sensor.brennstoff",
            "name": "Aktueller Brennstoff",
            "bereich": "sensor",
            "hat_wert": True,
            "text": "Hackgut feucht schlackend",
        }
    )
    assert werte.kesselart_erkennen([kessel]) == "hackgut"

    kessel["entitaeten"][-1]["text"] = "Pellets"
    assert werte.kesselart_erkennen([kessel]) == "pellets"


def test_kesselart_faellt_auf_den_namen_zurueck(werte):
    assert werte.kesselart_erkennen([_teil("PuroWIN 40", 25, [])]) == "hackgut"
    assert werte.kesselart_erkennen([_teil("BioWIN 2", 25, [])]) == "pellets"
    assert werte.kesselart_erkennen([_teil("AeroWIN", 25, [])]) == "waermepumpe"


def test_kesselart_raet_nicht(werte):
    """Sagt weder Brennstoff noch Name etwas, wird neutral gezeichnet."""
    assert werte.kesselart_erkennen([_teil("Waermeerzeuger", 25, [])]) is None
    assert werte.kesselart_erkennen([_teil("PuroWIN", 16, [])]) is None


def test_kesselart_waehlt_die_zeichnung(schema):
    kessel = [_teil("Kessel", 25, [("sensor.k", "Kesseltemperatur Ist")])]
    hackgut = _svg_von(schema, kessel, "hackgut")
    pellets = _svg_von(schema, kessel, "pellets")
    neutral = _svg_von(schema, kessel, None)
    assert hackgut != pellets != neutral


def test_unbekannte_kesselart_faellt_auf_die_neutrale_zeichnung(schema):
    kessel = [_teil("Kessel", 25, [("sensor.k", "Kesseltemperatur Ist")])]
    assert _svg_von(schema, kessel, "gibtsnicht") == _svg_von(schema, kessel, None)


# ---------------------------------------------------------------------------
# Funktionstypen
#
# Aus Namen abgeleitet gerät die Zuordnung falsch; sie stammt aus der
# Parameterliste des Herstellers. Hier wird sie festgehalten, damit sie
# niemand versehentlich zurückdreht.
# ---------------------------------------------------------------------------
def test_funktionstypen_stimmen_mit_der_parameterliste_ueberein(werte):
    erwartet = {
        1: "heizkreis",  # Heizkurve, Kühlgrenzen, Estrichprogramm
        2: "wasser",  # WW-Programm, Hygiene-Programm, Zirkulationspumpe
        4: "umschaltung",  # Weiche, Folgeschaltung, Zusatzkessel ZSK
        5: "solar",  # Kollektortemperatur, Kollektor spülen
        6: "kessel",  # Gas/Öl: Ionisationsstrom, Anlagendruck
        7: "kessel",  # Wärmepumpe: COP, Silentmode
        8: "kessel",  # E-Heizung: Stufen 1..3
        9: "kessel",  # BioWIN
        10: "kessel",  # Automatikkessel
        13: "solar",  # „Solar ES", von der Anlage selbst benannt
        14: "heizkreis",
        15: "umschaltung",  # Automatikkessel / Festbrennstoff / Puffer
        16: "puffer",
        20: "pumpenmodul",  # ZSP
        21: "puffer",
        24: "pumpenmodul",  # Pumpe Wärmeerzeuger, Schichtladung
        25: "kessel",  # PuroWIN
        26: "kessel",  # Wärmepumpe
        27: "kessel",  # Wärmepumpe
    }
    assert erwartet == werte.ART_JE_FCT
    assert werte.KESSELART_JE_FCT == {
        6: "gas_oel",
        7: "waermepumpe",
        26: "waermepumpe",
        27: "waermepumpe",
    }


def test_warmwasser_und_zirkulation_in_beiden_schreibweisen(werte):
    """Kuratierte Tabelle und Geräte-Datenbank benennen dieselben Werte anders."""
    import re

    for name in ("Warmwasser Ist-Temperatur", "WW-Temperatur Aktueller Wert"):
        assert re.search(werte.WARMWASSER_IST, name, re.IGNORECASE), name
    for name in ("WW-Zirkulation Ist-Temperatur", "WW-Zirkulationstemperatur Aktueller Wert"):
        assert re.search(werte.ZIRKULATION_IST, name, re.IGNORECASE), name
    # Der Sollwert darf nicht als Istwert durchgehen.
    assert not re.search(werte.ZIRKULATION_IST, "WW-Zirkulationstemperatur Sollwert", re.IGNORECASE)


def test_puffer_in_beiden_schreibweisen(werte):
    for namen in (
        [("sensor.o", "Puffer oben Temperatur (TPE)"), ("sensor.u", "Puffer unten Temperatur")],
        [("sensor.o", "Puffertemperatur oben"), ("sensor.u", "Puffertemperatur unten")],
        [("sensor.o", "Puffertemperatur TPE"), ("sensor.u", "Puffertemperatur TPA")],
    ):
        module = werte.zeichenbare_module([_teil("Puffer", 16, namen)])
        assert len(module[0]["werte"]) == 2, namen


def test_waermepumpe_ist_ein_waermeerzeuger(werte):
    """Eine Wärmepumpe steht an der Stelle des Kessels, nicht daneben."""
    for fct in (26, 27):
        assert werte.ART_JE_FCT[fct] == "kessel"
    # Und sie braucht weder Brennstoff noch sprechenden Namen.
    stumm = _teil("Modul 26", 26, [("sensor.k", "Kesseltemperatur Ist")])
    assert werte.kesselart_erkennen([stumm]) == "waermepumpe"


def test_zsp_und_zirkulation_sehen_verschieden_aus(werte, bauteile):
    """Ein Pumpenmodul ist kein Zirkulationskreis.

    Beide hingen bis 1.2.0 an derselben Zeichnung; im Schaubild einer Anlage
    mit beidem standen zwei gleiche Kreise nebeneinander.
    """
    zsp = _teil("ZSP-2", 20, [("sensor.t", "Temperatur Ist")])
    heizkreis = _teil(
        "UMLZ HEIZKREIS",
        14,
        [
            ("sensor.vorlauf", "Vorlauftemperatur Ist"),
            ("sensor.raum", "Raumtemperatur Ist"),
            ("sensor.zirk", "WW-Zirkulation Ist-Temperatur"),
        ],
    )
    arten = [m["art"] for m in werte.zeichenbare_module([zsp, heizkreis])]
    assert "pumpenmodul" in arten
    assert "zirkulation" in arten
    assert bauteile.bauteil("pumpenmodul.svg") != bauteile.bauteil("zirkulation.svg")


def test_zsp_meldet_seine_pumpe_ueber_die_drehzahl(werte):
    """Das ZSP hat keinen Pumpenzustand, nur „Pumpendrehzahl" in Prozent."""
    zsp = _teil(
        "ZSP-2",
        20,
        [("sensor.t", "Temperatur Ist"), ("sensor.dz", "Pumpendrehzahl")],
    )
    assert werte.zeichenbare_module([zsp], modulpumpe=True)[0]["pumpe"] == "sensor.dz"


def test_heizkoerper_haengt_an_der_vorlauftemperatur(karte):
    """Der Heizkörper färbt sich nach dem Istwert, nicht nach dem Sollwert.

    Der Sollwert steht auch dann auf seinem Wert, wenn der Kreis abgeschaltet
    ist und der Körper kalt an der Wand hängt.
    """
    kreis = _teil(
        "UMLZ",
        14,
        [
            ("sensor.soll", "Vorlauftemperatur Soll"),
            ("sensor.ist", "Vorlauftemperatur Ist"),
            ("sensor.raum", "Raumtemperatur Ist"),
        ],
    )
    bild = karte.anlagenschema([kreis])
    koerper = bild["heizkoerper"]
    assert len(koerper) == 1
    assert koerper[0]["entity"] == "sensor.ist"
    # Die Skala muss aufsteigen, sonst teilt die Ansicht durch null.
    assert koerper[0]["kalt"] < koerper[0]["heiss"]


def test_heizkoerper_raster_passt_zur_zeichnung(zeichnung, karte):
    """Das Streifenmuster muss in Anteilen kommen, nicht in Bildpunkten.

    Die Karte skaliert das Schaubild auf ihre eigene Breite. In 1.4.0 stand das
    Raster als feste Bildpunktwerte im Stylesheet: Nach der Skalierung saßen
    die Streifen neben den gezeichneten Gliedern, und dazwischen blitzte die
    rote Füllung der Zeichnung durch – der Heizkörper war blau-rot gestreift.

    Geprüft wird zweierlei: Die Angaben sind Prozentwerte, und fünf Glieder
    füllen die Ebene genau aus (5 × Raster − Abstand = Breite).
    """
    kreis = _teil("UMLZ", 14, [("sensor.ist", "Vorlauftemperatur Ist")])
    eintrag = karte.anlagenschema([kreis])["heizkoerper"][0]

    for feld in ("glied", "raster", "glanz_von", "glanz_bis"):
        assert eintrag[feld].endswith("%"), f"{feld} muss ein Anteil sein, ist {eintrag[feld]!r}"

    anteil = lambda feld: float(eintrag[feld].rstrip("%"))  # noqa: E731
    assert anteil("glied") < anteil("raster")
    assert anteil("glanz_von") < anteil("glanz_bis") <= anteil("glied")
    # Die Glieder im Raster ergeben genau die Breite der Ebene.
    assert eintrag["anzahl"] == zeichnung.HEIZKOERPER_ANZAHL
    assert (
        zeichnung.HEIZKOERPER_ANZAHL * zeichnung.HEIZKOERPER_RASTER
        - (zeichnung.HEIZKOERPER_RASTER - zeichnung.HEIZKOERPER_GLIED)
        == zeichnung.HEIZKOERPER_BREITE
    )
    # Das letzte Glied darf nicht über die Ebene hinausragen.
    assert anteil("raster") * (zeichnung.HEIZKOERPER_ANZAHL - 1) + anteil("glied") <= 100.0001


def test_puffer_schichtung_braucht_beide_fuehler(karte, anlage):
    """Oben und unten sind gemessen – mit nur einem wird nichts gezeichnet.

    Ein erfundener zweiter Wert wäre schlimmer als keine Schichtung: Der
    Speicher sähe halb geladen aus, ohne dass es jemand gemessen hat.
    """
    bild = karte.anlagenschema(anlage)
    schicht = bild["schichtung"]
    assert len(schicht) == 1
    assert schicht[0]["oben"] == "sensor.tpe"
    assert schicht[0]["unten"] == "sensor.tpa"
    assert schicht[0]["kalt"] < schicht[0]["heiss"]

    nur_oben = [
        _teil("PuroWIN", 25, [("sensor.k", "Kesseltemperatur Ist")]),
        _teil("Puffer", 16, [("sensor.tpe", "Puffer oben Temperatur (TPE)")]),
    ]
    assert karte.anlagenschema(nur_oben)["schichtung"] == []


def test_puffer_zeichnung_ist_neutral(bauteile):
    """Auch der Speicher darf unter der Ebene keine feste Schichtung tragen."""
    datei = bauteile.bauteil("puffer.svg")
    assert datei is not None
    assert "{{warm}}" not in datei
    assert "{{kalt}}" not in datei


def test_heizkoerper_zeichnung_ist_neutral(bauteile):
    """Unter der farbigen Ebene darf kein Rot liegen.

    Bis 1.4.1 füllte die Zeichnung die Glieder mit einem Verlauf von Glut nach
    Warm. An den runden Enden schimmerte er unter der Ebene hervor: Ein
    Heizkreis mit 27 °C Vorlauf hatte rote Ecken.
    """
    datei = bauteile.bauteil("heizkreis.svg")
    assert datei is not None
    assert "{{glut}}" not in datei
    assert "{{warm}}" not in datei


def test_ohne_vorlaufmessung_kein_gefaerbter_heizkoerper(karte):
    """Ohne Messwert bleibt es bei der Zeichnung – geraten wird nicht."""
    kreis = _teil("UMLZ", 14, [("sensor.raum", "Raumtemperatur Ist")])
    assert karte.anlagenschema([kreis])["heizkoerper"] == []


def test_zsp_ohne_aufgabe_kommt_nicht_ins_schaubild(werte):
    """Ein Pumpenmodul, an dem nichts hängt, gehört nicht in die Leitung.

    Ein unbenutztes Modul meldet nur Sollwerte (``0/95`` Analog-Sollwert,
    ``9/57`` Solltemperatur ext. Wärmeanforderung, ``20/23`` Digital-Sollwert
    WWK) und den Aktorentest. Kesseltemperatur, Pumpendrehzahl und die ganze
    Gruppe 29 beantwortet die Anlage dann nicht – dasselbe Bauteil im Betrieb
    liefert ``0/7``, ``0/22`` und die externe Wärmeanforderung.
    """
    ohne_aufgabe = _teil(
        "ZSP-2",
        20,
        [
            ("sensor.analog", "Analog-Sollwert"),
            ("number.ext", "Solltemperatur ext. Wärmeanforderung"),
            ("number.wwk", "Digital-Sollwert WWK"),
            ("sensor.test", "Aktorentest Drehzahl"),
        ],
    )
    in_betrieb = _teil(
        "ZSP-1",
        20,
        [
            ("sensor.analog", "Analog-Sollwert"),
            ("number.ext", "Solltemperatur ext. Wärmeanforderung"),
            ("sensor.kessel", "Kesseltemperatur"),
            ("sensor.dz", "Pumpendrehzahl"),
        ],
    )
    heizkreis = _teil("UMLZ", 14, [("sensor.v", "Vorlauftemperatur Ist")])

    assert [m["art"] for m in werte.zeichenbare_module([ohne_aufgabe, heizkreis])] == ["heizkreis"]
    assert "pumpenmodul" in [m["art"] for m in werte.zeichenbare_module([in_betrieb, heizkreis])]


# ---------------------------------------------------------------------------
# Ausrichtung der Zeichnungen
#
# Die Anschlussstutzen sitzen bei x = MITTE. Steht der Korpus eines Bauteils
# daneben, hängt das Rohr sichtbar schief am Kessel – genau das war bis
# 1.3.0-beta.2 bei Hackgut (Mitte 108) und Pellets (Mitte 120) der Fall.
# Beiwerk wie Einschubschnecke, Vorratsbehälter oder Sonne darf ausscheren;
# geprüft wird deshalb der größte Rechteckkorpus, nicht die ganze Hülle.
# ---------------------------------------------------------------------------
_RECHTECK = re.compile(
    r'<rect[^>]*?x="(-?[\d.]+)"[^>]*?y="(-?[\d.]+)"'
    r'[^>]*?width="([\d.]+)"[^>]*?height="([\d.]+)"'
)


def _korpus(inhalt: str) -> tuple[float, float, float, float]:
    """Das flächengrößte Rechteck einer Bauteilzeichnung."""
    kandidaten = [
        (float(x), float(y), float(b), float(h)) for x, y, b, h in _RECHTECK.findall(inhalt)
    ]
    assert kandidaten, "keine Rechtecke in der Zeichnung"
    return max(kandidaten, key=lambda r: r[2] * r[3])


@pytest.mark.parametrize(
    "datei",
    ["kessel.svg", "kessel-hackgut.svg", "kessel-pellets.svg", "kessel-scheitholz.svg"],
)
def test_kesselkoerper_steht_mittig_ueber_dem_anschluss(bauteile, zeichnung, datei):
    x, _y, breite, _h = _korpus(bauteile.bauteil(datei))
    assert x + breite / 2 == pytest.approx(zeichnung.MITTE, abs=1), (
        f"{datei}: Korpusmitte {x + breite / 2}, erwartet {zeichnung.MITTE}"
    )


def _senkrechte_huelle(inhalt: str) -> tuple[float, float]:
    """Oberste und unterste gezeichnete Kante einer Bauteilzeichnung."""
    ys: list[float] = []
    for _x, y, _b, hoehe in _RECHTECK.findall(inhalt):
        ys += [float(y), float(y) + float(hoehe)]
    for cy, r in re.findall(r'<circle[^>]*?cy="(-?[\d.]+)"[^>]*?r="([\d.]+)"', inhalt):
        ys += [float(cy) - float(r), float(cy) + float(r)]
    for y in re.findall(r"[ML] -?[\d.]+ (-?[\d.]+)", inhalt):
        ys.append(float(y))
    assert ys, "keine Formen in der Zeichnung"
    return min(ys), max(ys)


def test_anschluesse_reichen_bis_an_das_bauteil(bauteile, zeichnung):
    """Kein Loch zwischen Leitung und Bauteil.

    Beim Pumpenmodul begann die Zeichnung erst bei y = 150, der Stutzen endete
    aber schon bei 122 – dazwischen klaffte sichtbar nichts. Geprüft wird gegen
    die äußerste gezeichnete Kante: Reicht der Stutzen bis dorthin, kann keine
    Lücke mehr entstehen. Dass er ein Stück in das Bauteil hineinragt, ist
    unschädlich – er wird davor gezeichnet und verschwindet dahinter.
    """
    for art, (oben, unten) in zeichnung.KANTEN_JE_ART.items():
        inhalt = bauteile.bauteil(f"{art}.svg")
        assert inhalt is not None, f"{art}.svg fehlt"
        erste, letzte = _senkrechte_huelle(inhalt)
        assert oben >= erste, f"{art}: Vorlaufstutzen endet bei {oben}, Bauteil beginnt bei {erste}"
        assert unten <= letzte, (
            f"{art}: Rücklaufstutzen beginnt bei {unten}, Bauteil endet bei {letzte}"
        )
        assert zeichnung.VORLAUF_Y < oben < unten < zeichnung.RUECKLAUF_Y, (
            f"{art}: Kanten vertauscht"
        )


def test_schaubild_liefert_die_lage_der_leitungen(karte, anlage):
    """Die Oberfläche legt die Strömung als eigene Ebene darüber."""
    karte = karte.anlagenschema(anlage)
    leitungen = karte["leitungen"]
    for feld in ("left", "width", "vorlauf_top", "ruecklauf_top"):
        assert leitungen[feld].endswith("%")
    assert float(leitungen["vorlauf_top"].rstrip("%")) < float(
        leitungen["ruecklauf_top"].rstrip("%")
    )


def test_waermeerzeuger_meldet_sein_glutbett(karte, anlage):
    """Das Glutbett hängt an der Kesselleistung, nicht an der Betriebsphase.

    Die Betriebsphase heißt auf jeder Baureihe anders; eine Zahl über null
    nicht.
    """
    brenner = karte.anlagenschema(anlage)["brenner"]
    assert [e["entity"] for e in brenner] == ["sensor.leistung"]
    assert brenner[0]["titel"] == "PuroWIN"


def test_ohne_leistungswert_kein_glutbett(karte):
    """Meldet ein Kessel keine Leistung, bleibt das Bild ruhig."""
    teile = [_teil("Fremdkessel", 6, [("sensor.kessel_ist", "Kesseltemperatur Ist")])]
    assert karte.anlagenschema(teile)["brenner"] == []


def test_mischerstellung_wird_gemeldet(karte):
    """Der Heizkreismischer bekommt Anzeiger und eingefärbtes Vorlaufstück."""
    teile = [
        _teil(
            "Südbau",
            14,
            [
                ("sensor.vl", "Vorlauftemperatur Ist"),
                ("sensor.rt", "Raumtemperatur Ist"),
                ("sensor.mischer", "Mischer Stellwert"),
            ],
        )
    ]
    mischer = karte.anlagenschema(teile)["mischer"]
    assert [e["entity"] for e in mischer] == ["sensor.mischer"]
    # Das Vorlaufstück reicht von der Leitung bis zum Ventil.
    assert mischer[0]["stutzen_top"].endswith("%")
    assert float(mischer[0]["stutzen_hoehe"].rstrip("%")) > 0


def test_mischerlaufzeit_ist_kein_stellwert(karte):
    """Die Mischerlaufzeit ist eine Einstellung in Minuten, keine Stellung.

    Ohne die Abgrenzung landete sie als Prozentwert im Schaubild und der
    Zeiger stand irgendwo.
    """
    teile = [
        _teil(
            "Südbau",
            14,
            [
                ("sensor.vl", "Vorlauftemperatur Ist"),
                ("sensor.rt", "Raumtemperatur Ist"),
                ("sensor.laufzeit", "Mischerlaufzeit"),
            ],
        )
    ]
    assert karte.anlagenschema(teile)["mischer"] == []


def test_pumpenmodul_wird_ohne_messwert_gezeichnet(werte):
    """Das Pumpen-/Relaismodul zeigt im Schaubild keine Zahl.

    Sein Fühler (`0/7`) misst bei einer Fernwärmeübergabe den Speicher auf der
    *anderen* Seite – im Schaubild sah es aus, als stünde diese Temperatur im
    Heizhaus. Dass das Modul in der Leitung sitzt, muss man trotzdem sehen;
    seinen Zustand zeigen die Lampen.
    """
    module = werte.zeichenbare_module([_teil("ZSP-1", 20, [("sensor.t", "Kesseltemperatur")])])
    assert [m["art"] for m in module] == ["pumpenmodul"]
    assert module[0]["werte"] == []


def test_ohne_einen_einzigen_messwert_kein_schaubild(karte):
    """Ein Bild aus lauter leeren Kästen hilft niemandem."""
    nur_modul = [_teil("ZSP-1", 20, [("sensor.t", "Kesseltemperatur")])]
    assert karte.anlagenschema(nur_modul) is None

    # Zusammen mit einem messenden Anlagenteil erscheint es sehr wohl.
    mit_kessel = [
        _teil("PuroWIN", 25, [("sensor.k", "Kesseltemperatur Ist")]),
        *nur_modul,
    ]
    bild = karte.anlagenschema(mit_kessel)
    assert bild is not None
    assert len(bild["lampen"]) == 0, "ohne Analog-Sollwert gibt es nichts zu leuchten"


def test_puffer_kennt_kessel_und_obere_temperatur(karte):
    """„lädt" braucht mehr als die laufende Ladepumpe.

    Die Pumpe läuft auch, wenn der Kessel gerade direkt in einen Heizkreis
    fährt und dem Puffer nichts zugeht. Wärme geht nur dann hinein, wenn der
    Kessel wärmer ist als der obere Pufferbereich – dafür muss die Oberfläche
    beide Werte kennen.
    """
    teile = [
        _teil(
            "PuroWIN",
            25,
            [("sensor.kessel", "Kesseltemperatur Ist"), ("sensor.leistung", "Kesselleistung")],
        ),
        _teil(
            "B-PLMi PUFFER",
            16,
            [
                ("sensor.tpe", "Puffer oben Temperatur (TPE)"),
                ("sensor.tpa", "Puffer unten Temperatur (TPA)"),
                ("sensor.plp", "Pufferladepumpe Drehzahl"),
            ],
        ),
    ]
    speicher = karte.anlagenschema(teile)["speicher"]
    assert len(speicher) == 1
    assert speicher[0]["laden"] == "sensor.plp"
    assert speicher[0]["kessel"] == "sensor.kessel"
    assert speicher[0]["oben"] == "sensor.tpe"
    assert speicher[0]["toleranz"] > 0
    assert speicher[0]["unten"], "ohne den unteren Fühler fehlt der Bezug der Ladung"


# ------------------------------------------------- Schichtung und Zeichnung
def _puffer_teile(mit_beiden_fuehlern: bool) -> list:
    """Anlage mit einem Puffer – wahlweise mit beiden oder nur einem Fühler."""
    werte = [("sensor.tpe", "Puffer oben Temperatur (TPE)")]
    if mit_beiden_fuehlern:
        werte.append(("sensor.tpa", "Puffer unten Temperatur (TPA)"))
    return [
        _teil("PuroWIN", 25, [("sensor.kessel", "Kesseltemperatur Ist")]),
        _teil("B-PLMi PUFFER", 16, werte),
    ]


def test_mit_beiden_fuehlern_bleibt_der_speicherkoerper_ungefuellt(schema, karte):
    """Die Farbe liegt unter der Zeichnung – dort darf keine Füllung stehen.

    Füllte die Zeichnung den Körper, verdeckte sie die Schichtung; läge die
    Schichtung stattdessen darüber, verdeckte sie Glanz, Schichtlinien,
    Isolierbänder und Fühlerpunkte. Genau das sah unfertig aus.
    """
    teile = _puffer_teile(True)
    bild = karte.anlagenschema(teile)

    assert len(bild["schichtung"]) == 1
    # Der Speicherkörper ist das einzige Rechteck mit rx=30.
    svg = _svg_von(schema, teile)
    assert 'height="180" rx="30" fill="none"' in svg
    assert 'height="180" rx="30" fill="url(#t1-schichtung)"' not in svg


def test_ohne_zweiten_fuehler_bleibt_die_zeichnung_wie_sie_war(schema, karte):
    """Ein Fühler reicht für keine Schichtung – dann füllt die Zeichnung selbst."""
    teile = _puffer_teile(False)
    bild = karte.anlagenschema(teile)

    assert bild["schichtung"] == []
    assert 'height="180" rx="30" fill="url(#t1-schichtung)"' in _svg_von(schema, teile)


def test_zeichnung_und_farbflaeche_entscheiden_gemeinsam(zeichnung):
    """Beide Seiten hängen an derselben Prüfung, sonst klafft ein Loch."""

    def wert(beschriftung):
        return {"beschriftung": beschriftung, "entity_id": f"sensor.{beschriftung.lower()}"}

    puffer_beide = {"art": "puffer", "werte": [wert("oben"), wert("unten")]}
    puffer_einer = {"art": "puffer", "werte": [wert("oben")]}
    boiler = {"art": "wasser", "werte": [wert("Warmwasser")]}
    fremd = {"art": "kessel", "werte": [wert("oben"), wert("unten")]}

    assert zeichnung.hat_speicherfarbe(puffer_beide) is True
    # Ein einzelner Pufferfühler ergibt keine Schichtung.
    assert zeichnung.hat_speicherfarbe(puffer_einer) is False
    # Der Boiler hat von Haus aus nur einen – er wird gleichmäßig gefärbt.
    assert zeichnung.hat_speicherfarbe(boiler) is True
    assert zeichnung.hat_speicherfarbe(fremd) is False


def test_boiler_wird_gleichmaessig_gefaerbt(karte):
    """Ein Istwert, kein zweiter – `unten` bleibt leer statt erfunden."""
    heizkreis = _teil(
        "UMLZ HEIZKREIS",
        14,
        [
            ("sensor.vorlauf", "Vorlauftemperatur Ist"),
            ("sensor.raum", "Raumtemperatur Ist"),
            ("sensor.ww", "Warmwasser Ist-Temperatur"),
        ],
    )
    bild = karte.anlagenschema([heizkreis])
    boiler = [e for e in bild["schichtung"] if e["oben"] == "sensor.ww"]

    assert len(boiler) == 1
    assert boiler[0]["unten"] is None
    assert boiler[0]["grund"], "ohne Messwert braucht die Fläche einen Grundverlauf"


def test_die_struktur_der_zeichnung_bleibt_erhalten(schema):
    """Was den Speicher als Speicher lesbar macht, muss im Bild stehen.

    Die Farbfläche liegt darunter; wäre eines dieser Merkmale in die Fläche
    gewandert, hätte es der Farbklotz wieder verdeckt.
    """
    svg = _svg_von(schema, _puffer_teile(True))

    assert "t1-glanz" in svg, "der Glanzverlauf fehlt"
    # Der Dämmmantel als Ring um den Körper.
    assert 'x="37" y="111" width="126" height="190"' in svg, "der Dämmmantel fehlt"
    # Die drei Dämmnähte bei y=168, 206, 244 – dort schlägt auch die Farbe um.
    for y in (168, 206, 244):
        assert f'y1="{y}"' in svg, f"Dämmnaht bei y={y} fehlt"
    # Deckel und Sockel, an der Körperform beschnitten.
    assert "clipPath" in svg and "t1-innen" in svg, "der Beschnitt am Körper fehlt"
    # Die Anbauteile: vier Anschlussstutzen rechts, zwei Fühlertauchhülsen
    # links. Gezählt wird ihre gemeinsame Form, nicht ihre Maße – die sind
    # Gestaltung und dürfen sich ändern, ohne dass ein Test bricht.
    assert svg.count('rx="2.5"') == 6, "Stutzen oder Tauchhülsen fehlen"
    # Die Fühlerpunkte in den Hülsen.
    assert svg.count('r="2.2"') == 2, "die Fühlerpunkte fehlen"


def test_der_boiler_traegt_dieselbe_bildsprache(schema):
    """Sonst steht ein aufwendiger Puffer neben einem flachen Boiler."""
    heizkreis = _teil(
        "UMLZ HEIZKREIS",
        14,
        [
            ("sensor.vorlauf", "Vorlauftemperatur Ist"),
            ("sensor.raum", "Raumtemperatur Ist"),
            ("sensor.ww", "Warmwasser Ist-Temperatur"),
        ],
    )
    svg = _svg_von(schema, [heizkreis])

    # Körper ungefüllt, Farbe liegt darunter.
    assert 'height="168" rx="48" fill="none"' in svg
    # Dämmmantel, Beschnitt, Stutzen, Register.
    assert 'width="114" height="178"' in svg, "der Dämmmantel fehlt"
    assert "clipPath" in svg, "der Beschnitt am Körper fehlt"
    # Zwei Anschlussstutzen rechts plus eine Fühlertauchhülse links.
    assert svg.count('rx="2.5"') == 3, "Stutzen oder Tauchhülse fehlen"
    assert "M 70 176" in svg, "die Registerheizschlange fehlt"
    # Die Kalottennähte, wo die Wölbung auf den Zylinder trifft.
    for y in (172, 244):
        assert f'y1="{y}"' in svg, f"Kalottennaht bei y={y} fehlt"


# ---------------------------------------------------------------------------
# Heller Farbsatz
#
# Das Bild steckt als Daten-URL in einem `<img>` und erbt dort kein CSS – der
# Wechsel geschieht deshalb am fertigen Bild, durch Austausch der Farbwerte.
# Beide Fassungen gehen mit, weil beim Zeichnen niemand weiß, welches
# Erscheinungsbild der Betrachter eingestellt hat.
# ---------------------------------------------------------------------------
def _svg_hell_von(karte, teile, kesselart=None) -> str:
    karte = karte.anlagenschema(teile, kesselart)
    return base64.b64decode(karte["image"].split(",", 1)[1]).decode("utf-8")


def test_beide_farbsaetze_liegen_der_karte_bei(karte, anlage):
    karte = karte.anlagenschema(anlage)
    assert karte["image"] != karte["dark_mode_image"]


def test_jede_rolle_hat_eine_helle_entsprechung(farben):
    """Sonst fiele eine Farbe beim Wechsel still auf ihren dunklen Wert zurück."""
    assert set(farben.FARBEN) == set(farben.FARBEN_HELL)


def test_im_hellen_bild_bleibt_kein_dunkler_farbwert(schema, farben, anlage):
    hell = _svg_hell_von(schema, anlage)
    for rolle, farbe in farben.FARBEN.items():
        if rolle == "schrift" or rolle in farben.FESTE_ROLLEN:
            continue
        assert farbe not in hell, f"{rolle} steht noch mit dem dunklen Wert {farbe} im Bild"


def test_die_leitungsfarben_gelten_in_jedem_satz(farben):
    """Rot heißt Vorlauf, Blau heißt Rücklauf – in jedem Farbsatz derselbe Wert."""
    for satz in (
        farben.FARBEN_HELL,
        farben.FARBEN_TERRAKOTTA,
        farben.FARBEN_PETROL,
        farben.FARBEN_PFLAUME,
    ):
        for rolle in farben.FESTE_ROLLEN:
            assert satz[rolle] == farben.FARBEN[rolle], f"{rolle} weicht ab"


def test_die_leitungen_ueberstehen_jeden_wechsel(schema, farben, anlage):
    """Am fertigen Bild darf der Austausch die Rohre nicht mitnehmen."""
    dunkel = _svg_von(schema, anlage)
    for thema in (
        farben.THEMA_HELL,
        farben.THEMA_TERRAKOTTA,
        farben.THEMA_PETROL,
        farben.THEMA_PFLAUME,
    ):
        gewechselt = farben.farben_umstellen(dunkel, thema)
        assert farben.FARBE_VORLAUF in gewechselt, f"{thema}: der Vorlauf ist umgefärbt"
        assert farben.FARBE_RUECKLAUF in gewechselt, f"{thema}: der Rücklauf ist umgefärbt"


def test_das_helle_bild_traegt_die_hellen_werte(schema, farben, anlage):
    hell = _svg_hell_von(schema, anlage)
    for rolle in ("vorlauf", "ruecklauf", "rahmen", "titel"):
        assert farben.FARBEN_HELL[rolle] in hell, f"{rolle} fehlt im hellen Bild"


def test_der_wechsel_aendert_nur_farben(schema, anlage):
    """Gleiche Zeichnung, gleiche Kennungen – nur andere Werte."""
    dunkel = _svg_von(schema, anlage)
    hell = _svg_hell_von(schema, anlage)
    ohne_farben = re.compile(r"#[0-9a-f]{6}\b")
    assert ohne_farben.sub("#", dunkel) == ohne_farben.sub("#", hell)


def test_ohne_helles_thema_bleibt_das_bild_wie_es_ist(schema, farben, anlage):
    dunkel = _svg_von(schema, anlage)
    assert farben.farben_umstellen(dunkel, None) == dunkel
    assert farben.farben_umstellen(dunkel, farben.THEMA_DUNKEL) == dunkel


def test_geteilte_dunkle_farbe_muss_hell_geteilt_bleiben(farben, monkeypatch):
    """`vorlauf` und `glut` sind beide `#e2543a`.

    Im fertigen Bild ist nicht mehr zu erkennen, welche Rolle eine Farbe hatte;
    verschiedene helle Werte gäben einer der beiden still die falsche Farbe.
    """
    assert farben.FARBEN["vorlauf"] == farben.FARBEN["glut"]
    monkeypatch.setitem(farben.FARBEN_HELL, "glut", "#123456")
    with pytest.raises(ValueError, match="nicht zu unterscheiden"):
        farben.entsprechung(farben.FARBEN_HELL)


# ---------------------------------------------------------------------------
# Dritter Farbsatz: Terrakotta
# ---------------------------------------------------------------------------
def test_jede_rolle_hat_eine_terrakottaentsprechung(farben):
    assert set(farben.FARBEN) == set(farben.FARBEN_TERRAKOTTA)


def test_die_karte_traegt_die_rohzeichnung(karte, anlage):
    """Aus ihr stellt der Browser jeden weiteren Satz selbst her."""
    karte = karte.anlagenschema(anlage)
    assert karte["svg"].startswith("<svg")


def test_im_terrakottabild_bleibt_kein_dunkler_farbwert(schema, farben, anlage):
    terrakotta = farben.farben_umstellen(_svg_von(schema, anlage), farben.THEMA_TERRAKOTTA)
    for rolle, farbe in farben.FARBEN.items():
        if rolle == "schrift" or rolle in farben.FESTE_ROLLEN:
            continue
        assert farbe not in terrakotta, f"{rolle} steht noch mit {farbe} im Bild"


def test_der_terrakottawechsel_aendert_nur_farben(schema, farben, anlage):
    dunkel = _svg_von(schema, anlage)
    terrakotta = farben.farben_umstellen(dunkel, farben.THEMA_TERRAKOTTA)
    ohne_farben = re.compile(r"#[0-9a-f]{6}\b")
    assert ohne_farben.sub("#", dunkel) == ohne_farben.sub("#", terrakotta)


def test_ein_unbekannter_satz_laesst_das_bild_unveraendert(schema, farben, anlage):
    """Nur so bleibt eine falsche Angabe folgenlos statt farblos."""
    dunkel = _svg_von(schema, anlage)
    assert farben.farben_umstellen(dunkel, "gibtsnicht") == dunkel


# ---------------------------------------------------------------------------
# Weitere Farbsätze: Petrol und Pflaume
# ---------------------------------------------------------------------------
def _weitere(farben):
    return (
        (farben.THEMA_PETROL, farben.FARBEN_PETROL),
        (farben.THEMA_PFLAUME, farben.FARBEN_PFLAUME),
    )


def test_jeder_weitere_satz_kennt_alle_rollen(schema, farben):
    """Eine fehlende Rolle fiele still auf ihren dunklen Wert zurück."""
    for _thema, satz in _weitere(farben):
        assert set(farben.FARBEN) == set(satz)


def test_jeder_satz_hat_eine_farbtabelle(schema, farben):
    """Ohne Tabelle könnte der Browser den Satz nicht herstellen."""
    for thema, _satz in _weitere(farben):
        assert farben.FARBABBILDUNGEN[thema]


def test_in_weiteren_saetzen_bleibt_kein_dunkler_farbwert(schema, farben, anlage):
    dunkel = _svg_von(schema, anlage)
    for thema, _satz in _weitere(farben):
        gewechselt = farben.farben_umstellen(dunkel, thema)
        for rolle, farbe in farben.FARBEN.items():
            if rolle == "schrift" or rolle in farben.FESTE_ROLLEN:
                continue
            assert farbe not in gewechselt, f"{thema}: {rolle} steht noch mit {farbe} im Bild"


def test_weitere_wechsel_aendern_nur_farben(schema, farben, anlage):
    dunkel = _svg_von(schema, anlage)
    ohne_farben = re.compile(r"#[0-9a-f]{6}\b")
    for thema, _satz in _weitere(farben):
        gewechselt = farben.farben_umstellen(dunkel, thema)
        assert ohne_farben.sub("#", dunkel) == ohne_farben.sub("#", gewechselt)


def _im_browser(schema, tmp_path, rumpf: str, nutzlast):
    """Ein Stück JavaScript gegen `ordnung.js` laufen lassen.

    Die Nutzlast geht über eine Datei: Ein Schaubild ist mehrere Kilobyte groß,
    und Umlaute überstehen den Weg nur als UTF-8 in beide Richtungen.
    """
    ordnung_js = (Path(schema.__file__).parents[1] / "frontend" / "ordnung.js").resolve()
    eingabe = tmp_path / "eingabe.json"
    eingabe.write_text(json.dumps(nutzlast), encoding="utf-8")
    skript = tmp_path / "pruefung.mjs"
    skript.write_text(
        f'import {{ farbenUmstellen, schaubildAdresse }} from "{ordnung_js.as_uri()}";\n'
        'import { readFileSync } from "node:fs";\n'
        f'const daten = JSON.parse(readFileSync({json.dumps(str(eingabe))}, "utf-8"));\n'
        f"{rumpf}\n",
        encoding="utf-8",
    )
    ausgabe = subprocess.run(
        ["node", str(skript)], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return json.loads(ausgabe.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")
def test_der_browser_tauscht_dieselben_farben(schema, farben, anlage, tmp_path):
    """Der Austausch geschieht im Browser – er muss dasselbe ergeben wie hier."""
    dunkel = _svg_von(schema, anlage)
    themen = [farben.THEMA_HELL, farben.THEMA_TERRAKOTTA, farben.THEMA_PETROL, farben.THEMA_PFLAUME]
    ergebnis = _im_browser(
        schema,
        tmp_path,
        "console.log(JSON.stringify(daten[1].map((a) => farbenUmstellen(daten[0], a))));",
        [dunkel, [farben.FARBABBILDUNGEN[t] for t in themen]],
    )
    assert ergebnis == [farben.farben_umstellen(dunkel, t) for t in themen]


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")
def test_ohne_abbildung_bleibt_das_bild_im_browser_stehen(schema, anlage, tmp_path):
    """Ein unbekannter Satz darf folgenlos bleiben, nicht farblos."""
    ergebnis = _im_browser(
        schema,
        tmp_path,
        "console.log(JSON.stringify(farbenUmstellen(daten, null) === daten));",
        _svg_von(schema, anlage),
    )
    assert ergebnis is True


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht vorhanden")
def test_die_adresse_traegt_umlaute_unbeschadet(schema, anlage, tmp_path):
    """Die Beschriftungen tragen Umlaute; eine kaputte Adresse zeigt gar nichts."""
    dunkel = _svg_von(schema, anlage)
    adresse = _im_browser(
        schema, tmp_path, "console.log(JSON.stringify(schaubildAdresse(daten)));", dunkel
    )
    assert adresse.startswith("data:image/svg+xml;charset=utf-8,")
    assert unquote(adresse.split(",", 1)[1]) == dunkel


def test_die_nutzdaten_schicken_das_bild_einmal(karte, anlage):
    """Ein Bild je Farbsatz wäre fünfmal dieselbe Zeichnung."""
    nutzdaten = karte.schaubild_nutzdaten({"id": "a", "name": "X", "teile": anlage})
    assert nutzdaten["schema_svg"].startswith("<svg")
    assert set(nutzdaten["schema_farben"]) == {"hell", "terrakotta", "petrol", "pflaume"}
    assert not any(schluessel.endswith("_image") for schluessel in nutzdaten)


def test_die_oberflaeche_kennt_dieselben_saetze(schema, farben):
    """`ordnung.js` bietet an, was `anordnung.py` speichern darf."""
    text = (Path(schema.__file__).parents[1] / "frontend" / "ordnung.js").read_text(
        encoding="utf-8"
    )
    for satz in farben.FARBSAETZE:
        assert f'schluessel: "{satz}"' in text, f"{satz} fehlt in ordnung.js"


def test_warm_bleibt_warm_und_kalt_bleibt_kalt(farben):
    """Die Temperatur liest man an der Farbe, nicht an der Lage im Bild.

    Ein Farbsatz darf seine Handschrift überall zeigen – nur nicht am Vorlauf
    und am Rücklauf: Dort trüge sie eine falsche Auskunft.
    """

    def kanaele(wert: str) -> tuple[int, int, int]:
        return tuple(int(wert[i : i + 2], 16) for i in (1, 3, 5))

    saetze = {
        "dunkel": farben.FARBEN,
        "hell": farben.FARBEN_HELL,
        "terrakotta": farben.FARBEN_TERRAKOTTA,
        "petrol": farben.FARBEN_PETROL,
        "pflaume": farben.FARBEN_PFLAUME,
    }
    for name, farben in saetze.items():
        for rolle in ("vorlauf", "glut", "warm"):
            rot, gruen, blau = kanaele(farben[rolle])
            assert rot > blau and rot > gruen, f"{name}/{rolle} ist nicht warm"
        for rolle in ("ruecklauf", "kalt"):
            rot, gruen, blau = kanaele(farben[rolle])
            assert blau > rot and blau > gruen, f"{name}/{rolle} ist nicht kalt"


def test_jede_kesselzeichnung_traegt_eine_betriebslampe(bauteile, zeichnung):
    """Ohne Fundstelle in der Zeichnung bliebe der rote Punkt im Bild rot."""
    for kesselart in (None, "hackgut", "pellets", "scheitholz", "gas-oel", "waermepumpe"):
        stelle = bauteile.kessellampe(kesselart)
        assert stelle is not None, kesselart
        x, y, r = stelle
        assert 0 < x < zeichnung.MODUL_BREITE
        assert 0 < y < zeichnung.HOEHE
        assert r > 0


def test_die_betriebslampe_haengt_an_der_leistung(karte):
    kessel = _teil(
        "PuroWIN",
        25,
        [
            ("sensor.kessel_ist", "Kesseltemperatur Ist"),
            ("sensor.leistung", "Kesselleistung"),
            ("sensor.brennkammer", "Brennkammertemperatur"),
        ],
    )
    daten = karte.schaubild_daten([{"name": "Test", "teile": [kessel]}])[0]
    lampen = [la for la in daten["schema_lampen"] if la.get("zweck") == "erzeuger"]
    assert len(lampen) == 1
    assert lampen[0]["entity"] == "sensor.leistung"
    assert lampen[0]["ersatz"] == "sensor.brennkammer"
    assert lampen[0]["art"] == "betrieb"


def test_der_schluessel_gewinnt_gegen_einen_frueheren_namenstreffer(werte):
    """Ein Einsteller kann heißen wie der Messwert, den er begrenzt."""
    einsteller = {"name": "Heizkreispumpe Nachlauf", "schluessel": None, "entity_id": "a"}
    messwert = {"name": "Kreis Pumpe (LON)", "schluessel": "circuit_pump", "entity_id": "b"}

    treffer = werte.finde([einsteller, messwert], r"heizkreispumpe", "circuit_pump")

    assert treffer["entity_id"] == "b"


AUSSEN_MUSTER = (re.compile(r"au(ß|ss)entemperatur", re.IGNORECASE),)


def test_der_messwert_gewinnt_gegen_den_gleichnamigen_einsteller(werte):
    """Der Fall, für den die Rangfolge gebaut ist.

    Am Heizkreis heißt die Frostschutzgrenze wie die Außentemperatur. Ohne
    Rangfolge entschiede die Reihenfolge der Registry, welche gefunden wird.
    """
    grenze = {"name": "Aussentemperatur", "schluessel": None, "bereich": "number"}
    messwert = {"name": "Außentemperatur", "schluessel": "outdoor_temperature"}

    treffer = werte.treffer([grenze, messwert], AUSSEN_MUSTER, "outdoor_temperature")

    assert treffer[0] is messwert
    assert grenze in treffer


def test_ohne_schluessel_bleibt_die_reihenfolge_wie_gefunden(werte):
    """Wo keiner der Kandidaten eine Adresse trägt, entscheidet weiter das Muster."""
    erst = {"name": "Aussentemperatur", "schluessel": None}
    dann = {"name": "Außentemperatur", "schluessel": None}

    assert werte.treffer([erst, dann], AUSSEN_MUSTER, "outdoor_temperature") == [erst, dann]


def test_wer_weder_passt_noch_traegt_bleibt_draussen(werte):
    """Die Rangfolge sortiert, sie nimmt nichts zusätzlich auf."""
    fremd = {"name": "Kesseltemperatur Ist", "schluessel": "boiler_temperature"}

    assert werte.treffer([fremd], AUSSEN_MUSTER, "outdoor_temperature") == []


# ---------------------------------------------------------------------------
# Wärmequellen ohne Anschluss an die Steuerung
# ---------------------------------------------------------------------------
def _quelle(name: str, art: str) -> dict:
    """Ein Anlagenteil, das seine Bauart selbst mitbringt."""
    return {
        "name": name,
        "fct_type": None,
        "art": art,
        "entitaeten": [
            {
                "entity_id": "binary_sensor.solar_waermelieferung",
                "name": "Wärmelieferung",
                "hat_wert": True,
                "bereich": "binary_sensor",
            }
        ],
    }


@pytest.mark.parametrize("art", ["solar", "heizstab", "fremdquelle"])
def test_eine_quelle_wird_ohne_messwert_gezeichnet(werte, art):
    """Dass die Quelle in der Anlage steht, ist die Aussage."""
    module = werte.zeichenbare_module([_quelle("Solaranlage", art)])

    assert [m["art"] for m in module] == [art]


def test_die_bauart_der_quelle_sticht_den_funktionstyp(werte):
    teil = {**_quelle("Heizstab", "heizstab"), "fct_type": 16}

    module = werte.zeichenbare_module([teil])

    assert module[0]["art"] == "heizstab"


def test_ein_solarkreis_der_steuerung_traegt_keine_lieferung(werte):
    """Nur eine angelegte Wärmequelle bekommt Lampe und Strang."""
    teil = _teil("Solarkreis", 5, [("sensor.kollektor", "Kollektortemperatur")])
    teil["entitaeten"].append(
        {
            "entity_id": "binary_sensor.solar_waermelieferung",
            "name": "Wärmelieferung",
            "hat_wert": True,
            "bereich": "binary_sensor",
        }
    )

    module = werte.zeichenbare_module([teil])

    assert module[0]["art"] == "solar"
    assert module[0]["lieferung"] is None


@pytest.mark.parametrize("art", ["heizstab", "fremdquelle"])
def test_jede_bauart_hat_ihre_zeichnung(bauteile, art):
    assert f"{art}.svg" in bauteile.BAUTEILE


def test_eine_quelle_speist_ein_statt_abzunehmen(werte):
    """Die Strömung läuft von der Quelle weg, nicht zu ihr hin."""
    assert {"heizstab", "fremdquelle", "solar"} <= werte.ERZEUGER_ARTEN


@pytest.mark.parametrize("art", ["solar", "heizstab", "fremdquelle"])
def test_jede_bauart_nennt_ihre_betriebslampe(bauteile, art):
    assert bauteile.lampenpunkt(art) is not None


def test_die_lieferung_treibt_stich_und_lampe(karte, anlage):
    """Ohne Pumpe kein Strang – die Quelle hängt an ihrer Wärmelieferung."""
    bild = karte.anlagenschema([*anlage, _quelle("Solaranlage", "solar")])

    lieferung = "binary_sensor.solar_waermelieferung"
    strang = [p for p in bild["pumpen"] if p["entity"] == lieferung]
    lampe = [e for e in bild["lampen"] if e["entity"] == lieferung]

    assert strang and strang[0]["nur_strang"] and strang[0]["erzeuger"]
    assert strang[0]["vorlauf_hoehe"] and strang[0]["ruecklauf_hoehe"]
    assert lampe and lampe[0]["zweck"] == "quelle"


def test_der_puffer_zaehlt_die_lieferung_als_ladung(karte, anlage):
    bild = karte.anlagenschema([*anlage, _quelle("Solaranlage", "solar")])

    puffer = [s for s in bild["speicher"] if s["titel"].startswith("B-PLMi")]

    assert puffer
    assert "binary_sensor.solar_waermelieferung" in puffer[0]["quellen"]


def _anlage_mit_ladepumpe() -> list:
    """Anlage, deren Puffer eine Ladepumpe führt – sonst gibt es keinen Strang."""
    return [
        _teil("PuroWIN", 25, [("sensor.kessel_ist", "Kesseltemperatur Ist")]),
        _teil(
            "B-PLMi PUFFER",
            16,
            [
                ("sensor.tpe", "Puffer oben Temperatur (TPE)"),
                ("sensor.tpa", "Puffer unten Temperatur (TPA)"),
                ("sensor.plp", "Pufferladepumpe Drehzahl"),
            ],
        ),
    ]


def test_die_stichleitung_des_puffers_haengt_an_der_quelle(karte):
    """Der Speicher lädt aus der Quelle, also strömt auch seine Stichleitung."""
    teile = [*_anlage_mit_ladepumpe(), _quelle("Solaranlage", "solar")]

    strang = [p for p in karte.anlagenschema(teile)["pumpen"] if p["titel"].startswith("B-PLMi")]

    assert strang
    assert "binary_sensor.solar_waermelieferung" in strang[0]["quellen"]


def test_die_quelle_zeichnet_ihr_laufrad_nur_auf_wunsch(karte):
    """Eine Solaranlage hat eine Pumpe, ein Heizstab nicht – das sagt die Wahl."""
    lieferung = "binary_sensor.solar_waermelieferung"
    mit = karte.anlagenschema(
        [*_anlage_mit_ladepumpe(), {**_quelle("Solaranlage", "solar"), "quellenpumpe": True}]
    )
    ohne = karte.anlagenschema([*_anlage_mit_ladepumpe(), _quelle("Heizstab", "heizstab")])

    strang = [p for p in mit["pumpen"] if p["entity"] == lieferung]
    stumpf = [p for p in ohne["pumpen"] if p["entity"] == lieferung]

    assert strang and not strang[0]["nur_strang"]
    assert stumpf and stumpf[0]["nur_strang"]


@pytest.mark.parametrize("art", ["solar", "heizstab", "fremdquelle"])
def test_jede_bauart_nennt_ihre_waermeflaeche(bauteile, art):
    """Ohne markierte Fläche bliebe die Quelle im Bild unbeteiligt."""
    flaeche = bauteile.waermeflaeche(art)

    assert flaeche is not None
    assert flaeche["breite"] > 0 and flaeche["hoehe"] > 0


def test_die_flaeche_der_quelle_haengt_an_der_lieferung(karte):
    """Sie glüht nach demselben Zeichen wie die Lampe, nicht nach einem Messwert."""
    teile = [*_anlage_mit_ladepumpe(), _quelle("Solaranlage", "solar")]

    waerme = karte.anlagenschema(teile)["waerme"]

    assert len(waerme) == 1
    assert waerme[0]["entity"] == "binary_sensor.solar_waermelieferung"
    assert waerme[0]["dreh"] == -14


def test_ohne_quelle_bleibt_die_flaeche_leer(karte):
    assert karte.anlagenschema(_anlage_mit_ladepumpe())["waerme"] == []


def test_der_kesselstrang_zaehlt_die_quelle_nicht(karte):
    """Die Quelle lädt den Speicher; am Kessel ändert sie nichts."""
    teile = [*_anlage_mit_ladepumpe(), _quelle("Solaranlage", "solar")]

    kessel = [p for p in karte.anlagenschema(teile)["pumpen"] if p["titel"] == "PuroWIN"]

    assert kessel
    assert not kessel[0].get("quellen")


def test_das_schaubild_zeigt_die_quelle_neben_der_anlage(karte, anlage):
    bild = karte.anlagenschema([*anlage, _quelle("Heizstab", "heizstab")])

    assert bild is not None
    roh = base64.b64decode(bild["image"].split(",", 1)[1]).decode("utf-8")
    assert "Heizstab" in roh
