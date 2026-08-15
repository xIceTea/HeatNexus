"""Windhager HTTP API client."""

import asyncio
import contextlib
import json
import logging
import re as _re
import time
from xml.etree import ElementTree

import aiohttp
from yarl import URL

from . import geraetetexte
from .const import (
    ADVANCED_LEVELS,
    ANFRAGE_TIMEOUT,
    DEFAULT_LEVELS,
    DEFAULT_USERNAME,
    ERKENNUNG_MIN_ANTEIL,
    ERKENNUNG_MIN_DATENPUNKTE,
    EXTRA_OIDS_BY_FCT,
    FCT_CLIMATE,
    FCT_ENTITY_MAP,
    FCT_IDS_UNGEMELDET,
    FCT_MODELL,
    FCT_NV,
    FETCH_CONCURRENCY,
    FINGERABDRUCK_MIN_TREFFER,
    GRUPPE_LAUFZEIT,
    GRUPPE_ZAEHLER,
    LAUFPHASEN,
    MENU_PAGE_SIZE,
    POLL_BLOCK,
    POLL_CONCURRENCY,
    POLL_EINHEITEN_TRAEGE,
    POLL_FAST,
    POLL_NORMAL,
    POLL_SLOW,
    POLL_TYPEN_SCHNELL,
    POLL_WOERTER_SCHNELL,
    POLL_WOERTER_TRAEGE,
    STARTZAEHLER,
    SYSTEMZEIT_NAMEN,
    TAGESWERTE,
    TAGESZAEHLER,
    UPDATE_INTERVAL,
    VERBINDUNG_TIMEOUT,
)
from .const import (
    ENUMS as ENUMS_FALLBACK,
)
from .device_db import get_enum, get_layers, get_name
from .helpers import READONLY_FALLBACK, lesetyp, messgroesse, poll_takte
from .kanonisch import schluessel as kanonischer_schluessel
from .lon import ist_eingang as lon_ist_eingang
from .lon import kennungsteil as lon_kennungsteil
from .lon import snvt as lon_snvt
from .lon import ungueltig as lon_ungueltig
from .lon import zuordnen as lon_zuordnen

_LOGGER = logging.getLogger(__name__)

# Rückgabe eines Abrufs, der die Anlage nicht erreicht hat. Zu unterscheiden
# von ``None``: Das ist die Auskunft der Anlage, dass sie keinen Wert führt.
FEHLGESCHLAGEN = object()

# Die Felder eines Datenpunkt-Deskriptors und ihre Vorgabe. Plattformen, Panel,
# Dashboard und Diagnose lesen sie; fehlt eines, fällt das erst dort auf.
DESKRIPTOR_VORGABE: dict = {
    "id": None,
    "alt_id": None,
    "oid": None,
    "name": None,
    "type": "auto",
    # Die Bedienebene, aus der der Datenpunkt stammt. `None` heißt: aus einer
    # kuratierten Tabelle, nicht aus einer Ebene der Anlage.
    "level": None,
    "enabled_default": True,
    "enum": None,
    "enum_texte": None,
    "unit": None,
    "device_class": None,
    "state_class": None,
    "kanonisch": None,
    "category": None,
    "icon": None,
    "min": None,
    "max": None,
    "step": None,
    "press_value": None,
    "write_prot": None,
    "nv_name": None,
    # Abgeleitete Werte: Bezugsadresse bzw. die Codes, die als Lauf gelten.
    "ausloeser_oid": None,
    "laufphasen": None,
    "gruppe": None,
    # Beim Einlesen meldete die Anlage keinen Wert – der Eingang ist frei.
    "leer_beim_einlesen": None,
    "device_id": None,
    "alt_device_id": None,
    "device_name": None,
    "fct_type": None,
}

# Klarere, gruppierende Namen für einzelne auto-entdeckte Datenpunkte.
# HA sortiert Entities auf der Geräteseite nach dem Namen – mit gemeinsamem
# Präfix landen zusammengehörige Werte (z.B. WW-Zirkulation) beieinander.
NAME_OVERRIDES = {
    "5/6": "WW-Zirkulationspumpe Modus",
    # 39/107 meldet, ob das Befüllen gerade freigegeben ist; die Anforderung
    # läuft über die Betriebswahl des Kessels. Ohne eigenen Namen hießen beide
    # gleich und bekämen ihre Adresse angehängt.
    "39/107": "Lagerraum befüllen Freigabe",
    "39/5": "Lagerraumbefüllung Restlaufzeit",
    "5/70": "WW-Zirkulation Einschaltzeit",
    "5/71": "WW-Zirkulation Ausschaltzeit",
}


# Adressangaben in der statischen Navigation der Steuerung. Zwei Schreibweisen
# für dasselbe: `oidextension="4/80/0"` in der Zuordnung, `gnmn="03:61"` in der
# Navigation selbst.
_STATISCHE_ADRESSE = _re.compile(r"^0*(\d+)[:/]0*(\d+)(?:/\d+)?$")


def _statische_positionen(xml: str) -> set[str]:
    """Adressen aus einer Ressourcendatei der statischen Navigation lesen.

    Die Steuerung führt einige Datenpunkte ausschließlich hier – der Menü-Abzug
    kennt sie nicht. Gelesen wird jedes Element, das eine Adresse trägt; welche
    Art dahinter steckt, entscheidet später die Metadatenabfrage.

    Fehlt oder taugt die Datei nichts, bleibt die Menge leer: Die Erkennung
    verliert dann nur diese Ergänzung, statt abzubrechen.
    """
    try:
        wurzel = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return set()

    positionen = set()
    for element in wurzel.iter():
        for schluessel in ("oidextension", "gnmn"):
            if (treffer := _STATISCHE_ADRESSE.match(element.get(schluessel, ""))) is not None:
                positionen.add(f"{treffer.group(1)}/{treffer.group(2)}")
    return positionen


def _ist_zeitprogramm(wert) -> bool:
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


