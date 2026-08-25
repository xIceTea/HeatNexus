"""Wann ein Vorgang als laufend gilt.

Gebraucht an drei Stellen, die dasselbe Problem haben: eine unabhängige
Wärmequelle, die Übergabepumpe der Nachbaranlage und die Frage, ob an einem
Pumpen-/Relaismodul gerade Wärme abgenommen wird. Keine davon meldet einen
fertigen Zustand; alle drei lassen sich aus Werten ableiten.

Das Modul kommt ohne Home Assistant aus: Es bekommt Werte als Zeichenketten
und gibt ein Ja oder Nein zurück. Die Entitäten dazu baut `binary_sensor.py`,
die Auswahl trifft der Optionsdialog.
"""

from __future__ import annotations

from typing import Any

ART_ZUSTAND = "zustand"
ART_SCHWELLE = "schwelle"
ART_DIFFERENZ = "differenz"
ARTEN = (ART_ZUSTAND, ART_SCHWELLE, ART_DIFFERENZ)

ARTEN_BESCHRIFTUNG = {
    ART_ZUSTAND: "Zustand (an/aus)",
    ART_SCHWELLE: "Schwelle (Wert über oder unter einer Grenze)",
    ART_DIFFERENZ: "Differenz zweier Fühler",
}

# Zustände, die Home Assistant für „kein Wert" vergibt, plus die üblichen
# Aus-Zustände. Sie gelten nie als laufend.
AUS_ZUSTAENDE = frozenset({"off", "unavailable", "unknown", "none", "", "0", "0.0", "aus", "nein"})


def _zahl(wert: Any) -> float | None:
    """Zeichenkette zu Zahl, oder nichts."""
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


def quellen(bedingung: dict[str, Any]) -> list[str]:
    """Die Entitäten, die diese Bedingung liest."""
    return [str(e) for e in (bedingung.get("quelle"), bedingung.get("gegen")) if e]


def vollstaendig(bedingung: dict[str, Any]) -> bool:
    """Ob die Bedingung genug Angaben hat, um ausgewertet zu werden."""
    if bedingung.get("art") not in ARTEN:
        return False
    if not bedingung.get("quelle"):
        return False
    if bedingung["art"] == ART_DIFFERENZ and not bedingung.get("gegen"):
        return False
    if bedingung["art"] in (ART_SCHWELLE, ART_DIFFERENZ):
        return _zahl(bedingung.get("ein")) is not None
    return True


def _mit_hysterese(wert: float, ein: float, aus: float | None, lief: bool) -> bool:
    """Ein- und Ausschaltschwelle getrennt auswerten.

    Liegt der Wert zwischen beiden, bleibt es beim bisherigen Ergebnis. Ohne
    diesen Zwischenbereich flattert die Anzeige an der Grenze.
    """
    if aus is None or aus == ein:
        return wert >= ein
    # Fällt die Ausschaltschwelle unter die Einschaltschwelle, zählt „darüber"
    # als laufend; liegt sie darüber, ist die Bedingung umgekehrt gemeint.
    if aus < ein:
        if wert >= ein:
            return True
        if wert <= aus:
            return False
        return lief
    if wert <= ein:
        return True
    if wert >= aus:
        return False
    return lief


def erfuellt(bedingung: dict[str, Any], werte: dict[str, Any], lief: bool = False) -> bool:
    """Ob die Bedingung mit diesen Werten zutrifft.

    ``werte`` ordnet jeder Entität ihren Zustand zu, ``lief`` ist das vorige
    Ergebnis. Fehlt ein Wert, lautet die Antwort Nein: Eine Abnahme zu
    behaupten, die niemand gemessen hat, wäre schlimmer als keine Anzeige.
    """
    if not vollstaendig(bedingung):
        return False
    art = bedingung["art"]
    roh = werte.get(str(bedingung["quelle"]))
    if roh is None:
        return False

    if art == ART_ZUSTAND:
        zustand = str(roh).strip().lower()
        if erlaubt := bedingung.get("zustaende"):
            return zustand in {str(z).strip().lower() for z in erlaubt}
        return zustand not in AUS_ZUSTAENDE

    wert = _zahl(roh)
    if wert is None:
        return False
    if art == ART_DIFFERENZ:
        gegen = _zahl(werte.get(str(bedingung["gegen"])))
        if gegen is None:
            return False
        wert -= gegen
    return _mit_hysterese(wert, float(bedingung["ein"]), _zahl(bedingung.get("aus")), lief)


def beschreibung(bedingung: dict[str, Any], namen: dict[str, str] | None = None) -> str:
    """Die Bedingung als Satz, für Optionsdialog und Hilfetext."""
    if not vollstaendig(bedingung):
        return "unvollständig"
    namen = namen or {}
    quelle = namen.get(str(bedingung["quelle"]), str(bedingung["quelle"]))
    art = bedingung["art"]
    if art == ART_ZUSTAND:
        if erlaubt := bedingung.get("zustaende"):
            return f"{quelle} steht auf {', '.join(str(z) for z in erlaubt)}"
        return f"{quelle} ist an"
    ein, aus = float(bedingung["ein"]), _zahl(bedingung.get("aus"))
    if art == ART_DIFFERENZ:
        gegen = namen.get(str(bedingung["gegen"]), str(bedingung["gegen"]))
        satz = f"{quelle} minus {gegen} erreicht {ein:g}"
    else:
        satz = f"{quelle} erreicht {ein:g}"
    if aus is not None and aus != ein:
        satz += f", endet bei {aus:g}"
    return satz
