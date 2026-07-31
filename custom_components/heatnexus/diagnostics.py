"""Diagnosedaten für einen Konfigurationseintrag."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# Zugangsdaten und eindeutige Gerätekennungen bleiben draußen.
ZU_SCHWAERZEN = {"password", "host", "neuronId", "programId"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Alles zusammentragen, was zur Fehlersuche nützlich ist."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    client = coordinator.client
    daten = coordinator.data or {}

    beschreibungen = daten.get("devices", [])
    nach_typ: dict[str, int] = {}
    nach_ebene: dict[str, int] = {}
    for beschreibung in beschreibungen:
        typ = beschreibung.get("type", "unbekannt")
        nach_typ[typ] = nach_typ.get(typ, 0) + 1
        ebene = beschreibung.get("level", "kuratiert")
        nach_ebene[ebene] = nach_ebene.get(ebene, 0) + 1

    return {
        "eintrag": {
            "version": entry.version,
            "optionen": dict(entry.options),
        },
        "anlage": {
            "vollstaendig_eingelesen": getattr(client, "_vollstaendig", None),
            "datenpunkte": len(client.oids or []),
            "entitaeten": len(beschreibungen),
            "zyklisch_abgefragt": len(client.poll_oids),
            "zusaetzlich_angemeldet": len(client._dynamic_oids),
            "zeitprogramme": len(client.time_programs),
            "objekt_endpunkt": client._objects_supported,
            "anfragen_seit_start": client.request_count,
            "bedienebenen": client.levels,
            "fachparameter_aktiv": client.enable_advanced,
            "fachparameter_bedienbar": client.writable_advanced,
        },
        "entitaeten_nach_typ": dict(sorted(nach_typ.items())),
        "entitaeten_nach_ebene": dict(sorted(nach_ebene.items())),
        "geraete": async_redact_data(
            [
                {
                    "praefix": b.get("device_id"),
                    "name": b.get("device_name"),
                }
                for b in beschreibungen
                if b.get("device_id")
            ][:20],
            ZU_SCHWAERZEN,
        ),
        "meldungen": daten.get("status", {}),
        "beschreibungen": async_redact_data(beschreibungen, ZU_SCHWAERZEN),
        "werte": daten.get("oids", {}),
    }
