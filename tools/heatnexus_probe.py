#!/usr/bin/env python3
"""HeatNexus – Anlagen-Probe für Windhager-Heizungen.

Liest Struktur, Menü-Ebenen, Datenpunkte und Zeitprogramme einer oder mehrerer
Anlagen aus und schreibt JSON, CSV und einen Markdown-Bericht. Nutzt nur die
Python-Standardbibliothek.

Ohne Argumente startet der geführte Modus (Auswahlmenü). Alternativ direkt:

    python tools/heatnexus_probe.py menus 192.0.2.10 192.0.2.11
    python tools/heatnexus_probe.py oid 192.0.2.10 /1/15/0/3/50/0
    python tools/heatnexus_probe.py all 192.0.2.10 -o probe

Passwörter werden nie gespeichert. Sie kommen aus `--password`, aus der
Umgebungsvariablen HEATNEXUS_PW oder aus einer verdeckten Eingabe.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import datetime as dt
import getpass
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

# Zugang ab Werk. Die Steuerung kennt zwei: `USER` sieht Info- und
# Betreiberebene, `Service` zusätzlich die Fachparameter. Welcher gilt,
# entscheidet `--user`; fest eingebaut war er bis 1.4.2, und damit blieb
# alles unsichtbar, was Service verlangt.
USERNAME = "USER"
TIMEOUT = 30  # große Menü-Ebenen brauchen deutlich länger als eine Einzelabfrage
DEFAULT_WORKERS = 3  # mehr Parallelität quittieren die Geräte mit Abbrüchen
RETRIES = 2  # Wiederholungen bei Zeitüberschreitung/Verbindungsabbruch
RETRY_PAUSE = 1.5
PAGE_SIZE = 10  # das Gerät liefert je Menü-Abruf höchstens 10 Datenpunkte
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


def db_name(gnmn: str) -> str:
    """Datenpunktname aus der Geräte-Datenbank."""
    if DEVICE_DB is None:
        return ""
    try:
        return DEVICE_DB.get_name(gnmn) or ""
    except Exception:
        return ""


# ------------------------------------------------------------------- Client
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
            opener = urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(mgr))
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
        for attempt in range(RETRIES + 1):
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
                if err.code >= 500 and attempt < RETRIES:
                    time.sleep(RETRY_PAUSE)
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
        return last

    def lookup(self, path: str):
        """GET /api/1.0/lookup<path>."""
        return self.get(f"{self.base}/api/1.0/lookup{path}")

    def obj(self, full_oid: str):
        """GET /api/1.0/object?OID=<vollständige OID>."""
        return self.get(f"{self.base}/api/1.0/object?OID={full_oid}")

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
]


def _oids_of(items) -> list[str]:
    return [i.get("OID") for i in items if isinstance(i, dict) and i.get("OID")]


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
        fresh = [i for i in page if i.get("OID") not in seen]
        if not fresh:
            break
        items.extend(fresh)
        seen.update(_oids_of(fresh))
        offset += PAGE_SIZE
    return items, strategy, status


# ---------------------------------------------------------------- Abfragen
def fetch_structure(probe: Probe):
    """Anlagenstruktur (/1)."""
    data, status = probe.lookup("/1")
    if status != 200 or not isinstance(data, list):
        return None, status
    return data, status


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
STATISCHE_NAV = {
    "2/90/0": "Störspeicher (errorlog)",
    "4/80/0": "Sonderzeitprogramm",
    "4/42/0": "Passwort",
}


# ------------------------------------------------------------- Störspeicher
# Der Störspeicher steht in keinem Menü und ist über `lookup`/`object` nicht
# lesbar – beide antworten mit `409 – invalid Identifier`. Die Weboberfläche der
# Anlage zeigt ihn trotzdem. Wie, verrät ihr eigener Quelltext:
#
#     function zq(a,b){ … this.f = '/'+c[1]+'/'+c[2]+'/'+c[3]+'/2/96/0'; … }
#     BU(196,1,{},zq)          und in der Typtabelle:
#     uM = V6(snb,'StaticNavActionErrorLog',196)
#
# `zq` ist also der Störspeicher, und seine Adresse ist `2/96` – nicht `2/90`,
# das ist nur der Schlüssel des Navigationseintrags in `StaticNav.xml`.
#
# Gelesen wird sie über einen zweiten Kanal: einen SOAP-Dienst, dessen Vorlagen
# unter `res/xml/ws.*.req.xml` liegen. `getDpRequest` und `listDpRequest`
# kennen `startIndex` und `count` – genau das, was eine Liste braucht und was
# der REST-Schnittstelle fehlt.
SOAP_HUELLE = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope
 xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:ns="http://ws01.lom.ch/soap/">
 <SOAP-ENV:Body>
   <ns:{ruf}Request>
    <ref>
     <oid>{oid}</oid>
     <prop></prop>
    </ref>
    <startIndex>0</startIndex>
    <count>{anzahl}</count>
   </ns:{ruf}Request>
 </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
"""

