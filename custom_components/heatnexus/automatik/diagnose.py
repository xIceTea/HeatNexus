"""Der Stand einer Automatik für den Diagnose-Export.

Genug, um einen gemeldeten Eingriff nachzuvollziehen: Einstellungen, wirksame
Werte, die letzte Lage, Gedächtnis, Protokoll und der Verlauf des Tages.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_util

from . import eingaben, hausmodell, kennzahlen, regel

if TYPE_CHECKING:
    from .laufzeit import Laufzeit
    from .vorhersage import Vorhersage


def _lesbar(wert: Any) -> Any:
    if isinstance(wert, datetime | date):
        return wert.isoformat()
    if isinstance(wert, dict):
        return {schluessel: _lesbar(inhalt) for schluessel, inhalt in wert.items()}
    if isinstance(wert, list | tuple):
        return [_lesbar(inhalt) for inhalt in wert]
    return wert


def _vorhersage(v: Vorhersage | None) -> dict[str, Any] | None:
    """Stufe, Horizont und Grenzen der letzten Vorhersage; die Kurve bleibt dem Panel."""
    if v is None:
        return None
    return {
        "stufe": v.stufe,
        "bis": v.bis,
        "tiefst": v.tiefst,
        "ziel_min": v.ziel_min,
        "fehler": v.fehler,
    }


def _optimierer(laufzeit: Laufzeit, heute: date) -> dict[str, Any]:
    """Grundlage und Ergebnis der Optimierungshinweise, auch bei ausgeschaltetem Schalter."""
    return {
        "tage": len(laufzeit.tage_archiv),
        "parameter_gelesen": laufzeit.parameter_gelesen,
        "parameter_verlauf": laufzeit.parameter_verlauf,
        "hinweise": [asdict(h) for h in laufzeit.hinweise_liste(heute)],
    }


def auszug(laufzeit: Laufzeit) -> dict[str, Any]:
    """Alles, was die Regel zuletzt gesehen und entschieden hat."""
    lage, werte, heute = laufzeit.lage, laufzeit.werte, dt_util.now().date()
    fenster = werte.lernfenster
    stand = laufzeit.steller.stand.als_dict()
    modell = laufzeit.hausmodell
    return _lesbar(
        {
            "heizkreis": laufzeit.device_id,
            "name": laufzeit.name,
            "konfig": laufzeit.konfig,
            "werte": asdict(werte),
            "status": kennzahlen.status(laufzeit),
            "zustand": laufzeit.zustand.value,
            "begruendung": laufzeit.begruendung,
            "lage": asdict(lage) if lage else None,
            "grenze": regel.grenze(lage, werte) if lage else None,
            "gedaechtnis": regel.gedaechtnis_als_dict(laufzeit.gedaechtnis),
            "steller": {name: inhalt for name, inhalt in stand.items() if name != "protokoll"},
            "protokoll": stand.get("protokoll", []),
            "prognose_frisch": laufzeit.prognose_frisch,
            "pausiert_bis": laufzeit.pausiert_bis,
            "anforderung_zuletzt": laufzeit.anforderung_zuletzt,
            "vorrang": eingaben.lauf_als_dict(laufzeit.vorrang),
            "eingefroren": sorted(laufzeit.eingefroren),
            "stufen": laufzeit.stufen,
            "korrektur": {
                "versatz": laufzeit.temperatur.tagesversatz(fenster, heute),
                "tage_temperatur": laufzeit.temperatur.lerntage(fenster, heute),
                "faktor_sonne": laufzeit.pv.faktor(fenster, heute),
                "tage_sonne": laufzeit.pv.lerntage(fenster, heute),
            },
            "verlauf": laufzeit.verlauf,
            "hausmodell": hausmodell.als_dict(modell) if modell else None,
            "vorhersage": _vorhersage(laufzeit.vorhersage_zuletzt),
            "optimierer": _optimierer(laufzeit, heute),
        }
    )
