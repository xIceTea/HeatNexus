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
    PAUSE_SONNE_PLUS,
    PROGRAMMWAHL,
    SAISON_RAUM_K,
    SONDERBETRIEB,
    SONNE_RAUM_K,
    Gedaechtnis,
    Lage,
    Zustand,
    bald_aus,
    bald_schwelle,
    grenze,
    raeume_zum_ziel,
    sonne_im_fenster,
)

# Bei einem Eingriff: die Anlässe, von denen einer ihn auslöst, und die Bedingungen, die ihn zulassen.
TRAGEND: dict[Zustand, tuple[tuple[str, ...], tuple[str, ...]]] = {
    Zustand.SONNENTAG: (
        ("sonne", "vorrang", "hausmodell"),
        ("beginn", "raeume", "programmwahl", "betriebsart"),
    ),
    Zustand.HEIZPAUSE: (
        ("at_prognose", "at_gedaempft", "tagesmittel", "sonne", "vorrang", "raeume", "hausmodell"),
        ("raeume", "thermostate"),
    ),
    Zustand.NUR_WW: (("at_gedaempft", "tagesmittel", "sonne"), ("raeume", "thermostate")),
    Zustand.ABWESEND: (("abwesend",), ()),
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


def _schwellen(zustand: Zustand, w: Werte) -> tuple[float, float]:
    """Sonnenquote und Raumabstand, die die Regel für diesen Zustand verlangt."""
    if zustand is Zustand.HEIZPAUSE:
        return w.sonnenquote + PAUSE_SONNE_PLUS, -SAISON_RAUM_K
    if zustand is Zustand.NUR_WW:
        return w.sonnenquote, -SAISON_RAUM_K
    return w.sonnenquote, -SONNE_RAUM_K


def _messen(lage: Lage, g: Gedaechtnis, w: Werte, zustand: Zustand) -> list[Bewertung]:
    _, abstand = raeume_zum_ziel(lage, g)
    quote = lage.sonnenquote
    sonne_ab, raum_ab = _schwellen(zustand, w)
    return [
        Bewertung("daten", lage.daten_ok and lage.raum is not None),
        Bewertung("prognose", lage.prognose_ok),
        Bewertung("fenster", not lage.fenster_offen),
        Bewertung(
            "beginn", sonne_im_fenster(lage), _uhr(lage.jetzt), _uhr(lage.fruehester_beginn), "uhr"
        ),
        Bewertung("sonne", _ueber(quote, sonne_ab, gleich=True), _rund(quote), sonne_ab, "%"),
        Bewertung("vorrang", bool(lage.vorrang_laeuft), _rund(lage.vorrang_minuten), None, "min"),
        Bewertung("raeume", _ueber(abstand, raum_ab, gleich=True), _rund(abstand), raum_ab, "K"),
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


def _traegt(
    b: Bewertung, anlaesse: tuple[str, ...], bedingungen: tuple[str, ...], anlass: str | None
) -> bool:
    if b.name == anlass:
        return True
    # Ohne bekannten Anlass, etwa bei einem älteren Gedächtnis, gilt jeder erfüllte als tragend.
    offen = anlass is None or anlass not in anlaesse
    return b.erfuellt and (b.name in bedingungen or (offen and b.name in anlaesse))


def bewerten(
    lage: Lage, g: Gedaechtnis, w: Werte, zustand: Zustand, anlass: str | None = None
) -> tuple[Bewertung, ...]:
    """Alle Bewertungen eines Laufs; `entscheidend` markiert, was den Zustand trägt oder verhindert.

    `anlass` ist der Name, den die Regel im Gedächtnis des Kandidaten vermerkt (`regel.anlass`).
    """
    liste = _messen(lage, g, w, zustand)
    if (tragend := TRAGEND.get(zustand)) is not None:
        anlaesse, bedingungen = tragend
        return tuple(
            replace(b, entscheidend=_traegt(b, anlaesse, bedingungen, anlass)) for b in liste
        )
    offen = {b.name for b in liste if not b.erfuellt}
    erste = next((name for name in REIHE if name in offen), None)
    return tuple(replace(b, entscheidend=b.name == erste) for b in liste)


def kern(bewertungen: tuple[Bewertung, ...]) -> list[dict[str, Any]]:
    """Nur die entscheidenden Bewertungen, für Kachel und Empfehlung."""
    return [asdict(b) for b in bewertungen if b.entscheidend]
