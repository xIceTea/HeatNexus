"""Steuerungen eines Eintrags nachträglich hinzufügen und entfernen.

Eine Steuerung ist eine Adresse mit ihren Geräten; an ihr hängen die Automatiken
ihrer Heizkreise und ihre Wärmequellen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from . import waermequelle
from .automatik.verwaltung import verwaltung_holen
from .const import (
    CONF_MARKEN,
    CONF_MARKEN_STATUS,
    CONF_SYSTEMS,
    CONF_ZUSATZWERTE,
    DISCOVERY_STORE_VERSION,
    DOMAIN,
)
from .entity import steuerung_kennung
from .erkennungsstand import store_key
from .registrierung import geraet_suchen

# Hängen an einer bestimmten Anlage und gehen nicht auf eine neue über.
EIGENE_OPTIONEN = (CONF_MARKEN, CONF_MARKEN_STATUS, CONF_ZUSATZWERTE)


@dataclass(frozen=True)
class Folgen:
    """Was beim Entfernen einer Steuerung mitgeht."""

    geraete: int = 0
    automatiken: list[str] = field(default_factory=list)
    quellen: list[str] = field(default_factory=list)


def kennung_des_eintrags(systeme: list[dict[str, Any]]) -> str:
    """Kennung des Eintrags aus den Seriennummern seiner Steuerungen; ohne sie zählt die Adresse."""
    return "-".join(sorted(s.get("kennung") or s["host"] for s in systeme))


def mit_kennung(entry: ConfigEntry, systeme: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Die Steuerungen mit Seriennummer; fehlt sie in den Daten, kommt sie vom laufenden Abruf."""
    koordinatoren = _koordinatoren(entry)
    ergebnis = []
    for system in systeme:
        client = getattr(koordinatoren.get(system["host"]), "client", None)
        neuronen = getattr(client, "neuron_by_node", None) or {}
        if not system.get("kennung") and neuronen:
            system = {**system, "kennung": min(str(n) for n in neuronen.values())}
        ergebnis.append(dict(system))
    return ergebnis


def optionen_fuer_neue(entry: ConfigEntry) -> dict[str, Any]:
    """Der Umfang der ersten Steuerung als Vorgabe für eine neue, ohne Labels und Einzelwerte."""
    systeme = entry.data.get(CONF_SYSTEMS, [])
    vorbild = entry.options.get(systeme[0]["host"], {}) if systeme else {}
    return {k: v for k, v in vorbild.items() if k not in EIGENE_OPTIONEN}


def hinzufuegen(hass: HomeAssistant, entry: ConfigEntry, neu: dict[str, Any]) -> None:
    """Die Steuerung anhängen; das Update des Eintrags lädt ihn neu und liest sie ein."""
    systeme = [*mit_kennung(entry, entry.data.get(CONF_SYSTEMS, [])), neu]
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_SYSTEMS: systeme},
        options={**entry.options, neu["host"]: optionen_fuer_neue(entry)},
        unique_id=kennung_des_eintrags(systeme),
    )


def geraete_der_steuerung(hass: HomeAssistant, entry: ConfigEntry, host: str) -> list[Any]:
    """Alle Geräte unterhalb der Steuerung, das Steuerungsgerät zuletzt."""
    koordinator = _koordinatoren(entry).get(host)
    if koordinator is None:
        return []
    register = dr.async_get(hass)
    wurzel = geraet_suchen(register, steuerung_kennung(koordinator), entry.entry_id)
    if wurzel is None:
        return []
    eigene = dr.async_entries_for_config_entry(register, entry.entry_id)
    darunter: list[Any] = []
    offen = [wurzel.id]
    while offen:
        eltern = offen.pop()
        kinder = [g for g in eigene if g.via_device_id == eltern]
        darunter.extend(kinder)
        offen.extend(g.id for g in kinder)
    return [*darunter, wurzel]


def folgen(hass: HomeAssistant, entry: ConfigEntry, host: str) -> Folgen:
    """Geräte, Automatiken und Wärmequellen, die mit der Steuerung gehen."""
    geraete = geraete_der_steuerung(hass, entry, host)
    namen = _namen(geraete)
    kreise = _automatik_kreise(hass, entry, set(namen))
    return Folgen(
        geraete=len(geraete),
        automatiken=sorted(namen[k] for k in kreise),
        quellen=sorted(q["name"] for q in waermequelle.der_anlage(entry, host)),
    )


async def entfernen(hass: HomeAssistant, entry: ConfigEntry, host: str) -> None:
    """Die Steuerung mit allem entfernen, was an ihr hängt; das Neuladen löst das Update aus."""
    geraete = geraete_der_steuerung(hass, entry, host)
    verwaltung = verwaltung_holen(hass)
    for kreis in _automatik_kreise(hass, entry, set(_namen(geraete))):
        await verwaltung.entfernen(kreis)
    for quelle in waermequelle.der_anlage(entry, host):
        hass.config_entries.async_remove_subentry(entry, quelle["subentry_id"])
    register, entitaeten = dr.async_get(hass), er.async_get(hass)
    for geraet in geraete:
        # Automatik und Wärmequelle haben ihre Geräte schon selbst entfernt.
        if register.async_get(geraet.id) is None:
            continue
        for eintrag in er.async_entries_for_device(
            entitaeten, geraet.id, include_disabled_entities=True
        ):
            entitaeten.async_remove(eintrag.entity_id)
        register.async_remove_device(geraet.id)
    await Store(hass, DISCOVERY_STORE_VERSION, store_key(entry, host)).async_remove()
    systeme = [s for s in mit_kennung(entry, entry.data.get(CONF_SYSTEMS, [])) if s["host"] != host]
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_SYSTEMS: systeme},
        options={k: v for k, v in entry.options.items() if k != host},
        unique_id=kennung_des_eintrags(systeme),
    )


def _koordinatoren(entry: ConfigEntry) -> dict[str, Any]:
    daten = getattr(entry, "runtime_data", None)
    return (daten.get("coordinators") if isinstance(daten, dict) else None) or {}


def _namen(geraete: list[Any]) -> dict[str, str]:
    return {
        wert: geraet.name_by_user or geraet.name or wert
        for geraet in geraete
        for bereich, wert in geraet.identifiers
        if bereich == DOMAIN
    }


def _automatik_kreise(hass: HomeAssistant, entry: ConfigEntry, kennungen: set[str]) -> list[str]:
    return [k for k in verwaltung_holen(hass).eingerichtet(entry.entry_id) if k in kennungen]
