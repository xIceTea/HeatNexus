"""Anlagenschaubild: Aufbau der Grafik und Lage der Beschriftungen."""

from __future__ import annotations

import base64
import re
from xml.etree import ElementTree

import pytest

from .conftest import load_standalone


@pytest.fixture(scope="module")
def schema():
    """Das Modul kommt ohne Home Assistant aus und wird direkt geladen."""
    return load_standalone("schema")


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


def test_karte_ist_ein_bild_mit_beschriftungen(schema, anlage):
    karte = schema.anlagenschema(anlage)
    assert karte["type"] == "picture-elements"
    assert karte["image"].startswith("data:image/svg+xml;base64,")
    # Je Anlagenteil zwei Werte.
    assert len(karte["elements"]) == 4
    assert {e["entity"] for e in karte["elements"]} == {
        "sensor.kessel_ist",
        "sensor.leistung",
        "sensor.tpe",
        "sensor.tpa",
    }


def test_bild_enthaelt_die_namen(schema, anlage):
    karte = schema.anlagenschema(anlage)
    svg = base64.b64decode(karte["image"].split(",", 1)[1]).decode("utf-8")
    assert svg.startswith("<svg")
    assert "PuroWIN" in svg
    assert "B-PLMi PUFFER" in svg
    assert "</svg>" in svg


def test_beschriftungen_liegen_im_bild(schema, anlage):
    for element in schema.anlagenschema(anlage)["elements"]:
        for achse in ("top", "left"):
            anteil = float(element["style"][achse].rstrip("%"))
            assert 0 < anteil < 100


def test_ohne_messwerte_kein_schaubild(schema):
    assert schema.anlagenschema([]) is None
    ohne = [_teil("ZSP-PTS", 20, [("sensor.x", "Pumpendrehzahl")])]
    assert schema.anlagenschema(ohne) is None


def test_spitze_klammern_im_namen_zerlegen_das_bild_nicht(schema):
    teil = _teil("Kessel <b>", 25, [("sensor.k", "Kesseltemperatur Ist")])
    svg = base64.b64decode(schema.anlagenschema([teil])["image"].split(",", 1)[1]).decode("utf-8")
    assert "<b>" not in svg
    assert "&lt;b&gt;" in svg


def test_schaubild_entsteht_auch_ohne_werte(schema, anlage):
    """Beim ersten Aufbau ist die Anlage noch nicht eingelesen.

    Verlangte das Schaubild einen vorhandenen Wert, bliebe der Reiter „Anlage"
    dauerhaft leer – der Fehler aus 1.0.0.
    """
    for teil in anlage:
        for eintrag in teil["entitaeten"]:
            eintrag["hat_wert"] = False

    bild = schema.anlagenschema(anlage)
    assert bild is not None
    assert len(bild["elements"]) == 4


def test_anlagenteil_ohne_passenden_messwert_faellt_weg(schema):
    """Ein leerer Kasten hilft niemandem."""
    ohne = [{"name": "Rätsel", "fct_type": 99, "entitaeten": []}]
    assert schema.anlagenschema(ohne) is None


# ---------------------------------------------------------------------------
# Warmwasser als eigener Anlagenteil
#
# In 1.1.0-beta.6/7 fehlte der Warmwasserbehälter im Schaubild, obwohl die
# Anlage ihn liefert. Grund war ein Steuerzeichen im Suchmuster: Beim Erzeugen
# der Datei war aus der Wortgrenze `\b` ein echtes Backspace-Zeichen geworden.
# Im Quelltext war das nicht zu sehen – nur im Verhalten.
# ---------------------------------------------------------------------------
def test_muster_enthalten_keine_steuerzeichen(schema):
    """Ein Suchmuster darf nie ein Steuerzeichen enthalten."""
    muster = [schema.WARMWASSER_IST, schema.ZIRKULATION_IST]
    muster += [m for eintraege in schema.WERTE_JE_ART.values() for m, _ in eintraege]
    muster += list(schema.PUMPE_JE_ART.values())
    for einzeln in muster:
        assert not any(ord(z) < 32 for z in einzeln), f"Steuerzeichen in {einzeln!r}"


