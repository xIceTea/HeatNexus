"""Einstellungen einer Automatik prüfen und in ihre gespeicherte Form bringen.

Ohne Home Assistant. Was fehlt oder nicht passt, wird ergänzt oder abgewiesen;
eigene Werte werden auf ihre Abweichung vom Profil reduziert.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

from .eingaben import hat_thermostat, zahl
from .profile import (
    GRENZEN,
    HEIZFLAECHEN,
    PROFILE,
    SCHALTER,
    UHRZEITEN,
    abweichungen,
    profil_fuer,
)

MODI = ("beobachten", "schalten")
RAUM_ARTEN = ("mittel", "minimum")
LISTEN_MAX = {"raeume": 10, "personen": 10, "fenster": 20}
EIGENE_FELDER = frozenset({*GRENZEN, *UHRZEITEN, *SCHALTER, "lernfenster"})
# Wunschtemperatur der Räume, deren Fühler kein eigenes Ziel kennt.
RAUM_ZIEL = (10.0, 30.0)

_ENTITAET = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
# Temperaturen, die kein Raum sind: Taupunkt, Ziel- und Sollwerte, Oberflächen, Geräte.
_KEIN_RAUM = re.compile(
    r"taupunkt|dew_?point|_ziel|target|setpoint|_soll|oberflache|surface|device_temp|cpu|chip"
)
# Von einer PV-Prognose zählt nur der erwartete Ertrag des ganzen Tages.
_KEIN_TAGESERTRAG = re.compile(r"remaining|rest|hour|stunde|tomorrow|morgen|peak|power")
# Ein Ist-Zähler der PV verrät sich am Namen: PV, Tageswert, kein Monat, Netz oder Speicher.
_PV_IST = re.compile(r"pv|solar|photovolt|wechselrichter|inverter|ertrag|yield|_eq|balkonkraftwerk")
_TAGESWERT = re.compile(r"today|day|tag|daily|heute")
_KEIN_PV_IST = re.compile(
    r"month|monat|year|jahr|total|grid|netz|bms|charg|return|self|power|leistung"
)


def raumfuehler_passt(entity_id: str) -> bool:
    """Ob ein Temperatursensor nach Raumtemperatur aussieht."""
    return not _KEIN_RAUM.search(entity_id)


def pv_ist_passt(entity_id: str) -> bool:
    """Ob ein Energiezähler nach dem tatsächlichen PV-Ertrag des Tages aussieht."""
    return (
        bool(_PV_IST.search(entity_id))
        and bool(_TAGESWERT.search(entity_id))
        and not _KEIN_PV_IST.search(entity_id)
    )


def pv_passt(entity_id: str) -> bool:
    """Ob ein Sensor einer PV-Prognose den Ertrag des ganzen Tages nennt."""
    return not _KEIN_TAGESERTRAG.search(entity_id)


def _raum_ziel(wert: Any) -> float | None:
    ziel = zahl(wert)
    return ziel if ziel is not None and RAUM_ZIEL[0] <= ziel <= RAUM_ZIEL[1] else None


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
        "raum_ziel": _raum_ziel(roh.get("raum_ziel")),
        "wetter": wetter,
        "pv": pv if (pv := _entitaet(roh.get("pv"))) and pv_passt(pv) else None,
        "pv_ist": _entitaet(roh.get("pv_ist")),
        "aussen": _entitaet(roh.get("aussen")),
        "personen": _liste(roh.get("personen"), LISTEN_MAX["personen"]),
        "fenster": _liste(roh.get("fenster"), LISTEN_MAX["fenster"]),
        "fenster_erkennung": bool(roh.get("fenster_erkennung", False)),
        "eigene": abweichungen(profil, eigene),
    }


def klima_vorgabe(konfig: dict[str, Any], alte_raeume: Sequence[str]) -> dict[str, Any]:
    """Mit dem ersten Thermostat den Sonnentag abschalten; die Thermostate gleichen ihn aus."""
    neu = not hat_thermostat(alte_raeume) and hat_thermostat(konfig["raeume"])
    if not neu or "sonnentag" in konfig["eigene"]:
        return konfig
    eigene = abweichungen(konfig["profil"], {**konfig["eigene"], "sonnentag": False})
    return {**konfig, "eigene": eigene}
