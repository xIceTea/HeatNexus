"""Die Ergebnisse der Optimierung als Text für die Seitenleiste.

Eine Zeile je Hinweis mit Titel, Empfehlung und Grundlage, wie die Ergebniskachel sie zeigt.
Übersetzt wird über das übergebene Wörterbuch. Ohne Home Assistant testbar.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .optimierer import Hinweis

Uebersetzen = Callable[[str], str]

TITEL = {
    "heizkurve_frost": "Heizkurve bei Frost",
    "heizkurve_uebergang": "Heizkurve in der Übergangszeit",
    "heizkurve_parallel": "Heizkurve",
    "kurvenform": "Heizkurve",
    "sollwert_ausgleich": "Raumsollwert",
    "morgen_spaet": "Morgens zu spät warm",
    "morgen_frueh": "Morgens schon warm",
}
# Empfehlungen ohne Zahl; der Hinweis `steuerung_passt_an` empfiehlt nichts und fehlt in `TITEL`.
FESTE_EMPFEHLUNG = {
    "sollwert_ausgleich": "Heizkurve anpassen statt Sollwert",
    "kurvenform": "Kurvenform prüfen",
}
PARAMETERNAMEN = {
    "3/13": "Vorlauf bei Auslegung",
    "3/1": "Fußpunkt",
    "3/58": "Behaglichkeit",
    "3/6": "Vorhaltezeit",
}
SCHLUSS = "Die Automatik ändert diese Werte nicht."
MINUS = "−"


def _zahl(wert: float, punkt: bool, stellen: int | None = None) -> str:
    """Ganze Zahlen ohne Nachkommastelle, sonst eine; negativ mit echtem Minus."""
    if stellen is None:
        stellen = 0 if float(wert).is_integer() else 1
    text = f"{wert:.{stellen}f}"
    return (text if punkt else text.replace(".", ",")).replace("-", MINUS)


def _kelvin(wert: float | None, punkt: bool) -> str:
    """Abweichung mit Vorzeichen und einer Nachkommastelle."""
    if wert is None:
        return "–"
    v = round(wert, 1)
    zeichen = "+" if v > 0 else MINUS if v < 0 else "±"
    return f"{zeichen}{_zahl(abs(v), punkt, 1)} K"


def _mit(w: Uebersetzen, vorlage: str, **werte: object) -> str:
    """Die Vorlage übersetzen und ihre Platzhalter füllen."""
    text = w(vorlage)
    for name, wert in werte.items():
        text = text.replace("{" + name + "}", str(wert))
    return text


def _richtung(h: Hinweis, w: Uebersetzen, punkt: bool) -> str | None:
    """Empfehlungen ohne Parameterwechsel: Anschlag, Richtung, Morgen, Zeitprogramm."""
    if h.art == "heizkurve_parallel" and h.anschlag:
        return w("Behaglichkeit am Anschlag")
    if h.art == "heizkurve_parallel" and h.parameter is None and h.abweichung is not None:
        return w("Heizkurve anheben") if h.abweichung < 0 else w("Heizkurve absenken")
    if h.art == "morgen_frueh":
        if h.parameter == "3/6" and h.von is not None:
            return _mit(w, "Vorhaltezeit {von} min kürzer möglich", von=_zahl(h.von, punkt))
        return w("Absenkung vor Programmbeginn wirkt kaum")
    if h.parameter == "zeitprogramm" and h.nach is not None:
        return _mit(w, "Programmstart {minuten} min früher", minuten=_zahl(h.nach, punkt))
    return None


def _empfehlung(h: Hinweis, w: Uebersetzen, punkt: bool) -> str | None:
    """„Fußpunkt 45 → 43 °C“ oder ein fester Rat; ohne Zielwert `None`."""
    if h.art in FESTE_EMPFEHLUNG:
        return w(FESTE_EMPFEHLUNG[h.art])
    if (richtung := _richtung(h, w, punkt)) is not None:
        return richtung
    if h.von is None or h.nach is None or h.parameter not in PARAMETERNAMEN:
        return None
    werte = {
        "parameter": w(PARAMETERNAMEN[h.parameter]),
        "von": _zahl(h.von, punkt),
        "nach": _zahl(h.nach, punkt),
        "einheit": h.einheit or "",
    }
    return _mit(w, "{parameter} {von} → {nach} {einheit}", **werte).strip()


def _angaben(h: Hinweis, w: Uebersetzen, punkt: bool) -> list[str]:
    """Abweichung, gemessene Morgenzeit und die Zahl der Tage."""
    angaben = []
    if h.art == "sollwert_ausgleich" and h.von is not None:
        angaben.append(_mit(w, "Sollwert {wert} °C", wert=_zahl(h.von, punkt, 1)))
    elif h.art == "kurvenform":
        werte = {"uebergang": _kelvin(h.abweichung, punkt), "frost": _kelvin(h.frost, punkt)}
        angaben.append(_mit(w, "Übergang {uebergang} · Frost {frost}", **werte))
    elif h.abweichung is not None:
        angaben.append(_kelvin(h.abweichung, punkt))
    if h.minuten is not None:
        angaben.append(_mit(w, "Ziel nach {minuten} min", minuten=h.minuten))
    angaben.append(_mit(w, "{tage} Tage", tage=h.tage))
    return angaben


def zeile(h: Hinweis, w: Uebersetzen, punkt: bool = False) -> str | None:
    """Eine Zeile je Hinweis; ein Hinweis ohne Empfehlung wie `steuerung_passt_an` ergibt keine."""
    if (titel := TITEL.get(h.art)) is None:
        return None
    angaben = ", ".join(_angaben(h, w, punkt))
    if (empfehlung := _empfehlung(h, w, punkt)) is None:
        return f"{w(titel)}: {angaben}"
    return f"{w(titel)}: {empfehlung} ({angaben})"


def text(hinweise: Sequence[Hinweis], w: Uebersetzen, punkt: bool = False) -> str | None:
    """Die Hinweise als Liste mit Schlusssatz; ohne Empfehlung `None`."""
    zeilen = [f"- {z}" for h in hinweise if (z := zeile(h, w, punkt)) is not None]
    if not zeilen:
        return None
    return "\n".join(zeilen) + f"\n\n{w(SCHLUSS)}"
