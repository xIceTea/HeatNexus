"""Welche Entität eines Anlagenteils wo im Dashboard steht."""

from __future__ import annotations

from typing import Any

from .. import geraete
from ..helpers import mustername
from ..schema import passt as _passt
from .anlagen import vorrang
from .muster import BEDIENBAR, UEBERSICHT_TASTEN, ZEITPROGRAMM

# Ohne Eintrag im Baureihenmodul: so viele Werte nach `vorrang()` in der Übersicht.
KERNWERTE_RUECKFALL = 2
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


def messwerte(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Abzulesende Werte, die wichtigsten zuerst."""
    werte = [
        e
        for e in teil["entitaeten"]
        if _sichtbar(e) and e["bereich"] not in BEDIENBAR and not _ist_zeitprogramm(e)
    ]
    return sorted(werte, key=lambda e: (vorrang(e), e["name"]))


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


def kernwerte(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Die Werte für die Übersicht: nach Baureihenmodul, sonst die ersten Messwerte."""
    schluessel = geraete.KERNWERTE.get(_fct(teil))
    if schluessel is None:
        return messwerte(teil)[:KERNWERTE_RUECKFALL]
    return [e for s in schluessel if (e := _mit_schluessel(teil, s))]


def zeitprogramme(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Die Zeitprogramm-Sensoren des Anlagenteils."""
    return [e for e in teil["entitaeten"] if _ist_zeitprogramm(e)]


def einstellungen(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Konfigurationswerte des Anlagenteils."""
    return [e for e in teil["entitaeten"] if e["kategorie"] == "config"]


def diagnose(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Diagnosewerte des Anlagenteils."""
    return [e for e in teil["entitaeten"] if e["kategorie"] == "diagnostic"]


def _meldung(teil: dict[str, Any], art: str) -> dict[str, Any] | None:
    return next((e for e in teil["entitaeten"] if e.get("meldungsart") == art), None)


def klartext(teil: dict[str, Any]) -> dict[str, Any] | None:
    """Der Klartext-Sensor der Meldung, falls vorhanden."""
    return _meldung(teil, "fe01text")


def stoerung(teil: dict[str, Any]) -> dict[str, Any] | None:
    """Der Störungssensor, falls vorhanden."""
    return _meldung(teil, "fe01stoerung")


def tasten(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Alltägliche Tasten für die Übersicht."""
    return [
        e
        for e in teil["entitaeten"]
        if e["bereich"] == "button" and _passt(mustername(e), UEBERSICHT_TASTEN)
    ]
