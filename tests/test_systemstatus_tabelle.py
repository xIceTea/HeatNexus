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
        daten = anlage_daten(anlage)
        assert [(z["titel"], z["entity"]) for z in daten["status"]] == PANEL
        assert daten["regelung"] is None
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
    titel = [z.titel for z in geraete.statuszeilen.EINZELN if z.panel]
    assert titel[:6] == [
        "Betriebszustand",
        "Laufzeit",
        "Laufzeit heute",
        "Außentemperatur",
        "SG Ready",
        "Kesselleistung",
    ]


def _e(entity_id: str, name: str) -> dict:
    return {
        "entity_id": entity_id,
        "name": name,
        "bereich": entity_id.split(".")[0],
        "hat_wert": True,
        "schluessel": None,
        "kategorie": None,
    }


def _anlage(*teile: tuple[int, list[dict]]) -> dict:
    return {
        "teile": [
            {"id": f"teil{nummer}", "name": f"Teil {nummer}", "fct_type": fct, "entitaeten": e}
            for nummer, (fct, e) in enumerate(teile)
        ]
    }


@requires_ha()
def test_eine_anlage_nur_mit_waermepumpe_bleibt_wie_sie_ist():
    """Die Zeilen der Wärmepumpe gelten nur in ihrem Block; flach bleibt es bei denen eines Kessels."""
    from custom_components.heatnexus.dashboard.anlage import zustandswerte
    from custom_components.heatnexus.panel.daten import systemstatus

    anlage = _anlage(
        (
            7,
            [
                _e("sensor.wp_phase", "Betriebsphase"),
                _e("sensor.wp_leistung", "Aktuelle Leistung"),
                _e("sensor.wp_cop", "COP aktuell"),
                _e("sensor.wp_vorlauf", "Vorlauftemperatur"),
            ],
        ),
        (
            14,
            [_e("sensor.aussen", "Außentemperatur"), _e("sensor.hk_vorlauf", "Vorlauftemperatur")],
        ),
    )
    status, erzeuger = systemstatus(anlage)
    assert erzeuger == []
    assert [z["titel"] for z in status] == ["Betriebszustand", "Außentemperatur"]
    assert [e["entity_id"] for e in zustandswerte(anlage)] == ["sensor.wp_phase", "sensor.aussen"]


@requires_ha()
def test_ein_teil_ohne_treffer_zaehlt_nicht_als_erzeuger():
    """Kessel und Heizstab ohne passende Werte ergeben keinen Block nur mit Namen."""
    from custom_components.heatnexus.dashboard.anlage import zustandswerte
    from custom_components.heatnexus.panel.daten import systemstatus

    anlage = _anlage(
        (9, [_e("sensor.phase", "Betriebsphase"), _e("sensor.leistung", "Kesselleistung")]),
        (8, [_e("sensor.heizstab", "Heizstab Freigabe")]),
    )
    status, erzeuger = systemstatus(anlage)
    assert erzeuger == []
    assert [z["titel"] for z in status] == ["Betriebszustand", "Kesselleistung"]
    assert [e["entity_id"] for e in zustandswerte(anlage)] == ["sensor.phase", "sensor.leistung"]


@requires_ha()
def test_sg_ready_bleibt_mit_einem_erzeuger_oben():
    from custom_components.heatnexus.panel.daten import systemstatus
    from custom_components.heatnexus.panel.regelung import regelung

    anlage = _anlage(
        (9, [_e("sensor.phase", "Betriebsphase"), _e("sensor.sg", "SG Ready Status")]),
    )
    status, _ = systemstatus(anlage)
    assert [z["titel"] for z in status] == ["Betriebszustand", "SG Ready"]
    assert regelung(anlage) is None


@requires_ha()
def test_ab_zwei_erzeugern_zieht_sg_ready_in_die_regelung():
    """Der Hybridmanager nennt seine Betriebsart und je Erzeuger die Leistung, an der er liefert."""
    from custom_components.heatnexus.panel.daten import systemstatus
    from custom_components.heatnexus.panel.regelung import regelung

    anlage = _anlage(
        (9, [_e("sensor.phase", "Betriebsphase"), _e("sensor.kl", "Kesselleistung")]),
        (7, [_e("sensor.wp_phase", "Betriebsphase"), _e("sensor.wp", "Aktuelle Leistung")]),
        (26, [_e("select.art", "Betriebsart"), _e("sensor.sg", "SG Ready Status")]),
    )
    status, erzeuger = systemstatus(anlage)
    assert len(erzeuger) == 2
    assert "SG Ready" not in [z["titel"] for z in status]
    ergebnis = regelung(anlage)
    assert [(z["titel"], z["entity"]) for z in ergebnis["zeilen"]] == [("SG Ready", "sensor.sg")]
    assert ergebnis["hybrid"] == {
        "betriebsart": "select.art",
        "lieferanten": [
            {"name": "Teil 0", "entity": "sensor.kl"},
            {"name": "Teil 1", "entity": "sensor.wp"},
        ],
    }
    assert ergebnis["automatik"] is None