# Wohin der Dienst hört, sagt der Quelltext nicht eindeutig; diese Adressen
# stehen dort als Zeichenketten. Die erste, die antwortet, gewinnt.
SOAP_ADRESSEN = ("/WsAdmin/api/1.0/", "/WsAdmin", "/api/1.0/", "/soap", "/ws")


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
    "recorder/oids",
    "recorder/settings",
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
)

# Basispfade, unter denen die Kandidaten gesucht werden.
ENDPUNKT_BASEN = ("/api/1.0/", "/dprecorder/api/1.0/", "/WsAdmin/api/1.0/")


def suche_endpunkte(probe: Probe) -> dict:
    """Aufzählen, welche Endpunkte die Steuerung kennt.

    Rein lesend: Jeder Kandidat wird einmal mit GET angefragt. Die Antwort
    ``503 endpoint <name> does not exist`` heißt „kennt sie nicht"; alles
    andere – auch ein 400 oder 409 wegen fehlender Parameter – heißt „gibt es".
    """
    ergebnisse = []
    for basis in ENDPUNKT_BASEN:
        for name in ENDPUNKT_KANDIDATEN:
            data, status = probe.get(f"{probe.base}{basis}{name}")
            # `get` liefert, was die Anlage schickt – und das ist nicht immer
            # ein Objekt: `lookup` etwa antwortet mit einer **Liste**. Ein
            # blindes `.get("reason")` darauf beendet den ganzen Lauf mit
            # einem AttributeError, noch bevor eine Datei geschrieben ist.
            grund = str(data.get("reason") or "") if isinstance(data, dict) else ""
            unbekannt = status == 503 and "does not exist" in grund
            ergebnisse.append(
                {
                    "pfad": f"{basis}{name}",
                    "status": status,
                    "reason": grund[:200],
                    "vorhanden": not unbekannt and status != 404,
                }
            )
            if ergebnisse[-1]["vorhanden"]:
                print(f"    GIBT ES  {basis}{name:30} HTTP {status:>3}  {grund[:80]}", flush=True)
    gefunden = [e for e in ergebnisse if e["vorhanden"]]
    print(f"    {len(gefunden)} von {len(ergebnisse)} Kandidaten vorhanden")
    return {"vorhanden": gefunden, "alle": ergebnisse}


