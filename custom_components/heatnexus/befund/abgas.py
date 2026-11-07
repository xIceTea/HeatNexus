"""Abgaswächter: Abgasüberhöhung gegen den Bezug nach der Reinigung, Mehrverlust nach Siegert."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from . import form

MODULATION = 8
MIN_LAUF = timedelta(minutes=15)
# Der LogWIN moduliert erst nach mindestens 30 Minuten Anheizvorgang (Bedienungsanleitung).
MIN_LAUF_LOGWIN = timedelta(minutes=30)
MIN_LEISTUNG = 30.0
MAX_SPRUNG = 10.0
LOGWIN_STUFE = "m"
BEZUG_TAGE = 14
VERGLEICH_TAGE = 7
MIN_MESSUNGEN = 12
LOGWIN_BELASTBAR = 36
GRENZE_K = 20.0
LUFT_GESCHAETZT = 20.0
# Ein Fühler im Heizraum zählt nur mit plausiblen Werten; sonst gilt die Schätzung.
LUFT_MIN, LUFT_MAX = -10.0, 45.0
FELDER = 7
# Eine nachgerechnete Stunde zählt wie die zwölf Takte, die sie live gewesen wäre.
TAKTE_JE_STUNDE = 12
# Siegert `qA = (tA − tL)·(A2/(21 − O2) + B)`, Formel wie in der 1. BImSchV. Die Holzwerte stammen
# aus einer Verbrennungsrechnung je Wassergehalt, die die amtlichen Öl- und Gaswerte nachbildet.
KONSTANTEN: dict[str, tuple[float, float]] = {
    "pellets": (0.68, 0.0085),
    "scheitholz": (0.69, 0.0104),
    "hackgut_trocken": (0.70, 0.0115),
    "hackgut": (0.71, 0.0126),
    "hackgut_feucht": (0.73, 0.0156),
}
# Aktueller Brennstoff der PuroWIN (`38/127`).
PUROWIN_BRENNSTOFF = {1: "hackgut_feucht", 2: "pellets", 4: "hackgut_feucht", 5: "hackgut_trocken"}


@dataclass(frozen=True)
class Messung:
    """Ein Takt am Kessel; fehlende Werte sind `None`."""

    abgas: float | None
    kessel: float | None
    leistung: float | None
    phase: float | None
    o2: float | None


def stufe(leistung: float) -> str:
    """Leistungsstufe in Schritten von 20 Prozentpunkten ab 30 %."""
    for grenze in (90, 70, 50):
        if leistung >= grenze:
            return str(grenze)
    return "30"


def bewerten(
    zustand: dict[str, Any], messung: Messung, zeit: datetime, logwin: bool
) -> tuple[dict[str, Any], str | None]:
    """Ob ein Takt im ruhigen Betrieb liegt; liefert den neuen Laufzustand und die Stufe."""
    if messung.phase != MODULATION:
        return {}, None
    seit = zustand.get("seit") or zeit
    neu = {"seit": seit, "leistung": messung.leistung}
    if messung.abgas is None or messung.kessel is None:
        return neu, None
    if zeit - seit < (MIN_LAUF_LOGWIN if logwin else MIN_LAUF):
        return neu, None
    if logwin:
        return neu, LOGWIN_STUFE
    vorher, leistung = zustand.get("leistung"), messung.leistung
    if leistung is None or leistung < MIN_LEISTUNG or vorher is None:
        return neu, None
    return neu, stufe(leistung) if abs(leistung - vorher) <= MAX_SPRUNG else None


def sammeln(
    tage: dict[str, dict[str, list[float]]],
    tag: str,
    stufe_: str,
    dt: float,
    o2: float | None,
    ta: float,
    tl: float | None = None,
    anzahl: int = 1,
) -> dict[str, dict[str, list[float]]]:
    """Messungen in die Tagessummen `[Σ dT, n, Σ O2, n O2, Σ Abgas, Σ Raumluft, n Raumluft]`."""
    s_dt, n, s_o2, n_o2, s_ta, s_tl, n_tl = _voll(tage.get(tag, {}).get(stufe_))
    mit_o2 = o2 is not None
    mit_tl = tl is not None and LUFT_MIN <= tl <= LUFT_MAX
    summe = [
        round(s_dt + dt * anzahl, 2),
        n + anzahl,
        round(s_o2 + (o2 * anzahl if mit_o2 and o2 is not None else 0.0), 2),
        n_o2 + anzahl * int(mit_o2),
        round(s_ta + ta * anzahl, 2),
        round(s_tl + (tl * anzahl if mit_tl and tl is not None else 0.0), 2),
        n_tl + anzahl * int(mit_tl),
    ]
    return {**tage, tag: {**tage.get(tag, {}), stufe_: summe}}


def stunde_aus_statistik(
    leistung: dict[str, Any], abgas: dict[str, Any], kessel: dict[str, Any], o2: dict[str, Any]
) -> tuple[str, float, float | None, float] | None:
    """Stufe, `dT`, O2 und Abgas einer Stunde; sie gilt nur, wenn der Kessel durchgehend ruhig moduliert.

    Das Minimum der Leistung zeigt, dass der Brenner die ganze Stunde lief; die Spanne, dass er ruhig lief.
    """
    unten, oben, mittel = leistung.get("min"), leistung.get("max"), leistung.get("mean")
    ta, tk = abgas.get("mean"), kessel.get("mean")
    if None in (unten, oben, mittel, ta, tk) or unten < MIN_LEISTUNG or oben - unten > MAX_SPRUNG:
        return None
    return stufe(mittel), round(ta - tk, 2), o2.get("mean"), ta


def _voll(werte: list[float] | None) -> list[float]:
    """Summen auf sieben Felder; ältere Tage haben noch keine Raumluft."""
    werte = list(werte or [])[:FELDER]
    return werte + [0.0] * (FELDER - len(werte))


def brennstoff(fct_type: int | None, code: float | None) -> str:
    """Brennstoff für die Siegert-Konstanten aus Funktionstyp und, bei der PuroWIN, `38/127`."""
    if fct_type == 10:
        return "scheitholz"
    if fct_type == 25:
        return PUROWIN_BRENNSTOFF.get(int(code), "hackgut") if code is not None else "hackgut"
    return "pellets"


def konstanten(art: str) -> tuple[float, float]:
    """A2 und B für einen Brennstoff; unbekannt zählt als Pellets."""
    return KONSTANTEN.get(art, KONSTANTEN["pellets"])


def abgasverlust(
    ta: float | None, tl: float | None, o2: float | None, k: tuple[float, float]
) -> float | None:
    """Abgasverlust in Prozent nach Siegert; ohne O2 oder mit Luftsauerstoff keiner."""
    if ta is None or tl is None or o2 is None or o2 >= 20:
        return None
    return round((ta - tl) * (k[0] / (21 - o2) + k[1]), 2)


def _summen(tage: dict[str, dict[str, list[float]]], auswahl: list[str]) -> dict[str, list[float]]:
    summen: dict[str, list[float]] = {}
    for tag in auswahl:
        for stufe_, werte in tage[tag].items():
            alt = summen.get(stufe_, [0.0] * FELDER)
            summen[stufe_] = [a + b for a, b in zip(alt, _voll(werte), strict=True)]
    return summen


def _zeitraeume(
    tage: dict[str, dict[str, list[float]]], bezug_ab: str | None, heute: date
) -> tuple[list[str], list[str], str | None]:
    grenze = (heute - timedelta(days=VERGLEICH_TAGE)).isoformat()
    mit_daten = sorted(d for d, v in tage.items() if v)
    ab = bezug_ab or (mit_daten[0] if mit_daten else None)
    bezug = [d for d in mit_daten if ab and ab <= d < grenze][:BEZUG_TAGE]
    jetzt = [d for d in mit_daten if grenze <= d <= heute.isoformat()]
    return bezug, jetzt, (bezug[0] if bezug else ab)


def _verlaeufe(tage: dict[str, dict[str, list[float]]], stufen: list[str]) -> list[list[Any]]:
    """`dT` je Tag in der häufigsten gemeinsamen Stufe, für das Bild der Karte."""
    if not stufen:
        return []
    haeufig = max(stufen, key=lambda s: sum(v.get(s, [0, 0])[1] for v in tage.values()))
    return [
        [d, round(v[haeufig][0] / v[haeufig][1], 1)]
        for d, v in sorted(tage.items())
        if v.get(haeufig) and v[haeufig][1]
    ]


def _gewichtet(paare: list[tuple[float, float]]) -> float:
    gewicht = sum(g for _, g in paare)
    return round(sum(w * g for w, g in paare) / gewicht, 2)


def _raumluft(summe: list[float]) -> float | None:
    """Mittlere Raumluft, wenn der Fühler mindestens die Hälfte der Messungen lieferte."""
    return summe[5] / summe[6] if summe[6] and summe[6] * 2 >= summe[1] else None


def _verlust(
    b: dict[str, list[float]], v: dict[str, list[float]], stufen: list[str], k: tuple[float, float]
) -> form.Befund:
    paare, absolut, gemessen = [], [], True
    for s in stufen:
        if not (b[s][3] and v[s][3]):
            continue
        # Gemessen zählt nur in beiden Zeiträumen; gemischt entstünde ein Unterschied aus dem Fühler.
        tl_b, tl_v = _raumluft(b[s]), _raumluft(v[s])
        if tl_b is None or tl_v is None:
            tl_b = tl_v = LUFT_GESCHAETZT
            gemessen = False
        q_b = abgasverlust(b[s][4] / b[s][1], tl_b, b[s][2] / b[s][3], k)
        q_v = abgasverlust(v[s][4] / v[s][1], tl_v, v[s][2] / v[s][3], k)
        if q_b is not None and q_v is not None:
            paare.append((q_v - q_b, v[s][1]))
            absolut.append((q_v, v[s][1]))
    if not paare:
        return form.fehlt("abgasverlust", "o2")
    angaben = {"verlust_jetzt": _gewichtet(absolut), "luft_geschaetzt": not gemessen}
    stufe_ = form.BELASTBAR if len(paare) >= 2 else form.VORLAEUFIG
    return form.Befund("abgasverlust", form.UNAUFFAELLIG, _gewichtet(paare), "%", stufe_, angaben)


def vergleich(
    tage: dict[str, dict[str, list[float]]],
    bezug_ab: str | None,
    heute: date,
    logwin: bool,
    brennstoff_: str,
    nachgerechnet_bis: str | None = None,
) -> tuple[form.Befund, form.Befund]:
    """Anstieg von `dT` der letzten 7 Tage gegen die ersten 14 Tage nach der Reinigung, je Stufe."""
    bezug, jetzt, bezug_seit = _zeitraeume(tage, bezug_ab, heute)
    b, v = _summen(tage, bezug), _summen(tage, jetzt)
    stufen = sorted(s for s in b if s in v and min(b[s][1], v[s][1]) >= MIN_MESSUNGEN)
    angaben: dict[str, Any] = {
        "bezug_seit": bezug_seit,
        "ohne_reinigungsdatum": bezug_ab is None,
        "je_tag": _verlaeufe(tage, stufen),
        "nachgerechnet": bool(nachgerechnet_bis and bezug and bezug[0] <= nachgerechnet_bis),
    }
    if not stufen:
        sammelt = form.Befund("abgas", form.SAMMELT, angaben=angaben)
        return sammelt, form.Befund("abgasverlust", form.SAMMELT)
    paare = [(v[s][0] / v[s][1] - b[s][0] / b[s][1], v[s][1]) for s in stufen]
    anstieg = _gewichtet(paare)
    angaben["stufen"] = {
        s: [round(b[s][0] / b[s][1], 1), round(v[s][0] / v[s][1], 1)] for s in stufen
    }
    viele = logwin and all(min(b[s][1], v[s][1]) >= LOGWIN_BELASTBAR for s in stufen)
    stufe_ = form.BELASTBAR if len(stufen) >= 2 or viele else form.VORLAEUFIG
    status = form.status_aus(stufe_, anstieg >= GRENZE_K)
    dt = form.Befund("abgas", status, anstieg, "K", stufe_, angaben)
    return dt, _verlust(b, v, stufen, konstanten(brennstoff_))
