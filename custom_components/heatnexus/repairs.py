"""Reparaturabläufe für die Hinweise, die HeatNexus setzt."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

from . import verwaiste
from .const import DOMAIN
from .erkennungsstand import laufzeitdaten

_LOGGER = logging.getLogger(__name__)

# Hinweise, deren Kennung auf `<präfix>_<entry_id>_<adresse>` endet.
ADRESSHINWEISE = (
    "nicht_erreichbar",
    "sprache_neustart",
    "stumme_teile",
    "zirkulation_ohne_ein",
)


def adresshinweise_entfernen(hass: HomeAssistant, entry_id: str, host: str = "") -> None:
    """Die Hinweise einer Adresse des Eintrags löschen; ohne Adresse die aller Adressen."""
    anfaenge = tuple(f"{praefix}_{entry_id}_" for praefix in ADRESSHINWEISE)
    for domaene, kennung in list(ir.async_get(hass).issues):
        if domaene != DOMAIN or not kennung.startswith(anfaenge):
            continue
        if not host or kennung in {anfang + host for anfang in anfaenge}:
            ir.async_delete_issue(hass, DOMAIN, kennung)


class VerwaisteFlow(RepairsFlow):
    """Fragt nach, ob Entitäten ohne Datenpunkt gelöscht oder behalten werden."""

    def __init__(self, entry_id: str) -> None:
        self._entry_id = entry_id
        self._gezeigt: set[str] = set()

    def _bestand(self) -> tuple[ConfigEntry, dict] | None:
        """Eintrag und Koordinatoren; None, solange die Anlage nicht geladen ist."""
        eintrag = self.hass.config_entries.async_get_entry(self._entry_id)
        daten = laufzeitdaten(eintrag) if eintrag else None
        koordinatoren = (daten or {}).get("coordinators") or {}
        return (eintrag, koordinatoren) if koordinatoren else None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if (bestand := self._bestand()) is None:
            # Ohne geladene Anlage steht nicht fest, welche Datenpunkte es
            # gibt – und damit auch nicht, was fehlt.
            return self.async_abort(reason="nicht_geladen")
        eintrag, koordinatoren = bestand
        gefunden = verwaiste.finden(self.hass, eintrag, koordinatoren)
        if not gefunden:
            # Der Hinweis zählte vor einem späteren Abruf; inzwischen fehlt nichts mehr.
            verwaiste.hinweis_pflegen(self.hass, eintrag, 0)
            return self.async_abort(reason="nichts_verwaist")
        self._gezeigt = {e.entity_id for e in gefunden}
        # Die Beschriftung steht übersetzt zwischen den beiden Platzhaltern; das HTML kommt von hier.
        return self.async_show_menu(
            step_id="confirm",
            menu_options=["loeschen", "behalten"],
            description_placeholders={
                "anzahl": str(len(gefunden)),
                "liste_anfang": "<details><summary>",
                "liste_ende": f"</summary>\n\n{verwaiste.liste(gefunden)}\n\n</details>",
            },
        )

    async def async_step_loeschen(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if (bestand := self._bestand()) is None:
            return self.async_abort(reason="nicht_geladen")
        verwaiste.entfernen(self.hass, *bestand)
        return self.async_create_entry(title="", data={})

    async def async_step_behalten(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if (bestand := self._bestand()) is None:
            return self.async_abort(reason="nicht_geladen")
        eintrag, koordinatoren = bestand
        # Nur, was der Dialog gezeigt hat und noch immer fehlt.
        gefunden = verwaiste.finden(self.hass, eintrag, koordinatoren)
        verwaiste.merken(self.hass, [e for e in gefunden if e.entity_id in self._gezeigt])
        return self.async_create_entry(title="", data={})


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
