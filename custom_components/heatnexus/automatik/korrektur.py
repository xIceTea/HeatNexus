"""Gelernte Korrektur der Wetter- und PV-Prognose am eigenen Standort.

Temperatur: Versatz zwischen Prognose und Messwert je Tagesstunde. Sonne:
Verhältnis von tatsächlichem PV-Ertrag zur Prognose, wie bei evcc.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from typing import Any

FENSTER_MAX = 14
PV_TAGE = 30
MIN_TAGE = 7
VERSATZ_MAX = 5.0
FAKTOR_MIN = 0.5
FAKTOR_MAX = 1.5
# Die PV-Prognose des Tages zählt ab dem Morgen; nachts rechnet sie oft noch mit gestern.
MORGEN_AB = 5


def _stunde(zeit: datetime) -> str:
    return zeit.strftime("%Y-%m-%dT%H")


def _begrenzt(wert: float, grenze: float) -> float:
    return max(-grenze, min(grenze, wert))


def noetige_tage(fenster: int) -> int:
    """Ab so vielen Tagen mit Daten wirkt eine Korrektur."""
    return min(MIN_TAGE, fenster)


class Temperaturkorrektur:
    """Versatz Messwert minus Prognose, je Tagesstunde über die letzten Tage."""

    def __init__(self, daten: Any = None) -> None:
        daten = daten if isinstance(daten, Mapping) else {}
        self._vorgemerkt: dict[str, float] = {}
        self._fehler: list[tuple[str, int, float]] = []
        try:
            for schluessel, wert in (daten.get("vorgemerkt") or {}).items():
                self._vorgemerkt[str(schluessel)] = float(wert)
            for datum, stunde, fehler in daten.get("fehler") or []:
                self._fehler.append((str(datum), int(stunde), float(fehler)))
        except (TypeError, ValueError, AttributeError):
            self._vorgemerkt, self._fehler = {}, []

    def vormerken(self, prognose: Iterable[tuple[datetime, float | None]], jetzt: datetime) -> None:
        """Die Prognose der kommenden Stunden merken; spätere Abrufe überschreiben."""
        for zeit, temperatur in prognose:
            if temperatur is not None and zeit > jetzt:
                self._vorgemerkt[_stunde(zeit)] = float(temperatur)
        grenze = _stunde(jetzt - timedelta(hours=2))
        self._vorgemerkt = {k: v for k, v in self._vorgemerkt.items() if k >= grenze}

    def messen(self, jetzt: datetime, gemessen: float | None) -> None:
        """Im ersten Lauf einer Stunde den Fehler dieser Stunde festhalten."""
        # Erst bei gültigem Messwert entnehmen: Ein kurz fehlender Wert verschenkt die Stunde nicht.
        if gemessen is None or (prognose := self._vorgemerkt.pop(_stunde(jetzt), None)) is None:
            return
        self._fehler.append((jetzt.date().isoformat(), jetzt.hour, round(gemessen - prognose, 2)))
        grenze = (jetzt.date() - timedelta(days=FENSTER_MAX - 1)).isoformat()
        self._fehler = [eintrag for eintrag in self._fehler if eintrag[0] >= grenze]

    def _im_fenster(self, fenster: int, heute: date) -> list[tuple[str, int, float]]:
        von, bis = (heute - timedelta(days=fenster)).isoformat(), heute.isoformat()
        return [eintrag for eintrag in self._fehler if von <= eintrag[0] <= bis]

    def lerntage(self, fenster: int, heute: date) -> int:
        """Tage mit Daten im Lernfenster."""
        return len({eintrag[0] for eintrag in self._im_fenster(fenster, heute)})

    def tagesversatz(self, fenster: int, heute: date, *, vorlaeufig: bool = False) -> float | None:
        """Mittlerer Versatz über alle Stunden; `None`, solange zu wenig gelernt ist.

        `vorlaeufig` rechnet schon ab dem ersten Tag – nur zur Anzeige, nicht zum Anpassen.
        """
        if self.lerntage(fenster, heute) < (1 if vorlaeufig else noetige_tage(fenster)):
            return None
        werte = [eintrag[2] for eintrag in self._im_fenster(fenster, heute)]
        return round(_begrenzt(sum(werte) / len(werte), VERSATZ_MAX), 2)

    def versatz(self, stunde: int, fenster: int, heute: date) -> float | None:
        """Versatz einer Tagesstunde; ohne Daten zu dieser Stunde der Tagesversatz."""
        if self.lerntage(fenster, heute) < noetige_tage(fenster):
            return None
        werte = [e[2] for e in self._im_fenster(fenster, heute) if e[1] == stunde]
        if not werte:
            return self.tagesversatz(fenster, heute)
        return round(_begrenzt(sum(werte) / len(werte), VERSATZ_MAX), 2)

    def als_dict(self) -> dict[str, Any]:
        return {
            "vorgemerkt": dict(self._vorgemerkt),
            "fehler": [list(eintrag) for eintrag in self._fehler],
        }


class Pvkorrektur:
    """Morgenprognose und Ist-Ertrag je Tag; daraus der Faktor."""

    def __init__(self, daten: Any = None) -> None:
        tage = daten.get("tage") if isinstance(daten, Mapping) else None
        self._tage: dict[str, dict[str, float | None]] = {}
        for datum, werte in (tage if isinstance(tage, Mapping) else {}).items():
            if isinstance(werte, Mapping):
                self._tage[str(datum)] = {
                    "prognose": _zahl(werte.get("prognose")),
                    "ist": _zahl(werte.get("ist")),
                }

    def _tag(self, jetzt: datetime) -> dict[str, float | None]:
        grenze = (jetzt.date() - timedelta(days=PV_TAGE)).isoformat()
        self._tage = {d: w for d, w in self._tage.items() if d >= grenze}
        return self._tage.setdefault(jetzt.date().isoformat(), {"prognose": None, "ist": None})

    def prognose_merken(self, jetzt: datetime, kwh: float | None) -> None:
        """Die erste Prognose des Tages ab dem Morgen merken."""
        if kwh is None or jetzt.hour < MORGEN_AB:
            return
        tag = self._tag(jetzt)
        if tag["prognose"] is None:
            tag["prognose"] = float(kwh)

    def ist_merken(self, jetzt: datetime, kwh: float | None) -> None:
        """Den höchsten Stand des Tageszählers merken."""
        if kwh is None:
            return
        tag = self._tag(jetzt)
        tag["ist"] = max(tag["ist"] or 0.0, float(kwh))

    def _abgeschlossen(self, fenster: int, heute: date) -> list[tuple[float, float]]:
        von, bis = (heute - timedelta(days=fenster)).isoformat(), heute.isoformat()
        return [
            (w["prognose"], w["ist"])
            for d, w in self._tage.items()
            if von <= d < bis and (w["prognose"] or 0) > 0 and (w["ist"] or 0) > 0
        ]

    def lerntage(self, fenster: int, heute: date) -> int:
        """Abgeschlossene Tage mit Prognose und Ist im Lernfenster."""
        return len(self._abgeschlossen(fenster, heute))

    def faktor(self, fenster: int, heute: date, *, vorlaeufig: bool = False) -> float | None:
        """Ist ÷ Prognose; `None`, solange zu wenig gelernt ist.

        `vorlaeufig` rechnet schon ab dem ersten Tag – nur zur Anzeige, nicht zum Anpassen.
        """
        paare = self._abgeschlossen(fenster, heute)
        if len(paare) < (1 if vorlaeufig else noetige_tage(fenster)):
            return None
        faktor = sum(ist for _, ist in paare) / sum(prognose for prognose, _ in paare)
        return round(max(FAKTOR_MIN, min(FAKTOR_MAX, faktor)), 3)

    def bester_ist(self, heute: date) -> float | None:
        """Höchster Ist-Ertrag der vergangenen Tage – der Maßstab für einen klaren Tag."""
        werte = [w["ist"] for d, w in self._tage.items() if d < heute.isoformat() and w["ist"]]
        return max(werte) if werte else None

    def als_dict(self) -> dict[str, Any]:
        return {"tage": {d: dict(w) for d, w in self._tage.items()}}


def _zahl(wert: Any) -> float | None:
    try:
        return None if wert is None else float(wert)
    except (TypeError, ValueError):
        return None


def sonnenquote_korrigiert(
    prognose_kwh: float | None, faktor: float | None, bester_ist: float | None
) -> float | None:
    """Erwarteter Ertrag heute im Verhältnis zum besten tatsächlichen Tag, in Prozent."""
    if prognose_kwh is None or faktor is None or not bester_ist or bester_ist <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * prognose_kwh * faktor / bester_ist))
