"""Hausmodell in der Laufzeit: Lerndaten aus dem Verlauf, Modellpflege, Vorhersage."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
import logging
from typing import Any, NamedTuple

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from . import eingaben, hausmodell, nachladen, regel, tagesansicht, vorhersage, zeitprogramm

_LOGGER = logging.getLogger(__name__)
LERNTAGE = 14
# Der Verlauf des Vortags liegt nach Mitternacht vollständig vor.
LERNZEIT = {"hour": 0, "minute": 20, "second": 0}
Reihe = list[tuple[datetime, float | None]]
# Betriebswahl `3/50` → Zeitprogramm des Heizkreises.
ZEITPROGRAMME = {1: "/3/61/0", 2: "/3/62/0", 3: "/3/63/0"}
_STUFE_JE_ART = {regel.PAUSE: vorhersage.PAUSE, regel.SONNE: vorhersage.ABSENKUNG}
# Warum noch kein Modell besteht; der Reiter Automatik zeigt es unter „lernt noch“.
GRUND_DATEN = "daten"
GRUND_UNPASSEND = "unpassend"


class Reihen(NamedTuple):
    """Die Zeitreihen, aus denen die Lernstunden entstehen."""

    raeume: list[Reihe]
    at: Reihe
    heizen: Reihe
    wolken: Reihe
    wind: Reihe


def _schaltreihe(zustaende: list[Any]) -> Reihe:
    """Zeitreihe eines Schalters: ein 1, aus 0, sonst eine Lücke."""
    return [
        (dt_util.as_local(z.last_updated), {"on": 1.0, "off": 0.0}.get(z.state)) for z in zustaende
    ]


def _lernstunde(
    reihen: Reihen,
    art: str,
    raum: float | None,
    zeit: datetime,
    bogen: tuple[float, float] | None,
) -> hausmodell.Stunde | None:
    """Eine Stunde mit allen Werten; fehlt einer, entfällt sie."""
    at = eingaben.wert_zur_stunde(reihen.at, zeit)
    quelle = eingaben.wert_zur_stunde(reihen.heizen, zeit)
    if raum is None or at is None or quelle is None:
        return None
    wolken = eingaben.wert_zur_stunde(reihen.wolken, zeit)
    sonne = 0.0 if bogen is None else tagesansicht.sonnenanteil(zeit.hour, *bogen, wolken)
    heizen = quelle if art == "pumpe" else max(0.0, quelle - raum)
    wind = eingaben.wert_zur_stunde(reihen.wind, zeit)
    return hausmodell.Stunde(raum, None, at, sonne, wind, heizen)


def _kurvenwert(kurve: tuple[tuple[str, float], ...], jetzt: datetime) -> float | None:
    """Der erwartete Raumwert zur laufenden Stunde: der letzte Punkt der Kurve bis jetzt."""
    werte = [wert for zeit, wert in kurve if datetime.fromisoformat(zeit) <= jetzt]
    return werte[-1] if werte else None


def _lernzeiten(heute: date) -> list[datetime]:
    """Die vollen Stunden der Lerntage bis heute 00:00, diese Stunde als letzte."""
    anfang = dt_util.as_utc(dt_util.start_of_local_day(heute - timedelta(days=LERNTAGE)))
    ende = dt_util.as_utc(dt_util.start_of_local_day(heute))
    stunden = int((ende - anfang).total_seconds() // 3600)
    return [dt_util.as_local(anfang + timedelta(hours=i)) for i in range(stunden + 1)]


class VorausschauMixin:
    """Teil der `Laufzeit`: Hausmodell lernen, laden, verwerfen."""

    hausmodell: hausmodell.Modell | None

    def _hausmodell_laden(self, z: dict[str, Any]) -> None:
        self.hausmodell = hausmodell.aus_dict(z.get("hausmodell"))
        tag = z.get("hausmodell_tag")
        self._fehler_tag: str | None = tag if isinstance(tag, str) else None
        self._lernaufgabe: Any = None
        self.lern_grund: str | None = None
        self._vorhersage_zuletzt: vorhersage.Vorhersage | None = None
        # Die Vorhersage, mit der die laufende Stufe des Modells begann; an ihr misst sich die Rückkehr.
        self._vorhersage_bezug: vorhersage.Vorhersage | None = None

    @property
    def vorhersage_zuletzt(self) -> vorhersage.Vorhersage | None:
        """Die letzte Vorhersage, auch ohne Freigabe; für Anzeige und Diagnose."""
        return self._vorhersage_zuletzt

    def hausmodell_neu(self, sofort: bool = False) -> None:
        """Von vorn lernen, etwa nach geänderten Räumen; `sofort` startet den Lauf gleich."""
        self.hausmodell = None
        self._fehler_tag = None
        self._vorhersage_zuletzt = None
        self._vorhersage_bezug = None
        self._speichern()
        if sofort:
            self._lernen_anstossen()

    def _lernen_starten(self) -> None:
        """Einmal jetzt und danach täglich lernen."""
        self._lernen_beenden()
        self._lernen_anstossen()
        self._abmelden.append(async_track_time_change(self.hass, self._hausmodell_takt, **LERNZEIT))

    def _lernen_anstossen(self) -> None:
        """Als Aufgabe lernen, damit `stoppen` sie abbrechen kann; ein laufender Lauf genügt."""
        if self._lernaufgabe is not None and not self._lernaufgabe.done():
            return
        self._lernaufgabe = self.hass.async_create_background_task(
            self.hausmodell_lernen(), f"heatnexus_hausmodell_{self.device_id}"
        )

    def _lernen_beenden(self) -> None:
        if self._lernaufgabe is not None and not self._lernaufgabe.done():
            self._lernaufgabe.cancel()
        self._lernaufgabe = None

    async def _hausmodell_takt(self, _jetzt: datetime) -> None:
        self._lernen_anstossen()

    def _entitaet(self, adresse: str, plattform: str = "sensor") -> str | None:
        kennung = f"{self.device_id}-{adresse.strip('/').replace('/', '-')}"
        return er.async_get(self.hass).async_get_entity_id(plattform, DOMAIN, kennung)

    def _heizquellen(self) -> list[tuple[str, str]]:
        """Was die Heizleistung zeigt, in der Reihenfolge der Wahl: Vorlauf, dann Pumpe."""
        quellen = [
            ("vorlauf", self._entitaet("/0/2/0")),
            ("pumpe", self._entitaet("/1/20/0", "binary_sensor")),
        ]
        return [(art, entitaet) for art, entitaet in quellen if entitaet]

    async def _verlauf_lesen(
        self, mit_attributen: list[str], einfach: list[str], jetzt: datetime
    ) -> dict[str, list[Any]] | None:
        """Der Verlauf der Lerntage; ohne Aufzeichnung oder bei Fehler nichts."""
        if "recorder" not in self.hass.config.components:
            return None
        from homeassistant.components.recorder import get_instance, history

        anfang = dt_util.start_of_local_day(jetzt.date() - timedelta(days=LERNTAGE))

        def abfrage() -> dict[str, list[Any]]:
            zustaende: dict[str, list[Any]] = {}
            # Attribute nur dort lesen, wo sie gebraucht werden; sonst kostet der Join ohne Nutzen.
            for kennungen, ohne_attribute in ((mit_attributen, False), (einfach, True)):
                if kennungen:
                    zustaende |= history.get_significant_states(
                        self.hass,
                        anfang,
                        jetzt,
                        kennungen,
                        significant_changes_only=False,
                        no_attributes=ohne_attribute,
                    )
            return zustaende

        try:
            return await get_instance(self.hass).async_add_executor_job(abfrage)
        except Exception as fehler:  # die Aufzeichnung ist eine Zugabe, kein Muss
            _LOGGER.debug("Automatik %s: Lerndaten nicht lesbar: %s", self.name, fehler)
            return None

    def _sonnenboegen(self, tage: set[date]) -> dict[date, tuple[float, float]]:
        boegen = {}
        for tag in tage:
            aufgang, untergang = self.sonne(tag)
            if aufgang and untergang:
                boegen[tag] = (
                    aufgang.hour + aufgang.minute / 60,
                    untergang.hour + untergang.minute / 60,
                )
        return boegen

    def _je_tag(
        self, reihen: Reihen, art: str, zeiten: list[datetime]
    ) -> dict[date, list[hausmodell.Stunde]]:
        """Lernstunden je Tag; eine Stunde ohne Folgestunde bekommt kein `raum_danach`."""
        raum = [
            eingaben.raumwert(
                [eingaben.wert_zur_stunde(r, z) for r in reihen.raeume], self.konfig["raum_art"]
            )
            for z in zeiten
        ]
        boegen = self._sonnenboegen({z.date() for z in zeiten})
        ganz = [
            _lernstunde(reihen, art, r, z, boegen.get(z.date()))
            for z, r in zip(zeiten, raum, strict=True)
        ]
        ergebnis: dict[date, list[hausmodell.Stunde]] = {}
        for i, stunde in enumerate(ganz[:-1]):
            if stunde is not None:
                danach = raum[i + 1] if ganz[i + 1] is not None else None
                ergebnis.setdefault(zeiten[i].date(), []).append(
                    replace(stunde, raum_danach=danach)
                )
        return ergebnis

    def _reihen(self, zustaende: dict[str, list[Any]], art: str, heizer: str) -> Reihen:
        k, aussen = self.konfig, self.aussen_entitaet()
        wetter = zustaende.get(k["wetter"], [])
        heizen = zustaende.get(heizer, [])
        return Reihen(
            [nachladen.raumreihe(zustaende, r, luecken=True) for r in k["raeume"]],
            nachladen.zeitreihe(zustaende.get(aussen, []), luecken=True) if aussen else [],
            _schaltreihe(heizen) if art == "pumpe" else nachladen.zeitreihe(heizen, luecken=True),
            nachladen.zeitreihe(wetter, "cloud_coverage", luecken=True),
            nachladen.zeitreihe(wetter, "wind_speed", luecken=True),
        )

    async def _lerndaten(self) -> tuple[str, dict[date, list[hausmodell.Stunde]]] | None:
        """Die Heizart und die Stunden der letzten 14 Tage aus dem Verlauf, je Tag."""
        quellen = self._heizquellen()
        if not quellen:
            return None
        k, aussen = self.konfig, self.aussen_entitaet()
        thermostate = [r for r in k["raeume"] if eingaben.ist_thermostat(r)]
        einfach = [r for r in k["raeume"] if r not in thermostate]
        einfach += [entitaet for _, entitaet in quellen] + ([aussen] if aussen else [])
        jetzt = dt_util.now()
        zustaende = await self._verlauf_lesen([k["wetter"], *thermostate], einfach, jetzt)
        if not zustaende:
            return None
        # Hat der Vorlauf keinen Verlauf, zählt die Pumpe.
        for art, heizer in quellen:
            reihen = self._reihen(zustaende, art, heizer)
            if any(wert is not None for _, wert in reihen.heizen):
                return art, self._je_tag(reihen, art, _lernzeiten(jetzt.date()))
        return None

    def _mit_fehlern(
        self, neu: hausmodell.Modell, tag: date, stunden: list[hausmodell.Stunde]
    ) -> hausmodell.Modell:
        """Das neue Modell mit den Fehlern bis zum Vortag; beide Reihen nur gemeinsam länger."""
        alt = self.hausmodell
        fehler = list(alt.fehler) if alt else []
        bleibt = list(alt.fehler_bleibt) if alt else []
        gestern = hausmodell.tagesfehler(neu, stunden)
        ohne = hausmodell.tagesfehler_bleibt(stunden, neu.heiz_art)
        # Der Vortag zählt einmal, und nie ein Tag vor dem zuletzt gezählten.
        if (
            gestern is not None
            and ohne is not None
            and (self._fehler_tag is None or tag.isoformat() > self._fehler_tag)
        ):
            fehler.append(round(gestern, 3))
            bleibt.append(round(ohne, 3))
            self._fehler_tag = tag.isoformat()
        n = hausmodell.FEHLER_TAGE
        return replace(neu, fehler=tuple(fehler[-n:]), fehler_bleibt=tuple(bleibt[-n:]))

    async def hausmodell_lernen(self) -> None:
        """Die letzten 14 Tage lesen, lernen, den Fehler des Vortags fortschreiben.

        Ohne bisheriges Modell rechnet es die vergangenen Tage nach, statt 14 Tage zu sammeln.
        """
        daten = await self._lerndaten()
        if daten is None or not daten[1]:
            self.lern_grund = GRUND_DATEN
            return
        heiz_art, stunden_je_tag = daten
        tage = sorted(stunden_je_tag)
        alle = [s for tag in tage[:-1] for s in stunden_je_tag[tag]]
        ausfuehren = self.hass.async_add_executor_job
        neu = await ausfuehren(hausmodell.lernen, alle, heiz_art, len(tage) - 1)
        if neu is None:
            self.lern_grund = GRUND_UNPASSEND
            return
        self.lern_grund = None
        if self.hausmodell is None:
            reihen = [stunden_je_tag[tag] for tag in tage]
            fehler, bleibt = await ausfuehren(hausmodell.nachrechnen, reihen, heiz_art)
            self.hausmodell = replace(neu, fehler=tuple(fehler), fehler_bleibt=tuple(bleibt))
            self._fehler_tag = tage[-1].isoformat()
        else:
            self.hausmodell = self._mit_fehlern(neu, tage[-1], stunden_je_tag[tage[-1]])
        self._speichern()

    # --- Vorhersage ----------------------------------------------------------
    def _zeitprogramm(self, betriebswahl: int | None) -> Any:
        """Die Blöcke des aktiven Zeitprogramms; ohne Programm 1–3 oder ungelesen `None`."""
        if (adresse := ZEITPROGRAMME.get(betriebswahl)) is None:
            return None
        daten = self.coordinator.data or {}
        name = f"Programm {betriebswahl}"
        for d in daten.get("devices") or []:
            oid = str(d.get("oid") or "")
            if d.get("type") != "time_program" or not oid.startswith(f"{self.prefix}/"):
                continue
            if oid == f"{self.prefix}{adresse}" or d.get("name") == name:
                return (daten.get("objects") or {}).get(oid)
        return None

    def _ziel(self, lage: regel.Lage, bloecke: Any, zeit: datetime) -> float | None:
        """Ziel einer Stunde, passend zum Raumwert: Raum minus Abweichung, wie die Regel sie rechnet.

        Ohne eigene Raumziele folgt es dem Zeitprogramm; eigene Ziele bleiben über die Stunden gleich.
        """
        soll = regel.soll_bezug(lage, self.gedaechtnis)
        if soll is None or lage.raum is None:
            return None
        jetzt = lage.raum - regel.abweichung(lage, soll)
        eigene = any(ziel is not None for _, ziel in lage.raeume)
        programm = None if eigene else zeitprogramm.soll_um(bloecke, zeit)
        return jetzt if programm is None else jetzt + programm - soll

    def _eingaenge(
        self, lage: regel.Lage, bloecke: Any, jetzt: datetime, bis: datetime
    ) -> list[vorhersage.Stundeneingang] | None:
        """Die Stunden ab der nächsten vollen bis vor den Horizont; fehlt eine AT, keine."""
        prognose = self.stundenprognose(jetzt.date())
        sonne = tagesansicht.sonne(self, jetzt.date())
        eingaenge = []
        zeit = jetzt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        while zeit < bis:
            stunde = prognose.get(zeit.hour) or {}
            at, ziel = stunde.get("korrigiert"), self._ziel(lage, bloecke, zeit)
            if at is None or ziel is None:
                return None
            anteil = sonne[zeit.hour] if zeit.hour < len(sonne) else 0.0
            eingaenge.append(vorhersage.Stundeneingang(zeit, at, anteil, stunde.get("wind"), ziel))
            zeit += timedelta(hours=1)
        return eingaenge or None

    def _rueckkehr(
        self, v: vorhersage.Vorhersage, lage: regel.Lage, bloecke: Any, jetzt: datetime
    ) -> bool:
        """Ob eine laufende Stufe des Modells enden muss; ohne laufende Stufe nie."""
        g = self.gedaechtnis
        eigen = g.absenkung_anlass == regel.ANLASS_MODELL and regel.absenkung_laeuft(g, jetzt)
        stufe = _STUFE_JE_ART.get(g.absenkung_art) if eigen else None
        bezug = self._vorhersage_bezug
        erwartet = None
        if stufe is None or bezug is None or bezug.stufe != stufe:
            self._vorhersage_bezug = v
        else:
            erwartet = _kurvenwert(bezug.kurve, jetzt)
        if stufe is None or lage.raum is None:
            return False
        if (ziel := self._ziel(lage, bloecke, jetzt)) is None:
            return False
        return vorhersage.rueckkehr_noetig(
            lage.raum, erwartet, ziel, self.werte.spielraum_k, v.fehler
        )

    def vorhersage_fuer(self, jetzt: datetime, lage: regel.Lage) -> vorhersage.Vorhersage | None:
        """Die Vorhersage bis zum Horizont; steuern darf sie erst mit freigegebenem Hausmodell.

        Ohne Freigabe wird sie nur gemerkt, damit Anzeige und Diagnose sie beobachten.
        """
        self._vorhersage_zuletzt = None
        if self.hausmodell is None or lage.raum is None:
            return None
        bloecke = self._zeitprogramm(lage.betriebswahl)
        bis = zeitprogramm.horizont(bloecke, jetzt)
        if (eingaenge := self._eingaenge(lage, bloecke, jetzt, bis)) is None:
            return None
        w = self.werte
        v = vorhersage.waehlen(
            self.hausmodell,
            lage.raum,
            self._wert("/0/2/0"),
            eingaenge,
            w.absenkung_k,
            w.spielraum_k,
            bis,
        )
        v = replace(v, rueckkehr=self._rueckkehr(v, lage, bloecke, jetzt))
        self._vorhersage_zuletzt = v
        return v if hausmodell.freigegeben(self.hausmodell) else None
