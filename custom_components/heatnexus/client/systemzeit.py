"""Uhr der Steuerung (`WsAdmin/systemtime`): lesen und mit Home Assistant vergleichen."""

from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

PFAD = "/WsAdmin/api/1.0/systemtime"


def _zeit(roh) -> datetime | None:
    try:
        return datetime.fromisoformat(str(roh).strip())
    except (TypeError, ValueError):
        return None


class SystemzeitMixin:
    """Uhrzeit der Steuerung, im langsamen Takt gelesen."""

    systemzeit_vorhanden: bool | None = None
    _systemzeit: dict | None = None

    async def _systemzeit_lesen(self) -> dict | None:
        """Uhrzeit und Abweichung zu Home Assistant in Sekunden; `None` ohne Uhr an der Steuerung."""
        if self.systemzeit_vorhanden is False:
            return None
        try:
            daten, status = await self._get(f"http://{self.host}{PFAD}")
        except Exception as fehler:
            _LOGGER.debug("Uhrzeit von %s nicht lesbar: %s", self.host, fehler)
            return self._systemzeit
        if status in (404, 503) and not self.systemzeit_vorhanden:
            self.systemzeit_vorhanden = False
            return None
        zeit = _zeit(daten.get("dateTime")) if status == 200 and isinstance(daten, dict) else None
        if zeit is None:
            return self._systemzeit
        self.systemzeit_vorhanden = True
        # Die Steuerung führt Ortszeit ohne Zone; verglichen wird in der Zeitzone von Home Assistant.
        ortszeit = zeit.replace(tzinfo=dt_util.get_default_time_zone())
        self._systemzeit = {
            "uhrzeit": ortszeit.isoformat(),
            "abweichung": round((ortszeit - dt_util.now()).total_seconds()),
        }
        return self._systemzeit
