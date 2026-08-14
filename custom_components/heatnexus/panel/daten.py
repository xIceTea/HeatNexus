"""Die Aufteilung, die die Oberfläche darstellt.

**Hier entsteht die Struktur, nicht im Browser.** Python sucht die Entitäten
zusammen und legt sie als fertiges Gebilde ab; die Datei im Browser stellt es
nur dar und holt sich die aktuellen Werte aus ``hass.states``. Damit bleibt die
gesamte Gerätekenntnis an einer Stelle, und im Browser liegt nichts, was bei
einer neuen Anlage angepasst werden müsste.

Woran ein Datenpunkt erkannt wird, steht in :mod:`.muster`; was er bedeutet, in
:mod:`.hilfe`.
"""

from __future__ import annotations

import contextlib
import re
from typing import Any

from ..const import FCT_BUFFER, FCT_ZSP
from ..dashboard import (
    WARTUNG_RESTLAUFZEIT,
    WARTUNG_RESTLAUFZEIT_SCHLUESSEL,
    WARTUNG_WEITERE,
    WARTUNG_WEITERE_SCHLUESSEL,
    _muster,
    _passt,
    _trifft,
    rueckfrage,
)
from ..device_db import get_layers
from ..schema import anlagenschema, modul_in_betrieb
from .hilfe import HILFE_KARTEN, KARTE_BEDINGUNG, hilfe
from .muster import (
    AUSSENTEMPERATUR,
    BETRIEBSART,
    BETRIEBSART_URLAUB,
    BETRIEBSWAHL,
    BETRIEBSWAHL_STANDBY,
    BETRIEBSWAHL_WW,
    BETRIEBSWAHL_ZURUECK,
    EINMALLADUNG,
    EINMALLADUNG_TEMPERATUR,
    KENNWERT,
    KENNWERT_JE_FCT,
    KESSEL_BEDIENUNG,
    LAGERRAUM_ANFORDERN,
    LAGERRAUM_ZEILEN,
    SCHNELLZUGRIFF,
    STATUS,
    VERLAUF,
    VERLAUF_MAX,
    VERLAUF_SCHLUESSEL,
    WARMWASSER,
    WARMWASSER_ABSTAND,
    WARMWASSER_HYSTERESE,
    WARMWASSER_HYSTERESE_MUSTER,
    WARMWASSER_IST,
    WARMWASSER_IST_KENNWERT,
    WARMWASSER_KREIS,
    WARMWASSER_LADEPUMPE,
    WARMWASSER_LAEDT,
    WARMWASSER_MAX,
    WARMWASSER_SCHLUESSEL,
    WARMWASSER_SOLL,
    WARTUNG_BRENNSTOFF,
    WARTUNG_BRENNSTOFF_SCHLUESSEL,
    ZEITPROGRAMM,
    ZIRKULATION_IST_KENNWERT,
    ZIRKULATIONSPROGRAMM,
    ZIRKULATIONSPUMPE,
    Zeile,
)


def _erster(
    entitaeten: list[dict[str, Any]], muster: str, *schluessel: str
) -> dict[str, Any] | None:
    """Erste passende Entität; eine mit Wert hat Vorrang.

    Ein vorhandener Wert darf keine Bedingung sein: Beim ersten Aufbau ist die
    Anlage noch nicht fertig eingelesen. Was jetzt noch leer ist, bekommt
    trotzdem seine Zeile und füllt sich mit dem nächsten Abruf.

    Sind kanonische Schlüssel angegeben, zählen sie zuerst; das Muster bleibt
    der Rückfall (siehe `dashboard._trifft`).
    """
    regex = re.compile(muster, re.IGNORECASE)
    treffer = [e for e in entitaeten if _trifft(e, (regex,), *schluessel)]
    if not treffer:
        return None
    return next((e for e in treffer if e.get("hat_wert")), treffer[0])


