"""Abgaswächter im Takt des Befunds: ruhigen Betrieb erkennen, Tagessummen fortschreiben."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from ..helpers import get_oid_raw, get_oid_value
from . import abgas
from .abgasziele import ABGAS, BRENNSTOFF_PUROWIN, AbgasZiel, ziele
from .auswertung import Abgasgeraet
from .pflegelauf import beschreibungen, beschrieben, geraetename, klassen

KESSEL, LEISTUNG, PHASE, O2 = "/0/7/0", "/0/9/0", "/2/1/0", "/0/42/0"
# Im Pflegestand des Archivs: bis zu welchem Tag Abgastage aus der Langzeitstatistik stammen.
NACHGERECHNET = "abgas_nachgerechnet"
# Ebenda: seit wann ein O2-Wert gelesen wurde; ohne eigene Entität kommt er erst mit dem ersten Takt.
O2_GESEHEN = "abgas_o2"
# Reihenfolge wie `abgas.stunde_aus_statistik`.
FELDER_STATISTIK = {"leistung": LEISTUNG, "abgas": ABGAS, "kessel": KESSEL, "o2": O2}


def ziele_von(coordinator: Any) -> list[AbgasZiel]:
    """Die Kessel mit Abgaswächter aus Beschreibungen und Geräteklassen der Erkennung."""
    return ziele(beschreibungen(coordinator), klassen(coordinator))


def mit_o2(coordinator: Any, prefix: str, archiv: Any = None) -> bool:
    """Ob der Kessel ein O2-Signal führt: als Entität, als gelesener Wert oder laut Archiv."""
    gesehen = archiv is not None and bool(archiv.pflege_eintrag(prefix, O2_GESEHEN))
    if gesehen or beschrieben(coordinator, f"{prefix}{O2}"):
        return True
    return get_oid_raw(coordinator, O2, prefix) is not None


def _o2_merken(coordinator: Any, archiv: Any, prefix: str, tag: str) -> None:
    if archiv.pflege_eintrag(prefix, O2_GESEHEN) or get_oid_raw(coordinator, O2, prefix) is None:
        return
    archiv.pflege_setzen(prefix, O2_GESEHEN, {"seit": tag})


def abruf(coordinator: Any) -> set[str]:
    """Die Adressen je Kessel, die frisch sein müssen; O2 liegt meist nur auf der Serviceebene."""
    adressen = (ABGAS, KESSEL, LEISTUNG, PHASE, O2)
    # Der LogWIN wertet keine Leistung aus; sie wird dort nicht abgefragt.
    return {
        f"{z.prefix}{a}"
        for z in ziele_von(coordinator)
        for a in adressen
        if not (z.logwin and a == LEISTUNG)
    }


def messen(
    coordinator: Any,
    archiv: Any,
    zustaende: dict[str, dict[str, Any]],
    zeit: datetime,
    raumluft: float | None = None,
) -> dict[str, dict[str, Any]]:
    """Je Kessel einen Takt bewerten; liefert die neuen Laufzustände, gültige Takte gehen ins Archiv."""
    neu: dict[str, dict[str, Any]] = {}
    for z in ziele_von(coordinator):

        def wert(adresse: str, z: AbgasZiel = z) -> float | None:
            return get_oid_value(coordinator, adresse, z.prefix)

        _o2_merken(coordinator, archiv, z.prefix, zeit.date().isoformat())
        leistung = None if z.logwin else wert(LEISTUNG)
        messung = abgas.Messung(wert(ABGAS), wert(KESSEL), leistung, wert(PHASE), wert(O2))
        neu[z.prefix], stufe = abgas.bewerten(zustaende.get(z.prefix, {}), messung, zeit, z.logwin)
        if stufe is None or messung.abgas is None or messung.kessel is None:
            continue
        dt = messung.abgas - messung.kessel
        tage = abgas.sammeln(
            archiv.abgas_tage(z.prefix),
            zeit.date().isoformat(),
            stufe,
            dt,
            messung.o2,
            messung.abgas,
            raumluft,
        )
        archiv.abgas_setzen(z.prefix, tage)
    return neu


def geraete(coordinator: Any, archiv: Any) -> list[Abgasgeraet]:
    """Je Kessel mit Abgaswächter, was die Auswertung braucht; der Bezug folgt der letzten Reinigung."""
    liste = []
    for z in ziele_von(coordinator):
        code = (
            get_oid_value(coordinator, BRENNSTOFF_PUROWIN, z.prefix) if z.fct_type == 25 else None
        )
        liste.append(
            Abgasgeraet(
                kennung=z.device_id,
                name=geraetename(coordinator, z.device_id),
                prefix=z.prefix,
                logwin=z.logwin,
                brennstoff=abgas.brennstoff(z.fct_type, code),
                bezug_ab=archiv.pflege_eintrag(z.prefix, z.bezug_art).get("zuletzt"),
                mit_o2=mit_o2(coordinator, z.prefix, archiv),
                nachgerechnet_bis=archiv.pflege_eintrag(z.prefix, NACHGERECHNET).get("bis"),
            )
        )
    return liste


def arten(coordinator: Any, archiv: Any = None) -> list[tuple[str, str, tuple[str, ...]]]:
    """Je Kessel Kennung, Gerät und Arten der Befund-Sensoren, wie `geraete_der_anlage` sie führt."""
    return [
        (
            z.device_id,
            z.device_id,
            ("abgas", "abgasverlust") if mit_o2(coordinator, z.prefix, archiv) else ("abgas",),
        )
        for z in ziele_von(coordinator)
    ]


def _je_stunde(
    statistik: dict[str, list[dict[str, Any]]],
    felder: dict[str, str],
    stunde_von: Callable[[dict[str, Any]], str],
) -> dict[str, dict[str, dict[str, Any]]]:
    stunden: dict[str, dict[str, dict[str, Any]]] = {}
    for name, entity_id in felder.items():
        for zeile in statistik.get(entity_id, []):
            stunden.setdefault(stunde_von(zeile), {})[name] = zeile
    return stunden


async def nachrechnen(
    coordinator: Any,
    archiv: Any,
    entitaet_von: Callable[[str, str], str | None],
    holen: Callable[[set[str], set[str]], Awaitable[dict[str, list[dict[str, Any]]]]],
    stunde_von: Callable[[dict[str, Any]], str],
    heute: str,
) -> int:
    """Tage vor dem ersten Takt aus Stundenmittel, -minimum und -maximum.

    Ohne Leistung (LogWIN) oder O2 entsteht der Bezug nur im Takt, nach Phase gefiltert.
    """
    reihen = {}
    for z in ziele_von(coordinator):
        felder = {n: entitaet_von(z.device_id, a) for n, a in FELDER_STATISTIK.items()}
        if not z.logwin and all(felder.values()):
            reihen[z.prefix] = {n: e for n, e in felder.items() if e}
    ids = {e for felder in reihen.values() for e in felder.values()}
    statistik = await holen(ids, {"mean", "min", "max"}) if ids else {}
    neu = 0
    for prefix, felder in reihen.items():
        # Früher nachgerechnete Tage entstehen neu; die Langzeitstatistik hat sie noch.
        bis = archiv.pflege_eintrag(prefix, NACHGERECHNET).get("bis") or ""
        tage = {d: v for d, v in archiv.abgas_tage(prefix).items() if d > bis}
        vorhanden = set(tage)
        for stunde, werte in sorted(_je_stunde(statistik, felder, stunde_von).items()):
            tag = stunde[:10]
            ergebnis = abgas.stunde_aus_statistik(*(werte.get(n) or {} for n in FELDER_STATISTIK))
            if tag in vorhanden or tag >= heute or ergebnis is None:
                continue
            stufe_, dt, o2, ta = ergebnis
            # Nur den einen Tag fortschreiben; `tage` ist hier schon eine eigene Kopie.
            tage[tag] = abgas.sammeln(
                {tag: tage.get(tag, {})}, tag, stufe_, dt, o2, ta, None, abgas.TAKTE_JE_STUNDE
            )[tag]
            neu += 1
        archiv.abgas_setzen(prefix, tage)
        if neu_tage := sorted(set(tage) - vorhanden):
            archiv.pflege_setzen(prefix, NACHGERECHNET, {"bis": neu_tage[-1]})
    return neu
