"""Einstellungen einer Automatik prüfen und in ihre gespeicherte Form bringen.

Ohne Home Assistant. Was fehlt oder nicht passt, wird ergänzt oder abgewiesen;
eigene Werte werden auf ihre Abweichung vom Profil reduziert.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from .profile import GRENZEN, HEIZFLAECHEN, PROFILE, UHRZEITEN, abweichungen, profil_fuer

MODI = ("beobachten", "schalten")
RAUM_ARTEN = ("mittel", "minimum")
LISTEN_MAX = {"raeume": 10, "personen": 10, "fenster": 20}
EIGENE_FELDER = frozenset({*GRENZEN, *UHRZEITEN, "stark"})

_ENTITAET = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")


def _entitaet(wert: Any) -> str | None:
    return wert if isinstance(wert, str) and _ENTITAET.match(wert) else None


def _liste(wert: Any, grenze: int) -> list[str]:
    ergebnis: list[str] = []
    for eintrag in wert if isinstance(wert, list | tuple) else []:
        if (kennung := _entitaet(eintrag)) and kennung not in ergebnis:
            ergebnis.append(kennung)
    return ergebnis[:grenze]


def pruefen(roh: Mapping[str, Any]) -> dict[str, Any] | None:
    """Die gespeicherte Form; `None`, wenn Heizkreis, Raumfühler oder Wetter fehlen."""
    heizkreis = str(roh.get("heizkreis") or "").strip()
    raeume = _liste(roh.get("raeume"), LISTEN_MAX["raeume"])
    wetter = _entitaet(roh.get("wetter"))
    if not heizkreis or not raeume or wetter is None:
        return None
    heizflaechen = roh.get("heizflaechen")
    if heizflaechen not in HEIZFLAECHEN:
        heizflaechen = "gemischt"
    profil = roh.get("profil")
    if profil not in PROFILE:
        profil = profil_fuer(heizflaechen)
    eigene_roh = roh.get("eigene") if isinstance(roh.get("eigene"), Mapping) else {}
    eigene = {name: wert for name, wert in eigene_roh.items() if name in EIGENE_FELDER}
    return {
        "heizkreis": heizkreis,
        "entry_id": str(roh.get("entry_id") or ""),
        "aktiv": bool(roh.get("aktiv", True)),
        "modus": roh.get("modus") if roh.get("modus") in MODI else MODI[0],
        "heizflaechen": heizflaechen,
        "profil": profil,
        "raeume": raeume,
        "raum_art": roh.get("raum_art") if roh.get("raum_art") in RAUM_ARTEN else RAUM_ARTEN[0],
        "wetter": wetter,
        "pv": _entitaet(roh.get("pv")),
        "aussen": _entitaet(roh.get("aussen")),
        "personen": _liste(roh.get("personen"), LISTEN_MAX["personen"]),
        "fenster": _liste(roh.get("fenster"), LISTEN_MAX["fenster"]),
        "fenster_erkennung": bool(roh.get("fenster_erkennung", False)),
        "eigene": abweichungen(profil, eigene),
    }