def _zeilen(entitaeten: list[dict[str, Any]], vorlage: tuple[Zeile, ...]) -> list[dict[str, str]]:
    """Aus einer Mustervorlage die vorhandenen Entitäten als Zeilen."""
    zeilen = []
    for muster, beschriftung, symbol, schluessel in vorlage:
        if (treffer := _erster(entitaeten, muster, *schluessel)) is not None:
            zeilen.append(
                {
                    "entity": treffer["entity_id"],
                    "titel": beschriftung,
                    "symbol": symbol,
                }
            )
    return zeilen


def _bereitet_warmwasser(entitaeten: list[dict[str, Any]]) -> bool:
    """Prüfen, ob diese Anlage überhaupt Warmwasser bereitet.

    Zwei Belege lässt die Anlage zu: eine gemessene Warmwassertemperatur oder
    einen gemeldeten Warmwasserkreis ungleich null. Solange der Vollabzug noch
    läuft, hat der Istwert womöglich noch keinen Wert – vorhanden sein reicht
    deshalb, ein Wert ist nicht nötig.
    """
    for eintrag in entitaeten:
        if _trifft(eintrag, WARMWASSER_IST, "dhw_temperature"):
            return True
        if _trifft(eintrag, WARMWASSER_KREIS, "dhw_circuit") and (eintrag.get("wert") or 0) != 0:
            return True
    return False


