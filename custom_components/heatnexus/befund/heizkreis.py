"""Befunde zum Heizkreis aus Stundenwerten: Räume am Ziel, Nächte, Vorlauf gegen Soll."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean
from typing import Any

from . import form
from .haus import heiztag

ERHOLUNG_H = 2
BAND_FROST = 0.0
BAND_KUEHL = 5.0
HINWEIS_ANTEIL = 15
NACHT_BAND = (5.0, 15.0)
NACHT_HINWEIS_K = 1.0
MITTAG = 12
VORLAUF_HINWEIS = 10.0
FOLGE_STUNDEN = 3
FOLGE_TAGE = 3
STUFEN = {"vorlaeufig": 4, "belastbar": 7}
KLASSEN = ("unter", "am", "leicht", "ueber")
FORMAT = "%Y-%m-%d %H"


def _plus(zeit: str, stunden: int) -> str:
    return (datetime.strptime(zeit, FORMAT) + timedelta(hours=stunden)).strftime(FORMAT)


def saubere(stunden: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Heizstunden ohne Eingriff und ohne die zwei Stunden danach."""
    gestoert = {s["zeit"] for s in stunden if s.get("eingriff")}
    folgen = {_plus(z, n) for z in gestoert for n in range(ERHOLUNG_H + 1)}
    return [s for s in stunden if (s.get("vl") or 0) > 0 and s["zeit"] not in folgen]


def _band(at: float | None, grenze: float | None) -> str | None:
    if at is None or (grenze is not None and at >= grenze):
        return None
    if at < BAND_FROST:
        return "frost"
    return "kuehl" if at < BAND_KUEHL else "uebergang"


def _klasse(ist: float, ziel: float) -> str:
    d = ist - ziel
    if d < -0.5:
        return "unter"
    if d <= 0.5:
        return "am"
    return "leicht" if d <= 1.0 else "ueber"


def _je_raum(stunden: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Je Raum die Zahl der Stunden und die Anteile je Klasse in ganzen Prozent."""
    zaehler: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for s in stunden:
        for raum, (ist, ziel) in (s.get("raeume") or {}).items():
            ziel = ziel if ziel is not None else s.get("soll")
            if ist is not None and ziel is not None:
                zaehler[raum][_klasse(ist, ziel)] += 1
    ergebnis = {}
    for raum, z in zaehler.items():
        n = sum(z.values())
        ergebnis[raum] = {"stunden": n} | {k: round(100 * z[k] / n) for k in KLASSEN}
    return ergebnis


def raeume(stunden: list[dict[str, Any]], grenze: float | None) -> list[form.Befund]:
    """Je Band die Anteile je Raum; gezeigt wird das Band mit den meisten Tagen."""
    gut = [s for s in saubere(stunden) if s.get("raeume")]
    if not gut:
        return [form.fehlt("raeume", "raeume")]
    je_band: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in gut:
        if (band := _band(s.get("at"), grenze)) is not None:
            je_band[band].append(s)
    tage = {b: len({s["zeit"][:10] for s in liste}) for b, liste in je_band.items()}
    if not tage:
        return [form.Befund("raeume", form.SAMMELT)]
    band = max(tage, key=lambda b: tage[b])
    je_raum = _je_raum(je_band[band])
    auffaellig = any(
        w["unter"] >= HINWEIS_ANTEIL or w["ueber"] >= HINWEIS_ANTEIL for w in je_raum.values()
    )
    stufe = form.stufe(tage[band], **STUFEN)
    warm = round(mean(w["am"] + w["leicht"] + w["ueber"] for w in je_raum.values()))
    angaben = {"band": band, "baender": tage, "je_raum": je_raum, "tage": tage[band]}
    return [form.Befund("raeume", form.status_aus(stufe, auffaellig), warm, "%", stufe, angaben)]


def _nacht_wert(stunden: list[dict[str, Any]]) -> float | None:
    """Raum gegen Ziel in der letzten Stunde vor dem ersten Anstieg des Ziels nach Mitternacht."""
    vorher = None
    for s in sorted(stunden, key=lambda s: s["zeit"]):
        paare = [
            (i, z) for i, z in (s.get("raeume") or {}).values() if i is not None and z is not None
        ]
        if not paare:
            continue
        ziel = max(z for _, z in paare)
        if vorher is not None and ziel > vorher[1]:
            return vorher[0]
        vorher = (mean(i - z for i, z in paare), ziel)
    return None


def naechte(stunden: list[dict[str, Any]]) -> form.Befund:
    """Mittel über Nächte mit 5 bis 15 °C außen; Hinweis ab mehr als 1 K Abstand."""
    je_nacht: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in stunden:
        if int(s["zeit"][11:13]) < MITTAG and s.get("raeume"):
            je_nacht[s["zeit"][:10]].append(s)
    werte = []
    for datum, liste in sorted(je_nacht.items()):
        at = [s["at"] for s in liste if s.get("at") is not None]
        if not at or not NACHT_BAND[0] <= mean(at) <= NACHT_BAND[1]:
            continue
        if (wert := _nacht_wert(liste)) is not None:
            werte.append([datum, round(wert, 1)])
    if not werte:
        return form.Befund("naechte", form.SAMMELT) if je_nacht else form.fehlt("naechte", "raeume")
    mittel = round(mean(w for _, w in werte), 1)
    stufe = form.stufe(len(werte), **STUFEN)
    status = form.status_aus(stufe, abs(mittel) > NACHT_HINWEIS_K)
    return form.Befund("naechte", status, mittel, "K", stufe, {"naechte": werte})


def vorlauf(tage: list[dict[str, Any]]) -> form.Befund:
    """Anteil der Heizstunden mit Vorlauf mehr als 3 K unter Soll; Hinweis ab 10 % oder langen Folgen."""
    heiz = [t for t in tage if heiztag(t)]
    stunden = sum(t.get("heizh") or 0 for t in heiz)
    if not stunden:
        return form.Befund("vorlauf", form.SAMMELT)
    unter = sum(t.get("unter") or 0 for t in heiz)
    anteil = round(100 * unter / stunden, 1)
    lange = sum((t.get("folge") or 0) >= FOLGE_STUNDEN for t in heiz)
    stufe = form.stufe(len(heiz), **STUFEN)
    angaben = {
        "stunden": stunden,
        "unter": unter,
        "heiztage": len(heiz),
        "tage": sum((t.get("unter") or 0) > 0 for t in heiz),
        "je_tag": [[t["datum"], t.get("unter") or 0] for t in heiz],
        "folge": max((t.get("folge") or 0) for t in heiz),
    }
    status = form.status_aus(stufe, anteil >= VORLAUF_HINWEIS or lange >= FOLGE_TAGE)
    return form.Befund("vorlauf", status, anteil, "%", stufe, angaben)
