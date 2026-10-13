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

from collections import Counter
from collections.abc import Callable
from typing import Any

from ..const import FCT_ZSP, QUELLEN_SYMBOLE
from ..dashboard.anlagen import trifft
from ..dashboard.muster import (
    namensmuster,
    rueckfrage,
)
from ..device_db import get_layers
from ..helpers import mustername
from ..schema import modul_in_betrieb, schaubild_nutzdaten
from ..schema import passt as _passt
from .hilfe import HILFE_KARTEN, KARTE_BEDINGUNG, hilfe
from .muster import (
    AUSSENTEMPERATUR,
    KAMINKEHRER,
    KENNWERT,
    KENNWERT_JE_FCT,
    KENNWERT_QUELLE,
    SCHNELLZUGRIFF,
    STATUS,
    STOERUNGSMELDER,
    VERLAUF,
    VERLAUF_MAX,
    VERLAUF_SCHLUESSEL,
    WARMWASSER,
    WARMWASSER_IST_KENNWERT,
    ZIRKULATION_IST_KENNWERT,
)
from .programme import zeitprogramme
from .steuerung import (
    ausloeser_optionen,
    bereitet_warmwasser,
    kaminkehrer_bedienung,
    steuerung,
    warmwasser_bedienung,
    warmwasser_zeilen,
    ww_ausloeser,
)
from .suche import eintrag_suchen, erster, kennung_suchen, zeilen_aus
from .wartung import wartung


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
            if name not in gefunden and (text := hilfe(mustername(eintrag))):
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
    # Ein gefüllter Wert hat Vorrang – wie in `erster`. Beim ersten Aufbau ist
    # erst ein Teil der Anlage gelesen; die Reihenfolge des Herstellers allein
    # zeigte dann eine leere Zeile, obwohl daneben schon ein Wert bereitstand.
    return next((e for e in treffer if e.get("hat_wert")), treffer[0])


