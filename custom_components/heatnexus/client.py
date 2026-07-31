"""Windhager HTTP API client."""

import asyncio
import contextlib
import json
import logging
import re as _re
import time

import aiohttp
from yarl import URL

from .aiohelper import DigestAuth
from .const import (
    ADVANCED_LEVELS,
    DEFAULT_LEVELS,
    DEFAULT_USERNAME,
    EXTRA_OIDS_BY_FCT,
    FCT_CLIMATE,
    FCT_ENTITY_MAP,
    FETCH_CONCURRENCY,
    MENU_PAGE_SIZE,
)
from .const import (
    ENUMS as ENUMS_FALLBACK,
)
from .device_db import get_enum, get_layers, get_name

_LOGGER = logging.getLogger(__name__)

# Klarere, gruppierende Namen für einzelne auto-entdeckte Datenpunkte.
# HA sortiert Entities auf der Geräteseite nach dem Namen – mit gemeinsamem
# Präfix landen zusammengehörige Werte (z.B. WW-Zirkulation) beieinander.
NAME_OVERRIDES = {
    "5/6": "WW-Zirkulationspumpe Modus",
    "5/70": "WW-Zirkulation Einschaltzeit",
    "5/71": "WW-Zirkulation Ausschaltzeit",
}


class WindhagerHttpClient:
    """Raw API HTTP requests."""

    def __init__(
        self,
        host,
        password,
        levels: list | None = None,
        enable_advanced: bool = False,
        writable_advanced: bool = False,
    ) -> None:
        self.host = host
        self.password = password
        # Welche Bedienebenen überhaupt angelegt werden (Auswahl bei der
        # Einrichtung). Service- und Werksebene gelten als "fortgeschritten":
        # ihre Entities sind nur auf Wunsch aktiv bzw. bedienbar.
        self.levels = list(levels or DEFAULT_LEVELS)
        self.enable_advanced = enable_advanced
        self.writable_advanced = writable_advanced
        self.oids: set | None = None
        self.devices: list[dict] = []
        # Metadaten aus den Menü-Ebenen: OID -> vollständiger Datenpunkt.
        # Damit entfällt für diese OIDs die einzelne Metadaten-Abfrage.
        self.menu_meta: dict = {}
        # Statisch immer gepollte OIDs (aktive Entities + Climate).
        self.poll_oids: set = set()
        # Dynamisch von tatsächlich aktivierten Entities registrierte OIDs
        # (z.B. eine vom Nutzer eingeschaltete Service-Entity).
        self._dynamic_oids: set = set()
        # Zeitprogramme (typeId 30) werden nicht über lookup, sondern über den
        # object-Endpunkt gelesen. Liste der Programm-Deskriptoren + Flag, ob
        # das Gerät den object-Endpunkt lokal unterstützt (None = noch ungetestet).
        self.time_programs: list[dict] = []
        self._objects_supported: bool | None = None
        # Objekte mit einfachem Textwert (z.B. Modulinfo, Softwarestand).
        # Sie werden wie normale Werte behandelt, nicht als Zeitprogramm.
        self._object_texts: dict = {}
        # Anzahl der Anfragen an die Anlage (für die Startmeldung)
        self.request_count = 0
        self._session = None
        self._auth = None
        self._semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)

    # ------------------------------------------------------------------
    # Dynamische Poll-Registrierung
    # ------------------------------------------------------------------
    def register_poll_oid(self, oid: str) -> None:
        """Eine Entity meldet ihre OID zum zyklischen Polling an."""
        if oid:
            self._dynamic_oids.add(oid)

    def unregister_poll_oid(self, oid: str) -> None:
        """Eine entfernte/deaktivierte Entity meldet ihre OID ab."""
        self._dynamic_oids.discard(oid)

    async def _ensure_session(self):
        """Ensure that we have an active client session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._auth = DigestAuth(DEFAULT_USERNAME, self.password, self._session)

    async def close(self):
        """Close the client session."""
        if self._session:
            await self._session.close()
            self._session = None
            self._auth = None

    @staticmethod
    def _decode(raw: bytes) -> str:
        """Antwort dekodieren.

        Die Anlagen liefern Text nicht durchgängig als UTF-8: Funktionsnamen
        wie „Hebebühne" kommen als Latin-1/CP1252 zurück. Ohne Rückfall stünden
        Fragezeichen in Geräte- und Entitätsnamen.
        """
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("cp1252", "replace")

    async def _get(self, url: str):
        """GET auf die Anlage; gibt (json_oder_None, status) zurück."""
        await self._ensure_session()
        self.request_count += 1
        async with self._semaphore:
            ret = await self._auth.request("GET", url)
            raw = await ret.read()
        try:
            return json.loads(self._decode(raw)), ret.status
        except ValueError:
            return None, ret.status

    async def fetch(self, url):
        """GET /api/1.0/lookup<url> and return the parsed JSON."""
        data, _status = await self._get(f"http://{self.host}/api/1.0/lookup{url}")
        _LOGGER.debug("Fetched data for %s: %s", url, data)
        return data

    async def probe(self):
        """Verbindung prüfen: Anlagenstruktur und HTTP-Status zurückgeben.

        Wird vom Einrichtungsdialog benutzt, damit dort zwischen „nicht
        erreichbar" und „Passwort falsch" unterschieden werden kann.
        """
        return await self._get(f"http://{self.host}/api/1.0/lookup/1")

    # ------------------------------------------------------------------
    # Sammel-Lesezugriff über Menü-Ebenen
    # ------------------------------------------------------------------
    async def _read_menu(self, prefix: str, menu_id: str, expected: int) -> list:
        """Eine Menü-Ebene vollständig lesen.

        Ein Abruf liefert höchstens MENU_PAGE_SIZE Datenpunkte; weitere holt
        das Gerät über ?offset=<n>. Jeder Eintrag enthält bereits Wert und
        Metadaten, ein zusätzlicher Einzelabruf entfällt damit.
        """
        base = f"http://{self.host}/api/1.0/lookup{prefix}/{menu_id}"
        items: list = []
        seen: set = set()
        offset = 0

        while True:
            url = base if offset == 0 else f"{base}?offset={offset}"
            data, status = await self._get(url)
            if status != 200 or not isinstance(data, list) or not data:
                break
            fresh = [i for i in data if isinstance(i, dict) and i.get("OID") not in seen]
            if not fresh:
                break
            items.extend(fresh)
            seen.update(i["OID"] for i in fresh)
            if len(items) >= expected or len(data) < MENU_PAGE_SIZE:
                break
            offset += MENU_PAGE_SIZE

        if expected and len(items) < expected:
            _LOGGER.debug(
                "Menü %s%s: %d von %d Datenpunkten gelesen", prefix, menu_id, len(items), expected
            )
        return items

    async def _read_function_menus(self, prefix: str) -> dict:
        """Alle Datenpunkte einer Funktion über ihre Menü-Ebenen einlesen."""
        root, status = await self._get(f"http://{self.host}/api/1.0/lookup{prefix}")
        if status != 200 or not isinstance(root, list) or not root:
            return {}
        if not isinstance(root[0], dict) or "id" not in root[0]:
            # Ältere Firmware kennt die Menüliste nicht – Einzelabfragen greifen.
            return {}

        menus = {str(m.get("id")): int(m.get("count") or 0) for m in root}
        results = await asyncio.gather(
            *(self._read_menu(prefix, menu_id, count) for menu_id, count in menus.items())
        )
        datapoints: dict = {}
        for items in results:
            for item in items:
                oid = item.get("OID")
                if oid:
                    datapoints[oid] = item
        _LOGGER.debug("%s: %d Datenpunkte aus %d Menü-Ebenen", prefix, len(datapoints), len(menus))
        return datapoints

    async def update(self, oid, value):
        """PUT a new value to a datapoint."""
        await self._ensure_session()
        async with self._semaphore:
            ret = await self._auth.request(
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

    @staticmethod
    def _gnmn(prefix: str, oid: str) -> str:
        """Datenpunktadresse 'gn/mn' relativ zum Funktionspräfix."""
        rest = oid[len(prefix) :].strip("/").split("/")
        return f"{rest[0]}/{rest[1]}" if len(rest) >= 2 else oid

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------
    def _add_entity(self, definition: dict, prefix: str, device_id: str, fct: dict):
        """Create a device/entity descriptor from a const.py definition."""
        base = device_id if definition.get("node_level") else prefix
        oid = f"{base}{definition['oid']}"
        unique_id = self.slugify(f"{self.host}{oid}")
        if definition.get("key_suffix"):
            unique_id = f"{unique_id}-{definition['key_suffix']}"
        descriptor = {
            "id": unique_id,
            "oid": oid,
            "name": definition["name"],
            "type": definition["platform"],
            "unit": definition.get("unit"),
            "enum": definition.get("enum"),
            "device_class": definition.get("device_class"),
            "state_class": definition.get("state_class"),
            "category": definition.get("category"),
            "icon": definition.get("icon"),
            "min": definition.get("min"),
            "max": definition.get("max"),
            "step": definition.get("step"),
            "press_value": definition.get("press_value"),
            "write_prot": None,
            "device_id": self.slugify(f"{self.host}{prefix}"),
            "device_name": fct["name"],
        }
        self.devices.append(descriptor)
        self.oids.add(oid)

    async def _discover(self):
        """Discover devices/functions and build entity descriptors (once)."""
        self.oids = set()
        self.devices = []
        json_devices = await self.fetch("/1")

        for device in json_devices:
            node_id = device["nodeId"]
            device_id = f"/1/{node_id}"
            primary_prefix = None
            primary_name = None
            for fct in device.get("functions", []):
                fct_type = fct.get("fctType")
                if fct.get("lock"):
                    continue
                if fct_type not in FCT_ENTITY_MAP and not get_layers(fct_type):
                    continue

                prefix = f"{device_id}/{fct['fctId']}"

                # erste verwertbare Funktion des Knotens = Primärgerät
                # (daran hängt der Geräte-Meldungssensor aus FE01msg)
                if primary_prefix is None:
                    primary_prefix = prefix
                    primary_name = fct["name"]

                # Entities from the declarative tables (curated, take priority)
                for definition in FCT_ENTITY_MAP.get(fct_type, []):
                    self._add_entity(definition, prefix, device_id, fct)

                # Sammel-Lesezugriff: Die Menü-Ebenen der Funktion liefern
                # sämtliche vorhandenen Datenpunkte inklusive Metadaten in
                # wenigen Anfragen. Das ist die Hauptquelle der Erkennung.
                menu_data = await self._read_function_menus(prefix)
                self.menu_meta.update(menu_data)

                layers = get_layers(fct_type) or {}
                level_of = {
                    gnmn: level
                    for level in ("info", "operate", "service", "oem")
                    for gnmn in layers.get(level, [])
                }

                # Datenpunkte, die die Anlage meldet, plus die bekannten
                # Ergänzungen, die in keinem Menü stehen (Zeitprogramme u. a.).
                candidates = {oid: self._gnmn(prefix, oid) for oid in menu_data}
                for gnmn in EXTRA_OIDS_BY_FCT.get(fct_type, ()):
                    candidates.setdefault(f"{prefix}/{gnmn}/0", gnmn)

                if not menu_data:
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
                    # ausdrücklich gewählt wurde.
                    level = level_of.get(gnmn, "oem")
                    if level not in self.levels:
                        continue
                    self.devices.append(
                        {
                            "id": self.slugify(f"{self.host}{oid}"),
                            "oid": oid,
                            "name": NAME_OVERRIDES.get(gnmn) or get_name(gnmn) or gnmn,
                            "type": "auto",
                            "level": level,
                            # Service- und Werksebene sind vorhanden, aber
                            # standardmäßig deaktiviert (pro Entity in Home
                            # Assistant aktivierbar oder über die Optionen).
                            "enabled_default": (
                                level not in ADVANCED_LEVELS or self.enable_advanced
                            ),
                            "enum": gnmn if get_enum(gnmn) else None,
                            "unit": None,
                            "device_class": None,
                            "state_class": None,
                            "category": None,
                            "icon": None,
                            "min": None,
                            "max": None,
                            "step": None,
                            "press_value": None,
                            "write_prot": None,
                            "device_id": self.slugify(f"{self.host}{prefix}"),
                            "device_name": fct["name"],
                        }
                    )
                    self.oids.add(oid)

                # Heizkreis additionally gets a climate entity
                if fct_type == FCT_CLIMATE:
                    self.devices.append(
                        {
                            # keep legacy unique_id scheme of the climate entity
                            "id": self.slugify(f"{self.host}{device_id}"),
                            "name": fct["name"],
                            "type": "climate",
                            "prefix": prefix,
                            "device_id": self.slugify(f"{self.host}{prefix}"),
                            "device_name": fct["name"],
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

            # Geräte-Meldung (FE01msg, z.B. "PUR 09  OK") als Sensor je Knoten,
            # angehängt an das Primärgerät. Quelle ist die /1-Discovery selbst.
            if device.get("FE01msg") is not None and primary_prefix is not None:
                self.devices.append(
                    {
                        "id": self.slugify(f"{self.host}{device_id}-fe01"),
                        "type": "device_status",
                        "node_id": str(node_id),
                        "name": "Meldung",
                        "category": "diagnostic",
                        "icon": "mdi:message-alert-outline",
                        "enabled_default": True,
                        "device_id": self.slugify(f"{self.host}{primary_prefix}"),
                        "device_name": primary_name,
                    }
                )
                # Zweiter Sensor: Fehlercode -> Klartext (z.B. "Fehler 346 –
                # Verkleidungstür offen"), Liste aller aktiven Störungen im Attribut.
                self.devices.append(
                    {
                        "id": self.slugify(f"{self.host}{device_id}-fe01text"),
                        "type": "message_text",
                        "node_id": str(node_id),
                        "name": "Meldung Klartext",
                        "category": "diagnostic",
                        "icon": "mdi:alert-circle-outline",
                        "enabled_default": True,
                        "device_id": self.slugify(f"{self.host}{primary_prefix}"),
                        "device_name": primary_name,
                    }
                )

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
    def _resolve_auto_type(d: dict, m: dict) -> str:
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
            # Zeitprogramme (3/61.., 5/61..): liefern über lookup keinen Wert,
            # werden separat über den object-Endpunkt gelesen.
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
    _READONLY_FALLBACK = {
        "number": "sensor",
        "select": "enum_sensor",
        "switch": "binary_sensor",
        "time": "string_sensor",
    }

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
                    fallback = self._READONLY_FALLBACK[d["type"]]
                    # ein "Schalter" mit Einheit (z.B. Kaminkehrer 9/90 in min)
                    # ist in Wahrheit ein Zaehler -> normaler Sensor
                    if d["type"] == "switch" and m.get("unit"):
                        fallback = "sensor"
                    _LOGGER.info("%s (%s) is write protected, exposing read-only", d["name"], oid)
                    d["type"] = fallback
                d["write_prot"] = m.get("writeProt")
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
                d["type"] = self._READONLY_FALLBACK[d["type"]]

            if d["type"] == "climate":
                m50 = meta.get(f"{d['prefix']}/3/50/0")
                if m50 and m50.get("enum"):
                    with contextlib.suppress(ValueError, TypeError):
                        d["preset_allowed"] = [int(v) for v in json.loads(m50["enum"])]
            kept.append(d)
        self.devices = kept
        self.oids -= missing

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
        """Nur eine gezielte OID-Menge abfragen (für schnellen Burst-Refresh)."""
        results = await asyncio.gather(*(self._fetch_oid(o) for o in oids))
        return dict(results)

    def _compute_poll_oids(self) -> None:
        """Statisches Poll-Set: aktive Entities + Climate-Hilfs-OIDs.

        Service-/standardmäßig deaktivierte Entities landen NICHT hier –
        sie werden erst gepollt, wenn der Nutzer sie in HA aktiviert und
        die Entity sich per register_poll_oid() dynamisch anmeldet.
        """
        poll: set = set()
        for d in self.devices:
            if d.get("type") == "climate":
                prefix = d.get("prefix", "")
                poll.update(f"{prefix}{s}" for s in self._CLIMATE_POLL_SUFFIXES)
                continue
            if d.get("type") == "time_program":
                # wird über den object-Endpunkt gelesen, nicht über lookup
                continue
            if d.get("enabled_default", True) and d.get("oid"):
                poll.add(d["oid"])
        self.poll_oids = poll
        self.time_programs = [d for d in self.devices if d.get("type") == "time_program"]

    async def async_init(self) -> None:
        """Anlage einmalig einlesen (getrennt vom zyklischen Abruf)."""
        if self.oids is not None:
            return

        begonnen = time.monotonic()
        self.request_count = 0
        await self._discover()
        nach_discovery = self.request_count
        await self._apply_metadata()
        self._compute_poll_oids()

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
        }

    def restore_discovery(self, data: dict) -> None:
        """Discovery-Ergebnis aus dem Cache übernehmen (überspringt async_init)."""
        self.oids = set(data["oids"]) if data.get("oids") is not None else set()
        self.devices = [dict(d) for d in data.get("devices", [])]
        self.poll_oids = set(data.get("poll_oids", set()))
        self.time_programs = [d for d in self.devices if d.get("type") == "time_program"]
        # object-Unterstützung aus dem Cache übernehmen (kein erneutes Probing).
        self._objects_supported = data.get("objects_supported")

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------
    async def _fetch_oid(self, oid):
        """Fetch a single OID, returning (oid, value-or-None)."""
        try:
            json = await self.fetch(oid)
            value = json.get("value") if isinstance(json, dict) else None
            if value in (None, "-.-", "-", ""):
                return oid, None
            # Keep the raw string. The old code did str(int(float(v))) here,
            # which destroyed all decimals (21.5 °C -> "21"). Entities parse
            # the value themselves.
            return oid, str(value)
        except Exception as e:
            _LOGGER.warning("Error while fetching OID %s: %s", oid, e)
            return oid, None

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
                ret = await self._auth.request("GET", self._object_url(full_oid))
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
            ret = await self._auth.request(
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
            if isinstance(wert, list) and wert and isinstance(wert[0], dict):
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

    # Alle Meldungsfelder eines Geräts (FE01msg, FE02msg, …) – mehrere
    # gleichzeitige Störungen reihen sich aneinander.
    _FEMSG_RE = _re.compile(r"^FE\d+msg$")

    async def _fetch_status(self) -> dict:
        """Aktuelle Geräte-Meldungen (FExxmsg) je Knoten neu lesen.

        Quelle ist die /1-Discovery, die je Gerät FE01msg (+ ggf. weitere)
        mitliefert. Nur nötig, wenn ein Meldungs-/Klartext-Sensor existiert.
        """
        if not any(d.get("type") in ("device_status", "message_text") for d in self.devices):
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

    async def fetch_all(self):
        """Poll the currently relevant OIDs in parallel and return coordinator data.

        Es werden nur die statisch aktiven (poll_oids) plus die von aktivierten
        Entities dynamisch angemeldeten OIDs abgefragt – nicht mehr blind alle
        entdeckten OIDs. Das hält jeden Poll deutlich unter dem Coordinator-
        Timeout, auch wenn Hunderte Service-Datenpunkte bekannt sind.
        """
        if self.oids is None:
            # Fallback, falls async_init noch nicht lief (sollte nicht passieren).
            await self.async_init()

        oids_to_poll = self.poll_oids | self._dynamic_oids
        results = await asyncio.gather(*(self._fetch_oid(oid) for oid in oids_to_poll))
        objects = await self._fetch_time_programs()
        status = await self._fetch_status()

        werte = dict(results)
        werte.update(self._object_texts)
        return {
            "devices": self.devices,
            "oids": werte,
            "objects": objects,
            "status": status,
        }
