"""Archiv des Befunds je Anlage: 5-Minuten-Werte zu Stunden, Stunden zu Tagen."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any

STUNDEN_TAGE = 60
TAGE_TAGE = 400
UNTER_K = 3.0
FASSUNG = 1
HEIZKREIS = "hk"
KESSEL = "k"
MESSWERTE = ("at", "vl", "vi", "soll")


def _schluessel(zeit: datetime) -> str:
    return zeit.strftime("%Y-%m-%d %H")


def _mittel(werte: Iterable[Any]) -> float | None:
    zahlen = [w for w in werte if isinstance(w, int | float) and not isinstance(w, bool)]
    return round(mean(zahlen), 2) if zahlen else None


def _letzter(eintraege: list[dict[str, Any]], feld: str) -> Any:
    return next((e[feld] for e in reversed(eintraege) if e.get(feld) is not None), None)


def _stunde_heizkreis(messungen: list[dict[str, Any]]) -> dict[str, Any]:
    """Messwerte gemittelt, Eingriff wenn einer, Räume je Eintrag gemittelt."""
    stunde: dict[str, Any] = {f: _mittel(m.get(f) for m in messungen) for f in MESSWERTE}
    stunde["eingriff"] = any(m.get("eingriff") for m in messungen)
    raeume: dict[str, list[list[Any]]] = {}
    for m in messungen:
        for raum, paar in (m.get("raeume") or {}).items():
            raeume.setdefault(raum, []).append(paar)
    stunde["raeume"] = {
        r: [_mittel(p[0] for p in ps), _mittel(p[1] for p in ps)] for r, ps in raeume.items()
    }
    return stunde


def _stunde_kessel(messungen: list[dict[str, Any]]) -> dict[str, Any]:
    """Zähler mit dem letzten Stand, Wärme als mittlere Leistung über eine Stunde."""
    return {
        "starts": _letzter(messungen, "starts"),
        "bh": _letzter(messungen, "bh"),
        "kwh": _mittel(m.get("kw") for m in messungen),
    }


def _unter(stunden: list[dict[str, Any]]) -> tuple[int, int]:
    """Zahl und längste Folge der Heizstunden mit Vorlauf mehr als 3 K unter Soll."""
    zahl = laenge = laengste = 0
    for s in stunden:
        vl, vi = s.get("vl") or 0, s.get("vi")
        unter = vl > 0 and vi is not None and vi < vl - UNTER_K
        zahl += unter
        laenge = laenge + 1 if unter else 0
        laengste = max(laengste, laenge)
    return zahl, laengste


def _tag_heizkreis(stunden: list[dict[str, Any]]) -> dict[str, Any]:
    unter, folge = _unter(stunden)
    return {
        "at": _mittel(s.get("at") for s in stunden),
        "heizh": sum((s.get("vl") or 0) > 0 for s in stunden),
        "unter": unter,
        "folge": folge,
    }


def _tag_kessel(stunden: list[dict[str, Any]]) -> dict[str, Any]:
    kwh = [s["kwh"] for s in stunden if s.get("kwh") is not None]
    return {
        "starts": _letzter(stunden, "starts"),
        "bh": _letzter(stunden, "bh"),
        "kwh": round(sum(kwh), 1) if kwh else None,
    }


def _verschachtelt(roh: Any) -> dict[str, dict[str, dict[str, Any]]]:
    """Nur `{kennung: {schlüssel: {…}}}` übernehmen; alles andere verwerfen."""
    if not isinstance(roh, dict):
        return {}
    return {
        str(k): {str(s): w for s, w in v.items() if isinstance(w, dict)}
        for k, v in roh.items()
        if isinstance(v, dict)
    }


class Archiv:
    """Stunden 60 Tage, Tage 400 Tage, getrennt nach Heizkreis und Kessel."""

    def __init__(self) -> None:
        self.stunden_hk: dict[str, dict[str, dict[str, Any]]] = {}
        self.stunden_k: dict[str, dict[str, dict[str, Any]]] = {}
        self.tage_hk: dict[str, dict[str, dict[str, Any]]] = {}
        self.tage_k: dict[str, dict[str, dict[str, Any]]] = {}
        self._offen: dict[tuple[str, str], tuple[str, list[dict[str, Any]]]] = {}
        self.nachgerechnet = 0

    @classmethod
    def aus_dict(cls, roh: Any) -> Archiv:
        """Ein gespeichertes Archiv; Unlesbares ergibt ein leeres."""
        archiv = cls()
        if not isinstance(roh, dict):
            return archiv
        for name in ("stunden_hk", "stunden_k", "tage_hk", "tage_k"):
            setattr(archiv, name, _verschachtelt(roh.get(name)))
        stand = roh.get("nachgerechnet")
        archiv.nachgerechnet = (
            stand if isinstance(stand, int) and not isinstance(stand, bool) else 0
        )
        return archiv

    def als_dict(self) -> dict[str, Any]:
        return {
            "fassung": FASSUNG,
            "nachgerechnet": self.nachgerechnet,
            "stunden_hk": self.stunden_hk,
            "stunden_k": self.stunden_k,
            "tage_hk": self.tage_hk,
            "tage_k": self.tage_k,
        }

    def _quellen(self, art: str) -> tuple[dict, dict]:
        if art == HEIZKREIS:
            return self.stunden_hk, self.tage_hk
        return self.stunden_k, self.tage_k

    # --- Sammeln ----------------------------------------------------------
    def messen(self, kreis: str, zeit: datetime, werte: dict[str, Any]) -> bool:
        """Ein Wert eines Heizkreises; die Stunde schließt mit dem ersten Wert der nächsten.

        Liefert, ob dabei eine Stunde abgeschlossen wurde.
        """
        return self._messen(HEIZKREIS, kreis, zeit, werte)

    def messen_kessel(self, kessel: str, zeit: datetime, werte: dict[str, Any]) -> bool:
        """Ein Wert eines Kessels: Zählerstände und Leistung in kW."""
        return self._messen(KESSEL, kessel, zeit, werte)

    def _messen(self, art: str, kennung: str, zeit: datetime, werte: dict[str, Any]) -> bool:
        schluessel = _schluessel(zeit)
        offen = self._offen.get((art, kennung))
        if offen and offen[0] == schluessel:
            offen[1].append(werte)
            return False
        if offen:
            self._abschliessen(art, kennung, offen[0], offen[1])
        self._offen[(art, kennung)] = (schluessel, [werte])
        self._tage_bilden(art, kennung, self._offene_tage(art, kennung, schluessel[:10]))
        return offen is not None

    def _offene_tage(self, art: str, kennung: str, heute: str) -> set[str]:
        """Vergangene Tage mit Stunden, aber ohne Tageswert – auch nach einem Neustart über Mitternacht."""
        stunden, tage = self._quellen(art)
        vorhanden = tage.get(kennung, {})
        return {
            k[:10] for k in stunden.get(kennung, {}) if k[:10] < heute and k[:10] not in vorhanden
        }

    def _abschliessen(
        self, art: str, kennung: str, schluessel: str, messungen: list[dict[str, Any]]
    ) -> None:
        stunden, _ = self._quellen(art)
        verdichten = _stunde_heizkreis if art == HEIZKREIS else _stunde_kessel
        stunden.setdefault(kennung, {})[schluessel] = verdichten(messungen)

    # --- Nachtragen -------------------------------------------------------
    def nachtragen(self, kreis: str, stunden: dict[str, dict[str, Any]]) -> int:
        """Vergangene Stunden eines Heizkreises; vorhandene bleiben. Liefert die Zahl neuer."""
        return self._nachtragen(HEIZKREIS, kreis, stunden)

    def nachtragen_kessel(self, kessel: str, stunden: dict[str, dict[str, Any]]) -> int:
        return self._nachtragen(KESSEL, kessel, stunden)

    def _nachtragen(self, art: str, kennung: str, stunden: dict[str, dict[str, Any]]) -> int:
        ziel, _ = self._quellen(art)
        vorhanden = ziel.setdefault(kennung, {})
        neu = {k: v for k, v in stunden.items() if k not in vorhanden}
        vorhanden.update(neu)
        offen = self._offen.get((art, kennung))
        tage = {k[:10] for k in neu} - ({offen[0][:10]} if offen else set())
        self._tage_bilden(art, kennung, tage)
        return len(neu)

    # --- Tage ---------------------------------------------------------------
    def _tage_bilden(self, art: str, kennung: str, tage: Iterable[str]) -> None:
        gesucht = set(tage)
        if not gesucht:
            return
        stunden, ziel = self._quellen(art)
        je_tag: dict[str, list[dict[str, Any]]] = {}
        for k, v in sorted(stunden.get(kennung, {}).items()):
            if k[:10] in gesucht:
                je_tag.setdefault(k[:10], []).append({"zeit": k, **v})
        bilden = _tag_heizkreis if art == HEIZKREIS else _tag_kessel
        for datum, liste in je_tag.items():
            ziel.setdefault(kennung, {})[datum] = bilden(liste)

    # --- Lesen --------------------------------------------------------------
    def stunden(self, kreis: str) -> list[dict[str, Any]]:
        """Abgeschlossene Stunden eines Heizkreises, aufsteigend."""
        return [{"zeit": k, **v} for k, v in sorted(self.stunden_hk.get(kreis, {}).items())]

    def tage_heizkreis(self, kreis: str) -> list[dict[str, Any]]:
        """Abgeschlossene Tage eines Heizkreises, aufsteigend."""
        return [{"datum": d, **v} for d, v in sorted(self.tage_hk.get(kreis, {}).items())]

    def tage_kessel(self, kessel: str, at_je_tag: dict[str, float]) -> list[dict[str, Any]]:
        """Kesseltage mit dem Tagesmittel der Anlage; ob geheizt wurde, setzt die Auswertung."""
        return [
            {"datum": d, **v, "at": at_je_tag.get(d), "heiztag": False}
            for d, v in sorted(self.tage_k.get(kessel, {}).items())
        ]

    def kuerzen(self, heute: date) -> None:
        """Stunden älter als 60 Tage und Tage älter als 400 Tage entfernen."""
        grenze_s = (heute - timedelta(days=STUNDEN_TAGE)).isoformat()
        grenze_t = (heute - timedelta(days=TAGE_TAGE)).isoformat()
        for quelle in (self.stunden_hk, self.stunden_k):
            for kennung, eintraege in quelle.items():
                quelle[kennung] = {k: v for k, v in eintraege.items() if k[:10] >= grenze_s}
        for quelle in (self.tage_hk, self.tage_k):
            for kennung, eintraege in quelle.items():
                quelle[kennung] = {d: v for d, v in eintraege.items() if d >= grenze_t}