def suche_stoerspeicher(probe: Probe, structure: list, anzahl: int = 20) -> dict:
    """Den Störspeicher über den SOAP-Dienst der Steuerung suchen."""
    versuche = []
    for node in structure:
        node_id = node.get("nodeId")
        for fct in node.get("functions", []):
            if fct.get("fctType", -1) < 0:
                continue
            oid = f"/1/{node_id}/{fct.get('fctId')}/2/96/0"
            for adresse in SOAP_ADRESSEN:
                for ruf in ("listDp", "getDp"):
                    rumpf = SOAP_HUELLE.format(ruf=ruf, oid=oid, anzahl=anzahl)
                    antwort, status = probe.post(probe.base + adresse, rumpf.encode("utf-8"))
                    treffer = status == 200 and "Fault" not in antwort[:400]
                    print(
                        f"    {adresse:20} {ruf:7} {oid:20} HTTP {status:>3}"
                        f"{'  TREFFER' if treffer else ''}",
                        flush=True,
                    )
                    versuche.append(
                        {
                            "adresse": adresse,
                            "ruf": ruf,
                            "oid": oid,
                            "status": status,
                            "antwort": antwort[:4000],
                        }
                    )
                    if treffer:
                        return {"treffer": versuche[-1], "versuche": versuche}
    print("    kein SOAP-Dienst hat geantwortet")
    return {"treffer": None, "versuche": versuche}


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

    ziele = [(f"{p}/{gnmn}", p, gnmn) for p in praefixe for gnmn in STATISCHE_NAV]
    print(f"    {len(ziele)} Kombinationen aus {len(praefixe)} Präfixen werden geprüft")

    def read(ziel):
        oid, praefix, gnmn = ziel
        # Erst der object-Endpunkt: Ein Störspeicher ist eine Liste, kein
        # Einzelwert.
        data, status = probe.obj(oid)
        wie = "object"
        # `409 – invalid Identifier` ist die endgültige Antwort der Anlage:
        # Diese Adresse führt sie nicht. Ein zweiter Versuch über `lookup`
        # brächte dieselbe Auskunft und kostet nur Zeit. Nachgefasst wird
        # deshalb nur, wenn die erste Antwort *keine* Auskunft war.
        endgueltig = (
            status == 409 and "invalid identifier" in str((data or {}).get("reason", "")).lower()
        )
        if status != 200 and not endgueltig:
            data2, status2 = probe.lookup(f"/{oid.lstrip('/')}")
            if status2 == 200:
                data, status, wie = data2, status2, "lookup"
        return {
            "oid": oid,
            "prefix": praefix,
            "gnmn": gnmn,
            "status": status,
            "endpunkt": wie,
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
    ergebnisse = []
    for nummer, ziel in enumerate(ziele, start=1):
        eintrag = read(ziel)
        ergebnisse.append(eintrag)
        beschreibung = STATISCHE_NAV[eintrag["gnmn"]]
        print(
            f"    [{nummer:2}/{len(ziele)}] {eintrag['oid']:22} "
            f"HTTP {eintrag['status']:>3}  {beschreibung}",
            flush=True,
        )
        if eintrag["status"] == 200:
            treffer.append(eintrag)
            print(f"    TREFFER  {eintrag['oid']:22} {beschreibung} (ueber {eintrag['endpunkt']})")
    if not treffer:
        print("    kein statischer Eintrag lesbar – die Anlage führt sie woanders")
    return {"treffer": treffer, "alle": ergebnisse}


def fetch_menus(probe: Probe, structure: list) -> dict:
    """Alle Menü-Ebenen je Funktion einlesen (Sammelabruf)."""
    result = {
        "host": probe.host,
        "probed": dt.datetime.now().isoformat(timespec="seconds"),
        "structure": structure,
        "functions": [],
    }

    for node in structure:
        node_id = node.get("nodeId")
        for fct in node.get("functions", []):
            if fct.get("lock") or fct.get("fctType", -1) < 0:
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
                    items, strategy, mstatus = fetch_menu_all(
                        probe, url, expected, probe.page_strategy
                    )
                    if strategy is not None and probe.page_strategy is None:
                        probe.page_strategy = strategy
                    return menu_id, items, mstatus

                for menu_id, items, mstatus in probe.map(read_menu, list(entry["menus"])):
                    if mstatus == 200 and isinstance(items, list):
                        for item in items:
                            oid = item.get("OID")
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
    print(f"    Grundabruf liefert {len(first)} Einträge, erster: {sorted(known)[0]}")

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
# sie in keinem Menü steht, hat der Menü-Abzug sie nie gefunden.
STATISCHE_OBJEKTE = ("2/90/0", "4/80/0")


def fetch_objects(probe: Probe, menus: dict) -> dict:
    """Strukturierte Objekte (Zeitprogramme, Störspeicher) lesen."""
    targets = [
        oid
        for fct in menus["functions"]
        for oid, item in fct["datapoints"].items()
        if item.get("typeId") == 30
    ]
    targets += [
        f"{fct['prefix']}/{gnmn}"
        for fct in menus["functions"]
        for gnmn in STATISCHE_OBJEKTE
        if f"{fct['prefix']}/{gnmn}" not in targets
    ]
    if not targets:
        print("    keine strukturierten Objekte gefunden")
        return {}

    def read(oid):
        data, status = probe.obj(oid)
        return oid, data, status

    objects = {}
    ok = 0
    for oid, data, status in probe.map(read, targets):
        objects[oid] = {"status": status, "data": data}
        if status == 200 and isinstance(data, dict) and "value" in data:
            ok += 1
    print(f"    {ok} von {len(targets)} Objekten lesbar")
    return objects


# ----------------------------------------------------------------- Auswertung
def gnmn_of(prefix: str, oid: str) -> str:
    """'gn/mn' eines Datenpunkts relativ zum Funktionspräfix."""
    rest = oid[len(prefix) :].strip("/").split("/")
    return f"{rest[0]}/{rest[1]}" if len(rest) >= 2 else oid


def compare(menus: dict) -> list[dict]:
    """Gefundene Datenpunkte gegen die Geräte-Datenbank stellen."""
    rows = []
    for fct in menus["functions"]:
        found = {gnmn_of(fct["prefix"], oid) for oid in fct["datapoints"]}
        layers = {}
        if DEVICE_DB is not None:
            try:
                layers = DEVICE_DB.get_layers(fct["fct_type"]) or {}
            except Exception:
                layers = {}
        known = {g for lvl in ("info", "operate", "service") for g in layers.get(lvl, [])}
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
            ]
        )
        for fct in menus["functions"]:
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
                        db_name(gnmn),
                        item.get("value", ""),
                        item.get("unit", ""),
                        item.get("minValue", ""),
                        item.get("maxValue", ""),
                        item.get("step", ""),
                        "nein" if item.get("writeProt") else "ja",
                        item.get("enum", ""),
                        item.get("typeId", ""),
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


