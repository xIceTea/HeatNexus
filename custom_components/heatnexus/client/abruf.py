"""Der zyklische Abruf: Poll-Klassen, Fälligkeit, Zeitbudget, Zeitprogramme.

Die Steuerung beantwortet Anfragen nacheinander; Parallelität verkürzt keinen
Durchlauf. Die Adressen werden nach Klasse gestaffelt gelesen, und ein Durchlauf
endet mit dem Zeitbudget – der Rest kommt beim nächsten zuerst.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
import re as _re
import time

from ..const import (
    FETCH_CONCURRENCY,
    POLL_BLOCK,
    POLL_CONCURRENCY,
    POLL_EINHEITEN_TRAEGE,
    POLL_FAST,
    POLL_KLASSEN,
    POLL_NORMAL,
    POLL_SLOW,
    POLL_TYPEN_SCHNELL,
    POLL_TYPEN_STELLWERT,
    POLL_WOERTER_SCHNELL,
    POLL_WOERTER_TRAEGE,
    SYSTEMZEIT_NAMEN,
    UHR_TIMEOUT,
    VORMERK_MAX_ALTER_S,
)
from ..helpers import poll_takte
from ..lon import zuordnen as lon_zuordnen
from .gemeinsam import FEHLGESCHLAGEN, MELDUNGS_SENSOREN

_LOGGER = logging.getLogger(__name__)


def ist_zeitprogramm(wert) -> bool:
    """Prüfen, ob die Antwort ein Zeitprogramm ist und nicht irgendeine Liste.

    Der object-Endpunkt liefert für `typeId 30` je nach `subtypeId`
    Verschiedenes: ein Zeitprogramm (Blöcke aus Wochentagen und Schaltpunkten),
    einen Text (Gerätetyp „PW 400") oder die Funktionsliste eines Knotens
    (`[{"fctType": 25, "lock": false}]`). Die letzte ist ebenfalls eine Liste
    von Objekten und ging vorher als Zeitprogramm durch.
    """
    return (
        isinstance(wert, list)
        and bool(wert)
        and all(isinstance(b, dict) and ("weekdays" in b or "switchPoints" in b) for b in wert)
    )


class AbrufMixin:
    """Zyklischer Abruf und gezielte Lesevorgänge."""

    # Je schneller die Klasse, desto kleiner der Rang.
    _KLASSEN_RANG = {POLL_FAST: 0, POLL_NORMAL: 1, POLL_SLOW: 2}

    # OIDs, die statisch immer mitgepollt werden müssen, weil eine
    # Climate-Entity sie für Anzeige/Berechnung braucht.
    _CLIMATE_POLL_SUFFIXES = (
        "/0/1/0",  # Raumtemperatur Ist
        "/1/1/0",  # Raumtemperatur Soll (aktiv) = angezeigter Sollwert
        "/3/50/0",  # Betriebswahl
        "/2/10/0",  # Override-Restzeit (Timer) für Anzeige/Feedback
        "/3/58/0",  # Behaglichkeitskorrektur
        "/1/20/0",  # Heizkreispumpe (für hvac_action)
    )

    # Alle Meldungsfelder eines Geräts (FE01msg, FE02msg, …) – mehrere
    # gleichzeitige Störungen reihen sich aneinander.
    _FEMSG_RE = _re.compile(r"^FE\d+msg$")

    _ZEITSTEMPEL = "%Y-%m-%d %H:%M:%S"

    # Die Steuerung liefert Datum und Uhrzeit als Text. Welche Schreibweise
    # sie wählt, ist nicht für jede Baureihe belegt; deshalb mehrere.
    _DATUMSFORMATE = ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y")

    _UHRZEITFORMATE = ("%H:%M:%S", "%H:%M")

    @classmethod
    def _klasse_eintragen(cls, klassen: dict[str, str], oid: str, klasse: str) -> None:
        """Teilen sich mehrere Deskriptoren eine Adresse, gilt die schnellste.

        Ein abgeleiteter Wert ist abgeschaltet und damit träge eingestuft; er
        darf seine Quelle nicht ausbremsen.
        """
        if cls._KLASSEN_RANG.get(klasse, 9) < cls._KLASSEN_RANG.get(klassen.get(oid, ""), 9):
            klassen[oid] = klasse

    @property
    def abrufplan(self) -> set[str]:
        """Alle Adressen, die zyklisch gelesen werden.

        Fest angemeldete, von Entitäten nachgemeldete, abzüglich der von der
        Anlage abgelehnten. Die eine Stelle, an der das steht.
        """
        return (self.poll_oids | self._dynamic_oids) - self._abgemeldet

    def register_poll_oid(self, oid: str) -> None:
        """Eine Entity meldet ihre OID zum zyklischen Polling an.

        Eine eben angemeldete Adresse wird einmal gelesen, gleich welcher
        Klasse: Entities melden sich erst nach dem ersten Durchlauf an, und ein
        träger Wert stünde sonst bis zum nächsten langsamen Takt ohne Zahl da.
        """
        if oid and oid not in self._abgemeldet:
            neu = oid not in self._dynamic_oids
            self._dynamic_oids.add(oid)
            self._oid_nutzer[oid] = self._oid_nutzer.get(oid, 0) + 1
            if neu and oid not in self._letzte_werte:
                self._rest.add(oid)

    def unregister_poll_oid(self, oid: str) -> None:
        """Eine entfernte/deaktivierte Entity meldet ihre OID ab.

        Gezählt wird, wer sie braucht: Ein Zählerstand und seine Ableitungen
        lesen dieselbe Adresse, und die eine abzuschalten darf die andere nicht
        blind stellen.
        """
        offen = self._oid_nutzer.get(oid, 0) - 1
        if offen > 0:
            self._oid_nutzer[oid] = offen
            return
        self._oid_nutzer.pop(oid, None)
        self._dynamic_oids.discard(oid)
        # Auch das vorgemerkte Erstlesen entfällt: Niemand wartet mehr darauf.
        self._rest.discard(oid)

    def _abmelden(self, oid: str, data, status: int) -> bool:
        """Einen abgelehnten Datenpunkt aus dem zyklischen Abruf nehmen.

        Die Anlage antwortet auf Positionen, die sie nicht führt, mit `404`
        oder mit `409` und unbekannter Kennung. Beim Einlesen der Metadaten
        wurden sie schon bisher verworfen – Positionen aus den Menü-Ebenen
        laufen daran jedoch vorbei und wurden anschließend in jedem Durchlauf
        erneut angefragt, obwohl die Antwort feststeht.
        """
        grund = (data or {}).get("reason", "") if isinstance(data, dict) else ""
        if status != 404 and not (status == 409 and "invalid Identifier" in grund):
            return False
        if oid not in self._abgemeldet:
            self._abgemeldet.add(oid)
            _LOGGER.info("Datenpunkt %s wird nicht mehr abgefragt: %s", oid, grund or status)
        self.poll_oids.discard(oid)
        self._dynamic_oids.discard(oid)
        self._oid_nutzer.pop(oid, None)
        self._rest.discard(oid)
        return True

    @staticmethod
    def _poll_klasse(beschreibung: dict) -> str:
        """In welchem Takt ein Datenpunkt gelesen werden muss.

        Die Einstufung folgt dem, was der Wert *ist*, nicht wo er steht:
        Zählerstände und Restlaufzeiten bewegen sich in Stunden, Temperaturen
        und Betriebszustände in Sekunden. Im Zweifel bleibt es beim mittleren
        Takt – lieber einmal zu oft gelesen als eine Anzeige, die nachhinkt.
        """
        # Was die kuratierte Tabelle selbst festlegt, gilt: Art und Name
        # treffen einen Eingriff in die Betriebswahl nicht.
        if (vorgabe := beschreibung.get("poll_class")) in POLL_KLASSEN:
            return vorgabe
        # Netzwerkvariablen sind die zweite Quelle, nie die erste: Was sie
        # führen, steht meist schon als Datenpunkt da. Sie laufen deshalb
        # langsam, außer die Namenstabelle nennt einen anderen Takt – Pumpe
        # und Ventil zeigt das Schaubild. Ohne diese Regel griffe die
        # Einstufung unten: „Temperatur" und „Pumpe" gälten als laufende
        # Betriebswerte und kämen auf 120 Anfragen je Stunde und Wert.
        if nv_name := beschreibung.get("nv_name"):
            return (lon_zuordnen(nv_name) or {}).get("poll_class", POLL_SLOW)

        typ = beschreibung.get("type") or ""
        if typ in POLL_TYPEN_SCHNELL:
            return POLL_FAST

        name = (beschreibung.get("name") or "").lower()
        if any(wort in name for wort in POLL_WOERTER_TRAEGE):
            return POLL_SLOW
        if beschreibung.get("state_class") in ("total", "total_increasing"):
            return POLL_SLOW
        if (beschreibung.get("unit") or "") in POLL_EINHEITEN_TRAEGE:
            return POLL_SLOW
        # Fachparameter der Service- und Werksebene werden standardmäßig
        # deaktiviert angelegt. Sie ändern sich nur, wenn jemand sie ändert.
        if not beschreibung.get("enabled_default", True):
            return POLL_SLOW

        # Vor der Namensprüfung: „Raumtemperatur Heizbetrieb" ist ein Sollwert,
        # kein Messwert. Der eigene Schreibvorgang liest sofort nach, eine
        # Änderung am Bediengerät steht im mittleren Takt an.
        if typ in POLL_TYPEN_STELLWERT:
            return POLL_NORMAL
        if any(wort in name for wort in POLL_WOERTER_SCHNELL):
            return POLL_FAST
        return POLL_NORMAL

    def _compute_poll_oids(self) -> None:
        """Statisches Poll-Set: aktive Entities + Climate-Hilfs-OIDs.

        Service-/standardmäßig deaktivierte Entities landen NICHT hier –
        sie werden erst gepollt, wenn der Nutzer sie in HA aktiviert und
        die Entity sich per register_poll_oid() dynamisch anmeldet.
        """
        poll: set = set()
        klassen: dict[str, str] = {}
        for d in self.devices:
            if d.get("type") == "climate":
                prefix = d.get("prefix", "")
                for suffix in self._CLIMATE_POLL_SUFFIXES:
                    oid = f"{prefix}{suffix}"
                    poll.add(oid)
                    # Das Thermostat ist das Bedienelement der Anlage; es darf
                    # nicht hinterherlaufen.
                    klassen[oid] = POLL_FAST
                continue
            if d.get("type") == "time_program" or d.get("objekt"):
                # wird über den object-Endpunkt gelesen, nicht über lookup
                continue
            if d.get("type") == "button":
                # Eine Taste zeigt nichts an; ihre Adresse wird nur beschrieben.
                continue
            if not d.get("oid"):
                continue
            self._klasse_eintragen(klassen, d["oid"], self._poll_klasse(d))
            if d.get("enabled_default", True):
                poll.add(d["oid"])
        # Die Climate-Endungen kommen ungeprüft dazu – ob eine Anlage die
        # Heizkreispumpe führt, weiß erst ihre Antwort. Ohne diesen Abzug
        # stünden abgelehnte Positionen nach jedem Neustart und jedem neuen
        # Einlesen wieder im Abruf, bis die Anlage sie erneut ablehnt.
        self.poll_oids = poll - self._abgemeldet
        self.poll_class = klassen
        self.time_programs = [d for d in self.devices if d.get("type") == "time_program"]
        self.objekt_texte = [
            d for d in self.devices if d.get("objekt") and d.get("type") != "time_program"
        ]

    def climate_oids(self, prefix: str) -> list:
        """Vollständige Climate-OIDs für einen Heizkreis-Prefix."""
        return [f"{prefix}{s}" for s in self._CLIMATE_POLL_SUFFIXES]

    async def fetch_oids(self, oids) -> dict:
        """Nur eine gezielte OID-Menge abfragen (für schnellen Burst-Refresh).

        Was die Anlage nicht beantwortet hat, fehlt im Ergebnis: Die Aufrufer
        tragen es in den Bestand des Abrufs ein.
        """
        results = await asyncio.gather(*(self._fetch_oid(o) for o in oids))
        return self.ueberlagern({oid: wert for oid, wert in results if wert is not FEHLGESCHLAGEN})

    def vormerken(self, oid: str, wert: str) -> None:
        """Einen geschriebenen Wert bis zur Bestätigung durch die Anlage anzeigen.

        Die Anlage nimmt den Auftrag entgegen und arbeitet ihn ab; bis dahin
        meldet sie den alten Wert. Ohne Vormerkung springt ein Schalter erst
        zurück und Sekunden später wieder um.
        """
        self._vorgemerkt[oid] = (str(wert), time.monotonic())

    def ueberlagern(self, werte: dict[str, str | None]) -> dict[str, str | None]:
        """Vorgemerkte Werte über die gelesenen legen.

        Die Vormerkung endet, sobald die Anlage denselben Wert meldet oder
        `VORMERK_MAX_ALTER_S` verstrichen ist. Sie sitzt an der Adresse, weil
        auf der Betriebswahl des Kessels mehrere Entitäten hängen.
        """
        if not self._vorgemerkt:
            return werte
        jetzt = time.monotonic()
        for oid, (wert, seit) in list(self._vorgemerkt.items()):
            if jetzt - seit > VORMERK_MAX_ALTER_S or (oid in werte and str(werte[oid]) == wert):
                del self._vorgemerkt[oid]
                continue
            werte[oid] = wert
        return werte

    async def _fetch_time_programs(self) -> dict:
        """Read all known time programs via the object endpoint.

        Beim ersten Aufruf wird geprüft, ob das Gerät den object-Endpunkt
        lokal überhaupt beherrscht. Falls nicht, werden die Zeitprogramm-
        Entities verworfen (keine toten Sensoren) und nicht mehr abgefragt.
        """
        objekte = self.time_programs + self.objekt_texte
        if self._objects_supported is False or not objekte:
            return {}

        results = await asyncio.gather(*(self.fetch_object(tp["oid"]) for tp in objekte))
        objects: dict = {}
        any_ok = False
        for tp, (data, status) in zip(objekte, results, strict=False):
            self._objekte_versucht.add(tp["oid"])
            if status != 200 or not isinstance(data, dict) or "value" not in data:
                continue
            any_ok = True
            wert = data["value"]
            if wert is None or (isinstance(wert, str | list | dict) and not wert):
                # Eine leere Antwort ist kein Textwert. Als Text geführt stünde
                # „None" in der Entität, und ein Zeitprogramm bliebe umgestuft.
                continue
            if ist_zeitprogramm(wert):
                objects[tp["oid"]] = wert
                continue
            # Kein Zeitprogramm, sondern ein einfacher Wert (Modulinfo,
            # Software-/Hardwarestand). Als Textsensor führen.
            self._object_texts[tp["oid"]] = str(wert)
            tp["type"] = "string_sensor"
            tp["objekt"] = True
            _LOGGER.debug(
                "%s (%s) ist kein Zeitprogramm, sondern ein Textwert", tp.get("name"), tp["oid"]
            )

        if self._objects_supported is None:
            self._objects_supported = any_ok
            if not any_ok:
                _LOGGER.info(
                    "object-Endpunkt lokal nicht verfügbar – Zeitprogramme werden übersprungen"
                )
                tp_oids = {tp["oid"] for tp in objekte}
                self.devices = [d for d in self.devices if d.get("oid") not in tp_oids]
                objekte = []
        self.time_programs = [tp for tp in objekte if tp.get("type") == "time_program"]
        self.objekt_texte = [tp for tp in objekte if tp.get("type") != "time_program"]
        return objects

    async def refresh_object(self, oid: str):
        """Ein einzelnes Zeitprogramm sofort neu lesen.

        Zeitprogramme laufen im langsamen Takt mit – wer eines schreibt, sähe
        seinen eigenen Stand sonst bis zu mehrere Minuten lang nicht. Nach dem
        Schreiben wird deshalb genau dieses eine Objekt nachgelesen, nicht
        alle: Jedes kostet eine eigene Anfrage an der Anlage.

        Zurück kommen die Blöcke, oder ``None``, wenn die Anlage nichts
        Brauchbares liefert – dann bleibt der zuletzt bekannte Stand stehen.
        """
        data, status = await self.fetch_object(oid)
        if status != 200 or not isinstance(data, dict) or "value" not in data:
            return None
        wert = data["value"]
        if not ist_zeitprogramm(wert):
            return None
        self._letzte_objekte[oid] = wert
        return wert

    async def _fetch_status(self) -> dict:
        """Aktuelle Geräte-Meldungen (FExxmsg) je Knoten neu lesen.

        Quelle ist die /1-Discovery, die je Gerät FE01msg (+ ggf. weitere)
        mitliefert. Nur nötig, wenn ein Meldungs-/Klartext-Sensor existiert.
        """
        typen = {typ for _, typ, _, _ in MELDUNGS_SENSOREN}
        if not any(d.get("type") in typen for d in self.devices):
            return {}
        try:
            devs = await self.fetch("/1")
        except Exception as e:
            _LOGGER.debug("Meldungen nicht lesbar: %s", e)
            devs = None
        if not isinstance(devs, list):
            # Wie bei den Werten: Ein Fehlschlag lässt den letzten Stand stehen.
            return dict(self._letzte_meldungen)
        out: dict = {}
        for dev in devs:
            nid = dev.get("nodeId")
            if nid is None:
                continue
            msgs = [str(v) for k, v in dev.items() if self._FEMSG_RE.match(k) and v]
            if msgs:
                out[str(nid)] = "  ".join(msgs)
        self._letzte_meldungen = out
        return out

    def statistik(self) -> dict:
        """Kennzahlen des Abrufverhaltens – für die Diagnose.

        Erst mit diesen Zahlen lässt sich beurteilen, ob eine Änderung am
        Abrufverhalten etwas gebracht hat. Vorher war jede Aussage dazu
        geschätzt.
        """
        laufzeit = max(time.monotonic() - self.gestartet, 1.0)
        return {
            "anfragen": self.request_count,
            "anfragen_je_stunde": round(self.request_count / laufzeit * 3600),
            "anfragen_fehlgeschlagen": self.request_errors,
            "dauer_je_anfrage_ms": (
                round(self.request_seconds / self.request_count * 1000, 1)
                if self.request_count
                else None
            ),
            # Wartezeit in der eigenen Warteschlange. Ist sie groß gegenüber
            # der Antwortzeit, hilft nicht eine schnellere Anlage, sondern
            # weniger Anfragen oder mehr gleichzeitige.
            "wartezeit_je_anfrage_ms": (
                round(self.queue_seconds / self.request_count * 1000, 1)
                if self.request_count
                else None
            ),
            "abrufe": self.poll_count,
            "dauer_je_abruf_s": (
                round(self.poll_seconds / self.poll_count, 2) if self.poll_count else None
            ),
            "laufzeit_min": round(laufzeit / 60, 1),
            "gleichzeitige_anfragen": FETCH_CONCURRENCY,
            "gleichzeitige_abfragen": POLL_CONCURRENCY,
            # Was der letzte Durchlauf gekostet hat.
            "anfragen_je_abruf": self._poll_anfragen,
            # Was er nicht mehr geschafft hat. Dauerhaft hohe Werte heißen:
            # Das Zeitfenster ist für diese Anlage zu knapp.
            "noch_offen": len(self._rest),
            "abgemeldet": len(self._abgemeldet),
        }

    def _takte(self) -> dict[str, int]:
        """Wie viele Durchläufe eine Poll-Klasse aussetzt (siehe helpers)."""
        return poll_takte(self.update_interval)

    def _faellig(self) -> set:
        """OIDs, die in diesem Durchlauf an der Reihe sind.

        Nicht jeder Wert ändert sich im selben Takt: Die Kesseltemperatur
        gehört alle 30 s abgefragt, „Betriebsstunden gesamt" nicht. Jede OID
        trägt eine Poll-Klasse; langsame Klassen kommen nur jeden n-ten
        Durchlauf dran. Das senkt die Last auf der Steuerung erheblich, ohne
        dass an der Anzeige etwas fehlt – die zuletzt gelesenen Werte bleiben
        stehen.
        """
        takte = self._takte()
        faellig = set()
        for oid in self.abrufplan:
            takt = takte.get(self.poll_class.get(oid, POLL_NORMAL), 1)
            # Beim ersten Durchlauf ist alles fällig, sonst stünde eine
            # langsame Entität bis zu 15 Minuten ohne Wert da.
            if self._tick == 0 or self._tick % takt == 0:
                faellig.add(oid)
        # Was beim letzten Mal nicht mehr in die Zeit passte, ist weiterhin
        # fällig – unabhängig von seiner Klasse.
        return faellig | (self._rest - self._abgemeldet)

    async def _lese_faellige(self, faellig: set, ende: float | None = None) -> tuple[list, set]:
        """Die fälligen OIDs lesen – jede einzeln, bis die Zeit aufgebraucht ist.

        Eine Menü-Ebene lässt sich mit `count`/`offset` in einer Anfrage
        lesen, und lange galt das als der schnelle Weg. Gemessen ist es der
        langsame: Ein Fenster mit zehn Positionen kostet ein Vielfaches von
        zehn Einzelabrufen über `datapoint`. Nicht die Zahl der Anfragen
        kostet, sondern das Zusammenstellen der Metadaten, die dabei
        anfallen und beim Abruf niemand braucht.

        Gelesen wird in Blöcken, damit zwischendurch die Zeit geprüft werden
        kann. Reicht sie nicht, endet der Durchlauf mit dem, was er hat, und
        gibt den Rest zurück. Zurückgegeben wird ``(Gelesenes, Rest)``.
        """
        # Der Rest des letzten Durchlaufs zuerst: Seine Werte sind die
        # ältesten, und ohne Vorrang käme er bei knapper Zeit nie an die Reihe.
        reihenfolge = sorted(faellig, key=lambda oid: (oid not in self._rest, oid))
        gelesen: list = []
        offen = set(faellig)
        for anfang in range(0, len(reihenfolge), POLL_BLOCK):
            block = reihenfolge[anfang : anfang + POLL_BLOCK]
            gelesen += await asyncio.gather(*(self._fetch_oid(oid) for oid in block))
            offen.difference_update(block)
            if offen and ende is not None and time.monotonic() >= ende:
                _LOGGER.debug(
                    "Poll: Zeit reicht für %d von %d OIDs, %d kommen im nächsten Durchlauf zuerst",
                    len(gelesen),
                    len(faellig),
                    len(offen),
                )
                break
        self._poll_anfragen = len(gelesen)
        _LOGGER.debug("Poll: %d OIDs einzeln", len(gelesen))
        return gelesen, offen - self._abgemeldet

    async def _startwerte_lesen(self, max_alter_min: int, bezugszeit=None) -> int:
        """Den Lesespeicher der Anlage einmal auswerten.

        Er liefert bis zu 256 zuletzt gelesene Werte in einer Anfrage, jeden
        mit Zeitstempel. Übernommen wird nur, was jünger ist als die Grenze:
        Der Speicher füllt sich nicht selbst, seine Werte können alt sein.
        """
        if max_alter_min <= 0:
            return 0
        try:
            daten, status = await self._get(f"http://{self.host}/api/1.0/datapoints")
        except Exception as err:
            _LOGGER.debug("Lesespeicher nicht verfügbar: %s", err)
            return 0
        if status != 200 or not isinstance(daten, list):
            return 0

        jetzt = bezugszeit or datetime.now()
        grenze = timedelta(minutes=max_alter_min)
        gebraucht = self.abrufplan
        uebernommen = 0
        for eintrag in daten:
            if not isinstance(eintrag, dict):
                continue
            oid = eintrag.get("OID")
            if oid not in gebraucht or oid in self._letzte_werte:
                continue
            gemessen = self._zeitstempel(eintrag.get("timestamp"))
            # Ein Zeitstempel in der Zukunft ist keine Frische, sondern eine
            # Uhr, die vorgeht. Der Wert bleibt liegen.
            if gemessen is None or not timedelta(0) <= jetzt - gemessen <= grenze:
                continue
            self._letzte_werte[oid] = self._wert_oder_none(eintrag.get("value"))
            uebernommen += 1

        _LOGGER.info(
            "%s: %d von %d Werten aus dem Lesespeicher der Anlage",
            self.host,
            uebernommen,
            len(gebraucht),
        )
        return uebernommen

    async def vorabstand(self, max_alter_min: int):
        """Erster Stand aus dem Lesespeicher, noch vor dem ersten Abruf.

        Zeitprogramme und Meldungen bleiben leer – sie stehen nicht im
        Speicher und kommen mit dem ersten Durchlauf.
        """
        if max_alter_min <= 0:
            return None
        bezugszeit = await self._steuerungszeit()
        if await self._startwerte_lesen(max_alter_min, bezugszeit) == 0:
            return None
        return {
            "devices": self.devices,
            "oids": dict(self._letzte_werte),
            "objects": {},
            "status": {},
        }

    async def _steuerungszeit(self):
        """Datum und Uhrzeit der Steuerung als ein Zeitpunkt.

        Die Zeitstempel des Lesespeichers stammen aus dieser Uhr. Gegen sie
        gerechnet stimmt das Alter auch dann, wenn sie falsch gestellt ist.
        """
        # Beide aus derselben Funktion: Eine Anlage mit mehreren Heizkreisen
        # führt den Namen mehrfach, und zwei Hälften verschiedener Herkunft
        # ergäben einen zusammengesetzten Zeitpunkt.
        adressen = {}
        for teile in self._nach_praefix().values():
            paar = {
                d["name"]: d["oid"]
                for d in teile.values()
                if d.get("name") in SYSTEMZEIT_NAMEN and d.get("oid")
            }
            if len(paar) == 2:
                adressen = paar
                break
        if not adressen:
            return None
        try:
            # Frist für beide zusammen: Der Vorabstand darf die Einrichtung
            # nicht aufhalten. Läuft sie ab, gilt die Serverzeit.
            gelesen = await asyncio.wait_for(
                asyncio.gather(
                    self._fetch_oid(adressen["Datum"]),
                    self._fetch_oid(adressen["Uhrzeit"]),
                ),
                timeout=UHR_TIMEOUT,
            )
        except Exception as err:
            _LOGGER.debug("Uhr der Steuerung nicht lesbar: %s", err)
            return None

        werte = {oid: wert for oid, wert in gelesen}
        tag = self._nach_format(werte.get(adressen["Datum"]), self._DATUMSFORMATE)
        stunde = self._nach_format(werte.get(adressen["Uhrzeit"]), self._UHRZEITFORMATE)
        if tag is None or stunde is None:
            _LOGGER.debug("Uhr der Steuerung in unbekannter Schreibweise")
            return None
        return datetime.combine(tag.date(), stunde.time())

    @staticmethod
    def _nach_format(roh, formate):
        """Text in ein Datum wandeln, das erste passende Format gewinnt."""
        if not isinstance(roh, str):
            return None
        for form in formate:
            try:
                return datetime.strptime(roh.strip(), form)
            except ValueError:
                continue
        return None

    @classmethod
    def _zeitstempel(cls, roh):
        """Zeitstempel des Lesespeichers in ein Datum wandeln."""
        if not isinstance(roh, str):
            return None
        try:
            return datetime.strptime(roh.strip(), cls._ZEITSTEMPEL)
        except ValueError:
            return None

    async def fetch_all(self, budget: float | None = None):
        """Poll the currently relevant OIDs in parallel and return coordinator data.

        Es werden nur die statisch aktiven (poll_oids) plus die von aktivierten
        Entities dynamisch angemeldeten OIDs abgefragt – nicht mehr blind alle
        entdeckten OIDs. Aus diesem Satz kommt je Durchlauf nur dran, was nach
        seiner Poll-Klasse fällig ist; der Rest behält seinen letzten Wert.

        `budget` ist die Zeit in Sekunden, die der Durchlauf haben darf. Ist
        sie aufgebraucht, endet er mit dem, was er gelesen hat, und nimmt den
        Rest in den nächsten Durchlauf mit. Ohne diese Grenze bricht der
        Coordinator einen zu großen Durchlauf ab: Alles Gelesene ist verloren,
        der Zähler der Poll-Klassen bleibt stehen – und derselbe zu große
        Durchlauf steht unverändert wieder an. Auf einer Anlage mit
        Serviceebene und mehreren Heizkreisen hörte das Abfragen so dauerhaft
        auf (#2).
        """
        if self.oids is None:
            # Fallback, falls async_init noch nicht lief (sollte nicht passieren).
            await self.async_init()

        poll_begonnen = time.monotonic()
        ende = poll_begonnen + budget if budget else None
        # Zeitprogramme und Status ändern sich selten und kosten je eine
        # eigene Anfrage – sie laufen im langsamen Takt mit. Sie kommen vor den
        # Werten an die Reihe: Sonst bliebe bei knapper Zeit für sie nie
        # welche übrig.
        langsamer_takt = self._takte()[POLL_SLOW]
        langsam_faellig = self._tick == 0 or self._tick % langsamer_takt == 0
        # Objekte entstehen erst im Vollabzug, also nach dem ersten Durchlauf.
        # Gezählt wird jede Adresse einzeln: Ein gelesenes Zeitprogramm sagt
        # nichts über einen Textwert, der erst später dazukommt.
        if any(
            d["oid"] not in self._objekte_versucht for d in self.time_programs + self.objekt_texte
        ):
            langsam_faellig = True
        if langsam_faellig:
            self._letzte_objekte = await self._fetch_time_programs()
        status = await self._fetch_status()
        faellig = self._faellig()
        results, self._rest = await self._lese_faellige(faellig, ende)

        # Ein misslungener Abruf ist kein Messwert: Der zuletzt gelesene Wert
        # bleibt stehen, und die Adresse ist im nächsten Durchlauf wieder
        # fällig – unabhängig von ihrer Poll-Klasse.
        misslungen = {oid for oid, wert in results if wert is FEHLGESCHLAGEN}
        gelesen = {oid: wert for oid, wert in results if wert is not FEHLGESCHLAGEN}
        # Dasselbe für einen Wert, der von bekannt auf leer springt: Unter Last
        # antwortet die Steuerung auf eine gültige Adresse schon einmal mit
        # ihrer Leermarke. Nachgelesen wird einmal; bleibt es leer, gilt es.
        verloren = {
            oid
            for oid, wert in gelesen.items()
            if wert is None and self._letzte_werte.get(oid) is not None
        }
        self._letzte_werte.update(gelesen)
        self._rest |= (misslungen | verloren) - self._abgemeldet
        # Abgemeldete Entities dürfen nicht ewig als alter Wert weiterleben.
        aktuell = self.abrufplan
        for oid in list(self._letzte_werte):
            if oid not in aktuell and oid not in self._object_texts:
                del self._letzte_werte[oid]

        self._tick += 1
        self.poll_count += 1
        self.poll_seconds += time.monotonic() - poll_begonnen
        werte = dict(self._letzte_werte)
        werte.update(self._object_texts)
        werte = self.ueberlagern(werte)
        return {
            "devices": self.devices,
            "oids": werte,
            "objects": dict(self._letzte_objekte),
            "status": status,
        }

    async def geraet_abfragen(self, device_id: str) -> dict:
        """Die zyklisch abgefragten Werte eines Anlagenteils sofort lesen.

        Nur diese, nicht jeden Datenpunkt: Ein Kessel führt mehrere hundert.
        """
        aktiv = self.abrufplan
        oids = [
            d["oid"]
            for d in self.devices
            if d.get("device_id") == device_id and d.get("oid") in aktiv
        ]
        if not oids:
            return {}
        return await self.fetch_oids(oids)
