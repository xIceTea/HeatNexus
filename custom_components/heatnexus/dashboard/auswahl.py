"""Welche Entität eines Anlagenteils wo im Dashboard steht."""

from __future__ import annotations

from typing import Any

from .. import geraete
from ..const import GERAETEINFO_ADRESSEN
from ..helpers import mustername
from ..schema import passt as _passt
from .anlagen import vorrang
from .muster import BEDIENBAR, ZEITPROGRAMM

ZEIGER_MAX = 2


def _fct(teil: dict[str, Any]) -> int | None:
    try:
        return int(teil.get("fct_type"))
    except (TypeError, ValueError):
        return None


def _sichtbar(e: dict[str, Any]) -> bool:
    return e["hat_wert"] and e["kategorie"] is None


def _mit_schluessel(teil: dict[str, Any], schluessel: str) -> dict[str, Any] | None:
    return next(
        (e for e in teil["entitaeten"] if e.get("schluessel") == schluessel and _sichtbar(e)),
        None,
    )


def _ist_zeitprogramm(e: dict[str, Any]) -> bool:
    return e["bereich"] == "sensor" and _passt(mustername(e), ZEITPROGRAMM)


def _ist_geraeteinfo(e: dict[str, Any]) -> bool:
    return e.get("adresse") in GERAETEINFO_ADRESSEN


def _ohne_namen(e: dict[str, Any]) -> bool:
    """Ein Datenpunkt, für den es nur die Adresse als Namen gibt."""
    return mustername(e).startswith("Datenpunkt ")


def messwerte(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Abzulesende Werte, die wichtigsten zuerst."""
    werte = [
        e
        for e in teil["entitaeten"]
        if _sichtbar(e)
        and e["bereich"] not in BEDIENBAR
        and not _ist_zeitprogramm(e)
        and not _ist_geraeteinfo(e)
    ]
    return sorted(werte, key=lambda e: (vorrang(e), e["name"]))


def zustand(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Die Messwerte für den Abschnitt „Zustand“, ohne namenlose Datenpunkte."""
    return [e for e in messwerte(teil) if not _ohne_namen(e)]


def bedienung(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Was der Nutzer schaltet oder einstellt, ohne Thermostate."""
    return [
        e
        for e in teil["entitaeten"]
        if e["kategorie"] is None and e["bereich"] in BEDIENBAR and e["bereich"] != "climate"
    ]


def thermostate(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Die Klimaentitäten des Anlagenteils."""
    return [e for e in teil["entitaeten"] if e["bereich"] == "climate"]


def zeigerinstrumente(teil: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Entität und Skala je Zeigerinstrument nach Baureihenmodul."""
    paare = [
        (e, skala)
        for schluessel, skala in geraete.RUNDINSTRUMENTE.get(_fct(teil), ())
        if (e := _mit_schluessel(teil, schluessel))
    ]
    return paare[:ZEIGER_MAX]


def zeitprogramme(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Die Zeitprogramm-Sensoren des Anlagenteils."""
    return [e for e in teil["entitaeten"] if _ist_zeitprogramm(e)]


def einstellungen(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Konfigurationswerte des Anlagenteils; Zeitprogramme stehen in eigenem Abschnitt."""
    return [
        e for e in teil["entitaeten"] if e["kategorie"] == "config" and not _ist_zeitprogramm(e)
    ]


def diagnose(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Diagnosewerte des Anlagenteils, dazu die Angaben über das Gerät selbst."""
    return [
        e
        for e in teil["entitaeten"]
        if e["kategorie"] == "diagnostic" or (e["kategorie"] is None and _ist_geraeteinfo(e))
    ]


def _meldung(teil: dict[str, Any], art: str) -> dict[str, Any] | None:
    return next((e for e in teil["entitaeten"] if e.get("meldungsart") == art), None)


def klartext(teil: dict[str, Any]) -> dict[str, Any] | None:
    """Der Klartext-Sensor der Meldung, falls vorhanden."""
    return _meldung(teil, "fe01text")


def stoerung(teil: dict[str, Any]) -> dict[str, Any] | None:
    """Der Störungssensor, falls vorhanden."""
    return _meldung(teil, "fe01stoerung")
