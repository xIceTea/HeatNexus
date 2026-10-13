"""Der Reiter „Steuerung" und die Bedienung, die er mit der Übersicht teilt."""

from __future__ import annotations

import contextlib
import re
from typing import Any

from ..dashboard.anlagen import trifft
from ..dashboard.muster import (
    namensmuster,
    rueckfrage,
)
from ..helpers import mustername
from ..schema import passt as _passt
from .hilfe import HILFE_KARTEN, hilfe
from .muster import (
    BETRIEBSART,
    BETRIEBSART_URLAUB,
    BETRIEBSWAHL,
    BETRIEBSWAHL_STANDBY,
    BETRIEBSWAHL_STANDBY_WERT,
    BETRIEBSWAHL_WW,
    BETRIEBSWAHL_WW_WERT,
    BETRIEBSWAHL_ZURUECK,
    EINMALLADUNG,
    EINMALLADUNG_TEMPERATUR,
    KAMINKEHRER,
    KAMINKEHRER_LAUFZEIT,
    KAMINKEHRER_LEISTUNG,
    KESSEL_BEDIENUNG,
    LAGERRAUM_ANFORDERN,
    LAGERRAUM_ZEILEN,
    UEBERSTEUERUNG_DAUER,
    UEBERSTEUERUNG_TEMPERATUR,
    WARMWASSER,
    WARMWASSER_ABSTAND,
    WARMWASSER_HYSTERESE,
    WARMWASSER_HYSTERESE_MUSTER,
    WARMWASSER_IST,
    WARMWASSER_IST_KENNWERT,
    WARMWASSER_KREIS,
    WARMWASSER_LADEPUMPE,
    WARMWASSER_LAEDT,
    WARMWASSER_LAEDT_WERTE,
    WARMWASSER_MAX,
    WARMWASSER_SCHLUESSEL,
    WARMWASSER_SOLL,
    ZEITPROGRAMM,
)
from .suche import eintrag_suchen, erster, kennung_suchen


def bereitet_warmwasser(entitaeten: list[dict[str, Any]]) -> bool:
    """Prüfen, ob diese Anlage überhaupt Warmwasser bereitet.

    Zwei Belege lässt die Anlage zu: eine gemessene Warmwassertemperatur oder
    einen gemeldeten Warmwasserkreis ungleich null. Solange der Vollabzug noch
    läuft, hat der Istwert womöglich noch keinen Wert – vorhanden sein reicht
    deshalb, ein Wert ist nicht nötig.
    """
    for eintrag in entitaeten:
        if trifft(eintrag, WARMWASSER_IST, "dhw_temperature"):
            return True
        if trifft(eintrag, WARMWASSER_KREIS, "dhw_circuit") and (eintrag.get("wert") or 0) != 0:
            return True
    return False


