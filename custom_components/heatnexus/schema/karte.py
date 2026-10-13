"""Die `picture-elements`-Karte und die Nutzdaten des Schaubilds je Anlage."""

from __future__ import annotations

from typing import Any

from . import ebenen
from .bauteile import bauteilnamen
from .farben import FARBABBILDUNGEN, FARBEN, THEMA_HELL, farben_umstellen
from .werte import (
    waehlbare_werte,
    zeichenbare_module,
)
from .zeichnung import (
    MODUL_BREITE,
    RAND,
    Buch,
    beschriftungen,
    datenadresse,
    schaubild_svg,
)


def anlagenschema(
    teile: list[dict[str, Any]],
    kesselwert: str | None = None,
    auswahl: dict[str, list[str]] | None = None,
    teile_aus: list[str] | tuple[str, ...] = (),
    zeichnungen: dict[str, str] | None = None,
    mit_mischer: bool = True,
    modulpumpe: bool = False,
    buch: Buch | None = None,
) -> dict[str, Any] | None:
    """Eine `picture-elements`-Karte für eine Anlage – oder nichts.

    Erwartet die Anlagenteile in der Form, die `dashboard.anlagen_lesen` liefert.
    Kesselzeichnung je Kessel: die Wahl am Gerät, sonst die erkannte Art.
    `buch` übersetzt die Namen im Bild; ohne bleibt es deutsch.

    **Beide Farbsätze werden mitgeliefert**, nicht einer nach Vorgabe: Das Bild
    steckt als `data:`-Adresse in einem `<img>` und erbt dort kein CSS, die
    Karte wird aber serverseitig gebaut – zu diesem Zeitpunkt ist das
    Erscheinungsbild des Betrachters nicht bekannt, und bei einem Umschalten
    gäbe es niemanden, der neu zeichnet. ``image`` trägt den hellen Satz,
    ``dark_mode_image`` den dunklen; genau so erwartet es die
    `picture-elements`-Karte. Die eigene Oberfläche wählt mit derselben Angabe
    (`panel/daten.py`).
    """
    module = zeichenbare_module(teile, kesselwert, auswahl, teile_aus, zeichnungen, modulpumpe)
    # Ein Bild aus lauter leeren Kästen hilft niemandem: Ein Anlagenteil muss messen.
    if not any(m["werte"] for m in module):
        return None

    svg, breite = schaubild_svg(module, mit_mischer, buch)

    rahmen = ebenen.Rahmen.aus_modulen(module, breite)
    elemente: list[dict[str, Any]] = []
    for platz, modul in enumerate(module):
        elemente += beschriftungen(RAND + platz * MODUL_BREITE, modul, breite)
    module_lampen, uebergabe = ebenen.pumpenmodule(module, rahmen)
    lampen = [*ebenen.lampen_der_erzeuger(module, rahmen), *module_lampen]

    return {
        "type": "picture-elements",
        "image": datenadresse(farben_umstellen(svg, THEMA_HELL)),
        "dark_mode_image": datenadresse(svg),
        # `picture-elements` kennt nur hell und dunkel; weitere Farbsätze stellen selbst um.
        "svg": svg,
        # Die Breite der Zeichnung. Damit rechnet die Oberfläche ihre
        # Überlagerungen auf denselben Maßstab wie das Bild.
        "breite": breite,
        "elements": elemente,
        # Welche Anlagenteile gezeichnet sind – für die Wahl der Zeichnung.
        "zeichenbar": [
            {"id": m.get("kennung") or m["titel"], "titel": m["titel"], "art": m["art"]}
            for m in module
        ],
        "leitungen": ebenen.leitungen(rahmen),
        # Die Pumpen liegen nicht im Bild: Ein Standbild kann sich nicht
        # drehen. Sie werden als eigene Marken darübergelegt.
        "pumpen": ebenen.pumpen(module, rahmen),
        # Ebenso das Glutbett der Wärmeerzeuger und die Mischerstellung.
        "brenner": ebenen.brenner(module, rahmen),
        "mischer": ebenen.mischer(module, rahmen),
        # Der Heizkörper, eingefärbt nach seiner Vorlauftemperatur.
        "heizkoerper": ebenen.heizkoerper(module, rahmen),
        # Die Schichtung des Puffers aus seinen beiden Fühlern.
        "schichtung": ebenen.schichtung(module, rahmen),
        # Ob der Puffer gerade beladen oder entleert wird.
        "speicher": ebenen.speicher(module, rahmen),
        # Die Lampen des Pumpen-/Relaismoduls, siehe ZSP_KLEMMEN.
        "lampen": lampen,
        # Wärme im Gehäuse, drehendes Laufrad und Abgabe nach außen, solange
        # das Modul Wärme anfordert.
        "uebergabe": uebergabe,
        # Wärme im Bauteil einer Quelle, solange sie liefert.
        "waerme": ebenen.waerme(module, rahmen),
    }


