"""Reparaturabläufe für die Hinweise, die HeatNexus setzt."""

from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from . import karteileichen


class KarteileichenFlow(RepairsFlow):
    """Fragt nach, bevor Entitäten ohne Datenpunkt gelöscht werden."""

    def __init__(self, entry_id: str) -> None:
        self._entry_id = entry_id

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        from . import laufzeitdaten

        eintrag = self.hass.config_entries.async_get_entry(self._entry_id)
        daten = laufzeitdaten(eintrag) if eintrag else None
        koordinatoren = (daten or {}).get("coordinators") or {}
        if eintrag is None or not koordinatoren:
            # Der Eintrag ist nicht geladen; ohne Bestand ist nicht zu
            # entscheiden, was fehlt.
            return self.async_abort(reason="nicht_geladen")

        if user_input is not None:
            karteileichen.entfernen(self.hass, eintrag, koordinatoren)
            return self.async_create_entry(title="", data={})

        anzahl = len(karteileichen.finden(self.hass, eintrag, koordinatoren))
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"anzahl": str(anzahl)},
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None
) -> RepairsFlow:
    """Den Ablauf zu einem Hinweis erzeugen."""
    entry_id = str((data or {}).get("entry_id", ""))
    return KarteileichenFlow(entry_id)
