"""Der Reiter „Zeitprogramme" und die Frage, wann ein Programm gilt."""

from __future__ import annotations

from typing import Any

from ..const import FCT_BUFFER
from ..dashboard.anlagen import trifft
from ..helpers import mustername
from ..schema import passt as _passt
from .hilfe import hilfe
from .muster import (
    BETRIEBSWAHL,
    WARMWASSER,
    ZEITPROGRAMM,
    ZIRKULATIONSPROGRAMM,
    ZIRKULATIONSPUMPE,
)
from .suche import eintrag_suchen


def zeitprogramme(anlage: dict[str, Any]) -> list[dict[str, str]]:
    """Alle Zeitprogramme der Anlage, für den eigenen Reiter.

    Die Blöcke selbst holt die Oberfläche aus den Attributen der Entität – sie
    stehen dort schon, und ein zweiter Weg über den Server würde nur dieselben
    Daten ein zweites Mal aufbereiten.

    Was hier steht, ist eine **Vorauswahl am Namen**: Ob eine Entität wirklich
    ein Zeitprogramm führt, sagt erst ihr Attribut ``blocks``. Die Oberfläche
    lässt Karten ohne Blöcke weg. Andersherum ginge es nicht – die
    Registry-Einträge, aus denen diese Liste entsteht, tragen die Typkennung
    der Anlage nicht mit.
    """
    programme: list[dict[str, str]] = []
    for teil in anlage["teile"]:
        for eintrag in teil["entitaeten"]:
            if eintrag["bereich"] != "sensor" or not _passt(mustername(eintrag), ZEITPROGRAMM):
                continue
            programm = {
                "entity": eintrag["entity_id"],
                "titel": eintrag["name"],
                "anlagenteil": teil["name"],
                # Das Symbol des **Programms**, nicht des Anlagenteils.
                # Warmwasser und Zirkulation hängen als Datenpunkte am
                # Heizkreis; mit dessen Symbol trugen beide einen Heizkörper.
                "symbol": _programmsymbol(eintrag, teil),
            }
            if text := hilfe(mustername(eintrag)):
                programm["hilfe"] = text
            if bezeichnung := eintrag.get("bezeichnung"):
                programm["bezeichnung"] = bezeichnung
            if (wirkung := _wirkt_nur_wenn(eintrag, teil)) is not None:
                programm["wirkung"] = wirkung
            programm.update(_einordnung(eintrag, teil))
            programme.append(programm)
    return programme


def _einordnung(eintrag: dict[str, Any], teil: dict[str, Any]) -> dict[str, Any]:
    """Anlagenteil, Gruppe, Farbskala und Programmnummer einer Karte.

    Die Oberfläche fasst damit die Programme eines Anlagenteils in einer Karte zusammen.
    """
    einordnung: dict[str, Any] = {"teil": teil.get("id") or teil["name"]}
    adresse = eintrag.get("adresse")
    if adresse in HEIZPROGRAMM_ADRESSEN:
        nummer = HEIZPROGRAMM_ADRESSEN.index(adresse) + 1
        return {**einordnung, "gruppe": "heizen", "art": "raum", "nummer": nummer}
    if adresse in VORLAUFPROGRAMM_ADRESSEN:
        nummer = VORLAUFPROGRAMM_ADRESSEN.index(adresse) + 1
        return {**einordnung, "gruppe": "heizen", "art": "vorlauf", "nummer": nummer}
    if _ist_zirkulation(eintrag):
        # Nur das Temperaturprogramm führt Temperaturen; das Zeitprogramm schaltet ein und aus.
        if eintrag.get("schluessel") == "dhw_circulation_program_temperature":
            einordnung["art"] = "wasser"
        return {**einordnung, "gruppe": "zirkulation"}
    if adresse == WW_PROGRAMM_ADRESSE or _passt(mustername(eintrag), WARMWASSER):
        return {**einordnung, "gruppe": "warmwasser", "art": "wasser"}
    if teil.get("fct_type") == FCT_BUFFER:
        return {**einordnung, "gruppe": "puffer", "art": "wasser"}
    return einordnung


