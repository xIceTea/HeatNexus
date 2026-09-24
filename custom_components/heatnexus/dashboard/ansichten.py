"""Die Ansichten des Dashboards: Übersicht, Anlage, Wartung, Auswertung, je Anlagenteil."""

from __future__ import annotations

from typing import Any

from ..const import KARTE_ELEMENT
from ..schema import anlagenschema
from ..schema import passt as _passt
from ..schema import traegt as _traegt
from .anlagen import skala, trifft, voller_name, vorrang
from .muster import (
    BEDIENBAR,
    RUNDINSTRUMENT,
    UEBERSICHT_MAX,
    VERLAUF,
    VERLAUF_MAX,
    VERLAUF_SCHLUESSEL,
    WARTUNG_RESTLAUFZEIT,
    WARTUNG_RESTLAUFZEIT_SCHLUESSEL,
    WARTUNG_WEITERE,
    WARTUNG_WEITERE_SCHLUESSEL,
    ZUSTAND,
    ZUSTAND_SCHLUESSEL,
    rueckfrage,
)


# ---------------------------------------------------------------------------
# Karten
# ---------------------------------------------------------------------------
def kachel(eintrag: dict[str, Any], rundinstrument: bool = False) -> dict[str, Any]:
    """Passende Karte für eine Entität."""
    if eintrag["bereich"] == "climate":
        return {"type": "thermostat", "entity": eintrag["entity_id"]}
    if rundinstrument:
        # Die Adresse zuerst, der Name als Rückfall – wie überall sonst.
        zeilen = [z for z in RUNDINSTRUMENT if _traegt(eintrag, z[1])] or [
            z for z in RUNDINSTRUMENT if _passt(eintrag.get("name") or "", (z[0],))
        ]
        if zeilen:
            return {
                "type": "gauge",
                "entity": eintrag["entity_id"],
                "name": eintrag["name"],
                "needle": True,
                **zeilen[0][2],
            }
    karte: dict[str, Any] = {
        "type": "tile",
        "entity": eintrag["entity_id"],
        "name": eintrag["name"],
    }
    if (frage := rueckfrage(eintrag["name"])) and (
        aktion := _schaltaktion(eintrag["bereich"], eintrag["entity_id"])
    ):
        # Nur das Symbol schaltet; ein Tippen auf die Kachel öffnet weiterhin
        # die Detailansicht und braucht keine Rückfrage.
        karte["icon_tap_action"] = {**aktion, "confirmation": {"text": frage}}
    return karte


def _schaltaktion(bereich: str, entity_id: str) -> dict[str, Any] | None:
    """Die Aktion, die das Symbol einer Kachel auslöst."""
    if bereich == "switch":
        return {"action": "toggle"}
    if bereich == "button":
        return {
            "action": "perform-action",
            "perform_action": "button.press",
            "target": {"entity_id": entity_id},
        }
    return None


def _ueberschrift(titel: str, symbol: str | None = None, stil: str = "title") -> dict[str, Any]:
    karte: dict[str, Any] = {"type": "heading", "heading": titel, "heading_style": stil}
    if symbol:
        karte["icon"] = symbol
    return karte


def abschnitt(
    titel: str,
    karten: list[dict[str, Any]],
    symbol: str | None = None,
    stil: str = "title",
    spanne: int = 0,
) -> list[dict[str, Any]]:
    """Ein Abschnitt mit Überschrift – oder gar keiner, wenn nichts drin ist.

    ``spanne`` gibt dem Abschnitt mehrere Spalten der Ansicht. Das Schaubild
    braucht sie: Neben dem Bild steht die Werteliste.
    """
    if not karten:
        return []
    grid: dict[str, Any] = {"type": "grid", "cards": [_ueberschrift(titel, symbol, stil), *karten]}
    if spanne > 1:
        grid["column_span"] = spanne
    return [grid]


def meldungskarte(eintrag: dict[str, Any]) -> dict[str, Any]:
    """Je Störung Art, Code und Text, darunter die Abhilfe; sonst der Zustand."""
    entitaet = eintrag["entity_id"]
    inhalt = (
        f"{{% set m = state_attr('{entitaet}', 'meldungen') %}}"
        "{% if m %}{% for e in m %}**{{ e.kind }} {{ e.code }}: {{ e.text }}**"
        "{% if e.info %}  \n{{ e.info }}{% endif %}\n\n{% endfor %}"
        f"{{% else %}}{{{{ states('{entitaet}') }}}}{{% endif %}}"
    )
    return {"type": "markdown", "title": eintrag["name"], "content": inhalt}


