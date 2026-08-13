"""Die Namenstabelle der LON-Netzwerkvariablen.

Sie ist der Grund, warum eine fremde Baureihe benannte Werte bekommt, ohne
dass jemand für ihren Funktionstyp eine Adresstabelle schreibt. Geprüft wird
hier, dass der Zugriff den Index vom Begriff trennt und dass Unbekanntes
unbekannt bleibt statt geraten zu werden.
"""

from __future__ import annotations

import sys
from pathlib import Path

QUELLE = Path(__file__).parent.parent / "custom_components"
if str(QUELLE) not in sys.path:
    sys.path.insert(0, str(QUELLE))

from heatnexus import lon  # noqa: E402
from heatnexus.kanonisch import KANONISCH  # noqa: E402


def test_klarname_statt_rohname():
    assert lon.zuordnen("PMX_eeBetrStd")["name"] == "Betriebsstunden"


def test_index_zaehlt_den_kreis_und_trifft_denselben_eintrag():
    """`LX_nvoPump[0]` ist derselbe Begriff wie `LX_nvoPump`, nur der erste Kreis."""
    eintrag = lon.zuordnen("LX_nvoPump[0]")

    assert eintrag["index"] == 0
    assert eintrag["name"] == "Kreis Pumpe 1"


def test_unbekannter_name_bleibt_unbekannt():
    """Der Rückfall legt ihn mit dem Namen der Anlage an – hier gibt es nichts."""
    assert lon.zuordnen("nvoFileDirectory") is None
    assert lon.zuordnen(None) is None


def test_traege_werte_bleiben_in_der_langsamen_klasse():
    """Betriebsstunden brauchen keinen Halbminutentakt."""
    assert lon.zuordnen("PMX_eeBetrStd")["poll_class"] == "slow"
    # Pumpe und Ventil zeigt das Schaubild – sie laufen im mittleren Takt.
    assert lon.zuordnen("M_nvoPump")["poll_class"] == "normal"


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


def test_kein_eintrag_traegt_seinen_index_im_schluessel():
    """Sonst greift die Tabelle für den zweiten Kreis nicht mehr."""
    assert not [name for name in lon.LON_NAMEN if name.endswith("]")]