def warmwasser_zeilen(entitaeten: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Zeilen der Warmwasserkarte – leer, wo es kein Warmwasser gibt."""
    if not bereitet_warmwasser(entitaeten):
        return []
    return [
        {"entity": e["entity_id"], "titel": e["name"]}
        for e in entitaeten
        if e["kategorie"] is None
        and e["bereich"] != "climate"
        and not e.get("abgeleitet")
        and trifft(e, WARMWASSER, *WARMWASSER_SCHLUESSEL)
    ][:WARMWASSER_MAX]


def _ladeschwelle(entitaeten: list[dict[str, Any]]) -> dict[str, Any]:
    """Ab wann die Anlage eine Einmalladung überhaupt annimmt.

    Drei Werte, und der mittlere ist leicht zu verwechseln:

    * **Ist** – die gemessene Warmwassertemperatur.
    * **Soll** – die Temperatur, auf die die *Einmalladung* lädt (``5/51``).
      **Nicht** der gewöhnliche Warmwasser-Sollwert (``1/4``): Der liegt
      niedriger, und die Taste verweigerte damit Ladungen, die die Anlage
      klaglos ausgeführt hätte. Der Abstand sah dann nach der Hysterese aus,
      war aber die Differenz der beiden Sollwerte.
    * **Abstand** – „Hysterese EIN". Die Anleitung nennt 5 K als Werkswert bei
      einem Bereich von 1 bis 20 K; meldet die Anlage den Parameter (``5/0``,
      Serviceebene), gilt ihr eigener Wert.
    """
    ist = erster(entitaeten, WARMWASSER_IST_KENNWERT, "dhw_temperature")
    soll = kennung_suchen(
        entitaeten, EINMALLADUNG_TEMPERATUR, ("number", "sensor")
    ) or kennung_suchen(entitaeten, WARMWASSER_SOLL, ("number", "sensor"), "dhw_temperature_target")
    abstand = WARMWASSER_ABSTAND
    if (hysterese := erster(entitaeten, WARMWASSER_HYSTERESE)) is not None:
        with contextlib.suppress(TypeError, ValueError):
            if (gemeldet := hysterese.get("wert")) is not None:
                abstand = float(gemeldet)
    return {
        "ist": ist["entity_id"] if ist else None,
        "soll": soll,
        "abstand": abstand,
    }


def _optionstexte(eintrag: dict[str, Any] | None, *werte: int) -> list[str]:
    """Die Texte, die eine Entität für diese Werte anzeigt, soweit bekannt."""
    optionen = (eintrag or {}).get("optionen") or {}
    texte = (optionen.get(w) or optionen.get(str(w)) for w in werte)
    return [t for t in texte if t]


def _wahlmuster(eintrag: dict[str, Any] | None, wert: int, muster: str) -> str:
    """Muster für einen Eintrag der Betriebswahl: sein Text, das deutsche Wort als Rückfall."""
    texte = [f"^{re.escape(t)}$" for t in _optionstexte(eintrag, wert)]
    return "|".join([*texte, muster])


# Funktionstypen, die laut Herstellerdaten `2/16` „Freigabe starten" führen.
WW_FREIGABE_TYPEN = (2, 14)


def ww_ausloeser(teil: dict[str, Any]) -> dict[str, Any] | None:
    """Der Auslöser der Einmalladung: am Namen, sonst an der Adresse `2/16`."""
    treffer = eintrag_suchen(teil["entitaeten"], EINMALLADUNG, ("switch", "button"))
    if treffer is None and teil.get("fct_type") in WW_FREIGABE_TYPEN:
        treffer = next(
            (
                e
                for e in teil["entitaeten"]
                if e.get("adresse") == "2/16" and e["bereich"] in ("switch", "select")
            ),
            None,
        )
    return treffer


def _ww_ladetemperatur(entitaeten: list[dict[str, Any]], fct_type: Any) -> str | None:
    """Die Temperatur der Einmalladung: am Namen, sonst an der Adresse `5/51`."""
    if kennung := kennung_suchen(entitaeten, EINMALLADUNG_TEMPERATUR, ("number",)):
        return kennung
    if fct_type not in WW_FREIGABE_TYPEN:
        return None
    treffer = next(
        (e for e in entitaeten if e.get("adresse") == "5/51" and e["bereich"] == "number"), None
    )
    return treffer["entity_id"] if treffer else None


def ausloeser_optionen(ausloeser: dict[str, Any] | None) -> dict[str, Any]:
    """Bei einer Auswahl Nein/Ja die Texte für Starten und Beenden."""
    if not ausloeser or ausloeser["bereich"] != "select":
        return {}
    ja, nein = _optionstexte(ausloeser, 1), _optionstexte(ausloeser, 0)
    return {"ein_option": ja[0], "aus_option": nein[0]} if ja and nein else {}


def warmwasser_bedienung(alle: list[dict[str, Any]], kreis: list[dict[str, Any]]) -> dict[str, Any]:
    """Alles, was die Taste „Warmwasser laden" über die Anlage wissen muss.

    **Eine Beschreibung für beide Tasten.** Übersicht und Steuerung bauen ihre
    Taste aus denselben Angaben. Zwei getrennte Fassungen hießen: Ladeschwelle,
    Betriebswahl oder Abbruch fehlen in einer davon, und dieselbe Ladung ließe
    sich in der einen Ansicht beenden und in der anderen nicht.

    Die Anlage trennt dabei dreierlei:

    * ``2/16`` „Freigabe starten" – Nein/Ja. Er bleibt auf Ja, solange die
      Ladung läuft, auch wenn eine Vorgabe auf Zeit die Betriebsart belegt.
    * ``3/50`` „Betriebswahl" – die dauerhafte Wahl.
    * ``2/9``  „Betriebsart" – was gerade läuft. Dort steht „Warmwasser
      Einmalladung", und dort steht auch „Urlaubsprogramm".
    """
    # Zustand nur aus dem Teil des Auslösers: Kessel und Puffer führen eine eigene „Betriebsart".
    art = eintrag_suchen(kreis, BETRIEBSART, ("sensor",), "operating_mode")
    wahl = eintrag_suchen(kreis, BETRIEBSWAHL, ("select",), "mode_selection")
    laedt = _optionstexte(art, *WARMWASSER_LAEDT_WERTE)
    return {
        "zustand_an": art["entity_id"] if art else None,
        "zustand_wenn": [*laedt, *(t for t in WARMWASSER_LAEDT if t not in laedt)],
        # Zweiter Beleg für „lädt gerade": die Ladepumpe. Die Betriebsart
        # allein genügt nicht – sie meldet je nach Baureihe andere Worte, und
        # an einem Kreis mit nur einem zulässigen Wert (`allowed: [0]`) meldet
        # sie den Ladezustand gar nicht.
        "zustand_pumpe": kennung_suchen(
            kreis, WARMWASSER_LADEPUMPE, ("binary_sensor",), "dhw_charge_pump"
        ),
        # Die Betriebswahl gehört zur Ladung dazu: Auf Standby ist der Kreis
        # abgeschaltet und nimmt den Auftrag nicht an, im Urlaubsprogramm
        # ebenso wenig. Nur dann wird auf WW-Betrieb umgeschaltet – und
        # hinterher genau auf den Wert zurück, der vorher stand.
        "betriebswahl": wahl["entity_id"] if wahl else None,
        "betriebswahl_aus": _wahlmuster(wahl, BETRIEBSWAHL_STANDBY_WERT, BETRIEBSWAHL_STANDBY),
        "betriebswahl_ww": _wahlmuster(wahl, BETRIEBSWAHL_WW_WERT, BETRIEBSWAHL_WW),
        "betriebswahl_zurueck": BETRIEBSWAHL_ZURUECK,
        # „Urlaubsprogramm" ist kein Eintrag der Betriebswahl (3/50 kennt ihn
        # nicht), sondern ein Zustand der Betriebsart. Erkennbar ist er nur
        # dort – deshalb ein eigenes Muster statt eines weiteren
        # Betriebswahl-Eintrags.
        "zustand_urlaub": BETRIEBSART_URLAUB,
        "titel_abbrechen": "Warmwasser laden abbrechen",
        **_ladeschwelle(
            kreis if erster(kreis, WARMWASSER_IST_KENNWERT, "dhw_temperature") else alle
        ),
    }


def kaminkehrer_bedienung(entitaeten: list[dict[str, Any]]) -> dict[str, Any]:
    """Die Leistung, mit der die Kaminkehrerfunktion fährt.

    Sie wird vor dem Auslösen abgefragt: Die Abgasmessung gilt für genau
    diesen Wert, und nachträglich verstellen hieße neu messen.
    """
    # Solange die Messung läuft, beendet ein Druck sie. Ohne die zweite
    # Beschriftung steht auf der Kachel weiter „Kaminkehrer".
    bedienung: dict[str, Any] = {
        "titel_abbrechen": "Kaminkehrer beenden",
        "frage_abbrechen": (
            "Der Kessel kehrt in den normalen Betrieb zurück. "
            "Eine laufende Abgasmessung gilt danach nicht mehr."
        ),
    }
    if leistung := kennung_suchen(entitaeten, KAMINKEHRER_LEISTUNG, ("number",)):
        bedienung["leistung"] = leistung
    # Die Laufzeit steht nur dann als Feld im Dialog, wenn die Anlage sie
    # schreiben lässt; sonst demotiert die Erkennung sie zum Sensor.
    if laufzeit := kennung_suchen(entitaeten, KAMINKEHRER_LAUFZEIT, ("number",)):
        bedienung["laufzeit"] = laufzeit
    return bedienung


def steuerung(anlage: dict[str, Any]) -> dict[str, Any]:
    """Der Reiter „Steuerung": alles, was man an der Anlage wirklich verstellt.

    Vorbild ist die Bedienung der Anlage selbst – Heizkreis, Warmwasser,
    Kessel. Was nur abgelesen wird, gehört in die Übersicht.
    """
    alle = [e for teil in anlage["teile"] for e in teil["entitaeten"]]

    heizkreise = []
    for teil in anlage["teile"]:
        thermostat = next((e for e in teil["entitaeten"] if e["bereich"] == "climate"), None)
        if thermostat is None:
            continue
        heizkreise.append(
            {
                # Die Gerätekennung überlebt eine erneute Erkennung und ist
                # damit der einzige Anker, an dem eine selbst gewählte
                # Anordnung diese Karte wiedererkennt.
                "id": teil["id"],
                "entity": thermostat["entity_id"],
                "titel": teil["name"],
                "betriebswahl": kennung_suchen(
                    teil["entitaeten"], BETRIEBSWAHL, ("select",), "mode_selection"
                ),
                "betriebswahl_hilfe": hilfe("Betriebswahl"),
                "programm": kennung_suchen(teil["entitaeten"], ZEITPROGRAMM, ("sensor",)),
                # Eco und Comfort schreiben dieselbe befristete Übersteuerung
                # wie das Bediengerät: Temperatur (3/4) und Dauer (2/10). Die
                # Anlage kennt nur einen Übersteuerungswert – ob er Eco oder
                # Comfort heißt, entscheidet sie daran, ob er unter oder über
                # dem Programmsollwert liegt.
                "uebersteuerung_temperatur": kennung_suchen(
                    teil["entitaeten"], UEBERSTEUERUNG_TEMPERATUR, ("number",)
                ),
                "uebersteuerung_dauer": kennung_suchen(
                    teil["entitaeten"], UEBERSTEUERUNG_DAUER, ("number",)
                ),
                "vorlauf": (
                    v["entity_id"]
                    if (
                        v := erster(
                            teil["entitaeten"], r"vorlauftemperatur ist", "flow_temperature"
                        )
                    )
                    else None
                ),
            }
        )

    warmwasser = None
    if bereitet_warmwasser(alle):
        ist = erster(alle, r"\bww[- ]temperatur aktueller|\bwarmwasser ist", "dhw_temperature")
        # Der Kreis, an dem das Warmwasser hängt – seine Betriebswahl ist die,
        # die für die Ladung umgeschaltet und hinterher wiederhergestellt wird.
        kreis = next(
            (
                teil["entitaeten"]
                for teil in anlage["teile"]
                if erster(teil["entitaeten"], WARMWASSER_IST_KENNWERT, "dhw_temperature")
                is not None
            ),
            alle,
        )
        # Die Ladung gehört zum Teil, der ihren Auslöser führt; dort stehen Betriebsart und Pumpe.
        ww_teil, ausloeser = next(
            ((t, a) for t in anlage["teile"] if (a := ww_ausloeser(t)) is not None), (None, None)
        )
        laden = ausloeser["entity_id"] if ausloeser else None
        if ww_teil is not None:
            kreis = ww_teil["entitaeten"]
        warmwasser = {
            "ist": ist["entity_id"] if ist else None,
            "soll": kennung_suchen(alle, WARMWASSER_SOLL),
            "laden": laden,
            # Die Temperatur der Einmalladung ist an der Anlage Teil derselben
            # Bedienung; ohne sie lädt man auf einen Wert, den man nicht sieht.
            "laden_temperatur": _ww_ladetemperatur(kreis, (ww_teil or {}).get("fct_type")),
            # Die Einschalthysterese: wie weit die Temperatur unter den
            # Sollwert fallen darf, bevor nachgeladen wird. Sie entscheidet
            # mit, ob ein Ladeauftrag überhaupt angenommen wird – deshalb
            # gehört sie neben die Taste und nicht in die Serviceebene.
            "hysterese": kennung_suchen(kreis, WARMWASSER_HYSTERESE_MUSTER, ("number",)),
            # Was die Anlage gerade tut – daran hängt die Rückmeldung.
            "betriebsart": kennung_suchen(kreis, BETRIEBSART, ("sensor",), "operating_mode"),
            "programm": kennung_suchen(kreis, namensmuster(r"ww[- ].*programm"), ("sensor",)),
            # **Dieselbe Taste wie in der Übersicht.** Beschreibung, Ladeschwelle
            # und Abbruch kommen aus einer Quelle; die Ansicht baut daraus nur
            # noch die Schaltfläche.
            "taste": (
                {
                    "entity": laden,
                    "titel": "Warmwasser laden",
                    "symbol": "mdi:water-boiler",
                    "frage": rueckfrage("WW Einmalladung"),
                    "hilfe": hilfe("Einmalladung"),
                    **warmwasser_bedienung(alle, kreis),
                    **ausloeser_optionen(ausloeser),
                }
                if laden
                else None
            ),
        }

    kessel = []
    for teil in anlage["teile"]:
        for muster, beschriftung, symbol, schluessel in KESSEL_BEDIENUNG:
            treffer = eintrag_suchen(
                teil["entitaeten"],
                namensmuster(muster),
                ("switch", "button", "select"),
                *schluessel,
            )
            if treffer is not None:
                eintrag = {
                    "entity": treffer["entity_id"],
                    "titel": beschriftung,
                    "symbol": symbol,
                    "frage": rueckfrage(mustername(treffer)),
                    "hilfe": hilfe(mustername(treffer)) or hilfe(beschriftung),
                }
                if _passt(mustername(treffer), KAMINKEHRER):
                    eintrag.update(kaminkehrer_bedienung(teil["entitaeten"]))
                kessel.append(eintrag)

    # Lagerraumbefüllung: anfordern und dann ablesen, ob freigegeben ist.
    # Ohne die Anforderungstaste hat die Karte keinen Zweck.
    lagerraum = None
    if (anfordern := kennung_suchen(alle, LAGERRAUM_ANFORDERN, ("switch", "button"))) is not None:
        lagerraum = {
            "anfordern": anfordern,
            "titel_abbrechen": "Befüllung beenden",
            "frage_abbrechen": (
                "Erst beenden, wenn die Befüllung abgeschlossen ist. "
                "Das Rührwerk steht danach still."
            ),
            "frage": rueckfrage("Lagerraumbefüllung anfordern"),
            "hilfe": HILFE_KARTEN.get("Lagerraum befüllen", ""),
            "zeilen": [
                {"entity": treffer["entity_id"], "titel": beschriftung}
                for muster, beschriftung, schluessel in LAGERRAUM_ZEILEN
                if (treffer := erster(alle, muster, *schluessel)) is not None
            ],
        }

    return {
        "heizkreise": heizkreise,
        "warmwasser": warmwasser,
        "kessel": kessel,
        "lagerraum": lagerraum,
    }