def anlage_daten(
    anlage: dict[str, Any],
    aussen_gewaehlt: str | None = None,
    marken: list[dict[str, Any]] | None = None,
    marken_status: list[dict[str, str]] | None = None,
    buch: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Alles, was die Oberfläche für eine Anlage braucht.

    `marken` sind die Karten aus den Labels, die für genau diese Anlage
    gewählt sind; `buch` beschriftet das Schaubild in ihrer Sprache.
    """
    alle = [e for teil in anlage["teile"] for e in teil["entitaeten"]]

    kennwerte = []
    for teil in anlage["teile"]:
        # **Ein Pumpen-/Relaismodul ohne Aufgabe kommt gar nicht vor.** Es
        # meldet zwar Sollwerte, schaltet aber nichts – im Schaubild fliegt es
        # längst heraus, in der Übersicht stand es weiter und zeigte eine
        # Anforderung, die es nie geben wird.
        if teil.get("fct_type") == FCT_ZSP and not modul_in_betrieb(teil["entitaeten"]):
            continue
        # Eine Wärmequelle hat keinen Funktionstyp und kein Namensmuster der
        # Baureihe; ihre Zeile zeigt, ob sie gerade Wärme liefert.
        if (art := teil.get("art")) in QUELLEN_SYMBOLE:
            muster, beschriftung, _, schluessel = KENNWERT_QUELLE
            if (treffer := erster(teil["entitaeten"], muster, *schluessel)) is not None:
                kennwerte.append(
                    {
                        "entity": treffer["entity_id"],
                        "titel": teil["name"],
                        "untertitel": beschriftung,
                        "symbol": QUELLEN_SYMBOLE[art],
                    }
                )
            continue

        vorlage = KENNWERT_JE_FCT.get(teil.get("fct_type")) or KENNWERT
        gefunden = False
        for muster, beschriftung, symbol, schluessel in vorlage:
            if (treffer := erster(teil["entitaeten"], muster, *schluessel)) is not None:
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
        # Ist der Wert schon Leitwert eines eigenen Speichers, bleibt es bei einer Zeile.
        gelistet = {k["entity"] for k in kennwerte}
        for muster, beschriftung, symbol, schluessel in (
            (WARMWASSER_IST_KENNWERT, "Warmwasser", "mdi:water-boiler", ("dhw_temperature",)),
            (
                ZIRKULATION_IST_KENNWERT,
                "Zirkulation",
                "mdi:reload",
                ("dhw_circulation_temperature",),
            ),
        ):
            treffer = erster(teil["entitaeten"], muster, *schluessel)
            if treffer is not None and treffer["entity_id"] not in gelistet:
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
                        v := erster(
                            teil["entitaeten"], r"vorlauftemperatur ist", "flow_temperature"
                        )
                    )
                    else None
                ),
            }
        )

    warmwasser = warmwasser_zeilen(alle)

    # Der Klartext trägt den Text, der Ja/Nein-Sensor desselben Anlagenteils
    # sagt, ob etwas ansteht. Zwei Entitäten, eine Auskunft je Zweck.
    stoerungen = []
    for teil in anlage["teile"]:
        melder = kennung_suchen(teil["entitaeten"], STOERUNGSMELDER, ("binary_sensor",))
        stoerungen += [
            {"entity": e["entity_id"], "titel": e["name"], "melder": melder}
            for e in teil["entitaeten"]
            if e["kategorie"] == "diagnostic" and "klartext" in mustername(e).lower()
        ]

    # Ohne Warmwasserbereitung hat auch die Taste „Warmwasser laden" nichts
    # verloren – der Datenpunkt existiert am Heizkreis trotzdem.
    hat_warmwasser = bereitet_warmwasser(alle)
    schnellzugriff = []
    for teil in anlage["teile"]:
        for muster, beschriftung, symbol, schluessel in SCHNELLZUGRIFF:
            if not hat_warmwasser and _passt(beschriftung, WARMWASSER):
                continue
            treffer = ww_ausloeser(teil) if _passt(beschriftung, WARMWASSER) else None
            if treffer is None:
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
                if _passt(beschriftung, WARMWASSER):
                    eintrag.update(warmwasser_bedienung(alle, teil["entitaeten"]))
                    eintrag.update(ausloeser_optionen(treffer))
                if _passt(mustername(treffer), KAMINKEHRER):
                    eintrag.update(kaminkehrer_bedienung(teil["entitaeten"]))
                eintrag["anlagenteil"] = teil["name"]
                schnellzugriff.append(eintrag)
    # Den Anlagenteil nennt nur, wer sich sonst nicht unterscheiden ließe.
    titel = Counter(e["titel"] for e in schnellzugriff)
    for eintrag in schnellzugriff:
        if titel[eintrag["titel"]] == 1:
            del eintrag["anlagenteil"]

    # **Jede Anlage behält ihren eigenen Messwert.** Die in den Optionen
    # gewählte Entität gilt nur für die Ansicht „Alle" – dort gibt es keine
    # einzelne Anlage, deren Fühler man nehmen könnte. Überschriebe sie jede
    # Anlage, zeigte eine plötzlich den Fühler der anderen.
    aussen = (
        kennung_suchen(alle, AUSSENTEMPERATUR, ("sensor",), "outdoor_temperature")
        or aussen_gewaehlt
    )
    nutzdaten = {
        # Die Anordnung der Karten wird je Anlage gespeichert. Ohne eigene
        # Kennung teilten sich zwei Anlagen eines Eintrags eine Reihenfolge.
        "id": anlage.get("id") or anlage["name"],
        "name": anlage["name"],
        # Karten aus den Labels dieser Anlage. Die Auswahl gehört zur Anlage,
        # nicht zum Abzug als Ganzem.
        "marken": marken or [],
        # Erklärungen je Karte – im Browser als „?" neben der Überschrift.
        "hilfe": dict(HILFE_KARTEN),
        # Die Außentemperatur gilt für die ganze Anlage und steht deshalb oben,
        # nicht in der Liste der Anlagenteile.
        "aussentemperatur": aussen,
        "steuerung": steuerung(anlage),
        "zeitprogramme": zeitprogramme(anlage),
        "wartung": wartung(anlage),
        "kennwerte": kennwerte,
        "status": zeilen_aus(alle, STATUS) + list(marken_status or []),
        "heizkreise": heizkreise,
        "warmwasser": warmwasser,
        "stoerungen": stoerungen,
        "schnellzugriff": schnellzugriff[:6],
        # Nur Messwerte: Ein Einsteller trägt oft denselben Namen wie der
        # Wert, den er begrenzt, und gehört nicht als Linie in den Verlauf.
        "verlauf": [
            e["entity_id"]
            for e in alle
            if e["kategorie"] is None and trifft(e, VERLAUF, *VERLAUF_SCHLUESSEL)
        ][:VERLAUF_MAX],
        # Alles, was sich sonst noch als Linie eignet – in der Ansicht
        # dazuwaehlbar.
        "verlauf_moeglich": [
            {"entity": e["entity_id"], "titel": e["name"]}
            for e in alle
            if e["kategorie"] is None and e["bereich"] == "sensor"
        ],
        # Bilder, Lagen und Bewegung des Schaubilds, wie die Lovelace-Karte sie bekommt.
        **schaubild_nutzdaten(anlage, buch=buch),
    }
    # Braucht die fertigen Nutzdaten: Ob eine Karte gebaut wird, steht erst
    # darin.
    nutzdaten["hilfe_liste"] = _hilfe_liste(anlage, nutzdaten)
    return nutzdaten