def test_warmwasser_wird_eigener_anlagenteil(schema):
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
    arten = [m["art"] for m in schema._module([heizkreis])]
    assert "wasser" in arten, "Warmwasser fehlt im Schaubild"


def test_ohne_warmwasser_kein_eigener_anlagenteil(schema):
    heizkreis = _teil(
        "Hebebuehne",
        14,
        [("sensor.vorlauf", "Vorlauftemperatur Ist"), ("sensor.raum", "Raumtemperatur Ist")],
    )
    arten = [m["art"] for m in schema._module([heizkreis])]
    assert "wasser" not in arten


def test_pumpe_je_anlagenteil(schema):
    heizkreis = _teil(
        "UMLZ HEIZKREIS",
        14,
        [
            ("sensor.raum", "Raumtemperatur Ist"),
            ("sensor.vorlauf", "Vorlauftemperatur Ist"),
            ("binary_sensor.hkp", "Heizkreispumpe"),
        ],
    )
    module = schema._module([heizkreis])
    assert module[0]["pumpe"] == "binary_sensor.hkp"


# ---------------------------------------------------------------------------
# Bauteildateien
#
# Die Anlagenteile werden aus SVG-Dateien in `anlagenteile/` zusammengesetzt.
# Zwei Dinge dürfen dabei nie passieren: ein stehengebliebener Farbplatzhalter
# (dann steht `{{korpus}}` als Farbe im Bild und der Browser zeichnet gar
# nichts) und doppelte Kennungen (dann teilen sich zwei Puffer denselben
# Verlauf und einer bleibt leer).
# ---------------------------------------------------------------------------
def _svg_von(schema, teile, kesselart=None) -> str:
    karte = schema.anlagenschema(teile, kesselart)
    return base64.b64decode(karte["image"].split(",", 1)[1]).decode("utf-8")


def test_jedes_bauteil_hat_eine_datei(schema):
    """Für jede gezeichnete Art gibt es eine Datei – sonst greift der Rückfall."""
    for art in schema.ALLE_ARTEN:
        assert schema._bauteil(f"{art}.svg") is not None, f"anlagenteile/{art}.svg fehlt"


def test_bauteildateien_sind_bruchstuecke_ohne_platzhalterreste(schema):
    for pfad in sorted(schema.TEILE_ORDNER.glob("*.svg")):
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
        unbekannt = set(offen) - set(schema.FARBEN)
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
    svg = _svg_von(schema, zwei)
    kennungen = re.findall(r'id="([^"]+)"', svg)
    assert kennungen, "keine Kennungen im Bild – Bauteildateien nicht geladen?"
    assert len(kennungen) == len(set(kennungen))
    # Und jeder Verweis zeigt auf eine Kennung, die es auch gibt.
    for verweis in re.findall(r"url\(#([^)]+)\)", svg):
        assert verweis in kennungen


def test_fehlende_bauteildatei_zerreisst_das_bild_nicht(schema, anlage, monkeypatch):
    monkeypatch.setattr(schema, "_bauteil", lambda dateiname: None)
    svg = _svg_von(schema, anlage)
    ElementTree.fromstring(svg)
    assert "PuroWIN" in svg


# ---------------------------------------------------------------------------
# Kesselart
# ---------------------------------------------------------------------------
def test_kesselart_kommt_aus_dem_gemeldeten_brennstoff(schema):
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
    assert schema.kesselart_erkennen([kessel]) == "hackgut"

    kessel["entitaeten"][-1]["text"] = "Pellets"
    assert schema.kesselart_erkennen([kessel]) == "pellets"