def _programmsymbol(eintrag: dict[str, Any], teil: dict[str, Any]) -> str | None:
    """Das Symbol einer Zeitprogramm-Karte.

    Dieselben Bilder wie in der Heizungsübersicht – aber nach dem, was das
    Programm steuert, nicht nach dem Anlagenteil, an dem sein Datenpunkt
    hängt. Warmwasser und Zirkulation sitzen beide am Heizkreis und trugen
    deshalb dessen Heizkörper.
    """
    if _ist_zirkulation(eintrag):
        return "mdi:reload"
    if _passt(mustername(eintrag), WARMWASSER):
        return "mdi:water-boiler"
    return teil.get("symbol")


def _ist_zirkulation(eintrag: dict[str, Any]) -> bool:
    return _passt(mustername(eintrag), ZIRKULATIONSPROGRAMM) or trifft(
        eintrag,
        ZIRKULATIONSPROGRAMM,
        "dhw_circulation_program_time",
        "dhw_circulation_program_temperature",
    )


def _auswahltext(wahl: dict[str, Any], wert: int, ersatz: str) -> str:
    """Der Text, den die Auswahl für diesen Wert zeigt, klein geschrieben.

    Ohne bekannte Texte bleibt das deutsche Ersatzwort.
    """
    return ((wahl.get("optionen") or {}).get(wert) or ersatz).lower()


def _ziel(wahl: dict[str, Any], wert: int) -> dict[str, str]:
    """Worauf „Aktivieren" die Auswahl stellt – nur bei `select` und bekanntem Text."""
    text = (wahl.get("optionen") or {}).get(wert)
    if wahl.get("bereich") != "select" or not text:
        return {}
    return {"ziel": text, "wahl_name": wahl.get("name") or ""}


def _puffer_wirkung(teil: dict[str, Any]) -> dict[str, str] | None:
    """Das Zeitprogramm des Puffers greift nur in einer Betriebswahl.

    `20/15` kennt Standby, Automatikbetrieb, Festbrennstoff-, Pufferbetrieb,
    **Auto mit Zeitprogramm**, Hand- und Kaminkehrerbetrieb. Nur in „Auto mit
    Zeitprogramm" richtet sich der Puffer nach seinem Programm; in allen
    anderen läuft das schönste Programm ins Leere.

    Versteckt wird die Karte trotzdem nicht: Anders als bei der Zirkulation
    gibt es hier kein zweites Programm, das stattdessen gilt – es gäbe also
    nichts zu sehen, und vorbereiten können muss man es.
    """
    wahl = next(
        (
            e
            for e in teil["entitaeten"]
            if e["bereich"] in ("select", "sensor")
            and trifft(e, BETRIEBSWAHL, "buffer_mode_selection")
        ),
        None,
    )
    if wahl is None:
        return None
    return {
        "entity": wahl["entity_id"],
        "muster": _auswahltext(wahl, 4, "zeitprogramm"),
        "hinweis": "Wirkt erst, wenn die Betriebswahl auf „Auto mit Zeitprogramm“ steht.",
        **_ziel(wahl, 4),
    }


# Die drei Heizprogramme eines Kreises liegen auf `3/61` bis `3/63`, und die
# Betriebswahl `3/50` bietet dieselben drei unter ihren eigenen Namen an.
HEIZPROGRAMM_ADRESSEN = ("3/61", "3/62", "3/63")


# Das Warmwasserprogramm des Kreises.
WW_PROGRAMM_ADRESSE = "5/61"


# Vorlaufprogramme 1–3 (Infinity PLUS, DuoWIN). Sie gelten bei derselben Betriebswahl wie das
# Raumprogramm gleicher Nummer; ob der Kreis Raum- oder Vorlaufwerte fährt, entscheidet `7/76`.
VORLAUFPROGRAMM_ADRESSEN = ("58/78", "58/79", "58/80")


