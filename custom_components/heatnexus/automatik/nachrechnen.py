"""Aufgezeichnete Zeitreihen in Stundenwerte der Optimierungshinweise umrechnen.

Das Ergebnis hat das Format des Live-Verlaufs, damit `optimierer.tag_aus_stunden` daraus
Tage bildet. Reine Rechnung ohne Home Assistant; Zeiten kommen als `datetime` in Ortszeit.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from typing import Any

from .eingaben import raumwert

Reihe = list[tuple[datetime, float | None]]


@dataclass(frozen=True)
class Reihen:
    """Die Zeitreihen eines Heizkreises, je Reihe aufsteigend."""

    at: Reihe
    soll: Reihe  # Raumsoll `1/1`
    vl: Reihe  # Vorlauf-Soll
    ba: Reihe  # Betriebsart `2/9`
    restzeit: Reihe  # Restzeit `2/10`
    # Je Raum die Ist-Reihe und das Ziel: eine Reihe, ein fester Wert oder `None` für das Raumsoll.
    raeume: list[tuple[Reihe, Reihe | float | None]]
    raum_art: str


class _Stufe:
    """Eine Reihe als Stufenfunktion; ein `None` in der Reihe beendet den vorigen Wert."""

    def __init__(self, reihe: Reihe) -> None:
        self._zeiten = [zeit for zeit, _ in reihe]
        self._werte = [wert for _, wert in reihe]

    def vor(self, zeit: datetime) -> float | None:
        """Der Wert, der unmittelbar vor `zeit` galt; ein Wechsel genau um `zeit` zählt danach."""
        i = bisect_left(self._zeiten, zeit)
        return self._werte[i - 1] if i else None

    def positiv(self, beginn: datetime, ende: datetime) -> bool:
        """Ob der Wert irgendwann von `beginn` bis vor `ende` über null lag."""
        i = bisect_right(self._zeiten, beginn)
        j = bisect_left(self._zeiten, ende)
        return any(wert is not None and wert > 0 for wert in self._werte[max(i - 1, 0) : j])


@dataclass(frozen=True)
class _Stufen:
    at: _Stufe
    soll: _Stufe
    vl: _Stufe
    ba: _Stufe
    restzeit: _Stufe
    raeume: list[tuple[_Stufe, _Stufe | float | None]]
    raum_art: str


def _vorbereiten(reihen: Reihen) -> _Stufen:
    return _Stufen(
        at=_Stufe(reihen.at),
        soll=_Stufe(reihen.soll),
        vl=_Stufe(reihen.vl),
        ba=_Stufe(reihen.ba),
        restzeit=_Stufe(reihen.restzeit),
        raeume=[
            (_Stufe(ist), _Stufe(ziel) if isinstance(ziel, list | tuple) else ziel)
            for ist, ziel in reihen.raeume
        ],
        raum_art=reihen.raum_art,
    )


def _zone(reihen: Reihen) -> tzinfo | None:
    """Die Zeitzone der Reihen; die Stunden des Tages gelten in dieser Ortszeit."""
    alle = [reihen.at, reihen.soll, reihen.vl, reihen.ba, reihen.restzeit]
    for reihe in [*alle, *(ist for ist, _ in reihen.raeume)]:
        if reihe:
            return reihe[0][0].tzinfo
    return None


def _stunden(tag: date, zone: tzinfo | None) -> list[tuple[int, datetime, datetime]]:
    """Beginn und Ende jeder Stunde; die beim Wechsel auf Sommerzeit fehlende Stunde entfällt."""
    grenzen = [datetime.combine(tag, time(h), zone) for h in range(24)]
    grenzen.append(datetime.combine(tag + timedelta(days=1), time(0), zone))
    return [
        (h, grenzen[h], grenzen[h + 1])
        for h in range(24)
        if zone is None or grenzen[h].astimezone(UTC).astimezone(zone).hour == h
    ]


def _abweichung(stufen: _Stufen, ende: datetime, soll: float | None) -> float | None:
    """Raum minus Ziel wie im Live-Verlauf; fehlt ein Raumwert oder das Raumsoll, nichts."""
    if soll is None or not stufen.raeume:
        return None
    werte: list[float | None] = []
    for ist_reihe, ziel in stufen.raeume:
        if (ist := ist_reihe.vor(ende)) is None:
            return None
        eigen = ziel.vor(ende) if isinstance(ziel, _Stufe) else ziel
        werte.append(ist - (soll if eigen is None else eigen))
    ab = raumwert(werte, stufen.raum_art)
    return None if ab is None else round(ab, 2)


def _felder(stufen: _Stufen, beginn: datetime, ende: datetime) -> dict[str, Any]:
    """Die Felder einer Stunde aus den Werten zum Stundenende; eine Restzeit zählt jederzeit."""
    soll = stufen.soll.vor(ende)
    ba = stufen.ba.vor(ende)
    felder = {
        "at": stufen.at.vor(ende),
        "ab": _abweichung(stufen, ende, soll),
        "soll": soll,
        "vl": stufen.vl.vor(ende),
        "ba": None if ba is None else int(ba),
        "vorgabe": stufen.restzeit.positiv(beginn, ende) or None,
    }
    return {name: wert for name, wert in felder.items() if wert is not None}


def stunden_je_tag(reihen: Reihen, tage: list[date]) -> dict[str, dict[str, dict[str, Any]]]:
    """`{"JJJJ-MM-TT": {"H": {"at", "ab", "soll", "vl", "ba", "vorgabe"}}}` wie der Live-Verlauf.

    Die Stunde steht ohne führende Null; Stunden und Tage ohne jeden Wert entfallen.
    """
    stufen = _vorbereiten(reihen)
    zone = _zone(reihen)
    ergebnis: dict[str, dict[str, dict[str, Any]]] = {}
    for tag in tage:
        stunden = {
            str(stunde): felder
            for stunde, beginn, ende in _stunden(tag, zone)
            if (felder := _felder(stufen, beginn, ende))
        }
        if stunden:
            ergebnis[tag.isoformat()] = stunden
    return ergebnis
