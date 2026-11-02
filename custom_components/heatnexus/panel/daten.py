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

from collections.abc import Callable
from typing import Any

from ..dashboard.anlagen import erzeuger_von, steuerungsentitaet, trifft
from ..dashboard.kesselzustand import kesselzustand
from ..geraete import STATUSZEILEN
from ..geraete.statuszeilen import EINZELN, GEMEINSAM, Statuszeile
from ..helpers import mustername
from ..schema import schaubild_nutzdaten
from . import uebersicht
from .hilfe import HILFE_KARTEN, KARTE_BEDINGUNG, hilfe
from .hybrid import hybrid
from .muster import (
    AUSSENTEMPERATUR,
    VERLAUF,
    VERLAUF_MAX,
    VERLAUF_SCHLUESSEL,
    Zeile,
)
from .programme import zeitprogramme
from .steuerung import (
    steuerung,
    warmwasser_zeilen,
)
from .suche import kennung_suchen, zeilen_aus
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


def status_vorlage(anlage: dict[str, Any]) -> tuple[Zeile, ...]:
    """Die Zeilen des Systemstatus mit höchstens einem Erzeuger."""
    return tuple((z.muster, z.titel, z.symbol, z.schluessel) for z in EINZELN if z.panel)


def _zeilen(entitaeten: list[dict[str, Any]], zeilen: list[Statuszeile]) -> list[dict[str, str]]:
    """Je Statuszeile der erste Treffer, mit dem Vorsatz für die Kopfzeile."""
    gefunden = []
    for z in zeilen:
        for treffer in zeilen_aus(entitaeten, ((z.muster, z.titel, z.symbol, z.schluessel),)):
            gefunden.append({**treffer, "vorsatz": z.vorsatz} if z.vorsatz else treffer)
    return gefunden


def systemstatus(
    anlage: dict[str, Any], marken_status: list[dict[str, str]] | None = None
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Die Zeilen des Systemstatus und, ab zwei Erzeugern, je Erzeuger Kopf und Zeilen.

    Ab zwei Erzeugern sucht jeder seine Zeilen nur unter seinen eigenen
    Entitäten; oben bleibt, was für die ganze Anlage gilt.
    """
    alle = [e for teil in anlage["teile"] for e in teil["entitaeten"]]
    marken = list(marken_status or [])
    erzeuger = erzeuger_von(anlage["teile"])
    if len(erzeuger) < 2:
        return zeilen_aus(alle, status_vorlage(anlage)) + marken, []
    bloecke = []
    for teil in erzeuger:
        zeilen = [z for z in STATUSZEILEN[teil["fct_type"]] if z.panel]
        bloecke.append(
            {
                "id": teil["id"],
                "name": teil["name"],
                "kopf": _zeilen(teil["entitaeten"], [z for z in zeilen if z.kopf]),
                "zeilen": _zeilen(teil["entitaeten"], [z for z in zeilen if not z.kopf]),
            }
        )
    return _zeilen(alle, [z for z in GEMEINSAM if z.panel]) + marken, bloecke


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

    # **Jede Anlage behält ihren eigenen Messwert.** Die in den Optionen
    # gewählte Entität gilt nur für die Ansicht „Alle" – dort gibt es keine
    # einzelne Anlage, deren Fühler man nehmen könnte. Überschriebe sie jede
    # Anlage, zeigte eine plötzlich den Fühler der anderen.
    aussen = (
        kennung_suchen(alle, AUSSENTEMPERATUR, ("sensor",), "outdoor_temperature")
        or aussen_gewaehlt
    )
    status, erzeuger = systemstatus(anlage, marken_status)
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
        # Karte „Hybridmanager“ und ihre Diagramme; ohne Hybridmanager `None`.
        "hybrid": hybrid(anlage),
        "kennwerte": uebersicht.kennwerte(anlage),
        "status": status,
        "erzeuger": erzeuger,
        "heizkreise": uebersicht.heizkreise(anlage),
        "warmwasser": warmwasser_zeilen(alle),
        "stoerungen": uebersicht.stoerungen(anlage),
        "kesselzustand": kesselzustand(anlage),
        "stoerspeicher": steuerungsentitaet(anlage, "stoerspeicher"),
        "anlagenzustand": steuerungsentitaet(anlage, "anlagenzustand"),
        "schnellzugriff": uebersicht.schnellzugriff(anlage, alle),
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
