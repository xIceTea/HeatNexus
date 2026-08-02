#!/usr/bin/env python3
"""Datenpunkt-Referenz als Markdown aus der Geräte-Datenbank erzeugen.

Die Datenpunkte, ihre Namen und ihre Zuordnung zu den Bedienebenen liegen in
`custom_components/heatnexus/device_db.json`. Das ist eine erzeugte Datei und
für einen Menschen nicht lesbar. Diese Referenz macht daraus eine Tabelle je
Funktionstyp – nachschlagbar, ohne die Anlage zu befragen.

**Von Hand ändern hat keinen Zweck**: Der nächste Lauf überschreibt alles. Wer
einen Namen berichtigen will, ändert die Quelle und lässt beide Dateien neu
erzeugen:

    python tools/build_device_db.py
    python tools/build_datenpunkte_doku.py

Aufruf:

    python tools/build_datenpunkte_doku.py            # docs/ neu schreiben
    python tools/build_datenpunkte_doku.py --pruefen  # nur prüfen, ob aktuell
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

WURZEL = Path(__file__).resolve().parent.parent
DB = WURZEL / "custom_components" / "heatnexus" / "device_db.json"
FEHLERTEXTE = WURZEL / "custom_components" / "heatnexus" / "error_texts_de.json"
ZIEL_DATENPUNKTE = WURZEL / "docs" / "DATAPOINTS.md"
ZIEL_ENUMS = WURZEL / "docs" / "ENUMS.md"

# Was ein Funktionstyp ist, steht in keiner Datei – die Anlage liefert nur die
# Zahl. Die Zuordnung ist aus der Parameterliste des Herstellers abgeleitet:
# Welche Datenpunkte ein Typ führt, sagt, was er ist. Der Beleg je Zeile steht
# in `_intern/HERSTELLER-REFERENZ.md`.
FUNKTIONEN: dict[str, tuple[str, str]] = {
    "1": ("Heizkreis (Infinity PLUS)", "Heizkurve, Kühlgrenzen, Estrichprogramm"),
    "2": ("Warmwasser", "WW-Programm, Hygiene-Programm, Zirkulationspumpe"),
    "4": ("Kaskade / hydraulische Weiche", "Folgeschaltung, Zusatzkessel ZSK"),
    "5": ("Solar", "Kollektortemperatur, Kollektor spülen, Hydraulikschema"),
    "6": ("Kessel (Gas / Öl)", "Ionisationsstrom, Anlagendruck, Netzbetriebsstunden"),
    "7": ("Wärmepumpe", "COP, Silentmode, Betriebsstunden Heizen/Warmwasser"),
    "8": ("E-Heizung / Zusatzheizung", "Aktuelle Stufe, Betriebsstunden Stufe 1–3"),
    "9": ("Kessel (BioWIN)", "Laufzeit bis Reinigung, Brennstoffverbrauch, Sonden"),
    "10": ("Kessel (Automatik-/Zusatzkessel)", "Startverzögerung, O2-Signal"),
    "14": ("Heizkreis (UML / UMLZ)", "wie 1, ältere Baureihe, Warmwasser inbegriffen"),
    "15": ("Umschaltung", "Automatikkessel / Festbrennstoff / Puffer, Umschaltventil"),
    "16": ("Puffer (B-PLMi)", "TPE, TPA, TPT, Pufferladepumpe"),
    "20": ("ZSP Pumpen-/Relaismodul", "Pumpensteuerung, ext. Wärmeanforderung, Sammelstörung"),
    "21": ("Puffer", "Puffertemperatur oben/mitte/unten, Beladegrad"),
    "24": ("Pumpe Wärmeerzeuger / Schichtladung", "Rücklaufhochhaltung, Mischer"),
    "25": ("Kessel (PuroWIN)", "Hackgut und Pellets"),
    "26": ("Wärmepumpe (Energiemanagement)", "Stromtarife, PV-Eingang, SG Ready"),
    "27": ("Wärmepumpe", "Betriebsphase, Wärmemenge Heizen/Kühlen, E-Heizung"),
}

EBENEN = (
    ("info", "Info"),
    ("operate", "Betreiber"),
    ("service", "Service"),
    ("oem", "Werk"),
)


def _sortierschluessel(oid: str) -> tuple[int, int]:
    """OIDs als Zahlenpaar sortieren, damit 9/7 vor 10/1 steht."""
    try:
        gn, mn = oid.split("/", 1)
        return int(gn), int(mn)
    except ValueError:
        return 9999, 9999


def _tabelle(zeilen: list[tuple[str, ...]], kopf: tuple[str, ...]) -> list[str]:
    aus = ["| " + " | ".join(kopf) + " |", "|" + "---|" * len(kopf)]
    aus += ["| " + " | ".join(z) + " |" for z in zeilen]
    return aus


def _entwerten(text: str) -> str:
    """Zeichen entschärfen, die eine Markdown-Tabelle zerlegen."""
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def datenpunkte(db: dict) -> str:
    namen, ebenen = db["names"], db["layers"]
    zeilen: list[str] = [
        "# Datenpunkte",
        "",
        "**Erzeugt aus `device_db.json` – nicht von Hand ändern.**",
        "Neu erzeugen mit `python tools/build_datenpunkte_doku.py`.",
        "",
        "Die Integration erkennt Datenpunkte auf zwei Wegen: über kuratierte Tabellen",
        "in `const.py` (fester Name, Einheit, Kategorie, Symbol) und über diese",
        "Geräte-Datenbank, die die Bedienebenen je Funktionstyp beschreibt. Welche",
        "davon tatsächlich angelegt werden, entscheidet die Anlage: Nicht vorhandene",
        "werden entfernt, schreibgeschützte nur lesend angelegt.",
        "",
        "Eine OID ist `<gn>/<mn>`; die vollständige Adresse lautet",
        "`/1/<nodeId>/<fctId>/<gn>/<mn>/0`. Siehe [API.md](API.md).",
        "",
        "## Funktionstypen",
        "",
        "Die Anlage meldet je Funktion nur eine Zahl. Was sie bedeutet, ist aus der",
        "Parameterliste des Herstellers abgeleitet – welche Datenpunkte ein Typ führt,",
        "sagt, was er ist. **Nicht aus dem Namen raten**, den ein Installateur vergeben",
        "hat.",
        "",
    ]

    tabelle = []
    for fct in sorted(ebenen, key=lambda k: int(k)):
        name, merkmal = FUNKTIONEN.get(fct, ("unbekannt", "–"))
        anzahl = {k: len(ebenen[fct].get(k) or []) for k, _ in EBENEN}
        tabelle.append(
            (
                fct,
                name,
                merkmal,
                *[str(anzahl[k] or "–") for k, _ in EBENEN],
            )
        )
    zeilen += _tabelle(
        tabelle,
        ("fctType", "Funktion", "woran erkennbar", "Info", "Betreiber", "Service", "Werk"),
    )
    zeilen += [
        "",
        "`fctType -1` sind die internen Netzwerkvariablen (`NV's`); sie tragen keine",
        "Datenpunkte und werden übersprungen.",
        "",
        "## Bedienebenen",
        "",
        "- **Info** – Messwerte und Zustände, immer aktiv.",
        "- **Betreiber** – bedienbare Parameter, als Select, Number, Switch, Time oder",
        "  Date, aktiv.",
        "- **Service** – Fachparameter (Heizkurve, Grenzwerte, Estrichprogramm).",
        "  Angelegt, aber deaktiviert; je Entität in Home Assistant aktivierbar.",
        "- **Werk** – Herstellerparameter. Nur sichtbar, wenn ausdrücklich gewählt.",
        "",
        "## Datenpunkte je Funktionstyp",
        "",
    ]

    for fct in sorted(ebenen, key=lambda k: int(k)):
        name, _ = FUNKTIONEN.get(fct, ("unbekannt", "–"))
        zeilen += [f"### fctType {fct} – {name}", ""]
        je_oid: dict[str, list[str]] = {}
        for schluessel, beschriftung in EBENEN:
            for oid in ebenen[fct].get(schluessel) or []:
                je_oid.setdefault(str(oid), []).append(beschriftung)
        if not je_oid:
            zeilen += ["Keine Datenpunkte in der Datenbank.", ""]
            continue
        eintraege = [
            (f"`{oid}`", _entwerten(namen.get(oid, "–")), ", ".join(dict.fromkeys(stufen)))
            for oid, stufen in sorted(je_oid.items(), key=lambda x: _sortierschluessel(x[0]))
        ]
        zeilen += _tabelle(eintraege, ("OID", "Name", "Ebene"))
        zeilen.append("")

    return "\n".join(zeilen).rstrip() + "\n"


def enums(db: dict) -> str:
    tabellen = db["enums"]
    zeilen = [
        "# Auswahlwerte",
        "",
        "**Erzeugt aus `device_db.json` – nicht von Hand ändern.**",
        "Neu erzeugen mit `python tools/build_datenpunkte_doku.py`.",
        "",
        f"{len(tabellen)} Auswahltabellen. Sie sind **keine Listen**: Die Zahlen haben",
        "Lücken, weil nicht jede Anlage jeden Wert kennt. Zusätzlich meldet die Anlage",
        "im Feld `enum` ihrer Metadaten, welche Werte sie tatsächlich zulässt – erst",
        "das ergibt die Auswahl, die HeatNexus anbietet.",
        "",
        "Einige Tabellen pflegt `const.ENUMS` abweichend: Dort stehen an der Anlage",
        "geprüfte Texte, die den erzeugten vorgehen.",
        "",
    ]
    for oid in sorted(tabellen, key=_sortierschluessel):
        werte = tabellen[oid]
        zeilen += [f"### `{oid}`", ""]
        zeilen += _tabelle(
            [
                (str(k), _entwerten(str(v)))
                for k, v in sorted(werte.items(), key=lambda x: int(x[0]))
            ],
            ("Wert", "Bedeutung"),
        )
        zeilen.append("")
    return "\n".join(zeilen).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--pruefen",
        action="store_true",
        help="nur melden, ob die Dateien zum Stand der Datenbank passen",
    )
    args = parser.parse_args()

    db = json.loads(DB.read_text(encoding="utf-8"))
    erzeugt = {ZIEL_DATENPUNKTE: datenpunkte(db), ZIEL_ENUMS: enums(db)}

    veraltet = []
    for pfad, inhalt in erzeugt.items():
        vorhanden = pfad.read_text(encoding="utf-8") if pfad.exists() else ""
        if vorhanden == inhalt:
            continue
        veraltet.append(pfad)
        if not args.pruefen:
            pfad.write_text(inhalt, encoding="utf-8")

    if args.pruefen:
        if veraltet:
            for pfad in veraltet:
                print(f"veraltet: {pfad.relative_to(WURZEL)}", file=sys.stderr)
            print("Abhilfe: python tools/build_datenpunkte_doku.py", file=sys.stderr)
            return 1
        print("Datenpunkt-Referenz ist aktuell.")
        return 0

    for pfad in veraltet:
        print(f"geschrieben: {pfad.relative_to(WURZEL)}")
    if not veraltet:
        print("Nichts zu tun – beide Dateien waren aktuell.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
