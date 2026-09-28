"""Entscheidungsregel der Automatik je Heizkreis.

Aus einer Momentaufnahme (`Lage`) und dem Gedächtnis des letzten Laufs wird
eine `Entscheidung` mit Begründung. Reine Funktionen, ohne Home Assistant.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from .eingaben import raumwert
from .profile import Werte

AT_FROST = 3.0
RAUM_MIN = 16.0
OHNE_DATEN_MAX = timedelta(hours=2)
SAISON_RAUM_K = 0.5
ZU_KALT_K = 1.0
SONNE_RAUM_K = 0.3
STARK_QUOTE = 80.0
ABWESEND_K = 3.0
MAX_MINUTEN = 400
MIN_MINUTEN = 60
VORLAUF_UNTERGANG = timedelta(hours=2)
VERLAENGERN_REST = timedelta(minutes=5)
# So lange nach Beginn der Absenkung muss eine Quelle mit Vorrang Wärme geliefert haben.
VORRANG_PRUEFEN_NACH = timedelta(hours=4)
VORRANG_MIN_MINUTEN = 15.0
PROGRAMMWAHL = frozenset({1, 2, 3, 4, 5})
# Ohne lesbare Heizgrenze der Steuerung (`3/21`) gilt dieser Wert; außerhalb des Bereichs ebenso.
HEIZGRENZE_RUECKFALL = 17.0
HEIZGRENZE_BEREICH = (0.0, 30.0)
# Betriebsarten (`2/9`), in denen die Steuerung ein eigenes Programm fährt; `3/50` bleibt dabei.
SONDERBETRIEB = {
    5: "Urlaubsprogramm",
    6: "Estrich",
    9: "Handbetrieb",
    10: "Testbetrieb",
    11: "Kaminkehrer",
}

HEIZEN = "heizen"
NUR_WW = "nur_ww"
SONNE = "sonne"
ABWESEND = "abwesend"


class Zustand(StrEnum):
    """Was die Automatik gerade tut; zugleich die Zustände des Sensors."""

    PROGRAMM = "programm"
    SONNENTAG = "sonnentag"
    NUR_WW = "nur_ww"
    ABWESEND = "abwesend"
    PAUSIERT = "pausiert"
    FENSTER = "fenster"
    KEINE_DATEN = "keine_daten"
    SICHERHEIT = "sicherheit"
    AUS = "aus"


@dataclass(frozen=True)
class Lage:
    """Momentaufnahme aller Eingänge."""

    jetzt: datetime
    at: float | None = None
    at_gedaempft: float | None = None
    soll: float | None = None
    # Je Raum Ist und eigenes Ziel; ohne Ziel gilt der Sollwert des Heizkreises.
    raeume: tuple[tuple[float, float | None], ...] = ()
    # Ausgeschaltete Räume: nur ihr Ist-Wert, für Sicherheit und Anzeige.
    aus: tuple[float, ...] = ()
    raum_art: str = "mittel"
    # Ob seit zwei Stunden kein Raum Wärme anfordert; `None` ohne Thermostate.
    ruhig: bool | None = None
    sonnenquote: float | None = None
    mittel_heute: float | None = None
    mittel_morgen: float | None = None
    sonnenuntergang: datetime | None = None
    betriebswahl: int | None = None
    betriebsart: int | None = None
    grenze_steuerung: float | None = None
    daten_ok: bool = True
    daten_fehlen_seit: datetime | None = None
    fenster_offen: bool = False
    abwesend: bool = False
    pausiert_bis: datetime | None = None
    entscheidungszeit: bool = False
    absenkung_moeglich: bool = True
    # Wärmequellen mit Vorrang vor dem Kessel: welche liefert gerade, wie lange heute schon.
    vorrang_laeuft: bool | None = None
    vorrang_minuten: float | None = None
    vorrang_name: str | None = None

    @property
    def raum(self) -> float | None:
        """Raumwert für Sicherheit und Anzeige: Mittel oder kältester Raum."""
        return raumwert([*(ist for ist, _ in self.raeume), *self.aus], self.raum_art)


@dataclass(frozen=True)
class Gedaechtnis:
    """Was vom letzten Lauf bleibt; liegt im Store."""

    saison: str = HEIZEN
    saison_seit: datetime | None = None
    saison_soll: float | None = None
    stark_bis: datetime | None = None
    absenkung_art: str | None = None
    absenkung_von: datetime | None = None
    absenkung_bis: datetime | None = None
    absenkung_ziel: datetime | None = None
    absenkung_basis: float | None = None
    verlaengert: bool = False


@dataclass(frozen=True)
class Aktion:
    """Ein Eingriff: nur_ww, zurueck, absenken oder absenkung_ende."""

    art: str
    soll: float | None = None
    minuten: int | None = None
    sicherheit: bool = False


@dataclass(frozen=True)
class Entscheidung:
    """Ergebnis eines Laufs."""

    zustand: Zustand
    aktionen: tuple[Aktion, ...]
    begruendung: str
    gedaechtnis: Gedaechtnis


def _zahl(wert: float | None) -> str:
    return "–" if wert is None else f"{wert:.1f}".replace(".", ",")


def _kelvin(wert: float) -> str:
    text = f"{abs(wert):.1f} K".replace(".", ",")
    return ("\u2212" if wert < -0.05 else "+" if wert >= 0.05 else "\u00b1") + text


def _uhr(zeit: datetime) -> str:
    return zeit.strftime("%H:%M")


def ohne_absenkung(g: Gedaechtnis) -> Gedaechtnis:
    """Das Gedächtnis ohne laufende Absenkung."""
    return replace(
        g,
        absenkung_art=None,
        absenkung_von=None,
        absenkung_bis=None,
        absenkung_ziel=None,
        absenkung_basis=None,
        verlaengert=False,
    )


def absenkung_laeuft(g: Gedaechtnis, jetzt: datetime) -> bool:
    """Ob eine eigene Absenkung an der Steuerung noch aktiv sein muss."""
    return g.absenkung_art is not None and g.absenkung_bis is not None and g.absenkung_bis > jetzt


def _soll_bezug(lage: Lage, g: Gedaechtnis) -> float | None:
    # Während eigener Eingriffe zeigt `1/1` den gesetzten Wert, nicht den des Programms.
    if g.saison == NUR_WW and g.saison_soll is not None:
        return g.saison_soll
    if g.absenkung_art is not None and g.absenkung_basis is not None:
        return g.absenkung_basis
    return lage.soll


def _raeumen(lage: Lage, g: Gedaechtnis) -> Gedaechtnis:
    if g.absenkung_art is None or g.absenkung_bis is None or g.absenkung_bis > lage.jetzt:
        return g
    verlaengerbar = (
        g.absenkung_art == SONNE
        and not g.verlaengert
        and g.absenkung_ziel is not None
        and g.absenkung_ziel - lage.jetzt >= timedelta(minutes=MIN_MINUTEN)
    )
    weiter_weg = g.absenkung_art == ABWESEND and lage.abwesend
    return g if verlaengerbar or weiter_weg else ohne_absenkung(g)


def abweichung(lage: Lage, soll: float) -> float:
    """Raum minus Ziel, zusammengefasst wie eingestellt; ohne eigenes Ziel gilt `soll`."""
    werte = [ist - (soll if ziel is None else ziel) for ist, ziel in lage.raeume]
    return raumwert(werte, lage.raum_art) or 0.0


def grenze(lage: Lage, w: Werte) -> float:
    """Die Heizgrenze der Steuerung, verschoben um die Ausrichtung."""
    steuerung = lage.grenze_steuerung
    gueltig = steuerung is not None and HEIZGRENZE_BEREICH[0] <= steuerung <= HEIZGRENZE_BEREICH[1]
    return (steuerung if gueltig else HEIZGRENZE_RUECKFALL) + w.grenze_versatz


def _bereit(g: Gedaechtnis, jetzt: datetime, w: Werte) -> bool:
    return g.saison_seit is None or jetzt - g.saison_seit >= timedelta(hours=w.mindestdauer_h)


def _zurueck(lage: Lage, grund: str) -> Entscheidung:
    return Entscheidung(
        Zustand.PROGRAMM,
        (Aktion("zurueck"),),
        grund,
        Gedaechtnis(saison=HEIZEN, saison_seit=lage.jetzt),
    )


def _sicherheit(lage: Lage, g: Gedaechtnis, soll: float | None, w: Werte) -> Entscheidung | None:
    # Frost zählt nur bei abgeschaltetem Heizkreis; kalte klare Tage bringen die meiste Sonne.
    if g.saison == NUR_WW and lage.at is not None and lage.at < AT_FROST:
        anlass = f"Außen {_zahl(lage.at)} °C"
    elif lage.raum is not None and lage.raum < RAUM_MIN:
        anlass = f"Raum {_zahl(lage.raum)} °C"
    elif (
        g.saison == NUR_WW
        and lage.daten_fehlen_seit is not None
        and lage.jetzt - lage.daten_fehlen_seit >= OHNE_DATEN_MAX
    ):
        anlass = "Seit zwei Stunden ohne Messwerte"
    else:
        return None
    aktionen: list[Aktion] = []
    if g.saison == NUR_WW:
        aktionen.append(Aktion("zurueck", sicherheit=True))
    if absenkung_laeuft(g, lage.jetzt):
        aktionen.append(Aktion("absenkung_ende", sicherheit=True))
    folge = "zurück ins Programm." if aktionen else "die Automatik greift nicht ein."
    seit = lage.jetzt if g.saison == NUR_WW else g.saison_seit
    return Entscheidung(
        Zustand.SICHERHEIT,
        tuple(aktionen),
        f"{anlass} – {folge}",
        Gedaechtnis(saison=HEIZEN, saison_seit=seit),
    )


def _pause(lage: Lage, g: Gedaechtnis, soll: float | None, w: Werte) -> Entscheidung | None:
    if lage.pausiert_bis is None or lage.jetzt >= lage.pausiert_bis:
        return None
    return Entscheidung(
        Zustand.PAUSIERT, (), f"Handeingriff – pausiert bis {_uhr(lage.pausiert_bis)}.", g
    )


def _sonderbetrieb(lage: Lage, g: Gedaechtnis, soll: float | None, w: Werte) -> Entscheidung | None:
    if (name := SONDERBETRIEB.get(lage.betriebsart)) is None:
        return None
    return Entscheidung(Zustand.PAUSIERT, (), f"{name} an der Steuerung – keine Eingriffe.", g)


def _fenster(lage: Lage, g: Gedaechtnis, soll: float | None, w: Werte) -> Entscheidung | None:
    if not lage.fenster_offen:
        return None
    return Entscheidung(Zustand.FENSTER, (), "Fenster offen – Entscheidungen ausgesetzt.", g)


def _daten(lage: Lage, g: Gedaechtnis, soll: float | None, w: Werte) -> Entscheidung | None:
    if lage.daten_ok and lage.raum is not None and soll is not None:
        return None
    return Entscheidung(
        Zustand.KEINE_DATEN, (), "Messwerte oder Prognose fehlen – keine neue Entscheidung.", g
    )


def _saison_nur_ww(lage: Lage, g: Gedaechtnis, soll: float, w: Werte) -> Entscheidung:
    if g.stark_bis is not None:
        if (
            lage.jetzt >= g.stark_bis
            or abweichung(lage, soll) < -SAISON_RAUM_K
            or lage.ruhig is False
        ):
            return _zurueck(lage, "Sonnentag vorbei – zurück ins Programm.")
        return Entscheidung(
            Zustand.NUR_WW, (), f"Sehr sonnig – nur Warmwasser bis {_uhr(g.stark_bis)}.", g
        )
    abstand = abweichung(lage, soll)
    if abstand < -ZU_KALT_K:
        return _zurueck(lage, f"Räume {_kelvin(abstand)} – zurück ins Programm.")
    unten = grenze(lage, w) - w.hysterese
    kuehl = lage.at_gedaempft is not None and lage.at_gedaempft < unten
    if kuehl and _bereit(g, lage.jetzt, w) and abstand < -SAISON_RAUM_K:
        return _zurueck(
            lage,
            f"Gedämpfte AT {_zahl(lage.at_gedaempft)} °C unter "
            f"{_zahl(unten)} °C – zurück ins Programm.",
        )
    return Entscheidung(
        Zustand.NUR_WW,
        (),
        f"Übergangszeit – nur Warmwasser, gedämpfte AT {_zahl(lage.at_gedaempft)} °C.",
        g,
    )


def _saison(lage: Lage, g: Gedaechtnis, soll: float, w: Werte) -> Entscheidung | None:
    if g.saison == NUR_WW:
        return _saison_nur_ww(lage, g, soll, w)
    if lage.betriebswahl not in PROGRAMMWAHL or not _bereit(g, lage.jetzt, w):
        return None
    if abweichung(lage, soll) < -SAISON_RAUM_K:
        return None
    schwelle = grenze(lage, w)
    warm = lage.at_gedaempft is not None and lage.at_gedaempft > schwelle + w.hysterese
    mild = (
        lage.mittel_heute is not None
        and lage.mittel_morgen is not None
        and min(lage.mittel_heute, lage.mittel_morgen) >= schwelle
    )
    # Fordert ein Thermostat noch Wärme an, braucht der Heizkreis sie auch.
    if not (warm or mild) or lage.ruhig is False:
        return None
    if warm:
        grund = (
            f"Gedämpfte AT {_zahl(lage.at_gedaempft)} °C über "
            f"{_zahl(schwelle + w.hysterese)} °C – nur Warmwasser."
        )
    else:
        grund = f"Prognose heute und morgen im Mittel ab {_zahl(schwelle)} °C – nur Warmwasser."
    neu = Gedaechtnis(saison=NUR_WW, saison_seit=lage.jetzt, saison_soll=soll)
    # Das neue Gedächtnis kennt die Absenkung nicht mehr; an der Steuerung liefe sie weiter.
    ende = (Aktion("absenkung_ende"),) if absenkung_laeuft(g, lage.jetzt) else ()
    return Entscheidung(Zustand.NUR_WW, (*ende, Aktion("nur_ww")), grund, neu)


def _abwesenheit(lage: Lage, g: Gedaechtnis, soll: float, w: Werte) -> Entscheidung | None:
    laeuft = g.absenkung_art == ABWESEND and absenkung_laeuft(g, lage.jetzt)
    if not lage.abwesend:
        if not laeuft:
            return None
        return Entscheidung(
            Zustand.PROGRAMM,
            (Aktion("absenkung_ende"),),
            "Wieder jemand zu Hause – Absenkung beendet.",
            ohne_absenkung(g),
        )
    if lage.betriebswahl not in PROGRAMMWAHL or not lage.absenkung_moeglich:
        return None
    if laeuft and g.absenkung_bis - lage.jetzt > VERLAENGERN_REST:
        return Entscheidung(
            Zustand.ABWESEND, (), f"Niemand zu Hause – abgesenkt bis {_uhr(g.absenkung_bis)}.", g
        )
    ziel = round(soll - ABWESEND_K, 1)
    bis = lage.jetzt + timedelta(minutes=MAX_MINUTEN)
    neu = replace(
        ohne_absenkung(g),
        absenkung_art=ABWESEND,
        absenkung_von=lage.jetzt,
        absenkung_bis=bis,
        absenkung_basis=soll,
    )
    return Entscheidung(
        Zustand.ABWESEND,
        (Aktion("absenken", soll=ziel, minuten=MAX_MINUTEN),),
        f"Niemand zu Hause – {_zahl(ziel)} °C bis {_uhr(bis)}.",
        neu,
    )


def _programm(lage: Lage, g: Gedaechtnis) -> Entscheidung:
    text = (
        f"Heizt nach Programm – gedämpfte AT {_zahl(lage.at_gedaempft)} °C, "
        f"Raum {_zahl(lage.raum)} °C."
    )
    if lage.ruhig is False:
        text += " Die Räume fordern Wärme an."
    return Entscheidung(Zustand.PROGRAMM, (), text, g)


def _sonnentag_laeuft(lage: Lage, g: Gedaechtnis, soll: float, w: Werte) -> Entscheidung:
    if not w.sonnentag:
        return Entscheidung(
            Zustand.PROGRAMM,
            (Aktion("absenkung_ende"),),
            "Sonnentag ausgeschaltet – Absenkung beendet.",
            ohne_absenkung(g),
        )
    if (abstand := abweichung(lage, soll)) < -w.rueckkehr_k:
        return Entscheidung(
            Zustand.PROGRAMM,
            (Aktion("absenkung_ende"),),
            f"Räume {_kelvin(abstand)} unter Ziel – Absenkung beendet.",
            ohne_absenkung(g),
        )
    if (
        lage.vorrang_minuten is not None
        and lage.vorrang_minuten < VORRANG_MIN_MINUTEN
        and g.absenkung_von is not None
        and lage.jetzt - g.absenkung_von >= VORRANG_PRUEFEN_NACH
    ):
        return Entscheidung(
            Zustand.PROGRAMM,
            (Aktion("absenkung_ende"),),
            f"Keine Wärme aus den Vorrangquellen seit {_uhr(g.absenkung_von)} – Absenkung beendet.",
            ohne_absenkung(g),
        )
    ziel_soll = round(soll - w.absenkung_k, 1)
    if g.absenkung_bis is not None and g.absenkung_bis <= lage.jetzt and g.absenkung_ziel:
        minuten = min(MAX_MINUTEN, int((g.absenkung_ziel - lage.jetzt).total_seconds() // 60))
        bis = lage.jetzt + timedelta(minutes=minuten)
        return Entscheidung(
            Zustand.SONNENTAG,
            (Aktion("absenken", soll=ziel_soll, minuten=minuten),),
            f"Sonnentag verlängert – {_zahl(ziel_soll)} °C bis {_uhr(bis)}.",
            replace(g, absenkung_bis=bis, verlaengert=True),
        )
    ende = g.absenkung_ziel or g.absenkung_bis
    return Entscheidung(
        Zustand.SONNENTAG, (), f"Sonnentag – {_zahl(ziel_soll)} °C bis {_uhr(ende)}.", g
    )


def _sonnentag(lage: Lage, g: Gedaechtnis, soll: float, w: Werte) -> Entscheidung:
    if g.absenkung_art == SONNE:
        return _sonnentag_laeuft(lage, g, soll, w)
    moeglich = (
        w.sonnentag
        and lage.entscheidungszeit
        and lage.betriebswahl in PROGRAMMWAHL
        and lage.absenkung_moeglich
        and (lage.sonnenquote is not None or bool(lage.vorrang_laeuft))
        and lage.sonnenuntergang is not None
    )
    if not moeglich:
        return _programm(lage, g)
    quote = lage.sonnenquote or 0.0
    # Liefert eine Quelle mit Vorrang, soll ihre Wärme den Heizkreis decken, nicht der Kessel.
    if lage.vorrang_laeuft:
        quote = max(quote, w.sonnenquote)
    if quote < w.sonnenquote:
        return Entscheidung(
            Zustand.PROGRAMM,
            (),
            f"Sonnenquote {quote:.0f} % unter {w.sonnenquote:.0f} % – keine Absenkung.",
            g,
        )
    if (abstand := abweichung(lage, soll)) < -SONNE_RAUM_K:
        return Entscheidung(
            Zustand.PROGRAMM, (), f"Räume {_kelvin(abstand)} unter Ziel – keine Absenkung.", g
        )
    ziel = lage.sonnenuntergang - VORLAUF_UNTERGANG
    rest = int((ziel - lage.jetzt).total_seconds() // 60)
    if rest < MIN_MINUTEN:
        return Entscheidung(Zustand.PROGRAMM, (), "Zu spät am Tag für eine Absenkung.", g)
    if w.stark and abstand >= w.stark_k and quote >= STARK_QUOTE and lage.ruhig is not False:
        neu = replace(
            ohne_absenkung(g), saison=NUR_WW, saison_soll=soll, stark_bis=lage.sonnenuntergang
        )
        return Entscheidung(
            Zustand.NUR_WW,
            (Aktion("nur_ww"),),
            f"Sonnenquote {quote:.0f} %, Raum über Soll – nur Warmwasser bis "
            f"{_uhr(lage.sonnenuntergang)}.",
            neu,
        )
    minuten = min(MAX_MINUTEN, rest)
    ziel_soll = round(soll - w.absenkung_k, 1)
    neu = replace(
        g,
        absenkung_art=SONNE,
        absenkung_von=lage.jetzt,
        absenkung_bis=lage.jetzt + timedelta(minutes=minuten),
        absenkung_ziel=ziel,
        absenkung_basis=soll,
        verlaengert=False,
    )
    return Entscheidung(
        Zustand.SONNENTAG,
        (Aktion("absenken", soll=ziel_soll, minuten=minuten),),
        f"{f'{lage.vorrang_name or "Vorrangquelle"} liefert' if lage.vorrang_laeuft else f'Sonnenquote {quote:.0f} %'} – "
        f"{_zahl(ziel_soll)} °C bis {_uhr(ziel)}.",
        neu,
    )


def entscheiden(lage: Lage, alt: Gedaechtnis, werte: Werte) -> Entscheidung:
    """Nach Vorrang: Sicherheit, Pause, Sonderbetrieb, Fenster, Daten, Saison, Abwesenheit, Sonne."""
    g = _raeumen(lage, alt)
    soll = _soll_bezug(lage, g)
    for pruefung in (_sicherheit, _pause, _sonderbetrieb, _fenster, _daten):
        if (ergebnis := pruefung(lage, g, soll, werte)) is not None:
            return ergebnis
    for pruefung in (_saison, _abwesenheit):
        if (ergebnis := pruefung(lage, g, soll, werte)) is not None:
            return ergebnis
    return _sonnentag(lage, g, soll, werte)


_ZEITEN = ("saison_seit", "stark_bis", "absenkung_von", "absenkung_bis", "absenkung_ziel")


def gedaechtnis_als_dict(g: Gedaechtnis) -> dict[str, Any]:
    """Für den Store: Zeiten als ISO-Text."""
    daten = asdict(g)
    for name in _ZEITEN:
        daten[name] = daten[name].isoformat() if daten[name] else None
    return daten


def gedaechtnis_aus_dict(roh: Any) -> Gedaechtnis:
    """Aus dem Store; Unlesbares ergibt ein leeres Gedächtnis."""
    if not isinstance(roh, Mapping):
        return Gedaechtnis()
    bekannt = {feld.name for feld in fields(Gedaechtnis)}
    werte: dict[str, Any] = {}
    for name, wert in roh.items():
        if name not in bekannt:
            continue
        if name in _ZEITEN and wert is not None:
            try:
                wert = datetime.fromisoformat(str(wert))
            except ValueError:
                return Gedaechtnis()
        werte[name] = wert
    return Gedaechtnis(**werte)
