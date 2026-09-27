"""Eingänge der Automatik aufbereiten: gedämpfte AT, Raum, Sonne, Fenster.

Reine Rechnungen ohne Home Assistant; Zeiten kommen als `datetime` mit Zone.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
import math
from typing import Any

# Unter so vielen Vergleichstagen sagt der PV-Ertrag nichts über die Sonne.
PV_MIN_TAGE = 7
# Ein Thermostat in diesen Zuständen regelt den Raum nicht; er zählt dann nicht.
THERMOSTAT_AUS = frozenset({"off", "unavailable", "unknown"})


def daempfen(
    stufen: tuple[float, float] | None, messwert: float, dt_s: float, tau_h: float
) -> tuple[float, float]:
    """Zwei Filter erster Ordnung hintereinander, wie die gedämpfte AT bei Siemens."""
    if stufen is None:
        return (messwert, messwert)
    alpha = 1.0 - math.exp(-max(dt_s, 0.0) / (tau_h * 3600.0))
    eins = stufen[0] + alpha * (messwert - stufen[0])
    zwei = stufen[1] + alpha * (eins - stufen[1])
    return (eins, zwei)


def raumwert(werte: list[float | None], art: str) -> float | None:
    """Mittel der Fühler oder der kälteste Raum; ohne gültigen Wert nichts."""
    gueltig = [wert for wert in werte if wert is not None]
    if not gueltig:
        return None
    return min(gueltig) if art == "minimum" else sum(gueltig) / len(gueltig)


def _zahl(wert: Any) -> float | None:
    if wert is None or isinstance(wert, bool):
        return None
    try:
        zahl = float(wert)
    except (TypeError, ValueError):
        return None
    return zahl if math.isfinite(zahl) else None


def raum_messung(
    entity_id: str, zustand: str, attribute: Mapping[str, Any]
) -> tuple[float, float | None, bool | None] | None:
    """Ist, eigenes Ziel und Wärmeanforderung eines Raums; ein Sensor kennt nur den Ist-Wert."""
    if not entity_id.startswith("climate."):
        return None if (ist := _zahl(zustand)) is None else (ist, None, None)
    if zustand in THERMOSTAT_AUS or (ist := _zahl(attribute.get("current_temperature"))) is None:
        return None
    return (ist, _zahl(attribute.get("temperature")), attribute.get("hvac_action") == "heating")


def sonnenquote_aus_bewoelkung(
    stunden: list[tuple[datetime, float | None]], aufgang: datetime, untergang: datetime
) -> float | None:
    """100 minus mittlere Bewölkung der Stunden zwischen Auf- und Untergang."""
    werte = [
        wolken for zeit, wolken in stunden if wolken is not None and aufgang <= zeit < untergang
    ]
    if not werte:
        return None
    return max(0.0, min(100.0, 100.0 - sum(werte) / len(werte)))


def sonnenquote_aus_pv(heute_kwh: float | None, bisher: list[float]) -> float | None:
    """Erwarteter PV-Ertrag heute im Verhältnis zum besten Tag der letzten Wochen."""
    if heute_kwh is None or len(bisher) < PV_MIN_TAGE:
        return None
    bester = max([heute_kwh, *bisher])
    if bester <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * heute_kwh / bester))


def tagesmittel(tage: list[tuple[date, float | None, float | None]], tag: date) -> float | None:
    """Mittel aus Höchst- und Tiefstwert der Tagesprognose; ohne Tiefstwert der Höchstwert."""
    for datum, hoch, tief in tage:
        if datum != tag or hoch is None:
            continue
        return hoch if tief is None else (hoch + tief) / 2
    return None


def temperatursturz(
    verlauf: list[tuple[float, float]], schwelle_k_je_h: float, fenster_s: float = 600.0
) -> bool:
    """Ob der Raum im Zeitfenster schneller fällt als die Schwelle; `verlauf` aufsteigend."""
    if len(verlauf) < 2:
        return False
    ende_zeit, ende_wert = verlauf[-1]
    for zeit, wert in verlauf:
        dauer = ende_zeit - zeit
        if dauer > fenster_s:
            continue
        if dauer < 60:
            return False
        return (wert - ende_wert) / dauer * 3600.0 >= schwelle_k_je_h
    return False


def wert_zur_stunde(reihe: list[tuple[datetime, float]], stunde: datetime) -> float | None:
    """Der Wert, der zur vollen Stunde galt; davor der erste innerhalb der Stunde."""
    geltend = None
    for zeit, wert in reihe:
        if zeit <= stunde:
            geltend = wert
        elif geltend is None and zeit < stunde + timedelta(hours=1):
            return wert
        else:
            break
    return geltend
