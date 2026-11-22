"""Gerätewissen je Funktionstyp, ein Modul je Baureihe.

Hier werden die Einzelmodule zu den Tabellen zusammengesetzt, die der Rest der
Integration liest. Eine weitere Baureihe ist eine Datei und ein Eintrag in
`MODULE`.
"""

from __future__ import annotations

from collections.abc import Callable
import json
import re
from types import ModuleType

from . import (
    automatikkessel,
    biowin,
    erzeugerpumpe,
    gas_oel_kessel,
    heizkreis,
    heizkreis_infinity,
    io5500,
    kaskade,
    puffer,
    pufferspeicher,
    purowin,
    solar,
    solar_es,
    statuszeilen,
    umschaltung,
    waermepumpe,
    waermepumpe_direkt,
    waermepumpe_energie,
    warmwasser,
    zsp,
    zusatzheizung,
)

# Felder, die jedes Modul führt, und die, die nur einige brauchen.
PFLICHTFELDER = (
    "FCT_TYPE",
    "MODELL",
    "RANG",
    "SYMBOL",
    "SCHAUBILD",
    "KESSELART",
    "NAMEN",
    "EXTRA_OIDS",
    "NUR_BUS",
    "ENTITAETEN",
)
KANNFELDER = (
    "SCHALTPUNKTE",
    "VERBRAUCHER_ABSTAND",
    "ROLLEN",
    "MODELLE_JE_KLASSE",
    "RUNDINSTRUMENTE",
    "NUR_ANZEIGE",
    "STATUSZEILEN",
    "BEHAELTER",
    "FUELLGRAD",
    "BEDINGUNGEN",
    "TABELLEN",
    "SPIEGEL",
    "BEFUND",
)

MODULE: tuple[ModuleType, ...] = (
    purowin,
    biowin,
    waermepumpe,
    waermepumpe_energie,
    waermepumpe_direkt,
    gas_oel_kessel,
    zusatzheizung,
    automatikkessel,
    kaskade,
    umschaltung,
    puffer,
    pufferspeicher,
    erzeugerpumpe,
    heizkreis_infinity,
    heizkreis,
    warmwasser,
    solar,
    solar_es,
    io5500,
    zsp,
)

# Dateien, die mehrere Baureihen teilen; selbst keine Baureihe.
HILFSMODULE: tuple[str, ...] = ("quittung", "statuszeilen")

# Was für ein Anlagenteil das ist – für die Geräteseite in Home Assistant. Der
# Name der Anlage taugt dafür nicht: Er ist oft von Hand vergeben und
# beschreibt den Raum, nicht das Gerät.
MODELLE: dict[int, str] = {m.FCT_TYPE: m.MODELL for m in MODULE if m.MODELL}

# Genauere Bezeichnung, wo ein Funktionstyp mehrere Geräte umfasst.
MODELLE_JE_KLASSE: dict[tuple[int, str], str] = {
    (m.FCT_TYPE, klasse): modell
    for m in MODULE
    for klasse, modell in getattr(m, "MODELLE_JE_KLASSE", {}).items()
}

_KLASSE = re.compile(r"[0-9a-f]{4}")


def geraeteklasse(program_id: object) -> str | None:
    """Geräteklasse aus der `programId` eines Knotens, klein geschrieben wie beim Hersteller."""
    klasse = str(program_id or "")[6:10].lower()
    return klasse if _KLASSE.fullmatch(klasse) else None


def modell(fct_type: object, klasse: str | None = None) -> str | None:
    """Modellbezeichnung einer Funktion, die Geräteklasse vor dem Funktionstyp."""
    return MODELLE_JE_KLASSE.get((fct_type, klasse or "")) or MODELLE.get(fct_type)


# Reihenfolge der Abschnitte in Dashboard und Oberfläche, dem Weg der Wärme
# nach. Typen ohne Beleg stehen nicht in der Liste und landen hinten.
RANG: dict[int, int] = {m.FCT_TYPE: m.RANG for m in MODULE if m.RANG is not None}