def _warmwasser(entitaeten: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Zeilen der Warmwasserkarte – leer, wo es kein Warmwasser gibt."""
    if not _bereitet_warmwasser(entitaeten):
        return []
    return [
        {"entity": e["entity_id"], "titel": e["name"]}
        for e in entitaeten
        if e["kategorie"] is None
        and e["bereich"] != "climate"
        and _trifft(e, WARMWASSER, *WARMWASSER_SCHLUESSEL)
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
    ist = _erster(entitaeten, WARMWASSER_IST_KENNWERT, "dhw_temperature")
    soll = _kennung(entitaeten, EINMALLADUNG_TEMPERATUR, ("number", "sensor")) or _kennung(
        entitaeten, WARMWASSER_SOLL, ("number", "sensor"), "dhw_temperature_target"
    )
    abstand = WARMWASSER_ABSTAND
    if (hysterese := _erster(entitaeten, WARMWASSER_HYSTERESE)) is not None:
        with contextlib.suppress(TypeError, ValueError):
            if (gemeldet := hysterese.get("wert")) is not None:
                abstand = float(gemeldet)
    return {
        "ist": ist["entity_id"] if ist else None,
        "soll": soll,
        "abstand": abstand,
    }


def _warmwasser_bedienung(
    alle: list[dict[str, Any]], kreis: list[dict[str, Any]]
) -> dict[str, Any]:
    """Alles, was die Taste „Warmwasser laden" über die Anlage wissen muss.

    **Eine Beschreibung für beide Tasten.** Übersicht und Steuerung bauen ihre
    Taste aus denselben Angaben. Zwei getrennte Fassungen hießen: Ladeschwelle,
    Betriebswahl oder Abbruch fehlen in einer davon, und dieselbe Ladung ließe
    sich in der einen Ansicht beenden und in der anderen nicht.

    Die Anlage trennt dabei dreierlei:

    * ``2/16`` „Freigabe starten" – ein Auslöser. Er fällt zurück, sobald der
      Auftrag angenommen ist, und taugt deshalb nicht als Anzeige.
    * ``3/50`` „Betriebswahl" – die dauerhafte Wahl.
    * ``2/9``  „Betriebsart" – was gerade läuft. Dort steht „Warmwasser
      Einmalladung", und dort steht auch „Urlaubsprogramm".
    """
    return {
        "zustand_an": _kennung(alle, BETRIEBSART, ("sensor",), "operating_mode"),
        "zustand_wenn": list(WARMWASSER_LAEDT),
        # Zweiter Beleg für „lädt gerade": die Ladepumpe. Die Betriebsart
        # allein genügt nicht – sie meldet je nach Baureihe andere Worte, und
        # an einem Kreis mit nur einem zulässigen Wert (`allowed: [0]`) meldet
        # sie den Ladezustand gar nicht.
        "zustand_pumpe": _kennung(
            alle, WARMWASSER_LADEPUMPE, ("binary_sensor",), "dhw_charge_pump"
        ),
        # Die Betriebswahl gehört zur Ladung dazu: Auf Standby ist der Kreis
        # abgeschaltet und nimmt den Auftrag nicht an, im Urlaubsprogramm
        # ebenso wenig. Nur dann wird auf WW-Betrieb umgeschaltet – und
        # hinterher genau auf den Wert zurück, der vorher stand.
        "betriebswahl": _kennung(kreis, BETRIEBSWAHL, ("select",), "mode_selection"),
        "betriebswahl_aus": BETRIEBSWAHL_STANDBY,
        "betriebswahl_ww": BETRIEBSWAHL_WW,
        "betriebswahl_zurueck": BETRIEBSWAHL_ZURUECK,
        # „Urlaubsprogramm" ist kein Eintrag der Betriebswahl (3/50 kennt ihn
        # nicht), sondern ein Zustand der Betriebsart. Erkennbar ist er nur
        # dort – deshalb ein eigenes Muster statt eines weiteren
        # Betriebswahl-Eintrags.
        "zustand_urlaub": BETRIEBSART_URLAUB,
        "titel_abbrechen": "Warmwasser laden abbrechen",
        **_ladeschwelle(alle),
    }


def _kennung(
    entitaeten: list[dict[str, Any]],
    muster: tuple,
    bereiche: tuple = (),
    *schluessel: str,
) -> str | None:
    """Entity-ID der ersten passenden Entität, optional auf Plattformen begrenzt.

    Sind kanonische Schlüssel angegeben, zählen sie zuerst; das Muster bleibt
    der Rückfall (siehe `dashboard._trifft`).
    """
    for eintrag in entitaeten:
        if bereiche and eintrag["bereich"] not in bereiche:
            continue
        if _trifft(eintrag, muster, *schluessel):
            return eintrag["entity_id"]
    return None


def _steuerung(anlage: dict[str, Any]) -> dict[str, Any]:
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
                "betriebswahl": _kennung(
                    teil["entitaeten"], BETRIEBSWAHL, ("select",), "mode_selection"
                ),
                "betriebswahl_hilfe": hilfe("Betriebswahl"),
                "programm": _kennung(teil["entitaeten"], ZEITPROGRAMM, ("sensor",)),
                # Eco und Comfort schreiben dieselbe befristete Übersteuerung
                # wie das Bediengerät: Temperatur (3/4) und Dauer (2/10). Die
                # Anlage kennt nur einen Übersteuerungswert – ob er Eco oder
                # Comfort heißt, entscheidet sie daran, ob er unter oder über
                # dem Programmsollwert liegt.
                "uebersteuerung_temperatur": _kennung(
                    teil["entitaeten"], _muster(r"^temperatur$"), ("number",)
                ),
                "uebersteuerung_dauer": _kennung(
                    teil["entitaeten"], _muster(r"^dauer$"), ("number",)
                ),
                "vorlauf": (
                    v["entity_id"]
                    if (
                        v := _erster(
                            teil["entitaeten"], r"vorlauftemperatur ist", "flow_temperature"
                        )
                    )
                    else None
                ),
            }
        )

    warmwasser = None
    if _bereitet_warmwasser(alle):
        ist = _erster(alle, r"\bww[- ]temperatur aktueller|\bwarmwasser ist", "dhw_temperature")
        # Der Kreis, an dem das Warmwasser hängt – seine Betriebswahl ist die,
        # die für die Ladung umgeschaltet und hinterher wiederhergestellt wird.
        kreis = next(
            (
                teil["entitaeten"]
                for teil in anlage["teile"]
                if _erster(teil["entitaeten"], WARMWASSER_IST_KENNWERT, "dhw_temperature")
                is not None
            ),
            alle,
        )
        laden = _kennung(alle, EINMALLADUNG, ("switch", "button"))
        warmwasser = {
            "ist": ist["entity_id"] if ist else None,
            "soll": _kennung(alle, WARMWASSER_SOLL),
            "laden": laden,
            # Die Temperatur der Einmalladung ist an der Anlage Teil derselben
            # Bedienung; ohne sie lädt man auf einen Wert, den man nicht sieht.
            "laden_temperatur": _kennung(alle, EINMALLADUNG_TEMPERATUR, ("number",)),
            # Die Einschalthysterese: wie weit die Temperatur unter den
            # Sollwert fallen darf, bevor nachgeladen wird. Sie entscheidet
            # mit, ob ein Ladeauftrag überhaupt angenommen wird – deshalb
            # gehört sie neben die Taste und nicht in die Serviceebene.
            "hysterese": _kennung(alle, WARMWASSER_HYSTERESE_MUSTER, ("number",)),
            # Was die Anlage gerade tut – daran hängt die Rückmeldung.
            "betriebsart": _kennung(alle, BETRIEBSART, ("sensor",)),
            "programm": _kennung(alle, _muster(r"ww[- ].*programm"), ("sensor",)),
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
                    **_warmwasser_bedienung(alle, kreis),
                }
                if laden
                else None
            ),
        }

    kessel = []
    for teil in anlage["teile"]:
        for muster, beschriftung, symbol, schluessel in KESSEL_BEDIENUNG:
            treffer = next(
                (
                    e
                    for e in teil["entitaeten"]
                    if e["bereich"] in ("switch", "button", "select")
                    and _trifft(e, _muster(muster), *schluessel)
                ),
                None,
            )
            if treffer is not None:
                kessel.append(
                    {
                        "entity": treffer["entity_id"],
                        "titel": beschriftung,
                        "symbol": symbol,
                        "frage": rueckfrage(treffer["name"]),
                        "hilfe": hilfe(treffer["name"]) or hilfe(beschriftung),
                    }
                )

    # Lagerraumbefüllung: anfordern und dann ablesen, ob freigegeben ist.
    # Ohne die Anforderungstaste hat die Karte keinen Zweck.
    lagerraum = None
    if (anfordern := _kennung(alle, LAGERRAUM_ANFORDERN, ("button",))) is not None:
        lagerraum = {
            "anfordern": anfordern,
            "frage": rueckfrage("Lagerraumbefüllung anfordern"),
            "hilfe": HILFE_KARTEN.get("Lagerraum befüllen", ""),
            "zeilen": [
                {"entity": treffer["entity_id"], "titel": beschriftung}
                for muster, beschriftung, schluessel in LAGERRAUM_ZEILEN
                if (treffer := _erster(alle, muster, *schluessel)) is not None
            ],
        }

    return {
        "heizkreise": heizkreise,
        "warmwasser": warmwasser,
        "kessel": kessel,
        "lagerraum": lagerraum,
    }


def _zeitprogramme(anlage: dict[str, Any]) -> list[dict[str, str]]:
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
            if eintrag["bereich"] != "sensor" or not _passt(eintrag["name"], ZEITPROGRAMM):
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
            if text := hilfe(eintrag["name"]):
                programm["hilfe"] = text
            if (wirkung := _wirkt_nur_wenn(eintrag, teil)) is not None:
                programm["wirkung"] = wirkung
            programme.append(programm)
    return programme


def _programmsymbol(eintrag: dict[str, Any], teil: dict[str, Any]) -> str | None:
    """Das Symbol einer Zeitprogramm-Karte.

    Dieselben Bilder wie in der Heizungsübersicht – aber nach dem, was das
    Programm steuert, nicht nach dem Anlagenteil, an dem sein Datenpunkt
    hängt. Warmwasser und Zirkulation sitzen beide am Heizkreis und trugen
    deshalb dessen Heizkörper.
    """
    name = eintrag.get("name") or ""
    if _passt(name, ZIRKULATIONSPROGRAMM) or _trifft(
        eintrag,
        ZIRKULATIONSPROGRAMM,
        "dhw_circulation_program_time",
        "dhw_circulation_program_temperature",
    ):
        return "mdi:reload"
    if _passt(name, WARMWASSER):
        return "mdi:water-boiler"
    return teil.get("symbol")


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
            and _trifft(e, BETRIEBSWAHL, "buffer_mode_selection")
        ),
        None,
    )
    if wahl is None:
        return None
    return {
        "entity": wahl["entity_id"],
        "muster": "zeitprogramm",
        "hinweis": "Wirkt erst, wenn die Betriebswahl auf „Auto mit Zeitprogramm“ steht.",
    }


def _wirkt_nur_wenn(programm: dict[str, Any], teil: dict[str, Any]) -> dict[str, str] | None:
    """Der Datenpunkt, an dem hängt, ob ein Programm überhaupt etwas bewirkt.

    **Die Anlage führt zwei Zirkulationsprogramme.** In der Herstellerdatei
    heißen sie wortgleich „WW-Zirkulationsprogramm"; auseinanderhalten lassen
    sie sich nur an der Adresse. `5/65` gilt, wenn die Zirkulationspumpe
    (`5/6`) auf **Zeitsteuerung** steht, `5/64` bei **Temperatursteuerung**.
    Ohne diese Unterscheidung standen zwei gleichnamige Karten nebeneinander,
    und keine sagte, welche gerade wirkt.

    Deshalb zweierlei: Das Programm der *anderen* Steuerungsart verschwindet
    (`verbergen_bei`), und was übrig bleibt, trägt einen Hinweis, solange die
    Pumpe auf keiner der beiden steht – aus, nach Impuls oder durchlaufend.
    Versteckt wird also nur, was nachweislich eine andere Art betrifft; bei
    „Aus" bleiben beide sichtbar, damit man sein Programm vorbereiten kann,
    bevor man die Steuerung umstellt.
    """
    if not _passt(programm["name"], ZIRKULATIONSPROGRAMM):
        # Kein Zirkulationsprogramm – am Puffer entscheidet stattdessen seine
        # eigene Betriebswahl, ob das Programm greift.
        return _puffer_wirkung(teil) if teil.get("fct_type") == FCT_BUFFER else None
    pumpe = next(
        (
            e
            for e in teil["entitaeten"]
            if e["bereich"] in ("select", "sensor")
            # `5/6` ist der Modus, an dem hängt, ob das Programm überhaupt
            # greift – nicht `1/65`, der nur meldet, ob die Pumpe gerade läuft.
            and _trifft(e, ZIRKULATIONSPUMPE, "dhw_circulation_mode")
        ),
        None,
    )
    if pumpe is None:
        return None
    wirkung = {
        "entity": pumpe["entity_id"],
        "muster": "zeitsteuerung",
        "hinweis": "Wirkt erst, wenn die Zirkulationspumpe auf „Mit Zeitsteuerung“ steht.",
    }
    # Welche Art dieses Programm ist, sagt allein sein Schlüssel – der Name
    # taugt dafür nicht, beide heißen gleich.
    schluessel = programm.get("schluessel")
    if schluessel == "dhw_circulation_program_time":
        wirkung["verbergen_bei"] = "temperatursteuerung"
    elif schluessel == "dhw_circulation_program_temperature":
        wirkung["verbergen_bei"] = "zeitsteuerung"
        wirkung["muster"] = "temperatursteuerung"
        wirkung["hinweis"] = (
            "Wirkt erst, wenn die Zirkulationspumpe auf „Mit Temperatursteuerung“ steht."
        )
    return wirkung


def _wartung(anlage: dict[str, Any]) -> dict[str, Any]:
    """Der Reiter „Wartung": Restlaufzeiten, Brennstoff, Zählerstände."""
    alle = [e for teil in anlage["teile"] for e in teil["entitaeten"]]

    def zeilen(bedingung) -> list[dict[str, str]]:
        return [
            {"entity": e["entity_id"], "titel": e["name"]}
            for e in alle
            if e["kategorie"] is None and bedingung(e)
        ]

    return {
        "restlaufzeiten": zeilen(
            lambda e: _trifft(e, WARTUNG_RESTLAUFZEIT, *WARTUNG_RESTLAUFZEIT_SCHLUESSEL)
        ),
        "brennstoff": zeilen(
            lambda e: (
                _trifft(e, WARTUNG_BRENNSTOFF, *WARTUNG_BRENNSTOFF_SCHLUESSEL)
                and not _trifft(e, WARTUNG_RESTLAUFZEIT, *WARTUNG_RESTLAUFZEIT_SCHLUESSEL)
            )
        ),
        # Zählerstände erkennt man an der Statistikklasse, nicht am Namen.
        "zaehler": zeilen(lambda e: e.get("state_class") == "total_increasing"),
        "weitere": zeilen(
            lambda e: (
                _trifft(e, WARTUNG_WEITERE, *WARTUNG_WEITERE_SCHLUESSEL)
                and not _trifft(e, WARTUNG_RESTLAUFZEIT, *WARTUNG_RESTLAUFZEIT_SCHLUESSEL)
                and not _trifft(e, WARTUNG_BRENNSTOFF, *WARTUNG_BRENNSTOFF_SCHLUESSEL)
                and e.get("state_class") != "total_increasing"
            )
        ),
    }


def _hilfe_liste(anlage: dict[str, Any], nutzdaten: dict[str, Any]) -> list[dict[str, str]]:
    """Alle Erklärungen, die an dieser Anlage überhaupt greifen.

    Zwei Quellen: die Muster, die auf einen erkannten Datenpunkt passen, und
    die Kartentexte, deren Karte hier auch gebaut wird. Beides über dieselbe
    Zuordnung wie das Fragezeichen an der Karte – ein zweiter Weg liefe
    auseinander.
    """
    gefunden: dict[str, str] = {}
    for teil in anlage["teile"]:
        for eintrag in teil["entitaeten"]:
            name = eintrag["name"]
            if name not in gefunden and (text := hilfe(name)):
                gefunden[name] = text
    for titel, text in HILFE_KARTEN.items():
        feld = KARTE_BEDINGUNG.get(titel)
        if feld is not None and not nutzdaten.get(feld):
            continue
        gefunden.setdefault(titel, text)
    return [{"titel": titel, "text": gefunden[titel]} for titel in sorted(gefunden)]


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
    # Ein gefüllter Wert hat Vorrang – wie in `_erster`. Beim ersten Aufbau ist
    # erst ein Teil der Anlage gelesen; die Reihenfolge des Herstellers allein
    # zeigte dann eine leere Zeile, obwohl daneben schon ein Wert bereitstand.
    return next((e for e in treffer if e.get("hat_wert")), treffer[0])


def _anlage_daten(anlage: dict[str, Any], aussen_gewaehlt: str | None = None) -> dict[str, Any]:
    """Alles, was die Oberfläche für eine Anlage braucht."""
    alle = [e for teil in anlage["teile"] for e in teil["entitaeten"]]

    kennwerte = []
    for teil in anlage["teile"]:
        # **Ein Pumpen-/Relaismodul ohne Aufgabe kommt gar nicht vor.** Es
        # meldet zwar Sollwerte, schaltet aber nichts – im Schaubild fliegt es
        # längst heraus, in der Übersicht stand es weiter und zeigte eine
        # Anforderung, die es nie geben wird.
        if teil.get("fct_type") == FCT_ZSP and not modul_in_betrieb(teil["entitaeten"]):
            continue
        vorlage = KENNWERT_JE_FCT.get(teil.get("fct_type")) or KENNWERT
        gefunden = False
        for muster, beschriftung, symbol, schluessel in vorlage:
            if (treffer := _erster(teil["entitaeten"], muster, *schluessel)) is not None:
                gefunden = True
                eintrag = {
                    "entity": treffer["entity_id"],
                    "titel": teil["name"],
                    "untertitel": beschriftung,
                    "symbol": symbol,
                }
                # Ein Sollwert von null heißt: keine Anforderung. Statt „0 °C"
                # zu behaupten oder die Zeile verschwinden zu lassen, steht
                # dort dann ein Strich – das Anlagenteil bleibt sichtbar.
                #
                # Bewusst kein Klartext: Darunter steht bereits „Anforderung",
                # und ein „keine Anforderung / Anforderung" übereinander las
                # sich wie ein Fehler.
                if teil.get("fct_type") == FCT_ZSP:
                    eintrag["ersatz_unter_null"] = "–"
                kennwerte.append(eintrag)
                break

        if not gefunden and (treffer := _leitwert_aus_uebersicht(teil)) is not None:
            kennwerte.append(
                {
                    "entity": treffer["entity_id"],
                    "titel": teil["name"],
                    "untertitel": treffer["name"],
                    "symbol": "mdi:gauge",
                }
            )

        # Warmwasser und Zirkulation hängen als Datenpunkte am Heizkreis,
        # gehören in der Übersicht aber eigene Zeilen – man liest sie täglich.
        for muster, beschriftung, symbol, schluessel in (
            (WARMWASSER_IST_KENNWERT, "Warmwasser", "mdi:water-boiler", ("dhw_temperature",)),
            (
                ZIRKULATION_IST_KENNWERT,
                "Zirkulation",
                "mdi:reload",
                ("dhw_circulation_temperature",),
            ),
        ):
            if (treffer := _erster(teil["entitaeten"], muster, *schluessel)) is not None:
                kennwerte.append(
                    {
                        "entity": treffer["entity_id"],
                        "titel": teil["name"],
                        "untertitel": beschriftung,
                        "symbol": symbol,
                    }
                )

    heizkreise = []
    for teil in anlage["teile"]:
        thermostat = next(
            (e for e in teil["entitaeten"] if e["bereich"] == "climate"),
            None,
        )
        if thermostat is None:
            continue
        heizkreise.append(
            {
                "entity": thermostat["entity_id"],
                "titel": teil["name"],
                "vorlauf": (
                    v["entity_id"]
                    if (
                        v := _erster(
                            teil["entitaeten"], r"vorlauftemperatur ist", "flow_temperature"
                        )
                    )
                    else None
                ),
            }
        )

    warmwasser = _warmwasser(alle)

    stoerungen = [
        {"entity": e["entity_id"], "titel": e["name"]}
        for e in alle
        if e["kategorie"] == "diagnostic" and "klartext" in e["name"].lower()
    ]

    # Ohne Warmwasserbereitung hat auch die Taste „Warmwasser laden" nichts
    # verloren – der Datenpunkt existiert am Heizkreis trotzdem.
    hat_warmwasser = _bereitet_warmwasser(alle)
    schnellzugriff = []
    for teil in anlage["teile"]:
        for muster, beschriftung, symbol, schluessel in SCHNELLZUGRIFF:
            if not hat_warmwasser and _passt(beschriftung, WARMWASSER):
                continue
            treffer = next(
                (
                    e
                    for e in teil["entitaeten"]
                    if e["bereich"] in ("switch", "button", "select")
                    and _trifft(e, _muster(muster), *schluessel)
                ),
                None,
            )
            if treffer is not None:
                eintrag = {
                    "entity": treffer["entity_id"],
                    "titel": beschriftung,
                    "symbol": symbol,
                    "frage": rueckfrage(treffer["name"]),
                    "hilfe": hilfe(treffer["name"]) or hilfe(beschriftung),
                }
                if _passt(beschriftung, WARMWASSER):
                    eintrag.update(_warmwasser_bedienung(alle, teil["entitaeten"]))
                schnellzugriff.append(eintrag)

    bild = anlagenschema(anlage["teile"], anlage.get("kesselart"), anlage.get("kesselwert"))
    # **Jede Anlage behält ihren eigenen Messwert.** Die in den Optionen
    # gewählte Entität gilt nur für die Ansicht „Alle" – dort gibt es keine
    # einzelne Anlage, deren Fühler man nehmen könnte. Überschriebe sie jede
    # Anlage, zeigte eine plötzlich den Fühler der anderen.
    aussen = _kennung(alle, AUSSENTEMPERATUR, (), "outdoor_temperature") or aussen_gewaehlt
    nutzdaten = {
        # Die Anordnung der Karten wird je Anlage gespeichert. Ohne eigene
        # Kennung teilten sich zwei Anlagen eines Eintrags eine Reihenfolge.
        "id": anlage.get("id") or anlage["name"],
        "name": anlage["name"],
        # Erklärungen je Karte – im Browser als „?" neben der Überschrift.
        "hilfe": dict(HILFE_KARTEN),
        # Die Außentemperatur gilt für die ganze Anlage und steht deshalb oben,
        # nicht in der Liste der Anlagenteile.
        "aussentemperatur": aussen,
        "steuerung": _steuerung(anlage),
        "zeitprogramme": _zeitprogramme(anlage),
        "wartung": _wartung(anlage),
        "kennwerte": kennwerte,
        "status": _zeilen(alle, STATUS),
        "heizkreise": heizkreise,
        "warmwasser": warmwasser,
        "stoerungen": stoerungen,
        "schnellzugriff": schnellzugriff[:6],
        "verlauf": [e["entity_id"] for e in alle if _trifft(e, VERLAUF, *VERLAUF_SCHLUESSEL)][
            :VERLAUF_MAX
        ],
        # Alles, was sich sonst noch als Linie eignet – in der Ansicht
        # dazuwaehlbar.
        "verlauf_moeglich": [
            {"entity": e["entity_id"], "titel": e["name"]}
            for e in alle
            if e["kategorie"] is None and e["bereich"] == "sensor"
        ],
        # Alle Farbsätze. Welcher gilt, weiß erst der Browser – die Aufteilung
        # entsteht serverseitig und wird beim Umschalten des Erscheinungsbildes
        # nicht neu berechnet.
        "schema": bild["dark_mode_image"] if bild else None,
        "schema_hell": bild["image"] if bild else None,
        "schema_terrakotta": bild.get("terrakotta_image") if bild else None,
        "schema_werte": (
            [
                {
                    "entity": el["entity"],
                    "left": el["style"]["left"],
                    "top": el["style"]["top"],
                }
                for el in bild["elements"]
            ]
            if bild
            else []
        ),
        "schema_pumpen": bild.get("pumpen", []) if bild else [],
        # Bewegung im Schaubild: die Leitungen strömen, solange eine Pumpe
        # läuft, das Glutbett glimmt, solange der Kessel Leistung bringt.
        "schema_leitungen": bild.get("leitungen") if bild else None,
        "schema_brenner": bild.get("brenner", []) if bild else [],
        "schema_anforderung": bild.get("anforderung", []) if bild else [],
        "schema_mischer": bild.get("mischer", []) if bild else [],
        # Der Heizkörper färbt sich nach seiner Vorlauftemperatur.
        "schema_heizkoerper": bild.get("heizkoerper", []) if bild else [],
        # Die Schichtung des Puffers – oben und unten je nach Messwert.
        "schema_schichtung": bild.get("schichtung", []) if bild else [],
        "schema_lampen": bild.get("lampen", []) if bild else [],
        "schema_speicher": bild.get("speicher", []) if bild else [],
    }
    # Braucht die fertigen Nutzdaten: Ob eine Karte gebaut wird, steht erst
    # darin.
    nutzdaten["hilfe_liste"] = _hilfe_liste(anlage, nutzdaten)
    return nutzdaten
