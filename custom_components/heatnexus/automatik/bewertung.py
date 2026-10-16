"""Was die Regel geprüft hat, als Liste von Bewertungen für Anzeige und Regellauf.

Reine Funktionen, ohne Home Assistant; der Server liefert Struktur, das Panel den Text.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
from typing import Any

from .profile import Werte
from .regel import (
    ABSENKBETRIEB,
    PROGRAMMWAHL,
    SONDERBETRIEB,
    SONNE_RAUM_K,
    Gedaechtnis,
    Lage,
    Zustand,
    abweichung,
    bald_aus,
    bald_schwelle,
    grenze,
    soll_bezug,
    sonne_im_fenster,
)

# Bei einem Eingriff tragen ihn diese Bedingungen, soweit sie erfüllt sind.
TRAGEND = {
    Zustand.SONNENTAG: ("beginn", "sonne", "vorrang", "raeume", "programmwahl", "betriebsart"),
    Zustand.HEIZPAUSE: (
        "at_prognose",
        "at_gedaempft",
        "tagesmittel",
        "sonne",
        "vorrang",
        "raeume",
        "thermostate",
    ),
    Zustand.NUR_WW: ("at_gedaempft", "tagesmittel", "raeume", "thermostate"),
    Zustand.ABWESEND: ("abwesend",),
}
# Sonst entscheidet die erste Bedingung dieser Reihe, die nicht erfüllt ist.
REIHE = (
    "daten",
    "prognose",
    "fenster",
    "programmwahl",
    "betriebsart",
    "beginn",
    "raeume",
    "thermostate",
    "sonne",
)


@dataclass(frozen=True)
class Bewertung:
    """Eine geprüfte Bedingung: Wert, Schwelle, Einheit und ob sie erfüllt ist."""

    name: str
    erfuellt: bool
    wert: float | str | None = None
    schwelle: float | str | None = None
    einheit: str = ""
    entscheidend: bool = False


def _rund(wert: float | None) -> float | None:
    return None if wert is None else round(wert, 1)


def _uhr(zeit: datetime | None) -> str | None:
    return None if zeit is None else zeit.strftime("%H:%M")


def _ueber(wert: float | None, schwelle: float, gleich: bool = False) -> bool:
    if wert is None:
        return False
    return wert >= schwelle if gleich else wert > schwelle


def _temperaturen(lage: Lage, w: Werte) -> list[Bewertung]:
    heizgrenze = grenze(lage, w)
    oben = heizgrenze + w.hysterese
    prognose = min(lage.at_prognose) if lage.at_prognose else None
    bald = bald_schwelle(lage, w) + w.hysterese
    return [
        Bewertung(
            "at_gedaempft",
            _ueber(lage.at_gedaempft, oben),
            _rund(lage.at_gedaempft),
            _rund(oben),
            "°C",
        ),
        Bewertung(
            "tagesmittel",
            _ueber(lage.mittel_heute, heizgrenze, gleich=True),
            _rund(lage.mittel_heute),
            _rund(heizgrenze),
            "°C",
        ),
        Bewertung("at_prognose", bald_aus(lage, w) is not None, _rund(prognose), _rund(bald), "°C"),
    ]


def _messen(lage: Lage, g: Gedaechtnis, w: Werte) -> list[Bewertung]:
    soll = soll_bezug(lage, g)
    abstand = abweichung(lage, soll) if soll is not None and lage.raeume else None
    quote = lage.sonnenquote
    return [
        Bewertung("daten", lage.daten_ok and lage.raum is not None),
        Bewertung("prognose", lage.prognose_ok),
        Bewertung("fenster", not lage.fenster_offen),
        Bewertung(
            "beginn", sonne_im_fenster(lage), _uhr(lage.jetzt), _uhr(lage.fruehester_beginn), "uhr"
        ),
        Bewertung(
            "sonne", _ueber(quote, w.sonnenquote, gleich=True), _rund(quote), w.sonnenquote, "%"
        ),
        Bewertung("vorrang", bool(lage.vorrang_laeuft), _rund(lage.vorrang_minuten), None, "min"),
        Bewertung(
            "raeume",
            _ueber(abstand, -SONNE_RAUM_K, gleich=True),
            _rund(abstand),
            -SONNE_RAUM_K,
            "K",
        ),
        Bewertung("thermostate", lage.ruhig is not False),
        *_temperaturen(lage, w),
        Bewertung("programmwahl", lage.betriebswahl in PROGRAMMWAHL, lage.betriebswahl),
        Bewertung(
            "betriebsart",
            lage.betriebsart != ABSENKBETRIEB and lage.betriebsart not in SONDERBETRIEB,
            lage.betriebsart,
        ),
        Bewertung("abwesend", lage.abwesend),
        Bewertung("hausmodell", lage.modell_freigegeben),
        Bewertung("sperre", g.pause_sperre != lage.jetzt.date().isoformat()),
    ]


def bewerten(lage: Lage, g: Gedaechtnis, w: Werte, zustand: Zustand) -> tuple[Bewertung, ...]:
    """Alle Bewertungen eines Laufs; `entscheidend` markiert, was den Zustand trägt oder verhindert."""
    liste = _messen(lage, g, w)
    if (tragend := TRAGEND.get(zustand)) is not None:
        return tuple(replace(b, entscheidend=b.erfuellt and b.name in tragend) for b in liste)
    offen = {b.name for b in liste if not b.erfuellt}
    erste = next((name for name in REIHE if name in offen), None)
    return tuple(replace(b, entscheidend=b.name == erste) for b in liste)


def kern(bewertungen: tuple[Bewertung, ...]) -> list[dict[str, Any]]:
    """Nur die entscheidenden Bewertungen, für Kachel und Empfehlung."""
    return [asdict(b) for b in bewertungen if b.entscheidend]
