"""Optimierungshinweise: wie gut Heizkurve, Sollwert und Zeitprogramm zum Haus passen.

Ausgewertet werden ungestörte Tage seit der letzten Änderung der Kurvenparameter.
Die Hinweise sind Empfehlungen; geschrieben wird nichts. Ohne Home Assistant testbar.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
import math
from statistics import mean, median
from typing import Any

# Betriebsart `2/9` im Heizbetrieb des Zeitprogramms.
HEIZBETRIEB = 1
MIN_STUNDEN = 12
MIN_TAGE = 7
SCHWELLE_K = 0.5
FROST = 0.0
UEBERGANG = (5.0, 15.0)
# Kelvin Vorlauf je Kelvin Raum, bei Auslegung und am Fußpunkt.
K_VORLAUF = 4.0
K_FUSSPUNKT = 3.0
MORGEN_MIN = 60
SOLL_HOCH = 22.5
# Ab dieser Abweichung gilt der Raum morgens als warm.
WARM_K = -0.3
MAX_KURVE = 10
BEHAGLICHKEIT = (-3.0, 3.0)
MAX_VORHALTEZEIT = 240
# Außentemperatur, bei der die Kurve am Fußpunkt liegt; bei Windhager nicht belegt, übliche Auslegung.
FUSS_AT = 20.0
# Kleinster Anteil, mit dem eine Änderung am Kurvenende auf das Band durchschlägt.
MIN_ANTEIL = 0.25
# Liest die Steuerung hier einen Wert über null, passt sie die Kurve selbst an.
ANPASSUNG = ("3/101", "3/7")
# Welche Parameteränderung die Grundlage welcher Hinweise zurücksetzt.
KURVE = ("3/1", "3/12", "3/13", "3/7", "3/58", "3/101")
GRUPPEN = {"kurve": KURVE, "sollwert": (*KURVE, "3/51"), "morgen": ("3/6",)}


@dataclass(frozen=True)
class Tag:
    """Ein abgeschlossener Tag, zusammengefasst aus seinen Stundenwerten."""

    datum: str
    at: float | None
    abweichung: float | None
    soll: float | None
    morgen_min: int | None
    ungestoert: bool
    stunden: int


@dataclass(frozen=True)
class Hinweis:
    """Eine Empfehlung mit ihrer Grundlage; `nach` fehlt, wo es keinen Zielwert gibt."""

    art: str
    tage: int
    seit: str | None
    abweichung: float | None = None
    parameter: str | None = None
    von: float | None = None
    nach: float | None = None
    einheit: str | None = None
    # Gemessene Minuten bis zum Ziel; nur bei „morgens zu spät warm“.
    minuten: int | None = None


def _zahl(wert: Any) -> float | None:
    """Eine endliche Zahl oder `None`; Zahlen als Text werden gelesen."""
    if isinstance(wert, bool) or wert is None:
        return None
    try:
        zahl = float(wert)
    except (TypeError, ValueError):
        return None
    return zahl if math.isfinite(zahl) else None


def _runden(wert: float, schritt: float = 1.0) -> float:
    """Auf ein Vielfaches von `schritt`, die Hälfte weg von null."""
    return math.copysign(math.floor(abs(wert) / schritt + 0.5) * schritt, wert) + 0.0


def _begrenzt(wert: float, unten: float, oben: float) -> float:
    return max(unten, min(oben, wert))


def _werte(stunden: list[dict[str, Any]], feld: str) -> list[float]:
    return [z for s in stunden if (z := _zahl(s.get(feld))) is not None]


def _heizt(stunde: dict[str, Any]) -> bool | None:
    """Ob die Stunde im Heizbetrieb lag; ohne vermerkte Betriebsart unbekannt."""
    ba = _zahl(stunde.get("ba"))
    return None if ba is None else ba == HEIZBETRIEB


def _aufheizen(stunden: dict[int, dict[str, Any]]) -> tuple[int | None, set[int]]:
    """Minuten vom Beginn des ersten Heizblocks bis der Raum warm ist, dazu die Stunden davor.

    Der Block beginnt nach einer Stunde mit vermerkter anderer Betriebsart; sonst gibt es keinen Morgen.
    """
    heizt = {h: _heizt(s) for h, s in stunden.items()}
    beginn = next((h for h in sorted(heizt) if heizt[h] and heizt.get(h - 1) is False), None)
    if beginn is None:
        return None, set()
    h = beginn
    while heizt.get(h):
        ab = _zahl(stunden[h].get("ab"))
        if ab is not None and ab >= WARM_K:
            return (h - beginn) * 60, set(range(beginn, h))
        h += 1
    return None, set(range(beginn, h))


def _ungestoert(stunde: dict[str, Any]) -> bool:
    """Weder eine Vorgabe des Nutzers noch ein geschriebener Eingriff der Automatik."""
    if stunde.get("vorgabe"):
        return False
    return stunde.get("aktion") in (None, "programm") or bool(stunde.get("beobachtet"))


def _stunden_lesen(stunden: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    gelesen = {}
    for schluessel, werte in stunden.items():
        if isinstance(werte, dict) and str(schluessel).isdigit():
            gelesen[int(schluessel)] = werte
    return gelesen


def tag_aus_stunden(datum: str, stunden: Mapping[str, Any]) -> Tag | None:
    """Den Tag aus `verlauf["stunden"]` zusammenfassen; ohne Außentemperatur und Abweichung `None`."""
    gelesen = _stunden_lesen(stunden)
    alle = list(gelesen.values())
    at, ab = _werte(alle, "at"), _werte(alle, "ab")
    if not at and not ab:
        return None
    morgen, aufheizen = _aufheizen(gelesen)
    # Die Aufheizphase liegt naturgemäß unter dem Ziel; sie betrifft die Vorhaltezeit, nicht die Kurve.
    heizen = [s for h, s in gelesen.items() if _heizt(s) and h not in aufheizen]
    ab_heizen = _werte(heizen, "ab")
    soll = _werte([s for s in alle if _heizt(s)], "soll")
    return Tag(
        datum=datum,
        at=mean(at) if at else None,
        abweichung=mean(ab_heizen) if ab_heizen else None,
        soll=median(soll) if soll else None,
        morgen_min=morgen,
        ungestoert=all(_ungestoert(s) for s in alle),
        stunden=len(ab),
    )


def _seit(parameter_verlauf: Mapping[str, Any], gruppe: str = "sollwert") -> str | None:
    """Jüngste Änderung der Parameter einer Gruppe; der erste Eintrag ist nur der Anfangsstand."""
    daten = [
        str(eintrag[0])
        for name in GRUPPEN[gruppe]
        for eintrag in (parameter_verlauf.get(name) or [])[1:]
        if eintrag
    ]
    return max(daten, default=None)


def _aktuell(parameter_verlauf: Mapping[str, Any], schluessel: str) -> float | None:
    verlauf = parameter_verlauf.get(schluessel) or []
    letzter = verlauf[-1] if verlauf else None
    return _zahl(letzter[1]) if letzter and len(letzter) > 1 else None


def _grundlage(tage: Sequence[Tag], seit: str | None, heute: str) -> list[Tag]:
    """Ungestörte, ausreichend gemessene Tage nach `seit` und vor heute."""
    return [
        t
        for t in tage
        if t.ungestoert
        and t.stunden >= MIN_STUNDEN
        and t.datum < heute
        and (seit is None or t.datum > seit)
    ]


def _band(grundlage: list[Tag], passt: Any) -> list[Tag]:
    return [t for t in grundlage if t.at is not None and t.abweichung is not None and passt(t.at)]


def _anteil(at: float, klimapunkt: float | None, am_fusspunkt: bool) -> float:
    """Wie stark eine Änderung an einem Kurvenende bei dieser Außentemperatur durchschlägt."""
    if klimapunkt is None or klimapunkt >= FUSS_AT:
        return 1.0
    anteil = (at - klimapunkt) if am_fusspunkt else (FUSS_AT - at)
    return _begrenzt(anteil / (FUSS_AT - klimapunkt), MIN_ANTEIL, 1.0)


def _parallel(
    frost: list[Tag], uebergang: list[Tag], von: float | None, seit: str | None
) -> list[Hinweis] | None:
    """Liegen beide Bänder gleich weit daneben, die Behaglichkeit; sonst `None`."""
    if len(frost) < MIN_TAGE or len(uebergang) < MIN_TAGE:
        return None
    d_frost = mean(t.abweichung for t in frost)
    d_uebergang = mean(t.abweichung for t in uebergang)
    gleich = d_frost * d_uebergang > 0 and abs(d_frost - d_uebergang) < SCHWELLE_K
    if not gleich or min(abs(d_frost), abs(d_uebergang)) < SCHWELLE_K:
        return None
    mittel = (d_frost + d_uebergang) / 2
    if von is None:
        return []
    nach = _begrenzt(von - _runden(mittel, 0.5), *BEHAGLICHKEIT)
    if nach == von:
        return []
    tage = len(frost) + len(uebergang)
    return [Hinweis("heizkurve_parallel", tage, seit, round(mittel, 1), "3/58", von, nach, "K")]


def _band_hinweis(
    art: str, parameter: str, band: list[Tag], von: float | None, k: float, seit: str | None
) -> list[Hinweis]:
    if len(band) < MIN_TAGE or von is None:
        return []
    d = mean(t.abweichung for t in band)
    if abs(d) < SCHWELLE_K:
        return []
    aenderung = _begrenzt(_runden(d * k), -MAX_KURVE, MAX_KURVE)
    return [Hinweis(art, len(band), seit, round(d, 1), parameter, von, von - aenderung, "°C")]


def _kurve(grundlage: list[Tag], p: Mapping[str, Any], seit: str | None) -> list[Hinweis]:
    """Hinweise zur Heizkurve aus dem Frost- und dem Übergangsband."""
    frost = _band(grundlage, lambda at: at < FROST)
    uebergang = _band(grundlage, lambda at: UEBERGANG[0] <= at <= UEBERGANG[1])
    parallel = _parallel(frost, uebergang, _aktuell(p, "3/58"), seit)
    if parallel is not None:
        return parallel
    klima = _aktuell(p, "3/12")
    liste: list[Hinweis] = []
    # Eine Änderung am Kurvenende wirkt im Band nur anteilig; die Empfehlung rechnet das hoch.
    for art, name, band, k, am_fuss in (
        ("heizkurve_frost", "3/13", frost, K_VORLAUF, False),
        ("heizkurve_uebergang", "3/1", uebergang, K_FUSSPUNKT, True),
    ):
        anteil = _anteil(mean(t.at for t in band), klima, am_fuss) if band else 1.0
        liste += _band_hinweis(art, name, band, _aktuell(p, name), k / anteil, seit)
    return liste


def _sollwert(grundlage: list[Tag], seit: str | None) -> list[Hinweis]:
    """Ein dauerhaft hoher Raumsollwert gleicht meist eine zu flache Kurve aus."""
    werte = [t.soll for t in grundlage if t.soll is not None]
    if len(werte) < MIN_TAGE or (wert := median(werte)) < SOLL_HOCH:
        return []
    return [Hinweis("sollwert_ausgleich", len(werte), seit, None, "3/51", wert, None, "°C")]


def _morgen_spaet(grundlage: list[Tag], von: float | None, seit: str | None) -> list[Hinweis]:
    """Vorhaltezeit verlängern; meldet die Steuerung keine, das Heizprogramm früher starten."""
    werte = [t.morgen_min for t in grundlage if t.morgen_min is not None]
    if len(werte) < MIN_TAGE or (wert := median(werte)) < MORGEN_MIN:
        return []
    minuten, frueher = int(_runden(wert)), _runden(wert, 15)
    if von is None:
        return [
            Hinweis(
                "morgen_spaet",
                len(werte),
                seit,
                None,
                "zeitprogramm",
                None,
                frueher,
                "min",
                minuten,
            )
        ]
    nach = min(MAX_VORHALTEZEIT, von + frueher)
    return [Hinweis("morgen_spaet", len(werte), seit, None, "3/6", von, nach, "min", minuten)]


def grundlage(
    tage: Sequence[Tag], parameter_verlauf: Mapping[str, Any], heute: date | str
) -> list[Tag]:
    """Die Tage, auf denen die Kurvenhinweise beruhen: ungestört, seit der letzten Änderung."""
    return _grundlage(tage, _seit(parameter_verlauf, "kurve"), str(heute))


def hinweise(
    tage: Sequence[Tag], parameter_verlauf: Mapping[str, Any], heute: date | str
) -> list[Hinweis]:
    """Alle Hinweise in fester Reihenfolge; passt die Steuerung selbst an, keiner zur Kurve."""

    def basis(gruppe: str) -> tuple[list[Tag], str | None]:
        seit = _seit(parameter_verlauf, gruppe)
        return _grundlage(tage, seit, str(heute)), seit

    kurve, seit = basis("kurve")
    if any((_aktuell(parameter_verlauf, p) or 0) > 0 for p in ANPASSUNG):
        liste = [Hinweis("steuerung_passt_an", len(kurve), seit)]
    else:
        liste = _kurve(kurve, parameter_verlauf, seit)
    liste += _sollwert(*basis("sollwert"))
    morgen, seit_morgen = basis("morgen")
    return liste + _morgen_spaet(morgen, _aktuell(parameter_verlauf, "3/6"), seit_morgen)