def test_kesselart_faellt_auf_den_namen_zurueck(schema):
    assert schema.kesselart_erkennen([_teil("PuroWIN 40", 25, [])]) == "hackgut"
    assert schema.kesselart_erkennen([_teil("BioWIN 2", 25, [])]) == "pellets"
    assert schema.kesselart_erkennen([_teil("AeroWIN", 25, [])]) == "waermepumpe"


def test_kesselart_raet_nicht(schema):
    """Sagt weder Brennstoff noch Name etwas, wird neutral gezeichnet."""
    assert schema.kesselart_erkennen([_teil("Waermeerzeuger", 25, [])]) is None
    assert schema.kesselart_erkennen([_teil("PuroWIN", 16, [])]) is None


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
# Bis 1.2.0 waren fünf Zuordnungen falsch, weil sie aus Namen abgeleitet waren
# statt aus der Parameterliste des Herstellers. Der Beleg für jede Zeile steht
# in `_intern/HERSTELLER-REFERENZ.md` 5.3; hier wird er festgehalten, damit ihn
# niemand versehentlich zurückdreht.
# ---------------------------------------------------------------------------
def test_funktionstypen_stimmen_mit_der_parameterliste_ueberein(schema):
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
    assert erwartet == schema.ART_JE_FCT
    assert schema.KESSELART_JE_FCT == {
        6: "gas_oel",
        7: "waermepumpe",
        26: "waermepumpe",
        27: "waermepumpe",
    }


def test_warmwasser_und_zirkulation_in_beiden_schreibweisen(schema):
    """Kuratierte Tabelle und Geräte-Datenbank benennen dieselben Werte anders."""
    import re

    for name in ("Warmwasser Ist-Temperatur", "WW-Temperatur Aktueller Wert"):
        assert re.search(schema.WARMWASSER_IST, name, re.IGNORECASE), name
    for name in ("WW-Zirkulation Ist-Temperatur", "WW-Zirkulationstemperatur Aktueller Wert"):
        assert re.search(schema.ZIRKULATION_IST, name, re.IGNORECASE), name
    # Der Sollwert darf nicht als Istwert durchgehen.
    assert not re.search(
        schema.ZIRKULATION_IST, "WW-Zirkulationstemperatur Sollwert", re.IGNORECASE
    )


def test_puffer_in_beiden_schreibweisen(schema):
    for namen in (
        [("sensor.o", "Puffer oben Temperatur (TPE)"), ("sensor.u", "Puffer unten Temperatur")],
        [("sensor.o", "Puffertemperatur oben"), ("sensor.u", "Puffertemperatur unten")],
        [("sensor.o", "Puffertemperatur TPE"), ("sensor.u", "Puffertemperatur TPA")],
    ):
        module = schema._module([_teil("Puffer", 16, namen)])
        assert len(module[0]["werte"]) == 2, namen


def test_waermepumpe_ist_ein_waermeerzeuger(schema):
    """Eine Wärmepumpe steht an der Stelle des Kessels, nicht daneben."""
    for fct in (26, 27):
        assert schema.ART_JE_FCT[fct] == "kessel"
    # Und sie braucht weder Brennstoff noch sprechenden Namen.
    stumm = _teil("Modul 26", 26, [("sensor.k", "Kesseltemperatur Ist")])
    assert schema.kesselart_erkennen([stumm]) == "waermepumpe"


def test_zsp_und_zirkulation_sehen_verschieden_aus(schema):
    """Ein Pumpenmodul ist kein Zirkulationskreis.

    Beide hingen bis 1.2.0 an derselben Zeichnung; im Schaubild einer Anlage
    mit beidem standen zwei gleiche Kreise nebeneinander.
    """
    zsp = _teil("ZSP-PWA", 20, [("sensor.t", "Temperatur Ist")])
    heizkreis = _teil(
        "UMLZ HEIZKREIS",
        14,
        [
            ("sensor.vorlauf", "Vorlauftemperatur Ist"),
            ("sensor.raum", "Raumtemperatur Ist"),
            ("sensor.zirk", "WW-Zirkulation Ist-Temperatur"),
        ],
    )
    arten = [m["art"] for m in schema._module([zsp, heizkreis])]
    assert "pumpenmodul" in arten
    assert "zirkulation" in arten
    assert schema._bauteil("pumpenmodul.svg") != schema._bauteil("zirkulation.svg")


