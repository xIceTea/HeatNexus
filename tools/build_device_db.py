#!/usr/bin/env python3
"""Geräte-Datenbank aus den offiziellen Windhager-Parameterdateien erzeugen.

Die Dateien liegen öffentlich bereit und werden bei Bedarf geladen:

    de-parameters.json      Datenpunktnamen, Enum-Texte, Störungstexte
    de-oem-parameters.json  Datenpunktnamen der Werksebene
    parameterLayer.json     Zuordnung der Datenpunkte zu den Bedienebenen

Ergebnis sind zwei Dateien der Integration:

    custom_components/heatnexus/device_db.json
    custom_components/heatnexus/error_texts_de.json

Aufruf:

    python tools/build_device_db.py               # Dateien laden und erzeugen
    python tools/build_device_db.py --quelle ORDNER  # aus vorhandenen Dateien

**`--geraetetexte` nicht vergessen.** Gut die Hälfte der Datenpunktnamen steht
nicht in den Parameterdateien, sondern in `VarIdentTexte_de.xml` der Anlage –
ohne die Datei schrumpft die Datenbank von 2875 auf 1351 Namen, und der Rest
heißt dann nur noch „20-127". Die XML liegt auf jeder Anlage unter
`http://<IP>/res/xml/` und ist ohne Anmeldung lesbar; sie ist firmwareweit
gleich, ein Abzug von irgendeiner Anlage genügt also.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

BASIS = "https://connect-api.windhager.com/config"
DATEIEN = ("de-parameters.json", "de-oem-parameters.json", "parameterLayer.json")
EBENEN = ("overview", "info", "operate", "service", "oem")
REPO = Path(__file__).resolve().parent.parent
ZIEL = REPO / "custom_components" / "heatnexus"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def lade(name: str, quelle: Path | None) -> dict:
    """Eine Parameterdatei aus dem Ordner oder von Windhager laden."""
    if quelle:
        pfad = quelle / name
        print(f"  lese {pfad}")
        return json.loads(pfad.read_text(encoding="utf-8"))
    url = f"{BASIS}/{name}"
    print(f"  lade {url}")
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sammle_namen(parameter: dict, oem: dict, geraetetexte: Path | None = None) -> dict[str, str]:
    """Datenpunktnamen aus allen verfügbaren Listen zusammenführen.

    Reihenfolge nach Verlässlichkeit: die Bezeichnungen aus der Gerätedatei
    (falls vorhanden) füllen Lücken, die Werksliste ergänzt die Fachparameter,
    die reguläre Liste hat Vorrang – dort stehen die Namen, die auch am
    Bedienteil erscheinen.
    """
    namen: dict[str, str] = {}
    if geraetetexte and geraetetexte.exists():
        _uebernehmen(namen, lade_geraetetexte(geraetetexte))
    _uebernehmen(namen, oem.get("oids_oem", {}))
    _uebernehmen(namen, parameter.get("oids", {}))
    return namen


def _uebernehmen(namen: dict[str, str], quelle: dict) -> None:
    """Namen einer Liste übernehmen; leere Einträge übergehen.

    Die verlässlichere Liste hat Vorrang, aber nur dort, wo sie etwas sagt.
    Einige Adressen führt sie ohne Namen, während eine nachrangige Liste einen
    brauchbaren trägt.
    """
    for adresse, text in quelle.items():
        if isinstance(text, str) and text.strip():
            namen[adresse] = text.strip()


def lade_geraetetexte(pfad: Path) -> dict[str, str]:
    """Namen aus einer Gerätedatei (VarIdentTexte) einlesen.

    Die Steuerungen führen die Klartextnamen aller Datenpunkte als XML mit
    sich. Sie deckt auch Adressen ab, die in den Parameterlisten fehlen.
    """
    wurzel = ET.parse(pfad).getroot()
    namen: dict[str, str] = {}
    for gruppe in wurzel:
        for eintrag in gruppe:
            text = (eintrag.text or "").strip()
            if text:
                namen[f"{gruppe.get('id')}/{eintrag.get('id')}"] = text
    return namen


def _adressen(eintraege) -> list[str]:
    """Datenpunktadressen einer Ebene einsammeln.

    Eine Ebene enthält entweder einzelne Datenpunkte oder Gruppen mit einem
    Namen und den enthaltenen Datenpunkten.
    """
    gefunden: list[str] = []
    for eintrag in eintraege or []:
        if not isinstance(eintrag, dict):
            continue
        if eintrag.get("oid"):
            gefunden.append(eintrag["oid"])
        gefunden.extend(_adressen(eintrag.get("parameters")))
    return gefunden


def _bedingungen(eintraege) -> dict[str, list[dict]]:
    """Sichtbarkeitsbedingungen einsammeln: Adresse -> Bedingungen.

    Die Herstellerdatei vermerkt an einzelnen Datenpunkten, von welcher
    Einstellung sie abhängen. Ein Pumpenmodul ohne Pumpensteuerung führt seine
    Drehzahl zwar, meldet aber dauerhaft null.
    """
    ergebnis: dict[str, list[dict]] = {}
    for eintrag in eintraege or []:
        if not isinstance(eintrag, dict):
            continue
        adresse, bedingung = eintrag.get("oid"), eintrag.get("condition")
        if adresse and isinstance(bedingung, dict):
            for satz in _bedingungssaetze(bedingung):
                if satz not in ergebnis.setdefault(adresse, []):
                    ergebnis[adresse].append(satz)
        for adr, saetze in _bedingungen(eintrag.get("parameters")).items():
            for satz in saetze:
                if satz not in ergebnis.setdefault(adr, []):
                    ergebnis[adr].append(satz)
    return ergebnis


def _bedingungssaetze(bedingung: dict) -> list[dict]:
    """Eine Bedingung in Paare aus Adresse und erlaubten Werten auflösen.

    Zwei Formen kommen vor: eine einzelne Bedingung und `or-condition` mit
    einer Liste von Paaren. Die Oder-Form wird zu mehreren Sätzen, von denen
    einer zutreffen muss.
    """
    if bedingung.get("type") == "or-condition":
        saetze = []
        for teil in bedingung.get("conditions") or []:
            if isinstance(teil, list) and len(teil) == 2:
                saetze.append({"oid": teil[0], "values": [str(v) for v in teil[1]]})
            elif isinstance(teil, dict) and teil.get("oid"):
                saetze.append(
                    {"oid": teil["oid"], "values": [str(v) for v in teil.get("values") or []]}
                )
        return saetze
    if bedingung.get("oid"):
        return [
            {"oid": bedingung["oid"], "values": [str(v) for v in bedingung.get("values") or []]}
        ]
    return []


def _gruppen(eintraege, texte: dict) -> dict[str, list[str]]:
    """Benannte Gruppen einer Ebene: Klartext -> Datenpunkte."""
    ergebnis: dict[str, list[str]] = {}
    for eintrag in eintraege or []:
        if not isinstance(eintrag, dict) or not eintrag.get("group_name"):
            continue
        name = texte.get(eintrag["group_name"], eintrag["group_name"])
        adressen = _adressen(eintrag.get("parameters"))
        if adressen:
            ergebnis.setdefault(name, []).extend(
                a for a in adressen if a not in ergebnis.get(name, [])
            )
    return ergebnis


# Datenpunkte, die die Anlagen liefern, die aber in **keiner** Ebenenliste des
# Herstellers stehen. Ohne Eintrag zählen sie als Werksebene und sind damit
# unsichtbar, solange die niemand einschaltet – auch dann, wenn es sich um
# gewöhnliche Messwerte handelt.
#
# Jede Zeile ist an einer Anlage gemessen, nicht geraten. Beleg ist der
# vollständige Abzug beider Anlagen (`tools/heatnexus_probe.py`, PuroWIN mit
# 518 Datenpunkten); wo die Bedienungsanleitung denselben Parameter nennt,
# steht ihr Wertebereich daneben und stimmt mit dem der Anlage überein.
#
# Für Baureihen ohne eigenen Abzug gilt derselbe Maßstab: Beleg ist ein
# Datenpunktkatalog, der an einer laufenden Anlage dieser Baureihe erhoben
# wurde. Aus einer Anleitung abgeleitete oder aus einer anderen Baureihe
# übertragene Adressen zählen nicht.
#
# Neue Zeilen nur mit Messbeleg. Der Rest gehört auf die Werksebene.
UEBERSTEUERUNG: dict[str, dict[str, list[str]]] = {
    # Automatik-/Zusatzkessel (LogWIN)
    "10": {
        # Die Betriebswahl ist der Schalter, mit dem der Kessel überhaupt
        # bedient wird – schreibbar, und in keiner Ebenenliste des Herstellers.
        # Ohne Eintrag zählt sie als Werksebene und ist damit unsichtbar.
        "operate": ["9/75"],
        # Der Alarmcode gehört zur Diagnose und steht ebenfalls in keiner Ebene.
        "info": ["2/0"],
    },
    # Pelletskessel (BioWIN). Belegt durch einen Vollabzug einer laufenden
    # Anlage dieser Baureihe; sie meldet 64 Datenpunkte, die Ebenenlisten des
    # Herstellers erfassen davon siebzehn nicht.
    "9": {
        # Die Betriebswahl ist der Schalter, mit dem der Kessel bedient wird –
        # ohne Eintrag zählt sie als Werksebene und wäre unsichtbar.
        "operate": ["9/75"],
        # Ablesbares: Alarmcode, Restlaufzeit der Kaminkehrerfunktion und die
        # Aufforderung, die Aschetonne zu entleeren.
        "info": ["2/0", "9/90", "39/57"],
        # Einstellbares der Serviceebene: Kaminkehrerleistung, Brennstoffmenge
        # und die Soll-Drehzahl des Saugzuggebläses.
        "service": ["10/110", "23/99", "39/23"],
    },
    # Heizkreis (UML / UMLZ)
    "14": {
        # Frostschutzgrenzen – am Gerät die Ebene 119 „Frostschutzgrenzen".
        # Die Werte der Anlage (5 °C Raum, 2 °C außen, 10 °C Vorlauf,
        # 5 °C WW-Speicher) sind genau die der Anleitung.
        "service": ["3/0", "3/23", "7/45", "5/58"],
        # Warmwasser-Fachparameter. Anleitung: Hysterese EIN 1–20 K,
        # WW-Überhöhung 5–30 K, Mischerlaufzeit 60–300 s. Die Anlage meldet
        # 1…20, 5…30 und 1…6 min – dieselben Bereiche.
        "service_ww": ["5/0", "5/1", "7/13", "7/3", "5/3", "5/80"],
    },
    # Puffer (B-PLMi)
    "16": {
        # Zustände, die ins Schaubild gehören: Drehzahl der Wärmeerzeuger-
        # pumpe, Brenner an/aus, Transferpumpe an/aus, Sollwert des Puffers.
        "info": ["1/7", "1/15", "1/22", "1/100", "22/75"],
        "service": ["9/0", "5/1"],
    },
    # Kessel (PuroWIN)
    "25": {
        # „Kesseltype" der Infoebene – die Anlage meldet „PW 400". Sie kommt
        # über den object-Endpunkt als Text, nicht über lookup.
        "info": ["12/38"],
        # Messwerte und Parameter der Serviceebene laut Anleitung.
        "service": ["39/23", "39/100", "20/96"],
    },
}


def uebersteuern(ebenen: dict[str, dict]) -> int:
    """Gemessene Datenpunkte in die Ebene heben, in die sie gehören."""
    ergaenzt = 0
    for fct, je_ebene in UEBERSTEUERUNG.items():
        ziel = ebenen.setdefault(fct, {})
        for ebene, adressen in je_ebene.items():
            # Schlüssel wie „service_ww" sind nur zur Gliederung da.
            stufe = ebene.split("_")[0]
            vorhanden = ziel.setdefault(stufe, [])
            for adresse in adressen:
                if adresse not in vorhanden:
                    vorhanden.append(adresse)
                    ergaenzt += 1
    return ergaenzt


def sammle_ebenen(layer: dict, texte: dict) -> dict[str, dict]:
    """Ebenenlisten und Gruppennamen je Funktionstyp aufbauen."""
    ebenen: dict[str, dict] = {}
    for schluessel, inhalt in layer.items():
        geraet, _, fct = schluessel.partition("/")
        if not fct.isdigit():
            continue
        ziel = ebenen.setdefault(fct, {})
        for ebene in EBENEN:
            adressen = _adressen(inhalt.get(ebene))
            if adressen:
                vorhanden = ziel.setdefault(ebene, [])
                vorhanden.extend(a for a in adressen if a not in vorhanden)
            gruppen = _gruppen(inhalt.get(ebene), texte)
            if gruppen:
                ziel.setdefault("groups", {}).update(gruppen)
            for adresse, saetze in _bedingungen(inhalt.get(ebene)).items():
                vorhandene = ziel.setdefault("conditions", {}).setdefault(adresse, [])
                vorhandene.extend(s for s in saetze if s not in vorhandene)
        if geraet != "default":
            geraete = ziel.setdefault("devices", [])
            if geraet not in geraete:
                geraete.append(geraet)
    return ebenen


STOERUNG = re.compile(r"^EmStrId_(FE|AL|IN)(\d+)_(INFO_)?TEXT$")


def sammle_stoerungen(texte: dict) -> dict[str, dict[str, str]]:
    """Störungstexte nach Art und Code ordnen.

    Je Code gibt es zwei Einträge: die Kurzmeldung (…_TEXT) und die
    Handlungsempfehlung (…_INFO_TEXT).
    """
    ergebnis: dict[str, dict[str, str]] = {}
    for schluessel, text in texte.items():
        treffer = STOERUNG.match(schluessel)
        if not treffer or not isinstance(text, str) or not text.strip():
            continue
        art, code, ist_info = treffer.group(1), int(treffer.group(2)), bool(treffer.group(3))
        eintrag = ergebnis.setdefault(f"{art}{code}", {})
        eintrag["info" if ist_info else "text"] = text.strip()
    return ergebnis


def main() -> int:
    """Kommandozeile."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--quelle", type=Path, help="Ordner mit den Parameterdateien")
    parser.add_argument(
        "--geraetetexte",
        type=Path,
        help="XML einer Steuerung mit Datenpunktnamen (VarIdentTexte)",
    )
    parser.add_argument("--nur-anzeigen", action="store_true", help="nichts schreiben")
    args = parser.parse_args()

    print("Parameterdateien:")
    parameter, oem, layer = (lade(name, args.quelle) for name in DATEIEN)

    texte = parameter.get("emStrIds", {})
    namen = sammle_namen(parameter, oem, args.geraetetexte)
    enums = {k: v for k, v in parameter.get("enums", {}).items() if isinstance(v, dict)}
    ebenen = sammle_ebenen(layer, texte)
    ergaenzt = uebersteuern(ebenen)
    stoerungen = sammle_stoerungen(texte)

    print(f"\nDatenpunktnamen : {len(namen)}")
    print(f"davon ergänzt   : {ergaenzt} (an der Anlage gemessen, siehe UEBERSTEUERUNG)")
    print(f"Enum-Tabellen   : {len(enums)}")
    print(f"Funktionstypen  : {len(ebenen)}")
    print(f"Störungstexte   : {len(stoerungen)}")
    for fct in sorted(ebenen, key=int):
        zaehler = {e: len(ebenen[fct].get(e, [])) for e in EBENEN if ebenen[fct].get(e)}
        gruppen = len(ebenen[fct].get("groups", {}))
        zeile = ", ".join(f"{e} {n}" for e, n in zaehler.items())
        print(f"   fctType {fct:>3}: {zeile}" + (f", Gruppen {gruppen}" if gruppen else ""))

    if args.nur_anzeigen:
        return 0

    db = {"names": namen, "enums": enums, "layers": ebenen}
    (ZIEL / "device_db.json").write_text(
        json.dumps(db, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (ZIEL / "error_texts_de.json").write_text(
        json.dumps(stoerungen, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"\ngeschrieben: {ZIEL / 'device_db.json'}")
    print(f"geschrieben: {ZIEL / 'error_texts_de.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
