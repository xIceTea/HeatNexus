"""Befunde zum Haus: ab welcher Außentemperatur geheizt wird und wie lange es Wärme hält."""

from __future__ import annotations

from itertools import pairwise
import math
from typing import Any

from . import form, gradtage

HEIZTAG_STUNDEN = 2
MIN_SEITE = 5
BEREICH = (10, 22)
NACHT_H = 8
# Freigabe des Hausmodells: Fehler höchstens 0,5 K und höchstens 0,8 × „Raum bleibt“.
FREIGABE_K = 0.5
FREIGABE_ANTEIL = 0.8


def heiztag(tag: dict[str, Any]) -> bool:
    """Ein Tag, an dem der Heizkreis mindestens zwei Stunden ein Vorlauf-Soll hatte."""
    return (tag.get("heizh") or 0) >= HEIZTAG_STUNDEN


def _klassen(tage: list[dict[str, Any]]) -> dict[int, list[int]]:
    """Je 1-K-Klasse des Tagesmittels: Zahl der Tage und der Heiztage."""
    klassen: dict[int, list[int]] = {}
    for t in tage:
        if t.get("at") is None:
            continue
        eintrag = klassen.setdefault(math.floor(t["at"]), [0, 0])
        eintrag[0] += 1
        eintrag[1] += heiztag(t)
    return klassen


def _uebergang(klassen: dict[int, list[int]]) -> float | None:
    """Die höchste Stelle, an der der Anteil der Heiztage von ≥ 50 % unter 50 % fällt."""
    anteile = sorted((k, h / n) for k, (n, h) in klassen.items() if n)
    treffer = None
    for (k1, a1), (k2, a2) in pairwise(anteile):
        if a1 >= 0.5 > a2:
            treffer = (k1 + 0.5) + (a1 - 0.5) / (a1 - a2) * (k2 - k1)
    return treffer


def heizgrenze(tage: list[dict[str, Any]]) -> form.Befund:
    """Die Außentemperatur, an der Heiztage und heizfreie Tage kippen; mit Klassen fürs Bild."""
    klassen = _klassen(tage)
    gemessen = [t for t in tage if t.get("at") is not None]
    im_bereich = [t for t in gemessen if BEREICH[0] <= t["at"] < BEREICH[1]]
    heiz = sum(heiztag(t) for t in im_bereich)
    angaben = {
        "klassen": [[k, n, h] for k, (n, h) in sorted(klassen.items())],
        "tage": len(gemessen),
        "heiztage": sum(heiztag(t) for t in gemessen),
    }
    grenze = _uebergang(klassen)
    if heiz < MIN_SEITE or len(im_bereich) - heiz < MIN_SEITE or grenze is None:
        return form.Befund("heizgrenze", form.SAMMELT, angaben=angaben)
    return form.Befund(
        "heizgrenze", form.UNAUFFAELLIG, round(grenze, 1), "°C", form.BELASTBAR, angaben
    )


def heizstunden_je_gradtag(tage: list[dict[str, Any]], grenze: float) -> float | None:
    """Heizstunden je Kelvin-Tag über die Tage mit Gradtag; ohne Gradtag `None`."""
    mit = [(t, gradtage.gradtag(t["at"], grenze)) for t in tage if t.get("at") is not None]
    mit = [(t, g) for t, g in mit if g > 0]
    summe = sum(g for _, g in mit)
    return sum(t.get("heizh") or 0 for t, _ in mit) / summe if summe else None


def nacht(tau: float, raum: float | None, aussen: float | None) -> dict[str, Any] | None:
    """Raum nach acht Stunden ohne Heizung: T(t) = Ta + (Ti − Ta)·e^(−t/τ)."""
    if raum is None or aussen is None or not tau:
        return None
    nach = aussen + (raum - aussen) * math.exp(-NACHT_H / tau)
    return {"von": raum, "nach": round(nach, 1), "aussen": aussen, "stunden": NACHT_H}


def waermespeicher(
    modell: dict[str, Any] | None, raum: float | None, aussen: float | None
) -> form.Befund:
    """τ aus dem Hausmodell der Automatik, dazu die Nacht ohne Heizung."""
    if not modell:
        return form.fehlt("waermespeicher", "raeume")
    tau = modell.get("auskuehlzeit_h")
    if not tau:
        return form.Befund("waermespeicher", form.SAMMELT, angaben={"grund": modell.get("grund")})
    bleibt = modell.get("fehler_bleibt")
    sonne = modell.get("sonne_k_h") or 0
    angaben = {
        "raum": raum,
        "nacht": nacht(tau, raum, aussen),
        "sonne": sonne if sonne > 0 else None,
        "fehler": modell.get("fehler"),
        "ziel": round(min(FREIGABE_K, FREIGABE_ANTEIL * bleibt), 2) if bleibt else FREIGABE_K,
        "vergleiche": modell.get("vergleiche", 0),
        "tage": modell.get("tage", 0),
    }
    stufe = form.BELASTBAR if modell.get("status") == "aktiv" else form.VORLAEUFIG
    return form.Befund("waermespeicher", form.UNAUFFAELLIG, float(tau), "h", stufe, angaben)
