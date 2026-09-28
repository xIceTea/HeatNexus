"""Regelprofile der Automatik und ihre einstellbaren Werte.

Das Profil folgt der Art der Heizflächen. Eigene Werte aus „Erweitert"
überschreiben die Vorgabe feldweise und werden auf ihre Grenzen gezogen.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, fields, replace
import math
from typing import Any

SCHNELL = "schnell"
STANDARD = "standard"
TRAEGE = "traege"
PROFILE = (SCHNELL, STANDARD, TRAEGE)

HEIZFLAECHEN = {"heizkoerper": SCHNELL, "gemischt": STANDARD, "flaeche": TRAEGE}

ECO = "eco"
AUSGEWOGEN = "ausgewogen"
KOMFORT = "komfort"
AUSRICHTUNGEN = (ECO, AUSGEWOGEN, KOMFORT)


@dataclass(frozen=True)
class Werte:
    """Alle Schwellen und Zeiten, nach denen die Regel entscheidet."""

    heizgrenze: float = 17.0
    hysterese: float = 1.0
    tau_h: float = 15.0
    mindestdauer_h: float = 24.0
    entscheidung: str = "07:00"
    nachpruefung: str = ""
    absenkung_k: float = 1.5
    rueckkehr_k: float = 0.8
    sonnenquote: float = 60.0
    sonnentag: bool = True
    stark: bool = False
    stark_k: float = 1.0
    ruhe_h: float = 2.0
    budget: int = 4
    fenster_k_je_h: float = 3.0
    lernfenster: int = 14
    anpassen: bool = True


VORGABEN: dict[str, Werte] = {
    SCHNELL: Werte(
        tau_h=5.0,
        mindestdauer_h=12.0,
        entscheidung="07:30",
        nachpruefung="11:00",
        absenkung_k=1.0,
        rueckkehr_k=0.5,
        sonnenquote=55.0,
    ),
    STANDARD: Werte(),
    TRAEGE: Werte(
        tau_h=25.0,
        mindestdauer_h=48.0,
        entscheidung="05:00",
        absenkung_k=2.0,
        rueckkehr_k=1.0,
        sonnenquote=65.0,
    ),
}

# Kleinster und größter zulässiger Wert je einstellbarem Zahlenfeld.
GRENZEN: dict[str, tuple[float, float]] = {
    "heizgrenze": (10.0, 22.0),
    "hysterese": (0.5, 3.0),
    "tau_h": (1.0, 48.0),
    "mindestdauer_h": (1.0, 96.0),
    "absenkung_k": (0.5, 5.0),
    "rueckkehr_k": (0.2, 3.0),
    "sonnenquote": (20.0, 100.0),
    "budget": (1.0, 12.0),
    "fenster_k_je_h": (1.0, 10.0),
    "stark_k": (0.3, 3.0),
    "ruhe_h": (0.5, 6.0),
}

# Die Ausrichtung verschiebt die Vorgabe der Heizflächen: Eco greift früher und
# kräftiger ein, Komfort später und sanfter. Eigene Werte gehen beidem vor.
AUSRICHTUNG_VERSATZ: dict[str, dict[str, float]] = {
    ECO: {"heizgrenze": -2.0, "sonnenquote": -15.0, "absenkung_k": 0.5, "rueckkehr_k": 0.4},
    KOMFORT: {"heizgrenze": 1.0, "sonnenquote": 10.0, "absenkung_k": -0.5, "rueckkehr_k": -0.3},
}
AUSRICHTUNG_FEST: dict[str, dict[str, Any]] = {
    ECO: {"stark": True, "stark_k": 0.5, "ruhe_h": 1.0},
    KOMFORT: {"stark": False, "ruhe_h": 3.0},
}
UHRZEITEN = ("entscheidung", "nachpruefung")
SCHALTER = ("sonnentag", "stark", "anpassen")
# Über so viele Tage lernt die Prognosekorrektur; andere Werte gelten nicht.
LERNFENSTER = (3, 7, 14)


def profil_fuer(heizflaechen: str) -> str:
    """Das Profil zur Art der Heizflächen; Unbekanntes gilt als gemischt."""
    return HEIZFLAECHEN.get(heizflaechen, STANDARD)


def _uhrzeit(wert: Any) -> str | None:
    teile = str(wert or "").strip().split(":")
    if len(teile) != 2 or not all(teil.isdigit() for teil in teile):
        return None
    stunde, minute = int(teile[0]), int(teile[1])
    if stunde > 23 or minute > 59:
        return None
    return f"{stunde:02d}:{minute:02d}"


def _zahl(name: str, wert: Any) -> float | int | None:
    if isinstance(wert, bool):
        return None
    try:
        zahl = float(wert)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(zahl):
        return None
    unten, oben = GRENZEN[name]
    zahl = min(max(zahl, unten), oben)
    return round(zahl) if name == "budget" else zahl


def vorgabe(profil: str, ausrichtung: str = AUSGEWOGEN) -> Werte:
    """Die Werte des Profils, verschoben um die Ausrichtung und auf die Grenzen gezogen."""
    basis = VORGABEN.get(profil, VORGABEN[STANDARD])
    aenderungen: dict[str, Any] = {
        name: _zahl(name, getattr(basis, name) + versatz)
        for name, versatz in AUSRICHTUNG_VERSATZ.get(ausrichtung, {}).items()
    }
    return replace(basis, **aenderungen, **AUSRICHTUNG_FEST.get(ausrichtung, {}))


def werte(
    profil: str, eigene: Mapping[str, Any] | None = None, ausrichtung: str = AUSGEWOGEN
) -> Werte:
    """Die Vorgabe des Profils, überschrieben mit den gültigen eigenen Werten."""
    aenderungen: dict[str, Any] = {}
    for name, wert in (eigene or {}).items():
        if name in GRENZEN:
            if (zahl := _zahl(name, wert)) is not None:
                aenderungen[name] = zahl
        elif name == "nachpruefung" and str(wert or "").strip() == "":
            aenderungen[name] = ""
        elif name in UHRZEITEN:
            if (zeit := _uhrzeit(wert)) is not None:
                aenderungen[name] = zeit
        elif name in SCHALTER:
            aenderungen[name] = bool(wert)
        elif name == "lernfenster":
            with suppress(TypeError, ValueError):
                if int(wert) in LERNFENSTER:
                    aenderungen[name] = int(wert)
    return replace(vorgabe(profil, ausrichtung), **aenderungen)


def abweichungen(
    profil: str, eigene: Mapping[str, Any] | None, ausrichtung: str = AUSGEWOGEN
) -> dict[str, Any]:
    """Nur die Felder, die von der Vorgabe des Profils abweichen."""
    basis = vorgabe(profil, ausrichtung)
    aktuell = werte(profil, eigene, ausrichtung)
    return {
        feld.name: getattr(aktuell, feld.name)
        for feld in fields(Werte)
        if getattr(aktuell, feld.name) != getattr(basis, feld.name)
    }