class WindhagerHttpClient:
    """Raw API HTTP requests."""

    def __init__(
        self,
        host,
        password,
        levels: list | None = None,
        enable_advanced: bool = False,
        writable_advanced: bool = False,
        zeitwerte: bool = False,
        zusatzwerte: list[str] | None = None,
        lon: bool = False,
        username: str | None = None,
        update_interval: int = UPDATE_INTERVAL,
        sprache: str = "de",
    ) -> None:
        self.host = host
        self.password = password
        # Abfrageintervall des Coordinators. Es bestimmt, wie oft eine träge
        # Poll-Klasse überhaupt an die Reihe kommen kann.
        self.update_interval = int(update_interval or UPDATE_INTERVAL)
        # Die Anlage kennt zwei Zugänge mit unterschiedlichem Umfang: „USER"
        # sieht Info- und Betreiberebene, „Service" zusätzlich die
        # Fachparameter. Welcher gilt, entscheidet der Nutzer bei der
        # Einrichtung.
        self.username = username or DEFAULT_USERNAME
        # Welche Bedienebenen überhaupt angelegt werden (Auswahl bei der
        # Einrichtung). Service- und Werksebene gelten als "fortgeschritten":
        # ihre Entities sind nur auf Wunsch aktiv bzw. bedienbar.
        self.levels = list(levels or DEFAULT_LEVELS)
        self.enable_advanced = enable_advanced
        self.writable_advanced = writable_advanced
        # Ob Uhrzeit- und Datumsfelder von sich aus aktiv sind.
        self.zeitwerte = zeitwerte
        # Kennungen der abgeleiteten Werte, die der Nutzer angekreuzt hat.
        self.zusatzwerte = set(zusatzwerte or ())
        # Was zur Auswahl stünde – auch das Nichtgewählte, sonst bliebe der
        # Auswahldialog leer.
        self.zusatzkandidaten: list[dict] = []
        self.lon = lon
        # In welcher Sprache das Textwerk der Steuerung gelesen wird, und was
        # sie geliefert hat. Vor dem ersten Erkennungslauf ist es leer.
        self.sprache = sprache or "de"
        self._texte = geraetetexte.Texte()
        self.oids: set | None = None
        self.devices: list[dict] = []
        # Was die Steuerung über sich selbst sagt (Modell, Firmwarestand).
        # Leer, solange sie nicht gefragt wurde oder den Endpunkt nicht kennt.
        self.geraeteinfo: dict = {}
        # nodeId -> Werksbezeichnung des Bausteins, aus `nodes`.
        self.werksbezeichnung: dict[str, str] = {}
        # nodeId -> neuronId (Seriennummer des Bausteins). Grundlage aller
        # dauerhaften Kennungen; wird bei der Discovery aus /1 gefüllt.
        self.neuron_by_node: dict[str, str] = {}
        # Metadaten aus den Menü-Ebenen: OID -> vollständiger Datenpunkt.
        # Damit entfällt für diese OIDs die einzelne Metadaten-Abfrage.
        self.menu_meta: dict = {}
        # OID -> (prefix, menu_id, Position in der Ebene) für den Sammelabruf.
        # Statisch immer gepollte OIDs (aktive Entities + Climate).
        self.poll_oids: set = set()
        # Dynamisch von tatsächlich aktivierten Entities registrierte OIDs
        # (z.B. eine vom Nutzer eingeschaltete Service-Entity).
        self._dynamic_oids: set = set()
        # Wie viele Entitäten eine dynamisch angemeldete Adresse brauchen.
        self._oid_nutzer: dict[str, int] = {}
        # Zeitprogramme (typeId 30) werden nicht über lookup, sondern über den
        # object-Endpunkt gelesen. Liste der Programm-Deskriptoren + Flag, ob
        # das Gerät den object-Endpunkt lokal unterstützt (None = noch ungetestet).
        self.time_programs: list[dict] = []
        self._objects_supported: bool | None = None
        # Objekte mit einfachem Textwert (z.B. Modulinfo, Softwarestand).
        # Sie werden wie normale Werte behandelt, nicht als Zeitprogramm.
        self._object_texts: dict = {}
        # Poll-Klasse je OID und Zähler der Abrufdurchläufe. Zusammen sorgen
        # sie dafür, dass träge Werte nicht im 30-Sekunden-Takt gelesen werden.
        self.poll_class: dict[str, str] = {}
        self._tick = 0
        # Was im letzten Durchlauf nicht mehr in die Zeit passte. Es kommt im
        # nächsten zuerst dran, sonst stünden dieselben Werte immer hinten an.
        self._rest: set[str] = set()
        # Datenpunkte, die die Anlage ablehnt (404, oder 409 mit unbekannter
        # Kennung). Sie werden nicht wieder angefragt.
        self._abgemeldet: set[str] = set()
        # Ob diese Steuerung eine ganze Menü-Ebene auf einmal liefert. Unbekannt
        # bis zum ersten Versuch; danach wird nicht mehr vergeblich gefragt.
        self._sammelseite: bool | None = None
        self._letzte_werte: dict[str, str | None] = {}
        self._letzte_objekte: dict = {}
        # Anzahl der Anfragen an die Anlage (für die Startmeldung)
        self.request_count = 0
        # Abfragestatistik: Ohne Zahlen ist jede Optimierung geraten. Gezählt
        # werden alle Anfragen, ihre Gesamtdauer und die Fehlschläge; die
        # Diagnose rechnet daraus Mittelwert und Anfragen je Stunde.
        self.request_seconds = 0.0
        self.queue_seconds = 0.0
        self.request_errors = 0
        # Abgewiesene Anfragen in Folge (401/403). Erst wenn es mehrere sind,
        # ist es wirklich das Passwort und nicht ein verbrauchter Nonce.
        self.auth_errors = 0
        self.poll_count = 0
        self.poll_seconds = 0.0
        # Was der letzte Durchlauf gekostet hat – geht in die Diagnose ein.
        self._poll_anfragen = 0
        self.gestartet = time.monotonic()
        # Ist der vollständige Abzug (Menü-Ebenen) bereits gelaufen?
        self._vollstaendig = False
        self._session = None
        self._semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)
        # Für das zyklische Abrufen einzelner Werte gilt eine eigene, höhere
        # Grenze: Dort sind die Antworten klein, und die Warteschlange war der
        # Flaschenhals, nicht die Anlage.
        self._poll_semaphore = asyncio.Semaphore(POLL_CONCURRENCY)

    @property
    def erster_abruf(self) -> bool:
        """Sagen, ob der erste Abruf noch aussteht.

        Er ist der größte: Solange kein Wert dasteht, ist jede Poll-Klasse
        fällig – auch die trägen, die sonst nur jeden fünfzehnten Durchlauf
        drankommen. Er braucht deshalb ein größeres Zeitfenster als der Takt
        danach.
        """
        return self._tick == 0

    # ------------------------------------------------------------------
    # Dynamische Poll-Registrierung
    # ------------------------------------------------------------------

    # Je schneller die Klasse, desto kleiner der Rang.
    _KLASSEN_RANG = {POLL_FAST: 0, POLL_NORMAL: 1, POLL_SLOW: 2}

    @classmethod
    def _klasse_eintragen(cls, klassen: dict[str, str], oid: str, klasse: str) -> None:
        """Teilen sich mehrere Deskriptoren eine Adresse, gilt die schnellste.

        Ein abgeleiteter Wert ist abgeschaltet und damit träge eingestuft; er
        darf seine Quelle nicht ausbremsen.
        """
        if cls._KLASSEN_RANG.get(klasse, 9) < cls._KLASSEN_RANG.get(klassen.get(oid, ""), 9):
            klassen[oid] = klasse

    def register_poll_oid(self, oid: str) -> None:
        """Eine Entity meldet ihre OID zum zyklischen Polling an."""
        if oid and oid not in self._abgemeldet:
            self._dynamic_oids.add(oid)
            self._oid_nutzer[oid] = self._oid_nutzer.get(oid, 0) + 1

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

    async def _ensure_session(self):
        """Sitzung mit Digest-Authentifizierung bereitstellen.

        Die Anmeldung übernimmt aiohttp selbst (ab 3.12, in Home Assistant ab
        2025.6).

        `preemptive=True` schickt die Anmeldung nach der ersten Antwort gleich
        mit, statt sich jedes Mal einen `401` abzuholen. Bei einer Steuerung,
        die pro Abruf dutzende Anfragen bekommt, ist das die halbe Last.
        """
        if self._session is None:
            self._session = aiohttp.ClientSession(
                # Ohne eigene Grenze wartet aiohttp fünf Minuten auf eine
                # Antwort. `sock_connect` trennt dabei die nicht erreichbare
                # Anlage von der, die annimmt und dann schweigt.
                timeout=aiohttp.ClientTimeout(
                    total=ANFRAGE_TIMEOUT, sock_connect=VERBINDUNG_TIMEOUT
                ),
                connector=aiohttp.TCPConnector(
                    # Mehr Verbindungen als gleichzeitige Anfragen bringen
                    # nichts: Die Steuerung ist der Engpass, nicht das Netz.
                    # Ohne eigene Grenze macht aiohttp bis zu 100 auf.
                    limit=FETCH_CONCURRENCY + POLL_CONCURRENCY,
                    limit_per_host=FETCH_CONCURRENCY + POLL_CONCURRENCY,
                    # Der C-Auflöser (aiodns) verlangt unter Windows eine
                    # bestimmte Ereignisschleife und bricht sonst ab. Er brächte
                    # hier ohnehin nichts – die Anlage steht unter einer festen
                    # Adresse, meist einer IP.
                    resolver=aiohttp.ThreadedResolver(),
                ),
                middlewares=(
                    aiohttp.DigestAuthMiddleware(login=self.username, password=self.password),
                ),
            )

    async def close(self):
        """Close the client session."""
        if self._session:
            await self._session.close()
            self._session = None

    # Zeichensätze in der Reihenfolge, in der sie ausprobiert werden.
    # cp850 ist die DOS-Codepage der Steuerung: dort liegt „ü" auf 0x81,
    # einem in CP1252 gar nicht belegten Byte. Ohne cp850 in der Kette
    # verlieren von Hand vergebene Namen ihre Umlaute.
    _ZEICHENSAETZE = ("utf-8", "cp1252", "cp850")

    @classmethod
    def _decode(cls, raw: bytes) -> str:
        """Antwort dekodieren.

        Die Anlagen liefern Text nicht durchgängig als UTF-8: von Hand
        vergebene Funktionsnamen kommen im Zeichensatz der Steuerung zurück.
        Ohne passenden Rückfall stünden Fragezeichen in Geräte- und
        Entitätsnamen.
        """
        for zeichensatz in cls._ZEICHENSAETZE:
            try:
                return raw.decode(zeichensatz)
            except UnicodeDecodeError:
                continue
        # latin-1 kann jedes Byte abbilden und schlägt daher nie fehl.
        _LOGGER.debug("Antwort in keinem bekannten Zeichensatz lesbar, nutze latin-1")
        return raw.decode("latin-1")

    async def _get(self, url: str, semaphore=None):
        """GET auf die Anlage; gibt (json_oder_None, status) zurück.

        Gemessen wird die reine Antwortzeit der Anlage – **innerhalb** der
        Warteschlange. Wird die Wartezeit mitgezählt, misst man bei drei
        gleichzeitigen Anfragen und zweihundert Aufträgen nur noch die eigene
        Warteschlange und hält eine schnelle Anlage für langsam.
        """
        await self._ensure_session()
        self.request_count += 1
        angefragt = time.monotonic()
        async with semaphore or self._semaphore:
            begonnen = time.monotonic()
            self.queue_seconds += begonnen - angefragt
            try:
                ret = await self._session.request("GET", url)
                raw = await ret.read()
            except Exception:
                self.request_errors += 1
                raise
            finally:
                self.request_seconds += time.monotonic() - begonnen
        # Ein `401`, der bis hierher durchkommt, ist die Auskunft der Anlage,
        # dass das Passwort nicht stimmt – die Aufforderung selbst hat aiohttp
        # schon beantwortet. Gezählt wird beides, damit ein einzelner
        # verbrauchter Digest-Nonce nicht gleich nach dem Passwort fragen lässt.
        if ret.status in (401, 403):
            self.auth_errors += 1
        else:
            self.auth_errors = 0
        try:
            return json.loads(self._decode(raw)), ret.status
        except ValueError:
            return None, ret.status

    # Ressourcendateien der statischen Navigation. Die erste ordnet die
    # Positionen den Funktionsarten zu, die zweite benennt sie; welche eine
    # Steuerung ausliefert, hängt an ihrer Fassung.
    _STATISCHE_RESSOURCEN = ("xml/StaticNavAssignment.xml", "xml/StaticNav.xml")

    async def _ressource(self, pfad: str) -> str | None:
        """Eine Ressourcendatei der Anlage als Text lesen (`/res/<pfad>`).

        Gibt ``None`` zurück, wenn die Anlage sie nicht kennt – diese Dateien
        sind eine Zugabe, kein Teil der Datenschnittstelle.
        """
        try:
            await self._ensure_session()
            async with self._semaphore:
                ret = await self._session.request("GET", f"http://{self.host}/res/{pfad}")
                if ret.status != 200:
                    return None
                return self._decode(await ret.read())
        except Exception as fehler:
            _LOGGER.debug("Ressource %s nicht lesbar: %s", pfad, fehler)
            return None

    async def _lade_geraetetexte(self) -> geraetetexte.Texte:
        """Das Textwerk der Steuerung lesen.

        Die Klartexte der Datenpunkte passen zur Fassung der Anlage und zur
        gewählten Sprache; die mitgelieferte Datenbank kennt nur Deutsch.

        Wie die statischen Positionen gehört das **nicht** in den
        Kurzdurchlauf: Der soll mit wenigen Anfragen stehen.
        """
        return await geraetetexte.laden(self._ressource, self.sprache)

    async def _statische_adressen(self) -> set[str]:
        """Positionen ermitteln, die die Anlage außerhalb der Menüs führt.

        Die Menü-Abfrage ist die Hauptquelle der Erkennung, aber nicht die
        einzige: Sonderzeitprogramm, Störspeicher und Passwort stehen in keiner
        Menü-Ebene. Die Anlage benennt sie selbst, deshalb steht hier keine
        gepflegte Liste – eine neuere Fassung bringt ihre Ergänzungen mit.
        """
        dateien = await asyncio.gather(
            *(self._ressource(pfad) for pfad in self._STATISCHE_RESSOURCEN)
        )
        adressen: set[str] = set()
        for xml in dateien:
            if xml:
                adressen |= _statische_positionen(xml)
        _LOGGER.debug("Statische Navigation nennt %d Positionen", len(adressen))
        return adressen

    async def fetch(self, url, semaphore=None):
        """GET /api/1.0/lookup<url> and return the parsed JSON."""
        data, _status = await self._get(f"http://{self.host}/api/1.0/lookup{url}", semaphore)
        _LOGGER.debug("Fetched data for %s: %s", url, data)
        return data

    async def _lese_geraeteinfo(self) -> None:
        """Modell und Firmwarestand der Steuerung holen.

        Eine Anfrage, und die einzige Stelle, an der sich die Steuerung
        maschinenlesbar zu erkennen gibt: `lookup /1` nennt nur die Knoten.
        Ältere Fassungen kennen den Endpunkt nicht – dann bleibt die Auskunft
        leer und die Geräteseite zeigt weiterhin nur „Steuerung".
        """
        daten, status = await self._get(f"http://{self.host}/api/1.0/info/deviceinfo")
        self.geraeteinfo = daten if status == 200 and isinstance(daten, dict) else {}

    async def _lese_knotendaten(self) -> None:
        """Die Werksbezeichnung je Knoten holen.

        `lookup /1` nennt unter `device` nur eine Zahl und unter `name` den
        vergebenen Namen; `nodes` nennt zusätzlich, wie der Hersteller den
        Baustein nennt. Für Baureihen, die die kuratierte Tabelle nicht kennt,
        ist das die einzige belastbare Modellangabe.
        """
        daten, status = await self._get(f"http://{self.host}/api/1.0/nodes")
        if status != 200 or not isinstance(daten, list):
            self.werksbezeichnung = {}
            return
        self.werksbezeichnung = {
            str(knoten["nodeId"]): str(bezeichnung).strip()
            for knoten in daten
            if isinstance(knoten, dict)
            and knoten.get("nodeId") is not None
            and (bezeichnung := (knoten.get("device") or {}).get("name"))
        }

    async def probe(self):
        """Verbindung prüfen: Anlagenstruktur und HTTP-Status zurückgeben.

        Wird vom Einrichtungsdialog benutzt, damit dort zwischen „nicht
        erreichbar" und „Passwort falsch" unterschieden werden kann.
        """
        return await self._get(f"http://{self.host}/api/1.0/lookup/1")

    # ------------------------------------------------------------------
    # Sammel-Lesezugriff über Menü-Ebenen
    # ------------------------------------------------------------------
    async def _read_menu(
        self, prefix: str, menu_id: str, expected: int, gewuenscht, schluessel: str = "OID"
    ) -> list:
        """Eine Menü-Ebene lesen, soweit sie gebrauchte Datenpunkte enthält.

        Ein Abruf liefert höchstens MENU_PAGE_SIZE Datenpunkte; weitere holt
        das Gerät über ?offset=<n>. Jeder Eintrag enthält bereits Wert und
        Metadaten, ein zusätzlicher Einzelabruf entfällt damit.

        Enthält die erste Seite keinen einzigen Datenpunkt der gewählten
        Bedienebenen, werden die restlichen Seiten übersprungen. Die großen
        Werksebenen-Menüs des Kessels umfassen bis zu 95 Datenpunkte – das
        spart bei abgewählter Werksebene den Großteil der Anfragen.

        `schluessel` sagt, woran ein Eintrag zu erkennen ist. Im LON-Adressraum
        führen die Einträge keine `OID`, sondern einen `nvIndex`; das
        Seitenprotokoll ist dasselbe und steht deshalb nur hier.
        """
        base = f"http://{self.host}/api/1.0/lookup{prefix}/{menu_id}"
        items: list = []
        seen: set = set()
        offset = 0

        def brauchbar(eintrag) -> bool:
            return isinstance(eintrag, dict) and eintrag.get(schluessel) is not None

        # Das Bedienteil der Anlage fordert mit count=-1 alle Einträge einer
        # Ebene auf einmal an. Es gibt Steuerungen, die darauf mit einer leeren
        # Liste antworten; dort wird nach dem ersten Versuch geblättert.
        if expected > MENU_PAGE_SIZE and self._sammelseite is not False:
            data, status = await self._get(f"{base}?count=-1&offset=0")
            if status == 200 and isinstance(data, list):
                # Eine Antwort zählt, ein Fehler nicht: Sonst schaltete eine
                # einzelne Störung das Sammeln dauerhaft ab.
                self._sammelseite = len(data) > MENU_PAGE_SIZE
                if self._sammelseite:
                    return [i for i in data if brauchbar(i)]

        while True:
            url = base if offset == 0 else f"{base}?offset={offset}"
            data, status = await self._get(url)
            if status != 200 or not isinstance(data, list) or not data:
                break
            fresh = [i for i in data if brauchbar(i) and i[schluessel] not in seen]
            if not fresh:
                break
            items.extend(fresh)
            seen.update(i[schluessel] for i in fresh)
            if len(items) >= expected or len(data) < MENU_PAGE_SIZE:
                break
            if (
                offset == 0
                and gewuenscht is not None
                and not any(gewuenscht(self._gnmn(prefix, i[schluessel])) for i in fresh)
            ):
                _LOGGER.debug(
                    "Menü %s/%s übersprungen: keine Datenpunkte der gewählten Ebenen",
                    prefix,
                    menu_id,
                )
                break
            offset += MENU_PAGE_SIZE

        if expected and len(items) < expected:
            _LOGGER.debug(
                "Menü %s/%s: %d von %d Datenpunkten gelesen", prefix, menu_id, len(items), expected
            )
        return items

    @staticmethod
    def _ebene_ohne_antwort(prefix: str, menu_id: str, fehler: BaseException) -> None:
        """Eine Menü-Ebene ohne Antwort: übergehen oder den Lauf abbrechen.

        Eine Zeitüberschreitung kostet nur ihre Ebene. Alles andere ist ein
        Fehler der Verbindung; ihn zu verschlucken hieße, einen halben
        Erkennungsstand als vollständig zu speichern.
        """
        if not isinstance(fehler, TimeoutError):
            raise fehler
        _LOGGER.warning("Menü %s/%s antwortet nicht und wird übergangen", prefix, menu_id)

    def _typ_aus_datenpunkten(self, prefix: str, menu_data: dict) -> int | None:
        """Den Funktionstyp aus den gefundenen Adressen erschließen.

        Für eine Funktion, die `GET /1` nicht meldet, gibt es keinen `fctType`
        – und ohne ihn greift weder die kuratierte Tabelle noch die
        Ebenenzuordnung. Die Datenpunkte selbst sind aber kennzeichnend genug:
        Verglichen wird, welcher Anteil einer kuratierten Tabelle sich
        wiederfindet.

        Entschieden wird nach Anteil, nicht nach Trefferzahl, und erst ab
        `FINGERABDRUCK_MIN_TREFFER` Treffern – die Begründung für beides steht
        an der Konstanten.
        """
        vorhanden = {self._gnmn(prefix, oid) for oid in menu_data}
        if not vorhanden:
            return None

        bester: tuple[float, int, int] | None = None
        for fct_type, eintraege in FCT_ENTITY_MAP.items():
            tabelle = {d["oid"].strip("/").rsplit("/", 1)[0] for d in eintraege}
            treffer = len(tabelle & vorhanden)
            if treffer < FINGERABDRUCK_MIN_TREFFER:
                continue
            wertung = (treffer / len(tabelle), treffer, fct_type)
            if bester is None or wertung > bester:
                bester = wertung
        if bester is None:
            return None

        anteil, treffer, fct_type = bester
        _LOGGER.info(
            "%s ist in der Struktur nicht gemeldet, nach seinen Datenpunkten "
            "aber Funktionstyp %s (%s von %s Adressen, %.0f %%)",
            prefix,
            fct_type,
            treffer,
            len(FCT_ENTITY_MAP[fct_type]),
            anteil * 100,
        )
        return fct_type

    async def _ungemeldete_funktionen(self, device_id: str, gemeldet: list[dict]) -> list[dict]:
        """Funktionen suchen, die der Knoten hat, aber nicht meldet.

        **Ein Knoten kann antworten, ohne sich anzukündigen.** Es gibt Anlagen,
        deren Kessel in `GET /1` ausschließlich seinen LON-Adressraum führt und
        keine Funktion mit `fctType`. Die Datenpunkte darunter antworten
        trotzdem – vollständig, mit Metadaten und Werten. Wer nur die
        gemeldeten Funktionen liest, hält so einen Kessel für nicht vorhanden
        und legt für ihn keine einzige Entität an.

        Geprüft wird nur, wenn der Knoten gar keine brauchbare Funktion meldet;
        an einem Knoten mit gemeldeter Funktion wäre es geraten.
        """
        vergeben = {f.get("fctId") for f in gemeldet}
        gefunden = []
        for fct_id in FCT_IDS_UNGEMELDET:
            if fct_id in vergeben:
                continue
            prefix = f"{device_id}/{fct_id}"
            menu_data = await self._read_function_menus(prefix, None)
            if not menu_data:
                continue
            fct_type = self._typ_aus_datenpunkten(prefix, menu_data)
            if fct_type is None:
                _LOGGER.debug("%s antwortet, passt aber zu keiner bekannten Bauart", prefix)
                continue
            gefunden.append(
                {
                    "fctId": fct_id,
                    "fctType": fct_type,
                    "name": FCT_MODELL.get(fct_type, f"Funktion {fct_type}"),
                    "_menus": menu_data,
                }
            )
        return gefunden

    async def _menue_ebenen(self, prefix: str) -> dict[str, int] | None:
        """Die Menü-Ebenen einer Funktion und ihre angekündigte Länge.

        ``None``, wenn die Funktion keine Menüliste liefert – ältere Firmware
        kennt sie nicht, dann greifen Einzelabfragen.
        """
        # Ein Knoten, der die Verbindung annimmt und dann schweigt, gilt als
        # ohne Menüliste. Der Rest der Anlage wird deswegen nicht aufgegeben.
        try:
            root, status = await self._get(f"http://{self.host}/api/1.0/lookup{prefix}")
        except TimeoutError:
            _LOGGER.warning("%s antwortet nicht und wird übergangen", prefix)
            return None
        if status != 200 or not isinstance(root, list) or not root:
            return None
        if not isinstance(root[0], dict) or "id" not in root[0]:
            return None
        return {str(m.get("id")): int(m.get("count") or 0) for m in root}

    async def _read_function_menus(self, prefix: str, fct_type: int | None) -> dict:
        """Alle Datenpunkte einer Funktion über ihre Menü-Ebenen einlesen."""
        menus = await self._menue_ebenen(prefix)
        if menus is None:
            return {}

        layers = get_layers(fct_type) or {}
        interessant = {g for lvl in self.levels for g in layers.get(lvl, [])}
        # Kuratierte Datenpunkte und bekannte Ausnahmen zählen immer dazu.
        interessant.update(
            d["oid"].strip("/").rsplit("/", 1)[0] for d in FCT_ENTITY_MAP.get(fct_type, [])
        )
        interessant.update(EXTRA_OIDS_BY_FCT.get(fct_type, ()))
        pruefer = interessant.__contains__ if interessant else None

        results = await asyncio.gather(
            *(self._read_menu(prefix, menu_id, count, pruefer) for menu_id, count in menus.items()),
            return_exceptions=True,
        )
        datapoints: dict = {}
        for menu_id, items in zip(menus, results, strict=True):
            if isinstance(items, BaseException):
                self._ebene_ohne_antwort(prefix, menu_id, items)
                continue
            for item in items:
                oid = item.get("OID")
                if oid:
                    datapoints[oid] = item
        _LOGGER.debug("%s: %d Datenpunkte aus %d Menü-Ebenen", prefix, len(datapoints), len(menus))
        return datapoints

    async def _lese_nv(
        self,
        prefix: str,
        ziel_prefix: str | None = None,
        ziel_name: str | None = None,
        ziel_typ: int | None = None,
    ) -> None:
        """Die Netzwerkvariablen eines Knotens als Deskriptoren anlegen.

        Was die Anlage hier führt, hängt nicht an ihrer Baureihe: Die Namen
        kommen aus den Funktionsblöcken des Bus und bedeuten überall dasselbe.
        Für eine Steuerung, für die es keine gepflegte Adresstabelle gibt, ist
        das die einzige Quelle benannter Werte.

        Ab Werk aktiv ist nur, was `lon.py` kennt; alles andere wird angelegt
        und bleibt deaktiviert. Geschrieben wird nichts – die `nvi`-Variablen
        sind Eingänge der Regelung zwischen den Knoten, keine Bedienung.
        """
        ebenen = await self._menue_ebenen(prefix)
        if not ebenen:
            return

        gelesen = await asyncio.gather(
            *(
                self._read_menu(prefix, menu_id, anzahl, None, schluessel="nvIndex")
                for menu_id, anzahl in ebenen.items()
            ),
            return_exceptions=True,
        )
        for menu_id, items in zip(ebenen, gelesen, strict=True):
            if isinstance(items, BaseException):
                self._ebene_ohne_antwort(prefix, menu_id, items)
                continue
            for item in items:
                self._nv_deskriptor(prefix, menu_id, item, ziel_prefix, ziel_name, ziel_typ)

    def _nv_deskriptor(
        self,
        prefix: str,
        menu_id: str,
        item: dict,
        ziel_prefix: str | None = None,
        ziel_name: str | None = None,
        ziel_typ: int | None = None,
    ) -> None:
        """Einen Deskriptor aus einem Eintrag des LON-Adressraums bauen."""
        index = item.get("nvIndex")
        oid = f"{prefix}/{menu_id}/{index}/0"
        if oid in self.oids:
            return
        nv_name = item.get("nvName") or ""
        eintrag = lon_zuordnen(nv_name)
        knoten = prefix.strip("/").split("/")[1]

        # Was der LonMark-Typ über den Wert sagt. Er steht an jedem Eintrag und
        # gilt über Baureihen hinweg – die Namenstabelle entscheidet nur noch
        # über den Begriff, die Größe kommt von hier.
        typ = lon_snvt(item.get("snvtName"))
        if typ.get("verwaltung"):
            # Dateiverzeichnis und Anforderungs-Eingang sind Innenleben des
            # Bus. Als Entität wären sie eine Zeile, die niemand deuten kann.
            return

        # Die Metadaten stehen schon im Eintrag; ein Einzelabruf entfällt
        # damit. `writeProt` setzt der Client selbst – die Anlage meldet für
        # Netzwerkvariablen keinen Schreibschutz, geschrieben wird trotzdem
        # nicht. Die Einheit aus dem Typ springt nur ein, wo die Anlage keine
        # nennt.
        meta = {**item, "writeProt": True}
        if not meta.get("unit") and typ.get("unit"):
            meta["unit"] = typ["unit"]
        self.menu_meta[oid] = meta

        self.devices.append(
            self._deskriptor(
                id=f"{self._neuron(knoten)}-{lon_kennungsteil(nv_name, menu_id, index)}",
                alt_id=self._alte_kennung(oid),
                oid=oid,
                # Das Kürzel bleibt am Namen, auch beim kuratierten Wert: Wer
                # den Bus einschaltet und danach aufräumen will, filtert in der
                # Entitätsliste nach „LON" und sieht auf einen Blick, was von
                # dort kommt. Es steht auch in der Entitäts-ID.
                name=f"{eintrag['name'] if eintrag else nv_name or f'Netzwerkvariable {index}'} (LON)",
                # Netzwerkvariablen stehen in keiner Bedienebene der Anlage –
                # weder Info noch Service. Sie eine zu nennen, um durch den
                # Umfangsfilter zu kommen, wäre eine falsche Auskunft an alles,
                # was später nach Ebenen unterscheidet; den Filter durchlaufen
                # sie ohnehin nicht. Über ihre Sichtbarkeit entscheidet
                # `enabled_default`. Eine eigene Herkunft statt gar keiner:
                # `None` zählte die Diagnose unter dem Schlüssel `null`.
                level="lon",
                # Ab Werk aktiv ist nur ein benannter **Ausgang**. Der Eingang
                # daneben führt dieselbe Zahl, und Unbenanntes taugt ohne
                # Nachsehen zu nichts.
                enabled_default=bool(eintrag) and not lon_ist_eingang(nv_name),
                state_class=(eintrag or {}).get("state_class") or typ.get("state_class"),
                kanonisch=eintrag.get("kanonisch") if eintrag else None,
                category=None if eintrag and not typ.get("diagnose") else "diagnostic",
                write_prot=True,
                nv_name=nv_name,
                device_id=self._geraetekennung(ziel_prefix or prefix),
                alt_device_id=self._alte_kennung(ziel_prefix or prefix),
                # Ein Knoten ohne brauchbare Funktion trägt keinen Namen, den
                # man anzeigen möchte („NV's"). Dann nennt ihn die Anlage
                # selbst: die Werksbezeichnung des Bausteins, beim Bedienteil
                # „MB6611 LOP". Fehlt auch die, bleibt die Knotennummer – sie
                # ist wenigstens wahr, während „Bedienteil" bei jedem zweiten
                # Busgerät danebenläge.
                device_name=ziel_name or self.werksbezeichnung.get(knoten) or f"Knoten {knoten}",
                fct_type=ziel_typ if ziel_prefix else FCT_NV,
            )
        )
        self.oids.add(oid)

    async def _nv_ohne_fuehler_verwerfen(self) -> None:
        """Netzwerkvariablen ohne angeschlossenen Fühler gar nicht erst anlegen.

        Die Menü-Ebene liefert für sie keinen Wert (`"value": "-"`); erst ein
        Einzelabruf zeigt, ob etwas daranhängt. An der eigenen Anlage standen
        vier von siebzehn dauerhaft auf der Ungültig-Marke – in der Geräteliste
        Zeilen, die für immer „nicht verfügbar" sagen.

        Kostet einmalig eine Anfrage je Netzwerkvariable und läuft im
        Hintergrundabzug, nie in der Einrichtung.
        """
        nv = [d for d in self.devices if d.get("nv_name") and d.get("oid")]
        if not nv:
            return
        werte = await self.fetch_oids([d["oid"] for d in nv])
        ohne_fuehler = {d["oid"] for d in nv if lon_ungueltig(werte.get(d["oid"]))}
        if not ohne_fuehler:
            return
        _LOGGER.debug("%d Netzwerkvariablen ohne Fühler verworfen", len(ohne_fuehler))
        self.devices = [d for d in self.devices if d.get("oid") not in ohne_fuehler]
        self.oids -= ohne_fuehler

    def _nv_doppelte_stilllegen(self) -> None:
        """Netzwerkvariablen abschalten, deren Begriff schon einen Datenpunkt hat.

        Von 95 brauchbaren Werten einer fremden BioWIN hatten 46 eine
        Entsprechung im OID-Raum. Beide anzuzeigen hieße, dieselbe Größe
        zweimal zu führen – und niemand könnte sagen, welche der beiden gilt.

        Entschieden wird über den kanonischen Schlüssel, nicht über einen
        Wertevergleich: Zwei Zahlen sind auch dann gleich, wenn die Anlage
        gerade steht.

        Läuft **nach** den Metadaten, nicht am Ende der Erkennung: Bis dahin
        stehen auch die kuratierten Datenpunkte in der Liste, die diese Anlage
        gar nicht führt. Ein Kessel ohne den Zähler `2/81` verlöre sonst die
        Betriebsstunden aus dem LON-Raum an einen Datenpunkt, den es hier
        nicht gibt.
        """
        belegt = {
            kanonischer_schluessel(d.get("id"))
            for d in self.devices
            if not d.get("nv_name") and d.get("oid")
        }
        belegt.discard(None)
        for d in self.devices:
            if d.get("nv_name") and d.get("kanonisch") in belegt:
                d["enabled_default"] = False

    async def update(self, oid, value):
        """PUT a new value to a datapoint."""
        await self._ensure_session()
        async with self._semaphore:
            ret = await self._session.request(
                "PUT",
                f"http://{self.host}/api/1.0/datapoint",
                data=bytes(f'{{"OID":"{oid}","value":"{value}"}}', "utf-8"),
            )
            if ret.status >= 400:
                body = await ret.text()
                _LOGGER.error("Write to %s failed with HTTP %s: %s", oid, ret.status, body)
                raise aiohttp.ClientResponseError(
                    ret.request_info,
                    ret.history,
                    status=ret.status,
                    message=f"Write to {oid} rejected by device",
                )
        _LOGGER.debug("Wrote %s = %s", oid, value)

    @staticmethod
    def slugify(identifier_str):
        return identifier_str.replace(".", "-").replace("/", "-")

    # ------------------------------------------------------------------
    # Kennungen
    # ------------------------------------------------------------------
    # Jeder Knoten meldet in der Struktur eine `neuronId` – die Seriennummer
    # seines Bausteins. Sie bleibt gleich, wenn die Anlage eine andere
    # IP-Adresse bekommt, und ist damit die einzige tragfähige Grundlage für
    # dauerhafte Kennungen. Nur wenn ein Knoten keine meldet, bleibt die
    # Adresse als Notnagel.
    def _neuron(self, node_id: str) -> str:
        return self.neuron_by_node.get(str(node_id)) or self.slugify(self.host)

    def _kennung(self, oid: str) -> str:
        """Dauerhafte Kennung eines Datenpunkts aus seiner OID.

        `/1/60/0/0/7/0` wird zu `<neuronId>-0-0-7-0`: Knoten- und
        Anlagenadresse fallen weg, der Rest bleibt wie er ist.
        """
        teile = oid.strip("/").split("/")
        if len(teile) < 3:
            return self.slugify(f"{self.host}{oid}")
        return "-".join([self._neuron(teile[1]), *teile[2:]])

    def _geraetekennung(self, prefix: str) -> str:
        """Dauerhafte Kennung einer Funktion (`/1/<node>/<fct>`)."""
        return self._kennung(prefix)

    def _alte_kennung(self, teil: str) -> str:
        """Die frühere, adressgebundene Kennung – nur noch für die Umstellung."""
        return self.slugify(f"{self.host}{teil}")

    def steuerung_kennung(self) -> str | None:
        """Dauerhafte Kennung der Steuerung (eine Adresse, mehrere Knoten).

        Die Steuerung selbst meldet keine eigene Seriennummer; genommen wird
        deshalb die kleinste ihrer Knoten-Seriennummern. Sie ändert sich nur,
        wenn genau dieser Baustein getauscht wird.
        """
        if not self.neuron_by_node:
            return None
        return f"steuerung-{min(self.neuron_by_node.values())}"

    @staticmethod
    def _gnmn(prefix: str, oid: str) -> str:
        """Datenpunktadresse 'gn/mn' relativ zum Funktionspräfix."""
        rest = oid[len(prefix) :].strip("/").split("/")
        return f"{rest[0]}/{rest[1]}" if len(rest) >= 2 else oid

    def _name_fuer(self, gnmn: str, vorgabe: str | None) -> str | None:
        """Anzeigename eines Datenpunkts.

        Auf Deutsch führt die gepflegte Bezeichnung; der Gerätetext springt nur
        dort ein, wo keine vorliegt. Bei fremder Sprache ist es umgekehrt –
        sonst stünde die halbe Oberfläche weiter deutsch da.
        """
        geraet = self._texte.namen.get(gnmn)
        if self.sprache == "de":
            return vorgabe or geraet
        return geraet or vorgabe

    def _enum_texte_fuer(self, gnmn: str) -> dict[int, str] | None:
        """Zustandstexte, die die Anlage selbst für diesen Datenpunkt führt.

        Nur bei fremder Sprache: Auf Deutsch gilt die gepflegte Tabelle, die
        mehr Datenpunkte abdeckt als das Textwerk der Steuerung.
        """
        if self.sprache == "de":
            return None
        return self._texte.enums.get(gnmn)

    def _stoerungstexte(self) -> dict[int, str] | None:
        """Störungstexte der Anlage, für die Meldungssensoren.

        Nur bei fremder Sprache. Die gepflegte deutsche Tabelle führt deutlich
        mehr Codes als das Textwerk der Steuerung; auf Deutsch wäre der
        Wechsel ein Rückschritt.

        Sie hängt am Deskriptor und nicht an einem eigenen Speicher: So trägt
        der Erkennungsstand sie mit, und nach einem Neustart aus dem
        Zwischenspeicher steht sie ohne neuen Abruf wieder da.
        """
        if self.sprache == "de":
            return None
        return self._texte.stoerungen or None

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------
    @staticmethod
    def _deskriptor(**felder) -> dict:
        """Ein Datenpunkt-Deskriptor mit allen Feldern, die er führen muss.

        Die Beschreibung entstand an drei Stellen – kuratierte Tabelle, Menü-
        Erkennung, LON-Adressraum – und lief auseinander: Die eine führte
        `level` und `enabled_default`, die andere nicht. Ein neues Feld musste
        dreimal nachgezogen werden, und wer eines vergaß, merkte es erst an
        einer Anlage.

        Was hier steht, ist die Form. Was ein Aufrufer nicht nennt, bleibt auf
        der Vorgabe.
        """
        return {**DESKRIPTOR_VORGABE, **felder}

    def _add_entity(self, definition: dict, prefix: str, device_id: str, fct: dict):
        """Create a device/entity descriptor from a const.py definition."""
        base = device_id if definition.get("node_level") else prefix
        oid = f"{base}{definition['oid']}"
        unique_id = self._kennung(oid)
        alt = self._alte_kennung(oid)
        if definition.get("key_suffix"):
            unique_id = f"{unique_id}-{definition['key_suffix']}"
            alt = f"{alt}-{definition['key_suffix']}"
        descriptor = self._deskriptor(
            id=unique_id,
            alt_id=alt,
            oid=oid,
            # `base`, nicht `prefix`: Knotenweite Datenpunkte hängen am Gerät,
            # nicht an der Funktion – sonst schneidet `_gnmn` die falsche
            # Länge ab.
            name=self._name_fuer(self._gnmn(base, oid), definition["name"]),
            type=definition["platform"],
            unit=definition.get("unit"),
            enum=definition.get("enum"),
            enum_texte=self._enum_texte_fuer(self._gnmn(base, oid)),
            device_class=definition.get("device_class"),
            state_class=definition.get("state_class"),
            category=definition.get("category"),
            icon=definition.get("icon"),
            min=definition.get("min"),
            max=definition.get("max"),
            step=definition.get("step"),
            press_value=definition.get("press_value"),
            device_id=self._geraetekennung(prefix),
            alt_device_id=self._alte_kennung(prefix),
            device_name=fct["name"],
            fct_type=fct.get("fctType"),
        )
        self.devices.append(descriptor)
        self.oids.add(oid)

    # Was ein Knoten aus seiner Meldung (`FExxmsg`) hergibt: Kennungs-Endung,
    # Typ, Name, Symbol. Das Ja/Nein neben dem Klartext macht die Störung für
    # Automationen auswählbar – eine Entitätsauswahl filtert nach Geräteklasse.
    _MELDUNGS_SENSOREN = (
        ("fe01", "device_status", "Meldung", "mdi:message-alert-outline"),
        ("fe01text", "message_text", "Meldung Klartext", "mdi:alert-circle-outline"),
        ("fe01stoerung", "stoerung", "Störung gemeldet", "mdi:alert"),
        ("fe01liste", "message_list", "Meldungsliste", "mdi:format-list-bulleted"),
    )

    async def _discover(self, nur_kern: bool = False):
        """Geräte und Datenpunkte der Anlage ermitteln.

        Mit ``nur_kern`` werden ausschließlich die kuratierten Datenpunkte
        angelegt – ohne die Menü-Ebenen zu lesen.
        """
        self.oids = set()
        self.devices = []
        json_devices = await self.fetch("/1")
        if not self.geraeteinfo:
            await self._lese_geraeteinfo()
        if not self.werksbezeichnung:
            await self._lese_knotendaten()
        if nur_kern:
            statisch = set()
        else:
            statisch = await self._statische_adressen()
            self._texte = await self._lade_geraetetexte()

        # Erst die Seriennummern einsammeln – alle Kennungen hängen daran.
        for device in json_devices:
            if (neuron := device.get("neuronId")) and device.get("nodeId") is not None:
                self.neuron_by_node[str(device["nodeId"])] = str(neuron)

        for device in json_devices:
            node_id = device["nodeId"]
            device_id = f"/1/{node_id}"
            primary_prefix = None
            primary_name = None
            primary_type = None

            nv_funktionen: list[dict] = []
            funktionen = list(device.get("functions", []))
            brauchbar = any(
                not f.get("lock")
                and (f.get("fctType") in FCT_ENTITY_MAP or get_layers(f.get("fctType")))
                for f in funktionen
            )
            if not brauchbar and not nur_kern:
                funktionen += await self._ungemeldete_funktionen(device_id, funktionen)

            for fct in funktionen:
                fct_type = fct.get("fctType")
                if fct.get("lock"):
                    continue
                if fct_type == FCT_NV:
                    # Der LON-Adressraum kennt keine Bedienebenen und keine
                    # kuratierte Tabelle; er läuft über seinen eigenen Weg –
                    # und erst, wenn die Funktionen dieses Knotens gelesen
                    # sind: Seine Werte gehören an das Gerät der Funktion,
                    # nicht in ein zweites daneben.
                    nv_funktionen.append(fct)
                    continue
                if fct_type not in FCT_ENTITY_MAP and not get_layers(fct_type):
                    continue

                prefix = f"{device_id}/{fct['fctId']}"

                # erste verwertbare Funktion des Knotens = Primärgerät
                # (daran hängt der Geräte-Meldungssensor aus FE01msg)
                if primary_prefix is None:
                    primary_prefix = prefix
                    primary_name = fct["name"]
                    primary_type = fct_type

                # Kuratierte Tabellen: beim Kurzdurchlauf übersprungen, damit
                # die Einrichtung nur wenige Anfragen kostet. Thermostat und
                # Meldungen entstehen weiter unten und reichen für den Start.
                if not nur_kern:
                    for definition in FCT_ENTITY_MAP.get(fct_type, []):
                        self._add_entity(definition, prefix, device_id, fct)

                # Sammel-Lesezugriff: Die Menü-Ebenen der Funktion liefern
                # sämtliche vorhandenen Datenpunkte inklusive Metadaten in
                # wenigen Anfragen. Das ist die Hauptquelle der Erkennung.
                # Eine nicht gemeldete Funktion wurde schon gelesen – ihr Typ
                # stammt aus genau diesen Datenpunkten. Ein zweiter Abruf
                # brächte nichts und kostete die Anlage ein Menü mehr.
                menu_data = fct.get("_menus")
                if menu_data is None:
                    menu_data = (
                        {} if nur_kern else await self._read_function_menus(prefix, fct_type)
                    )
                self.menu_meta.update(menu_data)

                layers = get_layers(fct_type) or {}
                level_of = {
                    gnmn: level
                    for level in ("info", "operate", "service", "oem")
                    for gnmn in layers.get(level, [])
                }
                # Bereichsnamen der Bedienebenen als Rückfall für Datenpunkte
                # ohne eigenen Namen (z.B. "Zündung 39/4").
                gruppe_of = {
                    gnmn: bereich
                    for bereich, adressen in (layers.get("groups") or {}).items()
                    for gnmn in adressen
                }

                # Datenpunkte, die die Anlage meldet, plus die bekannten
                # Ergänzungen, die in keinem Menü stehen (Zeitprogramme u. a.).
                candidates = {oid: self._gnmn(prefix, oid) for oid in menu_data}
                # Die Ergänzungen stehen in keiner Bedienebene – sonst wären sie
                # im Menü. Ohne eigenen Vermerk fielen sie deshalb gleich unten
                # als „Werksebene" wieder heraus, und das war kein theoretischer
                # Fall: `39/107` („Lagerraum befüllen: freigegeben/gesperrt")
                # und `39/5` (Restlaufzeit der Freigabe) wurden abgefragt,
                # angelegt wurden sie nie. Die Karte „Lagerraum befüllen" zeigte
                # deshalb weder Freigabe noch Restzeit – genau die zwei Angaben,
                # wegen derer man beim Befüllen überhaupt hinschaut.
                ergaenzt: set[str] = set()
                if not nur_kern:
                    # Die statische Navigation gilt für die ganze Anlage und
                    # nennt nicht, an welcher Funktion eine Position tatsächlich
                    # sitzt. Sie wird deshalb überall angeboten; wo es sie nicht
                    # gibt, antwortet die Anlage mit 404 oder 409 und die
                    # Metadatenabfrage wirft den Datenpunkt wieder heraus.
                    for gnmn in (*EXTRA_OIDS_BY_FCT.get(fct_type, ()), *statisch):
                        candidates.setdefault(f"{prefix}/{gnmn}/0", gnmn)
                        ergaenzt.add(gnmn)

                if not menu_data and not nur_kern:
                    # Ältere Firmware ohne Menüliste: auf die Datenbank
                    # zurückfallen und jeden Datenpunkt einzeln prüfen.
                    for level in self.levels:
                        for gnmn in layers.get(level, []):
                            candidates.setdefault(f"{prefix}/{gnmn}/0", gnmn)

                for oid, gnmn in candidates.items():
                    if oid in self.oids:
                        continue
                    # Datenpunkte, die keiner Bedienebene zugeordnet sind,
                    # gehören zur Werksebene: Sie erscheinen nur, wenn diese
                    # ausdrücklich gewählt wurde. Die ausdrücklich ergänzten
                    # sind davon ausgenommen – sie stehen von Hand in
                    # `EXTRA_OIDS_BY_FCT`, gerade *weil* die Anlage sie in
                    # keiner Ebene führt, und das ist eine Entscheidung und
                    # kein Zufall.
                    level = level_of.get(gnmn) or ("operate" if gnmn in ergaenzt else "oem")
                    if level not in self.levels:
                        continue
                    self.devices.append(
                        self._deskriptor(
                            id=self._kennung(oid),
                            alt_id=self._alte_kennung(oid),
                            oid=oid,
                            name=(
                                self._name_fuer(gnmn, NAME_OVERRIDES.get(gnmn) or get_name(gnmn))
                                or (f"{gruppe_of[gnmn]} {gnmn}" if gnmn in gruppe_of else None)
                                or f"Datenpunkt {gnmn}"
                            ),
                            level=level,
                            # Service- und Werksebene sind vorhanden, aber
                            # standardmäßig deaktiviert (pro Entity in Home
                            # Assistant aktivierbar oder über die Optionen).
                            enabled_default=(level not in ADVANCED_LEVELS or self.enable_advanced),
                            enum=gnmn if get_enum(gnmn) else None,
                            enum_texte=self._enum_texte_fuer(gnmn),
                            device_id=self._geraetekennung(prefix),
                            alt_device_id=self._alte_kennung(prefix),
                            device_name=fct["name"],
                            fct_type=fct_type,
                        )
                    )
                    self.oids.add(oid)

                # Heizkreis additionally gets a climate entity
                if fct_type == FCT_CLIMATE:
                    self.devices.append(
                        {
                            "id": f"{self._geraetekennung(prefix)}-thermostat",
                            "alt_id": self._alte_kennung(device_id),
                            "name": fct["name"],
                            "type": "climate",
                            "prefix": prefix,
                            "device_id": self._geraetekennung(prefix),
                            "alt_device_id": self._alte_kennung(prefix),
                            "device_name": fct["name"],
                            "fct_type": fct_type,
                        }
                    )
                    self.oids.update(
                        [
                            f"{prefix}/0/1/0",  # Raumtemperatur Ist
                            f"{prefix}/1/1/0",  # Raumtemperatur Soll
                            f"{prefix}/3/50/0",  # Betriebswahl
                            f"{prefix}/2/10/0",  # Dauer Eco/Party (Resthandzeit)
                            f"{prefix}/3/58/0",  # Behaglichkeitskorrektur
                        ]
                    )

            # Der LON-Adressraum, jetzt mit bekanntem Primärgerät. Ein Knoten
            # ohne brauchbare Funktion – das Bedienteil – bekommt darüber sein
            # eigenes Gerät; einen Kessel ergänzen die Werte an seinem.
            if not nur_kern and self.lon:
                for fct in nv_funktionen:
                    await self._lese_nv(
                        f"{device_id}/{fct['fctId']}",
                        primary_prefix,
                        primary_name,
                        primary_type,
                    )

            # Geräte-Meldung (FE01msg, z.B. "PUR 09  OK") als Sensoren je Knoten,
            # angehängt an das Primärgerät. Quelle ist die /1-Discovery selbst.
            if device.get("FE01msg") is not None and primary_prefix is not None:
                for suffix, typ, name, icon in self._MELDUNGS_SENSOREN:
                    self.devices.append(
                        self._deskriptor(
                            id=f"{self._neuron(node_id)}-{suffix}",
                            alt_id=self._alte_kennung(f"{device_id}-{suffix}"),
                            type=typ,
                            node_id=str(node_id),
                            name=name,
                            stoerungstexte=self._stoerungstexte(),
                            category="diagnostic",
                            icon=icon,
                            device_id=self._geraetekennung(primary_prefix),
                            alt_device_id=self._alte_kennung(primary_prefix),
                            device_name=primary_name,
                            fct_type=primary_type,
                        )
                    )

        self._abfragetasten()

    def _abfragetasten(self) -> None:
        """Je Anlagenteil eine Taste, die seine Werte sofort liest.

        Der zyklische Abruf staffelt nach Poll-Klasse; ein Zählerstand ist erst
        nach einer Viertelstunde wieder frisch.
        """
        for kennung, muster in {
            d["device_id"]: d
            for d in self.devices
            if d.get("device_id") and d.get("device_name") and d.get("oid")
        }.items():
            self.devices.append(
                {
                    "id": f"{kennung}-abfragen",
                    "alt_id": f"{muster.get('alt_device_id') or kennung}-abfragen",
                    "type": "refresh",
                    "name": "Werte jetzt abfragen",
                    # Ohne Kategorie steht die Taste im Abschnitt Steuerung,
                    # und der liegt auf der Geräteseite ganz oben.
                    "icon": "mdi:refresh",
                    "enabled_default": True,
                    "device_id": kennung,
                    "alt_device_id": muster.get("alt_device_id"),
                    "device_name": muster["device_name"],
                    "fct_type": muster.get("fct_type"),
                }
            )

    async def geraet_abfragen(self, device_id: str) -> dict:
        """Die zyklisch abgefragten Werte eines Anlagenteils sofort lesen.

        Nur diese, nicht jeden Datenpunkt: Ein Kessel führt mehrere hundert.
        """
        aktiv = (self.poll_oids | self._dynamic_oids) - self._abgemeldet
        oids = [
            d["oid"]
            for d in self.devices
            if d.get("device_id") == device_id and d.get("oid") in aktiv
        ]
        if not oids:
            return {}
        return await self.fetch_oids(oids)

    # ------------------------------------------------------------------
    # Metadata (min/max/step/unit/writeProt from the device itself)
    # ------------------------------------------------------------------
    async def _fetch_json(self, oid):
        """Fetch one OID and return (oid, json_or_None, http_status)."""
        try:
            data, status = await self._get(f"http://{self.host}/api/1.0/lookup{oid}")
            return oid, data, status
        except Exception as e:
            _LOGGER.debug("Metadata fetch failed for %s: %s", oid, e)
            return oid, None, 0

    @staticmethod
    def _resolve_auto_type(d: dict, m: dict) -> str | None:
        """Map an auto-discovered datapoint to a HA platform via metadata."""
        writable = m.get("writeProt") is False
        value = m.get("value")
        unit = m.get("unit") or ""
        has_enum = bool(m.get("enum")) or bool(get_enum(d.get("enum") or ""))
        if has_enum:
            return "select" if writable else "enum_sensor"
        if isinstance(value, str) and _re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", value):
            return "time" if writable else "string_sensor"
        if isinstance(value, str) and _re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", value):
            return "date" if writable else "string_sensor"
        if m.get("typeId") == 30 and "value" not in m:
            # `typeId 30` heißt „über den object-Endpunkt lesen", **nicht**
            # „Zeitprogramm". Was drinsteht, sagt erst `subtypeId`. An der
            # Anlage gemessen (PuroWIN, 518 Datenpunkte):
            #   14  Zeitprogramm – Blöcke aus Wochentagen und Schaltpunkten
            #    9  Text – Gerätetyp „PW 400", Funktionsbezeichnung „PuroWIN",
            #        Softwarestände „V 0.13"
            #   10  Funktionsliste – [{"fctType": 25, "lock": false}]
            # Alle drei kommen über `lookup` ohne Wert.
            #
            # Text (9) erkennt `_fetch_time_programs` beim ersten Abruf selbst
            # und macht einen Textsensor daraus – so kommt der Gerätetyp
            # überhaupt erst herein. Die Funktionsliste (10) dagegen *ist* eine
            # Liste von Objekten und käme dort als Zeitprogramm durch. Sie ist
            # der einzige Fall, der hier heraus muss.
            if m.get("subtypeId") == 10:
                return None
            return "time_program"
        if writable:
            try:
                if float(m.get("minValue")) < float(m.get("maxValue")):
                    return "number"
            except (TypeError, ValueError):
                pass
        if m.get("typeId") == 30:
            return "string_sensor"
        try:
            if value not in (None, "-.-", "-", ""):
                float(value)
            return "temperature" if unit == "°C" else "sensor"
        except (TypeError, ValueError):
            return "string_sensor"

    # writeProt=True turns a writable platform into its read-only sibling
    _READONLY_FALLBACK = READONLY_FALLBACK

    async def _apply_metadata(self):
        """Read metadata for every OID once and refine the descriptors.

        - min/max/step/unit reported by the device override the static defaults
        - writeProt=True converts writable entities into read-only ones
        - OIDs answered with 404 are dropped entirely (e.g. Sonden ohne Saugzuführung)
        """
        # Alles, was schon aus den Menü-Ebenen bekannt ist, muss nicht erneut
        # gelesen werden – das spart den Großteil der Anfragen beim Start.
        meta = {oid: m for oid, m in self.menu_meta.items() if oid in self.oids}
        offen = [oid for oid in self.oids if oid not in meta]
        _LOGGER.debug(
            "Metadaten: %d aus Menü-Ebenen, %d werden einzeln gelesen", len(meta), len(offen)
        )

        results = await asyncio.gather(*(self._fetch_json(oid) for oid in offen))
        missing = set()
        for oid, data, status in results:
            reason = (data or {}).get("reason", "") if isinstance(data, dict) else ""
            if status == 404 or (status == 409 and "invalid Identifier" in reason):
                # Datenpunkt existiert auf dieser Anlage nicht
                missing.add(oid)
            elif isinstance(data, dict) and "code" not in data:
                meta[oid] = data

        kept = []
        for d in self.devices:
            oid = d.get("oid")
            if oid in missing and d["type"] != "climate":
                _LOGGER.info("Dropping %s (%s): OID not present on device", d["name"], oid)
                continue
            m = meta.get(oid)
            if d["type"] == "auto":
                if not m:
                    _LOGGER.info("Dropping %s (%s): no metadata", d["name"], oid)
                    continue
                resolved = self._resolve_auto_type(d, m)
                if not resolved:
                    _LOGGER.info("Dropping %s (%s): unreadable datapoint type", d["name"], oid)
                    continue
                d["type"] = resolved
                if d["type"] == "time_program":
                    # Gelesen/geschrieben über ?OID=<vollständige OID>.
                    d["enabled_default"] = True
                    # für den PUT-Envelope beim Schreiben merken
                    d["typeId"] = m.get("typeId", 30)
                    d["subtypeId"] = m.get("subtypeId", 14)
                    d["write_prot"] = m.get("writeProt")
                elif d["type"] in ("select", "number", "switch", "time", "date") and d.get(
                    "level"
                ) in ("operate", "service"):
                    d["category"] = "config"
                # `string_sensor` gehört dazu: Eine schreibgeschützte Systemuhr
                # wird als Text gelesen und liefe sonst an der Auswahl vorbei.
                if d["type"] in ("time", "date", "string_sensor") and (
                    d.get("name") in SYSTEMZEIT_NAMEN
                ):
                    # **Systemuhr und Systemdatum sind Einstellwerte, keine
                    # Messwerte.** Man stellt sie einmal und danach jahrelang
                    # nicht mehr. Standardmäßig angelegt füllten sie die
                    # Entitätsliste und kosteten in jedem Durchlauf eine
                    # Anfrage an eine Anlage, die ohnehin knapp zwei Sekunden
                    # je Anfrage braucht.
                    #
                    # Nur diese beiden: Ein Feld mit Datum darin ist noch kein
                    # Systemdatum. „Urlaubsprogramm bis" und die
                    # Zirkulationszeiten stellt man ein, um sie danach
                    # anzusehen.
                    d["enabled_default"] = self.zeitwerte
            if m:
                # Device reports the actually allowed enum values, e.g. "[1,2]"
                enum_raw = m.get("enum")
                if enum_raw and d["type"] in ("select", "enum_sensor", "switch"):
                    try:
                        allowed = [int(v) for v in __import__("json").loads(enum_raw)]
                        if allowed:
                            d["allowed"] = allowed
                    except (ValueError, TypeError):
                        _LOGGER.debug("Unparseable enum %r for %s", enum_raw, oid)
                if d["type"] in ("select", "enum_sensor") and not d.get("allowed"):
                    # Gerät meldet zwar keine Enum-Liste, aber einen Wertebereich
                    with contextlib.suppress(TypeError, ValueError, KeyError):
                        lo, hi = int(float(m["minValue"])), int(float(m["maxValue"]))
                        emap = (
                            ENUMS_FALLBACK.get(d.get("enum") or "")
                            or get_enum(d.get("enum") or "")
                            or {}
                        )
                        allowed = [v for v in emap if lo <= v <= hi]
                        if allowed:
                            d["allowed"] = allowed
                if d["type"] == "number":
                    with contextlib.suppress(ValueError, TypeError, KeyError):
                        lo = float(m["minValue"]) if m.get("minValue") not in (None, "") else None
                        hi = float(m["maxValue"]) if m.get("maxValue") not in (None, "") else None
                        st = float(m["step"]) if m.get("step") not in (None, "") else None
                        if lo is not None and hi is not None and lo < hi:
                            d["min"], d["max"] = lo, hi
                        if st and st > 0:
                            d["step"] = st
                if m.get("unit") and d["type"] in ("number", "sensor"):
                    d["unit"] = m["unit"]
                if m.get("writeProt") is True and d["type"] in self._READONLY_FALLBACK:
                    fallback = lesetyp(d["type"], m.get("unit") or d.get("unit"))
                    _LOGGER.info(
                        "%s (%s) ist schreibgeschützt und wird nur angezeigt", d["name"], oid
                    )
                    d["type"] = fallback
                    # Nur bedienbare Entitäten dürfen die Kategorie
                    # "Konfiguration" tragen; Home Assistant lehnt sie
                    # bei reinen Sensoren ab.
                    if d.get("category") == "config":
                        d["category"] = None
                d["write_prot"] = m.get("writeProt")
                # Ein Fühlereingang ohne Fühler meldet die Leermarke. Die
                # Entität entsteht abgeschaltet statt dauerhaft „nicht
                # verfügbar"; wer sie einmal einschaltet, behält sie.
                if (
                    m.get("value") in ("-.-", "-")
                    and d["type"] not in ("select", "number", "switch", "time", "date", "button")
                    and d.get("enabled_default", True)
                ):
                    d["enabled_default"] = False
                    d["leer_beim_einlesen"] = True
                # read-only-Punkt ganz ohne Wert (z.B. Softwareversion ohne value-Feld)
                if (
                    "value" not in m
                    and m.get("writeProt") is True
                    and d["type"] not in ("select", "number", "switch", "time", "button")
                ):
                    _LOGGER.info("Dropping %s (%s): no value delivered", d["name"], oid)
                    continue
            # Service- und Werksebene bleiben nur lesbar, solange der Nutzer sie
            # in den Optionen nicht ausdrücklich freigegeben hat.
            if (
                d.get("level") in ADVANCED_LEVELS
                and not self.writable_advanced
                and d["type"] in self._READONLY_FALLBACK
            ):
                d["type"] = lesetyp(d["type"], d.get("unit"))
                if d.get("category") == "config":
                    d["category"] = None

            if d["type"] == "climate":
                m50 = meta.get(f"{d['prefix']}/3/50/0")
                if m50 and m50.get("enum"):
                    with contextlib.suppress(ValueError, TypeError):
                        d["preset_allowed"] = [int(v) for v in json.loads(m50["enum"])]
            # Zum Schluss, wenn der endgültige Typ feststeht: Einheit in die
            # HA-Schreibweise bringen und Geräte-/Statistikklasse setzen.
            messgroesse(d)
            kept.append(d)
        self.devices = kept
        self.oids -= missing
        await self._nv_ohne_fuehler_verwerfen()
        self._nv_doppelte_stilllegen()
        self.zusatzkandidaten = []
        self._abgeleitete_zaehler()
        self._laufzeit()
        self._namen_vereindeutigen()

    # Zählerstände, aus denen sich ein Zuwachs bilden lässt.
    _ZAEHLERKLASSEN = ("total", "total_increasing")

    @staticmethod
    def _kennung_aus_oid(oid: str | None) -> str:
        """`gn/mn` aus einer vollständigen Adresse, ohne Präfix."""
        teile = str(oid or "").strip("/").split("/")
        return "/".join(teile[-3:-1]) if len(teile) >= 3 else ""

    def _ableitung(self, quelle: dict, endung: str, typ: str, zusatz: str, **felder) -> dict:
        """Ein Deskriptor, der von einem anderen lebt: gleiche Adresse, eigener Name."""
        return self._deskriptor(
            id=f"{quelle['id']}-{endung}",
            alt_id=f"{quelle.get('alt_id') or quelle['id']}-{endung}",
            oid=quelle["oid"],
            type=typ,
            name=f"{quelle['name']} {zusatz}".strip(),
            enabled_default=False,
            device_id=quelle.get("device_id"),
            alt_device_id=quelle.get("alt_device_id"),
            device_name=quelle.get("device_name"),
            fct_type=quelle.get("fct_type"),
            **felder,
        )

    def _abgeleitete_zaehler(self) -> None:
        """Je Zählerstand zwei Zuwächse: heute und seit dem letzten Start.

        Die Anlage führt nur Gesamtstände. Der Zuwachs entsteht deshalb hier,
        aus derselben Adresse – ohne einen zusätzlichen Abruf.
        """
        # Startzähler des Geräts sind der Bezugspunkt: Steigt der Stand, läuft
        # ein neuer Lauf. Welche Adresse das ist, sagt die kuratierte Tabelle.
        ausloeser = {
            d["device_id"]: d["oid"]
            for d in self.devices
            if d.get("device_id") and self._kennung_aus_oid(d.get("oid")) in STARTZAEHLER
        }
        # Geräte, deren Zustand die Laufzeit minutengenau hergibt. Dort ist der
        # Stundenzähler die schlechtere Antwort und bekommt keine Ableitung.
        mit_laufzeit = {
            d.get("device_id")
            for d in self.devices
            if LAUFPHASEN.get(str(d.get("enum") or "")) and d.get("device_id")
        }
        # Tageswerte, die die Anlage selbst führt, je Gerät.
        vom_geraet = {
            (d.get("device_id"), kennung)
            for d in self.devices
            if (kennung := self._kennung_aus_oid(d.get("oid"))) in TAGESWERTE
        }
        neu = []
        for d in self.devices:
            if not d.get("oid") or not d.get("name"):
                continue
            if d.get("state_class") not in self._ZAEHLERKLASSEN:
                continue
            kennung = self._kennung_aus_oid(d["oid"])
            # Ein Tageswert der Anlage braucht keine Ableitung seiner selbst.
            if kennung in TAGESWERTE:
                continue
            # Stunden sind Laufzeit, alles andere zählt Stück oder Menge.
            stunden = (d.get("unit") or "") == "h"
            if stunden and d.get("device_id") in mit_laufzeit:
                continue
            gruppe = GRUPPE_LAUFZEIT if stunden else GRUPPE_ZAEHLER
            gemeinsam = {
                "unit": d.get("unit"),
                "device_class": d.get("device_class"),
                "gruppe": gruppe,
            }
            bezug = ausloeser.get(d.get("device_id"))
            # Der Bezugszähler selbst bekommt keinen Bezug auf sich: Jeder
            # Start setzte die Basis neu, der Wert bliebe immer null.
            if bezug and bezug != d["oid"]:
                neu.append(
                    self._ableitung(
                        d, "start", "zaehler_start", "seit Start", ausloeser_oid=bezug, **gemeinsam
                    )
                )
            # Führt die Anlage den Tageswert selbst, gilt ihrer.
            if (d.get("device_id"), TAGESZAEHLER.get(kennung)) not in vom_geraet:
                neu.append(self._ableitung(d, "heute", "zaehler_heute", "heute", **gemeinsam))
        self._zusatzwerte_uebernehmen(neu)

    # Endung der Kennung -> Name des Werts, der daraus entsteht.
    _LAUFZEITEN = {
        "laufzeit": "Laufzeit aktuell",
        "laufzeit-heute": "Laufzeit heute",
    }

    def _laufzeit(self) -> None:
        """Wie lange das Aggregat läuft – aus dem Zustand, nicht aus Stunden.

        Der Stundenzähler der Anlage steht in ganzen Stunden und wird träge
        gelesen; der Zustand kommt alle 30 s. Verglichen werden Zahlencodes,
        nicht Beschriftungen.
        """
        neu = []
        for d in self.devices:
            phasen = LAUFPHASEN.get(str(d.get("enum") or ""))
            if not phasen or not d.get("oid"):
                continue
            for endung, name in self._LAUFZEITEN.items():
                neu.append(
                    self._ableitung(
                        {**d, "name": ""},
                        endung,
                        endung.replace("-", "_"),
                        name,
                        unit="min",
                        laufphasen=sorted(phasen),
                        icon="mdi:fire-circle",
                        gruppe=GRUPPE_LAUFZEIT,
                    )
                )
        self._zusatzwerte_uebernehmen(neu)

    # Deskriptorarten, die aus einem anderen Wert abgeleitet sind.
    ZUSATZTYPEN = (
        "zaehler_heute",
        "zaehler_start",
        "laufzeit",
        "laufzeit_heute",
    )

    def _zusatzwerte_uebernehmen(self, kandidaten: list[dict]) -> None:
        """Angekreuzte Werte einschalten, die übrigen abgeschaltet anlegen.

        Wie beim Schalter für die Zeitwerte: Ein weggenommenes Häkchen schaltet
        ab und wirft nichts weg – Verlauf und eigener Name bleiben.
        """
        for kandidat in kandidaten:
            kandidat["enabled_default"] = kandidat["id"] in self.zusatzwerte
        self.zusatzkandidaten += kandidaten
        self.devices += kandidaten

    def _namen_vereindeutigen(self) -> None:
        """Gleichnamige Datenpunkte eines Geräts unterscheidbar machen.

        Die Parameterliste des Herstellers vergibt denselben Namen mehrfach:
        „Betriebswahl" gibt es als Bedienung (3/50) und als Anzeige der
        Serviceebene (4/14), „WW-Zirkulationsprogramm" zweimal (5/64, 5/65).
        Bei Gleichstand wird die Datenpunktadresse angehängt.
        """
        namen_je_geraet: dict[tuple, list] = {}
        for d in self.devices:
            if not d.get("oid") or not d.get("name"):
                continue
            namen_je_geraet.setdefault((d.get("device_id"), d["name"]), []).append(d)

        for (_geraet, _name), gruppe in namen_je_geraet.items():
            if len(gruppe) < 2:
                continue
            for d in gruppe:
                praefix = d["oid"].rsplit("/", 3)[0]
                d["name"] = f"{d['name']} ({self._gnmn(praefix, d['oid'])})"

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

    def climate_oids(self, prefix: str) -> list:
        """Vollständige Climate-OIDs für einen Heizkreis-Prefix."""
        return [f"{prefix}{s}" for s in self._CLIMATE_POLL_SUFFIXES]

    async def fetch_oids(self, oids) -> dict:
        """Nur eine gezielte OID-Menge abfragen (für schnellen Burst-Refresh).

        Was die Anlage nicht beantwortet hat, fehlt im Ergebnis: Die Aufrufer
        tragen es in den Bestand des Abrufs ein.
        """
        results = await asyncio.gather(*(self._fetch_oid(o) for o in oids))
        return {oid: wert for oid, wert in results if wert is not FEHLGESCHLAGEN}

    @staticmethod
    def _poll_klasse(beschreibung: dict) -> str:
        """In welchem Takt ein Datenpunkt gelesen werden muss.

        Die Einstufung folgt dem, was der Wert *ist*, nicht wo er steht:
        Zählerstände und Restlaufzeiten bewegen sich in Stunden, Temperaturen
        und Betriebszustände in Sekunden. Im Zweifel bleibt es beim mittleren
        Takt – lieber einmal zu oft gelesen als eine Anzeige, die nachhinkt.
        """
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
            if d.get("type") == "time_program":
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

    async def async_init_basic(self) -> None:
        """Grunddaten lesen: Anlagenstruktur und die wichtigsten Datenpunkte.

        Kostet nur wenige Anfragen. Danach sind Geräte und Kernwerte in Home
        Assistant sichtbar; der vollständige Abzug folgt im Hintergrund.
        """
        if self.oids is not None:
            return

        begonnen = time.monotonic()
        self.request_count = 0
        await self._discover(nur_kern=True)
        await self._apply_metadata()
        self._compute_poll_oids()
        self._vollstaendig = False
        _LOGGER.info(
            "%s: Grunddaten gelesen – %d Entitäten, %d Anfragen, %.1f s. "
            "Die Anlage wird im Hintergrund vollständig eingelesen.",
            self.host,
            len(self.devices),
            self.request_count,
            time.monotonic() - begonnen,
        )

    def _erkennung_zu_mager(self, vorheriger: dict | None) -> bool:
        """Prüfen, ob dieser Lauf deutlich weniger fand als der Stand davor.

        Eine Steuerung, die gerade schwächelt, meldet weniger Datenpunkte;
        dieser Lauf räumte sonst still die halbe Anlage ab. Der alte Stand
        bleibt dann stehen, der nächste Lauf versucht es erneut.
        """
        vorher = len(vorheriger.get("oids") or ()) if vorheriger else 0
        if vorher < ERKENNUNG_MIN_DATENPUNKTE:
            return False
        jetzt = len(self.oids or ())
        if jetzt >= vorher * ERKENNUNG_MIN_ANTEIL:
            return False
        _LOGGER.warning(
            "%s meldet nur %d von zuvor %d Datenpunkten – der bekannte Stand bleibt. "
            "Bleibt es dabei, hilft der Dienst heatnexus.rediscover.",
            self.host,
            jetzt,
            vorher,
        )
        return True

    async def async_init(self, erzwingen: bool = False) -> None:
        """Anlage vollständig einlesen (getrennt vom zyklischen Abruf).

        Mit ``erzwingen`` läuft der Abzug auch dann, wenn bereits ein
        vollständiger Stand vorliegt – so gleicht eine neue Fassung der
        Integration einen aus dem Cache übernommenen Stand ab.
        """
        if self._vollstaendig and not erzwingen:
            return

        begonnen = time.monotonic()
        self.request_count = 0
        # Der bisherige Stand als Rückfall, solange er vollständig war.
        vorheriger = self.export_discovery() if self._vollstaendig else None
        self.oids = None
        await self._discover()
        nach_discovery = self.request_count
        await self._apply_metadata()
        self._compute_poll_oids()
        self._vollstaendig = True

        if self._erkennung_zu_mager(vorheriger):
            self.restore_discovery(vorheriger)
            return

        _LOGGER.info(
            "%s eingelesen: %d Datenpunkte, %d Entitäten, davon %d aktiv – "
            "%d Anfragen (%d für die Menü-Ebenen), %.1f s",
            self.host,
            len(self.oids),
            len(self.devices),
            len(self.poll_oids),
            self.request_count,
            nach_discovery,
            time.monotonic() - begonnen,
        )

    # ------------------------------------------------------------------
    # Discovery-Cache (überlebt einen Config-Entry-Reload, z.B. wenn der
    # Nutzer eine deaktivierte Entity aktiviert -> kein erneuter teurer
    # Discovery-/Metadaten-Lauf, nur noch normales Polling).
    # ------------------------------------------------------------------
    def export_discovery(self) -> dict:
        """Discovery-Ergebnis für die Wiederverwendung (RAM- und Platten-Cache).

        Bewusst JSON-tauglich (Listen statt Sets), damit es per HA-Store
        persistiert werden kann.
        """
        return {
            "oids": sorted(self.oids) if self.oids is not None else None,
            "devices": [dict(d) for d in self.devices],
            "poll_oids": sorted(self.poll_oids),
            "objects_supported": self._objects_supported,
            "neuron_by_node": dict(self.neuron_by_node),
            "geraeteinfo": dict(self.geraeteinfo),
            "werksbezeichnung": dict(self.werksbezeichnung),
            "zusatzkandidaten": list(self.zusatzkandidaten),
        }

    def restore_discovery(self, data: dict) -> None:
        """Discovery-Ergebnis aus dem Cache übernehmen (überspringt async_init)."""
        self.oids = set(data["oids"]) if data.get("oids") is not None else set()
        # Einheiten und Klassen werden neu bestimmt, nicht aus dem Cache
        # übernommen: Ein gespeicherter Stand kann von einer Fassung stammen,
        # die die Einheitentabelle noch nicht kannte. Der Aufruf ist
        # wiederholbar und ändert an einem aktuellen Stand nichts.
        self.devices = [messgroesse(dict(d)) for d in data.get("devices", [])]
        self.neuron_by_node = dict(data.get("neuron_by_node") or {})
        self.geraeteinfo = dict(data.get("geraeteinfo") or {})
        self.werksbezeichnung = dict(data.get("werksbezeichnung") or {})
        self.zusatzkandidaten = [dict(k) for k in data.get("zusatzkandidaten") or []]
        # Die Auswahl kann sich seit dem Speichern geändert haben.
        for d in self.devices:
            if d.get("type") in self.ZUSATZTYPEN:
                d["enabled_default"] = d["id"] in self.zusatzwerte
        # Abrufplan, Poll-Klassen und Zeitprogramme leiten sich aus den
        # Deskriptoren ab und werden deshalb neu bestimmt. Aus dem Zwischen-
        # speicher übernommen überlebte ein lückenhafter Plan jeden Neustart.
        self._compute_poll_oids()
        # object-Unterstützung aus dem Cache übernehmen (kein erneutes Probing).
        self._objects_supported = data.get("objects_supported")
        self._vollstaendig = True

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------
    @staticmethod
    def _wert_oder_none(value):
        """Rohwert übernehmen; die Leermarken der Anlage werden zu None.

        `-.-` ist die Auskunft der Steuerung, dass zu diesem Datenpunkt kein
        Messwert vorliegt (Fühler nicht angeschlossen). Ein `0` daraus zu
        machen wäre eine Falschaussage.
        """
        if value in (None, "-.-", "-", ""):
            return None
        # Rohe Zeichenkette behalten. Ein früheres str(int(float(v))) hat hier
        # alle Nachkommastellen vernichtet (21.5 °C -> "21"); die Entities
        # zerlegen den Wert selbst.
        return str(value)

    async def _fetch_oid(self, oid):
        """Einen Wert lesen; Rückgabe ``(oid, Wert oder None)``.

        Gelesen wird über `datapoint`, nicht über `lookup`. Beide liefern
        denselben Wert derselben Adresse und antworten gleich auf fehlende,
        nur schreibbare und unbekannte Positionen. Der Unterschied ist der
        Umfang: `lookup` stellt den ganzen Metadatensatz zusammen – Einheit,
        Grenzen, Schrittweite, Aufzählung, Schreibschutz –, `datapoint` nur
        den Wert. Beim Abruf ist davon nichts nötig, das steht im Deskriptor.

        Erreicht die Anfrage die Anlage nicht, kommt ``FEHLGESCHLAGEN`` zurück
        und nicht ``None``: Der Aufrufer lässt den zuletzt gelesenen Wert
        stehen, statt die Anzeige zu leeren.
        """
        try:
            data, status = await self._get(
                f"http://{self.host}/api/1.0/datapoint{oid}", self._poll_semaphore
            )
            if self._abmelden(oid, data, status):
                return oid, None
            value = data.get("value") if isinstance(data, dict) else None
            return oid, self._wert_oder_none(value)
        except Exception as e:
            _LOGGER.warning("Error while fetching OID %s: %s", oid, e)
            return oid, FEHLGESCHLAGEN

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

    def _object_url(self, full_oid: str) -> URL:
        """Build the object-endpoint URL.

        Lokal bestätigt: der Endpunkt liest die OID aus dem Query-Parameter
        `OID` (groß) als VOLLSTÄNDIGEN Pfad (z.B. /1/15/0/3/61/0). Slashes
        müssen unkodiert bleiben -> encoded=True verhindert ein Re-Quoting
        durch yarl.
        """
        return URL(f"http://{self.host}/api/1.0/object?OID={full_oid}", encoded=True)

    async def fetch_object(self, full_oid):
        """GET a structured object (Zeitprogramm) via ?OID=<full_oid>.

        Returns (json_or_None, http_status). Das Gerät liefert hier u.a.
        {"value": [{"weekdays": [...], "switchPoints": [{"time","value"}...]}]}.
        """
        try:
            await self._ensure_session()
            async with self._semaphore:
                ret = await self._session.request("GET", self._object_url(full_oid))
                status = ret.status
                try:
                    data = await ret.json()
                except Exception:
                    data = None
            return data, status
        except Exception as e:
            _LOGGER.debug("Object fetch failed for %s: %s", full_oid, e)
            return None, 0

    async def write_object(self, full_oid, payload: dict):
        """PUT a structured object (Zeitprogramm) via ?OID=<full_oid>."""
        await self._ensure_session()
        async with self._semaphore:
            ret = await self._session.request(
                "PUT",
                self._object_url(full_oid),
                data=bytes(json.dumps(payload), "utf-8"),
            )
            if ret.status >= 400:
                body = await ret.text()
                _LOGGER.error(
                    "Write to object %s failed with HTTP %s: %s",
                    full_oid,
                    ret.status,
                    body,
                )
                raise aiohttp.ClientResponseError(
                    ret.request_info,
                    ret.history,
                    status=ret.status,
                    message=f"Write to time program {full_oid} rejected by device",
                )
        _LOGGER.debug("Wrote object %s = %s", full_oid, payload)

    async def _fetch_time_programs(self) -> dict:
        """Read all known time programs via the object endpoint.

        Beim ersten Aufruf wird geprüft, ob das Gerät den object-Endpunkt
        lokal überhaupt beherrscht. Falls nicht, werden die Zeitprogramm-
        Entities verworfen (keine toten Sensoren) und nicht mehr abgefragt.
        """
        if self._objects_supported is False or not self.time_programs:
            return {}

        results = await asyncio.gather(*(self.fetch_object(tp["oid"]) for tp in self.time_programs))
        objects: dict = {}
        any_ok = False
        for tp, (data, status) in zip(self.time_programs, results, strict=False):
            if status != 200 or not isinstance(data, dict) or "value" not in data:
                continue
            any_ok = True
            wert = data["value"]
            if _ist_zeitprogramm(wert):
                objects[tp["oid"]] = wert
                continue
            # Kein Zeitprogramm, sondern ein einfacher Wert (Modulinfo,
            # Software-/Hardwarestand). Als Textsensor führen.
            self._object_texts[tp["oid"]] = str(wert)
            tp["type"] = "string_sensor"
            _LOGGER.debug(
                "%s (%s) ist kein Zeitprogramm, sondern ein Textwert", tp.get("name"), tp["oid"]
            )

        if self._objects_supported is None:
            self._objects_supported = any_ok
            if not any_ok:
                _LOGGER.info(
                    "object-Endpunkt lokal nicht verfügbar – Zeitprogramme werden übersprungen"
                )
                tp_oids = {tp["oid"] for tp in self.time_programs}
                self.devices = [d for d in self.devices if d.get("oid") not in tp_oids]
                self.time_programs = []
        self.time_programs = [tp for tp in self.time_programs if tp.get("type") == "time_program"]
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
        if not _ist_zeitprogramm(wert):
            return None
        self._letzte_objekte[oid] = wert
        return wert

    # Alle Meldungsfelder eines Geräts (FE01msg, FE02msg, …) – mehrere
    # gleichzeitige Störungen reihen sich aneinander.
    _FEMSG_RE = _re.compile(r"^FE\d+msg$")

    async def _fetch_status(self) -> dict:
        """Aktuelle Geräte-Meldungen (FExxmsg) je Knoten neu lesen.

        Quelle ist die /1-Discovery, die je Gerät FE01msg (+ ggf. weitere)
        mitliefert. Nur nötig, wenn ein Meldungs-/Klartext-Sensor existiert.
        """
        typen = {typ for _, typ, _, _ in self._MELDUNGS_SENSOREN}
        if not any(d.get("type") in typen for d in self.devices):
            return {}
        try:
            devs = await self.fetch("/1")
        except Exception as e:
            _LOGGER.debug("Status fetch failed: %s", e)
            return {}
        out: dict = {}
        if isinstance(devs, list):
            for dev in devs:
                nid = dev.get("nodeId")
                if nid is None:
                    continue
                msgs = [str(v) for k, v in dev.items() if self._FEMSG_RE.match(k) and v]
                if msgs:
                    out[str(nid)] = "  ".join(msgs)
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
        for oid in (self.poll_oids | self._dynamic_oids) - self._abgemeldet:
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
        # Zeitprogramme entstehen erst im Vollabzug, also nach dem ersten
        # Durchlauf. Ohne diesen Vorgriff stünden sie bis zum nächsten trägen
        # Durchlauf ohne Wert da und wären so lange nicht verfügbar.
        if self.time_programs and not self._letzte_objekte:
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
        aktuell = self.poll_oids | self._dynamic_oids
        for oid in list(self._letzte_werte):
            if oid not in aktuell and oid not in self._object_texts:
                del self._letzte_werte[oid]

        self._tick += 1
        self.poll_count += 1
        self.poll_seconds += time.monotonic() - poll_begonnen
        werte = dict(self._letzte_werte)
        werte.update(self._object_texts)
        return {
            "devices": self.devices,
            "oids": werte,
            "objects": dict(self._letzte_objekte),
            "status": status,
        }
