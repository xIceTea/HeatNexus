"""Optimierungshinweise: wie gut Heizkurve, Sollwert und Zeitprogramm zum Haus passen.

Ausgewertet werden ungestörte Heizstunden seit der letzten Änderung der Kurvenparameter.
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
# Stunden nach einem Eingriff, die noch nicht zählen; ab so vielen sauberen Stunden zählt der Tag.
ERHOLUNG_H = 2
MIN_SAUBER = 6
MIN_TAGE = 7
# Ab so vielen Tagen erscheint eine Tendenz ohne Empfehlung.
MIN_VORLAEUFIG = 4
SCHWELLE_K = 0.5
FROST = 0.0
UEBERGANG = (5.0, 15.0)
# Heizkreistyp `7/76`. Ohne Heizkurve: inaktiv, Pumpenkreis, Vorlaufregelung, Fan Coil.
RADIATOREN = 1
FUSSBODEN = 2
OHNE_KURVE = (0, 3, 4, 5)
# Ohne `7/76` folgt der Typ den Heizflächen der Einrichtung.
HEIZFLAECHEN = {"flaeche": FUSSBODEN, "heizkoerper": RADIATOREN, "gemischt": RADIATOREN}
# Kelvin Vorlauf je Kelvin Raum im Frost- und im Übergangsband.
K_RADIATOREN = (2.5, 3.5)
K_FUSSBODEN = (1.3, 1.3)
# Die Bänder hängen zusammen; empfohlen wird nur dieser Anteil der gerechneten Änderung.
DAEMPFUNG = 0.7
# Liegt der Vorlauf-Ist so weit unter dem Soll, misst die Stunde nicht die Heizkurve.
VORLAUF_LUECKE_K = 3.0
MORGEN_MIN = 60
# Median der Morgenzeit, bei dem der Raum schon zu Programmbeginn warm ist.
MORGEN_SOFORT = 0
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
KOMPENSATION = "3/7"
ANPASSUNG = ("3/101", KOMPENSATION)
# Kurvenpunkte der beiden Bänder; fehlt einer, gilt die Kurve als Ganzes.
BAENDER = ("3/1", "3/13")
# Welche Parameteränderung die Grundlage welcher Hinweise zurücksetzt; der Heizkreistyp
# `7/76` ändert Faktor und Arten.
KURVE = ("3/1", "3/12", "3/13", "3/7", "3/58", "3/101", "7/76")
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
    # Aus der Historie gerechnet statt live archiviert.
    nachgerechnet: bool = False
    # Saubere Heizstunden; fehlt bei älteren Einträgen, dann gilt das gespeicherte `ungestoert`.
    sauber: int | None = None


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
    # Die Behaglichkeit steht schon an ihrer Grenze; `nach` fehlt dann.
    anschlag: bool = False
    # Abweichung im Frostband; nur bei `kurvenform`, `abweichung` gilt dann dem Übergang.
    frost: float | None = None


@dataclass(frozen=True)
class Tendenz:
    """Vorläufige Richtung einer Hinweisart, solange die Tage für eine Empfehlung nicht reichen."""

    art: str
    tage: int
    richtung: str
    wert: float


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
            # Ein Eingriff von der Stunde vor Blockbeginn bis zum Warmwerden verfälscht die Zeit.
            stoerung = any(not _ungestoert(stunden[x]) for x in range(beginn - 1, h + 1))
            return None if stoerung else (h - beginn) * 60, set(range(beginn, h))
        h += 1
    return None, set(range(beginn, h))


def _ungestoert(stunde: dict[str, Any]) -> bool:
    """Weder eine Vorgabe des Nutzers noch ein geschriebener Eingriff der Automatik."""
    if stunde.get("vorgabe"):
        return False
    return stunde.get("aktion") in (None, "programm") or bool(stunde.get("beobachtet"))


def _vorlauf_fehlt(stunde: dict[str, Any]) -> bool:
    """Ob der Vorlauf sein Soll deutlich verfehlt (Puffer leer, Kessel aus, fremde Regelung)."""
    vi, vl = _zahl(stunde.get("vi")), _zahl(stunde.get("vl"))
    return vi is not None and vl is not None and vi < vl - VORLAUF_LUECKE_K


def _saubere(gelesen: dict[int, dict[str, Any]], aufheizen: set[int]) -> list[dict[str, Any]]:
    """Heizstunden mit Abweichung und erreichtem Vorlauf, ohne Aufheizen, Eingriff und Erholung."""
    gestoert = {h for h, s in gelesen.items() if not _ungestoert(s)}
    return [
        s
        for h, s in gelesen.items()
        if _heizt(s)
        and h not in aufheizen
        and _zahl(s.get("ab")) is not None
        and not _vorlauf_fehlt(s)
        and not any(h - e in gestoert for e in range(ERHOLUNG_H + 1))
    ]


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
    sauber = _saubere(gelesen, aufheizen)
    ab_heizen = _werte(sauber, "ab")
    soll = _werte([s for s in alle if _heizt(s)], "soll")
    return Tag(
        datum=datum,
        at=mean(at) if at else None,
        abweichung=mean(ab_heizen) if ab_heizen else None,
        soll=median(soll) if soll else None,
        morgen_min=morgen,
        ungestoert=len(sauber) >= MIN_SAUBER,
        stunden=len(ab),
        sauber=len(sauber),
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


def _grundlage(tage: Sequence[Tag], seit: str | None, heute: str, gruppe: str = "") -> list[Tag]:
    """Ungestörte, ausreichend gemessene Tage nach `seit` und vor heute.

    Die Morgenzeit prüft ihre Stunden selbst; nur ältere Einträge ohne `sauber` brauchen `ungestoert`.
    """
    return [
        t
        for t in tage
        if (t.ungestoert or (gruppe == "morgen" and t.sauber is not None))
        and t.stunden >= MIN_STUNDEN
        and t.datum < heute
        and (seit is None or t.datum > seit)
    ]


def _band(grundlage: list[Tag], passt: Any) -> list[Tag]:
    return [t for t in grundlage if t.at is not None and t.abweichung is not None and passt(t.at)]


def _frost(at: float) -> bool:
    return at < FROST


def _uebergang(at: float) -> bool:
    return UEBERGANG[0] <= at <= UEBERGANG[1]


def _anteil(at: float, klimapunkt: float | None, am_fusspunkt: bool) -> float:
    """Wie stark eine Änderung an einem Kurvenende bei dieser Außentemperatur durchschlägt."""
    if klimapunkt is None or klimapunkt >= FUSS_AT:
        return 1.0
    anteil = (at - klimapunkt) if am_fusspunkt else (FUSS_AT - at)
    return _begrenzt(anteil / (FUSS_AT - klimapunkt), MIN_ANTEIL, 1.0)


def _behaglichkeit(tage: int, seit: str | None, d: float, von: float | None) -> Hinweis:
    """Die Kurve parallel über `3/58`; an der Grenze ohne Zielwert, ohne `3/58` nur die Richtung."""
    art, ab = "heizkurve_parallel", round(d, 1)
    if von is None:
        return Hinweis(art, tage, seit, ab)
    nach = _begrenzt(von - _runden(d, 0.5), *BEHAGLICHKEIT)
    if nach == von:
        return Hinweis(art, tage, seit, ab, "3/58", von, None, "K", anschlag=True)
    return Hinweis(art, tage, seit, ab, "3/58", von, nach, "K")


def _baender(frost: list[Tag], uebergang: list[Tag]) -> tuple[float, float] | None:
    """Die mittlere Abweichung beider Bänder, wenn jedes genug Tage hat."""
    if len(frost) < MIN_TAGE or len(uebergang) < MIN_TAGE:
        return None
    return mean(t.abweichung for t in frost), mean(t.abweichung for t in uebergang)


def _parallel(
    frost: list[Tag], uebergang: list[Tag], von: float | None, seit: str | None
) -> list[Hinweis] | None:
    """Liegen beide Bänder gleich weit daneben, die Behaglichkeit; sonst und ohne `3/58` `None`."""
    if von is None or (mittel := _baender(frost, uebergang)) is None:
        return None
    d_frost, d_uebergang = mittel
    gleich = d_frost * d_uebergang > 0 and abs(d_frost - d_uebergang) < SCHWELLE_K
    if not gleich or min(abs(d_frost), abs(d_uebergang)) < SCHWELLE_K:
        return None
    tage = len(frost) + len(uebergang)
    return [_behaglichkeit(tage, seit, (d_frost + d_uebergang) / 2, von)]


def _band_hinweis(
    art: str, parameter: str, band: list[Tag], von: float | None, k: float, seit: str | None
) -> list[Hinweis]:
    if len(band) < MIN_TAGE or von is None:
        return []
    d = mean(t.abweichung for t in band)
    if abs(d) < SCHWELLE_K:
        return []
    # Ein Hinweis über der Schwelle ändert den Parameter um mindestens ein Grad.
    gerundet = _runden(d * k * DAEMPFUNG) or math.copysign(1, d)
    aenderung = _begrenzt(gerundet, -MAX_KURVE, MAX_KURVE)
    return [Hinweis(art, len(band), seit, round(d, 1), parameter, von, von - aenderung, "°C")]


def _kurve(
    grundlage: list[Tag], p: Mapping[str, Any], seit: str | None, heizkreis_typ: int
) -> list[Hinweis]:
    """Hinweise zur Heizkurve aus dem Frost- und dem Übergangsband."""
    frost = _band(grundlage, _frost)
    uebergang = _band(grundlage, _uebergang)
    parallel = _parallel(frost, uebergang, _aktuell(p, "3/58"), seit)
    if parallel is not None:
        return parallel
    klima = _aktuell(p, "3/12")
    k_frost, k_uebergang = K_FUSSBODEN if heizkreis_typ == FUSSBODEN else K_RADIATOREN
    liste: list[Hinweis] = []
    # Eine Änderung am Kurvenende wirkt im Band nur anteilig; die Empfehlung rechnet das hoch.
    for art, name, band, k, am_fuss in (
        ("heizkurve_frost", "3/13", frost, k_frost, False),
        ("heizkurve_uebergang", "3/1", uebergang, k_uebergang, True),
    ):
        anteil = _anteil(mean(t.at for t in band), klima, am_fuss) if band else 1.0
        liste += _band_hinweis(art, name, band, _aktuell(p, name), k / anteil, seit)
    return liste


def _mit_abweichung(grundlage: list[Tag]) -> list[Tag]:
    return [t for t in grundlage if t.abweichung is not None]


def _kurvenform(grundlage: list[Tag], seit: str | None) -> Hinweis | None:
    """Beide Bänder gegenläufig daneben: eine Parallelverschiebung hilft nicht, die Form passt nicht."""
    frost, uebergang = _band(grundlage, _frost), _band(grundlage, _uebergang)
    if (mittel := _baender(frost, uebergang)) is None:
        return None
    d_frost, d_uebergang = mittel
    if d_frost * d_uebergang >= 0 or min(abs(d_frost), abs(d_uebergang)) < SCHWELLE_K:
        return None
    tage = len(frost) + len(uebergang)
    return Hinweis("kurvenform", tage, seit, round(d_uebergang, 1), frost=round(d_frost, 1))


def _eine_kurve(grundlage: list[Tag], von: float | None, seit: str | None) -> list[Hinweis]:
    """Ohne Kurvenpunkte die ganze Kurve über die Behaglichkeit; ohne `3/58` nur die Richtung."""
    if (form := _kurvenform(grundlage, seit)) is not None:
        return [form]
    tage = _mit_abweichung(grundlage)
    if len(tage) < MIN_TAGE or abs(d := mean(t.abweichung for t in tage)) < SCHWELLE_K:
        return []
    return [_behaglichkeit(len(tage), seit, d, von)]


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


def _morgen_frueh(grundlage: list[Tag], von: float | None, seit: str | None) -> list[Hinweis]:
    """Schon zu Programmbeginn warm; einen Zielwert gibt es nicht, die Wärmespeicherung ist unbekannt."""
    werte = [t.morgen_min for t in grundlage if t.morgen_min is not None]
    if len(werte) < MIN_TAGE or median(werte) != MORGEN_SOFORT:
        return []
    name, wert = ("3/6", von) if von is not None and von > 0 else ("zeitprogramm", None)
    return [Hinweis("morgen_frueh", len(werte), seit, None, name, wert, None, "min", MORGEN_SOFORT)]


def grundlage(
    tage: Sequence[Tag], parameter_verlauf: Mapping[str, Any], heute: date | str
) -> list[Tag]:
    """Die Tage, auf denen die Kurvenhinweise beruhen: ungestört, seit der letzten Änderung."""
    return _grundlage(tage, _seit(parameter_verlauf, "kurve"), str(heute))


def _kurvenhinweise(
    kurve: list[Tag],
    parameter_verlauf: Mapping[str, Any],
    seit: str | None,
    heizkreis_typ: int,
    raumfuehler: bool,
) -> list[Hinweis]:
    if _passt_an(parameter_verlauf, raumfuehler):
        return [Hinweis("steuerung_passt_an", len(kurve), seit)]
    if _zwei_baender(parameter_verlauf):
        return _kurve(kurve, parameter_verlauf, seit, heizkreis_typ)
    return _eine_kurve(kurve, _aktuell(parameter_verlauf, "3/58"), seit)


def hinweise(
    tage: Sequence[Tag],
    parameter_verlauf: Mapping[str, Any],
    heute: date | str,
    *,
    heizkreis_typ: int = RADIATOREN,
    raumfuehler: bool = False,
) -> list[Hinweis]:
    """Die Hinweise zu den Arten aus `arten` in fester Reihenfolge.

    Passt die Steuerung die Kurve selbst an, gibt es keinen Hinweis zur Kurve.
    """
    gezeigt = arten(parameter_verlauf, heizkreis_typ=heizkreis_typ)

    def basis(gruppe: str) -> tuple[list[Tag], str | None]:
        seit = _seit(parameter_verlauf, gruppe)
        return _grundlage(tage, seit, str(heute), gruppe), seit

    liste: list[Hinweis] = []
    if any(art.startswith("kurve") for art in gezeigt):
        kurve, seit = basis("kurve")
        liste += _kurvenhinweise(kurve, parameter_verlauf, seit, heizkreis_typ, raumfuehler)
    if "sollwert" in gezeigt:
        liste += _sollwert(*basis("sollwert"))
    if "morgen" in gezeigt:
        morgen, seit_morgen = basis("morgen")
        vorhaltezeit = _aktuell(parameter_verlauf, "3/6")
        liste += _morgen_spaet(morgen, vorhaltezeit, seit_morgen)
        liste += _morgen_frueh(morgen, vorhaltezeit, seit_morgen)
    return liste


def _zwei_baender(parameter_verlauf: Mapping[str, Any]) -> bool:
    return all(_aktuell(parameter_verlauf, name) is not None for name in BAENDER)


def heizkreis_typ(parameter_verlauf: Mapping[str, Any], heizflaechen: str | None) -> int:
    """Der Typ aus `7/76`; ohne gelesenen Wert nach den Heizflächen der Einrichtung."""
    wert = _aktuell(parameter_verlauf, "7/76")
    if wert is not None and wert.is_integer():
        return int(wert)
    return HEIZFLAECHEN.get(heizflaechen or "", RADIATOREN)


def arten(parameter_verlauf: Mapping[str, Any], *, heizkreis_typ: int = RADIATOREN) -> list[str]:
    """Die Arten der Kachel in Anzeigereihenfolge; zwei Bänder nur mit beiden Kurvenpunkten.

    Ohne Heizkurve entfallen Kurve und Sollwert (sein Rat verweist auf die Kurve), bei Fußboden
    der Morgen.
    """
    morgen = [] if heizkreis_typ == FUSSBODEN else ["morgen"]
    if heizkreis_typ in OHNE_KURVE:
        return morgen
    kurve = ["kurve_uebergang", "kurve_frost"] if _zwei_baender(parameter_verlauf) else ["kurve"]
    return [*kurve, "sollwert", *morgen]


def _passt_an(parameter_verlauf: Mapping[str, Any], raumfuehler: bool) -> bool:
    """Ob die Steuerung die Kurve selbst anpasst; dann gibt es zur Kurve weder Hinweis noch Tendenz.

    Die Kompensation `3/7` passt nur mit einem Raumfühler an der Steuerung etwas an.
    """
    namen = [p for p in ANPASSUNG if raumfuehler or p != KOMPENSATION]
    return any((_aktuell(parameter_verlauf, p) or 0) > 0 for p in namen)


def _reihen(
    tage: Sequence[Tag], parameter_verlauf: Mapping[str, Any], heute: date | str
) -> dict[str, list[Any]]:
    """Je Art die gezählten Werte, mit denselben Filtern wie `hinweise`: Tage im Band, Soll, Minuten."""

    def basis(gruppe: str) -> list[Tag]:
        return _grundlage(tage, _seit(parameter_verlauf, gruppe), str(heute), gruppe)

    kurve = basis("kurve")
    return {
        "kurve_uebergang": _band(kurve, _uebergang),
        "kurve_frost": _band(kurve, _frost),
        "kurve": _mit_abweichung(kurve),
        "sollwert": [t.soll for t in basis("sollwert") if t.soll is not None],
        "morgen": [t.morgen_min for t in basis("morgen") if t.morgen_min is not None],
    }


def fortschritt(
    tage: Sequence[Tag], parameter_verlauf: Mapping[str, Any], heute: date | str
) -> dict[str, int]:
    """Gezählte Tage je Hinweisart."""
    return {art: len(werte) for art, werte in _reihen(tage, parameter_verlauf, heute).items()}


def _richtung(wert: float, schwelle: float, darueber: str) -> str:
    return darueber if wert >= schwelle else "unauffaellig"


def _tendenz(art: str, werte: list[Any]) -> Tendenz:
    if art == "sollwert":
        wert = median(werte)
        return Tendenz(art, len(werte), _richtung(wert, SOLL_HOCH, "hoch"), wert)
    if art == "morgen":
        wert = median(werte)
        minuten = int(_runden(wert))
        richtung = "frueh" if wert == MORGEN_SOFORT else _richtung(minuten, MORGEN_MIN, "spaet")
        return Tendenz(art, len(werte), richtung, minuten)
    d = round(mean(t.abweichung for t in werte), 1)
    richtung = "unauffaellig" if abs(d) < SCHWELLE_K else ("kalt" if d < 0 else "warm")
    return Tendenz(art, len(werte), richtung, d)


def tendenzen(
    tage: Sequence[Tag],
    parameter_verlauf: Mapping[str, Any],
    heute: date | str,
    *,
    heizkreis_typ: int = RADIATOREN,
    raumfuehler: bool = False,
) -> list[Tendenz]:
    """Je Art aus `arten` mit mindestens `MIN_VORLAEUFIG`, aber weniger als `MIN_TAGE` Tagen."""
    passt_an = _passt_an(parameter_verlauf, raumfuehler)
    reihen = _reihen(tage, parameter_verlauf, heute)
    return [
        _tendenz(art, reihen[art])
        for art in arten(parameter_verlauf, heizkreis_typ=heizkreis_typ)
        if MIN_VORLAEUFIG <= len(reihen[art]) < MIN_TAGE
        and not (passt_an and art.startswith("kurve"))
    ]


def parameterstand(parameter_verlauf: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Je Parameter der aktuelle Wert und das Datum der letzten Änderung; der Anfangsstand hat keins."""
    stand = {}
    for name, verlauf in parameter_verlauf.items():
        if (wert := _aktuell(parameter_verlauf, name)) is not None:
            stand[name] = {"wert": wert, "seit": str(verlauf[-1][0]) if len(verlauf) > 1 else None}
    return stand
