"""Der Weg zur Anlage: Sitzung, Digest-Anmeldung, Dekodierung, Endpunkte.

Hier steht, wie eine Anfrage gestellt und eine Antwort gelesen wird – nicht,
was sie bedeutet. Die Steuerung antwortet in einer DOS-Codepage, deshalb die
Zeichensatzkette in `_decode`.
"""

from __future__ import annotations

import json
import logging
import time

import aiohttp
from yarl import URL

from ..const import ANFRAGE_TIMEOUT, FETCH_CONCURRENCY, POLL_CONCURRENCY, VERBINDUNG_TIMEOUT
from ..exceptions import WindhagerWriteError
from .gemeinsam import FEHLGESCHLAGEN

_LOGGER = logging.getLogger(__name__)


class TransportMixin:
    """Sitzung, Anfragen und Antworten der Anlage."""

    # Zeichensätze in der Reihenfolge, in der sie ausprobiert werden.
    # cp850 ist die DOS-Codepage der Steuerung: dort liegt „ü" auf 0x81,
    # einem in CP1252 gar nicht belegten Byte. Ohne cp850 in der Kette
    # verlieren von Hand vergebene Namen ihre Umlaute.
    _ZEICHENSAETZE = ("utf-8", "cp1252", "cp850")

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

    async def fetch(self, url, semaphore=None):
        """GET /api/1.0/lookup<url> and return the parsed JSON."""
        data, _status = await self._get(f"http://{self.host}/api/1.0/lookup{url}", semaphore)
        _LOGGER.debug("Antwort von %s: %s", url, data)
        return data

    async def _fetch_json(self, oid):
        """Fetch one OID and return (oid, json_or_None, http_status)."""
        try:
            data, status = await self._get(f"http://{self.host}/api/1.0/lookup{oid}")
            return oid, data, status
        except Exception as e:
            _LOGGER.debug("Metadaten zu %s nicht lesbar: %s", oid, e)
            return oid, None, 0

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
            _LOGGER.warning("Fehler beim Lesen von %s: %s", oid, e)
            return oid, FEHLGESCHLAGEN

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
                _LOGGER.debug("Schreiben auf %s scheitert mit HTTP %s: %s", oid, ret.status, body)
                raise WindhagerWriteError(
                    f"Die Anlage hat den Wert für {oid} abgelehnt (HTTP {ret.status})."
                )
        self.vormerken(oid, value)
        _LOGGER.debug("Auf %s geschrieben: %s", oid, value)

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
            _LOGGER.debug("Objekt %s nicht lesbar: %s", full_oid, e)
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
                _LOGGER.debug(
                    "Schreiben auf Objekt %s scheitert mit HTTP %s: %s",
                    full_oid,
                    ret.status,
                    body,
                )
                raise WindhagerWriteError(
                    f"Die Anlage hat das Zeitprogramm {full_oid} abgelehnt (HTTP {ret.status})."
                )
        _LOGGER.debug("Auf Objekt %s geschrieben: %s", full_oid, payload)

    async def probe(self):
        """Verbindung prüfen: Anlagenstruktur und HTTP-Status zurückgeben.

        Wird vom Einrichtungsdialog benutzt, damit dort zwischen „nicht
        erreichbar" und „Passwort falsch" unterschieden werden kann.
        """
        return await self._get(f"http://{self.host}/api/1.0/lookup/1")
