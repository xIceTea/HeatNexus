"""Brennstoff im Takt des Befunds: Zählerstände je Tag, Vorgaben der Anlage, Lieferungen."""

from __future__ import annotations

from datetime import date
from typing import Any

from ..helpers import get_oid_value
from . import brennstoff
from .abgaslauf import ziele_von
from .abgasziele import BRENNSTOFF_PUROWIN, AbgasZiel
from .auswertung import Brennstoffgeraet
from .pflegelauf import beschrieben, geraetename

HEIZWERT_BIOWIN = "/43/104/0"
NENN = ("/39/61/0", "/11/2/0")
# Der Hybridmanager führt den Wirkungsgrad des Pelletskessels für seinen Kostenvergleich.
WIRKUNGSGRAD_HYBRID = "/54/2/0"


def _wirkungsgrad(coordinator: Any) -> float | None:
    for oid in (coordinator.data or {}).get("oids") or {}:
        if oid.endswith(WIRKUNGSGRAD_HYBRID):
            wert = get_oid_value(coordinator, oid)
            return wert / 100 if wert else None
    return None


def vorgabe(coordinator: Any, z: AbgasZiel) -> dict[str, Any]:
    """Art, Weise und Werte, die die Anlage selbst meldet; eingetragene Werte gehen vor."""

    def wert(adresse: str) -> float | None:
        return get_oid_value(coordinator, adresse, z.prefix)

    code = wert(BRENNSTOFF_PUROWIN) if z.fct_type == 25 else None
    art = brennstoff.art_von(z.fct_type, code)
    zaehler = brennstoff.ZAEHLER.get(z.fct_type)
    hat_zaehler = bool(zaehler) and beschrieben(coordinator, f"{z.prefix}{zaehler}")
    ergebnis: dict[str, Any] = {"art": art, "weise": brennstoff.weise_von(z.fct_type, hat_zaehler)}
    if (heizwert := wert(HEIZWERT_BIOWIN)) and art == "pellets":
        ergebnis["heizwert"] = heizwert * 1000
    if (grad := _wirkungsgrad(coordinator)) is not None:
        ergebnis["wirkungsgrad"] = grad
    if z.logwin:
        nenn = next((w for a in NENN if (w := wert(a))), None)
        ergebnis["fuellmenge"] = brennstoff.fuellmenge(nenn)
    return ergebnis


def messen(coordinator: Any, archiv: Any, heute: date) -> None:
    """Den Zählerstand je Tag merken, wo die Steuerung den Brennstoff zählt."""
    for z in ziele_von(coordinator):
        adresse = brennstoff.ZAEHLER.get(z.fct_type)
        if adresse and (wert := get_oid_value(coordinator, adresse, z.prefix)) is not None:
            archiv.zaehler_setzen(z.prefix, heute.isoformat(), wert)


def geraete(coordinator: Any) -> list[Brennstoffgeraet]:
    """Je Kessel mit Lager, was die Auswertung braucht."""
    return [
        Brennstoffgeraet(
            z.device_id, geraetename(coordinator, z.device_id), z.prefix, vorgabe(coordinator, z)
        )
        for z in ziele_von(coordinator)
    ]


def einstellung(coordinator: Any, z: AbgasZiel) -> str | None:
    """Welche Einstellung die Rechnung braucht: Füllmenge am LogWIN, Heizwert ohne Zähler."""
    if z.logwin:
        return "fuellmenge"
    return "heizwert" if vorgabe(coordinator, z)["weise"] == "waerme" else None


def kennungen(coordinator: Any) -> dict[str, str]:
    """Kennung → Domäne der Brennstoff-Entitäten; ohne sie gälten sie als verwaist."""
    gefunden: dict[str, str] = {}
    for z in ziele_von(coordinator):
        gefunden[f"{z.device_id}-befund-brennstoff"] = "sensor"
        gefunden[f"{z.device_id}-brennstoffvorrat"] = "number"
        if art := einstellung(coordinator, z):
            gefunden[f"{z.device_id}-brennstoff-{art}"] = "number"
    return gefunden


def liefern(
    archiv: Any,
    prefix: str,
    vorgabe_: dict[str, Any],
    menge: float,
    rest: float | None,
    heute: date,
) -> None:
    """Eine Lieferung eintragen; ohne `rest` gilt der gerechnete Vorrat als Rest."""
    eigen = archiv.lager(prefix)
    lager = vorgabe_ | eigen
    tage_k, zaehler = archiv.tage_k.get(prefix, {}), archiv.zaehler(prefix)
    roh = brennstoff.tagesverbrauch(lager, tage_k, zaehler, mit_korrektur=False)
    aktuell = brennstoff.bestand(lager, brennstoff.tagesverbrauch(lager, tage_k, zaehler))
    neu = brennstoff.geliefert(lager, menge, rest, heute, roh, aktuell)
    # Werte der Anlage bleiben Vorgabe; ins Lager kommt nur, was eingetragen oder gelernt ist.
    archiv.lager_setzen(prefix, {k: v for k, v in neu.items() if k in eigen or k not in vorgabe_})
