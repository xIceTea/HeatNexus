"""Pflege eines Wärmeerzeugers: Termine aus Restzählern, Stunden seit Service oder Kalender."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise
import math
from typing import Any

from . import form

ZAEHLER = "zaehler"
SEIT_SERVICE = "seit_service"
KALENDER = "kalender"
ARTEN = ("reinigung", "hauptreinigung", "wartung", "asche", "jahresreinigung")
FENSTER_TAGE = 14
VERLAUF_TAGE = 30
RUHE_H_JE_TAG = 0.5
SPRUNG_ANTEIL = 0.1
# Ab hier ist das `max` eines Datenpunkts sein Wertebereich, kein Intervall.
OHNE_MAX = 65534
BALD_TAGE = 7
STUFEN = {"vorlaeufig": 7, "belastbar": 14}


@dataclass(frozen=True)
class Pflege:
    """Eine Pflegearbeit: woran sie hängt und wie ihr Termin entsteht."""

    art: str
    weise: str
    adresse: str | None = None
    intervall_tage: int | None = None
    frist_monate: int | None = None


# Die Intervalle der Zähler hängen von Kesselgröße und Ausführung ab; sie stehen nicht im Code.
# Nach der Meldung „Wartung“ nennen die Windhager-Anleitungen drei Monate Frist.
PFLEGE: dict[int, tuple[Pflege, ...]] = {
    9: (
        Pflege("reinigung", ZAEHLER, "/20/61/0"),
        Pflege("hauptreinigung", ZAEHLER, "/20/62/0"),
        Pflege("wartung", ZAEHLER, "/20/63/0", frist_monate=3),
    ),
    25: (
        Pflege("asche", ZAEHLER, "/39/91/0"),
        Pflege("hauptreinigung", ZAEHLER, "/39/92/0"),
        Pflege("wartung", ZAEHLER, "/39/93/0", frist_monate=3),
    ),
    6: (Pflege("wartung", SEIT_SERVICE, "/60/29/0", intervall_tage=365),),
}
# Der LogWIN zählt keine Pflege; seine Anleitung nennt wöchentlich und jährlich.
LOGWIN = (
    Pflege("asche", KALENDER, intervall_tage=7),
    Pflege("jahresreinigung", KALENDER, intervall_tage=365),
)
LOGWIN_KLASSE = "2009"


def _zahl(wert: object) -> float | None:
    if isinstance(wert, int | float) and not isinstance(wert, bool):
        return float(wert)
    return None


def hoechst(max_feld: object, gesehen: float | None) -> float | None:
    """Das Intervall: das `max` des Datenpunkts, wenn es eines ist, sonst der größte gesehene Wert."""
    grenze = _zahl(max_feld)
    return grenze if grenze is not None and 0 < grenze < OHNE_MAX else gesehen


def sprung(alt: float | None, neu: float | None, hoechst_: float | None) -> bool:
    """Ein Restzähler springt nach erledigter Pflege um mehr als ein Zehntel des Intervalls."""
    if alt is None or neu is None or not hoechst_:
        return False
    return neu - alt > SPRUNG_ANTEIL * hoechst_


def zurueckgesetzt(alt: float | None, neu: float | None) -> bool:
    """Die Stunden seit Service fallen nach dem Service auf weniger als die Hälfte."""
    return alt is not None and neu is not None and alt > 0 and neu < alt / 2


def abnahme_je_tag(verlauf: dict[str, float], heute: date) -> tuple[float | None, int]:
    """Abnahme je Kalendertag über die letzten 14 Tage; Sprünge nach oben zählen nicht."""
    grenze = (heute - timedelta(days=FENSTER_TAGE)).isoformat()
    punkte = sorted((d, r) for d, r in verlauf.items() if d >= grenze and _zahl(r) is not None)
    if len(punkte) < 2:
        return None, 0
    abnahme = sum(max(0.0, a - b) for (_, a), (_, b) in pairwise(punkte))
    tage = (date.fromisoformat(punkte[-1][0]) - date.fromisoformat(punkte[0][0])).days
    return (round(abnahme / tage, 2) if tage else None), tage


def _monate(tag: date, monate: int) -> date:
    jahr, monat = divmod(tag.month - 1 + monate, 12)
    ziel = date(tag.year + jahr, monat + 1, 1)
    folgemonat = date(ziel.year + ziel.month // 12, ziel.month % 12 + 1, 1)
    return ziel.replace(day=min(tag.day, (folgemonat - timedelta(days=1)).day))


def _zaehler_fortschreiben(
    eintrag: dict[str, Any], rest: float, heute: date, max_feld: object, pflege: Pflege
) -> dict[str, Any]:
    tag, alt = heute.isoformat(), _zahl(eintrag.get("rest"))
    gesehen = max(x for x in (_zahl(eintrag.get("hoechst")), rest, alt) if x is not None)
    neu = dict(eintrag) | {"hoechst": hoechst(max_feld, gesehen)}
    if sprung(alt, rest, neu["hoechst"]):
        neu |= {"zuletzt": tag, "gemeldet": None}
    elif pflege.frist_monate and rest <= 0 and not eintrag.get("gemeldet"):
        neu["gemeldet"] = tag
    grenze = (heute - timedelta(days=VERLAUF_TAGE)).isoformat()
    verlauf = {**(eintrag.get("verlauf") or {}), tag: rest}
    neu["verlauf"] = {d: r for d, r in verlauf.items() if d >= grenze}
    return neu


def fortschreiben(
    eintrag: dict[str, Any], rest: float | None, heute: date, max_feld: object, pflege: Pflege
) -> dict[str, Any]:
    """Den gespeicherten Stand einer Pflege um einen Messwert ergänzen; liefert einen neuen Eintrag."""
    if rest is None:
        return dict(eintrag)
    if pflege.weise == SEIT_SERVICE:
        neu = dict(eintrag)
        if zurueckgesetzt(_zahl(eintrag.get("rest")), rest):
            neu["zuletzt"] = heute.isoformat()
    else:
        neu = _zaehler_fortschreiben(eintrag, rest, heute, max_feld, pflege)
    return neu | {"rest": rest}


def _termin(
    art: str, datum: date, heute: date, bald: int, angaben: dict[str, Any], stufe: str
) -> form.Befund:
    tage = (datum - heute).days
    status = form.status_aus(stufe, tage < bald)
    angaben = angaben | {"datum": datum.isoformat()}
    return form.Befund(art, status, float(tage), "d", stufe, angaben)


def _zaehler(art: str, pflege: Pflege, eintrag: dict[str, Any], heute: date) -> form.Befund:
    rest = _zahl(eintrag.get("rest")) or 0.0
    angaben: dict[str, Any] = {"rest_h": rest, "zuletzt": eintrag.get("zuletzt")}
    if gemeldet := eintrag.get("gemeldet"):
        frist = _monate(date.fromisoformat(gemeldet), pflege.frist_monate or 0)
        angaben["gemeldet"] = gemeldet
        return _termin(art, frist, heute, 10**6, angaben, form.BELASTBAR)
    rate, tage = abnahme_je_tag(eintrag.get("verlauf") or {}, heute)
    stufe = form.stufe(tage, **STUFEN)
    angaben["abnahme_je_tag"] = rate
    if rate is None or stufe == form.SAMMELT:
        return form.Befund(art, form.SAMMELT, angaben=angaben)
    if rate < RUHE_H_JE_TAG:
        return form.Befund(art, form.UNAUFFAELLIG, None, "d", stufe, angaben | {"ruht": True})
    datum = heute + timedelta(days=math.ceil(max(rest, 0.0) / rate))
    return _termin(art, datum, heute, BALD_TAGE, angaben, stufe)


def befund(pflege: Pflege, eintrag: dict[str, Any], heute: date) -> form.Befund:
    """Der Befund einer Pflege: Tage bis zur Fälligkeit, das Datum in den Angaben."""
    art = f"pflege_{pflege.art}"
    if pflege.weise == ZAEHLER:
        if _zahl(eintrag.get("rest")) is None:
            return form.fehlt(art, "pflege")
        return _zaehler(art, pflege, eintrag, heute)
    if not (zuletzt := eintrag.get("zuletzt")):
        return form.fehlt(art, "zuletzt")
    intervall = pflege.intervall_tage or 0
    datum = date.fromisoformat(zuletzt) + timedelta(days=intervall)
    angaben = {"zuletzt": zuletzt, "stunden": _zahl(eintrag.get("rest"))}
    return _termin(art, datum, heute, min(BALD_TAGE, intervall // 7), angaben, form.BELASTBAR)


def letzte_erledigung(
    reihe: list[tuple[str, float]], pflege: Pflege, max_feld: object
) -> str | None:
    """Der Tag der letzten Erledigung in einer Stundenreihe `(JJJJ-MM-TT HH, Wert)`."""
    werte = [w for _, w in reihe if _zahl(w) is not None]
    hoch = hoechst(max_feld, max(werte) if werte else None)
    tag = None
    for (_, alt), (zeit, neu) in pairwise(reihe):
        if pflege.weise == SEIT_SERVICE:
            erledigt = zurueckgesetzt(alt, neu)
        else:
            erledigt = sprung(alt, neu, hoch)
        tag = zeit[:10] if erledigt else tag
    return tag
