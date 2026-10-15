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

from ..dashboard.anlagen import trifft
from ..helpers import mustername
from ..schema import schaubild_nutzdaten
from . import uebersicht
from .hilfe import HILFE_KARTEN, KARTE_BEDINGUNG, hilfe
from .muster import (
    AUSSENTEMPERATUR,
    STATUS,
    VERLAUF,
    VERLAUF_MAX,
    VERLAUF_SCHLUESSEL,
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
        "kennwerte": uebersicht.kennwerte(anlage),
        "status": zeilen_aus(alle, STATUS) + list(marken_status or []),
        "heizkreise": uebersicht.heizkreise(anlage),
        "warmwasser": warmwasser_zeilen(alle),
        "stoerungen": uebersicht.stoerungen(anlage),
        "stoerspeicher": next(
            (
                e["entity_id"]
                for e in anlage.get("steuerung_entitaeten", [])
                if e.get("uebersetzung") == "stoerspeicher"
            ),
            None,
        ),
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
