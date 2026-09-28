"""Wetterprognose, Sonne und Wärmequellen mit Vorrang: die Quellen der Automatik.

Teil der Laufzeit; als Mixin, damit die Methoden an derselben Klasse hängen.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

from . import eingaben, korrektur


def ortszeit(wert: Any) -> datetime | None:
    """ISO-Text als Ortszeit; Unlesbares ergibt nichts."""
    if not wert:
        return None
    zeit = dt_util.parse_datetime(str(wert))
    return dt_util.as_local(zeit) if zeit else None


class QuellenMixin:
    """Prognose holen und merken, Sonnenquote, Vorrangquellen."""

    def tagesmittel(self, tag: date) -> float | None:
        """Tagesmittel der Prognose, um den gelernten Versatz verschoben."""
        if (mittel := eingaben.tagesmittel(self._tage, tag)) is None:
            return None
        if not self.werte.anpassen:
            return mittel
        versatz = self.temperatur.tagesversatz(self.werte.lernfenster, dt_util.now().date())
        return mittel + (versatz or 0.0)

    def _prognose_des_tages_merken(self, stunden: list[dict[str, Any]]) -> None:
        # Die Stundenprognose beginnt mit der laufenden Stunde; Vergangenes hält der Verlauf.
        heute = dt_util.now().date()
        if self.verlauf["datum"] != heute.isoformat():
            self.verlauf = {"datum": heute.isoformat(), "stunden": {}}
        for eintrag in stunden:
            zeit = ortszeit(eintrag.get("datetime"))
            if zeit is None or zeit.date() != heute:
                continue
            stunde = self.verlauf["stunden"].setdefault(str(zeit.hour), {})
            stunde["prognose"] = eintrag.get("temperature")
            stunde["wolken"] = eintrag.get("cloud_coverage")

    def stundenprognose(self, tag: date) -> dict[int, dict[str, float | None]]:
        """Stundenprognose eines Tages: roh, korrigiert, Bewölkung."""
        fenster, heute = self.werte.lernfenster, dt_util.now().date()
        roh_je_stunde: dict[int, tuple[Any, Any]] = {}
        if self.verlauf["datum"] == tag.isoformat():
            for stunde, werte in self.verlauf["stunden"].items():
                if "prognose" in werte:
                    roh_je_stunde[int(stunde)] = (werte.get("prognose"), werte.get("wolken"))
        for eintrag in self.stunden:
            zeit = ortszeit(eintrag.get("datetime"))
            if zeit is not None and zeit.date() == tag:
                roh_je_stunde[zeit.hour] = (
                    eintrag.get("temperature"),
                    eintrag.get("cloud_coverage"),
                )
        ergebnis: dict[int, dict[str, float | None]] = {}
        for stunde, (roh, wolken) in roh_je_stunde.items():
            versatz = (
                self.temperatur.versatz(stunde, fenster, heute) if self.werte.anpassen else None
            )
            ergebnis[stunde] = {
                "roh": roh,
                "korrigiert": None if roh is None else round(roh + (versatz or 0.0), 1),
                "wolken": wolken,
            }
        return ergebnis

    def sonne(self, tag: date) -> tuple[datetime | None, datetime | None]:
        """Sonnenauf- und -untergang des Tages in Ortszeit."""
        aufgang = get_astral_event_date(self.hass, "sunrise", tag)
        untergang = get_astral_event_date(self.hass, "sunset", tag)
        return (
            dt_util.as_local(aufgang) if aufgang else None,
            dt_util.as_local(untergang) if untergang else None,
        )

    def _pv_tag_merken(self, jetzt: datetime) -> None:
        """Die PV-Prognose des Tages als Maßstab für spätere Tage ablegen."""
        if (pv := self.zahl(self.konfig.get("pv"))) is None:
            return
        heute = jetzt.date().isoformat()
        self.pv_tage[heute] = max(pv, self.pv_tage.get(heute, 0.0))
        grenze = (jetzt.date() - timedelta(days=korrektur.PV_TAGE)).isoformat()
        self.pv_tage = {tag: wert for tag, wert in self.pv_tage.items() if tag > grenze}

    def sonnenquote(self, tag: date, pv_sensor: str | None) -> float | None:
        """Sonnenquote eines Tages; Betrieb und Vorschau rechnen sie gleich."""
        heute = dt_util.now().date()
        if self.konfig.get("pv_ist") and self.werte.anpassen:
            quote = korrektur.sonnenquote_korrigiert(
                self.kwh(pv_sensor),
                self.pv.faktor(self.werte.lernfenster, heute),
                self.pv.bester_ist(heute),
            )
            if quote is not None:
                return quote
        bisher = [wert for datum, wert in self.pv_tage.items() if datum != heute.isoformat()]
        if (quote := eingaben.sonnenquote_aus_pv(self.zahl(pv_sensor), bisher)) is not None:
            return quote
        aufgang, untergang = self.sonne(tag)
        if aufgang is None or untergang is None:
            return None
        return self.quote_aus_bewoelkung(tag, aufgang, untergang)

    def quote_aus_bewoelkung(
        self, tag: date, aufgang: datetime, untergang: datetime
    ) -> float | None:
        # Aus allen Stunden des Tages, auch den schon vergangenen aus dem Verlauf.
        stunden = [
            (aufgang.replace(hour=stunde, minute=0, second=0, microsecond=0), werte["wolken"])
            for stunde, werte in self.stundenprognose(tag).items()
        ]
        return eingaben.sonnenquote_aus_bewoelkung(stunden, aufgang, untergang)

    def _lieferbeginn(self) -> None:
        """Einmal am Tag sofort entscheiden, statt bis zur nächsten Entscheidungszeit zu warten."""
        heute = dt_util.now().date()
        if self._lieferbeginn_am == heute:
            return
        self._lieferbeginn_am = heute
        # Vorgemerkt: Läuft gerade eine Auswertung, holt der nächste Lauf die Entscheidung nach.
        self._entscheidung_offen = True
        self._geaendert = True
        self.hass.async_create_task(self.auswerten())

    def _vorrang_liefert(self) -> list[str]:
        return [
            kennung
            for kennung in self.konfig["vorrang"]
            if (zustand := self.hass.states.get(kennung)) is not None and zustand.state == "on"
        ]

    def _vorrang_fortschreiben(self, jetzt: datetime) -> None:
        if not self.konfig["vorrang"]:
            return
        liefert = bool(self._vorrang_liefert())
        self.vorrang = eingaben.lauf_fortschreiben(self.vorrang, jetzt, liefert)
        if liefert:
            self.stunde_nachtragen(jetzt.hour, vorrang=True)

    def _vorrang_lage(self, jetzt: datetime) -> dict[str, Any]:
        if not self.konfig["vorrang"]:
            return {}
        liefert = self._vorrang_liefert()
        return {
            "vorrang_laeuft": bool(liefert),
            "vorrang_minuten": eingaben.lauf_minuten(self.vorrang, jetzt),
            "vorrang_name": self._quellenname(liefert[0]) if liefert else None,
        }

    def _quellenname(self, entity_id: str) -> str:
        """Name des Geräts der Quelle; der Entitätsname allein heißt nur „Wärmelieferung“."""
        eintrag = er.async_get(self.hass).async_get(entity_id)
        geraet = (
            dr.async_get(self.hass).async_get(eintrag.device_id)
            if eintrag and eintrag.device_id
            else None
        )
        if geraet is not None and (name := geraet.name_by_user or geraet.name):
            return name
        zustand = self.hass.states.get(entity_id)
        return str(zustand.attributes.get("friendly_name") or entity_id) if zustand else entity_id

    async def _prognose(self, art: str) -> list[dict[str, Any]] | None:
        return await self._prognose_quelle(self.konfig["wetter"], art)

    async def _prognose_holen(self) -> None:
        stunden = await self._prognose("hourly")
        tage = await self._prognose("daily")
        if stunden is not None:
            self.stunden = stunden
            self._prognose_des_tages_merken(stunden)
            self.temperatur.vormerken(
                [
                    (zeit, eintrag.get("temperature"))
                    for eintrag in stunden
                    if (zeit := ortszeit(eintrag.get("datetime"))) is not None
                ],
                dt_util.now(),
            )
        if tage is not None:
            self._tage = [
                (zeit.date(), eintrag.get("temperature"), eintrag.get("templow"))
                for eintrag in tage
                if (zeit := ortszeit(eintrag.get("datetime"))) is not None
            ]
        if stunden is not None or tage is not None:
            self._prognose_zeit = dt_util.now()