def _ansicht(
    titel: str, pfad: str, symbol: str, abschnitte: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "title": titel,
        "path": pfad,
        "icon": symbol,
        "type": "sections",
        "max_columns": 3,
        "sections": abschnitte,
    }


# ---------------------------------------------------------------------------
# Ansichten
# ---------------------------------------------------------------------------
def uebersicht(anlagen: list[dict[str, Any]]) -> dict[str, Any]:
    """Erste Ansicht: je Anlagenteil die wichtigsten Werte."""
    abschnitte: list[dict[str, Any]] = []
    for anlage in anlagen:
        for teil in anlage["teile"]:
            messwerte = [
                e
                for e in teil["entitaeten"]
                if e["kategorie"] is None
                and e["hat_wert"]
                and e["bereich"] not in ("button", "time", "date")
            ]
            messwerte.sort(key=lambda e: (vorrang(e), e["name"]))
            abschnitte += abschnitt(
                voller_name(anlage, teil),
                [kachel(e, rundinstrument=True) for e in messwerte[:UEBERSICHT_MAX]],
                teil["symbol"],
            )

    meldungen = [
        e
        for anlage in anlagen
        for teil in anlage["teile"]
        for e in teil["entitaeten"]
        if e["kategorie"] == "diagnostic" and "klartext" in e["name"].lower()
    ]
    abschnitte += abschnitt(
        "Meldungen", [meldungskarte(e) for e in meldungen], "mdi:alert-circle-outline"
    )

    return _ansicht("Übersicht", "uebersicht", "mdi:view-dashboard-outline", abschnitte)


def _zustandswerte(anlage: dict[str, Any]) -> list[dict[str, Any]]:
    """Der Zustand einer Anlage in Kurzform – Meldung, Betriebsphase, Außentemperatur."""
    return [
        e
        for teil in anlage["teile"]
        for e in teil["entitaeten"]
        # Einsteller bleiben draußen: Ein Grenzwert der Serviceebene heißt
        # mitunter wie der Messwert, den er begrenzt.
        if e["hat_wert"] and e.get("kategorie") is None and trifft(e, ZUSTAND, *ZUSTAND_SCHLUESSEL)
    ]


def anlagenbild(anlagen: list[dict[str, Any]], als_karte: bool = False) -> dict[str, Any] | None:
    """Ansicht „Anlage": das Schaubild mit den Werten darauf.

    ``als_karte`` setzt die eigene Lovelace-Karte ein statt der fertigen
    Zeichnung: Sie lässt sich im Editor bearbeiten. Das mitgelieferte
    Dashboard bleibt bei der Zeichnung, die kein Modul im Browser braucht.
    """
    abschnitte: list[dict[str, Any]] = []
    for anlage in anlagen:
        zustand = _zustandswerte(anlage)
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
            if zustand:
                karte["zusatzwerte"] = [e["entity_id"] for e in zustand]
            abschnitte += abschnitt(
                anlage["name"] or "Anlage", [karte], "mdi:sitemap-outline", spanne=2
            )
            continue

        bild = anlagenschema(
            anlage["teile"],
            anlage.get("kesselart"),
            modulpumpe=anlage.get("modulpumpe", False),
        )
        if bild is None:
            continue
        abschnitte += abschnitt(anlage["name"] or "Anlage", [bild], "mdi:sitemap-outline")
        abschnitte += abschnitt(
            "Zustand", [kachel(e) for e in zustand], "mdi:information-outline", stil="subtitle"
        )

    if not abschnitte:
        return None
    return _ansicht("Anlage", "anlage", "mdi:sitemap-outline", abschnitte)


