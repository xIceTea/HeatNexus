"""Der Client: Zustand, Aufbau aus den Mixins, Start.

`async_init_basic` liest Struktur und kuratierten Kern unter dem
Einrichtungs-Timeout; `async_init` liest den Rest im Hintergrund. Alles
andere steht in den Modulen daneben.
"""

from __future__ import annotations

import asyncio
import logging
import time

from .. import geraetetexte
from ..const import (
    DEFAULT_LEVELS,
    DEFAULT_USERNAME,
    ERKENNUNG_MIN_ANTEIL,
    ERKENNUNG_MIN_DATENPUNKTE,
    FETCH_CONCURRENCY,
    POLL_CONCURRENCY,
    UPDATE_INTERVAL,
)
from .ableitungen import AbleitungenMixin
from .abruf import AbrufMixin
from .erkennung import ErkennungMixin
from .kennungen import KennungenMixin
from .menues import MenuesMixin
from .metadaten import MetadatenMixin
from .netzwerkvariablen import NetzwerkvariablenMixin
from .transport import TransportMixin

_LOGGER = logging.getLogger(__name__)


class WindhagerHttpClient(
    TransportMixin,
    MenuesMixin,
    NetzwerkvariablenMixin,
    KennungenMixin,
    ErkennungMixin,
    MetadatenMixin,
    AbleitungenMixin,
    AbrufMixin,
):
    """Zugriff auf eine Anlage: Erkennung, Metadaten und zyklischer Abruf."""

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
        lon_grundumfang: bool = True,
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
        # Geschriebene Werte, bis die Anlage sie bestaetigt: OID -> (Wert, Zeit).
        self._vorgemerkt: dict[str, tuple[str, float]] = {}
        self.zusatzkandidaten: list[dict] = []
        self._zusatz_neu: list[dict] = []
        self._zusatz_lauft = False
        self.lon = lon
        # Der Aufbau der Anlage kommt auch ohne den vollen Adressraum: Pumpe,
        # Mischer und die Kernmesswerte des Erzeugers, und nur dort, wo kein
        # Datenpunkt dieselbe Größe schon führt.
        self.lon_grundumfang = lon_grundumfang
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
        # Textobjekte als Deskriptoren, dazu die Adressen, die schon einmal
        # über den object-Endpunkt versucht wurden.
        self.objekt_texte: list[dict] = []
        self._objekte_versucht: set[str] = set()
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
