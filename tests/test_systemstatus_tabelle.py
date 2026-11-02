"""Panel und Schaubild-Karte lesen ihre Zeilen aus der Tabelle der Gerätemodule.

An einer Anlage mit einem Kessel hält der Test fest, welche Zeilen beide
Ansichten in welcher Reihenfolge zeigen.
"""

from __future__ import annotations

from .conftest import load_standalone, requires_frontend, requires_ha, requires_moderne_ha
from .test_anlagenkatalog_ha import _abbauen, _eigene_integration, _einrichten  # noqa: F401

KESSEL = "sensor.anlage_funktion_25_0_"
AUSSEN = "sensor.anlage_funktion_14_0_aussentemperatur"

PANEL = [
    ("Betriebszustand", KESSEL + "betriebsphase"),
    ("Außentemperatur", AUSSEN),
    ("Kesselleistung", KESSEL + "kesselleistung"),
    ("Brennkammertemperatur", KESSEL + "brennkammertemperatur"),
    ("Abgastemperatur", KESSEL + "abgastemperatur"),
    ("Brennstoff", KESSEL + "aktueller_brennstoff"),
    ("Vorratsbehälter", KESSEL + "vorratsbehalter_status"),
    ("Brennerstarts", KESSEL + "brennerstarts"),
    ("Betriebsstunden", KESSEL + "betriebsstunden"),
    ("Bis Ascheentleerung", KESSEL + "laufzeit_bis_ascheentleerung"),
]

KARTE = [
    KESSEL + "aktueller_brennstoff",
    KESSEL + "betriebsphase",
    KESSEL + "kesselleistung",
    KESSEL + "vorratsbehalter_status",
    AUSSEN,
]


@requires_ha()
@requires_frontend()
@requires_moderne_ha()
async def test_einkessel_anlage_zeigt_panel_und_karte_unveraendert(hass):
    from custom_components.heatnexus.dashboard.anlage import schaubild
    from custom_components.heatnexus.dashboard.anlagen import anlagen_lesen
    from custom_components.heatnexus.panel.daten import anlage_daten

    eintrag = await _einrichten(hass, "purowin-uml-puffer", "betreiber")
    try:
        [anlage] = anlagen_lesen(hass)
        status = anlage_daten(anlage)["status"]
        assert [(z["titel"], z["entity"]) for z in status] == PANEL
        karte = schaubild(anlage, als_karte=True, mit_liste=True)
        assert karte["zusatzwerte"] == KARTE
    finally:
        await _abbauen(hass, eintrag)


def test_jeder_erzeuger_im_schaubild_fuehrt_statuszeilen():
    """Ein Erzeuger ohne Zeilen fiele aus dem Systemstatus."""
    geraete = load_standalone("geraete")
    erzeuger = {f for f, art in geraete.SCHAUBILD_ARTEN.items() if art == "kessel"}
    assert erzeuger <= set(geraete.STATUSZEILEN)


def test_der_lauf_steht_vor_den_gemeinsamen_zeilen_und_den_werten():
    geraete = load_standalone("geraete")
    titel = [z.titel for z in geraete.statuszeilen_fuer([9]) if z.panel]
    assert titel[:6] == [
        "Betriebszustand",
        "Laufzeit",
        "Laufzeit heute",
        "Außentemperatur",
        "SG Ready",
        "Kesselleistung",
    ]


def test_ohne_erzeuger_gelten_die_zeilen_eines_kessels():
    """Auch eine Anlage ohne erkannten Erzeuger meldet Betriebsstunden und Brennstoff."""
    geraete = load_standalone("geraete")
    assert geraete.statuszeilen_fuer([14, 16]) == geraete.statuszeilen_fuer([25])