def wartung(anlagen: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Restlaufzeiten, Zähler und Brennstoff – alles, was Arbeit ankündigt."""
    abschnitte: list[dict[str, Any]] = []
    for anlage in anlagen:
        for teil in anlage["teile"]:
            restlaufzeit = [
                e
                for e in teil["entitaeten"]
                if e["hat_wert"]
                and trifft(e, WARTUNG_RESTLAUFZEIT, *WARTUNG_RESTLAUFZEIT_SCHLUESSEL)
            ]
            weitere = [
                e
                for e in teil["entitaeten"]
                if e["hat_wert"] and trifft(e, WARTUNG_WEITERE, *WARTUNG_WEITERE_SCHLUESSEL)
            ]
            if not restlaufzeit and not weitere:
                continue

            # Rundinstrument: Der Abstand zur Null ist auf einen Blick zu
            # sehen, eine Zahl allein sagt das nicht. Die Skala richtet sich
            # nach dem aktuellen Stand – die Wartungsintervalle der Anlagen
            # reichen von wenigen Dutzend bis über tausend Stunden.
            karten: list[dict[str, Any]] = [
                {
                    "type": "gauge",
                    "entity": e["entity_id"],
                    "name": e["name"].replace("Laufzeit bis ", ""),
                    "needle": True,
                    "min": 0,
                    "max": skala(e["wert"]),
                    # Absteigend gelesen: unter 20 h gelb, unter 5 h rot.
                    "severity": {"green": 20, "yellow": 5, "red": 0},
                }
                for e in restlaufzeit
            ]
            karten += [kachel(e) for e in weitere]
            abschnitte += abschnitt(voller_name(anlage, teil), karten, "mdi:wrench-clock")

    if not abschnitte:
        return None
    return _ansicht("Wartung", "wartung", "mdi:wrench-clock", abschnitte)


def auswertung(anlagen: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Verläufe und Zählerstände über die Zeit."""
    abschnitte: list[dict[str, Any]] = []

    # Zähler: Home Assistant führt für total_increasing eine Langzeitstatistik.
    # Damit lässt sich der Zuwachs eines Tages/Monats direkt anzeigen – ohne
    # Hilfsentität und ohne eigene Automation.
    zaehler = [
        (anlage, teil, e)
        for anlage in anlagen
        for teil in anlage["teile"]
        for e in teil["entitaeten"]
        if e["state_class"] == "total_increasing"
    ]
    for zeitraum, beschriftung in (("day", "heute"), ("month", "dieser Monat")):
        karten = [
            {
                "type": "statistic",
                "entity": e["entity_id"],
                "name": f"{e['name']} {beschriftung}",
                "stat_type": "change",
                "period": {"calendar": {"period": zeitraum}},
            }
            for _anlage, _teil, e in zaehler
        ]
        abschnitte += abschnitt(f"Zähler – {beschriftung}", karten, "mdi:counter", stil="subtitle")

    for anlage in anlagen:
        for teil in anlage["teile"]:
            verlauf = [
                e
                for e in teil["entitaeten"]
                if e["hat_wert"]
                and e["bereich"] == "sensor"
                and trifft(e, VERLAUF, *VERLAUF_SCHLUESSEL)
            ]
            if not verlauf:
                continue
            abschnitte += abschnitt(
                voller_name(anlage, teil),
                [
                    {
                        "type": "history-graph",
                        "hours_to_show": 48,
                        "entities": [
                            {"entity": e["entity_id"], "name": e["name"]}
                            for e in verlauf[:VERLAUF_MAX]
                        ],
                    }
                ],
                teil["symbol"],
            )

    if not abschnitte:
        return None
    return _ansicht("Auswertung", "auswertung", "mdi:chart-line", abschnitte)


def geraeteansicht(
    anlage: dict[str, Any], teil: dict[str, Any], mehrdeutig: set[str]
) -> dict[str, Any]:
    """Eine Ansicht je Anlagenteil, nach Verwendungszweck gegliedert."""
    entitaeten = teil["entitaeten"]
    bedienbar = [e for e in entitaeten if e["bereich"] in BEDIENBAR]
    messwerte = [e for e in entitaeten if e not in bedienbar and e["kategorie"] is None]
    einstellungen = [e for e in entitaeten if e not in bedienbar and e["kategorie"] == "config"]
    diagnose = [e for e in entitaeten if e["kategorie"] == "diagnostic"]

    titel = voller_name(anlage, teil) if teil["name"] in mehrdeutig else teil["name"]
    return _ansicht(
        titel,
        f"teil-{teil['id'][:8]}",
        teil["symbol"],
        [
            *abschnitt("Bedienung", [kachel(e) for e in bedienbar], "mdi:tune"),
            *abschnitt("Messwerte", [kachel(e) for e in messwerte], "mdi:gauge"),
            *abschnitt("Einstellungen", [kachel(e) for e in einstellungen], "mdi:cog-outline"),
            *abschnitt("Diagnose", [kachel(e) for e in diagnose], "mdi:stethoscope"),
        ],
    )