def schaubild_daten(
    anlagen: list[dict[str, Any]],
    auswahl: dict[str, list[str]] | None = None,
    teile_aus: list[str] | tuple[str, ...] = (),
    zeichnungen: dict[str, str] | None = None,
    mischer: bool = True,
    buecher: list[Buch] | None = None,
) -> list[dict[str, Any]]:
    """Schaubild je Anlage, wie die Lovelace-Karte es bekommt.

    Die Kennung entscheidet, welche Anlage eine Karte zeigt – nicht die Reihenfolge.
    `buecher` trägt je Anlage ihr Wörterbuch, in derselben Reihenfolge.
    """
    return [
        {
            "id": anlage.get("id") or anlage["name"],
            "name": anlage["name"],
            **schaubild_nutzdaten(anlage, auswahl, teile_aus, zeichnungen, mischer, buch),
        }
        for anlage, buch in zip(anlagen, buecher or [None] * len(anlagen), strict=True)
    ]


def schaubild_nutzdaten(
    anlage: dict[str, Any],
    auswahl: dict[str, list[str]] | None = None,
    teile_aus: list[str] | tuple[str, ...] = (),
    zeichnungen: dict[str, str] | None = None,
    mischer: bool = True,
    buch: Buch | None = None,
) -> dict[str, Any]:
    """Die Schaubild-Felder einer Anlage – Bilder, Lagen, Bewegung.

    Oberfläche und Karte lesen dieselben Felder; zwei Aufbauwege wären zwei Quellen.
    """
    bild = anlagenschema(
        anlage["teile"],
        kesselwert=anlage.get("kesselwert"),
        auswahl=auswahl,
        teile_aus=teile_aus,
        zeichnungen=zeichnungen,
        mit_mischer=mischer,
        modulpumpe=anlage.get("modulpumpe", False),
        buch=buch,
    )
    return {
        # Die Zeichnung geht **einmal** hinaus, dazu die Farbtabellen. Welcher
        # Satz gilt, weiß erst der Browser; er tauscht die Werte selbst.
        "schema_svg": bild["svg"] if bild else None,
        # Maßstab der Überlagerungen: Sie sollen mit dem Bild wachsen und
        # schrumpfen, nicht in Bildpunkten stehenbleiben.
        "schema_breite": bild.get("breite") if bild else None,
        # Was sich einstellen lässt: je Anlagenteil die Werte dieser Anlage.
        "schema_teile": waehlbare_werte(anlage["teile"], anlage.get("kesselwert")),
        # Die gezeichneten Anlagenteile und die Zeichnungen, die zur Wahl stehen.
        "schema_zeichenbar": bild.get("zeichenbar") if bild else [],
        "schema_bauteile": bauteilnamen(),
        # Die Grundfarben für die Überlagerungen – Mischer, Heizkörper,
        # Schichtung. Sie liegen über dem Bild und erben dessen Farben nicht.
        "schema_grundfarben": {
            rolle: FARBEN[rolle] for rolle in ("vorlauf", "ruecklauf", "warm", "kalt")
        },
        # Je Thema eine eigene Kopie: Eine flache reichte die Tabellen selbst
        # heraus, und wer sie änderte, änderte den Modulzustand mit.
        "schema_farben": (
            {thema: dict(werte) for thema, werte in FARBABBILDUNGEN.items()} if bild else {}
        ),
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
        "schema_mischer": bild.get("mischer", []) if bild else [],
        # Der Heizkörper färbt sich nach seiner Vorlauftemperatur.
        "schema_heizkoerper": bild.get("heizkoerper", []) if bild else [],
        # Die Schichtung des Puffers – oben und unten je nach Messwert.
        "schema_schichtung": bild.get("schichtung", []) if bild else [],
        "schema_lampen": bild.get("lampen", []) if bild else [],
        "schema_uebergabe": bild.get("uebergabe", []) if bild else [],
        "schema_waerme": bild.get("waerme", []) if bild else [],
        "schema_speicher": bild.get("speicher", []) if bild else [],
    }
