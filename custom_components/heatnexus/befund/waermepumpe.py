"""Gütegrad einer Wärmepumpe gegen ihren eigenen Bezug: Arbeitszahl bezogen auf die Carnot-Zahl.

Die Arbeitszahl hängt vor allem vom Hub zwischen Luft und Vorlauf ab. Der Gütegrad
`η = Q / Σ(W · COP_Carnot)` rechnet ihn heraus; was bleibt, ist der Zustand der Maschine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import pairwise
import math
from typing import Any

from . import form

FUNKTIONSTYPEN = (7, 27)
NULLPUNKT_K = 273.15
# Unter diesem Hub wächst die Carnot-Zahl über alle Grenzen; solche Tage sagen nichts.
MIN_HUB_K = 10.0
MIN_STUNDEN = 4.0
# Eine Stunde Takt mit laufendem Verdichter im Heizbetrieb.
MIN_PROBEN = 12
# Feldwerte von Luft-Wasser-Wärmepumpen liegen bei 0,4 bis 0,6; außerhalb misst ein Fühler falsch.
GUETE_MIN, GUETE_MAX = 0.15, 0.8
COP_MIN, COP_MAX = 1.0, 8.0
BAND_K = 5
BAND_MIN, BAND_MAX = -20, 15
VERGLEICH_TAGE = 28
BEZUG_JE_BAND = 10
MIN_BEZUG, MIN_JETZT = 5, 3
GRENZE_PROZENT = -10.0
RUECKSETZ_KWH, RUECKSETZ_H = 0.05, 0.05
VERLAUF_TAGE = 120
# Heizen und Silentmode Heizen (`50/6`) bzw. Heizen (`50/70`); Abtauen und Warmwasser zählen nicht.
PHASEN_HEIZEN = {7: frozenset({4, 7}), 27: frozenset({4})}
FAKTOR_KWH = {"wh": 0.001, "kwh": 1.0, "mwh": 1000.0}


@dataclass(frozen=True)
class Probe:
    """Ein Takt: Temperaturen, Leistung, Phase und die Zählerstände der Wärmepumpe."""

    vorlauf: float | None
    luft: float | None
    leistung: float | None
    phase: float | None
    ww: float | None = None
    eheizung: float | None = None


@dataclass(frozen=True)
class Tag:
    """Ein gültiger Tag: Wärme und Strom in kWh, Carnot-Zahl und Lufttemperatur im Betrieb."""

    waerme: float
    strom: float
    carnot: float
    luft: float

    @property
    def guete(self) -> float:
        return self.waerme / (self.strom * self.carnot)


def faktor(einheit: str | None) -> float:
    """Umrechnung einer Zählereinheit in kWh; ohne Einheit gilt kWh."""
    return FAKTOR_KWH.get((einheit or "kwh").strip().lower(), 1.0)


def carnot(vorlauf: float, luft: float) -> float | None:
    """Carnot-Leistungszahl `T_VL / (T_VL − T_Luft)` in Kelvin; ohne ausreichenden Hub `None`."""
    hub = vorlauf - luft
    return (vorlauf + NULLPUNKT_K) / hub if hub >= MIN_HUB_K else None


def band(luft: float) -> str | None:
    """Untergrenze des 5-K-Bands der Lufttemperatur, von −20 bis unter 15 °C."""
    unten = math.floor(luft / BAND_K) * BAND_K
    return str(unten) if BAND_MIN <= unten < BAND_MAX else None


def zaehlt(fct_type: int, probe: Probe, ww_vorher: float | None) -> bool:
    """Ob ein Takt in die Temperaturmittel geht: Verdichter läuft, Heizbetrieb, kein Warmwasser."""
    if probe.vorlauf is None or probe.luft is None or not (probe.leistung or 0) > 0:
        return False
    if probe.phase is None or int(probe.phase) not in PHASEN_HEIZEN.get(fct_type, frozenset()):
        return False
    return not (probe.ww is not None and ww_vorher is not None and probe.ww > ww_vorher)


def _zieltag(tage: dict[str, dict[str, Any]], zeit: datetime, q: float, bh: float | None) -> str:
    """Der Tag eines Tageszählers; kurz nach Mitternacht gehört ein noch nicht zurückgesetzter zum Vortag."""
    tag = zeit.date().isoformat()
    vortag = (zeit.date() - timedelta(days=1)).isoformat()
    alt = tage.get(vortag) or {}
    if zeit.hour != 0 or alt.get("q") is None or q < alt["q"] - RUECKSETZ_KWH:
        return tag
    return vortag if bh is None or alt.get("bh") is None or bh >= alt["bh"] - RUECKSETZ_H else tag


def sammeln(
    tage: dict[str, dict[str, Any]],
    zeit: datetime,
    fct_type: int,
    probe: Probe,
    gezaehlt: bool,
    zaehler: dict[str, float | None],
) -> dict[str, dict[str, Any]]:
    """Einen Takt in die Tagessummen schreiben; liefert eine neue Fassung der Tage."""
    neu = {t: dict(v) for t, v in tage.items()}
    tag = zeit.date().isoformat()
    eintrag = neu.setdefault(tag, {"n": 0, "vl": 0.0, "luft": 0.0})
    if gezaehlt and probe.vorlauf is not None and probe.luft is not None:
        eintrag["n"] += 1
        eintrag["vl"] = round(eintrag["vl"] + probe.vorlauf, 2)
        eintrag["luft"] = round(eintrag["luft"] + probe.luft, 2)
    if (probe.eheizung or 0) > 0:
        eintrag["eheiz"] = True
    if fct_type == 7:
        _tageszaehler(neu, zeit, zaehler)
    else:
        eintrag |= {k: v for k, v in zaehler.items() if v is not None}
    return neu


def _tageszaehler(
    tage: dict[str, dict[str, Any]], zeit: datetime, zaehler: dict[str, float | None]
) -> None:
    """`52/60` und `52/51` zählen den Tag; es gilt der höchste Stand mit dem COP von dann."""
    q, bh = zaehler.get("q"), zaehler.get("bh")
    if q is None:
        return
    tag = _zieltag(tage, zeit, q, bh)
    ziel = tage.setdefault(tag, {"n": 0, "vl": 0.0, "luft": 0.0})
    neu = {"q": q, "cop": zaehler.get("cop"), "bh": bh}
    if ziel.get("q") is None or q >= ziel["q"]:
        ziel |= neu
    elif _zurueckgesetzt(ziel, q, bh):
        # Spät zurückgesetzt: der Stand davor gehörte noch zum Vortag.
        vortag = tage.setdefault(_vortag(tag), {"n": 0, "vl": 0.0, "luft": 0.0})
        if vortag.get("q") is None or ziel["q"] > vortag["q"]:
            vortag |= {k: ziel.get(k) for k in neu}
        ziel |= neu


def _vortag(tag: str) -> str:
    return (date.fromisoformat(tag) - timedelta(days=1)).isoformat()


def _zurueckgesetzt(ziel: dict[str, Any], q: float, bh: float | None) -> bool:
    """Wärme und Stunden fallen zusammen; ein einzelner niedriger Wert bleibt ein Ausreißer."""
    alt_bh = ziel.get("bh")
    return (
        q < ziel["q"] - RUECKSETZ_KWH
        and bh is not None
        and alt_bh is not None
        and bh < alt_bh - RUECKSETZ_H
    )


def _mittel(eintrag: dict[str, Any]) -> tuple[float, float] | None:
    n = eintrag.get("n") or 0
    if n < MIN_PROBEN:
        return None
    return eintrag["vl"] / n, eintrag["luft"] / n


def _tag(waerme: float, strom: float, eintrag: dict[str, Any]) -> Tag | None:
    mittel = _mittel(eintrag)
    if mittel is None or strom <= 0 or eintrag.get("eheiz"):
        return None
    zahl, c = waerme / strom, carnot(*mittel)
    if c is None or not COP_MIN <= zahl <= COP_MAX or not GUETE_MIN <= zahl / c <= GUETE_MAX:
        return None
    return Tag(waerme, strom, c, mittel[1])


def tagewerte(tage: dict[str, dict[str, Any]], fct_type: int) -> dict[str, Tag]:
    """Die gültigen Tage; fctType 7 aus den Tageszählern, fctType 27 aus Zuwächsen der Gesamtzähler."""
    gueltig: dict[str, Tag] = {}
    if fct_type == 7:
        for t, e in tage.items():
            q, cop, bh = e.get("q"), e.get("cop"), e.get("bh")
            if q and cop and (bh or 0) >= MIN_STUNDEN and (tag := _tag(q, q / cop, e)):
                gueltig[t] = tag
        return gueltig
    reihe = sorted(tage.items())
    for (ta, a), (tb, b) in pairwise(reihe):
        if (date.fromisoformat(tb) - date.fromisoformat(ta)).days != 1:
            continue
        d = {k: b[k] - a[k] for k in ("wz", "sz", "bhz") if k in a and k in b}
        if len(d) < 3 or d["bhz"] < MIN_STUNDEN or (b.get("kz") or 0) > (a.get("kz") or 0):
            continue
        if tag := _tag(d["wz"], d["sz"], b):
            gueltig[tb] = tag
    return gueltig


def _guete(tage: list[Tag]) -> float:
    """Energiegewichtet: die erzeugte Wärme gegen die, die eine Carnot-Maschine mit demselben Strom gäbe."""
    return sum(t.waerme for t in tage) / sum(t.strom * t.carnot for t in tage)


def _je_band(tage: dict[str, Tag], auswahl: list[str], je_band: int | None) -> dict[str, list[Tag]]:
    gruppen: dict[str, list[Tag]] = {}
    for t in auswahl:
        if (b := band(tage[t].luft)) is not None and len(gruppen.get(b, [])) < (je_band or 10**6):
            gruppen.setdefault(b, []).append(tage[t])
    return gruppen


def _gewichtet(paare: list[tuple[float, int]]) -> float:
    return round(sum(w * n for w, n in paare) / sum(n for _, n in paare), 1)


def vergleich(
    tage: dict[str, Tag], bezug_ab: str | None, heute: date, inkl_warmwasser: bool = False
) -> form.Befund:
    """Änderung des Gütegrads der letzten 28 Tage gegen den Bezug nach der Reinigung, je Luftband."""
    grenze, heute_s = (heute - timedelta(days=VERGLEICH_TAGE)).isoformat(), heute.isoformat()
    sortiert = sorted(tage)
    ab = bezug_ab or (sortiert[0] if sortiert else None)
    bezug = _je_band(tage, [t for t in sortiert if ab and ab <= t < grenze], BEZUG_JE_BAND)
    jetzt = _je_band(tage, [t for t in sortiert if grenze <= t < heute_s], None)
    zuletzt = [t for t in sortiert if t < heute_s][-VERLAUF_TAGE:]
    angaben: dict[str, Any] = {
        "bezug_seit": next((t for t in sortiert if ab and t >= ab), ab),
        "ohne_reinigungsdatum": bezug_ab is None,
        "inkl_warmwasser": inkl_warmwasser,
        "je_tag": [[t, round(tage[t].guete, 3)] for t in zuletzt],
    }
    baender = sorted(
        (b for b in bezug if len(bezug[b]) >= MIN_BEZUG and len(jetzt.get(b, [])) >= MIN_JETZT),
        key=int,
    )
    if not baender:
        return form.Befund("arbeitszahl", form.SAMMELT, angaben=angaben)
    paare, angaben["baender"] = [], {}
    for b in baender:
        g_b, g_j = _guete(bezug[b]), _guete(jetzt[b])
        aenderung = (g_j / g_b - 1) * 100
        paare.append((aenderung, len(jetzt[b])))
        angaben["baender"][b] = [round(g_b, 3), round(g_j, 3), len(bezug[b]), len(jetzt[b])]
    alle = [t for b in baender for t in jetzt[b]]
    angaben["guete_jetzt"] = round(_guete(alle), 3)
    angaben["arbeitszahl_jetzt"] = round(
        sum(t.waerme for t in alle) / sum(t.strom for t in alle), 2
    )
    wert = _gewichtet(paare)
    stufe_ = form.BELASTBAR if len(baender) >= 2 else form.VORLAEUFIG
    status = form.status_aus(stufe_, wert <= GRENZE_PROZENT)
    return form.Befund("arbeitszahl", status, wert, "%", stufe_, angaben)
