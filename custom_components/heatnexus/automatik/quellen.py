"""Wetterprognose, Sonne und Wärmequellen mit Vorrang: die Quellen der Automatik.

Teil der Laufzeit; als Mixin, damit die Methoden an derselben Klasse hängen.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.core import State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from . import eingaben, korrektur, regel

# Bits von `WeatherEntityFeature`: welche Vorhersagearten eine Wetter-Entität liefert.
VORHERSAGEARTEN = {"daily": 1, "hourly": 2, "twice_daily": 4}
# So lange darf die Vorhersage fehlen, bevor eine Reparaturmeldung erscheint.
PROGNOSE_MELDEN = timedelta(hours=3)
SONNENZEITEN_MAX = 8  # Tage, die `sonne` je Heizkreis vorhält


def vorhersagearten(zustand: State | None) -> set[str] | None:
    """Die Vorhersagearten der Entität; ohne Angabe unbekannt (`None`)."""
    merkmale = zustand.attributes.get("supported_features") if zustand else None
    if not isinstance(merkmale, int) or isinstance(merkmale, bool):
        return None
    return {art for art, bit in VORHERSAGEARTEN.items() if merkmale & bit}


def tageswerte(
    eintraege: list[dict[str, Any]], halbtage: bool = False
) -> list[tuple[date, float | None, float | None]]:
    """Höchst- und Tiefstwert je Tag; Halbtage (`twice_daily`) fasst sie je Ortsdatum zusammen."""
    if not halbtage:
        return [
            (
                zeit.date(),
                eingaben.zahl(eintrag.get("temperature")),
                eingaben.zahl(eintrag.get("templow")),
            )
            for eintrag in eintraege
            if (zeit := ortszeit(eintrag.get("datetime"))) is not None
        ]
    je_tag: dict[date, list[float]] = {}
    for eintrag in eintraege:
        if (zeit := ortszeit(eintrag.get("datetime"))) is None:
            continue
        werte = (eingaben.zahl(eintrag.get(feld)) for feld in ("temperature", "templow"))
        je_tag.setdefault(zeit.date(), []).extend(w for w in werte if w is not None)
    return [(tag, max(werte), min(werte)) for tag, werte in je_tag.items() if werte]


def ortszeit(wert: Any) -> datetime | None:
    """ISO-Text als Ortszeit; Unlesbares ergibt nichts."""
    if not wert:
        return None
    zeit = dt_util.parse_datetime(str(wert))
    return dt_util.as_local(zeit) if zeit else None


class QuellenMixin:
    """Prognose holen und merken, Sonnenquote, Vorrangquellen."""

    _sonnenzeiten: dict[date, tuple[datetime | None, datetime | None]]

    def tagesmittel(self, tag: date, heute: date | None = None) -> float | None:
        """Tagesmittel der Prognose, um den gelernten Versatz verschoben."""
        if (mittel := eingaben.tagesmittel(self._tage, tag)) is None:
            return None
        if not self.werte.anpassen:
            return mittel
        versatz = self.temperatur.tagesversatz(
            self.werte.lernfenster, heute or dt_util.now().date()
        )
        return mittel + (versatz or 0.0)

    def _prognose_des_tages_merken(self, stunden: list[dict[str, Any]]) -> None:
        # Die Stundenprognose beginnt mit der laufenden Stunde; Vergangenes hält der Verlauf.
        heute = dt_util.now().date()
        self._tag_beginnen(heute.isoformat())
        for eintrag in stunden:
            zeit = ortszeit(eintrag.get("datetime"))
            if zeit is None or zeit.date() != heute:
                continue
            stunde = self.verlauf["stunden"].setdefault(str(zeit.hour), {})
            stunde["prognose"] = eintrag.get("temperature")
            stunde["wolken"] = eintrag.get("cloud_coverage")
            stunde["wind"] = eintrag.get("wind_speed")

    def stundenprognose(
        self, tag: date, heute: date | None = None
    ) -> dict[int, dict[str, float | None]]:
        """Stundenprognose eines Tages: roh, korrigiert, Bewölkung, Wind."""
        fenster, heute = self.werte.lernfenster, heute or dt_util.now().date()
        roh_je_stunde: dict[int, tuple[Any, Any, Any]] = {}
        if self.verlauf["datum"] == tag.isoformat():
            for stunde, werte in self.verlauf["stunden"].items():
                if "prognose" in werte:
                    roh_je_stunde[int(stunde)] = (
                        werte.get("prognose"),
                        werte.get("wolken"),
                        werte.get("wind"),
                    )
        for eintrag in self.stunden:
            zeit = ortszeit(eintrag.get("datetime"))
            if zeit is not None and zeit.date() == tag:
                roh_je_stunde[zeit.hour] = (
                    eintrag.get("temperature"),
                    eintrag.get("cloud_coverage"),
                    eintrag.get("wind_speed"),
                )
        ergebnis: dict[int, dict[str, float | None]] = {}
        for stunde, (roh, wolken, wind) in roh_je_stunde.items():
            versatz = (
                self.temperatur.versatz(stunde, fenster, heute) if self.werte.anpassen else None
            )
            ergebnis[stunde] = {
                "roh": roh,
                "korrigiert": None if roh is None else round(roh + (versatz or 0.0), 1),
                "wolken": wolken,
                "wind": wind,
            }
        return ergebnis

    def sonne(self, tag: date) -> tuple[datetime | None, datetime | None]:
        """Sonnenauf- und -untergang des Tages in Ortszeit."""
        if (bekannt := self._sonnenzeiten.get(tag)) is not None:
            return bekannt
        aufgang = get_astral_event_date(self.hass, "sunrise", tag)
        untergang = get_astral_event_date(self.hass, "sunset", tag)
        zeiten = (
            dt_util.as_local(aufgang) if aufgang else None,
            dt_util.as_local(untergang) if untergang else None,
        )
        if len(self._sonnenzeiten) >= SONNENZEITEN_MAX:
            self._sonnenzeiten.clear()
        self._sonnenzeiten[tag] = zeiten
        return zeiten

    def _pv_tag_merken(self, jetzt: datetime) -> None:
        """Die PV-Prognose des Tages als Maßstab für spätere Tage ablegen."""
        if (pv := self.zahl(self.konfig.get("pv"))) is None:
            return
        heute = jetzt.date().isoformat()
        self.pv_tage[heute] = max(pv, self.pv_tage.get(heute, 0.0))
        grenze = (jetzt.date() - timedelta(days=korrektur.PV_TAGE)).isoformat()
        self.pv_tage = {tag: wert for tag, wert in self.pv_tage.items() if tag > grenze}

    def sonnenquote(
        self,
        tag: date,
        pv_sensor: str | None,
        heute: date | None = None,
        ab: datetime | None = None,
    ) -> float | None:
        """Sonnenquote eines Tages; Betrieb und Vorschau rechnen sie gleich.

        `ab` beschränkt die Bewölkung auf die restlichen Stunden; PV-Prognosen gelten je Tag.
        """
        heute = heute or dt_util.now().date()
        breite = self.hass.config.latitude
        if self.konfig.get("pv_ist") and self.werte.anpassen:
            quote = korrektur.sonnenquote_korrigiert(
                self.kwh(pv_sensor),
                self.pv.faktor(self.werte.lernfenster, heute),
                self.pv.bester_ist(heute, breite, tag),
            )
            if quote is not None:
                return quote
        bisher = korrektur.auf_heute(
            {datum: wert for datum, wert in self.pv_tage.items() if datum != heute.isoformat()},
            tag,
            breite,
        )
        if (quote := eingaben.sonnenquote_aus_pv(self.zahl(pv_sensor), bisher)) is not None:
            return quote
        aufgang, untergang = self.sonne(tag)
        if aufgang is None or untergang is None:
            return None
        return self.quote_aus_bewoelkung(tag, aufgang, untergang, ab)

    def quote_aus_bewoelkung(
        self, tag: date, aufgang: datetime, untergang: datetime, ab: datetime | None = None
    ) -> float | None:
        # Aus den Stunden des Tages, mit `ab` nur aus denen, die noch kommen.
        stunden = [
            (aufgang.replace(hour=stunde, minute=0, second=0, microsecond=0), werte["wolken"])
            for stunde, werte in self.stundenprognose(tag).items()
        ]
        return eingaben.sonnenquote_aus_bewoelkung(stunden, aufgang, untergang, ab)

    def _lieferbeginn(self) -> None:
        """Einmal am Tag sofort entscheiden, statt bis zur nächsten Entscheidungszeit zu warten."""
        heute = dt_util.now().date()
        if self._lieferbeginn_am == heute:
            return
        self._lieferbeginn_am = heute
        self._geaendert = True
        self._aufgabe(self.auswerten(entscheidungszeit=True))

    def vorrang_liefert(self) -> list[str]:
        """Die gewählten Vorrangquellen, die gerade liefern."""
        return [
            kennung
            for kennung in self.konfig["vorrang"]
            if (zustand := self.hass.states.get(kennung)) is not None and zustand.state == "on"
        ]

    def _vorrang_fortschreiben(self, jetzt: datetime) -> None:
        if not self.konfig["vorrang"]:
            return
        liefert = bool(self.vorrang_liefert())
        self.vorrang = eingaben.lauf_fortschreiben(self.vorrang, jetzt, liefert)
        # Die Minuten des Tages bleiben einige Tage stehen; daraus folgen die Vorrangtage.
        self.vorrang_verlauf[self.vorrang.datum] = eingaben.lauf_minuten(self.vorrang, jetzt)
        grenze = (jetzt.date() - timedelta(days=4)).isoformat()
        self.vorrang_verlauf = {t: m for t, m in self.vorrang_verlauf.items() if t >= grenze}
        if liefert:
            self.stunde_nachtragen(jetzt.hour, vorrang=True)

    def _vorrang_lage(self, jetzt: datetime) -> dict[str, Any]:
        if not self.konfig["vorrang"]:
            return {}
        liefert = self.vorrang_liefert()
        return {
            "vorrang_laeuft": bool(liefert),
            "vorrang_minuten": eingaben.lauf_minuten(self.vorrang, jetzt),
            "vorrang_name": self._quellenname(liefert[0]) if liefert else None,
            "vorrang_tage": eingaben.vorrang_tage(
                self.vorrang_verlauf, jetzt.date(), regel.VORRANG_MIN_MINUTEN
            ),
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
        return self._anzeigename(entity_id)

    def _anzeigename(self, entity_id: str) -> str:
        zustand = self.hass.states.get(entity_id)
        return str(zustand.attributes.get("friendly_name") or entity_id) if zustand else entity_id

    async def _prognose(self, art: str) -> list[dict[str, Any]] | None:
        return await self._prognose_quelle(self.konfig["wetter"], art)

    async def _prognose_holen(self) -> None:
        """Stunden und Tage holen, nur was die Entität kann; ohne Tage gelten Halbtage.

        Nennt die Entität keine Art, wird trotzdem gefragt: Ihr Fehler gehört in Protokoll und Diagnose.
        """
        arten = vorhersagearten(self.hass.states.get(self.konfig["wetter"])) or None
        stunden = await self._prognose("hourly") if arten is None or "hourly" in arten else None
        tage, halbtage = None, False
        if arten is None or "daily" in arten:
            tage = await self._prognose("daily")
        elif "twice_daily" in arten:
            tage, halbtage = await self._prognose("twice_daily"), True
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
            self._tage = tageswerte(tage, halbtage)
        if stunden is not None or tage is not None:
            self._prognose_zeit = dt_util.now()
        self._prognose_melden()

    def _prognose_melden(self) -> None:
        """Fehlt die Vorhersage länger als `PROGNOSE_MELDEN`, eine Reparaturmeldung; sonst keine."""
        # Eine ausgeschaltete Automatik braucht keine Vorhersage.
        if self.prognose_frisch or not self.aktiv:
            self._prognose_fehlt_seit = None
            ir.async_delete_issue(self.hass, DOMAIN, self.prognose_kennung)
            return
        jetzt = dt_util.now()
        self._prognose_fehlt_seit = self._prognose_fehlt_seit or jetzt
        if jetzt - self._prognose_fehlt_seit >= PROGNOSE_MELDEN:
            self._meldung(
                self.prognose_kennung,
                "automatik_prognose",
                ir.IssueSeverity.WARNING,
                wetter=self._anzeigename(self.konfig["wetter"]),
            )

    @property
    def prognose_kennung(self) -> str:
        """Kennung der Reparaturmeldung „keine Wettervorhersage“."""
        return f"automatik_prognose_{self.device_id}"

    def wetter_stand(
        self, fehler: Mapping[tuple[str, str], tuple[datetime, str]]
    ) -> dict[str, Any]:
        """Wetter-Entität, ihre Vorhersagearten und die letzten Fehler aus `fehler`; für die Diagnose."""
        wetter = self.konfig["wetter"]
        zustand = self.hass.states.get(wetter)
        eintrag = er.async_get(self.hass).async_get(wetter)
        arten = vorhersagearten(zustand)
        return {
            "entitaet": wetter,
            "zustand": zustand.state if zustand else None,
            "plattform": eintrag.platform if eintrag else None,
            "arten": sorted(arten) if arten is not None else None,
            "fehler": [
                {"art": art, "zeit": zeit, "text": text}
                for (entitaet, art), (zeit, text) in sorted(fehler.items())
                if entitaet == wetter
            ],
        }
