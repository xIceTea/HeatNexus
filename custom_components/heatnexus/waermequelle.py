"""Wärmequellen, die nicht an der Windhager-Steuerung hängen.

Sie stehen in den Optionen, nicht im Abzug der Anlage: Ein Heizstab meldet
der Steuerung nichts. Je Quelle entsteht ein eigenes Gerät; wann sie Wärme
liefert, entscheidet `bedingung`.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_QUELLEN, DOMAIN, QUELLEN_ARTEN
from .entity import steuerung_kennung

TYP = "waermequelle"


def der_anlage(entry: ConfigEntry, host: str) -> list[dict[str, Any]]:
    """Die Wärmequellen einer Anlage aus den Optionen."""
    je_anlage = (entry.options or {}).get(host) or {}
    return [
        q
        for q in je_anlage.get(CONF_QUELLEN, [])
        if isinstance(q, dict) and q.get("id") and q.get("art") in QUELLEN_ARTEN
    ]


def kennung(coordinator: Any, quelle: dict[str, Any]) -> str:
    """Entitätskennung einer Quelle.

    Sie hängt an der Steuerung, nicht an der Adresse, und übersteht damit
    einen Wechsel der IP-Adresse.
    """
    return f"{steuerung_kennung(coordinator)}-{TYP}-{quelle['id']}"


def geraet_info(coordinator: Any, beschreibung: dict[str, Any]) -> DeviceInfo:
    """Gerätezuordnung: die Quelle als Teil unter ihrer Steuerung."""
    steuerung = (getattr(coordinator, "label", "") or "").strip()
    art = beschreibung.get("art")
    name = beschreibung.get("name") or QUELLEN_ARTEN.get(art, TYP)
    return DeviceInfo(
        identifiers={(DOMAIN, beschreibung["id"])},
        name=f"{steuerung} · {name}" if steuerung else name,
        model=QUELLEN_ARTEN.get(art, art),
        via_device=(DOMAIN, steuerung_kennung(coordinator)),
    )


def beschreibungen(entry: ConfigEntry, coordinator: Any) -> list[dict[str, Any]]:
    """Was aus den Quellen einer Anlage an Entitäten entsteht."""
    return [
        {
            "id": kennung(coordinator, q),
            "type": TYP,
            "name": q.get("name"),
            "art": q["art"],
            "bedingung": dict(q.get("bedingung") or {}),
        }
        for q in der_anlage(entry, getattr(coordinator, "host", "") or "")
    ]


def kennungen(entry: ConfigEntry, coordinators: dict) -> set[str]:
    """Alle Entitätskennungen, die aus Quellen entstehen."""
    return {
        b["id"] for coordinator in coordinators.values() for b in beschreibungen(entry, coordinator)
    }
