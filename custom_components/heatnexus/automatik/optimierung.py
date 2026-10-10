"""Optimierungshinweise in der Laufzeit: Tage archivieren, Kurvenparameter lesen, auswerten.

Gelesen wird nur; an die Steuerung geht nichts. Archiv und Parameterverlauf liegen im
Speicher der Automatik und hängen nicht an der Aufzeichnung von Home Assistant.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
import logging
import math
from typing import Any

from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from . import optimierer, regel

_LOGGER = logging.getLogger(__name__)
ARCHIV_TAGE = 150
# Heizkurve, Behaglichkeit, Vorhaltezeit, Raumsollwert und die eigene Anpassung der Steuerung.
PARAMETER = ("/3/1/0", "/3/12/0", "/3/13/0", "/3/7/0", "/3/58/0", "/3/6/0", "/3/51/0", "/3/101/0")
LESEZEIT = {"hour": 0, "minute": 40, "second": 0}


def _schluessel(adresse: str) -> str:
    """`/3/13/0` → `3/13`, wie der Optimierer die Parameter nennt."""
    return adresse.strip("/").rsplit("/", 1)[0]


def _parameterwert(roh: Any) -> float | str | None:
    """Zahlen als Zahl, damit `80` und `80.0` als derselbe Wert gelten; sonst der Text."""
    if roh is None:
        return None
    try:
        zahl = float(roh)
    except (TypeError, ValueError):
        return str(roh)
    return zahl if math.isfinite(zahl) else str(roh)


def _parameter_laden(roh: Any) -> dict[str, list[list[Any]]]:
    if not isinstance(roh, dict):
        return {}
    verlauf = {}
    for name, eintraege in roh.items():
        if isinstance(eintraege, list):
            gueltig = [list(e) for e in eintraege if isinstance(e, list | tuple) and len(e) == 2]
            if gueltig:
                verlauf[str(name)] = gueltig
    return verlauf


class OptimierungMixin:
    """Teil der `Laufzeit`: Grundlage der Optimierungshinweise sammeln und auswerten."""

    tage_archiv: list[dict[str, Any]]
    parameter_verlauf: dict[str, list[list[Any]]]
    parameter_gelesen: str | None

    def _optimierung_laden(self, z: dict[str, Any]) -> None:
        archiv = z.get("tage_archiv")
        archiv = archiv if isinstance(archiv, list) else []
        self.tage_archiv = [t for t in archiv if isinstance(t, dict)][-ARCHIV_TAGE:]
        self.parameter_verlauf = _parameter_laden(z.get("parameter_verlauf"))
        gelesen = z.get("parameter_gelesen")
        self.parameter_gelesen = gelesen if isinstance(gelesen, str) else None
        self._parameteraufgabe: Any = None

    def optimierung_als_dict(self) -> dict[str, Any]:
        return {
            "tage_archiv": self.tage_archiv,
            "parameter_verlauf": self.parameter_verlauf,
            "parameter_gelesen": self.parameter_gelesen,
        }

    # --- Tage ----------------------------------------------------------------
    def _tag_beginnen(self, heute: str) -> None:
        """Den Verlauf auf `heute` stellen; der abgeschlossene Tag geht vorher ins Archiv."""
        if self.verlauf["datum"] == heute:
            return
        self.tag_archivieren(self.verlauf)
        self.verlauf = {"datum": heute, "stunden": {}}

    def tag_archivieren(self, verlauf: dict[str, Any]) -> None:
        """Einen Tagesverlauf zusammenfassen und anhängen; derselbe Tag zählt einmal."""
        datum = verlauf.get("datum")
        if not datum or any(t.get("datum") == datum for t in self.tage_archiv):
            return
        if (tag := optimierer.tag_aus_stunden(datum, verlauf.get("stunden") or {})) is None:
            return
        self.tage_archiv = [*self.tage_archiv, asdict(tag)][-ARCHIV_TAGE:]

    def archivierte_tage(self) -> list[optimierer.Tag]:
        """Das Archiv als `Tag`; Einträge in fremdem Format entfallen."""
        tage = []
        for eintrag in self.tage_archiv:
            try:
                tage.append(optimierer.Tag(**eintrag))
            except TypeError:
                continue
        return tage

    def _stundenfelder(self) -> dict[str, Any]:
        """Abweichung, Raumsoll, Vorlauf-Soll und Betriebsart aus der letzten Lage.

        Eine Vorgabe des Nutzers und das Beobachten werden vermerkt; sie entscheiden, ob der Tag zählt.
        """
        if (lage := self.lage) is None:
            return {}
        soll = regel.soll_bezug(lage, self.gedaechtnis)
        genug = lage.raeume and lage.raeume_fehlen_seit is None
        ab = round(regel.abweichung(lage, soll), 2) if soll is not None and genug else None
        # Eine Restzeit ohne eigene Absenkung stammt vom Nutzer (Eco/Comfort an Steuerung oder App).
        eigen = regel.absenkung_laeuft(self.gedaechtnis, lage.jetzt)
        vorgabe = (self._wert("/2/10/0") or 0) > 0 and not eigen
        felder = {
            "ab": ab,
            "soll": lage.soll,
            "vl": lage.vl_soll,
            "ba": lage.betriebsart,
            "vorgabe": vorgabe or None,
            "beobachtet": self.beobachten or None,
        }
        return {name: wert for name, wert in felder.items() if wert is not None}

    # --- Parameter -----------------------------------------------------------
    def _optimierung_starten(self) -> None:
        """Täglich lesen; beim Start sofort, wenn heute noch nichts gelesen wurde."""
        self._abmelden.append(async_track_time_change(self.hass, self._parameter_takt, **LESEZEIT))
        if self.parameter_gelesen != dt_util.now().date().isoformat():
            self._parameter_anstossen()

    def _optimierung_beenden(self) -> None:
        if self._parameteraufgabe is not None and not self._parameteraufgabe.done():
            self._parameteraufgabe.cancel()
        self._parameteraufgabe = None

    def _parameter_anstossen(self) -> None:
        if self._parameteraufgabe is not None and not self._parameteraufgabe.done():
            return
        self._parameteraufgabe = self.hass.async_create_background_task(
            self.parameter_lesen(), f"heatnexus_parameter_{self.device_id}"
        )

    async def _parameter_takt(self, _jetzt: datetime) -> None:
        self._parameter_anstossen()

    async def parameter_lesen(self) -> None:
        """Die Kurvenparameter lesen; ein Eintrag entsteht nur, wo sich der Wert geändert hat."""
        heute = dt_util.now().date().isoformat()
        oids = {f"{self.prefix}{adresse}": _schluessel(adresse) for adresse in PARAMETER}
        try:
            gelesen = await self.coordinator.client.fetch_oids(list(oids))
        except Exception as fehler:  # die Hinweise sind eine Zugabe; der Betrieb läuft weiter
            _LOGGER.debug("Automatik %s: Parameter nicht lesbar: %s", self.name, fehler)
            return
        if not gelesen:
            return
        for oid, name in oids.items():
            if (wert := _parameterwert(gelesen.get(oid))) is None:
                continue
            verlauf = self.parameter_verlauf.setdefault(name, [])
            if not verlauf or verlauf[-1][1] != wert:
                verlauf.append([heute, wert])
        self.parameter_gelesen = heute
        self._speichern()

    # --- Auswertung ----------------------------------------------------------
    def hinweise_liste(self, heute: date | str) -> list[optimierer.Hinweis]:
        return optimierer.hinweise(self.archivierte_tage(), self.parameter_verlauf, heute)

    def hinweise_stand(self, heute: date | str) -> dict[str, Any] | None:
        """Die Kachel „Hinweise“; ohne eingeschalteten Schalter `None`."""
        if not self.werte.hinweise:
            return None
        tage = self.archivierte_tage()
        eintraege = optimierer.hinweise(tage, self.parameter_verlauf, heute)
        grundlage = optimierer.grundlage(tage, self.parameter_verlauf, heute)
        return {
            "status": "bereit" if eintraege else "sammelt",
            "tage": len(grundlage),
            "noetig": optimierer.MIN_TAGE,
            "eintraege": [asdict(h) for h in eintraege],
        }
