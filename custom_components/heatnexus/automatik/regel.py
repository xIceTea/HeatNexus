"""Entscheidungsregel der Automatik je Heizkreis.

Aus einer Momentaufnahme (`Lage`) und dem Gedächtnis des letzten Laufs wird
eine `Entscheidung` mit Begründung. Reine Funktionen, ohne Home Assistant.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime, timedelta
from enum import StrEnum
import math
from typing import Any

from .eingaben import raumwert
from .profile import Werte
from .vorhersage import PAUSE as V_PAUSE
from .vorhersage import PROGRAMM as PROGRAMM_STUFE
from .vorhersage import Vorhersage

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
# Heizpause: Die Steuerung schaltet ab, wenn ihre AT über Raumsoll + 1 K liegt, und heizt unter Raumsoll − 1 K.
PAUSE = "pause"
PAUSE_ABSTAND = 1.5
VORGABE_MIN = 6.0
PAUSE_EINSTIEG_K = 1.5
PAUSE_ERNEUERN_REST = timedelta(minutes=30)
PAUSE_NACHRUECKEN_K = 1.0
# Der Vorlauf-Soll steht nach dem Abschalten noch für den Pumpennachlauf.
PAUSE_NACHLAUF = timedelta(minutes=15)
PAUSE_SONNE_PLUS = 20.0
VORRANG_PAUSE_MINUTEN = 60.0
VORRANG_TAGE_MILD = 2
PROGRAMMWAHL = frozenset({1, 2, 3, 4, 5})
# `2/9` im Absenkbetrieb des Zeitprogramms; `1/1` zeigt dann den Absenksoll.
ABSENKBETRIEB = 2
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
# Woher eine Absenkung kommt: Sonnenquote, Vorrangquelle oder Hausmodell.
ANLASS_QUOTE = "quote"
ANLASS_VORRANG = "vorrang"
ANLASS_MODELL = "modell"


class Zustand(StrEnum):
    """Was die Automatik gerade tut; zugleich die Zustände des Sensors."""

    PROGRAMM = "programm"
    SONNENTAG = "sonnentag"
    NUR_WW = "nur_ww"
    HEIZPAUSE = "heizpause"
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
    # AT der vorigen Stunde; zwei Werte unter der Grenze gelten als anhaltend kalt.
    at_vor_einer_stunde: float | None = None
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
    # Tiefster Prognosewert bis zum nächsten Morgen; fällt er unter die Einschaltschwelle, kein nur Warmwasser.
    minimum_bis_morgen: float | None = None
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
    # AT und Vorlauf-Soll der Steuerung selbst; nach ihnen schaltet sie den Heizkreis.
    at_steuerung: float | None = None
    vl_soll: float | None = None
    # An wie vielen der letzten drei Tage die Vorrangquelle nennenswert geliefert hat.
    vorrang_tage: int | None = None
    # Im Beobachten schreibt die Automatik nichts; der Vorlauf-Soll sagt dann nichts über die Pause.
    beobachten: bool = False
    # Nur mit freigegebenem Hausmodell gesetzt; dann wählt die Vorausschau die Stufe.
    vorhersage: Vorhersage | None = None

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
    saison_grund: str | None = None
    stark_bis: datetime | None = None
    absenkung_art: str | None = None
    absenkung_von: datetime | None = None
    absenkung_bis: datetime | None = None
    absenkung_ziel: datetime | None = None
    absenkung_basis: float | None = None
    absenkung_soll: float | None = None
    # Woher die laufende Absenkung kommt: quote, vorrang oder modell.
    absenkung_anlass: str | None = None
    verlaengert: bool = False
    # Tag, an dem eine Heizpause endete; am selben Tag beginnt keine neue.
    pause_sperre: str | None = None


@dataclass(frozen=True)
class Aktion:
    """Ein Eingriff: nur_ww, zurueck, absenken, pause oder absenkung_ende."""

    art: str
    soll: float | None = None
    minuten: int | None = None
    sicherheit: bool = False
    # Eine laufende Pause neu schreiben; zählt nicht gegen das Budget.
    erneuern: bool = False


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


_KURZ_MIT_SOLL = {
    Zustand.SONNENTAG: "Sonnentag",
    Zustand.ABWESEND: "Abwesend",
    Zustand.HEIZPAUSE: "Heizpause",
}
_KURZ = {
    Zustand.NUR_WW: "Nur Warmwasser",
    Zustand.PAUSIERT: "Pausiert",
    Zustand.FENSTER: "Fenster offen",
    Zustand.KEINE_DATEN: "Keine Daten",
    Zustand.SICHERHEIT: "Sicherheit",
}


def kurz(zustand: Zustand, g: Gedaechtnis, pausiert_bis: datetime | None = None) -> str | None:
    """Der Zustand in wenigen Worten, für eine Badge; im Programm nichts."""
    if name := _KURZ_MIT_SOLL.get(zustand):
        return name if g.absenkung_soll is None else f"{name} · {_zahl(g.absenkung_soll)} °C"
    if zustand is Zustand.PAUSIERT and pausiert_bis is not None:
        return f"Pausiert bis {_uhr(pausiert_bis)}"
    return _KURZ.get(zustand)


def ohne_absenkung(g: Gedaechtnis) -> Gedaechtnis:
    """Das Gedächtnis ohne laufende Absenkung."""
    return replace(
        g,
        absenkung_art=None,
        absenkung_von=None,
        absenkung_bis=None,
        absenkung_ziel=None,
        absenkung_basis=None,
        absenkung_soll=None,
        absenkung_anlass=None,
        verlaengert=False,
    )


def nach_teilerfolg(g: Gedaechtnis, erledigt: tuple[Aktion, ...], jetzt: datetime) -> Gedaechtnis:
    """Das Gedächtnis, wenn nur die ersten Aktionen einer Entscheidung angenommen wurden."""
    for aktion in erledigt:
        if aktion.art == "absenkung_ende":
            g = ohne_absenkung(g)
        elif aktion.art == "zurueck":
            g = replace(
                g,
                saison=HEIZEN,
                saison_seit=jetzt,
                saison_soll=None,
                saison_grund=None,
                stark_bis=None,
            )
    return g


def absenkung_laeuft(g: Gedaechtnis, jetzt: datetime) -> bool:
    """Ob eine eigene Absenkung an der Steuerung noch aktiv sein muss."""
    return g.absenkung_art is not None and g.absenkung_bis is not None and g.absenkung_bis > jetzt


_ZUSTAND_JE_ART = {SONNE: Zustand.SONNENTAG, ABWESEND: Zustand.ABWESEND, PAUSE: Zustand.HEIZPAUSE}


def zustand_aus(g: Gedaechtnis, jetzt: datetime) -> Zustand:
    """Was an der Steuerung gerade gilt, nur aus dem Gedächtnis."""
    if g.saison == NUR_WW:
        return Zustand.NUR_WW
    if absenkung_laeuft(g, jetzt):
        return _ZUSTAND_JE_ART.get(g.absenkung_art, Zustand.PROGRAMM)
    return Zustand.PROGRAMM


def soll_bezug(lage: Lage, g: Gedaechtnis) -> float | None:
    """Raumsoll des Programms; während eigener Eingriffe zeigt `1/1` den gesetzten Wert."""
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


def pause_soll(lage: Lage, w: Werte) -> float | None:
    """Raumsoll der Heizpause: knapp unter der AT der Steuerung, höchstens Rückkehrgrenze + 1 K."""
    if lage.at_steuerung is None:
        return None
    wert = min(grenze(lage, w) - w.hysterese + 1.0, lage.at_steuerung - PAUSE_ABSTAND)
    return max(VORGABE_MIN, math.floor(wert * 2) / 2)


def _bereit(g: Gedaechtnis, jetzt: datetime, w: Werte) -> bool:
    return g.saison_seit is None or jetzt - g.saison_seit >= timedelta(hours=w.mindestdauer_h)


def _zurueck(lage: Lage, g: Gedaechtnis, grund: str) -> Entscheidung:
    return Entscheidung(
        Zustand.PROGRAMM,
        (Aktion("zurueck"),),
        grund,
        Gedaechtnis(saison=HEIZEN, saison_seit=lage.jetzt, pause_sperre=g.pause_sperre),
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
    sperre = lage.jetzt.date().isoformat() if g.absenkung_art == PAUSE else g.pause_sperre
    return Entscheidung(
        Zustand.SICHERHEIT,
        tuple(aktionen),
        f"{anlass} – {folge}",
        Gedaechtnis(saison=HEIZEN, saison_seit=seit, pause_sperre=sperre),
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
            return _zurueck(lage, g, "Sonnentag vorbei – zurück ins Programm.")
        return Entscheidung(
            Zustand.NUR_WW, (), f"Sehr sonnig – nur Warmwasser bis {_uhr(g.stark_bis)}.", g
        )
    abstand = abweichung(lage, soll)
    if abstand < -ZU_KALT_K:
        return _zurueck(lage, g, f"Räume {_kelvin(abstand)} – zurück ins Programm.")
    unten = grenze(lage, w) - w.hysterese
    # Unter ihrer Einschaltschwelle heizt die Steuerung; fordern die Thermostate Wärme an, gilt das sofort.
    if lage.at is not None and lage.at < unten and lage.ruhig is False and abstand < 0:
        return _zurueck(
            lage,
            g,
            f"Außen {_zahl(lage.at)} °C unter {_zahl(unten)} °C, Thermostate fordern Wärme "
            "an – zurück ins Programm.",
        )
    kalt = [x for x in (lage.at, lage.at_vor_einer_stunde) if x is not None]
    if len(kalt) == 2 and max(kalt) < unten:
        return _zurueck(
            lage, g, f"Außen seit einer Stunde unter {_zahl(unten)} °C – zurück ins Programm."
        )
    kuehl = lage.at_gedaempft is not None and lage.at_gedaempft < unten
    if kuehl and _bereit(g, lage.jetzt, w) and abstand < -SAISON_RAUM_K:
        return _zurueck(
            lage,
            g,
            f"Gedämpfte AT {_zahl(lage.at_gedaempft)} °C unter "
            f"{_zahl(unten)} °C – zurück ins Programm.",
        )
    mittel = [x for x in (lage.mittel_heute, lage.mittel_morgen) if x is not None]
    if g.saison_grund == "prognose" and mittel:
        text = (
            f"Übergangszeit – nur Warmwasser nach Prognose, Tagesmittel ab {_zahl(min(mittel))} °C."
        )
    else:
        text = f"Übergangszeit – nur Warmwasser, gedämpfte AT {_zahl(lage.at_gedaempft)} °C."
    return Entscheidung(Zustand.NUR_WW, (), text, g)


def _gleitend(lage: Lage, e: Entscheidung, soll: float, w: Werte) -> Entscheidung:
    """Der Ausstieg aus nur Warmwasser geht in die Heizpause, wenn sie heute noch passt."""
    if [a.art for a in e.aktionen] != ["zurueck"] or any(a.sicherheit for a in e.aktionen):
        return e
    if lage.vorhersage is not None:
        return e
    # Nach dem Zurückschalten steht die Betriebswahl wieder auf dem Programm.
    nachher = replace(lage, betriebswahl=min(PROGRAMMWAHL))
    if not _pause_erlaubt(nachher, e.gedaechtnis, soll, w) or _pause_anlass(lage, w) is None:
        return e
    if (ziel := pause_soll(lage, w)) is None:
        return e
    bis = lage.jetzt + timedelta(minutes=MAX_MINUTEN)
    text = f"{e.begruendung} Danach Heizpause, {_zahl(ziel)} °C bis {_uhr(bis)}."
    pause = _pause_schreiben(lage, e.gedaechtnis, soll, ziel, text, erneuern=False)
    return replace(pause, aktionen=(*e.aktionen, *pause.aktionen))


def _saison(lage: Lage, g: Gedaechtnis, soll: float, w: Werte) -> Entscheidung | None:
    if g.saison == NUR_WW:
        return _gleitend(lage, _saison_nur_ww(lage, g, soll, w), soll, w)
    if lage.betriebswahl not in PROGRAMMWAHL or not _bereit(g, lage.jetzt, w):
        return None
    if abweichung(lage, soll) < -SAISON_RAUM_K:
        return None
    schwelle = grenze(lage, w)
    # Wo die Steuerung jetzt oder in der Nacht wieder heizen will, hielte nur Warmwasser nicht bis morgen.
    unten = schwelle - w.hysterese
    if any(wert is not None and wert < unten for wert in (lage.at, lage.minimum_bis_morgen)):
        return None
    warm = lage.at_gedaempft is not None and lage.at_gedaempft > schwelle + w.hysterese
    tiefer = (
        min(lage.mittel_heute, lage.mittel_morgen)
        if lage.mittel_heute is not None and lage.mittel_morgen is not None
        else None
    )
    # Liefert die Vorrangquelle an mehreren Tagen, reicht ein Tagesmittel knapp unter der Grenze.
    vorrang = (lage.vorrang_tage or 0) >= VORRANG_TAGE_MILD
    mild_ab = schwelle - (1.0 if vorrang else 0.0)
    mild = tiefer is not None and tiefer >= mild_ab
    # Fordert ein Thermostat noch Wärme an, braucht der Heizkreis sie auch.
    if not (warm or mild) or lage.ruhig is False:
        return None
    if warm:
        grund = (
            f"Gedämpfte AT {_zahl(lage.at_gedaempft)} °C über "
            f"{_zahl(schwelle + w.hysterese)} °C – nur Warmwasser."
        )
    else:
        grund = f"Prognose heute und morgen im Mittel ab {_zahl(mild_ab)} °C – nur Warmwasser."
    neu = Gedaechtnis(
        saison=NUR_WW,
        saison_seit=lage.jetzt,
        saison_soll=soll,
        saison_grund="gedaempft" if warm else "prognose",
        pause_sperre=g.pause_sperre,
    )
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
        absenkung_soll=ziel,
    )
    return Entscheidung(
        Zustand.ABWESEND,
        (Aktion("absenken", soll=ziel, minuten=MAX_MINUTEN),),
        f"Niemand zu Hause – {_zahl(ziel)} °C bis {_uhr(bis)}.",
        neu,
    )


def _programm(lage: Lage, g: Gedaechtnis) -> Entscheidung:
    # Ohne Vorlauf-Soll ist der Heizkreis an der Steuerung aus, über ihrer Heizgrenze.
    if lage.vl_soll is not None and lage.vl_soll <= 0:
        at = lage.at_steuerung if lage.at_steuerung is not None else lage.at
        text = f"Kein Eingriff – der Heizkreis ist an der Steuerung aus, AT {_zahl(at)} °C."
    else:
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
        and g.absenkung_anlass == ANLASS_VORRANG
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
            replace(g, absenkung_bis=bis, absenkung_soll=ziel_soll, verlaengert=True),
        )
    ende = g.absenkung_ziel or g.absenkung_bis
    # Die Steuerung hält den geschriebenen Wert, auch wenn sich die Einstellung seither geändert hat.
    aktiv = ziel_soll if g.absenkung_soll is None else g.absenkung_soll
    return Entscheidung(
        Zustand.SONNENTAG, (), f"Sonnentag – {_zahl(aktiv)} °C bis {_uhr(ende)}.", g
    )


def _sonnentag(lage: Lage, g: Gedaechtnis, soll: float, w: Werte) -> Entscheidung:
    if g.absenkung_art == SONNE:
        return _sonnentag_laeuft(lage, g, soll, w)
    moeglich = (
        w.sonnentag
        and lage.vorhersage is None
        and lage.entscheidungszeit
        and lage.betriebswahl in PROGRAMMWAHL
        and lage.absenkung_moeglich
        and lage.betriebsart != ABSENKBETRIEB
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
    mild = lage.at is not None and lage.at >= grenze(lage, w) - w.hysterese
    if (
        w.stark
        and abstand >= w.stark_k
        and quote >= STARK_QUOTE
        and lage.ruhig is not False
        and mild
    ):
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
        absenkung_soll=ziel_soll,
        absenkung_anlass=ANLASS_VORRANG if lage.vorrang_laeuft else ANLASS_QUOTE,
        verlaengert=False,
    )
    return Entscheidung(
        Zustand.SONNENTAG,
        (Aktion("absenken", soll=ziel_soll, minuten=minuten),),
        f"{f'{lage.vorrang_name or "Vorrangquelle"} liefert' if lage.vorrang_laeuft else f'Sonnenquote {quote:.0f} %'} – "
        f"{_zahl(ziel_soll)} °C bis {_uhr(ziel)}.",
        neu,
    )


def _pause_anlass(lage: Lage, w: Werte) -> str | None:
    schwelle = grenze(lage, w)
    if lage.at_gedaempft is not None and lage.at_gedaempft > schwelle + w.hysterese:
        return f"Gedämpfte AT {_zahl(lage.at_gedaempft)} °C über {_zahl(schwelle + w.hysterese)} °C"
    if lage.mittel_heute is not None and lage.mittel_heute >= schwelle:
        return f"Tagesmittel heute {_zahl(lage.mittel_heute)} °C"
    # Die Sonnenquote gilt für den ganzen Tag; nach Sonnenuntergang wärmt sie nicht mehr.
    sonne_scheint = (
        lage.sonnenuntergang is not None and lage.jetzt < lage.sonnenuntergang - VORLAUF_UNTERGANG
    )
    if (
        sonne_scheint
        and lage.sonnenquote is not None
        and lage.sonnenquote >= w.sonnenquote + PAUSE_SONNE_PLUS
    ):
        return f"Sonnenquote {lage.sonnenquote:.0f} %"
    if lage.vorrang_laeuft and (lage.vorrang_minuten or 0.0) >= VORRANG_PAUSE_MINUTEN:
        return f"{lage.vorrang_name or 'Vorrangquelle'} liefert"
    return None


def _pause_erlaubt(lage: Lage, g: Gedaechtnis, soll: float, w: Werte) -> bool:
    unten = grenze(lage, w) - w.hysterese
    return (
        g.saison == HEIZEN
        and g.pause_sperre != lage.jetzt.date().isoformat()
        and lage.absenkung_moeglich
        and lage.betriebswahl in PROGRAMMWAHL
        and lage.at_steuerung is not None
        and lage.at_steuerung >= unten + PAUSE_EINSTIEG_K
        and lage.ruhig is not False
        and abweichung(lage, soll) >= -SAISON_RAUM_K
    )


def _pause_schreiben(
    lage: Lage, g: Gedaechtnis, soll: float, ziel: float, text: str, *, erneuern: bool
) -> Entscheidung:
    bis = lage.jetzt + timedelta(minutes=MAX_MINUTEN)
    basis = g if erneuern else ohne_absenkung(g)
    neu = replace(
        basis,
        absenkung_art=PAUSE,
        absenkung_von=g.absenkung_von if erneuern else lage.jetzt,
        absenkung_bis=bis,
        absenkung_basis=g.absenkung_basis if erneuern else soll,
        absenkung_soll=ziel,
        absenkung_anlass=g.absenkung_anlass if erneuern else None,
    )
    aktion = Aktion("pause", soll=ziel, minuten=MAX_MINUTEN, erneuern=erneuern)
    return Entscheidung(Zustand.HEIZPAUSE, (aktion,), text, neu)


def _pause_ende(lage: Lage, g: Gedaechtnis, soll: float, w: Werte) -> str | None:
    if (abstand := abweichung(lage, soll)) < -w.rueckkehr_k:
        return f"Räume {_kelvin(abstand)} unter Ziel"
    if lage.ruhig is False:
        return "Thermostate fordern Wärme an"
    nachlauf_vorbei = g.absenkung_von is not None and lage.jetzt - g.absenkung_von >= PAUSE_NACHLAUF
    heizt = lage.vl_soll is not None and lage.vl_soll > 0
    if nachlauf_vorbei and heizt and not lage.beobachten:
        return "Die Steuerung heizt wieder"
    return None


def _heizpause_laeuft(lage: Lage, g: Gedaechtnis, soll: float, w: Werte) -> Entscheidung:
    if (grund := _pause_ende(lage, g, soll, w)) is not None:
        neu = replace(ohne_absenkung(g), pause_sperre=lage.jetzt.date().isoformat())
        # Statt ins Programm direkt in den Sonnentag, wenn er jetzt passt; der schreibt die Vorgabe neu.
        folge = _sonnentag(replace(lage, entscheidungszeit=True), neu, soll, w)
        if folge.zustand is Zustand.SONNENTAG and folge.aktionen:
            return replace(folge, begruendung=f"{grund} – Heizpause beendet. {folge.begruendung}")
        return Entscheidung(
            Zustand.PROGRAMM, (Aktion("absenkung_ende"),), f"{grund} – Heizpause beendet.", neu
        )
    ziel = pause_soll(lage, w)
    alt = g.absenkung_soll if g.absenkung_soll is not None else ziel
    knapp = g.absenkung_bis is None or g.absenkung_bis - lage.jetzt < PAUSE_ERNEUERN_REST
    if ziel is not None and (knapp or ziel >= alt + PAUSE_NACHRUECKEN_K):
        # Ein tieferer Wert hielte den Heizkreis bei fallender AT länger aus; nachrücken nur nach oben.
        ziel = max(ziel, alt)
        bis = lage.jetzt + timedelta(minutes=MAX_MINUTEN)
        text = f"Heizpause verlängert – {_zahl(ziel)} °C bis {_uhr(bis)}."
        return _pause_schreiben(lage, g, soll, ziel, text, erneuern=True)
    return Entscheidung(
        Zustand.HEIZPAUSE, (), f"Heizpause – {_zahl(alt)} °C bis {_uhr(g.absenkung_bis)}.", g
    )


def _abwesend_tiefer(lage: Lage, g: Gedaechtnis, soll: float, ziel: float) -> bool:
    # Eine Pause mit höherem Raumsoll ersetzte die tiefere Abwesenheit und heizte mehr.
    laeuft = g.absenkung_art == ABWESEND and g.absenkung_soll is not None
    return (laeuft and ziel >= g.absenkung_soll) or (
        lage.abwesend and ziel >= round(soll - ABWESEND_K, 1)
    )


def _heizpause(lage: Lage, g: Gedaechtnis, soll: float, w: Werte) -> Entscheidung | None:
    if g.absenkung_art == PAUSE:
        if g.absenkung_bis is not None:
            return _heizpause_laeuft(lage, g, soll, w)
        # Ohne Ende ist das Gedächtnis beschädigt; die Regel rechnet ohne die Pause weiter.
        g = ohne_absenkung(g)
    if lage.vorhersage is not None or not _pause_erlaubt(lage, g, soll, w):
        return None
    if (anlass := _pause_anlass(lage, w)) is None:
        return None
    if (ziel := pause_soll(lage, w)) is None or _abwesend_tiefer(lage, g, soll, ziel):
        return None
    bis = lage.jetzt + timedelta(minutes=MAX_MINUTEN)
    text = f"{anlass}: Heizpause, {_zahl(ziel)} °C bis {_uhr(bis)}."
    return _pause_schreiben(lage, g, soll, ziel, text, erneuern=False)


def _text_stufe(v: Vorhersage) -> str:
    if v.stufe == V_PAUSE:
        return (
            f"Räume halten laut Prognose bis {_uhr(v.bis)} über {_zahl(v.tiefst)} °C – Heizpause."
        )
    return (
        f"Mit Absenkung halten die Räume bis {_uhr(v.bis)} über {_zahl(v.tiefst)} °C – Absenkung."
    )


def _vorausschau_ende(lage: Lage, g: Gedaechtnis, v: Vorhersage, eigen: bool) -> Entscheidung:
    """Keine Stufe: Eine Stufe des Modells endet, sonst bleibt das Programm."""
    if v.rueckkehr and eigen:
        text = f"Raum {_zahl(lage.raum)} °C weicht von der Vorhersage ab – zurück ins Programm."
        # Wie nach einer beendeten Heizpause: heute beginnt keine neue Stufe, sonst pendelt es.
        neu = replace(ohne_absenkung(g), pause_sperre=lage.jetzt.date().isoformat())
        return Entscheidung(Zustand.PROGRAMM, (Aktion("absenkung_ende"),), text, neu)
    folge = "zurück ins Programm" if eigen else "kein Eingriff"
    if v.stufe == PROGRAMM_STUFE:
        text = (
            f"Laut Prognose fielen die Räume ohne Programm unter {_zahl(v.ziel_min)} °C – {folge}."
        )
    else:
        text = f"Bis zum Horizont um {_uhr(v.bis)} bleibt keine Stunde – {folge}."
    if not eigen:
        return Entscheidung(Zustand.PROGRAMM, (), text, g)
    return Entscheidung(Zustand.PROGRAMM, (Aktion("absenkung_ende"),), text, ohne_absenkung(g))


def _vorausschau_stufe(
    lage: Lage, g: Gedaechtnis, soll: float, w: Werte, v: Vorhersage, eigen: bool
) -> Entscheidung | None:
    """Heizpause oder Absenkung bis zum Horizont; eine laufende gleiche Stufe nur kurz vor Ablauf neu."""
    art = PAUSE if v.stufe == V_PAUSE else SONNE
    zustand = Zustand.HEIZPAUSE if art == PAUSE else Zustand.SONNENTAG
    gleich = eigen and g.absenkung_art == art
    knapp = g.absenkung_bis is None or g.absenkung_bis - lage.jetzt < PAUSE_ERNEUERN_REST
    if gleich and not knapp:
        return Entscheidung(zustand, (), _text_stufe(v), g)
    ziel = pause_soll(lage, w) if art == PAUSE else round(soll - w.absenkung_k, 1)
    if ziel is None:
        return None
    rest = int((v.bis - lage.jetzt).total_seconds() // 60)
    minuten = max(MIN_MINUTEN, min(MAX_MINUTEN, rest))
    aktion = Aktion(
        "pause" if art == PAUSE else "absenken", soll=ziel, minuten=minuten, erneuern=gleich
    )
    neu = replace(
        g if gleich else ohne_absenkung(g),
        absenkung_art=art,
        absenkung_anlass=ANLASS_MODELL,
        absenkung_von=g.absenkung_von if gleich else lage.jetzt,
        absenkung_bis=lage.jetzt + timedelta(minutes=minuten),
        absenkung_ziel=v.bis,
        absenkung_basis=g.absenkung_basis if gleich else soll,
        absenkung_soll=ziel,
        verlaengert=False,
    )
    return Entscheidung(zustand, (aktion,), _text_stufe(v), neu)


def _vorausschau(lage: Lage, g: Gedaechtnis, soll: float, w: Werte) -> Entscheidung | None:
    """Mit freigegebenem Hausmodell: die gewählte Stufe bis zum Horizont."""
    v = lage.vorhersage
    if v is None or lage.abwesend or not lage.absenkung_moeglich:
        return None
    if lage.betriebswahl not in PROGRAMMWAHL:
        return None
    eigen = g.absenkung_anlass == ANLASS_MODELL and g.absenkung_bis is not None
    # Eine Absenkung der bisherigen Regel läuft nach ihren eigenen Bedingungen zu Ende.
    if g.absenkung_art is not None and not eigen:
        return None
    zu_nah = v.bis - lage.jetzt < timedelta(minutes=MIN_MINUTEN)
    if (v.rueckkehr and eigen) or v.stufe == PROGRAMM_STUFE or zu_nah:
        return _vorausschau_ende(lage, g, v, eigen)
    if not eigen and g.pause_sperre == lage.jetzt.date().isoformat():
        return None
    return _vorausschau_stufe(lage, g, soll, w, v, eigen)


def entscheiden(lage: Lage, alt: Gedaechtnis, werte: Werte) -> Entscheidung:
    """Nach Vorrang: Sicherheit, Pause, Sonderbetrieb, Fenster, Daten, Saison, Vorausschau, Heizpause, Abwesenheit, Sonne."""
    g = _raeumen(lage, alt)
    soll = soll_bezug(lage, g)
    for pruefung in (_sicherheit, _pause, _sonderbetrieb, _fenster, _daten):
        if (ergebnis := pruefung(lage, g, soll, werte)) is not None:
            return ergebnis
    for pruefung in (_saison, _vorausschau, _heizpause, _abwesenheit):
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
