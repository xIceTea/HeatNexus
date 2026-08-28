"""Wärmequellen, die nicht an der Windhager-Steuerung hängen.

Sie stehen in den Optionen, nicht im Abzug der Anlage: Ein Heizstab meldet
der Steuerung nichts. Je Quelle entsteht ein eigenes Gerät; wann sie Wärme
liefert, entscheidet `bedingung`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from . import bedingung
from .const import DOMAIN, QUELLEN_ARTEN, QUELLEN_MAX, SUBEINTRAG_QUELLE
from .entity import steuerung_kennung

TYP = SUBEINTRAG_QUELLE


def quelle_id(vorhandene: list[dict[str, Any]]) -> str:
    """Eine Kennung, die es noch nicht gibt.

    Sie hängt an der Entität und darf sich nie wiederholen; beim Entfernen
    einer Quelle rücken die übrigen deshalb nicht nach.
    """
    genommen = {str(q.get("id") or "") for q in vorhandene}
    nummer = 1
    while f"q{nummer}" in genommen:
        nummer += 1
    return f"q{nummer}"


def quellen_pruefen(roh: Any) -> list[dict[str, Any]]:
    """Gespeicherte Wärmequellen auf ihre Form bringen.

    Eine Quelle ohne Kennung, Namen oder auswertbare Bedingung fällt weg —
    sonst entstünde eine Entität, die nie etwas anderes als Nein sagen kann.
    """
    ergebnis: list[dict[str, Any]] = []
    for eintrag in roh if isinstance(roh, list) else []:
        if not isinstance(eintrag, Mapping):
            continue
        kennung = str(eintrag.get("id") or "").strip()
        name = str(eintrag.get("name") or "").strip()
        art = eintrag.get("art")
        regel = eintrag.get("bedingung")
        if not kennung or not name or art not in QUELLEN_ARTEN:
            continue
        if not isinstance(regel, Mapping) or not bedingung.vollstaendig(dict(regel)):
            continue
        ergebnis.append(
            {
                "id": kennung,
                "name": name,
                "art": art,
                "pumpe": bool(eintrag.get("pumpe")),
                "bedingung": bedingung_pruefen(regel),
            }
        )
    return ergebnis[:QUELLEN_MAX]


def bedingung_pruefen(roh: Mapping[str, Any]) -> dict[str, Any]:
    """Nur die Felder übernehmen, die zu dieser Bedingungsart gehören.

    Ein Wechsel der Art lässt sonst die Grenzen der vorigen stehen, und die
    Auswertung liest sie weiter.
    """
    regel: dict[str, Any] = {"art": roh["art"], "quelle": str(roh["quelle"])}
    if regel["art"] == bedingung.ART_ZUSTAND:
        if zustaende := roh.get("zustaende"):
            regel["zustaende"] = [str(z) for z in zustaende]
        return regel
    if regel["art"] == bedingung.ART_DIFFERENZ and (gegen := roh.get("gegen")):
        regel["gegen"] = str(gegen)
    for grenze in ("ein", "aus"):
        try:
            regel[grenze] = float(roh[grenze])
        except (KeyError, TypeError, ValueError):
            continue
    return regel


def subeintraege(entry: ConfigEntry) -> list[Any]:
    """Die Subeinträge, die eine Wärmequelle beschreiben."""
    return [s for s in (entry.subentries or {}).values() if s.subentry_type == TYP]


def der_anlage(entry: ConfigEntry, host: str) -> list[dict[str, Any]]:
    """Die Wärmequellen einer Anlage aus ihren Subeinträgen."""
    quellen = []
    for sub in subeintraege(entry):
        daten = sub.data or {}
        if daten.get("host") != host or daten.get("art") not in QUELLEN_ARTEN:
            continue
        if not daten.get("id"):
            continue
        quellen.append(
            {
                "id": daten["id"],
                "name": sub.title,
                "art": daten["art"],
                "pumpe": bool(daten.get("pumpe")),
                "bedingung": dict(daten.get("bedingung") or {}),
                "subentry_id": sub.subentry_id,
            }
        )
    return quellen


def geraete_entflechten(registry: Any, entry: ConfigEntry) -> int:
    """Geräte der Quellen vom Haupteintrag lösen.

    Eine Quelle gehört ihrem Subeintrag. Hängt ihr Gerät zusätzlich am
    Haupteintrag, steht es zweimal in der Übersicht der Integration.
    """
    kennungen = {sub.subentry_id for sub in subeintraege(entry)}
    geloest = 0
    for geraet in dr.async_entries_for_config_entry(registry, entry.entry_id):
        zuordnung = geraet.config_entries_subentries.get(entry.entry_id) or set()
        if None not in zuordnung or not zuordnung & kennungen:
            continue
        registry.async_update_device(
            geraet.id,
            remove_config_entry_id=entry.entry_id,
            remove_config_subentry_id=None,
        )
        geloest += 1
    return geloest


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
            "pumpe": bool(q.get("pumpe")),
            "bedingung": dict(q.get("bedingung") or {}),
            "subentry_id": q.get("subentry_id"),
        }
        for q in der_anlage(entry, getattr(coordinator, "host", "") or "")
    ]


def kennungen(entry: ConfigEntry, coordinators: dict) -> set[str]:
    """Alle Entitätskennungen, die aus Quellen entstehen."""
    return {
        b["id"] for coordinator in coordinators.values() for b in beschreibungen(entry, coordinator)
    }
