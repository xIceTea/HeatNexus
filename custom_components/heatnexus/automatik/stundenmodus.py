"""Welcher Modus in welcher vergangenen Stunde galt: aus Vermerken und Protokoll."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, time, timedelta, tzinfo
from typing import Any

OID_SOLL = "/3/4/0"
OID_DAUER = "/2/10/0"
OID_BETRIEBSWAHL = "/3/50/0"
PROGRAMM = "programm"


def _minuten(wert: Any) -> float:
    try:
        return float(wert)
    except (TypeError, ValueError):
        return 0.0


def _ereignisse(
    protokoll: Iterable[Mapping[str, Any]], tag: date, nur_ww_wert: int
) -> list[tuple[datetime, str, datetime | None]]:
    """Geschriebene Eingriffe bis Ende `tag` als (Zeit, Modus, Ende), aufsteigend.

    Ein Eingriff von einem Vortag (z. B. nur_ww über Mitternacht) zählt als
    Startzustand mit; nur Eingriffe nach `tag` werden verworfen.
    """
    liste = []
    for eintrag in protokoll:
        if eintrag.get("art") != "geschrieben":
            continue
        try:
            zeit = datetime.fromisoformat(str(eintrag.get("zeit")))
        except ValueError:
            continue
        if zeit.date() > tag:
            continue
        werte = {str(oid): str(wert) for oid, wert in eintrag.get("werte") or ()}
        dauer = _minuten(werte.get(OID_DAUER))
        if OID_BETRIEBSWAHL in werte:
            modus = "nur_ww" if werte[OID_BETRIEBSWAHL] == str(nur_ww_wert) else PROGRAMM
            liste.append((zeit, modus, None))
        elif OID_SOLL in werte and dauer > 0:
            liste.append((zeit, "absenkung", zeit + timedelta(minutes=dauer)))
        elif OID_DAUER in werte and dauer == 0:
            liste.append((zeit, PROGRAMM, None))
    return sorted(liste, key=lambda e: e[0])


def _modus_am(ereignisse: list[tuple[datetime, str, datetime | None]], zeitpunkt: datetime) -> str:
    modus, ende = PROGRAMM, None
    for zeit, neu, bis in ereignisse:
        if zeit >= zeitpunkt:
            break
        modus, ende = neu, bis
    return PROGRAMM if ende is not None and zeitpunkt > ende else modus


def ergaenzen(
    vermerke: Mapping[int, str],
    protokoll: Iterable[Mapping[str, Any]],
    tag: date,
    vorbei: int,
    nur_ww_wert: int,
    zone: tzinfo,
) -> dict[int, str]:
    """Jede Stunde vor `vorbei` mit Modus; Lücken nach einem Vermerk erben ihn.

    Vor dem ersten Vermerk gilt der Modus am Ende der Stunde laut Protokoll,
    auch wenn der zugehörige Eingriff an einem Vortag geschrieben wurde.
    """
    ereignisse = _ereignisse(protokoll, tag, nur_ww_wert)
    ergebnis: dict[int, str] = {}
    letzter: str | None = None
    for stunde in range(vorbei):
        if stunde in vermerke:
            letzter = vermerke[stunde]
        elif letzter is None:
            ende = datetime.combine(tag, time(stunde), zone) + timedelta(hours=1)
            ergebnis[stunde] = _modus_am(ereignisse, ende)
            continue
        ergebnis[stunde] = letzter
    return ergebnis