def test_zsp_meldet_seine_pumpe_ueber_die_drehzahl(schema):
    """Das ZSP hat keinen Pumpenzustand, nur „Pumpendrehzahl" in Prozent."""
    zsp = _teil(
        "ZSP-PWA",
        20,
        [("sensor.t", "Temperatur Ist"), ("sensor.dz", "Pumpendrehzahl")],
    )
    assert schema._module([zsp])[0]["pumpe"] == "sensor.dz"


def test_heizkoerper_haengt_an_der_vorlauftemperatur(schema):
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
    bild = schema.anlagenschema([kreis])
    koerper = bild["heizkoerper"]
    assert len(koerper) == 1
    assert koerper[0]["entity"] == "sensor.ist"
    # Die Skala muss aufsteigen, sonst teilt die Ansicht durch null.
    assert koerper[0]["kalt"] < koerper[0]["heiss"]


def test_heizkoerper_raster_passt_zur_zeichnung(schema):
    """Das Streifenmuster muss in Anteilen kommen, nicht in Bildpunkten.

    Die Karte skaliert das Schaubild auf ihre eigene Breite. In 1.4.0 stand das
    Raster als feste Bildpunktwerte im Stylesheet: Nach der Skalierung saßen
    die Streifen neben den gezeichneten Gliedern, und dazwischen blitzte die
    rote Füllung der Zeichnung durch – der Heizkörper war blau-rot gestreift.

    Geprüft wird zweierlei: Die Angaben sind Prozentwerte, und fünf Glieder
    füllen die Ebene genau aus (5 × Raster − Abstand = Breite).
    """
    kreis = _teil("UMLZ", 14, [("sensor.ist", "Vorlauftemperatur Ist")])
    eintrag = schema.anlagenschema([kreis])["heizkoerper"][0]

    for feld in ("glied", "raster", "glanz_von", "glanz_bis"):
        assert eintrag[feld].endswith("%"), f"{feld} muss ein Anteil sein, ist {eintrag[feld]!r}"

    anteil = lambda feld: float(eintrag[feld].rstrip("%"))  # noqa: E731
    assert anteil("glied") < anteil("raster")
    assert anteil("glanz_von") < anteil("glanz_bis") <= anteil("glied")
    # Fünf Glieder im Raster ergeben genau die Breite der Ebene.
    assert (
        5 * schema.HEIZKOERPER_RASTER - (schema.HEIZKOERPER_RASTER - schema.HEIZKOERPER_GLIED)
        == schema.HEIZKOERPER_BREITE
    )


def test_ohne_vorlaufmessung_kein_gefaerbter_heizkoerper(schema):
    """Ohne Messwert bleibt es bei der Zeichnung – geraten wird nicht."""
    kreis = _teil("UMLZ", 14, [("sensor.raum", "Raumtemperatur Ist")])
    assert schema.anlagenschema([kreis])["heizkoerper"] == []


