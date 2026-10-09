"""Hausmodell je Heizkreis: ein Wärmespeicher, gelernt aus Stundenwerten.

Je Stunde ändert sich der Raum um Auskühlen gegen die Außenluft (durch Wind
verstärkt), Sonnengewinn und Heizen. Gelernt wird aus Stunden ohne Heizen, weil
das Modell vorhersagt, was eine Heizpause bewirkt. Ohne Home Assistant testbar.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
import math
from typing import Any

# Ein Modell aus einem anderen Lernverfahren wird beim Laden verworfen und neu gelernt.
FASSUNG = 3
FREIGABE_TAGE = 14
FREIGABE_FEHLER_K = 0.5
FREIGABE_ANTEIL = 0.8
FEHLER_TAGE = 28
HEIZ_ARTEN = frozenset({"vorlauf", "pumpe"})
# Darunter gilt eine Stunde als ohne Heizen: Vorlauf über Raum in K, Pumpe als Anteil der Stunde.
AUS_GRENZE = {"vorlauf": 5.0, "pumpe": 0.2}
STRECKE_H = 12
STRECKE_TAKT = 3
STRECKE_MIN = 3
MIN_STUNDEN_AUS = 24
MIN_HEIZSTUNDEN = 12
MAX_SONNE_K_H = 2.0
MAX_HEIZWIRKUNG = {"vorlauf": 0.1, "pumpe": 2.0}
RASTER = 20
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


def heizt(stunde: Stunde, heiz_art: str) -> bool:
    """Ob der Heizkreis in dieser Stunde Wärme liefert."""
    return stunde.heizen >= AUS_GRENZE[heiz_art]


def _laeufe(stunden: Sequence[Stunde], passt: Any) -> list[list[Stunde]]:
    """Zusammenhängende Stunden mit Folgewert, für die `passt` gilt; alles andere trennt."""
    laeufe, lauf = [], []
    for s in stunden:
        if s.raum_danach is not None and passt(s):
            lauf.append(s)
            continue
        laeufe.append(lauf)
        lauf = []
    laeufe.append(lauf)
    return [lauf for lauf in laeufe if len(lauf) >= STRECKE_MIN]


def _fenster(laeufe: list[list[Stunde]]) -> list[list[Stunde]]:
    """Fenster bis `STRECKE_H` Stunden, Beginn alle `STRECKE_TAKT` Stunden."""
    return [
        lauf[i : i + STRECKE_H]
        for lauf in laeufe
        for i in range(0, len(lauf) - STRECKE_MIN + 1, STRECKE_TAKT)
    ]


def strecken(stunden: Sequence[Stunde], heiz_art: str) -> list[list[Stunde]]:
    """Fenster ohne Heizen."""
    return _fenster(_laeufe(stunden, lambda s: not heizt(s, heiz_art)))


def stunden_ohne_heizen(stunden: Sequence[Stunde], heiz_art: str) -> int:
    """Wie viele Stunden ohne Heizen zum Lernen taugen."""
    return sum(len(lauf) for lauf in _laeufe(stunden, lambda s: not heizt(s, heiz_art)))


def _laufen(tau: float, sonne_k: float, heiz: float, fenster: list[list[Stunde]]) -> float:
    """Mittlerer Fehler je Stunde, wenn jedes Fenster vom Startwert aus läuft."""
    summe, anzahl = 0.0, 0
    for stunden in fenster:
        raum = stunden[0].raum
        for s in stunden:
            raum += (s.at - raum) / tau + sonne_k * s.sonne + heiz * s.heizen
            summe += abs(raum - s.raum_danach)
            anzahl += 1
    return summe / anzahl


def _minimum(f: Any, a: float, b: float, schritte: int = 24) -> tuple[float, float]:
    """Goldener Schnitt: Stelle und Wert des Minimums einer Funktion mit einem Tal."""
    g = (math.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(schritte):
        if fc <= fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = f(d)
    return (c, fc) if fc <= fd else (d, fd)


def _anpassen(fehler: Any, oben: float) -> tuple[float, float] | None:
    """Auskühlzeit im Raster, dazu der zweite Wert mit dem kleinsten Fehler; am Rand `None`."""

    def mit_bestem(log_tau: float) -> float:
        tau = math.exp(log_tau)
        return _minimum(lambda k: fehler(tau, k), 0.0, oben)[1]

    unten_tau, oben_tau = math.log(MIN_AUSKUEHLZEIT_H), math.log(MAX_AUSKUEHLZEIT_H)
    raster = [unten_tau + (oben_tau - unten_tau) * i / (RASTER - 1) for i in range(RASTER)]
    werte = [mit_bestem(x) for x in raster]
    best = min(range(RASTER), key=werte.__getitem__)
    # Liegt das Minimum am Rand des Rasters, passt keine plausible Auskühlzeit.
    if best in (0, RASTER - 1):
        return None
    log_tau, _ = _minimum(mit_bestem, raster[best - 1], raster[best + 1], 16)
    tau = math.exp(log_tau)
    k, _ = _minimum(lambda k: fehler(tau, k), 0.0, oben)
    # Der goldene Schnitt erreicht den Rand nie genau; ein Rest nahe null ist null.
    return tau, 0.0 if k < oben * 1e-3 else k


def _heizwirkung(gut: list[Stunde], heiz_art: str, tau: float, sonne_k: float) -> float:
    """Was Heizstunden über Auskühlen und Sonne hinaus erwärmen, je Einheit Heizen; nie negativ."""
    paare = [
        (s.heizen, s.raum_danach - s.raum - (s.at - s.raum) / tau - sonne_k * s.sonne)
        for s in gut
        if heizt(s, heiz_art)
    ]
    nenner = sum(x * x for x, _ in paare)
    if len(paare) < MIN_HEIZSTUNDEN or nenner <= 0:
        return 0.0
    return max(0.0, sum(x * y for x, y in paare) / nenner)


def _aus_heizstunden(stunden: list[Stunde], heiz_art: str, tage: int) -> Modell | None:
    """Ohne genug Stunden ohne Heizen: Auskühlzeit und Heizwirkung gemeinsam aus allen Stunden.

    Die Sonne lässt sich so nicht von der Heizung trennen und bleibt null.
    """
    laeufe = _laeufe(stunden, lambda _s: True)
    fenster = _fenster(laeufe)
    if sum(len(lauf) for lauf in laeufe) < MIN_STUNDEN_AUS:
        return None
    passend = _anpassen(lambda tau, h: _laufen(tau, 0.0, h, fenster), MAX_HEIZWIRKUNG[heiz_art])
    if passend is None or passend[1] <= 0:
        return None
    return Modell(passend[0], 0.0, 0.0, passend[1], heiz_art, tage)


def lernen(stunden: list[Stunde], heiz_art: str, tage: int) -> Modell | None:
    """Auskühlzeit und Sonne aus den Stunden ohne Heizen, danach die Heizwirkung.

    Heizt der Heizkreis fast durchgehend, etwa im Winter, lernt es aus den Heizstunden.
    """
    if stunden_ohne_heizen(stunden, heiz_art) < MIN_STUNDEN_AUS:
        return _aus_heizstunden(stunden, heiz_art, tage)
    fenster = strecken(stunden, heiz_art)
    if (passend := _anpassen(lambda tau, k: _laufen(tau, k, 0.0, fenster), MAX_SONNE_K_H)) is None:
        return None
    tau, sonne_k = passend
    gut = [s for s in stunden if s.raum_danach is not None]
    return Modell(tau, 0.0, sonne_k, _heizwirkung(gut, heiz_art, tau, sonne_k), heiz_art, tage)


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
    """Mittlerer Fehler auf den Fenstern ohne Heizen des Tages; ohne Fenster `None`."""
    fenster = strecken(tag, modell.heiz_art)
    if not fenster:
        return None
    return _laufen(modell.auskuehlzeit_h, modell.sonne_k_h, 0.0, fenster)


def tagesfehler_bleibt(tag: list[Stunde], heiz_art: str) -> float | None:
    """Derselbe Fehler für „Raum bleibt“: jedes Fenster behält seinen Startwert."""
    fenster = strecken(tag, heiz_art)
    if not fenster:
        return None
    abweichungen = [abs(f[0].raum - s.raum_danach) for f in fenster for s in f]
    return sum(abweichungen) / len(abweichungen)


def nachrechnen(tage: list[list[Stunde]], heiz_art: str) -> tuple[list[float], list[float]]:
    """Beide Fehlerreihen für vergangene Tage: jeder Tag gegen ein Modell aus den Tagen davor."""
    fehler: list[float] = []
    bleibt: list[float] = []
    for i in range(1, len(tage)):
        davor = tage[max(0, i - FREIGABE_TAGE) : i]
        modell = lernen([s for tag in davor for s in tag], heiz_art, len(davor))
        if modell is None:
            continue
        mit = tagesfehler(modell, tage[i])
        ohne = tagesfehler_bleibt(tage[i], heiz_art)
        if mit is not None and ohne is not None:
            fehler.append(round(mit, 3))
            bleibt.append(round(ohne, 3))
    return fehler, bleibt


def mittlerer_fehler(modell: Modell) -> float | None:
    """Mittel der gespeicherten Tagesfehler, ohne Tage `None`."""
    return sum(modell.fehler) / len(modell.fehler) if modell.fehler else None


def mittlerer_fehler_bleibt(modell: Modell) -> float | None:
    """Mittel der gespeicherten Tagesfehler von „Raum bleibt“, ohne Tage `None`."""
    return sum(modell.fehler_bleibt) / len(modell.fehler_bleibt) if modell.fehler_bleibt else None


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
        "fassung": FASSUNG,
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
    if not isinstance(roh, dict) or roh.get("fassung") != FASSUNG:
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
