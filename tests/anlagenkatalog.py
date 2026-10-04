"""Testanlagen aus `daten/anlagen/` als Steuerung nachspielen, ohne Netz.

Jede Datei beschreibt eine Anlage einer Baureihe: Struktur, Menüs mit den
Metadaten jedes Datenpunkts, Einzelantworten, Objekte. Werte und Namen sind
ersetzt; Enum-Grenzen, Einheiten und Schreibschutz sind die des Geräts.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qsl

KATALOG = Path(__file__).parent / "daten" / "anlagen"
HOST = "192.0.2.10"
FEHLT = ({"code": 409, "message": "Conflict", "reason": "Target returns invalid Identifier"}, 409)


def anlagen() -> list[str]:
    return sorted(p.stem for p in KATALOG.glob("*.json"))


class Nachspiel:
    """Beantwortet die Anfragen des Clients aus einer Testanlage."""

    def __init__(self, name: str) -> None:
        """Die Testanlage laden und ihre Einzelantworten bereitlegen."""
        self.name = name
        self.daten = json.loads((KATALOG / f"{name}.json").read_text(encoding="utf-8"))
        self.funktionen = self.daten["funktionen"]
        self.einzel: dict[str, tuple] = {}
        for f in self.funktionen.values():
            for oid, dp in f["datapoints"].items():
                self.einzel[oid] = ({k: v for k, v in dp.items() if k != "_menu"}, 200)
        for oid, (dp, status) in self.daten["einzel"].items():
            self.einzel.setdefault(oid, (dp, status))
        self.anfragen: list[tuple[str, int]] = []

    def metadaten(self, oid: str) -> dict | None:
        daten, status = self.einzel.get(oid, (None, 404))
        return daten if status == 200 and isinstance(daten, dict) else None

    def _seite(self, praefix: str, menue: str, query: dict):
        f = self.funktionen.get(praefix)
        if not f:
            return None, 404
        eintraege = [
            {k: v for k, v in dp.items() if k != "_menu"}
            for dp in f["datapoints"].values()
            if str(dp.get("_menu")) == str(menue)
        ]
        if query.get("count") == "-1":
            return eintraege, 200
        offset = int(query.get("offset", 0))
        return eintraege[offset : offset + 10], 200

    def antwort(self, url: str):
        pfad = url.split(HOST, 1)[1]
        pfad, _, roh = pfad.partition("?")
        query = dict(parse_qsl(roh))
        if pfad.startswith("/api/1.0/lookup"):
            rest = pfad[len("/api/1.0/lookup") :]
            teile = rest.strip("/").split("/")
            if rest == "/1":
                return self.daten["struktur"], 200
            if len(teile) == 3:
                f = self.funktionen.get(rest)
                if not f or not f.get("menus"):
                    return None, 404
                return [{"id": int(m), "count": n} for m, n in f["menus"].items()], 200
            if len(teile) == 4:
                return self._seite("/" + "/".join(teile[:3]), teile[3], query)
            return self.einzel.get(rest, FEHLT)
        if pfad.startswith("/api/1.0/datapoint"):
            oid = pfad[len("/api/1.0/datapoint") :]
            daten, status = self.einzel.get(oid, FEHLT)
            if status == 200 and isinstance(daten, dict):
                return {"OID": oid, "value": daten.get("value")}, 200
            return daten, status
        if pfad.startswith("/api/1.0/object"):
            e = self.daten["objekte"].get(query.get("OID", ""))
            return (e.get("data"), e["status"]) if e else (None, 404)
        treffer = self.daten["endpunkte"].get(pfad)
        return tuple(treffer) if treffer else (None, 404)

    def einsetzen(self, client) -> None:
        """Den Transport des Clients durch dieses Nachspiel ersetzen."""

        async def _ensure_session():
            return None

        async def _get(url, semaphore=None):
            client.request_count += 1
            daten, status = self.antwort(url)
            self.anfragen.append((url.split(HOST, 1)[1], status))
            return (json.loads(json.dumps(daten)) if daten is not None else None), status

        async def _ressource(pfad):
            return None

        async def fetch_object(full_oid):
            client.request_count += 1
            e = self.daten["objekte"].get(full_oid)
            if not e:
                return None, 404
            return json.loads(json.dumps(e.get("data"))), e["status"]

        client._ensure_session = _ensure_session
        client._get = _get
        client._ressource = _ressource
        client.fetch_object = fetch_object
