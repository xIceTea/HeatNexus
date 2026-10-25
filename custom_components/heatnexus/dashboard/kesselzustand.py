"""Sonderzustände des Kessels und die Erreichbarkeit der Steuerung, für Übersicht und Kopfzeile."""

from __future__ import annotations

from typing import Any

from ..device_db import get_enum

BETRIEBSART = "2/59"
BETRIEBSWAHL = "9/75"
PHASE = "2/1"
# Betriebsart eines Anlagenteils (Heizkreis, Puffer): reicht als Bezug für die Erreichbarkeit.
BETRIEBSART_ANLAGENTEIL = "2/9"
SERVICEAUSBRAND = 6

OFFLINE = ("Steuerung nicht erreichbar", "mdi:lan-disconnect")
# Reihenfolge = Vorrang. `True`/`False`: nur mit bzw. ohne Serviceausbrand in `9/75`; Text `None`: Text der Anlage.
REGELN: tuple[tuple[tuple[int, ...], bool | None, str | None, str], ...] = (
    ((1,), True, "Serviceausbrand läuft", "mdi:fire-off"),
    ((0,), True, "Kessel aus nach Serviceausbrand", "mdi:fire-off"),
    ((9,), None, "Kaminkehrer aktiv", "mdi:account-hard-hat"),
    ((14, 15), None, "Lagerraum befüllen", "mdi:warehouse"),
    ((8, 10, 11, 13, 16), None, None, "mdi:wrench"),
    ((1,), False, "Kessel schaltet ab", "mdi:power"),
    ((0,), False, "Kessel ausgeschaltet", "mdi:power-off"),
)
PHASEN_GESPERRT = ((0, 9), "mdi:lock-outline")
TEXTE = (OFFLINE[0], *(text for *_, text, _ in REGELN if text))


def _finden(teil: dict[str, Any], adresse: str) -> dict | None:
    return next(
        (e for e in teil["entitaeten"] if e.get("adresse") == adresse and e["bereich"] == "sensor"),
        None,
    )


def _texte(eintrag: dict[str, Any] | None, adresse: str, werte: tuple[int, ...]) -> list[str]:
    """Die Zustandstexte zu den Werten: aus der Entität, sonst aus der Werttabelle; ohne Doppel."""
    optionen = (eintrag or {}).get("optionen") or get_enum(adresse) or {}
    texte = (optionen.get(w) or optionen.get(str(w)) for w in werte)
    return list(dict.fromkeys(t for t in texte if t))


def _regeln(art: dict, wahl: dict | None, phase: dict | None) -> list[dict[str, Any]]:
    regeln = [
        {
            "quelle": "betriebsart",
            "wenn": wenn,
            "serviceausbrand": service,
            "text": text,
            "symbol": symbol,
        }
        for werte, service, text, symbol in REGELN
        if (service is not True or wahl) and (wenn := _texte(art, BETRIEBSART, werte))
    ]
    werte, symbol = PHASEN_GESPERRT
    if phase and (wenn := _texte(phase, PHASE, werte)):
        regeln.append(
            {
                "quelle": "phase",
                "wenn": wenn,
                "serviceausbrand": None,
                "text": None,
                "symbol": symbol,
            }
        )
    return regeln


def kesselzustand(anlage: dict[str, Any]) -> dict[str, Any] | None:
    """Was den Zustand im Kopf bestimmt: der erste Kessel, sonst nur die Erreichbarkeit."""
    kessel = next((t for t in anlage["teile"] if _finden(t, BETRIEBSART)), None)
    art = _finden(kessel, BETRIEBSART) if kessel else None
    wahl = _finden(kessel, BETRIEBSWAHL) if kessel else None
    phase = _finden(kessel, PHASE) if kessel else None
    bezug = art or next(
        (e for t in anlage["teile"] if (e := _finden(t, BETRIEBSART_ANLAGENTEIL))), None
    )
    if bezug is None:
        return None
    return {
        "bezug": bezug["entity_id"],
        "betriebsart": art["entity_id"] if art else None,
        "betriebswahl": wahl["entity_id"] if wahl else None,
        "phase": phase["entity_id"] if phase else None,
        "serviceausbrand": _texte(wahl, BETRIEBSWAHL, (SERVICEAUSBRAND,)) if wahl else [],
        "offline": {"text": OFFLINE[0], "symbol": OFFLINE[1]},
        "regeln": _regeln(art, wahl, phase) if art else [],
    }
