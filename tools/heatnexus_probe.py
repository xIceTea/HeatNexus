#!/usr/bin/env python3
"""HeatNexus – Anlagen-Probe für Windhager-Heizungen.

Liest Struktur, Menü-Ebenen, Datenpunkte und Zeitprogramme einer oder mehrerer
Anlagen aus und schreibt JSON, CSV und einen Markdown-Bericht. Nutzt nur die
Python-Standardbibliothek.

Ohne Argumente startet der geführte Modus (Auswahlmenü). Alternativ direkt:

    python tools/heatnexus_probe.py menus 192.0.2.10 192.0.2.11
    python tools/heatnexus_probe.py oid 192.0.2.10 /1/15/0/3/50/0
    python tools/heatnexus_probe.py all 192.0.2.10 -o probe

Passwörter werden nie gespeichert. Sie kommen aus einer verdeckten Eingabe,
aus der Umgebungsvariablen HEATNEXUS_PW oder aus `--password`; Letzteres steht
in Prozessliste und Shell-Verlauf.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import contextlib
import contextvars
import csv
import datetime as dt
import getpass
import importlib.util
import json
import locale
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from xml.etree import ElementTree
import zipfile

# Zugang ab Werk. Die Steuerung kennt zwei Benutzer, `USER` und `Service`; der
# Name wird geprüft, der Umfang hängt aber nicht daran – über die Schnittstelle
# liefern beide dieselben Datenpunkte samt Fachparametern. `--user` bleibt
# trotzdem wählbar, weil das nur an einer Baureihe gemessen ist.
USERNAME = "USER"
TIMEOUT = 30  # große Menü-Ebenen brauchen deutlich länger als eine Einzelabfrage
# An der Anlage gemessen: derselbe Menü-Abzug mit 3 und mit 6 Worker braucht
# gleich lang (174,6 s gegen 179,4 s bei 690 Datenpunkten), ohne Abbrüche. Die
# Steuerung serialisiert; zusätzliche Threads warten nur woanders. Mehr als 3
# lohnt nicht.
DEFAULT_WORKERS = 3
RETRIES = 2  # Wiederholungen bei Zeitüberschreitung/Verbindungsabbruch
RETRY_PAUSE = 1.5
# Ein ausgelasteter InfoWIN Plus bricht Abrufe mit 502/504 ab; die Pause wächst je Versuch.
GATEWAY_RETRIES = 3
# Wie `GATEWAY_FEHLER` der Integration; 500 und 501 sind Auskünfte, keine Überlastung.
GATEWAY_FEHLER = frozenset({502, 503, 504})
PAGE_SIZE = 10  # das Gerät liefert je Menü-Abruf höchstens 10 Datenpunkte
# Adressen, mit denen der Stapelabruf gemessen wird. Genug für einen
# belastbaren Vergleich, wenig genug, dass der Lauf Sekunden dauert.
STAPEL_PROBE = 20
REPO = Path(__file__).resolve().parent.parent
HOSTS_FILE = "hosts.txt"

if hasattr(sys.stdout, "reconfigure"):  # Umlaute auch in der Windows-Konsole
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------- Geräte-DB
def _load_device_db():
    """device_db ohne Home-Assistant-Umgebung laden."""
    path = REPO / "custom_components" / "heatnexus" / "device_db.py"
    spec = importlib.util.spec_from_file_location("heatnexus_device_db", path)
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    return module


DEVICE_DB = _load_device_db()


def _load_geraete():
    """Gerätewissen ohne Home Assistant laden: die Zusatzadressen je Funktionstyp."""
    ordner = REPO / "custom_components" / "heatnexus" / "geraete"
    name = "heatnexus_geraete"
    spec = importlib.util.spec_from_file_location(
        name, ordner / "__init__.py", submodule_search_locations=[str(ordner)]
    )
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        return None
    return module


GERAETE = _load_geraete()


def db_name(gnmn: str) -> str:
    """Datenpunktname aus der Geräte-Datenbank."""
    if DEVICE_DB is None:
        return ""
    try:
        return DEVICE_DB.get_name(gnmn) or ""
    except Exception:
        return ""


# ------------------------------------------------------------------- Client
def _voruebergehend(status: int, rumpf: str) -> bool:
    """Ob eine Fehlerantwort eine Wiederholung lohnt; „does not exist“ ist endgültig."""
    return status in GATEWAY_FEHLER and "does not exist" not in rumpf


class Probe:
    """Digest-authentifizierter Lesezugriff auf eine Anlage."""

    def __init__(
        self,
        host: str,
        password: str,
        workers: int = DEFAULT_WORKERS,
        username: str = USERNAME,
    ) -> None:
        """Zugriff auf eine Anlage vorbereiten."""
        self.host = host  # darf "1.2.3.4" oder "1.2.3.4:8080" sein
        self.username = username
        self.base = f"http://{host}"
        self.password = password
        self.workers = workers
        self.requests = 0
        self.errors = 0
        # erkannte Form für das Nachladen weiterer Menü-Seiten:
        # None = noch unbekannt, "keine" = Gerät kann es nicht, sonst (Name, Bauer)
        self.page_strategy = None
        self._local = threading.local()
        self._lock = threading.Lock()

    @property
    def opener(self) -> urllib.request.OpenerDirector:
        """Je Thread ein eigener Opener (urllib ist nicht nebenläufigkeitssicher)."""
        opener = getattr(self._local, "opener", None)
        if opener is None:
            mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            mgr.add_password(None, f"{self.base}/", self.username, self.password)
            # Ohne Proxy, wie die Integration: urllib übernähme sonst den des
            # Systems und schickte die Anfrage über ihn statt direkt zur Steuerung.
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}),
                urllib.request.HTTPDigestAuthHandler(mgr),
            )
            self._local.opener = opener
        return opener

    # Dieselbe Kette wie in ``client._decode``. Sie muss dieselbe sein: Sonst
    # zeigt die Sonde einen anderen Namen als die Integration, und man sucht
    # den Fehler an der falschen Stelle. CP850 ist die DOS-Codepage der
    # Steuerung – dort liegt „ü" auf 0x81, einem in CP1252 unbelegten Byte.
    ZEICHENSAETZE = ("utf-8", "cp1252", "cp850")

    @classmethod
    def _decode(cls, raw: bytes) -> str:
        """Antwort dekodieren.

        Die Geräte liefern Texte nicht durchgängig als UTF-8: Von Hand
        vergebene Funktionsnamen kommen im Zeichensatz der Steuerung zurück.
        """
        for zeichensatz in cls.ZEICHENSAETZE:
            try:
                return raw.decode(zeichensatz)
            except UnicodeDecodeError:
                continue
        # latin-1 bildet jedes Byte ab und schlägt daher nie fehl.
        return raw.decode("latin-1")

    def get(self, url: str):
        """GET mit Zählung und Wiederholung; gibt (json_oder_None, status) zurück."""
        last = ({"error": "unbekannt"}, 0)
        for attempt in range(max(RETRIES, GATEWAY_RETRIES) + 1):
            with self._lock:
                self.requests += 1
            try:
                with self.opener.open(url, timeout=TIMEOUT) as resp:
                    return json.loads(self._decode(resp.read())), resp.status
            except urllib.error.HTTPError as err:
                body = self._decode(err.read())
                # 401 nach erfolgreicher Anmeldung heißt: Der Digest-Nonce ist
                # verbraucht. `HTTPDigestAuthHandler` versucht es genau einmal
                # neu und gibt dann auf – und weil er seinen Zähler erst bei
                # Erfolg zurücksetzt, antwortet derselbe Opener danach auf
                # *jede* Anfrage mit 401. Sichtbar wurde das bei der Suche nach
                # den statischen Einträgen: die ersten drei Präfixe lieferten
                # saubere 409er, alle folgenden 401 – ein Ergebnis, das wie
                # „gibt es nicht" aussieht und keines ist.
                #
                # Genau ein zweiter Versuch, und ohne Pause: Eine neue Anmeldung
                # braucht keine Bedenkzeit, und scheitert auch die, liegt es
                # wirklich am Passwort. Mit Wartezeit und drei Anläufen wurde
                # aus einer Suche über 36 Adressen ein Lauf, der aussah, als
                # hinge er.
                if err.code == 401 and attempt == 0:
                    self._local.opener = None
                    continue
                if _voruebergehend(err.code, body) and attempt < GATEWAY_RETRIES:
                    time.sleep(RETRY_PAUSE * (attempt + 1))
                    continue
                try:
                    return json.loads(body), err.code
                except ValueError:
                    return {"raw": body}, err.code
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as err:
                last = ({"error": str(err)}, 0)
                if attempt < RETRIES:
                    time.sleep(RETRY_PAUSE)
                    continue
                with self._lock:
                    self.errors += 1
                break
        return last

    def lookup(self, path: str):
        """GET /api/1.0/lookup<path>."""
        return self.get(f"{self.base}/api/1.0/lookup{path}")

    def obj(self, full_oid: str):
        """GET /api/1.0/object?OID=<vollständige OID>."""
        return self.get(f"{self.base}/api/1.0/object?OID={full_oid}")

    def ressource(self, pfad: str):
        """GET /res/<pfad> als Text; gibt (text_oder_None, status) zurück.

        Die Ressourcendateien der Steuerung sind XML, kein JSON – `get` würde
        sie als unlesbar verwerfen.
        """
        with self._lock:
            self.requests += 1
        try:
            with self.opener.open(f"{self.base}/res/{pfad}", timeout=TIMEOUT) as resp:
                return self._decode(resp.read()), resp.status
        except urllib.error.HTTPError as err:
            return None, err.code
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            with self._lock:
                self.errors += 1
            return None, 0

    def post(self, url: str, rumpf: bytes, typ: str = "text/xml; charset=utf-8"):
        """POST mit derselben Anmeldung; gibt (Text, Status) zurück.

        **Nur für Leseanfragen.** Der Web-Service der Steuerung kennt auch
        `setDp` und `writeDp`; die haben in einer Sonde nichts zu suchen.
        """
        anfrage = urllib.request.Request(url, data=rumpf, method="POST")
        anfrage.add_header("Content-Type", typ)
        with self._lock:
            self.requests += 1
        try:
            with self.opener.open(anfrage, timeout=TIMEOUT) as resp:
                return self._decode(resp.read()), resp.status
        except urllib.error.HTTPError as err:
            if err.code == 401:
                # Wie bei `get`: verbrauchter Nonce, einmal neu anmelden.
                self._local.opener = None
                try:
                    with self.opener.open(anfrage, timeout=TIMEOUT) as resp:
                        return self._decode(resp.read()), resp.status
                except urllib.error.HTTPError as zweiter:
                    return self._decode(zweiter.read()), zweiter.code
                except (urllib.error.URLError, TimeoutError, OSError) as zweiter:
                    return str(zweiter), 0
            return self._decode(err.read()), err.code
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            return str(err), 0

    def map(self, func, items):
        """Aufgaben parallel abarbeiten."""
        if self.workers <= 1:
            return [func(i) for i in items]
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            return list(pool.map(func, items))


def safe_name(host: str) -> str:
    """Dateinamensicherer Name einer Anlage (Windows erlaubt kein ':')."""
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in host)


def zielordner(angabe: str) -> Path:
    """Zielordner bestimmen – relative Angaben gelten ab dem Repository.

    Sonst landet die Ausgabe dort, wo man gerade steht: Wer die Sonde aus
    ``tools/`` startet, bekam ein zweites ``tools/probe/``, und die Integration
    verglich später gegen einen Ordner, in dem nichts lag. Absolute Pfade
    bleiben unberührt.
    """
    pfad = Path(angabe)
    return pfad if pfad.is_absolute() else REPO / pfad


def reachable(host: str, timeout: float = 2.0) -> bool:
    """Kurzer TCP-Test, ob die Anlage antwortet ('ip' oder 'ip:port')."""
    name, _, port = host.partition(":")
    try:
        with socket.create_connection((name, int(port or 80)), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


# ------------------------------------------------------- Seitenweises Lesen
# Ein Menü-Abruf liefert höchstens PAGE_SIZE Datenpunkte. Welche Form das Gerät
# zum Nachladen der übrigen versteht, ist offen – diese Varianten werden
# durchprobiert, die erste funktionierende gilt für die ganze Anlage.
PAGE_STRATEGIES = [
    ("start", lambda base, off: f"{base}?start={off}"),
    ("offset", lambda base, off: f"{base}?offset={off}"),
    ("index", lambda base, off: f"{base}?index={off}"),
    ("from", lambda base, off: f"{base}?from={off}"),
    ("first", lambda base, off: f"{base}?first={off}"),
    ("page", lambda base, off: f"{base}?page={off // PAGE_SIZE}"),
    ("pfad", lambda base, off: f"{base}/{off}"),
    ("start+count", lambda base, off: f"{base}?start={off}&count={PAGE_SIZE}"),
    # Die Form, die die Weboberfläche der Anlage selbst benutzt. Ihr Lesepfad
    # lautet im Quelltext wörtlich
    #     'api/1.0/' + 'lookup' + <OID> + '?count=' + n + '&offset=' + m
    # und die Vorgabewerte der zuständigen Klasse sind `t=0` (count) und
    # `u=0` (offset). Auch die SOAP-Vorlage `ws.getDP.req.xml` trägt
    # `<count>0</count>`. Beides deutet darauf, dass **0 „alle" heißt**.
    #
    # Falls das stimmt, ist es der größte Leistungshebel des Projekts: Heute
    # liefert ein Menü-Abruf zehn Datenpunkte, und beide Anlagen zusammen
    # kommen auf rund 8900 Anfragen je Stunde.
    ("count+offset", lambda base, off: f"{base}?count={PAGE_SIZE}&offset={off}"),
    ("count=0", lambda base, off: f"{base}?count=0&offset={off}"),
    ("count=50", lambda base, off: f"{base}?count=50&offset={off}"),
]


def _eintrag_schluessel(item, praefix: str = "") -> str | None:
    """Was einen Eintrag einer Menü-Ebene unterscheidbar macht.

    An einer NV-Funktion führt ein Eintrag keine `OID`, sondern einen
    `nvIndex` – die Steuerung deutet die Adresse dort um. Ohne Rückfall
    darauf gilt eine solche Ebene als leer: Der Seitenvergleich findet nie
    etwas Neues, und die Zusammenfassung greift auf ein leeres Ergebnis zu.

    Mit `praefix` entsteht daraus die Adresse, unter der der Eintrag im Abzug
    steht; ohne ihn genügt der Index, weil dort nur innerhalb einer Ebene
    verglichen wird.
    """
    if not isinstance(item, dict):
        return None
    if item.get("OID"):
        return item["OID"]
    if item.get("nvIndex") is not None:
        return f"{praefix}/{item['nvIndex']}" if praefix else f"nv/{item['nvIndex']}"
    return None


def _oids_of(items) -> list[str]:
    return [s for i in items if (s := _eintrag_schluessel(i))]


def detect_pagination(probe: Probe, menu_url: str, first_page: list) -> tuple[str, object] | None:
    """Ermitteln, wie sich die zweite Seite einer Menü-Ebene abrufen lässt."""
    known = set(_oids_of(first_page))
    for name, build in PAGE_STRATEGIES:
        data, status = probe.get(build(menu_url, PAGE_SIZE))
        if status != 200 or not isinstance(data, list) or not data:
            continue
        oids = set(_oids_of(data))
        if oids and not oids & known:
            return name, build
    return None


def fetch_menu_all(
    probe: Probe, menu_url: str, expected: int, strategy
) -> tuple[list, object | None, int]:
    """Eine Menü-Ebene vollständig lesen (soweit das Gerät es zulässt)."""
    # Das Bedienteil ruft ganze Ebenen mit count=-1 ab.
    if expected > PAGE_SIZE:
        alles, status = probe.get(f"{menu_url}?count=-1&offset=0")
        if status == 200 and isinstance(alles, list) and len(alles) > PAGE_SIZE:
            return alles, strategy, status

    data, status = probe.get(menu_url)
    if status != 200 or not isinstance(data, list):
        return [], strategy, status

    items = list(data)
    if len(items) >= expected or len(items) < PAGE_SIZE:
        return items, strategy, status

    if strategy is None:
        strategy = detect_pagination(probe, menu_url, items) or "keine"
    if strategy == "keine":
        return items, strategy, status

    _name, build = strategy
    seen = set(_oids_of(items))
    offset = PAGE_SIZE
    while len(items) < expected and offset < expected + PAGE_SIZE:
        page, pstatus = probe.get(build(menu_url, offset))
        if pstatus != 200 or not isinstance(page, list) or not page:
            break
        fresh = [i for i in page if _eintrag_schluessel(i) not in seen]
        if not fresh:
            break
        items.extend(fresh)
        seen.update(_oids_of(fresh))
        offset += PAGE_SIZE
    return items, strategy, status


# ---------------------------------------------------------------- Abfragen
def struktur_hinweis(status: int, data) -> str:
    """Erklären, warum die Struktur nicht lesbar war."""
    if status in (401, 403):
        return _t("Passwort prüfen – dasselbe wie in der Integration")
    if status == 0:
        return _t("keine Verbindung: {}", (data or {}).get("error", "unbekannt"))
    hinweis = f"HTTP {status}"
    # Die Struktur lehnt eine Steuerung nur mit 401/403 ab. Jede andere
    # 4xx-Antwort stammt von einem anderen Gerät unter derselben Adresse.
    if 400 <= status < 500:
        hinweis += (
            ": Unter dieser Adresse antwortet keine Windhager-Steuerung."
            " Dieselbe IP-Adresse wie in der Integration verwenden"
        )
    if isinstance(data, dict) and "raw" in data:
        seite = data["raw"]
    elif data:
        seite = json.dumps(data, ensure_ascii=False)
    else:
        seite = ""
    titel = re.search(r"<title>(.*?)</title>", seite, re.I | re.S)
    text = titel.group(1) if titel else re.sub(r"<[^>]+>", " ", seite)
    text = " ".join(text.split())[:80]
    return f"{hinweis} (Antwort: {text})" if text else hinweis


# Statische Navigationseinträge der Steuerung. Sie stehen in
# `res/xml/StaticNavAssignment.xml`, das die Anlage ohne Anmeldung ausliefert,
# und sind absichtlich in keiner Menü-Ebene enthalten – der Menü-Abzug findet
# sie deshalb nie:
#
#     <staticentry type="errorlog"    oidextension="2/90/0"/>   Störspeicher
#     <staticentry type="timeprogram" oidextension="4/80/0"/>   Sonderzeitprogramm
#     <staticentry type="parameter"   oidextension="4/42/0"/>   Passwort
#
# Zugeordnet sind sie dort den Funktionstypen 0 und 18 – einer Zählung, die
# **nicht** die des `fctType` aus `/1` ist. Wo sie tatsächlich liegen, lässt
# sich nur durch Ausprobieren feststellen, und genau das macht `suche_statisch`:
# Sie klappert jeden Knoten und jede Funktion ab, auch die sonst übersprungenen
# (`NV's` mit fctType −1, gesperrte) und den Knoten ohne Funktionsangabe.
#
# Die Liste kommt von der Anlage selbst (`statische_navigation`); dieser Satz
# ist nur der Rückfall für eine Fassung, die die Dateien nicht ausliefert.
STATISCHE_NAV = {
    "2/90/0": "Störspeicher (errorlog)",
    "4/80/0": "Sonderzeitprogramm",
    "4/42/0": "Passwort",
}

# Die Ressourcendateien führen dieselbe Adresse in zwei Schreibweisen:
# `oidextension="4/80/0"` in der Zuordnung, `gnmn="04:80"` in der Navigation.
_ADRESSE = re.compile(r"^0*(\d+)[:/]0*(\d+)(?:/\d+)?$")

RESSOURCEN_STATISCH = ("xml/StaticNavAssignment.xml", "xml/StaticNav.xml")


def _entzerrt(text: str) -> str:
    """Doppelt kodierte Umlaute zurückholen („StÃ¶rspeicher" -> „Störspeicher").

    Die Dateien geben UTF-8 an, enthalten aber UTF-8-Bytes eines bereits
    dekodierten Textes. Lässt sich der Text nicht zurückrechnen, bleibt er wie
    er ist – ein Anzeigename ist keinen Abbruch wert.
    """
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def statische_navigation(probe: Probe) -> dict:
    """Die statischen Positionen von der Anlage lesen statt sie zu raten.

    Liefert `{"<gruppe>/<member>/0": "<Beschreibung>"}`. Der Name kommt aus dem
    deutschen Text der Navigationsdatei, sonst aus dem Elementnamen der
    Zuordnung (`errorlog`, `timeprogram`, `parameter`). Antwortet die Anlage
    auf keine der Dateien, bleibt es beim eingebauten Rückfall.
    """
    gefunden: dict[str, str] = {}
    for pfad in RESSOURCEN_STATISCH:
        text, status = probe.ressource(pfad)
        if status != 200 or not text:
            print(f"    {pfad}: HTTP {status}")
            continue
        try:
            wurzel = ElementTree.fromstring(text)
        except ElementTree.ParseError as fehler:
            print(f"    {pfad}: nicht lesbar ({fehler})")
            continue
        neu = 0
        for element in wurzel.iter():
            for schluessel in ("oidextension", "gnmn"):
                treffer = _ADRESSE.match(element.get(schluessel, ""))
                if treffer is None:
                    continue
                adresse = f"{treffer.group(1)}/{treffer.group(2)}/0"
                benannt = element.find("text/de")
                name = _entzerrt((benannt.text or "").strip()) if benannt is not None else ""
                # Der eigene Text gewinnt: Der Elementname sagt nur die Art.
                if name or adresse not in gefunden:
                    gefunden[adresse] = name or element.get("type") or element.tag
                    neu += 1
        print(f"    {pfad}: {neu} Positionen")
    if not gefunden:
        print("    keine Ressourcendatei lesbar – eingebauter Rückfall")
        return dict(STATISCHE_NAV)
    return gefunden


# ------------------------------------------------------------- Störspeicher
# **Nicht geraten, sondern aus der Weboberfläche der Anlage abgelesen.**
#
# Deren Quelltext liegt unter `/infowintouch/<STRONGNAME>.cache.html` und ist
# ohne Anmeldung ladbar. Darin:
#
#     function zq(a,b){ … this.f = '/'+c[1]+'/'+c[2]+'/'+c[3]+'/2/96/0'; … }
#     BU(196,1,{},zq)      und  uM = V6(snb,'StaticNavActionErrorLog',196)
#
# `zq` ist der Störspeicher; seine Adresse ist `2/96`. (`2/90` aus
# `StaticNav.xml` ist nur der Schlüssel des Menüeintrags und antwortet überall
# mit `409 – invalid Identifier`.)
#
# `zq` baut vier Leser, einen je Kesselfamilie – und alle vier sind gleich
# aufgebaut:
#
#     function Pf(a,b){ … c = h8(a,0,a.length-1);          // OID ohne letzte Stelle
#                       for(d=0;d<10;d++){ … new Sf(c+d) } }
#
# Der **letzte OID-Abschnitt ist der Index**, und es sind genau zehn Einträge:
# `/1/<node>/<fct>/2/96/0` bis `…/9`.
#
# Gelesen werden sie über denselben Endpunkt wie alles andere. Der Lesepfad der
# Oberfläche lautet im Klartext:
#
#     'api/1.0/' + 'lookup' + <OID> + '?count=' + n + '&offset=' + m
#
# Also `lookup`, nicht `object` – deshalb ging die Suche über den
# object-Endpunkt ins Leere.
STOERSPEICHER_GNMN = "2/96"
STOERSPEICHER_EINTRAEGE = 10


def suche_stoerspeicher(probe: Probe, structure: list) -> dict:
    """Den Störspeicher lesen, so wie die Oberfläche der Anlage es tut."""
    treffer = []
    ergebnisse = []
    for node in structure:
        node_id = node.get("nodeId")
        for fct in node.get("functions", []):
            if fct.get("fctType", -1) < 0:
                continue
            praefix = f"/1/{node_id}/{fct.get('fctId')}"
            for index in range(STOERSPEICHER_EINTRAEGE):
                oid = f"{praefix}/{STOERSPEICHER_GNMN}/{index}"
                data, status = probe.lookup(oid)
                eintrag = {
                    "oid": oid,
                    "funktion": fct.get("name"),
                    "status": status,
                    "data": data,
                }
                ergebnisse.append(eintrag)
                grund = str(data.get("reason") or "") if isinstance(data, dict) else ""
                print(
                    f"    {oid:24} HTTP {status:>3}  {grund[:60]}",
                    flush=True,
                )
                if status == 200:
                    treffer.append(eintrag)
                    print(f"    TREFFER  {oid}  {json.dumps(data, ensure_ascii=False)[:200]}")
                elif status == 409 and index == 0:
                    # Diese Funktion führt keinen Störspeicher – die übrigen
                    # neun Anfragen wären reine Zeitverschwendung.
                    break
    if not treffer:
        print("    kein Störspeicher lesbar")
    return {"treffer": treffer, "alle": ergebnisse}


# Endpunkte unter `/api/1.0/`. Die Steuerung verrät selbst, welche es gibt:
# Auf einen unbekannten Namen antwortet sie
#
#     503  {"reason": "endpoint <name> does not exist."}
#
# Damit lässt sich die Liste **aufzählen** statt raten. Die Namen unten stehen
# als Zeichenketten im Quelltext der Weboberfläche; ergänzt sind ein paar
# naheliegende für den Störspeicher.
ENDPUNKT_KANDIDATEN = (
    # belegt aus dem Quelltext
    "lookup",
    "datapoint",
    "object",
    "monitoring",
    "config/Alarm",
    "config/DynIP",
    "config/network",
    "scan/nodes/status",
    "settings/systemtime/interval",
    "systemtime/timezone",
    "systemtime/ntpserver",
    "user",
    "user/group",
    # Aufzeichnung – laut Quelltext unter `dprecorder/api/1.0/`
    #
    # Die vollständige Liste steht im Quelltext des Herstellerportals: Es
    # spricht dieselbe Steuerung über einen Weiterleiter an, und die Pfade
    # bilden die lokalen Dienste ab (`/remote/<dienst>/<pfad>` entspricht
    # `/<Dienst>/api/1.0/<pfad>`; belegt an `wsadmin/systemtime/interval` und
    # `dprecorder/settings`, die lokal beide antworten).
    #
    #     /remote/dprecorder/settings   /remote/dprecorder/datalogs
    #     /remote/dprecorder/datalogs/<id>   /remote/dprecorder/interval
    #     /remote/dprecorder/start      /remote/dprecorder/stop
    #     /remote/info/deviceinfo
    #
    # Nur die lesenden Pfade stehen hier. `start`, `stop` und `interval`
    # schreiben in die Gerätekonfiguration und gehören nicht in einen Suchlauf.
    "recorder/oids",
    "recorder/settings",
    "recorder/datalogs",
    "recorder/datalogs/0",
    "deviceinfo",
    "info/deviceinfo",
    # Vermutungen zum Störspeicher
    "errorlog",
    "error",
    "errors",
    "alarm",
    "alarms",
    "message",
    "messages",
    "log",
    "history",
    # Aus `domfie/windhager-rest-api-documentation` – eine fremde
    # Dokumentation des RC7030-Webservers. Sie nennt Dienste, auf die von
    # allein niemand kommt, allen voran **InfoWinFehlerlog**. Ungeprüft, aber
    # aus einer Quelle und nicht geraten.
    "InfoWinFehlerlog",
    "InfoWinHeartbeat",
    "datapoints",
    "nodes",
    "notification",
    "vpn",
    "dynip",
    "scan",
    "led",
    "update",
    # Neuere Steuerungen ordnen Knoten Zonen und einem gewählten Kessel zu;
    # beide Listen sagen, unter welcher Zone ein Knoten zu lesen ist.
    "Zones",
    "kesselwahl",
    "scan/status",
    # Pfade, die die Integration selbst abfragt, und Funde aus der Firmware.
    # `windyndata` nur ohne Adresse: Mit Adresse löst die App eine Zündung aus.
    "info/LONApp",
    "systemtime",
    "fehlerlog",
    "heartbeat",
    "windyndata",
    "gui/version",
    "buildinfo",
    "version",
)

# Basispfade, unter denen die Kandidaten gesucht werden.
ENDPUNKT_BASEN = (
    "/api/1.0/",
    "/dprecorder/api/1.0/",
    "/WsAdmin/api/1.0/",
    # Ebenfalls aus der fremden Dokumentation: Der Webserver trägt mehrere
    # Dienste nebeneinander. Unangemeldet antworten alle mit 401 – das sagt
    # nichts; erst der angemeldete Lauf unterscheidet.
    "/RestApiRC7030/api/1.0/",
    "/WsFUP7030/api/1.0/",
    "/DcmRC7030/api/1.0/",
    "/InfoWinFehlerlog/api/1.0/",
    "/InfoWinHeartbeat/api/1.0/",
    # Das Portal spricht `info/deviceinfo` als eigenen Dienst an; welcher Mount
    # das lokal ist, steht nicht fest.
    "/info/api/1.0/",
)

# Wie oft ein 401 mit frischer Anmeldung wiederholt wird, bevor der Kandidat
# als „unklar" gilt. Drei reichen: Die Steuerung verwirft ihren Nonce sporadisch,
# nicht dauerhaft.
ENDPUNKT_ANLAEUFE = 3


# ------------------------------------------------------- LON-Netzwerkvariablen
# **Was hier gemessen wird und warum.**
#
# Jeder Knoten führt neben seinen Funktionen eine `NV's` (fctType −1): die
# LON-Netzwerkschnittstelle des Bausteins, also seine Ein- und Ausgänge zur
# Verständigung mit den anderen Modulen. Am geprüften PuroWIN sind das 172
# Einträge über vier Knoten.
#
# Drei Dinge sind daran geklärt:
#
# 1. Die Menü-Liste ist ein **Katalog**: Sie nennt `nvIndex`, `nvName` und den
#    LON-Datentyp `snvtName`, der Wert steht durchgängig auf `"-"`. Ein leerer
#    Wert im Katalog heißt deshalb nicht, dass der Eintrag keine Daten führt.
# 2. Einzeln gelesen liefert `/1/<node>/32/<gruppe>/<nvIndex>/0` einen Wert –
#    und die **Gruppe wird ignoriert**: `…/0/3/0` und `…/4/3/0` geben dasselbe.
#    Daneben ist die kürzere Form ohne abschließendes `/0`, dafür mit
#    `?count=&offset=`, belegt. Welche eine Steuerung beantwortet, hängt an
#    ihrer Generation – der Lauf probiert beide und behält die, die trägt.
# 3. Die Werte sind **rohe LON-Nutzlasten**, keine Zahlen: `"0 0"`,
#    sechsundzwanzig Nullen, `"2026 8 5 10 19 10"`.
#
# Offen ist die Frage, die über das ganze Vorhaben entscheidet: **Wie viele der
# Einträge führen überhaupt Daten?** Ein Gutteil ist auf einer konkreten Anlage
# nicht verdrahtet und meldet die Ungültig-Marke seines Datentyps – 65535 bei
# `SNVT_count`, −1 bei `SNVT_hvac_mode`, 163.835 bei `SNVT_lev_percent`.
#
# Deshalb liest der Lauf `nv` einmalig jeden Eintrag und zählt aus. Das kostet
# rund 172 Anfragen und anderthalb Minuten – einmal, nicht im Betrieb.
NV_GRUPPEN = (0,)

# Der fctType, unter dem eine Steuerung ihren LON-Adressraum führt. Er ist kein
# Gerätetyp: Wo er steht, sind `gn/mn` Gruppe und nvIndex, nicht Datenpunkt.
FCT_TYPE_NV = -1

# Die belegten Adressformen für den Einzelabruf einer Netzwerkvariablen, in der
# Reihenfolge, in der sie probiert werden.
NV_ADRESSFORMEN = (
    "{prefix}/{gruppe}/{index}/0",
    "{prefix}/{gruppe}/{index}?count=10&offset=0",
)

# Wieviele Indizes ein Blindlauf abklopft, wenn die Funktion keinen Katalog
# liefert. Die vier bekannten Funktionen führen 16 bis 68 Einträge; 80 deckt
# das mit Rand ab und bleibt eine Anfragezahl, die eine Anlage wegsteckt.
NV_BLIND_MAX = 80

# Wieviele davon zuerst geprüft werden. Antwortet keine, hat die Funktion
# keine Netzwerkvariablen und die restlichen Versuche kosten nur Zeit.
NV_BLIND_PROBE = 5

# Werte, die „nicht verdrahtet" heißen, nicht „gemessen". Sie stehen so in der
# LON-Norm: Jeder SNVT hat eine Marke am Rand seines Wertebereichs.
NV_UNGUELTIG = {
    "SNVT_count": {"65535"},
    "SNVT_hvac_mode": {"-1"},
    "SNVT_lev_percent": {"163.835", "-163.84"},
    "SNVT_temp_p": {"327.67", "-327.68"},
    "SNVT_lev_cont": {"163.835", "-163.84"},
    "SNVT_time_sec": {"6553.5"},
    "SNVT_time_min": {"65535"},
}

# Datentypen, die mehrere Felder in einer Zeichenkette tragen. Aus ihnen wird
# ohne eigene Zerlegung kein Sensor.
NV_STRUKTUREN = {
    "SNVT_obj_request",
    "SNVT_obj_status",
    "SNVT_state",
    "SNVT_switch",
    "SNVT_time_stamp",
}


def nv_bewerten(snvt: str | None, wert: str | None) -> str:
    """Einordnen, was ein gelesener NV-Wert taugt."""
    if wert in (None, "", "-", "-.-"):
        return "leer"
    text = str(wert).strip()
    if snvt in NV_STRUKTUREN:
        return "struktur"
    if snvt is None:
        return "ohne Typ"
    if text in NV_UNGUELTIG.get(snvt, ()):
        return "ungueltig"
    try:
        float(text)
    except ValueError:
        return "kein Zahlwert"
    return "brauchbar"


def _nv_lesen(probe: Probe, prefix: str, index, form: str):
    """Eine Netzwerkvariable in der angegebenen Adressform lesen."""
    pfad = form.format(prefix=prefix, gruppe=NV_GRUPPEN[0], index=index)
    data, status = probe.lookup(pfad)
    # Die kurze Form antwortet je nach Firmware mit einem einelementigen Array
    # statt mit dem Objekt.
    if isinstance(data, list):
        data = data[0] if data else None
    wert = data.get("value") if isinstance(data, dict) else None
    return pfad, status, wert


def _nv_form_bestimmen(probe: Probe, prefix: str, index) -> str:
    """Die Adressform ermitteln, die diese Funktion beantwortet.

    Einmal je Funktion, an einem einzigen Eintrag. Antwortet keine Form mit
    einem Wert, bleibt es bei der ersten – dann steht in der Datei ein
    ehrliches „leer" statt einer stillen Umschaltung.
    """
    for form in NV_ADRESSFORMEN:
        _, status, wert = _nv_lesen(probe, prefix, index, form)
        if status == 200 and wert not in (None, "", "-"):
            return form
    return NV_ADRESSFORMEN[0]


def suche_nv_werte(probe: Probe, menus: dict) -> dict:
    """Jeden LON-Eintrag lesen und einordnen.

    **Ohne Stichprobe.** Eine Stichprobe je Datentyp war richtig, solange die
    Adressform unklar war – sie ist geklärt. Ein Schalter dafür wäre nur noch
    eine Fehlerquelle: Wird er im geführten Modus nicht durchgereicht, steht
    hinterher eine Stichprobe in der Datei, obwohl der Vollabzug gemeint war.
    """
    ziele = [
        (fct, eintrag)
        for fct in menus["functions"]
        if fct.get("fct_type", 0) == -1
        for eintrag in fct["datapoints"].values()
    ]

    # Blindlauf für Funktionen ohne Katalog.
    #
    # Knoten 90 (MB6611 LOP, die Bedieneinheit) meldet in `structure` sehr wohl
    # eine Funktion `NV's`, aber ihre Menüwurzel antwortet mit HTTP 500. Ohne
    # Katalog fällt sie aus der Liste oben heraus, und im Ergebnis sieht es aus,
    # als hätte der Knoten keine Netzwerkvariablen – dabei wurde er nie
    # gefragt. Ein fehlgeschlagener Lesevorgang ist kein Befund.
    for fct in menus["functions"]:
        if fct.get("fct_type", 0) != -1 or fct.get("datapoints"):
            continue
        print(f"    {fct['prefix']} ohne Katalog – Blindlauf über {NV_BLIND_MAX} Indizes")
        ziele.extend((fct, {"nvIndex": i, "_blind": True}) for i in range(NV_BLIND_MAX))

    print(f"    {len(ziele)} Einträge werden gelesen")

    # Die Adressform je Funktion zuerst, seriell: Sie ist die Voraussetzung
    # für alles Weitere und kostet zwei Anfragen.
    formen: dict[str, str] = {}
    for fct, eintrag in ziele:
        prefix = fct["prefix"]
        if prefix not in formen and eintrag.get("nvIndex") is not None:
            formen[prefix] = _nv_form_bestimmen(probe, prefix, eintrag["nvIndex"])
            print(f"    {prefix} Adressform: {formen[prefix]}")

    # **Ein Wert, eine Anfrage.** Die Menü-Ebene liefert für Netzwerkvariablen
    # Namen und Typ, aber keinen Wert (`"value": "-"`); anders als bei
    # Datenpunkten hilft der Sammelabruf hier nicht. An der eigenen Anlage
    # sind das 252 Anfragen – seriell über eine halbe Stunde, in der niemand
    # weiß, ob der Lauf noch lebt. Nebenläufig mit derselben Zahl Arbeiter wie
    # der Menü-Abruf ist es ein Drittel davon; mehr bringt an dieser Steuerung
    # nichts (gemessen 12.08.: drei gegen sechs Arbeiter, 2,7 % Unterschied).
    def lesen(auftrag):
        fct, eintrag = auftrag
        index = eintrag.get("nvIndex")
        prefix = fct["prefix"]
        oid, status, wert = _nv_lesen(probe, prefix, index, formen[prefix])
        return {
            "oid": oid,
            "funktion": prefix,
            "nvIndex": index,
            "nvName": eintrag.get("nvName"),
            "snvtName": eintrag.get("snvtName"),
            "unit": eintrag.get("unit"),
            "status": status,
            "value": wert,
            "urteil": nv_bewerten(eintrag.get("snvtName"), wert) if status == 200 else "Fehler",
        }

    # **Blindlauf abbrechen, wenn nichts antwortet.** Knoten 90 der eigenen
    # Anlage – das Bedienteil – beantwortet keine einzige NV-Adresse: 80
    # Versuche, 80 Fehler, neun Minuten von 34. Wer auf die ersten fünf nicht
    # antwortet, antwortet auf keine.
    blind_je_funktion: dict[str, list] = {}
    for fct, eintrag in ziele:
        if eintrag.get("_blind"):
            blind_je_funktion.setdefault(fct["prefix"], []).append(eintrag)
    stumm = set()
    for prefix, eintraege in blind_je_funktion.items():
        proben = eintraege[:NV_BLIND_PROBE]
        if all(_nv_lesen(probe, prefix, e["nvIndex"], formen[prefix])[1] != 200 for e in proben):
            stumm.add(prefix)
            print(f"    {prefix} antwortet auf keine Netzwerkvariable – Blindlauf abgebrochen")
    if stumm:
        ziele = [z for z in ziele if not (z[1].get("_blind") and z[0]["prefix"] in stumm)]

    auftraege = [z for z in ziele if z[1].get("nvIndex") is not None and z[0]["prefix"] in formen]
    versuche = []
    with ThreadPoolExecutor(max_workers=probe.workers) as pool:
        for nummer, ergebnis in enumerate(pool.map(lesen, auftraege), start=1):
            versuche.append(ergebnis)
            if nummer % 20 == 0 or nummer == len(auftraege):
                print(f"      {nummer}/{len(auftraege)} …", flush=True)

    zaehler: dict[str, int] = {}
    for v in versuche:
        zaehler[v["urteil"]] = zaehler.get(v["urteil"], 0) + 1
    print("\n    Einordnung:")
    for urteil, anzahl in sorted(zaehler.items(), key=lambda x: -x[1]):
        print(f"      {urteil:14} {anzahl:>4}")
    brauchbar = [v for v in versuche if v["urteil"] == "brauchbar"]
    print(f"\n    Als Sensor verwendbar: {len(brauchbar)} von {len(versuche)}")
    if brauchbar:
        print("    Beispiele:")
        for v in brauchbar[:12]:
            print(f"      {str(v['nvName'])[:26]:28} {v['unit'] or ''!s:8} {v['value']}")
    return {
        "brauchbar": brauchbar,
        "zaehler": zaehler,
        "adressformen": formen,
        "alle": versuche,
    }


# Toleranz beim Zuordnen eines LON-Werts zu einem Datenpunkt derselben Anlage.
VERGLEICH_TOLERANZ = 0.05


def vergleich_lon_oid(menus: dict, nv: dict) -> dict:
    """LON-Werte gegen die OID-Datenpunkte derselben Anlage stellen.

    Die Frage ist nicht das Tempo – ein Menü-Fenster liefert zehn Werte je
    Anfrage, eine Netzwerkvariable einen. Die Frage ist, ob LON etwas liefert,
    das es als OID nicht gibt.

    Zugeordnet wird über Einheit und Wert am selben Knoten, mit Toleranz. Das
    ist eine **Heuristik**: Zwei Fühler mit gleichem Messwert sind nicht zu
    unterscheiden. Sie taugt für die Frage „hat dieser LON-Wert überhaupt eine
    Entsprechung", nicht für „welche".

    Beide Seiten müssen aus **demselben Lauf** stammen. Ein Messwert, der sich
    zwischen Menü-Abzug und LON-Abruf bewegt hat – eine Außentemperatur etwa –
    findet sonst keine Entsprechung mehr und steht fälschlich in `ohne_oid`.
    """

    def _zahl(wert) -> float | None:
        try:
            return float(str(wert).replace(",", "."))
        except (TypeError, ValueError):
            return None

    je_knoten: dict[str, list[tuple[str, float]]] = {}
    for fct in menus["functions"]:
        if fct.get("fct_type", 0) == -1:
            continue
        teile = fct["prefix"].strip("/").split("/")
        knoten = teile[1] if len(teile) > 1 else ""
        for eintrag in (fct.get("datapoints") or {}).values():
            wert = _zahl(eintrag.get("value"))
            if wert is not None:
                je_knoten.setdefault(knoten, []).append((eintrag.get("unit") or "", wert))

    ohne, mit = [], []
    for eintrag in nv.get("brauchbar", []):
        wert = _zahl(eintrag.get("value"))
        if wert is None:
            continue
        teile = str(eintrag.get("funktion", "")).strip("/").split("/")
        kandidaten = je_knoten.get(teile[1] if len(teile) > 1 else "", [])
        einheit = eintrag.get("unit") or ""
        treffer = any(e == einheit and abs(w - wert) <= VERGLEICH_TOLERANZ for e, w in kandidaten)
        (mit if treffer else ohne).append(
            {
                "nvName": eintrag.get("nvName"),
                "snvtName": eintrag.get("snvtName"),
                "unit": einheit,
                "value": eintrag.get("value"),
                "oid": eintrag.get("oid"),
            }
        )

    return {
        "mit_oid": mit,
        "ohne_oid": ohne,
        "hinweis": (
            "Zuordnung über Einheit und Wert am selben Knoten, Toleranz "
            f"{VERGLEICH_TOLERANZ}. Gleiche Messwerte sind nicht unterscheidbar – "
            "die Liste beantwortet 'hat eine Entsprechung', nicht 'welche'."
        ),
    }


# Wieviel vom Antwortkörper eines gefundenen Endpunkts abgelegt wird.
ENDPUNKT_INHALT_MAX = 4000


def _gekuerzt(data, grenze: int = ENDPUNKT_INHALT_MAX):
    """Antwortkörper für die Ablage kürzen.

    Ein `200` ohne seinen Inhalt ist eine halbe Auskunft. Der erste Lauf hielt
    nur den Status fest, und danach stand in der Datei, dass `config/Alarm`,
    `datapoints` und `nodes` mit 200 antworten – aber nicht, *womit*. Genau
    dort hätte die Meldungsliste stehen können.
    """
    if data is None:
        return None
    text = json.dumps(data, ensure_ascii=False)
    if len(text) <= grenze:
        return data
    return {"gekuerzt": True, "laenge": len(text), "anfang": text[:grenze]}


def abzugsname(out_dir: Path, stem: str, abzug: dict) -> Path:
    """Der Dateiname sagt, ob der Lauf etwas gelesen hat.

    Ohne den Zusatz sieht eine Fehlerantwort wie ein Abzug aus und wird als
    solcher weitergereicht.
    """
    if abzug.get("status") != 200:
        return out_dir / f"{stem}_vollabzug-fehlgeschlagen.json"
    return out_dir / f"{stem}_vollabzug.json"


def hole_vollabzug(probe: Probe) -> dict:
    """`/api/1.0/datapoints` ganz lesen und ausmessen.

    Der Endpunkt stand seit dem ersten Endpunktlauf als „vorhanden, HTTP 200"
    in der Liste, ohne dass jemand hineingesehen hätte. Er liefert **alle**
    Datenpunkte samt Wert, Typ, Einheit, Schreibschutz und Zeitstempel in
    *einer* Antwort – die Integration holt heute jeden einzeln.

    Die Frage, die dieser Lauf beantwortet: Deckt der Abzug alle Knoten ab
    oder nur einen? Davon hängt ab, ob er den Abfragepfad ersetzen kann.
    """
    data, status = probe.get(f"{probe.base}/api/1.0/datapoints")
    if status != 200 or not isinstance(data, list):
        print(f"    Vollabzug nicht lesbar: HTTP {status}")
        if status == 404:
            print("    Diese Steuerung kennt den Endpunkt nicht. Das ist kein Bedienfehler;")
            print("    lies stattdessen `structure` und `menus` – oder gleich `all`.")
        return {"status": status, "data": data}

    je_praefix: dict[str, int] = {}
    ohne_wert = 0
    zeitstempel: set[str] = set()
    for eintrag in data:
        teile = str(eintrag.get("OID", "")).split("/")
        praefix = "/".join(teile[:4]) if len(teile) >= 4 else "?"
        je_praefix[praefix] = je_praefix.get(praefix, 0) + 1
        if eintrag.get("value") in (None, ""):
            ohne_wert += 1
        if eintrag.get("timestamp"):
            zeitstempel.add(str(eintrag["timestamp"]))

    print(f"    {len(data)} Datenpunkte in einer Anfrage")
    for praefix, anzahl in sorted(je_praefix.items()):
        print(f"      {praefix:<14} {anzahl:>4}")
    print(f"    ohne Wert: {ohne_wert}, verschiedene Zeitstempel: {len(zeitstempel)}")
    return {
        "status": status,
        "anzahl": len(data),
        "je_praefix": je_praefix,
        "ohne_wert": ohne_wert,
        "zeitstempel": sorted(zeitstempel)[:20],
        "data": data,
    }


def miss_stapelabruf(probe: Probe, oids: list[str]) -> dict:
    """Prüfen, ob `/api/1.0/datapoints?OID=…` mehrere Adressen auf einmal liest.

    Die Herstellerbeschreibung führt den Parameter als Liste im CSV-Format und
    sagt zum Aufruf ohne Parameter: er gibt zurück, was gerade im
    Datenzwischenspeicher liegt. Das erklärt dessen feste Obergrenze und macht
    ihn zu etwas anderem als einem Sammelabruf.

    Gemessen wird beides gegeneinander: dieselben Adressen einzeln über
    ``lookup``, dann in einem Zug. Verglichen werden Anzahl, Werte und Dauer –
    ein Stapel, der schneller ist, aber andere Werte liefert, taugt nichts.
    """
    einzeln: dict[str, str | None] = {}
    begonnen = time.monotonic()
    for oid in oids:
        data, status = probe.lookup(oid)
        einzeln[oid] = data.get("value") if status == 200 and isinstance(data, dict) else None
    dauer_einzeln = time.monotonic() - begonnen

    begonnen = time.monotonic()
    data, status = probe.get(f"{probe.base}/api/1.0/datapoints?OID={','.join(oids)}")
    dauer_stapel = time.monotonic() - begonnen

    gestapelt: dict[str, str | None] = {}
    if status == 200 and isinstance(data, list):
        for eintrag in data:
            if isinstance(eintrag, dict) and eintrag.get("OID"):
                gestapelt[str(eintrag["OID"])] = eintrag.get("value")

    abweichend = sorted(o for o in oids if str(einzeln.get(o)) != str(gestapelt.get(o)))
    print(f"    einzeln:  {len(oids)} Anfragen, {dauer_einzeln:.2f} s")
    print(
        f"    Stapel:   1 Anfrage, HTTP {status}, {len(gestapelt)} Adressen, {dauer_stapel:.2f} s"
    )
    if abweichend:
        print(f"    abweichende Werte: {len(abweichend)} von {len(oids)}")
    return {
        "status": status,
        "angefragt": len(oids),
        "geliefert": len(gestapelt),
        "sekunden_einzeln": round(dauer_einzeln, 3),
        "sekunden_stapel": round(dauer_stapel, 3),
        "abweichend": abweichend,
        "einzeln": einzeln,
        "stapel": gestapelt,
    }


def suche_endpunkte(probe: Probe) -> dict:
    """Aufzählen, welche Endpunkte die Steuerung kennt.

    Rein lesend: Jeder Kandidat wird mit GET angefragt. Es gibt **drei**
    Ausgänge, nicht zwei:

    ``503 endpoint <name> does not exist``
        Die Anlage kennt den Namen nicht. Verlässlich.
    ``401``
        Nichts gelernt. Der Digest-Nonce der Steuerung ist verbraucht, und das
        hat mit dem Endpunkt nichts zu tun. Solche Antworten als „vorhanden"
        zu zählen war der Fehler des ersten Laufs: `errorlog`, `message` und
        `alarm` standen als Fund in der Liste, obwohl niemand sie je gesehen
        hatte.
    alles andere
        Der Endpunkt existiert – auch ein `400` wegen fehlendem Parameter oder
        ein `500 Wrong formatted OID` ist eine Auskunft und damit ein Beleg.

    Bei ``401`` wird bis zu ``ENDPUNKT_ANLAEUFE``-mal mit frischer Anmeldung
    nachgefasst; bleibt es dabei, gilt der Kandidat als **unklar** und nicht
    als Fund.
    """
    ergebnisse = []
    for basis in ENDPUNKT_BASEN:
        for name in ENDPUNKT_KANDIDATEN:
            for anlauf in range(ENDPUNKT_ANLAEUFE):
                data, status = probe.get(f"{probe.base}{basis}{name}")
                if status != 401:
                    break
                # Frische Anmeldung erzwingen und noch einmal.
                probe._local.opener = None
                if anlauf + 1 < ENDPUNKT_ANLAEUFE:
                    time.sleep(0.4)
            # `get` liefert, was die Anlage schickt – und das ist nicht immer
            # ein Objekt: `lookup` etwa antwortet mit einer **Liste**. Ein
            # blindes `.get("reason")` darauf beendet den ganzen Lauf mit
            # einem AttributeError, noch bevor eine Datei geschrieben ist.
            grund = str(data.get("reason") or "") if isinstance(data, dict) else ""
            fehlt = (status == 503 and "does not exist" in grund) or status == 404
            unklar = status == 401
            ergebnisse.append(
                {
                    "pfad": f"{basis}{name}",
                    "status": status,
                    "reason": grund[:200],
                    "vorhanden": not fehlt and not unklar,
                    "unklar": unklar,
                    "inhalt": _gekuerzt(data) if status == 200 else None,
                }
            )
            if ergebnisse[-1]["vorhanden"]:
                vorschau = ""
                if status == 200:
                    vorschau = json.dumps(data, ensure_ascii=False)[:80]
                print(
                    f"    GIBT ES  {basis}{name:30} HTTP {status:>3}  {grund[:80]}{vorschau}",
                    flush=True,
                )
            elif unklar:
                print(f"    unklar   {basis}{name:30} HTTP 401 (Anmeldung)", flush=True)
    gefunden = [e for e in ergebnisse if e["vorhanden"]]
    offen = [e for e in ergebnisse if e["unklar"]]
    print(
        f"    {len(gefunden)} vorhanden, {len(offen)} unklar, "
        f"{len(ergebnisse) - len(gefunden) - len(offen)} kennt sie nicht"
    )
    return {"vorhanden": gefunden, "unklar": offen, "alle": ergebnisse}


def _ist_nv_antwort(data) -> bool:
    """Ob die Antwort eine LON-Netzwerkvariable statt des gefragten Datenpunkts ist.

    An einer NV-Funktion (`fctType -1`, Präfix `/1/<knoten>/32`) deutet die
    Steuerung die Adresse um: Die Gruppe wird ignoriert, der Member gilt als
    `nvIndex`. `/1/16/32/3/61/0` beantwortet deshalb nicht „Gruppe 3,
    Member 61", sondern liefert die Netzwerkvariable Nummer 61. Ohne diese
    Prüfung zählt jede geprüfte Position an jeder NV-Funktion als Treffer.
    """
    return isinstance(data, dict) and "nvName" in data


def suche_statisch(probe: Probe, structure: list) -> dict:
    """Die statischen Navigationseinträge an allen Knoten und Funktionen suchen."""
    praefixe: list[str] = []
    for node in structure:
        node_id = node.get("nodeId")
        praefixe.append(f"/1/{node_id}/0")
        for fct in node.get("functions", []):
            kandidat = f"/1/{node_id}/{fct.get('fctId')}"
            if kandidat not in praefixe:
                praefixe.append(kandidat)

    positionen = statische_navigation(probe)
    ziele = [(f"{p}/{gnmn}", p, gnmn) for p in praefixe for gnmn in positionen]
    print(
        f"    {len(ziele)} Kombinationen aus {len(praefixe)} Präfixen und "
        f"{len(positionen)} Positionen werden geprüft"
    )

    def read(ziel):
        oid, praefix, gnmn = ziel
        # **Beide Endpunkte, immer.** Ein Störspeicher ist eine Liste und
        # spricht damit für `object` – die Weboberfläche der Anlage liest ihn
        # aber über `lookup` (`'api/1.0/' + 'lookup' + <OID> + '?count='`).
        # Die Endpunkte antworten unabhängig voneinander: Ein `409 – invalid
        # Identifier` von `object` besagt über `lookup` nichts. Wer nach dem
        # ersten 409 aufhört, hält eine ungestellte Frage für beantwortet.
        data, status = probe.obj(oid)
        wie = "object"
        antworten = {"object": status}
        if status != 200:
            data2, status2 = probe.lookup(f"/{oid.lstrip('/')}")
            antworten["lookup"] = status2
            if status2 == 200:
                data, status, wie = data2, status2, "lookup"
        return {
            "oid": oid,
            "prefix": praefix,
            "gnmn": gnmn,
            "status": status,
            "endpunkt": wie,
            "antworten": antworten,
            "umgedeutet": _ist_nv_antwort(data),
            "data": data,
        }

    # Bewusst nacheinander statt über `probe.map`: Es sind wenige Dutzend
    # Anfragen, und jeder Thread müsste sich einzeln anmelden. Bei einer Suche,
    # deren Ergebnis „gibt es nicht" sein darf, ist ein sauberer Lauf mehr wert
    # als ein schneller.
    #
    # Jede Zeile wird gemeldet, sobald sie da ist. Vorher lief die Schleife
    # stumm durch – bei einer Anlage, die auf nicht vorhandene Adressen
    # langsam antwortet, sah ein laufender Suchlauf wie ein hängender aus.
    treffer = []
    umgedeutet = []
    ergebnisse = []
    for nummer, ziel in enumerate(ziele, start=1):
        eintrag = read(ziel)
        ergebnisse.append(eintrag)
        beschreibung = positionen[eintrag["gnmn"]]
        print(
            f"    [{nummer:2}/{len(ziele)}] {eintrag['oid']:22} "
            f"HTTP {eintrag['status']:>3}  {beschreibung}",
            flush=True,
        )
        if eintrag["status"] == 200 and not eintrag["umgedeutet"]:
            treffer.append(eintrag)
            print(f"    TREFFER  {eintrag['oid']:22} {beschreibung} (ueber {eintrag['endpunkt']})")
        elif eintrag["umgedeutet"]:
            umgedeutet.append(eintrag)
            print(f"    (Netzwerkvariable statt Datenpunkt: {eintrag['data'].get('nvName')})")
    if not treffer:
        print("    kein statischer Eintrag lesbar – die Anlage führt sie woanders")
    if umgedeutet:
        print(f"    {len(umgedeutet)} Antworten waren umgedeutete Netzwerkvariablen, keine Treffer")
    return {"treffer": treffer, "umgedeutet": umgedeutet, "alle": ergebnisse}


# Welche Funktions-Ids an einem Knoten probiert werden, der in `GET /1` keine
# gewöhnliche Funktion meldet. Bei einem Kessel ist es die 0; mehr zu probieren
# hieße raten, und jeder Versuch kostet eine Anfrage.
FCT_IDS_UNGEMELDET = (0,)


def _funktionen_eines_knotens(node: dict) -> list[dict]:
    """Die Funktionen, die an diesem Knoten gelesen werden – gemeldete und nicht.

    **Ein Knoten kann antworten, ohne sich anzukündigen.** Es gibt Anlagen,
    deren Kessel in `GET /1` ausschließlich seinen LON-Adressraum führt und
    keine Funktion mit `fctType`. Die Datenpunkte darunter antworten trotzdem –
    öffentliche Auslesungen derselben Kesselreihe lesen genau diese Adressen.

    Wer nur die gemeldeten Funktionen liest, hält so einen Knoten für leer.
    Deshalb bekommt jeder Knoten ohne gewöhnliche Funktion die Kandidaten aus
    `FCT_IDS_UNGEMELDET` mit; ob es sie gibt, beantwortet der Abruf selbst.
    """
    gemeldet = [f for f in node.get("functions", []) if not f.get("lock")]
    if any(isinstance(f.get("fctType"), int) and f["fctType"] >= 0 for f in gemeldet):
        return gemeldet

    vergeben = {f.get("fctId") for f in gemeldet}
    return gemeldet + [
        {"fctId": fct_id, "fctType": None, "name": "(nicht gemeldet)", "_ungemeldet": True}
        for fct_id in FCT_IDS_UNGEMELDET
        if fct_id not in vergeben
    ]


def fetch_menus(probe: Probe, structure: list) -> dict:
    """Alle Menü-Ebenen je Funktion einlesen (Sammelabruf)."""
    result = {
        "host": probe.host,
        "probed": dt.datetime.now().isoformat(timespec="seconds"),
        "structure": structure,
        "functions": [],
    }

    paare = [(n, f) for n in structure for f in _funktionen_eines_knotens(n)]
    for nr, (node, fct) in enumerate(paare, start=1):
        fortschritt(_t("Funktion {} von {}", nr, len(paare)))
        node_id = node.get("nodeId")
        # `fctType -1` ist die Funktion `NV's`: der LON-Adressraum des
        # Knotens. Bis heute wurde sie hier übersprungen – und damit auch
        # in der Integration, die denselben Filter hat. Zwei fremde
        # Projekte lesen daraus rund 200 zusätzliche Werte je Anlage
        # (Betriebsstunden, Verbrauch, Zündungen), und Knoten 90 – die
        # Bedieneinheit – besteht ausschließlich daraus.
        #
        # Gelesen wird sie genauso wie jede andere Funktion: `lookup
        # /1/<node>/<fctId>` liefert die Menü-Ebenen mit Anzahl. Die Sonde
        # nimmt sie jetzt mit, damit überhaupt einmal Daten vorliegen,
        # bevor irgendjemand etwas darauf baut.
        if fct.get("lock"):
            continue
        prefix = f"/1/{node_id}/{fct['fctId']}"
        root, status = probe.lookup(prefix)
        entry = {
            "prefix": prefix,
            "node_id": node_id,
            "fct_id": fct.get("fctId"),
            "fct_type": fct.get("fctType"),
            "name": fct.get("name"),
            "device_id": (node.get("device") or {}).get("id"),
            "program_id": node.get("programId"),
            "root_status": status,
            "ungemeldet": bool(fct.get("_ungemeldet")),
            "menus": {},
            "menu_errors": {},
            "datapoints": {},
        }

        if status == 200 and isinstance(root, list) and root and "id" in root[0]:
            entry["menus"] = {str(m.get("id")): m.get("count") for m in root}
            entry["unvollstaendig"] = {}

            def read_menu(menu_id, _prefix=prefix, _entry=entry):
                url = f"{probe.base}/api/1.0/lookup{_prefix}/{menu_id}"
                expected = _entry["menus"].get(menu_id) or 0
                items, strategy, mstatus = fetch_menu_all(probe, url, expected, probe.page_strategy)
                if strategy is not None and probe.page_strategy is None:
                    probe.page_strategy = strategy
                return menu_id, items, mstatus

            for menu_id, items, mstatus in probe.map(read_menu, list(entry["menus"])):
                if mstatus == 200 and isinstance(items, list):
                    for item in items:
                        # LON-Netzwerkvariablen tragen **kein** `OID`-Feld,
                        # sondern `nvIndex` und `nvName`. Ohne diesen Zweig
                        # fielen sie stillschweigend heraus: Der erste Lauf
                        # meldete je NV-Funktion „1 Menü, 30 Einträge" und
                        # danach null Datenpunkte.
                        #
                        # Ihre Adresse ist der Menü-Eintrag selbst; als
                        # Schlüssel dient deshalb der Pfad mit dem Index.
                        oid = _eintrag_schluessel(item, f"{entry['prefix']}/{menu_id}")
                        if oid:
                            item["_menu"] = menu_id
                            entry["datapoints"][oid] = item
                    expected = entry["menus"].get(menu_id) or 0
                    if len(items) < expected:
                        entry["unvollstaendig"][menu_id] = [len(items), expected]
                else:
                    entry["menu_errors"][menu_id] = mstatus
        else:
            entry["fallback"] = "Funktions-Root liefert keine Menüliste"

        result["functions"].append(entry)
        soll = sum(v or 0 for v in entry["menus"].values())
        ist = len(entry["datapoints"])
        hinweis = ""
        if entry["menus"] and ist < soll:
            hinweis = f"  ({soll - ist} fehlen)"
        if entry["menu_errors"]:
            hinweis += f"  [{len(entry['menu_errors'])} Menüs ohne Antwort]"
        print(
            f"    {prefix:<12} fctType {entry['fct_type']!s:>3}  "
            f"{str(entry['name'])[:22]:<22} Menüs {len(entry['menus']):>3}  "
            f"Datenpunkte {ist:>4}{hinweis}"
        )

    strategy = probe.page_strategy
    if strategy and strategy != "keine":
        result["seitenmodus"] = strategy[0]
        print(f"    Nachladen weiterer Menü-Seiten funktioniert über: {strategy[0]}")
    elif strategy == "keine":
        result["seitenmodus"] = "keine"
        print(
            "    Das Gerät liefert je Menü nur die ersten 10 Datenpunkte (kein Nachladen möglich)"
        )
    return result


def run_diagnose(probe: Probe, menus: dict) -> dict:
    """Prüfen, wie sich weitere Datenpunkte einer Menü-Ebene abrufen lassen."""
    candidates = [
        (fct, menu, count)
        for fct in menus["functions"]
        for menu, count in fct["menus"].items()
        if (count or 0) > PAGE_SIZE
    ]
    if not candidates:
        print("    keine Menü-Ebene mit mehr als 10 Datenpunkten vorhanden")
        return {}

    fct, menu, count = max(candidates, key=lambda c: c[2])
    url = f"{probe.base}/api/1.0/lookup{fct['prefix']}/{menu}"
    print(f"    Testebene: {fct['prefix']}/{menu} mit {count} Datenpunkten laut Gerät")

    first, status = probe.get(url)
    if status != 200 or not isinstance(first, list):
        print(f"    Grundabruf fehlgeschlagen (HTTP {status})")
        return {"status": status}
    known = set(_oids_of(first))
    erster = f", erster: {sorted(known)[0]}" if known else ""
    print(f"    Grundabruf liefert {len(first)} Einträge{erster}")

    findings = {
        "ebene": f"{fct['prefix']}/{menu}",
        "count": count,
        "grundabruf": len(first),
        "varianten": {},
    }
    for name, build in PAGE_STRATEGIES:
        test_url = build(url, PAGE_SIZE)
        data, st = probe.get(test_url)
        if isinstance(data, list):
            oids = set(_oids_of(data))
            neu = len(oids - known)
            ergebnis = f"HTTP {st}, {len(data)} Einträge, davon {neu} neu"
            findings["varianten"][name] = {"status": st, "eintraege": len(data), "neu": neu}
        else:
            ergebnis = f"HTTP {st}"
            findings["varianten"][name] = {"status": st, "eintraege": 0, "neu": 0}
        marker = " <== funktioniert" if findings["varianten"][name]["neu"] else ""
        print(f"      {name:<12} {test_url.split('/api/1.0/lookup')[1]:<28} {ergebnis}{marker}")

    if not any(v["neu"] for v in findings["varianten"].values()):
        print(
            "    Keine Variante liefert weitere Datenpunkte – die fehlenden müssen "
            "einzeln gelesen werden."
        )
    return findings


# Datenpunkte, die die Anlage als Struktur führt, aber in keiner Menü-Ebene
# nennt. Sie stehen in `res/xml/StaticNavAssignment.xml`, das die Steuerung
# ohne Anmeldung ausliefert:
#
#     <staticentry type="errorlog"   oidextension="2/90/0"/>
#     <staticentry type="timeprogram" oidextension="4/80/0"/>
#     <staticentry type="parameter"  oidextension="4/42/0"/>
#
# `2/90` ist der **Störspeicher** – die Meldungsliste des Bediengeräts. Weil
# sie in keinem Menü steht, hat der Menü-Abzug sie nie gefunden. Die vollständige
# Liste holt `statische_navigation` von der Anlage; das hier ist der Rückfall.
STATISCHE_OBJEKTE = ("2/90/0", "4/80/0")


def fetch_objects(probe: Probe, menus: dict) -> dict:
    """Strukturierte Objekte (Zeitprogramme, Störspeicher) lesen."""
    targets = [
        oid
        for fct in menus["functions"]
        for oid, item in fct["datapoints"].items()
        if item.get("typeId") == 30
    ]
    # Die Zeitprogramme stehen in keiner Menü-Ebene: Ohne die statischen
    # Positionen prüfte dieser Abzug nur die Textobjekte und meldete „keine
    # Zeitprogramme" an einer Anlage, die sieben davon führt.
    statisch = statische_navigation(probe)
    targets += [
        f"{fct['prefix']}/{gnmn}"
        for fct in menus["functions"]
        for gnmn in statisch
        if f"{fct['prefix']}/{gnmn}" not in targets
    ]
    # Nicht jede Steuerung nennt ihre Zeitprogramme in der Navigation; die
    # Adressen, die der Hersteller über den object-Endpunkt liest, kommen dazu.
    if DEVICE_DB is not None:
        for fct in menus["functions"]:
            for gnmn in sorted(DEVICE_DB.get_objekte(fct.get("fct_type"))):
                if (oid := f"{fct['prefix']}/{gnmn}/0") not in targets:
                    targets.append(oid)
    if not targets:
        print("    keine strukturierten Objekte gefunden")
        return {}

    def read(oid):
        # Beide Endpunkte, und beide Antworten festhalten: Welcher der beiden
        # eine Position führt, unterscheidet sich je Steuerung.
        data, status = probe.obj(oid)
        data2, status2 = probe.lookup(f"/{oid.lstrip('/')}")
        antworten = {"object": status, "lookup": status2}
        wie = "object"
        if status != 200 and status2 == 200:
            data, status, wie = data2, status2, "lookup"
        return oid, data, status, wie, antworten

    objects = {}
    ok = 0
    for oid, data, status, wie, antworten in probe.map(read, targets):
        objects[oid] = {"status": status, "endpunkt": wie, "antworten": antworten, "data": data}
        if status == 200 and isinstance(data, dict) and "value" in data:
            ok += 1
    print(f"    {ok} von {len(targets)} Objekten lesbar")
    return objects


# ----------------------------------------------------------------- Auswertung
def gnmn_of(prefix: str, oid: str) -> str:
    """'gn/mn' eines Datenpunkts relativ zum Funktionspräfix."""
    rest = oid[len(prefix) :].strip("/").split("/")
    return f"{rest[0]}/{rest[1]}" if len(rest) >= 2 else oid


def _bekannt(fct_type) -> set[str]:
    """Adressen, die die Herstellerdaten für einen Funktionstyp führen."""
    if DEVICE_DB is None:
        return set()
    try:
        layers = DEVICE_DB.get_layers(fct_type) or {}
    except Exception:
        return set()
    return {g for lvl in ("info", "operate", "service") for g in layers.get(lvl, [])}


def _zusatz(fct_type) -> set[str]:
    """Adressen, die die Integration außerhalb der Menüs einzeln liest."""
    if GERAETE is None:
        return set()
    try:
        return set(GERAETE.EXTRA_OIDS.get(int(fct_type), ()))
    except (TypeError, ValueError):
        return set()


def einzelziele(menus: dict) -> list[dict]:
    """Je Funktion die Adressen, die kein Menü der Anlage geliefert hat."""
    ziele = []
    for fct in menus["functions"]:
        fct_type = fct.get("fct_type")
        if not isinstance(fct_type, int) or fct_type < 0:
            continue
        found = {gnmn_of(fct["prefix"], oid) for oid in fct["datapoints"]}
        zusatz = _zusatz(fct_type)
        for gnmn in sorted((_bekannt(fct_type) | zusatz) - found, key=_sort_gnmn):
            ziele.append(
                {
                    "oid": f"{fct['prefix']}/{gnmn}/0",
                    "quelle": "zusatz" if gnmn in zusatz else "hersteller",
                }
            )
    return ziele


def hole_einzelwerte(probe: Probe, ziele: list[dict]) -> dict:
    """Jede Adresse einzeln über `lookup` lesen und Antwort samt Status festhalten."""

    def read(ziel):
        data, status = probe.lookup(ziel["oid"])
        return ziel, data, status

    werte = {}
    lesbar = 0
    for ziel, data, status in probe.map(read, ziele):
        gnmn = "/".join(ziel["oid"].split("/")[-3:-1])
        werte[ziel["oid"]] = {
            "quelle": ziel["quelle"],
            "name": db_name(gnmn),
            "status": status,
            "data": _gekuerzt(data),
        }
        if status == 200 and isinstance(data, dict) and "value" in data:
            lesbar += 1
    print(f"    {lesbar} von {len(ziele)} Adressen lesbar")
    return {"angefragt": len(ziele), "lesbar": lesbar, "werte": werte}


def compare(menus: dict) -> list[dict]:
    """Gefundene Datenpunkte gegen die Geräte-Datenbank stellen."""
    rows = []
    for fct in menus["functions"]:
        found = {gnmn_of(fct["prefix"], oid) for oid in fct["datapoints"]}
        known = _bekannt(fct["fct_type"])
        rows.append(
            {
                "prefix": fct["prefix"],
                "fct_type": fct["fct_type"],
                "name": fct["name"],
                "found": sorted(found, key=_sort_gnmn),
                "known": sorted(known, key=_sort_gnmn),
                "only_device": sorted(found - known, key=_sort_gnmn),
                "only_db": sorted(known - found, key=_sort_gnmn),
            }
        )
    return rows


def vergleichszeile(row: dict) -> str:
    """Eine Zeile der Gegenprobe; `fct_type` fehlt bei manchen Funktionen."""
    return (
        f"    {row['prefix']:<12} fctType {row['fct_type']!s:>3}: "
        f"Anlage {len(row['found']):>3} | DB {len(row['known']):>3} | "
        f"nur Anlage {len(row['only_device']):>3} | nur DB {len(row['only_db']):>3}"
    )


def _sort_gnmn(gnmn: str):
    gn, _, mn = gnmn.partition("/")
    return (int(gn) if gn.isdigit() else 0, int(mn) if mn.isdigit() else 0)


def write_csv(path: Path, menus: dict) -> None:
    """Alle Datenpunkte als CSV (Semikolon, Excel-tauglich)."""
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(
            [
                "host",
                "prefix",
                "fctType",
                "funktion",
                "menue",
                "oid",
                "gn/mn",
                "name_db",
                "wert",
                "einheit",
                "min",
                "max",
                "step",
                "schreibbar",
                "enum",
                "typeId",
                # Nur bei LON-Netzwerkvariablen belegt: Index, Kurzname und
                # der standardisierte LON-Datentyp. Aus `snvtName` lässt sich
                # eine Gruppe ableiten (Temperatur, Leistung, Zähler …), aus
                # `nvName` ein sprechender Name.
                "nvIndex",
                "nvName",
                "snvtName",
            ]
        )
        for fct in menus["functions"]:
            # An einer NV-Funktion ist `gn/mn` der nvIndex, kein Datenpunkt.
            # Die Namenstabelle darf hier nicht greifen: `0/0` hieße sonst
            # „Aussentemperatur", obwohl der Eintrag `nviRequest` ist. Aus
            # demselben Grund bleibt die Schreibbarkeit leer – `writeProt`
            # kommt am Katalog nicht vor, „ja" wäre geraten.
            ist_nv = fct["fct_type"] == FCT_TYPE_NV
            for oid, item in sorted(fct["datapoints"].items()):
                gnmn = gnmn_of(fct["prefix"], oid)
                writer.writerow(
                    [
                        menus["host"],
                        fct["prefix"],
                        fct["fct_type"],
                        fct["name"],
                        item.get("_menu", ""),
                        oid,
                        gnmn,
                        item.get("nvName", "") if ist_nv else db_name(gnmn),
                        item.get("value", ""),
                        item.get("unit", ""),
                        item.get("minValue", ""),
                        item.get("maxValue", ""),
                        item.get("step", ""),
                        "" if ist_nv else ("nein" if item.get("writeProt") else "ja"),
                        item.get("enum", ""),
                        item.get("typeId", ""),
                        item.get("nvIndex", ""),
                        item.get("nvName", ""),
                        item.get("snvtName", ""),
                    ]
                )


def write_report(path: Path, menus: dict, objects: dict, stats: dict) -> None:
    """Markdown-Bericht je Anlage."""
    lines = [
        f"# Anlagenbericht {menus['host']}",
        "",
        f"Erhoben: {menus['probed']}",
        "",
        "## Kennzahlen",
        "",
        f"- Funktionen: {len(menus['functions'])}",
        f"- Datenpunkte: {sum(len(f['datapoints']) for f in menus['functions'])}",
        f"- davon schreibbar: {sum(1 for f in menus['functions'] for i in f['datapoints'].values() if not i.get('writeProt'))}",
        f"- strukturierte Objekte (Zeitprogramme): {len(objects)}",
        f"- HTTP-Requests: {stats['requests']}",
        f"- Dauer: {stats['seconds']:.1f} s",
    ]
    abbrueche = stats.get("abbrueche") or {}
    lines += [
        f"  - {name}: {s:.0f} s"
        + (f", abgebrochen: {abbrueche[name]}" if name in abbrueche else "")
        for name, s in (stats.get("etappen") or {}).items()
    ]
    erwartet = sum(sum(v or 0 for v in f["menus"].values()) for f in menus["functions"])
    gelesen = sum(len(f["datapoints"]) for f in menus["functions"])
    if erwartet and gelesen < erwartet:
        lines += [
            f"- **Unvollständig:** Das Gerät meldet {erwartet} Datenpunkte in den "
            f"Menü-Ebenen, gelesen wurden {gelesen}. Ein Menü-Abruf liefert höchstens "
            f"{PAGE_SIZE} Einträge; Nachladen: {menus.get('seitenmodus', 'nicht getestet')}.",
        ]
    lines += [
        "",
        "## Funktionen",
        "",
        "| Präfix | fctType | Name | Menüs | erwartet | gelesen | schreibbar | ohne Antwort |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for fct in menus["functions"]:
        writable = sum(1 for i in fct["datapoints"].values() if not i.get("writeProt"))
        soll = sum(v or 0 for v in fct["menus"].values())
        lines.append(
            f"| `{fct['prefix']}` | {fct['fct_type']} | {fct['name']} | "
            f"{len(fct['menus'])} | {soll} | {len(fct['datapoints'])} | {writable} | "
            f"{len(fct.get('menu_errors') or {})} |"
        )

    lines += ["", "## Abgleich mit der Geräte-Datenbank", ""]
    for row in compare(menus):
        lines += [
            f"### `{row['prefix']}` – fctType {row['fct_type']} – {row['name']}",
            "",
            f"- Anlage liefert: {len(row['found'])}",
            f"- Datenbank kennt: {len(row['known'])}",
            f"- nur an der Anlage ({len(row['only_device'])}): "
            + (", ".join(row["only_device"]) if row["only_device"] else "–"),
            f"- nur in der Datenbank ({len(row['only_db'])}): "
            + (", ".join(row["only_db"]) if row["only_db"] else "–"),
            "",
        ]
        if row["only_device"]:
            lines += ["| gn/mn | Name laut Datenbank |", "|---|---|"]
            lines += [f"| {g} | {db_name(g) or '–'} |" for g in row["only_device"]]
            lines.append("")

    if objects:
        lines += ["## Strukturierte Objekte", "", "| OID | Status | Blöcke |", "|---|---|---|"]
        for oid, entry in sorted(objects.items()):
            data = entry.get("data")
            blocks = (
                len(data["value"])
                if isinstance(data, dict) and isinstance(data.get("value"), list)
                else "–"
            )
            lines.append(f"| `{oid}` | {entry['status']} | {blocks} |")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- Schwärzen
# Datenpunkte, die die Anlage eindeutig kennzeichnen: MAC-Adresse und Seriennummer.
KENNUNGEN = {"39/112": "<mac>", "39/115": "<seriennummer>"}
# Kürzere Werte bleiben stehen, sonst ersetzte eine „0“ jede Ziffer im Abzug.
KENNUNG_MIN_LAENGE = 6


# Felder der Geräteauskunft (`info/deviceinfo`, `config/network`) mit denselben Kennungen.
AUSKUNFT = {"serialnumber": "<seriennummer>", "checknumber": "<pruefnummer>", "mac": "<mac>"}
_AUSKUNFT_FELD = re.compile(rb'"(serialnumber|checknumber|mac)"\s*:\s*"([^"<]+)"', re.IGNORECASE)


def auskunft_kennungen(dateien: list[Path]) -> dict[str, str]:
    """Kennungen aus den Antworten der Geräteauskunft, die im Abzug stehen."""
    ersatz: dict[str, str] = {}
    for datei in dateien:
        for feld, wert in _AUSKUNFT_FELD.findall(datei.read_bytes()):
            text = wert.decode("utf-8", "replace").strip()
            if len(text) >= KENNUNG_MIN_LAENGE:
                ersatz[text] = AUSKUNFT[feld.decode().lower()]
                ersatz[text.replace(":", "").replace("-", "")] = AUSKUNFT[feld.decode().lower()]
    return ersatz


def kennungen_ersatz(structure: list, menus: dict | None) -> dict[str, str]:
    """Kennung -> Platzhalter, in Groß- und Kleinschreibung, MAC auch ohne Trenner."""
    ersatz: dict[str, str] = {}
    neurons = sorted({str(n.get("neuronId")) for n in structure if n.get("neuronId")})
    for lfd, neuron in enumerate(neurons, start=1):
        ersatz[neuron] = f"SN1-{lfd}"
    for fct in (menus or {}).get("functions", []):
        for oid, dp in fct.get("datapoints", {}).items():
            platzhalter = KENNUNGEN.get("/".join(oid.strip("/").split("/")[3:5]))
            text = str((dp or {}).get("value") or "").strip()
            if platzhalter and len(text) >= KENNUNG_MIN_LAENGE:
                ersatz[text] = platzhalter
                ersatz[text.replace(":", "").replace("-", "")] = platzhalter
    return {form: p for k, p in ersatz.items() for form in (k, k.upper(), k.lower())}


def schwaerzen(dateien: list[Path], structure: list, menus: dict | None) -> list[Path]:
    """Seriennummer, MAC-Adresse und Knotenkennungen ersetzen; liefert die geänderten Dateien."""
    ersatz = kennungen_ersatz(structure, menus)
    auskunft = auskunft_kennungen(dateien)
    ersatz.update({form: p for k, p in auskunft.items() for form in (k, k.upper(), k.lower())})
    if not ersatz:
        return []
    # Auf Bytes, weil Namensdateien der Steuerung nicht in UTF-8 vorliegen müssen.
    paare = [(k.encode(), ersatz[k].encode()) for k in sorted(ersatz, key=len, reverse=True)]
    geaendert = []
    for datei in dateien:
        vorher = inhalt = datei.read_bytes()
        for bekannt, platzhalter in paare:
            inhalt = inhalt.replace(bekannt, platzhalter)
        if inhalt != vorher:
            datei.write_bytes(inhalt)
            geaendert.append(datei)
    return geaendert


def schwaerzen_befehl(ordner: Path) -> int:
    """Befehl `schwaerzen`: einen vorhandenen Abzug schwärzen und das Ergebnis nennen."""
    if not ordner.is_dir():
        sage(f"  ✗ {_t('Den Ordner gibt es nicht: {}', ordner)}")
        return 1
    if not any(ordner.glob("*_menus.json")):
        sage(f"  ✗ {_t('In {} liegt kein Abzug der Sonde.', ordner)}")
        return 1
    geaendert = schwaerzen_ordner(ordner)
    if geaendert:
        sage(f"  ✓ {_t('{} Dateien geschwärzt.', len(geaendert))}")
        sage(f"    {_t('Seriennummer, MAC-Adresse und Knotenkennungen sind ersetzt.')}")
    else:
        sage(f"  ✓ {_t('Der Abzug ist bereits geschwärzt.')}")
    return 0


def _json_oder_none(pfad: Path):
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def schwaerzen_ordner(ordner: Path) -> list[Path]:
    """Einen fertigen Abzug nachträglich schwärzen, je Anlage anhand ihrer Menü-Datei."""
    geaendert = []
    for menus_datei in sorted(ordner.glob("*_menus.json")):
        stamm = menus_datei.name[: -len("_menus.json")]
        menus = _json_oder_none(menus_datei) or {}
        structure = _json_oder_none(ordner / f"{stamm}_structure.json")
        if not isinstance(structure, list):
            structure = menus.get("structure") or []
        dateien = [d for d in ordner.glob(f"{stamm}_*") if d.is_file()]
        geaendert += schwaerzen(dateien, structure, menus)
    return geaendert


# ----------------------------------------------------------------- Sprache
# Was ein Nutzer im geführten Modus sieht, gibt es auf Deutsch und Englisch.
# Technische Zeilen bleiben deutsch; sie stehen im Protokoll und im Expertenmodus.
EN = {
    "Anlagen-Sonde": "controller probe",
    "Zuletzt verwendet: {}": "Last used: {}",
    "Diese Anlagen verwenden? [J/n] oder neue IP-Adressen eingeben: ": (
        "Use these controllers? [Y/n] or enter new IP addresses: "
    ),
    "IP-Adressen der Anlagen (mehrere durch Komma oder Leerzeichen trennen)": (
        "IP addresses of the controllers (separate several with commas or spaces)"
    ),
    "IP-Adresse(n): ": "IP address(es): ",
    "Erreichbarkeit": "Reachability",
    "erreichbar": "reachable",
    "keine Antwort": "no response",
    "Gleiches Passwort für alle Anlagen? [J/n] ": "Same password for all controllers? [Y/n] ",
    "Passwort der Anlage (Eingabe bleibt verdeckt): ": (
        "Controller password (input stays hidden): "
    ),
    "Passwort für {}: ": "Password for {}: ",
    "Empfehlung: HeatNexus in Home Assistant für die Dauer des Laufs deaktivieren.": (
        "Recommended: disable HeatNexus in Home Assistant while the probe runs."
    ),
    "Die Steuerung beantwortet nur eine Anfrage nach der anderen. Mit beiden": (
        "The controller answers one request at a time. With both running,"
    ),
    "gleichzeitig dauert der Lauf länger, und einzelne Abfragen können ausfallen.": (
        "the run takes longer and single requests may fail."
    ),
    "Der Lauf dauert je nach Anlage 15 bis 40 Minuten, manchmal länger.": (
        "Depending on the system, the run takes 15 to 40 minutes, sometimes longer."
    ),
    "Anlage {}": "Controller {}",
    "Struktur lesen": "Reading structure",
    "{} Regler": "{} controllers",
    "Datenpunkte lesen": "Reading datapoints",
    "Funktion {} von {}": "function {} of {}",
    "{} Datenpunkte": "{} datapoints",
    "Zeitprogramme": "Time programs",
    "Einzelabruf": "Single reads",
    "LON-Netzwerkvariablen": "LON network variables",
    "LON gegen OID": "LON vs. OID",
    "Endpunktsuche": "Endpoint search",
    "Vollabzug": "Full dump",
    "Stapelabruf": "Batch read",
    "Störspeichersuche": "Fault memory search",
    "Statische Navigation": "Static navigation",
    "Namensdateien": "Name files",
    "Nachlade-Varianten": "Paging variants",
    "Gegenprobe": "Cross-check",
    "Bericht": "Report",
    "abgebrochen: {}": "aborted: {}",
    "Passwort prüfen – dasselbe wie in der Integration": (
        "Check the password – the same as in the integration"
    ),
    "keine Verbindung: {}": "no connection: {}",
    "Port 80 antwortet nicht": "port 80 does not respond",
    "Seriennummer, MAC-Adresse und Knotenkennungen sind geschwärzt.": (
        "Serial number, MAC address and node IDs are redacted."
    ),
    "Fertig.": "Done.",
    "Die Datei liegt bereit:": "The file is ready:",
    "Hänge sie an dein Issue auf GitHub an.": "Attach it to your issue on GitHub.",
    "Keine Anlage ließ sich auslesen.": "No controller could be read.",
    "Abgebrochen.": "Aborted.",
    "Unerwarteter Fehler: {}": "Unexpected error: {}",
    "Die Einzelheiten stehen in {}.": "Details are in {}.",
    "Keine gültige Auswahl.": "No valid choice.",
    "Den Ordner gibt es nicht: {}": "The folder does not exist: {}",
    "In {} liegt kein Abzug der Sonde.": "{} contains no probe dump.",
    "{} Dateien geschwärzt.": "{} files redacted.",
    "Seriennummer, MAC-Adresse und Knotenkennungen sind ersetzt.": (
        "Serial number, MAC address and node IDs are replaced."
    ),
    "Der Abzug ist bereits geschwärzt.": "The dump is already redacted.",
    "läuft noch, seit {} min": "still running, for {} min",
    "Fassung {}": "Version {}",
    "fehlgeschlagen": "failed",
}


def _sprache_erkennen() -> str:
    """Sprache aus `HEATNEXUS_SPRACHE`, sonst aus der Systemsprache; Deutsch nur bei Deutsch."""
    gesetzt = os.environ.get("HEATNEXUS_SPRACHE", "").lower()
    if gesetzt in ("de", "en"):
        return gesetzt
    name = (locale.getlocale()[0] or os.environ.get("LANG") or "").lower()
    return "de" if name.startswith(("de", "german")) else "en"


SPRACHE = _sprache_erkennen()


def _t(text: str, *werte) -> str:
    """Nutzertext in der gewählten Sprache, Platzhalter `{}` gefüllt."""
    vorlage = EN.get(text, text) if SPRACHE == "en" else text
    return vorlage.format(*werte) if werte else vorlage


# ------------------------------------------------------------------ Ausgabe
# Geführter Modus: Der Nutzer sieht Schritte mit laufender Zeit; jede technische
# Zeile geht nur ins Protokoll. Expertenmodus und Kommandozeile zeigen alles.
LEBENSZEICHEN_S = 60
LEBENSZEICHEN_TAKT_S = 5
STATUS_TAKT_S = 1


class _Ausgabe:
    """Leitet an die echte Ausgabe weiter, schreibt mit ins Protokoll, kann still sein."""

    def __init__(self, ziel, log=None, still: bool = False) -> None:
        self.ziel = ziel
        self.log = log
        self.still = still
        self.zuletzt = time.monotonic()
        self.sperre = threading.RLock()
        self.status: list | None = None  # [Name, Zusatz, Start] der laufenden Zeile

    def write(self, text: str) -> int:
        with self.sperre:
            if self.log:
                self.log.write(text)
            if self.still:
                return len(text)
            self.zuletzt = time.monotonic()
            return self.ziel.write(text)

    def sage(self, text: str) -> None:
        """Eine Zeile für den Nutzer, auch im stillen Modus."""
        with self.sperre:
            if self.log:
                self.log.write(text + "\n")
            if self.status:
                self.ziel.write("\r\x1b[K")
            self.ziel.write(text + "\n")
            self.ziel.flush()
            self.zuletzt = time.monotonic()
            self.zeichne()

    def zeichne(self, ende: str = "") -> None:
        """Die Statuszeile neu schreiben; `ende` schließt sie ab."""
        with self.sperre:
            if not self.status:
                return
            name, zusatz, start = self.status
            dauer = int(time.monotonic() - start)
            teile = [name, *([zusatz] if zusatz else []), f"{dauer // 60}:{dauer % 60:02d}"]
            zeichen = ende or "▸"
            self.ziel.write(f"\r    {zeichen} {' · '.join(teile)}\x1b[K" + ("\n" if ende else ""))
            self.ziel.flush()
            if ende and self.log:
                self.log.write(f"    {zeichen} {' · '.join(teile)}\n")
            self.zuletzt = time.monotonic()

    def __getattr__(self, name: str):
        return getattr(self.ziel, name)


def _aktuelle_ausgabe() -> _Ausgabe | None:
    return sys.stdout if isinstance(sys.stdout, _Ausgabe) else None


def sage(text: str = "") -> None:
    """Nutzerzeile: im geführten Modus sichtbar, sonst ein gewöhnliches print."""
    ausgabe = _aktuelle_ausgabe()
    if ausgabe:
        ausgabe.sage(text)
    else:
        print(text)


def fortschritt(zusatz: str) -> None:
    """Zusatz der laufenden Statuszeile setzen, etwa „Funktion 7 von 23“."""
    ausgabe = _aktuelle_ausgabe()
    if ausgabe and ausgabe.still and ausgabe.status:
        ausgabe.status[1] = zusatz
        ausgabe.zeichne()


@contextlib.contextmanager
def ausgabe(log_pfad: Path | None = None, still: bool = False):
    """Ausgabe für einen Lauf einrichten: Protokolldatei, still oder ausführlich, Wächter."""
    if _aktuelle_ausgabe():
        yield
        return
    log = log_pfad.open("a", encoding="utf-8") if log_pfad else None
    neue = _Ausgabe(sys.stdout, log, still)
    ende = threading.Event()
    start = time.monotonic()

    def wachen() -> None:
        takt = STATUS_TAKT_S if still else LEBENSZEICHEN_TAKT_S
        while not ende.wait(takt):
            if neue.still:
                neue.zeichne()
            elif time.monotonic() - neue.zuletzt >= LEBENSZEICHEN_S:
                minuten = int((time.monotonic() - start) // 60)
                print(f"      … {_t('läuft noch, seit {} min', minuten)}", flush=True)

    sys.stdout = neue
    waechter = threading.Thread(target=wachen, daemon=True)
    waechter.start()
    try:
        yield
    finally:
        ende.set()
        waechter.join()
        sys.stdout = neue.ziel
        if log:
            log.close()


def lebenszeichen():
    """Ohne Protokoll und ausführlich: nur das Lebenszeichen nach langer Stille."""
    return ausgabe()


# Je Anlage gesetzt von `run_host`; sammelt die Dauer jedes Schritts für den Bericht.
ETAPPEN: contextvars.ContextVar[dict[str, float] | None] = contextvars.ContextVar(
    "etappen", default=None
)
# Ebenso gesetzt: der Grund je abgebrochenem Schritt, damit er im Bericht steht.
ABBRUECHE: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    "abbrueche", default=None
)


@contextlib.contextmanager
def etappe(name: str, schuetzen: bool = True):
    """Ein sichtbarer Schritt mit laufender Zeit; geschützt, damit der Lauf weitergeht."""
    dauern = ETAPPEN.get()
    begonnen = time.monotonic() if dauern is not None else 0.0
    titel = _t(name)
    ausgabe_jetzt = _aktuelle_ausgabe()
    zeigen = bool(ausgabe_jetzt and ausgabe_jetzt.still)
    if zeigen:
        ausgabe_jetzt.status = [titel, "", time.monotonic()]
        ausgabe_jetzt.zeichne()
    try:
        yield
    except Exception as fehler:  # der Lauf wiegt mehr als der einzelne Schritt
        if not schuetzen:
            if zeigen:
                ausgabe_jetzt.zeichne("✗")
                ausgabe_jetzt.status = None
            raise
        print(f"    {name} abgebrochen: {type(fehler).__name__}: {fehler}")
        if (abbrueche := ABBRUECHE.get()) is not None:
            abbrueche[name] = f"{type(fehler).__name__}: {fehler}"[:200]
        if zeigen:
            ausgabe_jetzt.status[1] = _t("abgebrochen: {}", type(fehler).__name__)
            ausgabe_jetzt.zeichne("✗")
    else:
        if zeigen:
            ausgabe_jetzt.zeichne("✓")
    finally:
        if zeigen:
            ausgabe_jetzt.status = None
        if dauern is not None:
            dauern[name] = time.monotonic() - begonnen


# -------------------------------------------------------------------- Ablauf
def run_host(*args, **kwargs) -> dict:
    """Alle gewählten Aktionen für eine Anlage ausführen, mit Lebenszeichen."""
    token = ETAPPEN.set({})
    token_abbruch = ABBRUECHE.set({})
    try:
        with lebenszeichen():
            return _host_lauf(*args, **kwargs)
    finally:
        ETAPPEN.reset(token)
        ABBRUECHE.reset(token_abbruch)


def _host_lauf(
    host: str,
    password: str,
    actions: set[str],
    out_dir: Path,
    workers: int,
    username: str = USERNAME,
) -> dict:
    """Alle gewählten Aktionen für eine Anlage ausführen."""
    sage(f"\n  {_t('Anlage {}', host)}")
    if not reachable(host):
        sage(f"    ✗ {_t('Port 80 antwortet nicht')}")
        return {"host": host, "ok": False}

    if not _ensure_dir(out_dir):
        return {"host": host, "ok": False}

    stem = safe_name(host)
    probe = Probe(host, password, workers, username)
    started = time.monotonic()

    structure, status = probe.lookup("/1")
    if status != 200 or not isinstance(structure, list):
        sage(f"    ✗ {_t('Struktur lesen')} · {struktur_hinweis(status, structure)}")
        return {"host": host, "ok": False}

    nodes = len(structure)
    offen = [f for n in structure for f in n.get("functions", []) if not f.get("lock")]
    fcts = sum(1 for f in offen if f.get("fctType", -1) >= 0)
    nvs = sum(1 for f in offen if f.get("fctType", -1) < 0)
    print(f"    {nodes} Knoten, {fcts} nutzbare Funktionen, {nvs} LON-Adressräume")
    if _aktuelle_ausgabe() and _aktuelle_ausgabe().still:
        sage(f"    ✓ {_t('Struktur lesen')} · {_t('{} Regler', nodes)}")
    for node in structure:
        msg = node.get("FE01msg")
        print(f"      Knoten {node.get('nodeId'):>3}  {str(node.get('name'))[:18]:<18} {msg or ''}")

    written = []

    if "structure" in actions:
        path = out_dir / f"{stem}_structure.json"
        path.write_text(json.dumps(structure, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(path)

    menus = objects = None
    if actions & {"menus", "objects", "compare", "report", "diag", "nv", "vergleich", "einzeln"}:
        print("    Menü-Ebenen werden gelesen …")
        with etappe("Datenpunkte lesen", schuetzen=False):
            menus = fetch_menus(probe, structure)
            gelesen = sum(len(f["datapoints"]) for f in menus["functions"])
            fortschritt(_t("{} Datenpunkte", gelesen))
        for fct in menus["functions"]:
            if not fct.get("ungemeldet"):
                continue
            anzahl = len(fct["datapoints"])
            befund = f"{anzahl} Datenpunkte" if anzahl else f"HTTP {fct['root_status']}"
            print(f"      {fct['prefix']} nicht in der Struktur gemeldet: {befund}")
        path = out_dir / f"{stem}_menus.json"
        path.write_text(json.dumps(menus, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(path)
        path = out_dir / f"{stem}_datenpunkte.csv"
        write_csv(path, menus)
        written.append(path)

    if menus and actions & {"objects", "report"}:
        with etappe("Zeitprogramme"):
            print("    Zeitprogramme werden gelesen …")
            objects = fetch_objects(probe, menus)
            if objects:
                path = out_dir / f"{stem}_objekte.json"
                path.write_text(json.dumps(objects, indent=2, ensure_ascii=False), encoding="utf-8")
                written.append(path)

    nv = None
    if menus and "einzeln" in actions:
        with etappe("Einzelabruf"):
            ziele = einzelziele(menus)
            print(f"    {len(ziele)} Adressen außerhalb der Menüs werden einzeln gelesen …")
            einzeln = hole_einzelwerte(probe, ziele)
            path = out_dir / f"{stem}_einzeln.json"
            path.write_text(json.dumps(einzeln, indent=2, ensure_ascii=False), encoding="utf-8")
            written.append(path)

    if menus and actions & {"nv", "vergleich"}:
        with etappe("LON-Netzwerkvariablen"):
            print("    LON-Netzwerkvariablen: Adressform wird gesucht …")
            nv = suche_nv_werte(probe, menus)
            path = out_dir / f"{stem}_nv.json"
            path.write_text(json.dumps(nv, indent=2, ensure_ascii=False), encoding="utf-8")
            written.append(path)

    if menus and nv and "vergleich" in actions:
        with etappe("LON gegen OID"):
            print("    LON gegen OID …")
            ergebnis = vergleich_lon_oid(menus, nv)
            print(
                f"    {len(ergebnis['ohne_oid'])} LON-Werte ohne OID-Entsprechung, "
                f"{len(ergebnis['mit_oid'])} mit"
            )
            for eintrag in ergebnis["ohne_oid"][:15]:
                print(
                    f"      {str(eintrag['nvName'])[:30]:32} {eintrag['unit']:6} {eintrag['value']}"
                )
            path = out_dir / f"{stem}_vergleich.json"
            path.write_text(json.dumps(ergebnis, indent=2, ensure_ascii=False), encoding="utf-8")
            written.append(path)

    if "endpunkte" in actions:
        with etappe("Endpunktsuche"):
            print("    Endpunkte der Steuerung werden aufgezählt …")
            punkte = suche_endpunkte(probe)
            path = out_dir / f"{stem}_endpunkte.json"
            path.write_text(json.dumps(punkte, indent=2, ensure_ascii=False), encoding="utf-8")
            written.append(path)

    if "vollabzug" in actions:
        with etappe("Vollabzug"):
            print("    Vollabzug /api/1.0/datapoints wird gelesen …")
            abzug = hole_vollabzug(probe)
            path = abzugsname(out_dir, stem, abzug)
            path.write_text(json.dumps(abzug, indent=2, ensure_ascii=False), encoding="utf-8")
            written.append(path)

    if "stapel" in actions:
        with etappe("Stapelabruf"):
            print("    Stapelabruf gegen Einzelabrufe …")
            # Adressen dieser Anlage statt einer gepflegten Liste: Der
            # Zwischenspeicher nennt nur, was es hier wirklich gibt.
            vorrat, _status = probe.get(f"{probe.base}/api/1.0/datapoints")
            kandidaten = [
                str(e["OID"])
                for e in (vorrat if isinstance(vorrat, list) else [])
                if isinstance(e, dict) and e.get("OID")
            ][:STAPEL_PROBE]
            if not kandidaten:
                print("    keine Adressen für die Messung gefunden")
            else:
                messung = miss_stapelabruf(probe, kandidaten)
                path = out_dir / f"{stem}_stapel.json"
                path.write_text(json.dumps(messung, indent=2, ensure_ascii=False), encoding="utf-8")
                written.append(path)

    if "stoerspeicher" in actions:
        with etappe("Störspeichersuche"):
            print("    Störspeicher wird über den SOAP-Dienst gesucht …")
            speicher = suche_stoerspeicher(probe, structure)
            path = out_dir / f"{stem}_stoerspeicher.json"
            path.write_text(json.dumps(speicher, indent=2, ensure_ascii=False), encoding="utf-8")
            written.append(path)

    if "statisch" in actions:
        with etappe("Statische Navigation"):
            print("    Statische Navigationseinträge werden gesucht …")
            statisch = suche_statisch(probe, structure)
            path = out_dir / f"{stem}_statisch.json"
            path.write_text(json.dumps(statisch, indent=2, ensure_ascii=False), encoding="utf-8")
            written.append(path)

    if "texte" in actions:
        with etappe("Namensdateien"):
            print("    Namensdateien werden gesucht …")
            written.extend(run_texte(probe, out_dir, stem))

    if menus and "diag" in actions:
        with etappe("Nachlade-Varianten"):
            print("    Nachlade-Varianten werden getestet …")
            findings = run_diagnose(probe, menus)
            if findings:
                path = out_dir / f"{stem}_seitenmodus.json"
                path.write_text(
                    json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                written.append(path)

    seconds = time.monotonic() - started

    if menus and "compare" in actions:
        with etappe("Gegenprobe"):
            for row in compare(menus):
                print(vergleichszeile(row))

    if menus and "report" in actions:
        with etappe("Bericht"):
            path = out_dir / f"{stem}_bericht.md"
            write_report(
                path,
                menus,
                objects or {},
                {
                    "requests": probe.requests,
                    "seconds": seconds,
                    "etappen": ETAPPEN.get() or {},
                    "abbrueche": ABBRUECHE.get() or {},
                },
            )
            written.append(path)

    schwaerzen(written, structure, menus)
    total = sum(len(f["datapoints"]) for f in menus["functions"]) if menus else 0
    print(f"    fertig: {total} Datenpunkte, {probe.requests} Requests, {seconds:.1f} s")
    sage(f"    {_t('Seriennummer, MAC-Adresse und Knotenkennungen sind geschwärzt.')}")
    for path in written:
        print(f"      -> {path}")

    return {
        "host": host,
        "ok": True,
        "datapoints": total,
        "requests": probe.requests,
        "seconds": seconds,
        "files": [str(p) for p in written],
    }


TEXTDATEIEN = (
    "/VarIdentTexte_de.xml",
    "/config/VarIdentTexte_de.xml",
    "/VarIdentTexte.xml",
    "/EbenenTexte_de.xml",
    "/config/EbenenTexte_de.xml",
    "/api/1.0/VarIdentTexte_de.xml",
)


def run_texte(probe: Probe, out_dir: Path, stem: str) -> list:
    """Suchen, ob die Anlage ihre Namensdateien selbst ausliefert.

    Die Steuerungen tragen die Klartextnamen aller Datenpunkte als XML mit
    sich. Findet sich die Datei, können Namen direkt vom Gerät kommen statt
    aus einer mitgelieferten Datenbank.
    """
    gefunden = []
    for pfad in TEXTDATEIEN:
        url = f"{probe.base}{pfad}"
        try:
            with probe.opener.open(url, timeout=TIMEOUT) as resp:
                inhalt = resp.read()
                status = resp.status
        except urllib.error.HTTPError as err:
            status, inhalt = err.code, b""
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            print(f"      {pfad:<32} Fehler: {err}")
            continue
        marker = " <== gefunden" if status == 200 and len(inhalt) > 200 else ""
        print(f"      {pfad:<32} HTTP {status}, {len(inhalt)} Bytes{marker}")
        if marker:
            ziel = out_dir / f"{stem}{pfad.replace('/', '_')}"
            ziel.write_bytes(inhalt)
            gefunden.append(ziel)
    if not gefunden:
        print("    Die Anlage liefert keine Namensdatei aus.")
    return gefunden


ACTIONS = {
    "1": ("structure", "Anlagenstruktur (Knoten, Funktionen, Meldungen)"),
    "2": ("menus", "Menü-Ebenen und alle Datenpunkte (JSON + CSV)"),
    "3": ("objects", "Zeitprogramme / strukturierte Objekte"),
    "4": ("compare", "Abgleich mit der Geräte-Datenbank"),
    "5": ("report", "Markdown-Bericht je Anlage"),
    "6": ("diag", "Test: wie lassen sich Menüs mit über 10 Datenpunkten nachladen"),
    "7": ("texte", "Test: liefert die Anlage ihre Datenpunktnamen als Datei"),
    "8": ("statisch", "Suche: statische Navigationseinträge (Störspeicher, Sonderzeitprogramm)"),
    "9": ("stoerspeicher", "Suche: Störspeicher über den SOAP-Dienst der Steuerung"),
    "10": ("endpunkte", "Aufzählen: welche Endpunkte die Steuerung überhaupt kennt"),
    "11": ("nv", "Test: wie sich der Wert einer LON-Netzwerkvariablen lesen lässt"),
    "12": ("vollabzug", "Vollabzug: alle Datenpunkte über /api/1.0/datapoints"),
    "13": ("vergleich", "Vergleich: liefern LON-Werte etwas, das es als OID nicht gibt"),
    "14": ("stapel", "Messung: liest /api/1.0/datapoints?OID= mehrere Adressen auf einmal"),
    "15": (
        "einzeln",
        "Einzelabruf: Adressen außerhalb der Menüs (Herstellerdaten, Zusatzadressen)",
    ),
}


def _fassung() -> str:
    """Fassung von HeatNexus, aus der die Sonde stammt."""
    manifest = Path(__file__).resolve().parent.parent / "custom_components/heatnexus/manifest.json"
    daten = _json_oder_none(manifest)
    return str(daten.get("version", "?")) if isinstance(daten, dict) else "?"


def _anlagen_erfragen(out_dir: Path) -> list[str]:
    """IP-Adressen abfragen; die zuletzt verwendeten werden angeboten."""
    hosts_file = out_dir / HOSTS_FILE
    stored = []
    if hosts_file.exists():
        stored = [h.strip() for h in hosts_file.read_text(encoding="utf-8").splitlines()]
        stored = [h for h in stored if h]
    hosts: list[str] = []
    if stored:
        sage(f"\n  {_t('Zuletzt verwendet: {}', ', '.join(stored))}")
        answer = input("  " + _t("Diese Anlagen verwenden? [J/n] oder neue IP-Adressen eingeben: "))
        answer = answer.strip()
        hosts = stored if answer.lower() in ("", "j", "ja", "y", "yes") else _split_hosts(answer)
    else:
        sage(f"\n  {_t('IP-Adressen der Anlagen (mehrere durch Komma oder Leerzeichen trennen)')}")
    while not hosts:
        hosts = _split_hosts(input("  " + _t("IP-Adresse(n): ")))
    sage(f"\n  {_t('Erreichbarkeit')}")
    for host in hosts:
        if reachable(host):
            sage(f"    ✓ {host:<16} {_t('erreichbar')}")
        else:
            sage(f"    ✗ {host:<16} {_t('keine Antwort')}")
    return hosts


def _passwoerter_erfragen(hosts: list[str]) -> dict[str, str]:
    """Ein Passwort für alle oder je Anlage, verdeckt eingegeben."""
    same = True
    if len(hosts) > 1:
        antwort = input("\n  " + _t("Gleiches Passwort für alle Anlagen? [J/n] ")).strip().lower()
        same = antwort not in ("n", "nein", "no")
    if same:
        pw = os.environ.get("HEATNEXUS_PW") or getpass.getpass(
            "\n  " + _t("Passwort der Anlage (Eingabe bleibt verdeckt): ")
        )
        return dict.fromkeys(hosts, pw)
    return {h: getpass.getpass("  " + _t("Passwort für {}: ", h)) for h in hosts}


def _aktionen_erfragen() -> set[str]:
    """Expertenmodus: einzelne Aktionen wählen."""
    print("\nWas soll gemacht werden?")
    for key, (_, label) in ACTIONS.items():
        print(f"  {key}) {label}")
    print("  a) alles")
    choice = input("Auswahl (z. B. 2,4,5 oder a) [a]: ").strip().lower() or "a"
    if choice == "a":
        return {name for name, _ in ACTIONS.values()}
    return {ACTIONS[c][0] for c in (x.strip() for x in choice.split(",")) if c in ACTIONS}


def _empfehlung_zeigen() -> None:
    sage()
    sage(f"  {_t('Empfehlung: HeatNexus in Home Assistant für die Dauer des Laufs deaktivieren.')}")
    sage(f"  {_t('Die Steuerung beantwortet nur eine Anfrage nach der anderen. Mit beiden')}")
    sage(f"  {_t('gleichzeitig dauert der Lauf länger, und einzelne Abfragen können ausfallen.')}")
    sage(f"  {_t('Der Lauf dauert je nach Anlage 15 bis 40 Minuten, manchmal länger.')}")


def _abzug_packen(out_dir: Path, dateien: list[Path]) -> Path:
    """Die Dateien dieses Laufs als ZIP neben den Zielordner legen."""
    ziel = out_dir.absolute().parent / f"heatnexus-abzug-{dt.datetime.now():%Y-%m-%d-%H%M}.zip"
    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as zip_datei:
        for datei in dateien:
            if datei.is_file():
                zip_datei.write(datei, f"{out_dir.name}/{datei.name}")
    return ziel


def _im_explorer_zeigen(datei: Path) -> None:
    """Unter Windows den Explorer mit markierter Datei öffnen; sonst nichts."""
    if os.name != "nt":
        return
    with contextlib.suppress(OSError):
        subprocess.Popen(["explorer", "/select,", str(datei)])


def _abschluss(results: list[dict], out_dir: Path, log: Path) -> int:
    """Geführter Modus: Ergebnis je Anlage, ZIP packen und zeigen."""
    sage()
    gut = [r for r in results if r.get("ok")]
    for res in results:
        if res.get("ok"):
            dauer = int(res["seconds"])
            sage(
                f"  ✓ {res['host']:<16} {_t('{} Datenpunkte', res['datapoints'])} · "
                f"{dauer // 60}:{dauer % 60:02d}"
            )
        else:
            sage(f"  ✗ {res['host']:<16} {_t('fehlgeschlagen')}")
    if not gut:
        sage(f"\n  {_t('Keine Anlage ließ sich auslesen.')}")
        return 1
    dateien = [Path(f) for r in gut for f in r.get("files", [])] + [log]
    zip_datei = _abzug_packen(out_dir, dateien)
    sage(f"\n  ✓ {_t('Fertig.')} {_t('Die Datei liegt bereit:')}")
    sage(f"    {zip_datei}")
    sage(f"  {_t('Hänge sie an dein Issue auf GitHub an.')}")
    _im_explorer_zeigen(zip_datei)
    return 0


def _zusammenfassung_ausfuehrlich(results: list[dict], out_dir: Path) -> None:
    print("\n" + "=" * 64)
    print(" Zusammenfassung")
    print("=" * 64)
    for res in results:
        if res.get("ok"):
            print(
                f"  {res['host']:<16} {res['datapoints']:>4} Datenpunkte  "
                f"{res['requests']:>4} Anfragen  {res['seconds']:.1f} s"
            )
        else:
            print(f"  {res['host']:<16} fehlgeschlagen")
    print(f"\nDateien liegen in: {out_dir.resolve()}")


def interactive(out_default: str = "probe", experte: bool = False) -> int:
    """Geführter Modus; im Expertenmodus mit Auswahl der Aktionen und des Zielordners."""
    # `probe.cmd` zeigt einen eigenen Kopf und setzt dafür diese Variable.
    if not os.environ.get("HEATNEXUS_KOPF_GEZEIGT"):
        print("=" * 64)
        print(" HeatNexus – Anlagen-Sonde")
        print("=" * 64)
    sage(f"  {_t('Fassung {}', _fassung())}")

    out_dir = zielordner(out_default)
    hosts = _anlagen_erfragen(out_dir)
    passwords = _passwoerter_erfragen(hosts)
    actions = {name for name, _ in ACTIONS.values()}
    if experte:
        actions = _aktionen_erfragen()
        if not actions:
            print(_t("Keine gültige Auswahl."))
            return 1
        while True:
            out_dir = Path(input(f"Zielordner [{out_default}]: ").strip() or out_default)
            if _ensure_dir(out_dir):
                break
    elif not _ensure_dir(out_dir):
        return 1
    _empfehlung_zeigen()

    (out_dir / HOSTS_FILE).write_text("\n".join(hosts) + "\n", encoding="utf-8")
    log = out_dir / "sonde.log"
    log.unlink(missing_ok=True)
    with ausgabe(log, still=not experte):
        results = [run_host(h, passwords[h], actions, out_dir, DEFAULT_WORKERS) for h in hosts]
    if experte:
        _zusammenfassung_ausfuehrlich(results, out_dir)
        return 0
    return _abschluss(results, out_dir, log)


def _split_hosts(text: str) -> list[str]:
    return [h.strip() for h in text.replace(",", " ").split() if h.strip()]


def _ensure_dir(path: Path) -> bool:
    """Zielordner anlegen; bei Problemen verständlich melden."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe_file = path / ".schreibtest"
        probe_file.write_text("", encoding="utf-8")
        probe_file.unlink()
        return True
    except OSError as err:
        print(f"    Zielordner nicht nutzbar ({err.strerror or err}). Bitte anderen Pfad angeben.")
        return False


