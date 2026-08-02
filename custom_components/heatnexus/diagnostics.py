"""Diagnosedaten für einen Konfigurationseintrag."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# Zugangsdaten und eindeutige Gerätekennungen bleiben draußen.
ZU_SCHWAERZEN = {"password", "host", "neuronId", "programId"}

# IPv4-Adresse als ganzer Wert bzw. irgendwo im Text.
_ADRESSE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_ADRESSE_IM_TEXT = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Alles zusammentragen, was zur Fehlersuche nützlich ist.

    Der Export landet in Fehlerberichten – oft ungelesen weitergereicht.
    Deshalb steht hier keine Adresse und keine Seriennummer: Die Anlagen
    werden durchnummeriert, und die Seriennummer, die in jeder Kennung
    steckt, wird durch einen gleichbleibenden Platzhalter ersetzt. Wer zwei
    Anlagen vergleicht, kann sie weiterhin auseinanderhalten.
    """
    eintrag = hass.data[DOMAIN][entry.entry_id]
    anlagen = {}
    for nummer, coordinator in enumerate(eintrag["coordinators"].values(), start=1):
        anlagen[f"anlage_{nummer}"] = _anlage(coordinator)

    optionen = async_redact_data(dict(entry.options), ZU_SCHWAERZEN)
    # Die Optionen sind je Anlage unter deren Adresse abgelegt.
    optionen = {
        (schluessel if not _ist_adresse(schluessel) else "anlage"): wert
        for schluessel, wert in optionen.items()
    }
    daten = {
        "eintrag": {
            "name": eintrag["name"],
            "version": entry.version,
            "optionen": optionen,
            "anlagen": len(anlagen),
        },
        "anlagen": async_redact_data(anlagen, ZU_SCHWAERZEN),
    }
    return _anonymisieren(daten, _seriennummern(eintrag))


def _ist_adresse(wert: Any) -> bool:
    """Sieht der Schlüssel nach einer IP-Adresse aus."""
    return isinstance(wert, str) and bool(_ADRESSE.match(wert))


def _seriennummern(eintrag: dict[str, Any]) -> dict[str, str]:
    """Seriennummer -> Platzhalter, je Anlage durchnummeriert."""
    ersatz: dict[str, str] = {}
    for nummer, coordinator in enumerate(eintrag.get("coordinators", {}).values(), start=1):
        for lfd, seriennummer in enumerate(
            sorted(getattr(coordinator.client, "neuron_by_node", {}).values()), start=1
        ):
            ersatz.setdefault(str(seriennummer), f"SN{nummer}-{lfd}")
    return ersatz


def _anonymisieren(wert: Any, ersatz: dict[str, str]) -> Any:
    """Seriennummern und Adressen in allen Zeichenketten ersetzen.

    Auch in zusammengesetzten Kennungen wie ``12345678-0-7-0``.
    """
    if isinstance(wert, dict):
        return {
            _anonymisieren(schluessel, ersatz): _anonymisieren(inhalt, ersatz)
            for schluessel, inhalt in wert.items()
        }
    if isinstance(wert, list):
        return [_anonymisieren(eintrag, ersatz) for eintrag in wert]
    if isinstance(wert, str):
        for seriennummer, platzhalter in ersatz.items():
            wert = wert.replace(seriennummer, platzhalter)
        return _ADRESSE_IM_TEXT.sub("<adresse>", wert)
    return wert


def _geraete(beschreibungen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Die Anlagenteile einer Anlage, jedes einmal, mit Zahl der Datenpunkte."""
    je_geraet: dict[str, dict[str, Any]] = {}
    for beschreibung in beschreibungen:
        kennung = beschreibung.get("device_id")
        if not kennung:
            continue
        eintrag = je_geraet.setdefault(
            kennung,
            {
                "praefix": kennung,
                "name": beschreibung.get("device_name"),
                "fct_type": beschreibung.get("fct_type"),
                "entitaeten": 0,
            },
        )
        eintrag["entitaeten"] += 1
    return list(je_geraet.values())


def _anlage(coordinator) -> dict[str, Any]:
    """Kennzahlen und Daten einer einzelnen Anlage."""
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
        "bezeichnung": coordinator.label,
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
        # Ohne diese Zahlen ist jede Aussage über das Abrufverhalten geschätzt.
        "abrufverhalten": client.statistik() if hasattr(client, "statistik") else {},
        "entitaeten_nach_typ": dict(sorted(nach_typ.items())),
        "entitaeten_nach_ebene": dict(sorted(nach_ebene.items())),
        # Je Gerät eine Zeile, nicht je Datenpunkt: Sonst füllten die ersten
        # zwanzig Beschreibungen desselben Geräts die ganze Liste, und man sah
        # zwanzigmal "ZSP-PTS" statt der vier Anlagenteile.
        "geraete": async_redact_data(_geraete(beschreibungen), ZU_SCHWAERZEN),
        "meldungen": daten.get("status", {}),
        "beschreibungen": async_redact_data(beschreibungen, ZU_SCHWAERZEN),
        "werte": daten.get("oids", {}),
    }
