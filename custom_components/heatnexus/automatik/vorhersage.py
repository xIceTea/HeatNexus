"""Vorausschau: Heizpause, Absenkung oder Programm aus dem Hausmodell.

Gewählt wird die tiefste Stufe, deren Raumverlauf bis zum Horizont nicht
unter Ziel − Spielraum fällt; der Modellfehler macht vorsichtiger.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .hausmodell import Modell, mittlerer_fehler, vorhersagen

PAUSE = "pause"
ABSENKUNG = "absenkung"
PROGRAMM = "programm"
# Mittlerer Anstieg der Heizkurve: Vorlauf-Soll je K Raumsoll.
VL_JE_K = 2.3


@dataclass(frozen=True)
class Stundeneingang:
    """Wetter und Ziel einer Stunde, auf die das Hausmodell rechnet."""

    zeit: datetime
    at: float
    sonne: float
    wind: float | None
    ziel: float


@dataclass(frozen=True)
class Vorhersage:
    """Die gewählte Stufe mit Tiefstwert, Verlauf und der Grenze, gegen die gewählt wurde."""

    stufe: str
    bis: datetime
    tiefst: float
    tiefst_zeit: datetime | None
    kurve: tuple[tuple[str, float], ...]
    ziel_min: float
    fehler: float
    rueckkehr: bool = False


def _heizen(modell: Modell, stufe: str, vl: float | None, raum: float, absenkung_k: float) -> float:
    if stufe == PAUSE:
        return 0.0
    if modell.heiz_art == "pumpe" or vl is None:
        return 1.0
    vorlauf = vl - (absenkung_k * VL_JE_K if stufe == ABSENKUNG else 0.0)
    return max(0.0, vorlauf - raum)


def _verlauf(
    modell: Modell,
    raum: float,
    vl: float | None,
    stunden: list[Stundeneingang],
    stufe: str,
    absenkung_k: float,
) -> list[float]:
    werte = []
    for s in stunden:
        heizen = _heizen(modell, stufe, vl, raum, absenkung_k)
        raum = vorhersagen(modell, raum, [(s.at, s.sonne, s.wind, heizen)])[0]
        werte.append(raum)
    return werte


def waehlen(
    modell: Modell,
    raum: float,
    vl: float | None,
    stunden: list[Stundeneingang],
    absenkung_k: float,
    spielraum_k: float,
    bis: datetime,
) -> Vorhersage:
    """Die tiefste Stufe, deren Raumverlauf bis `bis` die Grenze hält; sonst das Programm."""
    fehler = mittlerer_fehler(modell) or 0.0
    relevant = [s for s in stunden if s.zeit < bis]
    ziel = min((s.ziel for s in relevant), default=raum)
    ziel_min = ziel - spielraum_k + fehler
    # Ohne Vorlaufwert lässt sich die Absenkung nicht rechnen, sie wird dann nicht angeboten.
    mit_absenkung = modell.heiz_art == "vorlauf" and vl is not None
    stufen = (PAUSE, ABSENKUNG, PROGRAMM) if mit_absenkung else (PAUSE, PROGRAMM)
    for stufe in stufen:
        verlauf = _verlauf(modell, raum, vl, relevant, stufe, absenkung_k)
        tiefst = min(verlauf, default=raum)
        if tiefst >= ziel_min or stufe == PROGRAMM:
            zeit = relevant[verlauf.index(tiefst)].zeit if verlauf else None
            kurve = tuple(
                (s.zeit.isoformat(), round(w, 2)) for s, w in zip(relevant, verlauf, strict=True)
            )
            return Vorhersage(stufe, bis, tiefst, zeit, kurve, ziel_min, fehler)
    raise AssertionError("PROGRAMM wird immer gewählt")


def rueckkehr_noetig(
    gemessen: float, erwartet: float | None, ziel: float, spielraum_k: float, fehler: float
) -> bool:
    """Zurück, wenn der Raum unter die Grenze fällt oder weit unter der Vorhersage liegt."""
    if gemessen < ziel - spielraum_k:
        return True
    return erwartet is not None and gemessen < erwartet - 2 * max(fehler, 0.1)
