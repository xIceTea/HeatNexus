"""Die Ergebnisse der Optimierung als Text, für die Kachel und die Seitenleiste.

Je Hinweis Titel, Empfehlung und Angaben; die Kachel zeigt sie als Block, die Seitenleiste
als Zeile. Übersetzt wird über das übergebene Wörterbuch. Ohne Home Assistant testbar.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from ..texte import fuellen
from .optimierer import Hinweis
from .stellgroessen import TABELLE
from .zahlen import kelvin, zahl

Uebersetzen = Callable[[str], str]

TITEL = {
    "heizkurve_frost": "Heizkurve bei Frost",
    "heizkurve_uebergang": "Heizkurve in der Übergangszeit",
    "heizkurve_parallel": "Heizkurve",
    "kurvenform": "Heizkurve",
    "steuerung_passt_an": "Heizkurve",
    "sollwert_ausgleich": "Raumsollwert",
    "morgen_spaet": "Morgens zu spät warm",
    "morgen_frueh": "Morgens schon warm",
}
# Empfehlungen ohne Zahl.
FESTE_EMPFEHLUNG = {
    "steuerung_passt_an": "Keine Empfehlung zur Kurve",
    "sollwert_ausgleich": "Heizkurve anpassen statt Sollwert",
    "kurvenform": "Kurvenform prüfen",
}
# Die Seitenleiste nennt nur Hinweise, aus denen sich etwas ändern lässt.
NICHT_MELDEN = frozenset({"steuerung_passt_an"})
SCHLUSS = "Die Automatik ändert diese Werte nicht."


def _mit(w: Uebersetzen, vorlage: str, **werte: object) -> str:
    return fuellen(w(vorlage), **werte)


def tag_monat(datum: str | None) -> str | None:
    """Ein ISO-Datum als „14.11.“."""
    teile = str(datum or "").split("-")
    return f"{teile[2]}.{teile[1]}." if len(teile) == 3 else None


def _richtung(h: Hinweis, w: Uebersetzen, punkt: bool) -> str | None:
    """Empfehlungen ohne Parameterwechsel: Anschlag, Richtung, Morgen, Zeitprogramm."""
    if h.art == "heizkurve_parallel" and h.anschlag:
        return w("Behaglichkeit am Anschlag")
    if h.art == "heizkurve_parallel" and h.parameter is None and h.abweichung is not None:
        return w("Heizkurve anheben") if h.abweichung < 0 else w("Heizkurve absenken")
    if h.art == "morgen_frueh":
        if h.parameter == "3/6" and h.von is not None:
            return _mit(w, "Vorhaltezeit {von} min kürzer möglich", von=zahl(h.von, punkt))
        if h.parameter == "thermostate":
            return w("Absenkung der Thermostate wirkt kaum")
        return w("Absenkung vor Programmbeginn wirkt kaum")
    if h.parameter == "zeitprogramm" and h.nach is not None:
        return _mit(w, "Programmstart {minuten} min früher", minuten=zahl(h.nach, punkt))
    if h.parameter == "thermostate" and h.nach is not None:
        return _mit(
            w, "Zeitsteuerung der Thermostate {minuten} min früher", minuten=zahl(h.nach, punkt)
        )
    return None


def _empfehlung(h: Hinweis, w: Uebersetzen, punkt: bool) -> str | None:
    """„Fußpunkt 45 → 43 °C“ oder ein fester Rat; ohne Zielwert `None`."""
    if h.art in FESTE_EMPFEHLUNG:
        return w(FESTE_EMPFEHLUNG[h.art])
    if (richtung := _richtung(h, w, punkt)) is not None:
        return richtung
    groesse = TABELLE.get(h.parameter or "")
    if h.von is None or h.nach is None or groesse is None or groesse.name is None:
        return None
    werte = {
        "parameter": w(groesse.name),
        "von": zahl(h.von, punkt),
        "nach": zahl(h.nach, punkt),
        "einheit": h.einheit or "",
    }
    return _mit(w, "{parameter} {von} → {nach} {einheit}", **werte).strip()


def _angaben(h: Hinweis, w: Uebersetzen, punkt: bool) -> list[str]:
    """Abweichung, gemessene Morgenzeit und die Zahl der Tage seit der letzten Änderung."""
    if h.art == "steuerung_passt_an":
        return [w("Anpassung durch die Steuerung aktiv")]
    angaben = []
    if h.art == "sollwert_ausgleich" and h.von is not None:
        angaben.append(_mit(w, "Sollwert {wert} °C", wert=zahl(h.von, punkt, 1)))
    elif h.art == "kurvenform":
        werte = {"uebergang": kelvin(h.abweichung, punkt), "frost": kelvin(h.frost, punkt)}
        angaben.append(_mit(w, "Übergang {uebergang} · Frost {frost}", **werte))
    elif h.abweichung is not None:
        angaben.append(kelvin(h.abweichung, punkt))
    if h.minuten is not None:
        angaben.append(_mit(w, "Ziel nach {minuten} min", minuten=h.minuten))
    if (seit := tag_monat(h.seit)) is not None:
        angaben.append(_mit(w, "{tage} Tage seit {seit}", tage=h.tage, seit=seit))
    else:
        angaben.append(_mit(w, "{tage} Tage", tage=h.tage))
    return angaben


def texte(h: Hinweis, w: Uebersetzen, punkt: bool = False) -> dict[str, Any] | None:
    """Titel, Empfehlung (ohne Zielwert `None`) und Angaben eines Hinweises; unbekannt `None`."""
    if (titel := TITEL.get(h.art)) is None:
        return None
    return {
        "titel": w(titel),
        "empfehlung": _empfehlung(h, w, punkt),
        "angaben": _angaben(h, w, punkt),
    }


def zeile(h: Hinweis, w: Uebersetzen, punkt: bool = False) -> str | None:
    """Eine Zeile der Seitenleiste; ein Hinweis ohne Empfehlung wie `steuerung_passt_an` ergibt keine."""
    if h.art in NICHT_MELDEN or (t := texte(h, w, punkt)) is None:
        return None
    angaben = ", ".join(t["angaben"])
    if t["empfehlung"] is None:
        return f"{t['titel']}: {angaben}"
    return f"{t['titel']}: {t['empfehlung']} ({angaben})"


def text(hinweise: Sequence[Hinweis], w: Uebersetzen, punkt: bool = False) -> str | None:
    """Die Hinweise als Liste mit Schlusssatz; ohne Empfehlung `None`."""
    zeilen = [f"- {z}" for h in hinweise if (z := zeile(h, w, punkt)) is not None]
    if not zeilen:
        return None
    return "\n".join(zeilen) + f"\n\n{w(SCHLUSS)}"


def parameterstand(
    stand: dict[str, dict[str, Any]], w: Uebersetzen, punkt: bool = False
) -> dict[str, dict[str, Any]]:
    """Der gelesene Stand je Parameter; mit eigenem Verlauf dazu die Zeile „Fußpunkt 45 °C“."""
    ergebnis = {}
    for name, eintrag in stand.items():
        groesse = TABELLE.get(name)
        if groesse is None or groesse.name is None or groesse.bezug != "eigen":
            ergebnis[name] = eintrag
            continue
        werte = {"parameter": w(groesse.name), "wert": zahl(eintrag["wert"], punkt)}
        zeile = _mit(w, "{parameter} {wert} {einheit}", **werte, einheit=groesse.einheit or "")
        if (seit := tag_monat(eintrag.get("seit"))) is not None:
            zeile = _mit(
                w,
                "{parameter} {wert} {einheit} seit {seit}",
                **werte,
                einheit=groesse.einheit or "",
                seit=seit,
            )
        ergebnis[name] = {**eintrag, "zeile": zeile.strip()}
    return ergebnis
