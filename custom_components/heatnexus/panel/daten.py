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
from ..schema import anlagenschema
from .hilfe import HILFE_KARTEN, hilfe
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

    Drei Werte, und der mittlere war bis 1.3.1 der falsche:

    * **Ist** – die gemessene Warmwassertemperatur.
    * **Soll** – die Temperatur, auf die die *Einmalladung* lädt (``5/51``,
      an der geprüften Anlage 65 °C). Verglichen wurde bisher mit dem
      gewöhnlichen Warmwasser-Sollwert (``1/4``, dort 49,5 °C). Bei 61 °C im
      Speicher meldete die Taste deshalb „schon 61 °C – erst ab 45 °C" und
      verweigerte eine Ladung, die die Anlage klaglos ausgeführt hätte. Der
      Abstand sah nach 16 K aus, war aber die Differenz der beiden Sollwerte.
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

    **Eine Beschreibung für beide Tasten.** Bis 1.3.1 baute die Übersicht ihre
    Taste aus diesen Angaben, die Steuerung dagegen aus einer eigenen, ärmeren
    Fassung: Dort fehlten Ladeschwelle, Betriebswahl und Abbruch, und dieselbe
    Ladung ließ sich in der einen Ansicht beenden und in der anderen nicht.

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
            }
            if text := hilfe(eintrag["name"]):
                programm["hilfe"] = text
            if (wirkung := _wirkt_nur_wenn(eintrag, teil["entitaeten"])) is not None:
                programm["wirkung"] = wirkung
            programme.append(programm)
    return programme


def _wirkt_nur_wenn(
    programm: dict[str, Any], geschwister: list[dict[str, Any]]
) -> dict[str, str] | None:
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
        return None
    pumpe = next(
        (
            e
            for e in geschwister
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


def _anlage_daten(anlage: dict[str, Any], aussen_gewaehlt: str | None = None) -> dict[str, Any]:
    """Alles, was die Oberfläche für eine Anlage braucht."""
    alle = [e for teil in anlage["teile"] for e in teil["entitaeten"]]

    kennwerte = []
    for teil in anlage["teile"]:
        vorlage = KENNWERT_JE_FCT.get(teil.get("fct_type")) or KENNWERT
        for muster, beschriftung, symbol, schluessel in vorlage:
            if (treffer := _erster(teil["entitaeten"], muster, *schluessel)) is not None:
                eintrag = {
                    "entity": treffer["entity_id"],
                    "titel": teil["name"],
                    "untertitel": beschriftung,
                    "symbol": symbol,
                }
                # Ein Sollwert von null heißt: keine Anforderung. Die Zeile
                # bleibt dann leer statt „0 °C" zu behaupten.
                if teil.get("fct_type") == 20:
                    eintrag["nur_ueber_null"] = True
                kennwerte.append(eintrag)
                break

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
    # einzelne Anlage, deren Fühler man nehmen könnte. Bis 1.2.0-beta.3
    # überschrieb die Auswahl jede Anlage, und das Heizhaus zeigte plötzlich
    # den Fühler des Wohnhauses.
    aussen = _kennung(alle, AUSSENTEMPERATUR, (), "outdoor_temperature") or aussen_gewaehlt
    return {
        # Die Anordnung der Karten wird je Anlage gespeichert. Ohne eigene
        # Kennung teilten sich Heizhaus und Wohnhaus eine Reihenfolge – wer
        # im Heizhaus etwas verschob, verschob es im Wohnhaus mit.
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
        # Beide Farbsätze. Welcher gilt, weiß erst der Browser – die Aufteilung
        # entsteht serverseitig und wird beim Umschalten des Erscheinungsbildes
        # nicht neu berechnet.
        "schema": bild["dark_mode_image"] if bild else None,
        "schema_hell": bild["image"] if bild else None,
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