SYMBOLE: dict[int, str] = {m.FCT_TYPE: m.SYMBOL for m in MODULE if m.SYMBOL}

# Welches Bauteil das Schaubild zeichnet.
SCHAUBILD_ARTEN: dict[int, str] = {m.FCT_TYPE: m.SCHAUBILD for m in MODULE if m.SCHAUBILD}

# Die kuratierten Datenpunkttabellen. Sie haben Vorrang vor dem, was die
# Menü-Ebenen der Anlage melden.
ENTITAETEN: dict[int, list[dict]] = {m.FCT_TYPE: m.ENTITAETEN for m in MODULE if m.ENTITAETEN}

# Adressen, die in keiner Menü-Ebene stehen und einzeln gelesen werden.
EXTRA_OIDS: dict[int, tuple[str, ...]] = {m.FCT_TYPE: m.EXTRA_OIDS for m in MODULE if m.EXTRA_OIDS}

# Sichtbarkeit nach Einstellung, wo die Herstellerdatei sie nicht führt: Adresse -> Bedingungssätze.
BEDINGUNGEN: dict[int, dict[str, list[dict]]] = {
    m.FCT_TYPE: m.BEDINGUNGEN for m in MODULE if getattr(m, "BEDINGUNGEN", None)
}


def satz_trifft(wert: str, satz: dict) -> bool:
    """Gilt der Satz beim Wert? `values` nennt die Werte der Adresse, `ausser` ihre Gegenwerte."""
    if "ausser" in satz:
        return wert not in satz["ausser"]
    return wert in satz["values"]


def _gemeldet(meta: dict, wert: int) -> bool:
    """Ob die Steuerung den Wert für die Einstellung nennt; ohne Aufzählung und Bereich gilt jeder."""
    try:
        if (roh := meta.get("enum")) not in (None, ""):
            return wert in {int(w) for w in (json.loads(roh) if isinstance(roh, str) else roh)}
        if meta.get("minValue") is not None and meta.get("maxValue") is not None:
            return float(meta["minValue"]) <= wert <= float(meta["maxValue"])
    except (TypeError, ValueError):
        return False
    return True


def schaltwert(meta: dict | None) -> int | None:
    """Der Wert einer Einstellung als Zahl; None, wenn er unlesbar oder nicht gemeldet ist."""
    try:
        wert = float((meta or {}).get("value"))
    except (TypeError, ValueError):
        return None
    if not wert.is_integer():
        return None
    return int(wert) if _gemeldet(meta or {}, int(wert)) else None


def satz_widerspricht(meta: dict | None, satz: dict) -> bool:
    """Ob der Wert den Satz belegt verneint. Unlesbar oder unbelegt verneint nie."""
    wert = schaltwert(meta)
    if wert is None:
        return False
    if "ausser" in satz:
        return str(wert) in satz["ausser"]
    return str(wert) not in satz["values"]


def wegnahme(
    bedingungen: dict[str, list[dict]], rolle: dict | None, quelle: Callable[[str], dict | None]
) -> set[str]:
    """Adressen eines Geräts, die belegt ohne Aufgabe sind; `quelle` liefert Metadaten je Adresse.

    Eine Adresse entfällt nur, wenn jeder ihrer Sätze widerspricht, und eine Rolle
    zählt nur, wenn die Rollentabelle sie nennt.
    """
    weg = {
        adresse
        for adresse, saetze in bedingungen.items()
        if saetze and all(satz_widerspricht(quelle(s["oid"]), s) for s in saetze)
    }
    if rolle:
        wert = schaltwert(quelle(rolle["quelle"]))
        if wert in set().union(*rolle["nur_bei"].values()):
            weg |= {a for a, erlaubt in rolle["nur_bei"].items() if wert not in erlaubt}
    return weg


# Zustandstexte für Adressen ohne Tabelle in der Herstellerdatei, deutsch.
TABELLEN: dict[str, dict[int, str]] = {
    adresse: tabelle
    for m in MODULE
    for adresse, tabelle in (getattr(m, "TABELLEN", None) or {}).items()
}

