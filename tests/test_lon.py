"""Die Namenstabelle der LON-Netzwerkvariablen.

Sie ist der Grund, warum eine fremde Baureihe benannte Werte bekommt, ohne
dass jemand für ihren Funktionstyp eine Adresstabelle schreibt. Geprüft wird
hier, dass der Zugriff den Index vom Begriff trennt und dass Unbekanntes
unbekannt bleibt statt geraten zu werden.
"""

from __future__ import annotations

from pathlib import Path
import sys

QUELLE = Path(__file__).parent.parent / "custom_components"
if str(QUELLE) not in sys.path:
    sys.path.insert(0, str(QUELLE))

from heatnexus import lon  # noqa: E402
from heatnexus.kanonisch import KANONISCH  # noqa: E402


def test_klarname_statt_rohname():
    assert lon.zuordnen("PMX_eeBetrStd")["name"] == "Betriebsstunden"


def test_index_zaehlt_den_kreis_und_trifft_denselben_eintrag():
    """`LX_nvoPump[0]` ist derselbe Begriff wie `LX_nvoPump`, nur der erste Kreis."""
    assert lon.zuordnen("LX_nvoPump[0]")["name"] == "Kreis Pumpe 1"
    assert lon.zuordnen("LX_nvoPump[1]")["name"] == "Kreis Pumpe 2"


def test_bus_eingaenge_werden_erkannt():
    """Eingang und Ausgang führen dieselbe Zahl; nur der Ausgang wird gelesen."""
    assert lon.ist_eingang("WET_nviTist") is True
    assert lon.ist_eingang("nviTaFb") is True
    assert lon.ist_eingang("LX_nviTsoll[0]") is True
    assert lon.ist_eingang("WET_nvoTist") is False
    assert lon.ist_eingang("PMX_eeBetrStd") is False


def test_unbekannter_name_bleibt_unbekannt():
    """Der Rückfall legt ihn mit dem Namen der Anlage an – hier gibt es nichts."""
    assert lon.zuordnen("nvoFileDirectory") is None
    assert lon.zuordnen(None) is None


def test_kein_eintrag_setzt_einen_eigenen_takt():
    """Netzwerkvariablen sind die zweite Quelle und laufen langsam.

    An der eigenen PuroWIN wären elf Pumpen und Ventile im mittleren Takt
    gelandet: 478 Abfragen je Stunde für Werte, die es zum großen Teil schon
    als Datenpunkt gibt. Wer einen schnelleren Takt braucht, schaltet die
    Entität ein und HA fragt sie mit an.
    """
    assert not [name for name, e in lon.LON_NAMEN.items() if e.get("poll_class")]


def test_kanonische_schluessel_gibt_es_wirklich():
    """Ein Schlüssel, den die Datenpunkttabelle nicht kennt, verbindet nichts.

    Der Abgleich gegen die OID-Seite läuft über genau diesen Wert; ein
    Tippfehler bliebe sonst unbemerkt und der LON-Wert stünde doppelt da.
    """
    bekannt = set(KANONISCH.values())
    verwendet = {
        eintrag["kanonisch"] for eintrag in lon.LON_NAMEN.values() if eintrag.get("kanonisch")
    }

    assert verwendet <= bekannt, verwendet - bekannt


def test_ungueltige_marken_gelten_als_kein_wert():
    """Ein nicht angeschlossener Fühler meldet die größte darstellbare Zahl.

    An der eigenen Anlage standen so vier Pufferfühler und zwei
    Raumtemperaturen auf 327,67 °C. Als Messwert gelesen wäre das ein Alarm
    ohne Anlass — und im Langzeitverlauf eine Spitze, die nie stattfand.
    """
    assert lon.ungueltig("327.67") is True
    assert lon.ungueltig("163.835") is True
    assert lon.ungueltig("42.78") is False
    assert lon.ungueltig(None) is False
    assert lon.ungueltig("-.-") is False


def test_der_schluessel_findet_aus_der_kennung_zurueck():
    """Schaubild und Kennwerte kennen nur die `unique_id`, nicht den Deskriptor.

    Ohne den Rückweg käme dort für jede Netzwerkvariable `None` an – und der
    Wert stünde in der Entitätsliste, aber in keiner Karte.
    """
    from heatnexus.kanonisch import schluessel

    assert schluessel("0702bb000002-nv-0-7-wet-nvotist") == "boiler_temperature"
    # Indizierte Namen: Der Index unterscheidet die Kreise, nicht den Begriff.
    assert schluessel("0702bb000002-nv-0-12-lx-nvopump-0") == "circuit_pump"
    # Unbenannte bleiben ohne Schlüssel.
    assert schluessel("0702bb000002-nv-0-3-nvofiledirectory") is None


def test_datenpunkte_behalten_ihren_weg():
    """Der Rückweg über den Namen darf die Adresse nicht verdrängen."""
    from heatnexus.kanonisch import schluessel

    assert schluessel("0702bb000002-0-0-7-0") == "boiler_temperature"
    assert schluessel("0702bb000002-0-99-99-0") is None


def test_kein_eintrag_traegt_seinen_index_im_schluessel():
    """Sonst greift die Tabelle für den zweiten Kreis nicht mehr."""
    assert not [name for name in lon.LON_NAMEN if name.endswith("]")]
