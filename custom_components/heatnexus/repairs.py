"""Reparaturabläufe für die Hinweise, die HeatNexus setzt."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from . import laufzeitdaten, verwaiste

_LOGGER = logging.getLogger(__name__)


class VerwaisteFlow(RepairsFlow):
    """Fragt nach, bevor Entitäten ohne Datenpunkt gelöscht werden."""

    def __init__(self, entry_id: str) -> None:
        self._entry_id = entry_id

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        eintrag = self.hass.config_entries.async_get_entry(self._entry_id)
        daten = laufzeitdaten(eintrag) if eintrag else None
        koordinatoren = (daten or {}).get("coordinators") or {}
        if not koordinatoren:
            # Ohne geladene Anlage steht nicht fest, welche Datenpunkte es
            # gibt – und damit auch nicht, was fehlt.
            return self.async_abort(reason="nicht_geladen")

        if user_input is not None:
            verwaiste.entfernen(self.hass, eintrag, koordinatoren)
            return self.async_create_entry(title="", data={})

        anzahl = len(verwaiste.finden(self.hass, eintrag, koordinatoren))
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"anzahl": str(anzahl)},
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None
) -> RepairsFlow:
    """Den Ablauf zu einem Hinweis erzeugen.

    Die Kennung entscheidet, welcher Ablauf startet: Ein zweiter Hinweis darf
    nicht in diesem hier landen und Entitäten löschen.
    """
    if not issue_id.startswith(verwaiste.SCHLUESSEL):
        raise ValueError(f"Kein Reparaturablauf für {issue_id}")
    entry_id = str((data or {}).get("entry_id", ""))
    if not entry_id:
        _LOGGER.warning("Hinweis %s ohne Zuordnung zu einer Anlage", issue_id)
    return VerwaisteFlow(entry_id)
