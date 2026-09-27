"""Eingänge der Automatik aufbereiten: gedämpfte AT, Raum, Sonne, Fenster.

Reine Rechnungen ohne Home Assistant; Zeiten kommen als `datetime` mit Zone.
"""

from __future__ import annotations

from datetime import date, datetime
import math

# Unter so vielen Vergleichstagen sagt der PV-Ertrag nichts über die Sonne.
PV_MIN_TAGE = 7


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
