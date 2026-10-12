"""Aufgezeichnete Zeitreihen in Stundenwerte der Optimierungshinweise umrechnen.

Das Ergebnis hat das Format des Live-Verlaufs, damit `optimierer.tag_aus_stunden` daraus
Tage bildet. Reine Rechnung ohne Home Assistant; Zeiten kommen als `datetime` in Ortszeit.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from statistics import mean
from typing import Any

from .eingaben import raumwert, wert_zur_stunde

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
    # Je Raum in der Reihenfolge von `raeume`: 1, solange sein Thermostat aus ist; ohne Reihe nie.
    aus: list[Reihe] = field(default_factory=list)
    vi: Reihe = field(default_factory=list)  # Vorlauf-Ist `0/2`
    # Behaglichkeit `3/58`; sie verschiebt `1/1`. Das Raumsoll der Stunde zählt ohne sie.
    behaglichkeit: Reihe = field(default_factory=list)
    # Mit eigenen Raumzielen bleibt die Abweichung gegen diese Ziele unverändert.
    eigene_ziele: bool = False


class _Stufe:
    """Eine Reihe als Stufenfunktion; ein `None` in der Reihe beendet den vorigen Wert."""

    def __init__(self, reihe: Reihe) -> None:
        self._reihe = reihe
        self._zeiten = [zeit for zeit, _ in reihe]

    def _ausschnitt(self, beginn: datetime, ende: datetime) -> Reihe:
        """Der zu `beginn` geltende Eintrag und alle bis vor `ende`."""
        i = bisect_right(self._zeiten, beginn)
        return self._reihe[max(i - 1, 0) : bisect_left(self._zeiten, ende)]

    def zur_stunde(self, beginn: datetime, ende: datetime) -> float | None:
        """Der Wert zum Stundenbeginn, sonst der erste der Stunde; live gilt der erste gesehene."""
        return wert_zur_stunde(self._ausschnitt(beginn, ende), beginn)

    def positiv(self, beginn: datetime, ende: datetime) -> bool:
        """Ob der Wert irgendwann von `beginn` bis vor `ende` über null lag."""
        return any(w is not None and w > 0 for _, w in self._ausschnitt(beginn, ende))


@dataclass(frozen=True)
class _Stufen:
    at: _Stufe
    soll: _Stufe
    vl: _Stufe
    ba: _Stufe
    restzeit: _Stufe
    raeume: list[tuple[_Stufe, _Stufe | float | None]]
    raum_art: str
    aus: list[_Stufe]
    vi: _Stufe
    behaglichkeit: _Stufe
    eigene_ziele: bool


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
        aus=[_Stufe(reihe) for reihe in reihen.aus],
        vi=_Stufe(reihen.vi),
        behaglichkeit=_Stufe(reihen.behaglichkeit),
        eigene_ziele=reihen.eigene_ziele,
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


def _abweichung(
    stufen: _Stufen, beginn: datetime, ende: datetime, soll: float | None
) -> tuple[float | None, float | None]:
    """Raum minus Ziel wie im Live-Verlauf und das mittlere Ziel; mit zu wenigen Räumen nichts."""
    if soll is None:
        return None, None
    werte: list[float | None] = []
    ziele: list[float] = []
    gemeldet = 0
    for i, (ist_reihe, ziel) in enumerate(stufen.raeume):
        if (ist := ist_reihe.zur_stunde(beginn, ende)) is None:
            continue
        gemeldet += 1
        # Ausgeschaltet: gemeldet, aber ohne Ziel; live fehlt der Raum in `Lage.raeume`.
        if i < len(stufen.aus) and stufen.aus[i].zur_stunde(beginn, ende):
            continue
        eigen = ziel.zur_stunde(beginn, ende) if isinstance(ziel, _Stufe) else ziel
        ziele.append(soll if eigen is None else eigen)
        werte.append(ist - ziele[-1])
    # Wie `Laufzeit._lage`: mindestens die Hälfte der eingerichteten Räume liefert einen Wert.
    if not werte or 2 * gemeldet < len(stufen.raeume):
        return None, None
    ab = raumwert(werte, stufen.raum_art)
    return (None if ab is None else round(ab, 2)), round(mean(ziele), 2)


def _felder(stufen: _Stufen, beginn: datetime, ende: datetime) -> dict[str, Any]:
    """Die Felder einer Stunde aus den Werten zum Stundenbeginn; eine Restzeit zählt jederzeit."""
    soll = stufen.soll.zur_stunde(beginn, ende)
    behaglichkeit = stufen.behaglichkeit.zur_stunde(beginn, ende) or 0.0
    basis = None if soll is None else round(soll - behaglichkeit, 2)
    ba = stufen.ba.zur_stunde(beginn, ende)
    ab, ziel = _abweichung(stufen, beginn, ende, soll if stufen.eigene_ziele else basis)
    felder = {
        "at": stufen.at.zur_stunde(beginn, ende),
        "ab": ab,
        "ziel": ziel,
        "soll": basis,
        "vl": stufen.vl.zur_stunde(beginn, ende),
        "vi": stufen.vi.zur_stunde(beginn, ende),
        "ba": None if ba is None else int(ba),
        "vorgabe": stufen.restzeit.positiv(beginn, ende) or None,
    }
    return {name: wert for name, wert in felder.items() if wert is not None}


def stunden_je_tag(reihen: Reihen, tage: list[date]) -> dict[str, dict[str, dict[str, Any]]]:
    """`{"JJJJ-MM-TT": {"H": {"at", "ab", "ziel", "soll", "vl", "vi", "ba", "vorgabe"}}}` wie live.

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
