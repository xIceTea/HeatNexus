"""Optimierungshinweise in der Laufzeit: Tage archivieren, Kurvenparameter lesen, auswerten.

Gelesen wird nur; an die Steuerung geht nichts. Archiv und Parameterverlauf liegen im
Speicher der Automatik. Aus der Aufzeichnung von Home Assistant werden einmal die
vergangenen Tage nachgerechnet; danach hängt das Archiv nicht mehr an ihr.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date, datetime, timedelta
import logging
import math
from typing import Any, NamedTuple

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..helpers import enum_texte
from . import eingaben, nachladen, nachrechnen, optimierer, regel
from .vorausschau import LERNTAGE

_LOGGER = logging.getLogger(__name__)
ARCHIV_TAGE = 150
# Heizkurve, Behaglichkeit, Vorhaltezeit, Raumsollwert und die eigene Anpassung der Steuerung.
PARAMETER = ("/3/1/0", "/3/12/0", "/3/13/0", "/3/7/0", "/3/58/0", "/3/6/0", "/3/51/0", "/3/101/0")
LESEZEIT = {"hour": 0, "minute": 40, "second": 0}
# Raumsoll, Vorlauf-Soll, Betriebsart und Restzeit: die Adressen, die `_stundenfelder` live liest.
VERLAUFSWERTE = {"soll": "/1/1/0", "vl": "/1/2/0", "ba": "/2/9/0", "restzeit": "/2/10/0"}
# So weit liest `_verlauf_lesen` zurück; so viele Tage vor heute lassen sich nachrechnen.
NACHRECHNEN_TAGE = LERNTAGE
# Fassung der Tageswertung; ein Archiv aus einer älteren Fassung wird einmal neu gerechnet.
NACHRECHNEN_FASSUNG = 2
VOLLER_TAG = 24
# Die Klima-Entität des Heizkreises führt die Restzeit `2/10` als Merkmal.
RESTZEIT_MERKMAL = "override_restzeit_min"


class Quellen(NamedTuple):
    """Die Entitäten, aus deren Verlauf die Tage des Archivs nachgerechnet werden."""

    aussen: str | None
    werte: dict[str, str | None]
    raeume: list[str]
    parameter: dict[str, str]
    # Die Klima-Entität des Heizkreises; nur gesetzt, wenn `2/10` keine eigene Entität hat.
    klima: str | None = None

    def lesen(self) -> tuple[list[str], list[str]]:
        """Thermostate und die Klima-Entität mit Attributen, alles andere ohne."""
        thermostate = [r for r in self.raeume if eingaben.ist_thermostat(r)]
        einfach = [r for r in self.raeume if r not in thermostate]
        einfach += [e for e in (self.aussen, *self.werte.values(), *self.parameter.values()) if e]
        mit_attributen = [*thermostate, *([self.klima] if self.klima else [])]
        return list(dict.fromkeys(mit_attributen)), list(dict.fromkeys(einfach))


def _schluessel(adresse: str) -> str:
    """`/3/13/0` → `3/13`, wie der Optimierer die Parameter nennt."""
    return adresse.strip("/").rsplit("/", 1)[0]


def _fassung(roh: Any) -> int:
    """Die gespeicherte Marke als Fassung; `True` stammt aus der ersten Fassung."""
    if roh is True:
        return 1
    return roh if isinstance(roh, int) and not isinstance(roh, bool) and roh > 0 else 0


def _ersetzbar(alt: dict[str, Any] | None, stunden: int) -> bool:
    """Ob ein nachgerechneter Tag mit `stunden` Stunden den Archivtag `alt` ersetzt.

    Ein live archivierter Tag bleibt, außer er hat weniger Stunden (live begonnener Teiltag).
    """
    if alt is None or alt.get("nachgerechnet"):
        return True
    vorhanden = alt.get("stunden")
    return not isinstance(vorhanden, int) or vorhanden < stunden


def _offene_tage(archiv: list[dict[str, Any]], heute: date) -> list[date]:
    """Die Tage vor heute im Zeitraum des Nachrechnens, die ein nachgerechneter Tag ersetzen kann."""
    je_datum = {t.get("datum"): t for t in archiv}
    tage = [heute - timedelta(days=n) for n in range(NACHRECHNEN_TAGE, 0, -1)]
    return [t for t in tage if _ersetzbar(je_datum.get(t.isoformat()), VOLLER_TAG)]


def _letzte_tage(tage: list[optimierer.Tag], heute: date | str) -> list[optimierer.Tag]:
    """Die Archivtage im Zeitraum des Nachrechnens vor heute."""
    bis = date.fromisoformat(str(heute))
    von = (bis - timedelta(days=NACHRECHNEN_TAGE)).isoformat()
    return [t for t in tage if von <= t.datum < bis.isoformat()]


def _ausreihe(zustaende: list[Any]) -> nachrechnen.Reihe:
    """Wann ein Thermostat aus war (1) und wann nicht (0)."""
    return [(dt_util.as_local(z.last_updated), float(z.state == "off")) for z in zustaende]


def _raum(
    zustaende: dict[str, list[Any]], kennung: str, raum_ziel: float | None
) -> tuple[nachrechnen.Reihe, nachrechnen.Reihe | float | None, nachrechnen.Reihe]:
    """Ist, Ziel und Ausschaltung eines Raums; ohne eigenes Ziel gilt die Wunschtemperatur."""
    ist = nachladen.raumreihe(zustaende, kennung, luecken=True)
    if not eingaben.ist_thermostat(kennung):
        return ist, raum_ziel, []
    eigen = nachladen.zeitreihe(zustaende.get(kennung, []), "temperature", luecken=True)
    ziel = [(zeit, raum_ziel if wert is None else wert) for zeit, wert in eigen]
    return ist, ziel, _ausreihe(zustaende.get(kennung, []))


def _textreihe(zustaende: list[Any], werte_je_text: dict[str, int]) -> nachrechnen.Reihe:
    """Eine Auswahl als Zahl; die Entität zeichnet ihren Text auf."""
    return [(dt_util.as_local(z.last_updated), werte_je_text.get(z.state)) for z in zustaende]


def _wertwechsel(reihe: nachrechnen.Reihe, anfang: date) -> list[list[Any]]:
    """Anfangsstand und jeder Wechsel als `[datum, wert]`; der Anfangsstand gilt ab `anfang`."""
    eintraege: list[list[Any]] = []
    for zeit, wert in reihe:
        if wert is not None and (not eintraege or eintraege[-1][1] != wert):
            eintraege.append([max(zeit.date(), anfang).isoformat(), wert])
    return eintraege


def _zusammenfuehren(frueher: list[list[Any]], gelesen: list[list[Any]]) -> list[list[Any]]:
    """Aufgezeichnete Wechsel vor die gelesenen Einträge; ab der ersten Lesung gilt die Lesung.

    Zeigt die erste Lesung denselben Wert wie die Aufzeichnung, ist sie kein Wechsel.
    """
    if gelesen:
        frueher = [e for e in frueher if e[0] < str(gelesen[0][0])]
        if frueher and frueher[-1][1] == gelesen[0][1]:
            gelesen = gelesen[1:]
    return [*frueher, *gelesen]


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
    archiv_nachgerechnet: int
    parameter_eingeschaltet: bool

    def _optimierung_laden(self, z: dict[str, Any]) -> None:
        archiv = z.get("tage_archiv")
        archiv = archiv if isinstance(archiv, list) else []
        self.tage_archiv = [t for t in archiv if isinstance(t, dict)][-ARCHIV_TAGE:]
        self.parameter_verlauf = _parameter_laden(z.get("parameter_verlauf"))
        gelesen = z.get("parameter_gelesen")
        self.parameter_gelesen = gelesen if isinstance(gelesen, str) else None
        self.archiv_nachgerechnet = _fassung(z.get("archiv_nachgerechnet"))
        self.parameter_eingeschaltet = z.get("parameter_eingeschaltet") is True
        self._parameteraufgabe: Any = None
        self._nachrechenaufgabe: Any = None

    def optimierung_als_dict(self) -> dict[str, Any]:
        return {
            "tage_archiv": self.tage_archiv,
            "parameter_verlauf": self.parameter_verlauf,
            "parameter_gelesen": self.parameter_gelesen,
            "archiv_nachgerechnet": self.archiv_nachgerechnet,
            "parameter_eingeschaltet": self.parameter_eingeschaltet,
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
        # Beim Beobachten ist die Absenkung nur gerechnet; jede Restzeit stammt dann vom Nutzer.
        eigen = regel.absenkung_laeuft(self.gedaechtnis, lage.jetzt) and not self.beobachten
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

    # --- Nachrechnen ----------------------------------------------------------
    async def archiv_nachrechnen(self) -> int:
        """Tage der letzten zwei Wochen aus der Aufzeichnung archivieren; liefert die Zahl geschriebener.

        Ohne Aufzeichnung oder bei einem Lesefehler bleibt die Marke offen, für den nächsten Start.
        """
        heute = dt_util.now().date()
        neu: list[dict[str, Any]] = []
        if offen := _offene_tage(self.tage_archiv, heute):
            quellen = self._nachrechenquellen()
            ende = dt_util.start_of_local_day(heute)
            if (zustaende := await self._verlauf_lesen(*quellen.lesen(), ende)) is None:
                return 0
            neu = self._tage_nachrechnen(zustaende, quellen, offen)
            anfang = heute - timedelta(days=NACHRECHNEN_TAGE)
            self._parameter_nachtragen(zustaende, quellen.parameter, anfang)
        self.archiv_nachgerechnet = NACHRECHNEN_FASSUNG
        self.nachgetragen()
        return len(neu)

    def _verlaufsentitaet(self, adresse: str) -> str | None:
        """Die Entität einer Adresse: schreibbar eine Zahl, schreibgeschützt ein Sensor."""
        return self._entitaet(adresse, "number") or self._entitaet(adresse)

    def _klima_entitaet(self) -> str | None:
        """Die Klima-Entität des Heizkreises, über seine Beschreibung wie im Reiter Automatik."""
        for d in (self.coordinator.data or {}).get("devices") or []:
            if d.get("type") == "climate" and d.get("device_id") == self.device_id:
                kennung = d.get("id", "")
                return er.async_get(self.hass).async_get_entity_id("climate", DOMAIN, kennung)
        return None

    def _nachrechenquellen(self) -> Quellen:
        """Dieselben Quellen wie im laufenden Betrieb, als Entitäten mit Verlauf."""
        werte = {name: self._verlaufsentitaet(a) for name, a in VERLAUFSWERTE.items()}
        return Quellen(
            aussen=self.aussen_entitaet(),
            werte=werte,
            raeume=list(self.konfig["raeume"]),
            parameter={
                _schluessel(a): kennung for a in PARAMETER if (kennung := self._verlaufsentitaet(a))
            },
            klima=None if werte["restzeit"] else self._klima_entitaet(),
        )

    def _betriebsarten(self) -> dict[str, int]:
        """Die Zahl je Text der Betriebsart, wie die Entität ihn anzeigt."""
        oid = f"{self.prefix}{VERLAUFSWERTE['ba']}"
        geraete = (self.coordinator.data or {}).get("devices") or []
        beschreibung = next((d for d in geraete if d.get("oid") == oid), {"enum": "2/9"})
        return {text: wert for wert, text in enum_texte(beschreibung).items()}

    def _tagesreihen(self, zustaende: dict[str, list[Any]], quellen: Quellen) -> nachrechnen.Reihen:
        """Die Zeitreihen des Heizkreises aus dem gelesenen Verlauf."""
        raeume = [_raum(zustaende, r, self.konfig.get("raum_ziel")) for r in quellen.raeume]
        werte = {
            name: nachladen.zeitreihe(zustaende.get(kennung, []), luecken=True)
            for name, kennung in quellen.werte.items()
        }
        if quellen.klima:
            klima = zustaende.get(quellen.klima, [])
            werte["restzeit"] = nachladen.zeitreihe(klima, RESTZEIT_MERKMAL, luecken=True)
        return nachrechnen.Reihen(
            at=nachladen.zeitreihe(zustaende.get(quellen.aussen, []), luecken=True),
            soll=werte["soll"],
            vl=werte["vl"],
            ba=_textreihe(zustaende.get(quellen.werte["ba"], []), self._betriebsarten()),
            restzeit=werte["restzeit"],
            raeume=[(ist, ziel) for ist, ziel, _ in raeume],
            raum_art=self.konfig["raum_art"],
            aus=[aus for _, _, aus in raeume],
        )

    def _tage_nachrechnen(
        self, zustaende: dict[str, list[Any]], quellen: Quellen, offen: list[date]
    ) -> list[dict[str, Any]]:
        """Die Tage aus dem Verlauf; ein vollständiger live archivierter Tag bleibt."""
        je_tag = nachrechnen.stunden_je_tag(self._tagesreihen(zustaende, quellen), offen)
        je_datum = {t.get("datum"): t for t in self.tage_archiv}
        neu = []
        for datum, stunden in je_tag.items():
            tag = optimierer.tag_aus_stunden(datum, stunden)
            if tag is not None and _ersetzbar(je_datum.get(datum), tag.stunden):
                neu.append(asdict(replace(tag, nachgerechnet=True)))
        ersetzt = {t["datum"] for t in neu}
        bleibt = [t for t in self.tage_archiv if t.get("datum") not in ersetzt]
        archiv = sorted([*bleibt, *neu], key=lambda t: str(t.get("datum") or ""))
        self.tage_archiv = archiv[-ARCHIV_TAGE:]
        return neu

    def _parameter_nachtragen(
        self, zustaende: dict[str, list[Any]], parameter: dict[str, str], anfang: date
    ) -> None:
        """Aufgezeichnete Wechsel der Parameter vor den gelesenen Verlauf stellen."""
        verlauf = dict(self.parameter_verlauf)
        for name, kennung in parameter.items():
            if frueher := _wertwechsel(nachladen.zeitreihe(zustaende.get(kennung, [])), anfang):
                verlauf[name] = _zusammenfuehren(frueher, verlauf.get(name, []))
        self.parameter_verlauf = verlauf

    # --- Parameter -----------------------------------------------------------
    def _optimierung_starten(self) -> None:
        """Täglich lesen; beim Start sofort, wenn heute noch nichts gelesen wurde.

        Fehlt die Marke oder stammt sie aus einer älteren Fassung, werden einmal die vergangenen
        Tage aus der Aufzeichnung nachgerechnet.
        """
        self._abmelden.append(async_track_time_change(self.hass, self._parameter_takt, **LESEZEIT))
        self._parameter_einschalten()
        if self.parameter_gelesen != dt_util.now().date().isoformat():
            self._parameter_anstossen()
        if self.archiv_nachgerechnet < NACHRECHNEN_FASSUNG:
            self._nachrechenaufgabe = self.hass.async_create_background_task(
                self.archiv_nachrechnen(), f"heatnexus_nachrechnen_{self.device_id}"
            )

    def _parameter_einschalten(self) -> None:
        """Mit Hinweisen die deaktiviert angelegten Kurvenparameter einmal einschalten, sobald sie gelesen sind.

        Nur Parameter mit Wert; was der Nutzer selbst abgeschaltet hat, bleibt aus.
        """
        stand = optimierer.parameterstand(self.parameter_verlauf)
        if not self.konfig.get("hinweise") or self.parameter_eingeschaltet or not stand:
            return
        register = er.async_get(self.hass)
        for adresse in PARAMETER:
            if _schluessel(adresse) not in stand:
                continue
            kennung = self._verlaufsentitaet(adresse)
            eintrag = register.async_get(kennung) if kennung else None
            if eintrag is not None and eintrag.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
                register.async_update_entity(eintrag.entity_id, disabled_by=None)
        self.parameter_eingeschaltet = True
        self._speichern()

    def _optimierung_beenden(self) -> None:
        for aufgabe in (self._parameteraufgabe, self._nachrechenaufgabe):
            if aufgabe is not None and not aufgabe.done():
                aufgabe.cancel()
        self._parameteraufgabe = None
        self._nachrechenaufgabe = None

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
        self._parameter_einschalten()
        self._speichern()

    # --- Auswertung ----------------------------------------------------------
    def hinweise_liste(self, heute: date | str) -> list[optimierer.Hinweis]:
        return optimierer.hinweise(self.archivierte_tage(), self.parameter_verlauf, heute)

    def hinweise_stand(self, heute: date | str) -> dict[str, Any]:
        """Die Kachel „Optimierung“; ohne eingeschalteten Schalter nur `{"status": "aus"}`.

        `aufgezeichnet` zählt die Archivtage der letzten zwei Wochen, `ohne_grundlage` die mit Eingriffen.
        `entitaeten` nennt je Kurvenparameter die aktive Entität, deren Verlauf ein Klick zeigt.
        `parameter` nennt je Kurvenparameter Wert und letzte Änderung, auch ohne aktive Entität.
        `vorlaeufig` nennt die Tendenz der Arten, denen für eine Empfehlung noch Tage fehlen.
        """
        if not self.konfig.get("hinweise"):
            return {"status": "aus"}
        tage = self.archivierte_tage()
        eintraege = optimierer.hinweise(tage, self.parameter_verlauf, heute)
        grundlage = optimierer.grundlage(tage, self.parameter_verlauf, heute)
        zuletzt = _letzte_tage(tage, heute)
        return {
            "status": "bereit" if eintraege else "sammelt",
            "tage": len(grundlage),
            "noetig": optimierer.MIN_TAGE,
            "eintraege": [asdict(h) for h in eintraege],
            "fortschritt": optimierer.fortschritt(tage, self.parameter_verlauf, heute),
            "aufgezeichnet": len(zuletzt),
            "ohne_grundlage": sum(not t.ungestoert for t in zuletzt),
            "entitaeten": self._ergebnis_entitaeten(
                stand := optimierer.parameterstand(self.parameter_verlauf)
            ),
            "vorlaeufig": [
                asdict(t) for t in optimierer.tendenzen(tage, self.parameter_verlauf, heute)
            ],
            "parameter": stand,
            "arten": optimierer.arten(self.parameter_verlauf),
        }

    def _ergebnis_entitaeten(self, stand: dict[str, Any]) -> dict[str, str]:
        """Je Parameter mit gelesenem Wert die aktive Entität, deren Verlauf ein Klick zeigt.

        Der Hinweis zum Raumsollwert bewertet den wirksamen Sollwert; den zeigt das Thermostat, nicht `3/51`.
        """
        kennungen = {
            name: self._klima_entitaet() if name == "3/51" else self._verlaufsentitaet(a)
            for a in PARAMETER
            if (name := _schluessel(a)) == "3/51" or name in stand
        }
        return {name: k for name, k in kennungen.items() if k and self._aktiv(k)}

    def _aktiv(self, entity_id: str) -> bool:
        """Ob die Entität eingeschaltet ist; eine deaktivierte hat keinen Verlauf."""
        eintrag = er.async_get(self.hass).async_get(entity_id)
        return eintrag is not None and not eintrag.disabled
