"""Gerätewissen je Funktionstyp, ein Modul je Baureihe.

Hier werden die Einzelmodule zu den Tabellen zusammengesetzt, die der Rest der
Integration liest. Eine weitere Baureihe ist eine Datei und ein Eintrag in
`MODULE`.
"""

from __future__ import annotations

from types import ModuleType

from . import (
    automatikkessel,
    biowin,
    erzeugerpumpe,
    gas_oel_kessel,
    heizkreis,
    heizkreis_infinity,
    kaskade,
    puffer,
    pufferspeicher,
    purowin,
    solar,
    solar_es,
    umschaltung,
    waermepumpe,
    waermepumpe_direkt,
    waermepumpe_energie,
    warmwasser,
    zsp,
    zusatzheizung,
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
    zsp,
)

# Was für ein Anlagenteil das ist – für die Geräteseite in Home Assistant. Der
# Name der Anlage taugt dafür nicht: Er ist oft von Hand vergeben und
# beschreibt den Raum, nicht das Gerät.
MODELLE: dict[int, str] = {m.FCT_TYPE: m.MODELL for m in MODULE if m.MODELL}

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

# Begriffe, die eine Baureihe nur über den LON-Bus hergibt.
NUR_BUS: dict[int, tuple[str, ...]] = {m.FCT_TYPE: m.NUR_BUS for m in MODULE if m.NUR_BUS}

# Namen, die erst im Zusammenhang einer Baureihe eindeutig sind.
NAMEN: dict[int, dict[str, str]] = {m.FCT_TYPE: m.NAMEN for m in MODULE if m.NAMEN}

# Wo der Funktionstyp die Bauart des Wärmeerzeugers schon festlegt.
KESSELARTEN: dict[int, str] = {m.FCT_TYPE: m.KESSELART for m in MODULE if m.KESSELART}

SCHALTPUNKTE: tuple[dict[str, object], ...] = tuple(
    eintrag for m in MODULE for eintrag in getattr(m, "SCHALTPUNKTE", ())
)

VERBRAUCHER_ABSTAND: tuple[dict[str, object], ...] = tuple(
    eintrag for m in MODULE for eintrag in getattr(m, "VERBRAUCHER_ABSTAND", ())
)

ROLLEN_FILTER: dict[int, dict[str, object]] = {
    m.FCT_TYPE: m.ROLLEN for m in MODULE if getattr(m, "ROLLEN", None)
}
