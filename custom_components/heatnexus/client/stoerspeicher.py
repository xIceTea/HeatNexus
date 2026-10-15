"""Störspeicher des Bediengeräts: lesen, quittieren, zurücksetzen, löschen.

Das Bediengerät führt die Liste selbst (`InfoWinFehlerlog`); jede Meldung
eines Geräts wird dort ein Eintrag, bis sie gelöscht wird. Die Regeln, wann
ein Eintrag zurückgesetzt, quittiert oder gelöscht werden darf, folgen der
Oberfläche des Bediengeräts.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.util import dt as dt_util

from ..exceptions import WindhagerWriteError, mit_text

_LOGGER = logging.getLogger(__name__)

PFAD = "/InfoWinFehlerlog/api/1.0/fehlerlog"
PARTNER_PFAD = "/InfoWinHeartbeat/api/1.0/heartbeat"
# Ohne neue Meldung gilt ein Eintrag nach dieser Zeit als nicht mehr anliegend.
AKTIV_HOECHSTENS = timedelta(minutes=7)
# Kesselknoten; deren Meldungen bearbeitet nur das Bediengerät, das mit dem
# Kessel gekoppelt ist.
KESSELKNOTEN = range(55, 81)
# Nach so vielen Abrufen fragt eine Steuerung ohne Störspeicher erneut nach.
NEU_PRUEFEN_NACH = 120
_ZEIT = "%Y-%m-%d %H:%M:%S"


def _zeit(roh) -> datetime | None:
    try:
        return datetime.strptime(str(roh).strip(), _ZEIT)
    except (TypeError, ValueError):
        return None


def eintrag_aufbereiten(roh: dict, partner: dict | None, jetzt: datetime) -> dict | None:
    """Ein Eintrag der Steuerung mit den Regeln der Oberfläche.

    Zeiten bleiben in der Uhrzeit der Steuerung; `jetzt` muss dieselbe sein.
    """
    try:
        kennung = int(roh["id"])
        knoten = int(roh.get("nodeId"))
    except (KeyError, TypeError, ValueError):
        return None
    zuletzt = _zeit(roh.get("lastRxTime"))
    aktiv = bool(roh.get("active")) and (zuletzt is None or jetzt - zuletzt <= AKTIV_HOECHSTENS)
    subnetz = roh.get("subnet")
    partner = partner or {}
    bearbeitbar = knoten not in KESSELKNOTEN or (
        knoten == partner.get("peerId") and subnetz == partner.get("subnet")
    )
    status = str(roh.get("status") or "new")
    return {
        "id": kennung,
        "code": roh.get("code"),
        "symbol": roh.get("symbol"),
        "meldung": str(roh.get("FE01Msg") or "").strip(),
        "knoten": knoten,
        "subnetz": subnetz,
        "geraet": roh.get("nodeName"),
        "status": status,
        "aktiv": aktiv,
        "zuerst": roh.get("timestamp"),
        "zuletzt": roh.get("lastRxTime"),
        "zuruecksetzbar": bearbeitbar and aktiv,
        "quittierbar": status == "new",
        "loeschbar": not aktiv,
    }


class StoerspeicherMixin:
    """Zugriff auf den Störspeicher des Bediengeräts."""

    # None: noch nicht gefragt; False: Die Steuerung führt keinen.
    stoerspeicher_vorhanden: bool | None = None
    _stoerspeicher: list[dict] | None = None
    _stoerspeicher_partner: dict | None = None
    _stoerspeicher_tick: int = 0

    def _stoerspeicher_url(self, rest: str = "") -> str:
        return f"http://{self.host}{PFAD}{rest}"

    async def _stoerspeicher_partner_lesen(self) -> None:
        """Mit welchem Kessel das Bediengerät gekoppelt ist."""
        try:
            daten, status = await self._get(f"http://{self.host}{PARTNER_PFAD}")
        except Exception as fehler:
            _LOGGER.debug("Kopplung des Bediengeräts nicht lesbar: %s", fehler)
            return
        # Eine Antwort ohne Kopplung wird gemerkt; nur ein Fehlschlag fragt beim nächsten Abruf erneut.
        self._stoerspeicher_partner = daten if status == 200 and isinstance(daten, dict) else {}

    def _stoerspeicher_faellig(self) -> bool:
        if self.stoerspeicher_vorhanden is not False:
            return True
        self._stoerspeicher_tick += 1
        return self._stoerspeicher_tick % NEU_PRUEFEN_NACH == 0

    async def _fetch_stoerspeicher(self) -> list[dict] | None:
        """Die Einträge lesen; `None`, wenn die Steuerung keinen Störspeicher hat."""
        if not self._stoerspeicher_faellig():
            return None
        try:
            daten, status = await self._get(self._stoerspeicher_url())
        except Exception as fehler:
            _LOGGER.debug("Störspeicher nicht lesbar: %s", fehler)
            return self._stoerspeicher
        if status in (404, 503):
            if self.stoerspeicher_vorhanden:
                # Hat die Steuerung schon geantwortet, ist das ein Aussetzer, kein Fehlen.
                return self._stoerspeicher
            self.stoerspeicher_vorhanden = False
            self._stoerspeicher = None
            return None
        if status != 200 or not isinstance(daten, list):
            # Wie bei den Werten: Ein Fehlschlag lässt den letzten Stand stehen.
            return self._stoerspeicher
        if self._stoerspeicher_partner is None:
            await self._stoerspeicher_partner_lesen()
        self.stoerspeicher_vorhanden = True
        # Die Steuerung führt Ortszeit; Home Assistant kennt dieselbe Zeitzone.
        jetzt = dt_util.now().replace(tzinfo=None)
        eintraege = [
            e
            for roh in daten
            if isinstance(roh, dict)
            and (e := eintrag_aufbereiten(roh, self._stoerspeicher_partner, jetzt))
        ]
        self._stoerspeicher = sorted(eintraege, key=lambda e: e["id"], reverse=True)
        return self._stoerspeicher

    async def _stoerspeicher_senden(self, methode: str, rest: str) -> None:
        await self._ensure_session()
        async with (
            self._semaphore,
            self._session.request(methode, self._stoerspeicher_url(rest), data=b"") as ret,
        ):
            if ret.status >= 400:
                _LOGGER.debug(
                    "Störspeicher %s %s scheitert mit HTTP %s: %s",
                    methode,
                    rest,
                    ret.status,
                    await ret.text(),
                )
                raise mit_text(WindhagerWriteError, "stoerspeicher_abgelehnt", status=ret.status)

    async def stoerung_quittieren(self, kennung: int) -> None:
        """Als gelesen markieren; das schließt die Meldung am Bediengerät."""
        await self._stoerspeicher_senden("PUT", f"/{int(kennung)}?status=receipted")

    async def stoerung_zuruecksetzen(self, kennung: int) -> None:
        """Wie die Taste am Bediengerät: zurücksetzen, dann quittieren."""
        await self._stoerspeicher_senden("PUT", f"/reset/{int(kennung)}")
        try:
            await self.stoerung_quittieren(kennung)
        except WindhagerWriteError as fehler:
            # Zurückgesetzt ist die Störung schon; offen bleibt nur die Meldung am Bediengerät.
            _LOGGER.debug("Quittieren nach dem Zurücksetzen scheitert: %s", fehler)

    async def stoerung_loeschen(self, kennung: int) -> None:
        """Den Eintrag aus der Liste des Bediengeräts nehmen."""
        await self._stoerspeicher_senden("DELETE", f"/{int(kennung)}")
