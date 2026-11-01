"""Welcher Wärmeerzeuger in der Oberfläche vorn steht.

Mit nur einem Kessel bleibt alles wie gehabt.
"""

# Erst Wärmepumpe oder Hybridmanager bringen mehr als einen Kandidaten – und
# der Kessel gewönne sonst immer, weil nur seine Datenpunkte kanonische
# Schlüssel tragen.

from __future__ import annotations

from typing import Any

from ..const import (
    HAUPTSYSTEM_AUTO,
    HAUPTSYSTEM_HYBRID,
    HAUPTSYSTEM_KESSEL,
    HAUPTSYSTEM_WAERMEPUMPE,
)
from ..schema.werte import ART_JE_FCT, kesselart_des_teils
from .muster import STATUS, STATUS_HYBRID, STATUS_WAERMEPUMPE, Zeile
from .suche import zeilen_aus

HYBRIDMANAGER = 26

ROLLEN = (HAUPTSYSTEM_HYBRID, HAUPTSYSTEM_WAERMEPUMPE, HAUPTSYSTEM_KESSEL)

VORLAGE_JE_ROLLE: dict[str, tuple[Zeile, ...]] = {
    HAUPTSYSTEM_HYBRID: STATUS_HYBRID,
    HAUPTSYSTEM_WAERMEPUMPE: STATUS_WAERMEPUMPE,
    HAUPTSYSTEM_KESSEL: STATUS,
}


def _rolle(teil: dict[str, Any]) -> str | None:
    """Hybridmanager, Wärmepumpe, Kessel – oder nichts davon."""
    try:
        fct = int(teil.get("fct_type"))
    except (TypeError, ValueError):
        return None
    if fct == HYBRIDMANAGER:
        return HAUPTSYSTEM_HYBRID
    if ART_JE_FCT.get(fct) != "kessel":
        return None
    if kesselart_des_teils(teil) == "waermepumpe":
        return HAUPTSYSTEM_WAERMEPUMPE
    return HAUPTSYSTEM_KESSEL


def erzeuger(anlage: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Die Teile der Anlage nach Rolle, in ihrer Reihenfolge."""
    je_rolle: dict[str, list[dict[str, Any]]] = {rolle: [] for rolle in ROLLEN}
    for teil in anlage["teile"]:
        if rolle := _rolle(teil):
            je_rolle[rolle].append(teil)
    return je_rolle


def _mehrere(je_rolle: dict[str, list[dict[str, Any]]]) -> bool:
    """Ob es überhaupt etwas zu entscheiden gibt."""
    return bool(je_rolle[HAUPTSYSTEM_HYBRID] or je_rolle[HAUPTSYSTEM_WAERMEPUMPE])


def aufloesen(wahl: str | None, je_rolle: dict[str, list[dict[str, Any]]]) -> str:
    """Die Wahl in eine Rolle übersetzen, die es an der Anlage auch gibt."""
    if wahl and wahl != HAUPTSYSTEM_AUTO and je_rolle.get(wahl):
        return wahl
    for rolle in (HAUPTSYSTEM_HYBRID, HAUPTSYSTEM_WAERMEPUMPE):
        if je_rolle[rolle]:
            return rolle
    return HAUPTSYSTEM_KESSEL


def reihenfolge(rolle: str) -> tuple[str, ...]:
    """Die gewählte Rolle vorn, die übrigen in fester Folge dahinter."""
    return (rolle, *(r for r in ROLLEN if r != rolle))


# So viele Werte stehen je Erzeuger unter dem Schaubild; der Rest bleibt
# auf der Geräteseite.
SPALTE_MAX = 8


def _phase(teil: dict[str, Any]) -> list[dict[str, str]]:
    """Der Betriebszustand eines Erzeugers als eine Zeile mit seinem Namen."""
    zeilen = zeilen_aus(
        teil["entitaeten"], VORLAGE_JE_ROLLE[_rolle(teil) or HAUPTSYSTEM_KESSEL][:1]
    )
    return [{**z, "titel": teil["name"]} for z in zeilen]


def status(anlage: dict[str, Any], alle: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Die Zeilen des Systemstatus: nur das Hauptsystem.

    Ohne Wärmepumpe und Hybridmanager entsteht genau die bisherige Liste. Am
    Hybridmanager kommt je Erzeuger sein Betriebszustand dazu – daran sieht
    man, welcher gerade läuft.
    """
    je_rolle = erzeuger(anlage)
    if not _mehrere(je_rolle):
        return zeilen_aus(alle, STATUS)
    rolle = aufloesen(anlage.get("hauptsystem"), je_rolle)
    zeilen: list[dict[str, str]] = []
    for teil in je_rolle[rolle]:
        eigene = zeilen_aus(teil["entitaeten"], VORLAGE_JE_ROLLE[rolle])
        if eigene:
            zeilen.append({"abschnitt": teil["name"]})
            zeilen.extend(eigene)
    if rolle == HAUPTSYSTEM_HYBRID:
        for andere in (HAUPTSYSTEM_WAERMEPUMPE, HAUPTSYSTEM_KESSEL):
            for teil in je_rolle[andere]:
                zeilen.extend(_phase(teil))
    return zeilen


def nebensysteme(anlage: dict[str, Any]) -> list[dict[str, Any]]:
    """Die übrigen Erzeuger mit ihren wichtigsten Werten, für unter das Schaubild."""
    je_rolle = erzeuger(anlage)
    if not _mehrere(je_rolle):
        return []
    rolle = aufloesen(anlage.get("hauptsystem"), je_rolle)
    spalten = []
    for andere in reihenfolge(rolle)[1:]:
        for teil in je_rolle[andere]:
            zeilen = zeilen_aus(teil["entitaeten"], VORLAGE_JE_ROLLE[andere])[:SPALTE_MAX]
            if zeilen:
                spalten.append({"titel": teil["name"], "zeilen": zeilen})
    return spalten


def teile_geordnet(anlage: dict[str, Any]) -> list[dict[str, Any]]:
    """Die Teile mit dem Hauptsystem vorn – für das Schaubild."""
    je_rolle = erzeuger(anlage)
    if not _mehrere(je_rolle):
        return anlage["teile"]
    # Die Umschaltung steht zwischen den Erzeugern, nicht am Rand: das
    # Hauptsystem links, dann der Hybridmanager, dann der andere Erzeuger.
    rolle = aufloesen(anlage.get("hauptsystem"), je_rolle)
    if rolle == HAUPTSYSTEM_HYBRID:
        rolle = HAUPTSYSTEM_WAERMEPUMPE
    erster = (rolle, HAUPTSYSTEM_HYBRID)
    folge = (*erster, *(r for r in ROLLEN if r not in erster))
    vorn = [teil for rolle in folge for teil in je_rolle[rolle]]
    return vorn + [t for t in anlage["teile"] if t not in vorn]
