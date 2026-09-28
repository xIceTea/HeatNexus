"""Was der Reiter je Tag zeigt: Sonnenbogen, Stundenraster, Vorschau der Entscheidung.

Liest nur aus der Laufzeit und rechnet die Vorschau mit derselben Regel wie
der Betrieb; geschrieben wird hier nichts.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import math
from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_util

from . import eingaben, regel

if TYPE_CHECKING:
    from .laufzeit import Laufzeit

VORSCHAU_TAGE = 2
TITEL = {0: "Heute", 1: "Morgen", 2: "Übermorgen"}


def stunde_als_zahl(zeit: datetime | None, tag: date) -> float | None:
    """Uhrzeit als Kommazahl am Tag `tag`; davor 0, danach 24."""
    if zeit is None:
        return None
    lokal = dt_util.as_local(zeit)
    if lokal.date() != tag:
        return 24.0 if lokal.date() > tag else 0.0
    return lokal.hour + lokal.minute / 60


def sonne(laufzeit: Laufzeit, tag: date) -> list[float]:
    """Relative Einstrahlung je Stunde: Tagbogen mal (1 − Bewölkung)."""
    aufgang, untergang = laufzeit.sonne(tag)
    prognose = laufzeit.stundenprognose(tag)
    if not aufgang or not untergang or not prognose:
        return []
    auf = aufgang.hour + aufgang.minute / 60
    unter = untergang.hour + untergang.minute / 60
    werte = []
    for stunde in range(25):
        if not auf < stunde < unter:
            werte.append(0.0)
            continue
        wolken = (prognose.get(stunde) or {}).get("wolken")
        bogen = math.sin(math.pi * (stunde - auf) / (unter - auf))
        anteil = 1 - (50.0 if wolken is None else float(wolken)) / 100
        werte.append(round(max(0.0, bogen * anteil), 3))
    return werte


def aktion(g: regel.Gedaechtnis, stunde: int, tag: date) -> str:
    """Was das Gedächtnis für eine Stunde vorsieht: nur_ww, absenkung oder programm."""
    if g.saison == regel.NUR_WW:
        return "nur_ww"
    von = stunde_als_zahl(g.absenkung_von, tag)
    bis = stunde_als_zahl(g.absenkung_ziel or g.absenkung_bis, tag)
    if von is not None and bis is not None and von <= stunde < bis:
        return "absenkung"
    return "programm"


def stunden(laufzeit: Laufzeit, tag: date, g: regel.Gedaechtnis) -> list[dict[str, Any]]:
    """24 Stunden mit Prognose, Messwerten und dem, was die Automatik tut."""
    prognose = laufzeit.stundenprognose(tag)
    gemessen = laufzeit.verlauf["stunden"] if laufzeit.verlauf["datum"] == tag.isoformat() else {}
    jetzt = dt_util.now()
    vorbei = jetzt.hour if tag == jetzt.date() else (24 if tag < jetzt.date() else 0)
    leer = {"roh": None, "korrigiert": None, "wolken": None}
    return [
        {
            "stunde": stunde,
            **(prognose.get(stunde) or leer),
            "at": (gemessen.get(str(stunde)) or {}).get("at"),
            "raum": (gemessen.get(str(stunde)) or {}).get("raum"),
            "gedaempft": (gemessen.get(str(stunde)) or {}).get("gedaempft"),
            "vorrang": bool((gemessen.get(str(stunde)) or {}).get("vorrang")),
            # Vergangene Stunden zeigen, was galt; ohne Vermerk lief das Programm.
            "aktion": (gemessen.get(str(stunde)) or {}).get("aktion")
            or ("programm" if stunde < vorbei else aktion(g, stunde, tag)),
        }
        for stunde in range(24)
    ]


def _band(g: regel.Gedaechtnis, tag: date) -> dict[str, float | None]:
    return {
        "absenkung_von": stunde_als_zahl(g.absenkung_von, tag),
        "absenkung_bis": stunde_als_zahl(g.absenkung_bis, tag),
        "absenkung_ziel": stunde_als_zahl(g.absenkung_ziel, tag),
    }


def heute(laufzeit: Laufzeit, jetzt: datetime) -> dict[str, Any]:
    """Der laufende Tag mit Messwerten und dem tatsächlichen Gedächtnis."""
    werte, tag, g = laufzeit.werte, jetzt.date(), laufzeit.gedaechtnis
    return {
        "sonne": sonne(laufzeit, tag),
        **_band(g, tag),
        "entscheidungen": [
            int(z[:2]) + int(z[3:]) / 60 for z in (werte.entscheidung, werte.nachpruefung) if z
        ],
        "jetzt": jetzt.hour + jetzt.minute / 60,
        "stunden": stunden(laufzeit, tag, g),
    }


def _pv_sensor(laufzeit: Laufzeit, abstand: int) -> str | None:
    # Forecast.Solar und Solcast benennen die Folgetage nach demselben Muster.
    heute_sensor = laufzeit.konfig.get("pv")
    if not heute_sensor or "today" not in heute_sensor:
        return heute_sensor if abstand == 0 else None
    namen = {0: "today", 1: "tomorrow", 2: "day_3"}
    kennung = heute_sensor.replace("today", namen.get(abstand, ""))
    return kennung if laufzeit.hass.states.get(kennung) is not None else None


def vorschau(laufzeit: Laufzeit, jetzt: datetime) -> list[dict[str, Any]]:
    """Morgen und übermorgen: was die Regel voraussichtlich entscheidet, Raum am Sollwert."""
    werte, g = laufzeit.werte, laufzeit.gedaechtnis
    soll = g.saison_soll or g.absenkung_basis or (laufzeit.lage.soll if laufzeit.lage else None)
    stunde, minute = (int(teil) for teil in werte.entscheidung.split(":"))
    tage = []
    for abstand in range(1, VORSCHAU_TAGE + 1):
        tag = jetzt.date() + timedelta(days=abstand)
        quote = laufzeit.sonnenquote(tag, _pv_sensor(laufzeit, abstand))
        # Für einen kommenden Tag steht die gedämpfte AT noch nicht fest; das Mittel aus
        # Vortag und Tag laut angepasster Prognose kommt ihr am nächsten.
        mittel = [
            m
            for m in (laufzeit.tagesmittel(tag - timedelta(days=1)), laufzeit.tagesmittel(tag))
            if m is not None
        ]
        lage = regel.Lage(
            jetzt=dt_util.start_of_local_day(tag).replace(hour=stunde, minute=minute),
            at_gedaempft=sum(mittel) / len(mittel) if mittel else None,
            raeume=() if soll is None else ((soll, None),),
            soll=soll,
            sonnenquote=quote,
            mittel_heute=laufzeit.tagesmittel(tag),
            mittel_morgen=laufzeit.tagesmittel(tag + timedelta(days=1)),
            sonnenuntergang=laufzeit.sonne(tag)[1],
            betriebswahl=6 if g.saison == regel.NUR_WW else 1,
            entscheidungszeit=True,
        )
        ausgang = regel.Gedaechtnis(saison=g.saison, saison_soll=g.saison_soll)
        entscheidung = regel.entscheiden(lage, ausgang, werte)
        begruendung = entscheidung.begruendung
        if entscheidung.aktionen and eingaben.hat_thermostat(laufzeit.konfig["raeume"]):
            begruendung += " Vorausgesetzt, die Räume fordern keine Wärme an."
        tage.append(
            {
                "datum": tag.isoformat(),
                "titel": TITEL[abstand],
                "zustand": entscheidung.zustand.value,
                "begruendung": begruendung,
                "sonnenquote": quote,
                "tag": {
                    "sonne": sonne(laufzeit, tag),
                    **_band(entscheidung.gedaechtnis, tag),
                    "entscheidungen": [],
                    "jetzt": None,
                    "stunden": stunden(laufzeit, tag, entscheidung.gedaechtnis),
                },
            }
        )
    return tage


def raumwerte(laufzeit: Laufzeit) -> list[dict[str, Any]]:
    """Jeder gewählte Raum mit Name und aktuellem Wert."""
    ergebnis = []
    for entity_id in laufzeit.konfig["raeume"]:
        zustand = laufzeit.hass.states.get(entity_id)
        name = zustand.attributes.get("friendly_name") if zustand else None
        seit = laufzeit.seit(entity_id)
        ist, ziel, heizt, aus = laufzeit.messung(entity_id) or (None, None, None, False)
        ergebnis.append(
            {
                "entity_id": entity_id,
                "name": name or entity_id,
                "wert": ist,
                "ziel": ziel,
                "heizt": heizt,
                "aus": aus,
                "veraltet": laufzeit.veraltet(entity_id),
                "seit": seit.isoformat() if seit else None,
            }
        )
    return ergebnis
