"""Hausmodell je Heizkreis: ein Wärmespeicher, gelernt aus Stundenwerten.

Je Stunde ändert sich der Raum um Auskühlen gegen die Außenluft (durch Wind
verstärkt), Sonnengewinn und Heizen. Ohne Home Assistant, für sich testbar.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
import math
from typing import Any

FREIGABE_TAGE = 14
FREIGABE_FEHLER_K = 0.5
FREIGABE_ANTEIL = 0.8
FEHLER_TAGE = 28
HEIZ_ARTEN = frozenset({"vorlauf", "pumpe"})
# Wind bleibt nur, wenn er den mittleren Fehler um mindestens diesen Anteil senkt.
WIND_NUTZEN = 0.05
MIN_STUNDEN = 48
MIN_AUSKUEHLZEIT_H = 2.0
MAX_AUSKUEHLZEIT_H = 500.0


@dataclass(frozen=True)
class Stunde:
    """Werte einer Stunde; `raum_danach` nur beim Lernen."""

    raum: float
    raum_danach: float | None
    at: float
    sonne: float
    wind: float | None
    heizen: float


@dataclass(frozen=True)
class Modell:
    """Gelernte Hauswerte und die Treffsicherheit der letzten Tage."""

    auskuehlzeit_h: float
    wind_je_ms: float
    sonne_k_h: float
    heizwirkung: float
    heiz_art: str
    tage: int
    fehler: tuple[float, ...] = ()
    wind_mittel: float = 0.0
    fehler_bleibt: tuple[float, ...] = ()


def _loesen(a: list[list[float]], b: list[float]) -> list[float] | None:
    """Gauß-Elimination mit Pivotsuche; `None` bei singulärer Matrix."""
    n = len(b)
    m = [[*zeile, b[i]] for i, zeile in enumerate(a)]
    for spalte in range(n):
        pivot = max(range(spalte, n), key=lambda z: abs(m[z][spalte]))
        if abs(m[pivot][spalte]) < 1e-12:
            return None
        m[spalte], m[pivot] = m[pivot], m[spalte]
        for zeile in range(spalte + 1, n):
            faktor = m[zeile][spalte] / m[spalte][spalte]
            for k in range(spalte, n + 1):
                m[zeile][k] -= faktor * m[spalte][k]
    x = [0.0] * n
    for zeile in range(n - 1, -1, -1):
        rest = m[zeile][n] - sum(m[zeile][k] * x[k] for k in range(zeile + 1, n))
        x[zeile] = rest / m[zeile][zeile]
    return x


def _merkmale(s: Stunde) -> list[float]:
    abstand = s.at - s.raum
    return [abstand, abstand * (s.wind or 0.0), s.sonne, s.heizen]


def _anpassen(
    stunden: Sequence[Stunde], spalten: tuple[int, ...]
) -> tuple[list[float], tuple[int, ...]] | None:
    """Kleinste Quadrate; negative Koeffizienten außer dem Auskühlen entfallen, dann neu anpassen."""
    ziel = [s.raum_danach - s.raum for s in stunden]
    while True:
        zeilen = [[_merkmale(s)[i] for i in spalten] for s in stunden]
        n = len(spalten)
        ata = [[sum(z[i] * z[j] for z in zeilen) for j in range(n)] for i in range(n)]
        atb = [sum(z[i] * y for z, y in zip(zeilen, ziel, strict=True)) for i in range(n)]
        loesung = _loesen(ata, atb)
        if loesung is None or loesung[0] <= 0:
            return None
        negativ = min(range(1, n), key=loesung.__getitem__, default=None)
        if negativ is None or loesung[negativ] >= 0:
            break
        spalten = spalten[:negativ] + spalten[negativ + 1 :]
    koeff = [0.0] * 4
    for i, wert in zip(spalten, loesung, strict=True):
        koeff[i] = wert
    return koeff, spalten


def _mae(stunden: Sequence[Stunde], koeff: list[float]) -> float:
    fehler = [
        abs(sum(k * x for k, x in zip(koeff, _merkmale(s), strict=True)) - (s.raum_danach - s.raum))
        for s in stunden
    ]
    return sum(fehler) / len(fehler)


def lernen(stunden: list[Stunde], heiz_art: str, tage: int) -> Modell | None:
    """Kleinste Quadrate über vollständige Stunden; Sonne und Heizen entfallen bei negativem Anteil."""
    gut = [s for s in stunden if s.raum_danach is not None]
    if len(gut) < MIN_STUNDEN:
        return None
    heizt = any(s.heizen > 0 for s in gut)
    if (basis := _anpassen(gut, (0, 2, 3) if heizt else (0, 2))) is None:
        return None
    (a, _, s, h), spalten = basis
    w, wind_mittel = 0.0, 0.0
    mit = (
        _anpassen(gut, tuple(sorted({*spalten, 1})))
        if all(x.wind is not None for x in gut)
        else None
    )
    if mit and _mae(gut, mit[0]) <= _mae(gut, basis[0]) * (1 - WIND_NUTZEN):
        a, w, s, h = mit[0][0], mit[0][1] / mit[0][0], mit[0][2], mit[0][3]
        wind_mittel = sum(x.wind for x in gut) / len(gut)
    if not MIN_AUSKUEHLZEIT_H <= 1 / a <= MAX_AUSKUEHLZEIT_H:
        return None
    return Modell(1 / a, w, s, h, heiz_art, tage, (), wind_mittel)


def schritt(
    modell: Modell, raum: float, at: float, sonne: float, wind: float | None, heizen: float
) -> float:
    """Der Raumwert eine Stunde später; fehlender Wind gilt als mittlerer Wind des Lernens."""
    ms = modell.wind_mittel if wind is None else wind
    verlust = (raum - at) * (1 + modell.wind_je_ms * ms) / modell.auskuehlzeit_h
    return raum - verlust + modell.sonne_k_h * sonne + modell.heizwirkung * heizen


def vorhersagen(
    modell: Modell, raum: float, eingaben: list[tuple[float, float, float | None, float]]
) -> list[float]:
    """Raumwerte nach jeder Stunde; `heizen` je Stunde kommt vom Aufrufer."""
    werte = []
    for at, sonne, wind, heizen in eingaben:
        raum = schritt(modell, raum, at, sonne, wind, heizen)
        werte.append(raum)
    return werte


def tagesfehler(modell: Modell, tag: list[Stunde]) -> float | None:
    """Mittlerer absoluter Fehler; nach einer Lücke startet die Rechnung beim Messwert neu."""
    if sum(s.raum_danach is not None for s in tag) < 12:
        return None
    raum, fehler = None, []
    for s in tag:
        if s.raum_danach is None:
            raum = None
            continue
        raum = schritt(modell, s.raum if raum is None else raum, s.at, s.sonne, s.wind, s.heizen)
        fehler.append(abs(raum - s.raum_danach))
    return sum(fehler) / len(fehler)


def tagesfehler_bleibt(tag: list[Stunde]) -> float | None:
    """Mittlerer Fehler von „Raum bleibt“: der Startwert gilt für den Rest, nach einer Lücke neu."""
    if sum(s.raum_danach is not None for s in tag) < 12:
        return None
    start, fehler = None, []
    for s in tag:
        if s.raum_danach is None:
            start = None
            continue
        start = s.raum if start is None else start
        fehler.append(abs(start - s.raum_danach))
    return sum(fehler) / len(fehler)


def mittlerer_fehler(modell: Modell) -> float | None:
    """Mittel der gespeicherten Tagesfehler, ohne Tage `None`."""
    return sum(modell.fehler) / len(modell.fehler) if modell.fehler else None


def freigegeben(modell: Modell | None) -> bool:
    """Frei, wenn das Modell über genug Tage klein und deutlich besser als „Raum bleibt“ lag."""
    if modell is None or len(modell.fehler) != len(modell.fehler_bleibt):
        return False
    if len(modell.fehler) < FREIGABE_TAGE:
        return False
    fehler = sum(modell.fehler) / len(modell.fehler)
    bleibt = sum(modell.fehler_bleibt) / len(modell.fehler_bleibt)
    return fehler <= FREIGABE_FEHLER_K and fehler <= FREIGABE_ANTEIL * bleibt


def als_dict(modell: Modell) -> dict[str, Any]:
    """Für den Store; beide Fehlerreihen als Liste der letzten Tage."""
    return {
        **asdict(modell),
        "fehler": list(modell.fehler[-FEHLER_TAGE:]),
        "fehler_bleibt": list(modell.fehler_bleibt[-FEHLER_TAGE:]),
    }


def _gueltig(modell: Modell) -> bool:
    zahlen = (modell.auskuehlzeit_h, modell.wind_je_ms, modell.sonne_k_h, modell.heizwirkung)
    zahlen += (modell.wind_mittel, *modell.fehler, *modell.fehler_bleibt)
    return (
        all(math.isfinite(z) for z in zahlen)
        and modell.auskuehlzeit_h > 0
        and modell.heiz_art in HEIZ_ARTEN
    )


def aus_dict(roh: Any) -> Modell | None:
    """Aus dem Store; Unlesbares oder Unsinniges ergibt `None`."""
    if not isinstance(roh, dict):
        return None
    try:
        modell = Modell(
            float(roh["auskuehlzeit_h"]),
            float(roh["wind_je_ms"]),
            float(roh["sonne_k_h"]),
            float(roh["heizwirkung"]),
            str(roh["heiz_art"]),
            int(roh["tage"]),
            tuple(float(f) for f in roh.get("fehler", ()))[-FEHLER_TAGE:],
            float(roh.get("wind_mittel", 0.0)),
            tuple(float(f) for f in roh.get("fehler_bleibt", ()))[-FEHLER_TAGE:],
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    return modell if _gueltig(modell) else None
