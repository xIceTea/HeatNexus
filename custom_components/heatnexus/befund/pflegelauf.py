"""Pflege im Takt des Befunds: Restwerte fortschreiben, Abschnitte bauen, aus der Statistik nachholen."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from ..helpers import get_oid_value
from . import pflege
from .auswertung import Pflegegeraet
from .pflegeziele import Ziel, ziele

Statistik = Callable[[set[str]], Awaitable[dict[str, list[dict[str, Any]]]]]


def pflegeziele_von(coordinator: Any) -> list[Ziel]:
    """Die Pflegeziele einer Anlage aus Beschreibungen und Geräteklassen der Erkennung."""
    beschreibungen = (coordinator.data or {}).get("devices") or []
    klassen = getattr(getattr(coordinator, "client", None), "geraeteklasse", None) or {}
    return ziele(beschreibungen, klassen)


def messen(coordinator: Any, archiv: Any, heute: date) -> None:
    """Je Zählerpflege den Restwert fortschreiben; Kalenderpflege kennt nur die Eingabe."""
    for z in pflegeziele_von(coordinator):
        if z.pflege.adresse is None:
            continue
        rest = get_oid_value(coordinator, z.pflege.adresse, z.prefix)
        alt = archiv.pflege_eintrag(z.prefix, z.pflege.art)
        neu = pflege.fortschreiben(alt, rest, heute, z.max_feld, z.pflege)
        archiv.pflege_setzen(z.prefix, z.pflege.art, neu)


def _geraetename(coordinator: Any, device_id: str) -> str:
    for b in (coordinator.data or {}).get("devices") or []:
        if b.get("device_id") == device_id and b.get("device_name"):
            return str(b["device_name"])
    return device_id


def geraete(coordinator: Any) -> list[Pflegegeraet]:
    """Je Gerät mit Pflege seine Ziele, für die Abschnitte der Auswertung."""
    je_geraet: dict[str, list[Ziel]] = {}
    for z in pflegeziele_von(coordinator):
        je_geraet.setdefault(z.device_id, []).append(z)
    return [Pflegegeraet(d, _geraetename(coordinator, d), zs) for d, zs in je_geraet.items()]


def kennungen(coordinator: Any) -> dict[str, str]:
    """Kennung → Domäne aller Pflege-Entitäten; ohne sie gälten sie als verwaist."""
    gefunden: dict[str, str] = {}
    for z in pflegeziele_von(coordinator):
        basis = f"{z.device_id}-pflege-{z.pflege.art}"
        gefunden[f"{z.device_id}-befund-pflege-{z.pflege.art}"] = "sensor"
        gefunden[f"{basis}-zuletzt"] = "date"
        if z.pflege.weise == pflege.KALENDER:
            gefunden[f"{basis}-erledigt"] = "button"
    return gefunden


def _wert(zeile: dict[str, Any]) -> Any:
    return zeile.get("mean") if zeile.get("mean") is not None else zeile.get("state")


async def nachrechnen(
    coordinator: Any,
    archiv: Any,
    entitaet_von: Callable[[str, str], str | None],
    holen: Statistik,
    stunde_von: Callable[[dict[str, Any]], str],
) -> int:
    """Den Tag der letzten Erledigung aus der Langzeitstatistik, wo noch keiner bekannt ist."""
    offen = [
        (z, e)
        for z in pflegeziele_von(coordinator)
        if z.pflege.adresse and not archiv.pflege_eintrag(z.prefix, z.pflege.art).get("zuletzt")
        if (e := entitaet_von(z.device_id, z.pflege.adresse))
    ]
    statistik = await holen({e for _, e in offen}) if offen else {}
    gefunden = 0
    for z, entity_id in offen:
        reihe = [(stunde_von(zeile), _wert(zeile)) for zeile in statistik.get(entity_id, [])]
        if tag := pflege.letzte_erledigung(reihe, z.pflege, z.max_feld):
            eintrag = archiv.pflege_eintrag(z.prefix, z.pflege.art) | {"zuletzt": tag}
            archiv.pflege_setzen(z.prefix, z.pflege.art, eintrag)
            gefunden += 1
    return gefunden
