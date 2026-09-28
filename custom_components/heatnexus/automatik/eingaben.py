"""Eingänge der Automatik aufbereiten: gedämpfte AT, Raum, Sonne, Fenster.

Reine Rechnungen ohne Home Assistant; Zeiten kommen als `datetime` mit Zone.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
import math
from typing import Any, NamedTuple

# Unter so vielen Vergleichstagen sagt der PV-Ertrag nichts über die Sonne.
PV_MIN_TAGE = 7
# Ein Thermostat in diesen Zuständen liefert nichts; er zählt dann nicht.
NICHT_ERREICHBAR = frozenset({"unavailable", "unknown"})


def daempfen(
    stufen: tuple[float, float] | None, messwert: float, dt_s: float, tau_h: float
) -> tuple[float, float]:
    """Zwei Filter erster Ordnung hintereinander, wie die gedämpfte AT bei Siemens."""
    if stufen is None:
        return (messwert, messwert)
    alpha = 1.0 - math.exp(-max(dt_s, 0.0) / (tau_h * 3600.0))
    eins = stufen[0] + alpha * (messwert - stufen[0])
    zwei = stufen[1] + alpha * (eins - stufen[1])
    return (eins, zwei)


def raumwert(werte: list[float | None], art: str) -> float | None:
    """Mittel der Fühler oder der kälteste Raum; ohne gültigen Wert nichts."""
    gueltig = [wert for wert in werte if wert is not None]
    if not gueltig:
        return None
    return min(gueltig) if art == "minimum" else sum(gueltig) / len(gueltig)


class Messung(NamedTuple):
    """Ein Raum: Ist, eigenes Ziel und ob er Wärme anfordert."""

    ist: float
    ziel: float | None
    heizt: bool | None
    # Von Hand oder per Automation ausgeschaltet: kein Bedarf, kein Ziel, gemessen wird weiter.
    aus: bool = False


def zahl(wert: Any) -> float | None:
    """Endliche Zahl oder nichts; Wahrheitswerte zählen nicht als Zahl."""
    if wert is None or isinstance(wert, bool):
        return None
    try:
        zahl = float(wert)
    except (TypeError, ValueError):
        return None
    return zahl if math.isfinite(zahl) else None


def ist_thermostat(entity_id: str) -> bool:
    """Ob ein Raum eine Klima-Entität ist, die Ist, Ziel und Anforderung kennt."""
    return entity_id.startswith("climate.")


def hat_thermostat(raeume: Iterable[str]) -> bool:
    """Ob unter den Räumen ein Thermostat ist."""
    return any(map(ist_thermostat, raeume))


def messmerkmal(entity_id: str) -> str | None:
    """Wo der Messwert eines Raums steht: im Zustand, beim Thermostat in einem Attribut."""
    return "current_temperature" if ist_thermostat(entity_id) else None


def raum_messung(entity_id: str, zustand: str, attribute: Mapping[str, Any]) -> Messung | None:
    """Ist, eigenes Ziel und Wärmeanforderung eines Raums; ein Sensor kennt nur den Ist-Wert."""
    if (merkmal := messmerkmal(entity_id)) is None:
        return None if (ist := zahl(zustand)) is None else Messung(ist, None, None)
    if zustand in NICHT_ERREICHBAR or (ist := zahl(attribute.get(merkmal))) is None:
        return None
    if zustand == "off":
        return Messung(ist, None, False, aus=True)
    return Messung(
        ist, zahl(attribute.get("temperature")), attribute.get("hvac_action") == "heating"
    )


@dataclass(frozen=True)
class Lauf:
    """Wie lange eine Quelle heute geliefert hat; `seit` ist gesetzt, solange sie läuft."""

    datum: str = ""
    minuten: float = 0.0
    seit: datetime | None = None


def lauf_fortschreiben(lauf: Lauf, jetzt: datetime, laeuft: bool) -> Lauf:
    """Den Stand zu `jetzt` bilden; ein neuer Tag beginnt bei null, ein Lauf ab Mitternacht."""
    heute = jetzt.date().isoformat()
    if lauf.datum != heute:
        mitternacht = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
        lauf = Lauf(datum=heute, seit=mitternacht if lauf.seit is not None else None)
    if laeuft and lauf.seit is None:
        return replace(lauf, seit=jetzt)
    if not laeuft and lauf.seit is not None:
        return replace(lauf, minuten=lauf_minuten(lauf, jetzt), seit=None)
    return lauf


def lauf_minuten(lauf: Lauf, jetzt: datetime) -> float:
    """Minuten des Tages bis `jetzt`, der laufende Abschnitt eingerechnet."""
    offen = (jetzt - lauf.seit).total_seconds() / 60 if lauf.seit is not None else 0.0
    return lauf.minuten + max(offen, 0.0)


def lauf_als_dict(lauf: Lauf) -> dict[str, Any]:
    """Für den Store."""
    return {
        "datum": lauf.datum,
        "minuten": lauf.minuten,
        "seit": lauf.seit.isoformat() if lauf.seit else None,
    }


def lauf_aus_dict(roh: Any) -> Lauf:
    """Aus dem Store; Unlesbares ergibt einen leeren Stand."""
    if not isinstance(roh, Mapping):
        return Lauf()
    try:
        seit = datetime.fromisoformat(roh["seit"]) if roh.get("seit") else None
        return Lauf(str(roh.get("datum") or ""), float(roh.get("minuten") or 0.0), seit)
    except (TypeError, ValueError):
        return Lauf()


def sonnenquote_aus_bewoelkung(
    stunden: list[tuple[datetime, float | None]], aufgang: datetime, untergang: datetime
) -> float | None:
    """100 minus mittlere Bewölkung der Stunden zwischen Auf- und Untergang."""
    werte = [
        wolken for zeit, wolken in stunden if wolken is not None and aufgang <= zeit < untergang
    ]
    if not werte:
        return None
    return max(0.0, min(100.0, 100.0 - sum(werte) / len(werte)))


def sonnenquote_aus_pv(heute_kwh: float | None, bisher: list[float]) -> float | None:
    """Erwarteter PV-Ertrag heute im Verhältnis zum besten Tag der letzten Wochen."""
    if heute_kwh is None or len(bisher) < PV_MIN_TAGE:
        return None
    bester = max([heute_kwh, *bisher])
    if bester <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * heute_kwh / bester))


def tagesmittel(tage: list[tuple[date, float | None, float | None]], tag: date) -> float | None:
    """Mittel aus Höchst- und Tiefstwert der Tagesprognose; ohne Tiefstwert der Höchstwert."""
    for datum, hoch, tief in tage:
        if datum != tag or hoch is None:
            continue
        return hoch if tief is None else (hoch + tief) / 2
    return None


def temperatursturz(
    verlauf: list[tuple[float, float]], schwelle_k_je_h: float, fenster_s: float = 600.0
) -> bool:
    """Ob der Raum im Zeitfenster schneller fällt als die Schwelle; `verlauf` aufsteigend."""
    if len(verlauf) < 2:
        return False
    ende_zeit, ende_wert = verlauf[-1]
    for zeit, wert in verlauf:
        dauer = ende_zeit - zeit
        if dauer > fenster_s:
            continue
        if dauer < 60:
            return False
        return (wert - ende_wert) / dauer * 3600.0 >= schwelle_k_je_h
    return False


def wert_zur_stunde(reihe: list[tuple[datetime, float]], stunde: datetime) -> float | None:
    """Der Wert, der zur vollen Stunde galt; davor der erste innerhalb der Stunde."""
    geltend = None
    for zeit, wert in reihe:
        if zeit <= stunde:
            geltend = wert
        elif geltend is None and zeit < stunde + timedelta(hours=1):
            return wert
        else:
            break
    return geltend
