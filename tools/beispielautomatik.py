"""Erfundene Automatik zur Beispielanlage, für den Rundgang durch die Oberfläche.

Die Antwort hat die Form von ``heatnexus/automatik``: ein sonniger Herbsttag,
an dem die Automatik den Heizkreis über Mittag absenkt. Profile und Grenzen
stammen aus der Integration, alle Messwerte sind erfunden.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta

from custom_components.heatnexus.automatik import profile

HEIZKREIS = "geraet_heizkreis"
JETZT = 13.5

# Außentemperatur laut Prognose je Stunde, 0 bis 23 Uhr.
PROGNOSE = [
    -4.8, -5.2, -5.5, -5.9, -6.1, -6.3, -6.2, -5.6, -4.1, -2.2, -0.4, 1.0,
    1.9, 2.4, 2.6, 2.3, 1.5, 0.2, -1.2, -2.3, -3.1, -3.7, -4.2, -4.6,
]  # fmt: skip
WOLKEN = [20, 20, 18, 15, 15, 12, 12, 10, 8, 6, 5, 5, 8, 10, 12, 15, 20, 30, 40, 45, 45, 45, 45, 45]
SONNE = [0.0] * 7 + [0.02, 0.15, 0.35, 0.55, 0.7, 0.78, 0.8, 0.74, 0.6, 0.4, 0.18, 0.03] + [0.0] * 6


def _aktion(stunde: int) -> str:
    return "absenkung" if 8 <= stunde <= 15 else "programm"


def _stunden(versatz: float, gemessen: bool) -> list[dict]:
    stunden = []
    for stunde, roh in enumerate(PROGNOSE):
        vorbei = gemessen and stunde <= JETZT
        stunden.append(
            {
                "stunde": stunde,
                "roh": round(roh + versatz, 1),
                "korrigiert": round(roh + versatz - 0.6, 1),
                "wolken": WOLKEN[stunde],
                "at": round(roh + versatz + 0.4, 1) if vorbei else None,
                "raum": round(21.2 + 0.3 * SONNE[stunde], 1) if vorbei else None,
                "gedaempft": round(-0.8 + 0.12 * stunde, 2) if vorbei else None,
                "vorrang": gemessen and 11 <= stunde <= JETZT,
                "aktion": _aktion(stunde),
            }
        )
    return stunden


def _tag(versatz: float = 0.0, gemessen: bool = True) -> dict:
    return {
        "sonne": SONNE,
        "aufgang": 7.25,
        "untergang": 18.55,
        "absenkung_von": 7.0,
        "absenkung_bis": 13.67,
        "absenkung_ziel": 16.55,
        "entscheidungen": [7.0] if gemessen else [],
        "jetzt": JETZT if gemessen else None,
        "stunden": _stunden(versatz, gemessen),
    }


def automatik_daten(heute: datetime | None = None) -> dict:
    """Die Antwort von ``heatnexus/automatik`` für die Beispielanlage."""
    heute = (heute or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)

    def zeit(tage: int, stunde: int, minute: int) -> str:
        return (heute + timedelta(days=tage, hours=stunde, minutes=minute)).isoformat()

    werte = asdict(profile.VORGABEN["standard"])
    return {
        "darf_aendern": True,
        "profile": {name: asdict(w) for name, w in profile.VORGABEN.items()},
        "grenzen": profile.GRENZEN,
        "heizkreise": [
            {
                "heizkreis": HEIZKREIS,
                "name": "UMLZ HEIZKREIS",
                "anlage": "Kesselhaus",
                "anlage_id": "steuerung",
                "eingerichtet": True,
                "konfig": {
                    "heizkreis": HEIZKREIS,
                    "aktiv": True,
                    "modus": "schalten",
                    "heizflaechen": "gemischt",
                    "profil": "standard",
                    "ausrichtung": "ausgewogen",
                    "raeume": ["climate.wohnzimmer", "climate.kueche", "climate.bad"],
                    "raum_art": "mittel",
                    "raum_ziel": None,
                    "wetter": "weather.zuhause",
                    "pv": None,
                    "pv_ist": None,
                    "aussen": None,
                    "personen": [],
                    "fenster": [],
                    "fenster_erkennung": True,
                    "vorrang": ["binary_sensor.solaranlage_waermelieferung"],
                    "eigene": {},
                },
                "werte": werte,
                "vorgabe": werte,
                "zustand": "sonnentag",
                "begruendung": "Sonnentag – 19,5 °C bis 16:33.",
                "kennwerte": {
                    "sonnenquote": 68.0,
                    "raum": 21.5,
                    "soll": 21.0,
                    "abweichung": 0.3,
                    "eigene_ziele": True,
                    "raum_bezug": None,
                    "at": 2.4,
                    "at_gedaempft": 0.8,
                    "raeume": [
                        {
                            "entity_id": "climate.wohnzimmer",
                            "name": "Wohnzimmer",
                            "wert": 21.6,
                            "ziel": 21.5,
                            "heizt": False,
                            "aus": False,
                            "veraltet": False,
                        },
                        {
                            "entity_id": "climate.kueche",
                            "name": "Küche",
                            "wert": 21.2,
                            "ziel": 21.0,
                            "heizt": False,
                            "aus": False,
                            "veraltet": False,
                        },
                        {
                            "entity_id": "climate.bad",
                            "name": "Bad",
                            "wert": 22.1,
                            "ziel": 22.0,
                            "heizt": True,
                            "aus": False,
                            "veraltet": False,
                        },
                    ],
                    "raum_art": "mittel",
                    "heizgrenze": 17.0,
                    "grenze_steuerung": 17.0,
                    "grenze_absenk": 5.0,
                    "versatz": 0.0,
                    "hysterese": werte["hysterese"],
                    "sonne_schwelle": werte["sonnenquote"],
                    "stark_quote": 80.0,
                    "stark_k": werte["stark_k"],
                    "rueckkehr_k": werte["rueckkehr_k"],
                    "sonne_raum_k": 0.3,
                    "eingriffe": 1,
                    "budget": werte["budget"],
                    "naechste_pruefung": zeit(1, 7, 0),
                    "modus_seit": zeit(0, 7, 0),
                    "vorrang": {"laeuft": True, "minuten": 95},
                },
                "tag": _tag(),
                "vorschau": [
                    {
                        "datum": zeit(1, 0, 0)[:10],
                        "titel": "Morgen",
                        "zustand": "programm",
                        "begruendung": "Sonnenquote 31 % unter 60 % – keine Absenkung.",
                        "sonnenquote": 31.0,
                        "tag": _tag(-2.5, gemessen=False),
                    },
                    {
                        "datum": zeit(2, 0, 0)[:10],
                        "titel": "Übermorgen",
                        "zustand": "sonnentag",
                        "begruendung": "Sonnenquote 72 % – 19,5 °C bis 16:31.",
                        "sonnenquote": 72.0,
                        "tag": _tag(1.2, gemessen=False),
                    },
                ],
                "korrektur": {
                    "an": True,
                    "fenster": 14,
                    "noetig": 7,
                    "temperatur": {"versatz": -0.6, "versatz_bisher": -0.6, "tage": 12},
                    "sonne": {"aktiv": True, "faktor": 0.94, "faktor_bisher": 0.94, "tage": 12},
                },
                "protokoll": [
                    {
                        "zeit": zeit(0, 7, 0),
                        "art": "geschrieben",
                        "text": "Sonnenquote 68 % – 19,5 °C bis 16:33.",
                        "werte": [["/3/4/0", "19.5"], ["/2/10/0", "400"]],
                    },
                    {
                        "zeit": zeit(-1, 7, 0),
                        "art": "geprueft",
                        "text": "Sonnenquote 22 % unter 60 % – keine Absenkung.",
                        "werte": [],
                    },
                ],
                "beobachtet_seit": zeit(-14, 7, 0),
                "pausiert_bis": None,
                "entitaeten": {},
            }
        ],
    }