def test_zsp_ohne_aufgabe_kommt_nicht_ins_schaubild(schema):
    """Ein Pumpenmodul, an dem nichts hängt, gehört nicht in die Leitung.

    Der Fall stammt aus dem Wohnhaus: Dort meldet das ZSP-PWA nur noch
    Sollwerte (``0/95`` Analog-Sollwert, ``9/57`` Solltemperatur ext.
    Wärmeanforderung, ``20/23`` Digital-Sollwert WWK) und den Aktorentest.
    Kesseltemperatur, Pumpendrehzahl und die ganze Gruppe 29 beantwortet die
    Anlage dort nicht – das Modul hat keine Aufgabe. Im Heizhaus dagegen
    liefert dasselbe Bauteil ``0/7`` und ``0/22`` und steht mit „Ext.
    Wärmeanforderung = Ja" mitten im Betrieb.
    """
    ohne_aufgabe = _teil(
        "ZSP-PWA",
        20,
        [
            ("sensor.analog", "Analog-Sollwert"),
            ("number.ext", "Solltemperatur ext. Wärmeanforderung"),
            ("number.wwk", "Digital-Sollwert WWK"),
            ("sensor.test", "Aktorentest Drehzahl"),
        ],
    )
    in_betrieb = _teil(
        "ZSP-PTS",
        20,
        [
            ("sensor.analog", "Analog-Sollwert"),
            ("number.ext", "Solltemperatur ext. Wärmeanforderung"),
            ("sensor.kessel", "Kesseltemperatur"),
            ("sensor.dz", "Pumpendrehzahl"),
        ],
    )
    heizkreis = _teil("UMLZ", 14, [("sensor.v", "Vorlauftemperatur Ist")])

    assert [m["art"] for m in schema._module([ohne_aufgabe, heizkreis])] == ["heizkreis"]
    assert "pumpenmodul" in [m["art"] for m in schema._module([in_betrieb, heizkreis])]


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
def test_kesselkoerper_steht_mittig_ueber_dem_anschluss(schema, datei):
    x, _y, breite, _h = _korpus(schema._bauteil(datei))
    assert x + breite / 2 == pytest.approx(schema.MITTE, abs=1), (
        f"{datei}: Korpusmitte {x + breite / 2}, erwartet {schema.MITTE}"
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


def test_anschluesse_reichen_bis_an_das_bauteil(schema):
    """Kein Loch zwischen Leitung und Bauteil.

    Beim Pumpenmodul begann die Zeichnung erst bei y = 150, der Stutzen endete
    aber schon bei 122 – dazwischen klaffte sichtbar nichts. Geprüft wird gegen
    die äußerste gezeichnete Kante: Reicht der Stutzen bis dorthin, kann keine
    Lücke mehr entstehen. Dass er ein Stück in das Bauteil hineinragt, ist
    unschädlich – er wird davor gezeichnet und verschwindet dahinter.
    """
    for art, (oben, unten) in schema.KANTEN_JE_ART.items():
        inhalt = schema._bauteil(f"{art}.svg")
        assert inhalt is not None, f"{art}.svg fehlt"
        erste, letzte = _senkrechte_huelle(inhalt)
        assert oben >= erste, f"{art}: Vorlaufstutzen endet bei {oben}, Bauteil beginnt bei {erste}"
        assert unten <= letzte, (
            f"{art}: Rücklaufstutzen beginnt bei {unten}, Bauteil endet bei {letzte}"
        )
        assert schema.VORLAUF_Y < oben < unten < schema.RUECKLAUF_Y, f"{art}: Kanten vertauscht"


def test_schaubild_liefert_die_lage_der_leitungen(schema, anlage):
    """Die Oberfläche legt die Strömung als eigene Ebene darüber."""
    karte = schema.anlagenschema(anlage)
    leitungen = karte["leitungen"]
    for feld in ("left", "width", "vorlauf_top", "ruecklauf_top"):
        assert leitungen[feld].endswith("%")
    assert float(leitungen["vorlauf_top"].rstrip("%")) < float(
        leitungen["ruecklauf_top"].rstrip("%")
    )


def test_waermeerzeuger_meldet_sein_glutbett(schema, anlage):
    """Das Glutbett hängt an der Kesselleistung, nicht an der Betriebsphase.

    Die Betriebsphase heißt auf jeder Baureihe anders; eine Zahl über null
    nicht.
    """
    brenner = schema.anlagenschema(anlage)["brenner"]
    assert [e["entity"] for e in brenner] == ["sensor.leistung"]
    assert brenner[0]["titel"] == "PuroWIN"


def test_ohne_leistungswert_kein_glutbett(schema):
    """Meldet ein Kessel keine Leistung, bleibt das Bild ruhig."""
    teile = [_teil("Fremdkessel", 6, [("sensor.kessel_ist", "Kesseltemperatur Ist")])]
    assert schema.anlagenschema(teile)["brenner"] == []


def test_mischerstellung_wird_gemeldet(schema):
    """Der Heizkreismischer bekommt Anzeiger und eingefärbtes Vorlaufstück."""
    teile = [
        _teil(
            "Hebebühne",
            14,
            [
                ("sensor.vl", "Vorlauftemperatur Ist"),
                ("sensor.rt", "Raumtemperatur Ist"),
                ("sensor.mischer", "Mischer Stellwert"),
            ],
        )
    ]
    mischer = schema.anlagenschema(teile)["mischer"]
    assert [e["entity"] for e in mischer] == ["sensor.mischer"]
    # Das Vorlaufstück reicht von der Leitung bis zum Ventil.
    assert mischer[0]["stutzen_top"].endswith("%")
    assert float(mischer[0]["stutzen_hoehe"].rstrip("%")) > 0


def test_mischerlaufzeit_ist_kein_stellwert(schema):
    """Die Mischerlaufzeit ist eine Einstellung in Minuten, keine Stellung.

    Ohne die Abgrenzung landete sie als Prozentwert im Schaubild und der
    Zeiger stand irgendwo.
    """
    teile = [
        _teil(
            "Hebebühne",
            14,
            [
                ("sensor.vl", "Vorlauftemperatur Ist"),
                ("sensor.rt", "Raumtemperatur Ist"),
                ("sensor.laufzeit", "Mischerlaufzeit"),
            ],
        )
    ]
    assert schema.anlagenschema(teile)["mischer"] == []


def test_pumpenmodul_wird_ohne_messwert_gezeichnet(schema):
    """Das Pumpen-/Relaismodul zeigt im Schaubild keine Zahl.

    Sein Fühler (`0/7`) misst bei einer Fernwärmeübergabe den Speicher auf der
    *anderen* Seite – im Schaubild sah es aus, als stünde diese Temperatur im
    Heizhaus. Dass das Modul in der Leitung sitzt, muss man trotzdem sehen;
    seinen Zustand zeigen die Lampen.
    """
    module = schema._module([_teil("ZSP-PTS", 20, [("sensor.t", "Kesseltemperatur")])])
    assert [m["art"] for m in module] == ["pumpenmodul"]
    assert module[0]["werte"] == []


def test_ohne_einen_einzigen_messwert_kein_schaubild(schema):
    """Ein Bild aus lauter leeren Kästen hilft niemandem."""
    nur_modul = [_teil("ZSP-PTS", 20, [("sensor.t", "Kesseltemperatur")])]
    assert schema.anlagenschema(nur_modul) is None

    # Zusammen mit einem messenden Anlagenteil erscheint es sehr wohl.
    mit_kessel = [
        _teil("PuroWIN", 25, [("sensor.k", "Kesseltemperatur Ist")]),
        *nur_modul,
    ]
    bild = schema.anlagenschema(mit_kessel)
    assert bild is not None
    assert len(bild["lampen"]) == 0, "ohne Analog-Sollwert gibt es nichts zu leuchten"


def test_puffer_kennt_kessel_und_obere_temperatur(schema):
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
    speicher = schema.anlagenschema(teile)["speicher"]
    assert len(speicher) == 1
    assert speicher[0]["laden"] == "sensor.plp"
    assert speicher[0]["kessel"] == "sensor.kessel"
    assert speicher[0]["oben"] == "sensor.tpe"
    assert speicher[0]["hysterese"] > 0