AERO = "sensor.anlage_funktion_7_1_"
BIO = "sensor.anlage_funktion_9_0_"


@requires_ha()
@requires_frontend()
@requires_moderne_ha()
async def test_ab_zwei_erzeugern_hat_jeder_kopf_und_eigene_zeilen(hass):
    """Die BioWIN Hybrid: Kopfwerte stehen nur im Kopf, jeder Erzeuger sucht bei sich."""
    from custom_components.heatnexus.dashboard.anlagen import anlagen_lesen
    from custom_components.heatnexus.panel.daten import anlage_daten

    eintrag = await _einrichten(hass, "biowin-hybrid", "betreiber")
    try:
        [anlage] = anlagen_lesen(hass)
        daten = anlage_daten(anlage)
        assert [z["titel"] for z in daten["status"]] == ["Außentemperatur"]
        regelung = daten["regelung"]
        assert [z["titel"] for z in regelung["zeilen"]] == ["SG Ready"]
        assert regelung["hybrid"]["betriebsart"]
        assert [e["entity"] for e in regelung["hybrid"]["lieferanten"]] == [
            AERO + "aktuelle_leistung",
            BIO + "kesselleistung",
        ]
        aero, bio = daten["erzeuger"]
        assert [(z["entity"], z.get("vorsatz")) for z in aero["kopf"]] == [
            (AERO + "betriebsphase", None),
            (AERO + "aktuelle_leistung", None),
            (AERO + "cop_aktuell", "COP"),
        ]
        assert [z["titel"] for z in aero["zeilen"]] == [
            "COP heute Heizen",
            "COP heute Warmwasser",
            "Vorlauf",
            "Starts",
            "Betriebsstunden Heizen",
            "Wärmemenge Heizen",
        ]
        assert [z["entity"] for z in bio["kopf"]] == [BIO + "betriebsphase", BIO + "kesselleistung"]
        assert all(z["entity"].startswith(BIO) for z in bio["zeilen"])
    finally:
        await _abbauen(hass, eintrag)


@requires_ha()
@requires_frontend()
@requires_moderne_ha()
async def test_ab_zwei_erzeugern_zeigt_die_karte_je_erzeuger_seine_werte(hass):
    from custom_components.heatnexus.dashboard.anlage import schaubild
    from custom_components.heatnexus.dashboard.anlagen import anlagen_lesen

    eintrag = await _einrichten(hass, "biowin-hybrid", "betreiber")
    try:
        [anlage] = anlagen_lesen(hass)
        werte = schaubild(anlage, als_karte=True, mit_liste=True)["zusatzwerte"]
        assert {AERO + "aktuelle_leistung", AERO + "cop_aktuell"} <= set(werte)
        assert BIO + "kesselleistung" in werte
        assert not any(e.startswith(AERO) and "kessel" in e for e in werte)
    finally:
        await _abbauen(hass, eintrag)


@requires_ha()
@requires_frontend()
@requires_moderne_ha()
async def test_der_zweite_kessel_zeigt_seine_eigenen_werte(hass):
    """Ab zwei Erzeugern sucht auch der Zusatzkessel der DuoWIN seine Zeilen nur bei sich."""
    from custom_components.heatnexus.dashboard.anlagen import anlagen_lesen
    from custom_components.heatnexus.panel.daten import anlage_daten

    eintrag = await _einrichten(hass, "duowin", "betreiber")
    try:
        [anlage] = anlagen_lesen(hass)
        _, zusatz = anlage_daten(anlage)["erzeuger"]
        assert {z["titel"] for z in zusatz["zeilen"]} >= {"Abgastemperatur", "Betriebsstunden"}
        assert all("funktion_10_0" in z["entity"] for z in zusatz["zeilen"])
    finally:
        await _abbauen(hass, eintrag)
