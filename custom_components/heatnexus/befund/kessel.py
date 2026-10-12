"""Befunde zum Kessel aus Zählern und Leistung; verglichen nur mit dem Kessel selbst."""

from __future__ import annotations

from datetime import date
from statistics import mean
from typing import Any

from . import form, gradtage

FENSTER = 28
SOCKEL_MIN_TAGE = 14
SOCKEL_AT = 18.0
LAUFZEIT_STUFEN = {"vorlaeufig": 7, "belastbar": 14}
ENERGIE_VORLAEUFIG = 7
ENERGIE_BELASTBAR = 30
WOCHE = 7
PUNKT_ABSTAND = 3
MIN_PUNKTE = 3
# Mehr Zuwachs an einem Tag ist kein Betrieb, sondern ein Sprung im Zähler.
MAX_JE_TAG = {"starts": 100.0, "bh": 24.0}


def _deltas(tage: list[dict[str, Any]], feld: str) -> list[float | None]:
    """Tageszuwachs eines Zählers; Rücksprung oder unmöglicher Zuwachs zählt als Lücke."""
    werte: list[float | None] = []
    vorher = None
    for t in tage:
        jetzt = t.get(feld)
        delta = None if jetzt is None or vorher is None else jetzt - vorher
        werte.append(delta if delta is not None and 0 <= delta <= MAX_JE_TAG[feld] else None)
        vorher = jetzt if jetzt is not None else vorher
    return werte


def laufzeit(tage: list[dict[str, Any]], zaehler: tuple[float, float] | None) -> form.Befund:
    """Laufzeit je Start und Starts je Tag über die letzten Heiztage; dazu der Gesamtstand."""
    if not tage and zaehler is None:
        return form.fehlt("laufzeit", "kessel")
    paare = list(zip(tage, _deltas(tage, "starts"), _deltas(tage, "bh"), strict=True))
    fenster = [p for p in paare if p[0].get("heiztag") and None not in p[1:]][-FENSTER:]
    starts = sum(p[1] for p in fenster)
    stunden = sum(p[2] for p in fenster)
    angaben = {
        "starts": starts,
        "stunden": stunden,
        "starts_tag": round(starts / len(fenster), 2) if fenster else None,
        "zaehler": list(zaehler) if zaehler else None,
        "gesamt_h_je_start": round(zaehler[1] / zaehler[0], 2) if zaehler and zaehler[0] else None,
        "je_tag": [[t["datum"], b, bool(t.get("heiztag"))] for t, _, b in paare],
    }
    if not starts:
        return form.Befund("laufzeit", form.SAMMELT, angaben=angaben)
    stufe = form.stufe(len(fenster), **LAUFZEIT_STUFEN)
    return form.Befund(
        "laufzeit", form.UNAUFFAELLIG, round(stunden / starts, 1), "h", stufe, angaben
    )


def _wochenpunkte(tage: list[dict[str, Any]]) -> list[list[float]]:
    """Gleitende 7-Tage-Mittel von Außentemperatur und Wärme, jeden dritten Tag ein Punkt.

    Ein Fenster mit fehlenden Tagen fällt weg; es mischte sonst verschiedene Witterungen.
    """
    punkte = []
    for i in range(WOCHE - 1, len(tage), PUNKT_ABSTAND):
        woche = tage[i - WOCHE + 1 : i + 1]
        spanne = date.fromisoformat(woche[-1]["datum"]) - date.fromisoformat(woche[0]["datum"])
        if spanne.days != WOCHE - 1:
            continue
        at = round(mean(t["at"] for t in woche), 1)
        punkte.append([at, round(mean(t["kwh"] for t in woche), 1)])
    return punkte


def _gerade(punkte: list[list[float]], heizgrenze: float | None) -> float | None:
    """Mehr Wärme je Kelvin kälter, über die Wochenpunkte unter der Heizgrenze."""
    unten = [p for p in punkte if heizgrenze is None or p[0] < heizgrenze]
    if len(unten) < MIN_PUNKTE:
        return None
    mx, my = mean(p[0] for p in unten), mean(p[1] for p in unten)
    nenner = sum((p[0] - mx) ** 2 for p in unten)
    if not nenner:
        return None
    return round(-sum((p[0] - mx) * (p[1] - my) for p in unten) / nenner, 1)


def energie(tage: list[dict[str, Any]], grenze: float, heizgrenze: float | None) -> form.Befund:
    """(Wärme − Sockel) je Gradtag nach VDI 3807 über die letzten 28 Tage mit Gradtag."""
    mit_kwh = [t for t in tage if t.get("kwh") is not None and t.get("at") is not None]
    if not mit_kwh:
        return form.fehlt("energie", "energie")
    sommer = [t["kwh"] for t in mit_kwh if not t.get("heiztag") and t["at"] >= SOCKEL_AT]
    punkte = _wochenpunkte(mit_kwh)
    angaben: dict[str, Any] = {"punkte": punkte, "gerade": _gerade(punkte, heizgrenze)}
    angaben["sockel"] = None
    if len(sommer) < SOCKEL_MIN_TAGE:
        return form.Befund("energie", form.SAMMELT, angaben=angaben)
    sockel = mean(sommer)
    fenster = [t for t in mit_kwh if gradtage.gradtag(t["at"], grenze) > 0][-FENSTER:]
    gt = sum(gradtage.gradtag(t["at"], grenze) for t in fenster)
    heiztage = [t for t in mit_kwh if t.get("heiztag")]
    angaben |= {
        "sockel": round(sockel, 1),
        "gradtage": round(gt, 1),
        "heiztage": len(heiztage),
        "ohne_gradtag": sum(gradtage.gradtag(t["at"], grenze) == 0 for t in heiztage[-FENSTER:]),
    }
    if not gt:
        return form.Befund("energie", form.SAMMELT, angaben=angaben)
    wert = round((sum(t["kwh"] for t in fenster) - sockel * len(fenster)) / gt, 1)
    stufe = form.stufe(len(heiztage), ENERGIE_VORLAEUFIG, ENERGIE_BELASTBAR)
    return form.Befund("energie", form.UNAUFFAELLIG, wert, "kWh", stufe, angaben)
