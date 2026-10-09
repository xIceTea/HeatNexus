"""Hausmodell je Heizkreis: ein Wärmespeicher, gelernt aus Stundenwerten.

Je Stunde ändert sich der Raum um Auskühlen gegen die Außenluft (durch Wind
verstärkt), Sonnengewinn und Heizen. Ohne Home Assistant, für sich testbar.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

FREIGABE_TAGE = 5
FREIGABE_FEHLER_K = 0.5
FEHLER_TAGE = 14
# Wind bleibt nur, wenn er den mittleren Fehler um mindestens diesen Anteil senkt.
WIND_NUTZEN = 0.05
MIN_STUNDEN = 48


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


def _merkmale(s: Stunde, mit_wind: bool) -> list[float]:
    abstand = s.at - s.raum
    werte = [abstand, s.sonne, s.heizen]
    if mit_wind:
        werte.insert(1, abstand * (s.wind or 0.0))
    return werte


def _ausgleich(stunden: Sequence[Stunde], mit_wind: bool) -> list[float] | None:
    zeilen = [(_merkmale(s, mit_wind), s.raum_danach - s.raum) for s in stunden]
    n = len(zeilen[0][0])
    ata = [[sum(x[i] * x[j] for x, _ in zeilen) for j in range(n)] for i in range(n)]
    atb = [sum(x[i] * y for x, y in zeilen) for i in range(n)]
    return _loesen(ata, atb)


def _mae(stunden: Sequence[Stunde], koeff: list[float], mit_wind: bool) -> float:
    fehler = [
        abs(
            sum(k * x for k, x in zip(koeff, _merkmale(s, mit_wind), strict=True))
            - (s.raum_danach - s.raum)
        )
        for s in stunden
    ]
    return sum(fehler) / len(fehler)


def lernen(stunden: list[Stunde], heiz_art: str, tage: int) -> Modell | None:
    """Kleinste Quadrate über vollständige Stunden; physikalisch Unsinniges ergibt `None`."""
    gut = [s for s in stunden if s.raum_danach is not None]
    if len(gut) < MIN_STUNDEN:
        return None
    ohne = _ausgleich(gut, mit_wind=False)
    if ohne is None or ohne[0] <= 0 or ohne[1] < 0 or ohne[2] < 0:
        return None
    a, s, h, w = ohne[0], ohne[1], ohne[2], 0.0
    mit = _ausgleich(gut, mit_wind=True) if all(x.wind is not None for x in gut) else None
    plausibel = mit is not None and min(mit) >= 0 and mit[0] > 0
    if plausibel and _mae(gut, mit, True) <= _mae(gut, ohne, False) * (1 - WIND_NUTZEN):
        a, w, s, h = mit[0], mit[1] / mit[0], mit[2], mit[3]
    return Modell(1 / a, w, s, h, heiz_art, tage)


def schritt(
    modell: Modell, raum: float, at: float, sonne: float, wind: float | None, heizen: float
) -> float:
    """Der Raumwert eine Stunde später."""
    verlust = (raum - at) * (1 + modell.wind_je_ms * (wind or 0.0)) / modell.auskuehlzeit_h
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
    """Mittlerer absoluter Fehler, wenn das Modell den Tag aus dem ersten Wert vorrechnet."""
    gut = [s for s in tag if s.raum_danach is not None]
    if len(gut) < 12:
        return None
    raum, fehler = gut[0].raum, []
    for s in gut:
        raum = schritt(modell, raum, s.at, s.sonne, s.wind, s.heizen)
        fehler.append(abs(raum - s.raum_danach))
    return sum(fehler) / len(fehler)


def mittlerer_fehler(modell: Modell) -> float | None:
    """Mittel der gespeicherten Tagesfehler, ohne Tage `None`."""
    return sum(modell.fehler) / len(modell.fehler) if modell.fehler else None


def freigegeben(modell: Modell | None) -> bool:
    """Ab fünf Tagen und mittlerem Fehler bis 0,5 K darf das Modell entscheiden."""
    if modell is None or modell.tage < FREIGABE_TAGE:
        return False
    fehler = mittlerer_fehler(modell)
    return fehler is not None and fehler <= FREIGABE_FEHLER_K


def als_dict(modell: Modell) -> dict[str, Any]:
    """Für den Store; `fehler` als Liste."""
    return {**asdict(modell), "fehler": list(modell.fehler)}


def aus_dict(roh: Any) -> Modell | None:
    """Aus dem Store; Unlesbares ergibt `None`."""
    if not isinstance(roh, dict):
        return None
    try:
        return Modell(
            float(roh["auskuehlzeit_h"]),
            float(roh["wind_je_ms"]),
            float(roh["sonne_k_h"]),
            float(roh["heizwirkung"]),
            str(roh["heiz_art"]),
            int(roh["tage"]),
            tuple(float(f) for f in roh.get("fehler", ()))[-FEHLER_TAGE:],
        )
    except (KeyError, TypeError, ValueError):
        return None
