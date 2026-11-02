"""Arbeitsseite einer Anlage: je Anlagenteil Zeiger, Zustand, Bedienung und Details."""

from __future__ import annotations

from functools import lru_cache
import re
from typing import Any

from ..const import KARTE_ELEMENT
from ..geraete import STATUSZEILEN
from ..geraete.statuszeilen import EINZELN, GEMEINSAM, Statuszeile
from ..schema import anlagenschema
from ..texte import Woerterbuch
from . import auswahl
from .anlagen import erzeuger_von, trifft, voller_name
from .karten import (
    abschnitt,
    ansicht,
    kachel,
    meldungskarte,
    pfad_anlage,
    pfad_teil,
    ueberschrift,
    zeigerinstrument,
)
from .muster import namensmuster


@lru_cache(maxsize=16)
def _kartenmuster(
    zeilen: tuple[Statuszeile, ...],
) -> tuple[tuple[re.Pattern, ...], tuple[str, ...]]:
    """Muster und Schlüssel der Zeilen mit `karte`."""
    karte = [z for z in zeilen if z.karte]
    return namensmuster(*(z.muster for z in karte)), tuple(s for z in karte for s in z.schluessel)


def _trifft_zeilen(eintrag: dict[str, Any], zeilen: tuple[Statuszeile, ...]) -> bool:
    """Ob ein Messwert eine der Zeilen mit `karte` trifft."""
    muster, schluessel = _kartenmuster(zeilen)
    return trifft(eintrag, muster, *schluessel)


def zustandswerte(anlage: dict[str, Any]) -> list[dict[str, Any]]:
    """Meldung, Betriebsphase, Außentemperatur – der Zustand in Kurzform.

    Ab zwei Erzeugern trifft jeder nur seine eigenen Zeilen; die übrigen Teile
    nur die Zeilen der ganzen Anlage.
    """
    erzeuger = {teil["id"] for teil in erzeuger_von(anlage["teile"])}

    def zeilen(teil: dict[str, Any]) -> tuple[Statuszeile, ...]:
        if len(erzeuger) < 2:
            return EINZELN
        return (
            (*GEMEINSAM, *STATUSZEILEN.get(teil["fct_type"], ()))
            if teil["id"] in erzeuger
            else GEMEINSAM
        )

    return [
        e
        for teil in anlage["teile"]
        for e in teil["entitaeten"]
        # Einsteller bleiben draußen: Ein Grenzwert der Serviceebene heißt
        # mitunter wie der Messwert, den er begrenzt.
        if e["hat_wert"] and e.get("kategorie") is None and _trifft_zeilen(e, zeilen(teil))
    ]


def meldungsabschnitt(anlagen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Abschnitt „Meldungen“ über die volle Breite, sichtbar nur, solange eine Störung anliegt."""
    meldungen = [
        meldungskarte(text, voller_name(anlage, teil), stoerung)
        for anlage in anlagen
        for teil in anlage["teile"]
        if (text := auswahl.klartext(teil)) and (stoerung := auswahl.stoerung(teil))
    ]
    abschnitte = abschnitt("Meldungen", meldungen, stil="subtitle", spanne=3)
    if abschnitte:
        # Die Überschrift ist sichtbar, solange eine der Meldungen es ist.
        bedingungen = [b for karte in meldungen for b in karte["visibility"]]
        abschnitte[0]["cards"][0]["visibility"] = (
            bedingungen
            if len(bedingungen) == 1
            else [{"condition": "or", "conditions": bedingungen}]
        )
    return abschnitte


BILDKARTE_FELDER = ("type", "image", "dark_mode_image", "elements")


def schaubild(
    anlage: dict[str, Any], als_karte: bool, mit_liste: bool, buch: Woerterbuch | None = None
) -> dict[str, Any] | None:
    """Schaubild als eigene Karte (bewegt) oder als feste Zeichnung in der Sprache von `buch`."""
    if als_karte:
        karte: dict[str, Any] = {
            "type": f"custom:{KARTE_ELEMENT}",
            "anlage": anlage["id"],
            "farbsatz": "auto",
            "schrift": "normal",
            "animation": True,
            "liste": "rechts",
            "titel_bild": "",
            "titel_liste": "Zustand",
            # Volle Breite: Bild und Werteliste stehen nebeneinander.
            "grid_options": {"columns": 24, "rows": "auto"},
        }
        if mit_liste and (werte := zustandswerte(anlage)):
            karte["zusatzwerte"] = [e["entity_id"] for e in werte]
        return karte
    bild = anlagenschema(anlage["teile"], modulpumpe=anlage.get("modulpumpe", False), buch=buch)
    # Lovelace liest nur diese Felder; Zeichnung und Hilfslisten dienen der Oberfläche.
    if not bild:
        return None
    karte = {feld: bild[feld] for feld in BILDKARTE_FELDER}
    # Den kurzen Namen braucht nur die Oberfläche, für Werte unter dem Bild.
    karte["elements"] = [{k: v for k, v in e.items() if k != "name"} for e in karte["elements"]]
    return karte


def teilabschnitt(teil: dict[str, Any]) -> list[dict[str, Any]]:
    """Abschnitt eines Anlagenteils: Thermostate, Zeiger, Zustand und Bedienung."""
    zeiger = auswahl.zeigerinstrumente(teil)
    gezeigt = {e["entity_id"] for e, _ in zeiger}
    zustand = [e for e in auswahl.zustand(teil) if e["entity_id"] not in gezeigt]
    bedienung = auswahl.bedienung(teil)
    karten: list[dict[str, Any]] = [
        *(kachel(e) for e in auswahl.thermostate(teil)),
        *(zeigerinstrument(e, skala) for e, skala in zeiger),
    ]
    if zustand:
        karten += [ueberschrift("Zustand", "subtitle"), *(kachel(e) for e in zustand)]
    if bedienung:
        karten += [ueberschrift("Bedienung", "subtitle"), *(kachel(e) for e in bedienung)]
    return abschnitt(teil["name"], karten, ziel=pfad_teil(teil))


def arbeitsseite(
    anlage: dict[str, Any], badges: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Ansicht einer Anlage mit allen ihren Teilen; Meldungen und Schaubild stehen in der Übersicht."""
    abschnitte: list[dict[str, Any]] = []
    for teil in anlage["teile"]:
        abschnitte += teilabschnitt(teil)
    return ansicht(anlage["name"] or "Anlage", pfad_anlage(anlage), abschnitte, badges=badges)
