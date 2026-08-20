#!/usr/bin/env python3
"""Prüft neu hinzugekommene Changelog-Zeilen auf Wortlaut und Länge.

Geprüft wird nur, was eine Änderung hinzufügt — Bestand bleibt außen vor.
`--datei`, `--gestaged` und `--bereich` wählen die Quelle wie bei
`kommentarregel.py`.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys

MAX_WOERTER = 15
# Zwei Wörter gelten als dieselbe Wiederholung, wenn eines im anderen steckt
# und beide fast gleich lang sind. „eigene/eigenen" ja, „Systemuhr/Systemdatum"
# nein — deutsche Zusammensetzungen teilen sich oft den Anfang.
MIN_WORTLAENGE = 5
MAX_ABSTAND = 3

# Namen und Verweise zählen nicht als Prosa: In „X heißt jetzt Y" ist die
# Wiederholung gewollt, und eine Adresse ist kein Wort.
OHNE_NAMEN = re.compile(r"„[^„“\"]*[“\"]|`[^`]*`|\*[^*]+\*|\(?\[[^\]]*\]\([^)]*\)\)?")

# Funktionswörter wiederholen sich, ohne dass es holpert.
HAEUFIG = frozenset(
    (
        "nicht",
        "keine",
        "keinen",
        "keiner",
        "keines",
        "einem",
        "einen",
        "einer",
        "eines",
        "jedem",
        "jeden",
        "jeder",
        "jedes",
        "dieser",
        "diese",
        "diesem",
        "diesen",
        "welche",
        "welcher",
        "wurde",
        "wurden",
        "werden",
        "sollte",
        "könnte",
        "damit",
        "dabei",
        "dafür",
        "danach",
        "jetzt",
        "schon",
        "immer",
        "wieder",
        "allen",
        "aller",
        "ohne",
        "statt",
        "wenn",
        "oder",
        "auch",
        "noch",
        "beim",
    )
)

# Possessiv vor einem Hauptwort: „seine Restlaufzeit", „ihr Größenverhältnis".
# Technik besitzt nichts, und „ihre" liest sich zusätzlich als Anrede.
POSSESSIV = re.compile(
    r"\b(ihr|ihre|ihren|ihrem|ihrer|ihres|sein|seine|seinen|seinem|seiner|seines)"
    r"\s+[A-ZÄÖÜ]"
)

# Großgeschrieben mitten im Satz: die Anrede, die im Changelog nichts zu
# suchen hat.
ANREDE = re.compile(r"\S\s+\b(Sie|Ihnen|Ihre|Ihren|Ihrem|Ihrer)\b")

# Verben, die aus einem Gerät jemanden machen.
PERSONIFIZIEREND = re.compile(
    r"\b(kennt|kennen|will|wollen|möchte|möchten|bekommt|bekommen|weiß|wissen"
    r"|denkt|versteht|merkt|versucht|vergisst|erfährt)\b"
)

FETT_AM_ANFANG = re.compile(r"^\*\*")


@dataclass(frozen=True)
class Befund:
    """Eine Fundstelle: Datei, Zeile, Art, der beanstandete Text."""

    datei: str
    zeile: int
    art: str
    text: str

    def __str__(self) -> str:
        """Eine Zeile für Hook, CI und Kommandozeile."""
        return f"{self.datei}:{self.zeile} – {self.art}: „{self.text}“"


def eintragstext(zeile: str) -> str | None:
    """Der Text eines Listeneintrags, sonst None."""
    blank = zeile.strip()
    if not blank.startswith("- "):
        return None
    return blank[2:].strip()


def _woerter(text: str) -> list[str]:
    return [wort for wort in re.split(r"[\s/]+", text) if wort]


def ohne_namen(text: str) -> str:
    """Zitierte Namen, Code und Verweise entfernen."""
    return OHNE_NAMEN.sub(" ", text)


def doppeltes_wort(text: str) -> str | None:
    """Dasselbe Wort zweimal, auch mit anderer Endung."""
    blanke: list[str] = []
    for wort in _woerter(ohne_namen(text).lower()):
        blank = re.sub(r"[^a-zäöüß-]", "", wort)
        if len(blank) >= MIN_WORTLAENGE and blank not in HAEUFIG:
            blanke.append(blank)
    for i, eins in enumerate(blanke):
        for zwei in blanke[i + 1 :]:
            kurz, lang = sorted((eins, zwei), key=len)
            if lang.startswith(kurz) and len(lang) - len(kurz) <= MAX_ABSTAND:
                return f"{eins} / {zwei}"
    return None


def pruefe_eintrag(datei: str, nummer: int, text: str) -> list[Befund]:
    """Alle Regeln auf einen Listeneintrag anwenden."""
    befunde: list[Befund] = []

    def melde(art: str, stelle: str = "") -> None:
        befunde.append(Befund(datei, nummer, art, stelle or text))

    if treffer := POSSESSIV.search(text):
        melde("Possessivpronomen", treffer.group(0).strip())
    if treffer := ANREDE.search(text):
        melde("Anrede", treffer.group(1))
    if treffer := PERSONIFIZIEREND.search(text):
        melde("personifizierendes Verb", treffer.group(1))
    if FETT_AM_ANFANG.match(text):
        melde("Fettdruck am Zeilenanfang")

    anzahl = len(_woerter(ohne_namen(text)))
    if anzahl > MAX_WOERTER:
        melde(f"{anzahl} Wörter (erlaubt {MAX_WOERTER})")

    if paar := doppeltes_wort(text):
        melde("Wortwiederholung", paar)

    return befunde


def pruefe(datei: str, quelle: str, zeilen: set[int] | None = None) -> list[Befund]:
    """Die genannten Zeilen einer Changelog-Datei prüfen, sonst alle."""
    befunde: list[Befund] = []
    for nummer, zeile in enumerate(quelle.splitlines(), start=1):
        if zeilen is not None and nummer not in zeilen:
            continue
        if (text := eintragstext(zeile)) is not None:
            befunde += pruefe_eintrag(datei, nummer, text)
    return befunde


def neue_zeilen(diff: str) -> dict[str, set[int]]:
    """Aus einem Diff je Datei die Nummern der hinzugefügten Zeilen lesen."""
    je_datei: dict[str, set[int]] = {}
    datei = ""
    zeile = 0
    for text in diff.splitlines():
        if text.startswith("+++ b/"):
            datei = text[6:]
            continue
        if kopf := re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", text):
            zeile = int(kopf.group(1))
            continue
        if text.startswith("+++") or text.startswith("---"):
            continue
        if text.startswith("+"):
            je_datei.setdefault(datei, set()).add(zeile)
            zeile += 1
        elif not text.startswith("-"):
            zeile += 1
    return je_datei


def pruefe_diff(diff: str, wurzel: Path, nur: str | None = None) -> list[Befund]:
    """Jede Changelog-Datei eines Diffs prüfen, wahlweise nur eine davon."""
    befunde: list[Befund] = []
    for datei, zeilen in sorted(neue_zeilen(diff).items()):
        pfad = wurzel / datei
        if not datei.endswith("CHANGELOG.md") or not pfad.is_file():
            continue
        if nur and datei != nur:
            continue
        befunde += pruefe(datei, pfad.read_text(encoding="utf-8"), zeilen)
    return befunde


def _git(*argumente: str, wurzel: Path) -> str:
    ergebnis = subprocess.run(
        ["git", *argumente], cwd=wurzel, capture_output=True, text=True, encoding="utf-8"
    )
    return ergebnis.stdout or ""


def main(argv: list[str] | None = None) -> int:
    """Befunde ausgeben; 1 heißt: es gibt welche."""
    zerleger = argparse.ArgumentParser(description="Wortlaut neuer Changelog-Zeilen prüfen")
    zerleger.add_argument("--datei", help="nur diese Datei prüfen, repo-relativ")
    zerleger.add_argument("--gestaged", action="store_true", help="den vorgemerkten Stand prüfen")
    zerleger.add_argument("--bereich", help="einen Commit-Bereich prüfen, z.B. origin/main...HEAD")
    zerleger.add_argument("--wurzel", default=".", help="Wurzel des Repos")
    argumente = zerleger.parse_args(argv)

    wurzel = Path(argumente.wurzel).resolve()
    auswahl = "--cached" if argumente.gestaged else (argumente.bereich or "HEAD")
    diff = _git("diff", auswahl, "--unified=0", "-M", "--", "CHANGELOG.md", wurzel=wurzel)
    nur = Path(argumente.datei).as_posix() if argumente.datei else None
    befunde = pruefe_diff(diff, wurzel, nur=nur)
    for befund in befunde:
        print(befund)
    return 1 if befunde else 0


if __name__ == "__main__":
    sys.exit(main())
