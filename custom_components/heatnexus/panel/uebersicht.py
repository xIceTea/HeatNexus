"""Die Zeilen der Übersicht: Kennwerte, Heizkreise, Störungen und Schnellzugriff."""

from __future__ import annotations

from collections import Counter
from typing import Any

from ..const import FCT_ZSP, QUELLEN_SYMBOLE
from ..dashboard.muster import namensmuster, rueckfrage
from ..device_db import get_layers
from ..helpers import mustername
from ..schema import modul_in_betrieb
from ..schema import passt as _passt
from .hilfe import hilfe
from .muster import (
    KAMINKEHRER,
    KENNWERT,
    KENNWERT_JE_FCT,
    KENNWERT_QUELLE,
    SCHNELLZUGRIFF,
    STOERUNGSMELDER,
    WARMWASSER,
    WARMWASSER_IST_KENNWERT,
    ZIRKULATION_IST_KENNWERT,
)
from .steuerung import (
    ausloeser_optionen,
    bereitet_warmwasser,
    kaminkehrer_bedienung,
    warmwasser_bedienung,
    ww_ausloeser,
)
from .suche import eintrag_suchen, erster, kennung_suchen

SCHNELLZUGRIFF_MAX = 6


def _zeile(treffer: dict[str, Any], teil: dict[str, Any], untertitel: str, symbol: str) -> dict:
    return {
        "entity": treffer["entity_id"],
        "titel": teil["name"],
        "untertitel": untertitel,
        "symbol": symbol,
    }


def _quellen_kennwert(teil: dict[str, Any], symbol: str) -> list[dict[str, Any]]:
    """Eine Wärmequelle hat keinen Funktionstyp und kein Namensmuster der Baureihe.

    Ihre Zeile zeigt, ob sie gerade Wärme liefert.
    """
    muster, beschriftung, _, schluessel = KENNWERT_QUELLE
    treffer = erster(teil["entitaeten"], muster, *schluessel)
    return [_zeile(treffer, teil, beschriftung, symbol)] if treffer is not None else []


