"""Abgaswächter im Takt des Befunds: ruhigen Betrieb erkennen, Tagessummen fortschreiben."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..helpers import get_oid_value
from . import abgas
from .abgasziele import AbgasZiel, ziele
from .auswertung import Abgasgeraet
from .pflegelauf import geraetename

ABGAS, KESSEL, LEISTUNG, PHASE, O2 = "/0/11/0", "/0/7/0", "/0/9/0", "/2/1/0", "/0/42/0"
BRENNSTOFF_PUROWIN = "/38/127/0"


def ziele_von(coordinator: Any) -> list[AbgasZiel]:
    """Die Kessel mit Abgaswächter aus Beschreibungen und Geräteklassen der Erkennung."""
    beschreibungen = (coordinator.data or {}).get("devices") or []
    klassen = getattr(getattr(coordinator, "client", None), "geraeteklasse", None) or {}
    return ziele(beschreibungen, klassen)


def mit_o2(coordinator: Any, prefix: str) -> bool:
    """Ob die Erkennung am Kessel ein O2-Signal fand; ohne Sonde gibt es keinen Verlust."""
    oid = f"{prefix}{O2}"
    return any(b.get("oid") == oid for b in (coordinator.data or {}).get("devices") or [])


def messen(
    coordinator: Any,
    archiv: Any,
    zustaende: dict[str, dict[str, Any]],
    zeit: datetime,
    raumluft: float | None = None,
) -> dict[str, dict[str, Any]]:
    """Je Kessel einen Takt bewerten; liefert die neuen Laufzustände, gültige Takte gehen ins Archiv."""
    neu: dict[str, dict[str, Any]] = {}
    for z in ziele_von(coordinator):

        def wert(adresse: str, z: AbgasZiel = z) -> float | None:
            return get_oid_value(coordinator, adresse, z.prefix)

        leistung = None if z.logwin else wert(LEISTUNG)
        messung = abgas.Messung(wert(ABGAS), wert(KESSEL), leistung, wert(PHASE), wert(O2))
        neu[z.prefix], stufe = abgas.bewerten(zustaende.get(z.prefix, {}), messung, zeit, z.logwin)
        if stufe is None or messung.abgas is None or messung.kessel is None:
            continue
        dt = messung.abgas - messung.kessel
        tage = abgas.sammeln(
            archiv.abgas_tage(z.prefix),
            zeit.date().isoformat(),
            stufe,
            dt,
            messung.o2,
            messung.abgas,
            raumluft,
        )
        archiv.abgas_setzen(z.prefix, tage)
    return neu


def geraete(coordinator: Any, archiv: Any) -> list[Abgasgeraet]:
    """Je Kessel mit Abgaswächter, was die Auswertung braucht; der Bezug folgt der letzten Reinigung."""
    liste = []
    for z in ziele_von(coordinator):
        code = (
            get_oid_value(coordinator, BRENNSTOFF_PUROWIN, z.prefix) if z.fct_type == 25 else None
        )
        liste.append(
            Abgasgeraet(
                kennung=z.device_id,
                name=geraetename(coordinator, z.device_id),
                prefix=z.prefix,
                logwin=z.logwin,
                brennstoff=abgas.brennstoff(z.fct_type, code),
                bezug_ab=archiv.pflege_eintrag(z.prefix, z.bezug_art).get("zuletzt"),
                mit_o2=mit_o2(coordinator, z.prefix),
            )
        )
    return liste


def arten(coordinator: Any) -> list[tuple[str, str, tuple[str, ...]]]:
    """Je Kessel Kennung, Gerät und Arten der Befund-Sensoren, wie `geraete_der_anlage` sie führt."""
    return [
        (
            z.device_id,
            z.device_id,
            ("abgas", "abgasverlust") if mit_o2(coordinator, z.prefix) else ("abgas",),
        )
        for z in ziele_von(coordinator)
    ]