def _heizkreis_wirkung(programm: dict[str, Any], teil: dict[str, Any]) -> dict[str, str] | None:
    """Woran hängt, ob ein Programm des Heizkreises gerade gilt.

    `3/61`–`3/63` entsprechen den Werten 1–3 der Betriebswahl `3/50`, Standby ist 0.
    """
    adresse = programm.get("adresse")
    if adresse not in (*HEIZPROGRAMM_ADRESSEN, *VORLAUFPROGRAMM_ADRESSEN, WW_PROGRAMM_ADRESSE):
        return None
    wahl = eintrag_suchen(teil["entitaeten"], BETRIEBSWAHL, ("select", "sensor"), "mode_selection")
    if wahl is None:
        return None
    if adresse == WW_PROGRAMM_ADRESSE:
        # „WW-Betrieb" heißt nur Warmwasser, „Programm 1–3", „Heizbetrieb" und
        # „Absenkbetrieb" heißen Heizung und Warmwasser. Übrig bleibt Standby,
        # und dort nimmt der Kreis nicht einmal einen Ladebefehl an.
        return {
            "entity": wahl["entity_id"],
            "muster_nicht": _auswahltext(wahl, 0, "standby"),
            "hinweis": "Wirkt nicht, solange die Betriebswahl auf „Standby“ steht.",
        }
    nummern = (
        HEIZPROGRAMM_ADRESSEN if adresse in HEIZPROGRAMM_ADRESSEN else VORLAUFPROGRAMM_ADRESSEN
    )
    wert = nummern.index(adresse) + 1
    return {
        "entity": wahl["entity_id"],
        "muster": _auswahltext(wahl, wert, programm.get("name") or ""),
        "hinweis": "Wirkt erst, wenn die Betriebswahl auf diesem Programm steht.",
        **_ziel(wahl, wert),
    }


def _wirkt_nur_wenn(programm: dict[str, Any], teil: dict[str, Any]) -> dict[str, str] | None:
    """Der Datenpunkt, an dem hängt, ob ein Programm überhaupt etwas bewirkt.

    **Die Anlage führt zwei Zirkulationsprogramme.** In der Herstellerdatei
    heißen sie wortgleich „WW-Zirkulationsprogramm"; auseinanderhalten lassen
    sie sich nur an der Adresse. `5/65` gilt, wenn die Zirkulationspumpe
    (`5/6`) auf **Zeitsteuerung** steht, `5/64` bei **Temperatursteuerung**.
    Ohne diese Unterscheidung standen zwei gleichnamige Karten nebeneinander,
    und keine sagte, welche gerade wirkt.

    Deshalb nennt jedes Programm die Steuerungsart, bei der es greift.
    """
    if not _passt(mustername(programm), ZIRKULATIONSPROGRAMM):
        # Kein Zirkulationsprogramm – am Puffer entscheidet seine eigene
        # Betriebswahl, am Heizkreis die des Kreises.
        if teil.get("fct_type") == FCT_BUFFER:
            return _puffer_wirkung(teil)
        return _heizkreis_wirkung(programm, teil)
    pumpe = next(
        (
            e
            for e in teil["entitaeten"]
            if e["bereich"] in ("select", "sensor")
            # `5/6` ist der Modus, an dem hängt, ob das Programm überhaupt
            # greift – nicht `1/65`, der nur meldet, ob die Pumpe gerade läuft.
            and trifft(e, ZIRKULATIONSPUMPE, "dhw_circulation_mode")
        ),
        None,
    )
    if pumpe is None:
        return None
    wirkung = {
        "entity": pumpe["entity_id"],
        "muster": _auswahltext(pumpe, 1, "zeitsteuerung"),
        "hinweis": "Wirkt erst, wenn die Zirkulationspumpe auf „Mit Zeitsteuerung“ steht.",
    }
    # Welche Art dieses Programm ist, sagt allein sein Schlüssel – der Name
    # taugt dafür nicht, beide heißen gleich.
    schluessel = programm.get("schluessel")
    if schluessel == "dhw_circulation_program_temperature":
        wirkung["muster"] = _auswahltext(pumpe, 2, "temperatursteuerung")
        wirkung["hinweis"] = (
            "Wirkt erst, wenn die Zirkulationspumpe auf „Mit Temperatursteuerung“ steht."
        )
    temperatur = schluessel == "dhw_circulation_program_temperature"
    wirkung.update(_ziel(pumpe, 2 if temperatur else 1))
    return wirkung