def _leitkennwert(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Der Leitwert eines Anlagenteils: die erste passende Zeile seiner Mustervorlage."""
    vorlage = KENNWERT_JE_FCT.get(teil.get("fct_type")) or KENNWERT
    for muster, beschriftung, symbol, schluessel in vorlage:
        if (treffer := erster(teil["entitaeten"], muster, *schluessel)) is None:
            continue
        zeile = _zeile(treffer, teil, beschriftung, symbol)
        # Ein Sollwert von null heißt: keine Anforderung. Statt „0 °C" zu
        # behaupten oder die Zeile verschwinden zu lassen, steht dort dann ein
        # Strich. Kein Klartext: Darunter steht bereits „Anforderung".
        if teil.get("fct_type") == FCT_ZSP:
            zeile["ersatz_unter_null"] = "–"
        return [zeile]
    if (treffer := _leitwert_aus_uebersicht(teil)) is not None:
        return [_zeile(treffer, teil, treffer["name"], "mdi:gauge")]
    return []


def _warmwasser_kennwerte(teil: dict[str, Any], gelistet: set[str]) -> list[dict[str, Any]]:
    """Warmwasser und Zirkulation hängen als Datenpunkte am Heizkreis.

    In der Übersicht bekommen sie eigene Zeilen, weil man sie täglich liest. Ist der
    Wert schon Leitwert eines eigenen Speichers, bleibt es bei einer Zeile.
    """
    zeilen = []
    for muster, beschriftung, symbol, schluessel in (
        (WARMWASSER_IST_KENNWERT, "Warmwasser", "mdi:water-boiler", ("dhw_temperature",)),
        (ZIRKULATION_IST_KENNWERT, "Zirkulation", "mdi:reload", ("dhw_circulation_temperature",)),
    ):
        treffer = erster(teil["entitaeten"], muster, *schluessel)
        if treffer is not None and treffer["entity_id"] not in gelistet:
            zeilen.append(_zeile(treffer, teil, beschriftung, symbol))
    return zeilen


def kennwerte(anlage: dict[str, Any]) -> list[dict[str, Any]]:
    """Eine Zeile je Anlagenteil, dazu Warmwasser und Zirkulation."""
    zeilen: list[dict[str, Any]] = []
    for teil in anlage["teile"]:
        # **Ein Pumpen-/Relaismodul ohne Aufgabe kommt gar nicht vor.** Es meldet
        # zwar Sollwerte, schaltet aber nichts – im Schaubild fliegt es längst heraus.
        if teil.get("fct_type") == FCT_ZSP and not modul_in_betrieb(teil["entitaeten"]):
            continue
        if (art := teil.get("art")) in QUELLEN_SYMBOLE:
            zeilen += _quellen_kennwert(teil, QUELLEN_SYMBOLE[art])
            continue
        neu = _leitkennwert(teil)
        gelistet = {k["entity"] for k in [*zeilen, *neu]}
        zeilen += neu + _warmwasser_kennwerte(teil, gelistet)
    return zeilen


def heizkreise(anlage: dict[str, Any]) -> list[dict[str, Any]]:
    """Thermostat und Vorlauf je Heizkreis."""
    zeilen = []
    for teil in anlage["teile"]:
        thermostat = next((e for e in teil["entitaeten"] if e["bereich"] == "climate"), None)
        if thermostat is None:
            continue
        vorlauf = erster(teil["entitaeten"], r"vorlauftemperatur ist", "flow_temperature")
        zeilen.append(
            {
                "entity": thermostat["entity_id"],
                "titel": teil["name"],
                "vorlauf": vorlauf["entity_id"] if vorlauf else None,
            }
        )
    return zeilen


def stoerungen(anlage: dict[str, Any]) -> list[dict[str, Any]]:
    """Der Klartext trägt den Text; der Ja/Nein-Sensor desselben Teils sagt, ob etwas ansteht."""
    zeilen = []
    for teil in anlage["teile"]:
        melder = kennung_suchen(teil["entitaeten"], STOERUNGSMELDER, ("binary_sensor",))
        zeilen += [
            {"entity": e["entity_id"], "titel": e["name"], "melder": melder}
            for e in teil["entitaeten"]
            if e["kategorie"] == "diagnostic" and "klartext" in mustername(e).lower()
        ]
    return zeilen


def _schnellzugriff_ziel(
    teil: dict[str, Any], muster: str, schluessel: tuple[str, ...], warmwasser: bool
) -> dict[str, Any] | None:
    """Die Entität hinter einer Schnellzugriff-Taste."""
    if warmwasser and (treffer := ww_ausloeser(teil)) is not None:
        return treffer
    return eintrag_suchen(
        teil["entitaeten"], namensmuster(muster), ("switch", "button", "select"), *schluessel
    )


def _schnellzugriff_eintrag(
    treffer: dict[str, Any],
    teil: dict[str, Any],
    beschriftung: str,
    symbol: str,
    alle: list[dict[str, Any]],
) -> dict[str, Any]:
    """Eine Taste mit Rückfrage, Hilfe und den Angaben ihrer Bedienung."""
    eintrag = {
        "entity": treffer["entity_id"],
        "titel": beschriftung,
        "symbol": symbol,
        "frage": rueckfrage(mustername(treffer)),
        "hilfe": hilfe(mustername(treffer)) or hilfe(beschriftung),
    }
    if _passt(beschriftung, WARMWASSER):
        eintrag.update(warmwasser_bedienung(alle, teil["entitaeten"]))
        eintrag.update(ausloeser_optionen(treffer))
    if _passt(mustername(treffer), KAMINKEHRER):
        eintrag.update(kaminkehrer_bedienung(teil["entitaeten"]))
    eintrag["anlagenteil"] = teil["name"]
    return eintrag


def schnellzugriff(anlage: dict[str, Any], alle: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Die Tasten der Übersicht.

    Ohne Warmwasserbereitung hat auch „Warmwasser laden" nichts verloren – der
    Datenpunkt existiert am Heizkreis trotzdem.
    """
    hat_warmwasser = bereitet_warmwasser(alle)
    eintraege = []
    for teil in anlage["teile"]:
        for muster, beschriftung, symbol, schluessel in SCHNELLZUGRIFF:
            ist_warmwasser = _passt(beschriftung, WARMWASSER)
            if ist_warmwasser and not hat_warmwasser:
                continue
            treffer = _schnellzugriff_ziel(teil, muster, schluessel, ist_warmwasser)
            if treffer is not None:
                eintraege.append(_schnellzugriff_eintrag(treffer, teil, beschriftung, symbol, alle))
    # Den Anlagenteil nennt nur, wer sich sonst nicht unterscheiden ließe.
    titel = Counter(e["titel"] for e in eintraege)
    for eintrag in eintraege:
        if titel[eintrag["titel"]] == 1:
            del eintrag["anlagenteil"]
    return eintraege[:SCHNELLZUGRIFF_MAX]


def _leitwert_aus_uebersicht(teil: dict[str, Any]) -> dict[str, Any] | None:
    """Der Leitwert einer Baureihe, für die es kein Namensmuster gibt.

    `parameterLayer.json` führt je Funktionstyp eine Übersichtsebene – die
    Antwort des Herstellers auf „was gehört auf die Titelseite". Sie steht als
    `overview` in der Geräte-Datenbank und dient hier als Rückfall, in ihrer
    eigenen Reihenfolge. Ohne sie bliebe die Zeile eines fremden Anlagenteils
    leer, obwohl die Anlage Werte liefert.
    """
    ebenen = get_layers(teil.get("fct_type")) or {}
    uebersicht = ebenen.get("overview") or []
    if not uebersicht:
        return None
    je_adresse = {
        eintrag["adresse"]: eintrag
        for eintrag in reversed(teil["entitaeten"])
        if eintrag.get("adresse") and eintrag.get("kategorie") is None
    }
    treffer = [je_adresse[a] for a in uebersicht if a in je_adresse]
    if not treffer:
        return None
    # Ein gefüllter Wert hat Vorrang – wie in `erster`. Beim ersten Aufbau ist
    # erst ein Teil der Anlage gelesen; die Reihenfolge des Herstellers allein
    # zeigte dann eine leere Zeile, obwohl daneben schon ein Wert bereitstand.
    return next((e for e in treffer if e.get("hat_wert")), treffer[0])