def _password_for(args) -> str:
    return args.password or os.environ.get("HEATNEXUS_PW") or getpass.getpass("Service-Passwort: ")


def main() -> int:
    """Kommandozeile."""
    parser = argparse.ArgumentParser(
        description="HeatNexus – Anlagen-Probe für Windhager-Heizungen",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="interactive",
        choices=[
            "interactive",
            "structure",
            "menus",
            "objects",
            "compare",
            "report",
            "diag",
            "all",
            "oid",
            "objekt",
            "statisch",
            "stoerspeicher",
            "endpunkte",
            "nv",
            "vollabzug",
            "vergleich",
            "stapel",
            "einzeln",
            "schwaerzen",
        ],
        help="Aktion (Standard: geführter Modus)",
    )
    parser.add_argument("hosts", nargs="*", help="eine oder mehrere IP-Adressen")
    parser.add_argument("--oid", help="vollständige OID für die Aktionen 'oid' und 'objekt'")
    parser.add_argument(
        "--password",
        help="Service-Passwort; steht dann in Prozessliste und Shell-Verlauf. "
        "Besser weglassen: Abfrage oder HEATNEXUS_PW",
    )
    parser.add_argument(
        "--user",
        default=USERNAME,
        help=f"Zugang der Anlage: USER oder Service (Standard: {USERNAME})",
    )
    parser.add_argument(
        "-o",
        "--out",
        default="probe",
        help="Zielordner, relativ zum Repository (Standard: probe)",
    )
    parser.add_argument(
        "--experte",
        action="store_true",
        help="geführter Modus mit Auswahl der Aktionen und ausführlicher Ausgabe",
    )
    parser.add_argument("--sprache", choices=("de", "en"), help="Sprache der Ausgabe")
    parser.add_argument("--de", dest="sprache", action="store_const", const="de", help="Deutsch")
    parser.add_argument("--en", dest="sprache", action="store_const", const="en", help="English")
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"parallele Anfragen je Anlage (Standard: {DEFAULT_WORKERS})",
    )
    args = parser.parse_args()

    global SPRACHE
    SPRACHE = args.sprache or SPRACHE
    if args.command == "interactive":
        return interactive(args.out, args.experte)
    if args.command == "schwaerzen":
        return schwaerzen_befehl(Path(args.hosts[0]) if args.hosts else zielordner(args.out))

    hosts = args.hosts
    if args.command in ("oid", "objekt") and hosts and not args.oid:
        # Aufruf: oid <host> <OID>
        candidates = [h for h in hosts if h.startswith("/")]
        if candidates:
            args.oid = candidates[0]
            hosts = [h for h in hosts if not h.startswith("/")]
    if not hosts:
        parser.error("Bitte mindestens eine IP-Adresse angeben")

    password = _password_for(args)

    if args.command == "oid":
        if not args.oid:
            parser.error("Bitte die OID angeben, z. B. /1/15/0/3/50/0")
        for host in hosts:
            data, status = Probe(host, password, 1, args.user).lookup(args.oid)
            print(f"\n{host}  HTTP {status}")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    if args.command == "objekt":
        # Der object-Endpunkt statt lookup. Nötig für alles, was die Anlage
        # als Struktur führt statt als einzelnen Wert: Zeitprogramme – und der
        # Störspeicher (2/90), den `res/xml/StaticNavAssignment.xml` als
        # `errorlog` führt. Er steht in keiner Menü-Ebene und wird deshalb von
        # `menus` nie gefunden.
        if not args.oid:
            parser.error("Bitte die OID angeben, z. B. /1/60/0/2/90/0")
        ziel = zielordner(args.out)
        ziel.mkdir(parents=True, exist_ok=True)
        for host in hosts:
            data, status = Probe(host, password, 1, args.user).obj(args.oid)
            print(f"\n{host}  HTTP {status}")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            # Zusätzlich als Datei: Was man ansehen will, will man meist auch
            # weitergeben, und Abtippen aus der Konsole verliert Umlaute.
            name = args.oid.strip("/").replace("/", "-")
            pfad = ziel / f"{safe_name(host)}_objekt_{name}.json"
            pfad.write_text(
                json.dumps(
                    {"oid": args.oid, "status": status, "data": data}, indent=2, ensure_ascii=False
                ),
                encoding="utf-8",
            )
            print(f"  -> {pfad}")
        return 0

    if args.command == "all":
        actions = {name for name, _ in ACTIONS.values()}
    else:
        actions = {args.command}
        if args.command in ("compare", "report"):
            actions |= {"menus"}

    _empfehlung_zeigen()
    results = [
        run_host(h, password, actions, zielordner(args.out), args.workers, args.user) for h in hosts
    ]
    return 0 if all(r.get("ok") for r in results) else 1


def _start() -> int:
    """`main` mit verständlicher Meldung bei Strg+C und bei unerwarteten Fehlern."""
    try:
        return main()
    except (KeyboardInterrupt, EOFError):
        sage()
        sage(f"  {_t('Abgebrochen.')}")
        return 130
    except Exception as fehler:  # Nutzer sehen einen Satz, das Protokoll den Rest
        pfad = Path(__file__).resolve().parent.parent / "sonde-fehler.log"
        with contextlib.suppress(OSError):
            pfad.write_text(traceback.format_exc(), encoding="utf-8")
        sage(f"  ✗ {_t('Unerwarteter Fehler: {}', fehler)}")
        sage(f"  {_t('Die Einzelheiten stehen in {}.', pfad)}")
        return 1


if __name__ == "__main__":
    raise SystemExit(_start())