# -------------------------------------------------------------------- Ablauf
def run_host(
    host: str,
    password: str,
    actions: set[str],
    out_dir: Path,
    workers: int,
    username: str = USERNAME,
) -> dict:
    """Alle gewählten Aktionen für eine Anlage ausführen."""
    print(f"\n=== {host}")
    if not reachable(host):
        print("    nicht erreichbar (Port 80 antwortet nicht)")
        return {"host": host, "ok": False}

    if not _ensure_dir(out_dir):
        return {"host": host, "ok": False}

    stem = safe_name(host)
    probe = Probe(host, password, workers, username)
    started = time.monotonic()

    structure, status = fetch_structure(probe)
    if structure is None:
        hint = "Passwort prüfen" if status in (401, 403) else f"HTTP {status}"
        print(f"    Struktur nicht lesbar ({hint})")
        return {"host": host, "ok": False}

    nodes = len(structure)
    fcts = sum(
        1
        for n in structure
        for f in n.get("functions", [])
        if not f.get("lock") and f.get("fctType", -1) >= 0
    )
    print(f"    {nodes} Knoten, {fcts} nutzbare Funktionen")
    for node in structure:
        msg = node.get("FE01msg")
        print(f"      Knoten {node.get('nodeId'):>3}  {str(node.get('name'))[:18]:<18} {msg or ''}")

    written = []

    if "structure" in actions:
        path = out_dir / f"{stem}_structure.json"
        path.write_text(json.dumps(structure, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(path)

    menus = objects = None
    if actions & {"menus", "objects", "compare", "report", "diag"}:
        print("    Menü-Ebenen werden gelesen …")
        menus = fetch_menus(probe, structure)
        path = out_dir / f"{stem}_menus.json"
        path.write_text(json.dumps(menus, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(path)
        path = out_dir / f"{stem}_datenpunkte.csv"
        write_csv(path, menus)
        written.append(path)

    if menus and actions & {"objects", "report"}:
        print("    Zeitprogramme werden gelesen …")
        objects = fetch_objects(probe, menus)
        if objects:
            path = out_dir / f"{stem}_objekte.json"
            path.write_text(json.dumps(objects, indent=2, ensure_ascii=False), encoding="utf-8")
            written.append(path)

    if "endpunkte" in actions:
        print("    Endpunkte der Steuerung werden aufgezählt …")
        punkte = suche_endpunkte(probe)
        path = out_dir / f"{stem}_endpunkte.json"
        path.write_text(json.dumps(punkte, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(path)

    if "stoerspeicher" in actions:
        print("    Störspeicher wird über den SOAP-Dienst gesucht …")
        speicher = suche_stoerspeicher(probe, structure)
        path = out_dir / f"{stem}_stoerspeicher.json"
        path.write_text(json.dumps(speicher, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(path)

    if "statisch" in actions:
        print("    Statische Navigationseinträge werden gesucht …")
        statisch = suche_statisch(probe, structure)
        path = out_dir / f"{stem}_statisch.json"
        path.write_text(json.dumps(statisch, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(path)

    if "texte" in actions:
        print("    Namensdateien werden gesucht …")
        written.extend(run_texte(probe, out_dir, stem))

    if menus and "diag" in actions:
        print("    Nachlade-Varianten werden getestet …")
        findings = run_diagnose(probe, menus)
        if findings:
            path = out_dir / f"{stem}_seitenmodus.json"
            path.write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")
            written.append(path)

    seconds = time.monotonic() - started

    if menus and "compare" in actions:
        for row in compare(menus):
            print(
                f"    {row['prefix']:<12} fctType {row['fct_type']:>3}: "
                f"Anlage {len(row['found']):>3} | DB {len(row['known']):>3} | "
                f"nur Anlage {len(row['only_device']):>3} | nur DB {len(row['only_db']):>3}"
            )

    if menus and "report" in actions:
        path = out_dir / f"{stem}_bericht.md"
        write_report(path, menus, objects or {}, {"requests": probe.requests, "seconds": seconds})
        written.append(path)

    total = sum(len(f["datapoints"]) for f in menus["functions"]) if menus else 0
    print(f"    fertig: {total} Datenpunkte, {probe.requests} Requests, {seconds:.1f} s")
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
}


def interactive(out_default: str = "probe") -> int:
    """Geführter Modus mit Auswahlmenü."""
    print("=" * 64)
    print(" HeatNexus – Anlagen-Probe")
    print("=" * 64)

    out_dir = zielordner(out_default)
    hosts_file = out_dir / HOSTS_FILE
    stored = []
    if hosts_file.exists():
        stored = [
            h.strip() for h in hosts_file.read_text(encoding="utf-8").splitlines() if h.strip()
        ]

    if stored:
        print(f"\nZuletzt verwendet: {', '.join(stored)}")
        answer = input("Diese Anlagen verwenden? [J/n] oder neue IPs eingeben: ").strip()
        if answer.lower() in ("", "j", "ja", "y"):
            hosts = stored
        else:
            hosts = _split_hosts(answer)
    else:
        print("\nIP-Adressen der Anlagen (mehrere durch Komma oder Leerzeichen trennen)")
        hosts = _split_hosts(input("IP(s): "))

    while not hosts:
        hosts = _split_hosts(input("IP(s): "))

    print("\nErreichbarkeit:")
    for host in hosts:
        print(f"  {host:<16} {'erreichbar' if reachable(host) else 'KEINE ANTWORT'}")

    same = True
    if len(hosts) > 1:
        same = input("\nGleiches Passwort für alle Anlagen? [J/n] ").strip().lower() not in (
            "n",
            "nein",
        )

    passwords: dict[str, str] = {}
    env_pw = os.environ.get("HEATNEXUS_PW")
    if same:
        pw = env_pw or getpass.getpass("Service-Passwort (Eingabe bleibt verdeckt): ")
        passwords = dict.fromkeys(hosts, pw)
    else:
        for host in hosts:
            passwords[host] = getpass.getpass(f"Passwort für {host}: ")

    print("\nWas soll gemacht werden?")
    for key, (_, label) in ACTIONS.items():
        print(f"  {key}) {label}")
    print("  a) alles")
    choice = input("Auswahl (z. B. 2,4,5 oder a) [a]: ").strip().lower() or "a"
    if choice == "a":
        actions = {name for name, _ in ACTIONS.values()}
    else:
        actions = {ACTIONS[c][0] for c in (x.strip() for x in choice.split(",")) if c in ACTIONS}
    if not actions:
        print("Keine gültige Auswahl.")
        return 1

    while True:
        target = input(f"Zielordner [{out_default}]: ").strip() or out_default
        out_dir = Path(target)
        if _ensure_dir(out_dir):
            break

    hosts_file = out_dir / HOSTS_FILE
    hosts_file.write_text("\n".join(hosts) + "\n", encoding="utf-8")

    results = [run_host(h, passwords[h], actions, out_dir, DEFAULT_WORKERS) for h in hosts]

    print("\n" + "=" * 64)
    print(" Zusammenfassung")
    print("=" * 64)
    for res in results:
        if res.get("ok"):
            print(
                f"  {res['host']:<16} {res['datapoints']:>4} Datenpunkte  "
                f"{res['requests']:>4} Requests  {res['seconds']:.1f} s"
            )
        else:
            print(f"  {res['host']:<16} fehlgeschlagen")
    print(f"\nDateien liegen in: {out_dir.resolve()}")
    return 0


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
        ],
        help="Aktion (Standard: geführter Modus)",
    )
    parser.add_argument("hosts", nargs="*", help="eine oder mehrere IP-Adressen")
    parser.add_argument("--oid", help="vollständige OID für die Aktionen 'oid' und 'objekt'")
    parser.add_argument("--password", help="Service-Passwort (sonst Abfrage oder HEATNEXUS_PW)")
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
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"parallele Anfragen je Anlage (Standard: {DEFAULT_WORKERS})",
    )
    args = parser.parse_args()

    if args.command == "interactive":
        return interactive(args.out)

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

    results = [
        run_host(h, password, actions, zielordner(args.out), args.workers, args.user) for h in hosts
    ]
    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