# Adressen, die ein anderer Funktionstyp nur spiegelt: Modul -> {gespiegelt an: Adressen}.
SPIEGEL: dict[int, dict[int, tuple[str, ...]]] = {
    m.FCT_TYPE: m.SPIEGEL for m in MODULE if getattr(m, "SPIEGEL", None)
}

# Begriffe, die eine Baureihe nur über den LON-Bus hergibt.
NUR_BUS: dict[int, tuple[str, ...]] = {m.FCT_TYPE: m.NUR_BUS for m in MODULE if m.NUR_BUS}

# Adressen, die eine Anzeige bleiben, auch wenn die Steuerung sie schreiben lässt.
NUR_ANZEIGE: dict[int, frozenset[str]] = {
    m.FCT_TYPE: frozenset(m.NUR_ANZEIGE) for m in MODULE if getattr(m, "NUR_ANZEIGE", None)
}

# Zeilen des Systemstatus je Erzeuger, ab zwei Erzeugern in dessen Block.
STATUSZEILEN: dict[int, tuple[statuszeilen.Statuszeile, ...]] = {
    m.FCT_TYPE: m.STATUSZEILEN for m in MODULE if getattr(m, "STATUSZEILEN", None)
}


# Namen, die erst im Zusammenhang einer Baureihe eindeutig sind.
NAMEN: dict[int, dict[str, str]] = {m.FCT_TYPE: m.NAMEN for m in MODULE if m.NAMEN}

# Füllstand im Schaubild: Vorratsbehälter in Stufen oder in Prozent.
BEHAELTER: dict[int, str] = {
    m.FCT_TYPE: m.BEHAELTER for m in MODULE if getattr(m, "BEHAELTER", None)
}
FUELLGRAD: dict[int, str] = {
    m.FCT_TYPE: m.FUELLGRAD for m in MODULE if getattr(m, "FUELLGRAD", None)
}

# Was der Befund je Baureihe auswertet: Pflege, Abgaswächter, Brennstoff, Wärmepumpe.
BEFUND: dict[int, dict] = {m.FCT_TYPE: m.BEFUND for m in MODULE if getattr(m, "BEFUND", None)}

# Wo der Funktionstyp die Bauart des Wärmeerzeugers schon festlegt.
KESSELARTEN: dict[int, str] = {m.FCT_TYPE: m.KESSELART for m in MODULE if m.KESSELART}

# Bauart je Geräteklasse, wie die Kesselwahl der Steuerung sie zuordnet. Sie
# gilt für den Kessel selbst; ein PuroWIN verbrennt Hackgut oder Pellets.
KESSELART_JE_KLASSE: dict[str, str] = {
    **dict.fromkeys(("1403", "1407", "140a", "140b", "140c", "1415", "2015"), "pellets"),
    **dict.fromkeys(("1414", "2014"), "hackgut"),
    **dict.fromkeys(("1404", "1409", "2009"), "scheitholz"),
    "1203": "gas_oel",
    **dict.fromkeys(("1416", "1417", "2016"), "waermepumpe"),
}

SCHALTPUNKTE: tuple[dict[str, object], ...] = tuple(
    eintrag for m in MODULE for eintrag in getattr(m, "SCHALTPUNKTE", ())
)

VERBRAUCHER_ABSTAND: tuple[dict[str, object], ...] = tuple(
    eintrag for m in MODULE for eintrag in getattr(m, "VERBRAUCHER_ABSTAND", ())
)

ROLLEN_FILTER: dict[int, dict[str, object]] = {
    m.FCT_TYPE: m.ROLLEN for m in MODULE if getattr(m, "ROLLEN", None)
}

RUNDINSTRUMENTE: dict[int, tuple[tuple[str, dict], ...]] = {
    m.FCT_TYPE: m.RUNDINSTRUMENTE for m in MODULE if getattr(m, "RUNDINSTRUMENTE", None)
}
