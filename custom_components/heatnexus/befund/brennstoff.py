"""Brennstoff im Lager: Verbrauch je Tag, Vorrat seit der Lieferung, Datum „reicht bis“."""

from __future__ import annotations

from datetime import date, timedelta
from itertools import pairwise
import math
from typing import Any

from . import form
from .pflege import JAHR_MIN_TAGE, VORSCHAU_TAGE, vorschau

EINHEIT = {"pellets": "t", "hackgut": "Srm", "scheitholz": "Rm"}
# Heizwert je Lagereinheit (LWF-Merkblatt 12): Pellets 4,8 kWh/kg, Hackgut Fichte W30 je
# Schüttraummeter, Scheitholz Buche W20 je Raummeter; daraus 488 kg Buche je Raummeter.
HEIZWERT = {"pellets": 4800.0, "hackgut": 745.0, "scheitholz": 1885.0}
KG_JE_RM = 488.0
WIRKUNGSGRAD = 0.9
KORREKTUR_MIN, KORREKTUR_MAX = 0.5, 2.0
KORREKTUREN = 3
MITTEL_TAGE = 14
BALD_TAGE = 7
# Mehr Zuwachs an einem Tag ist kein Verbrauch, sondern ein Sprung im Zähler.
MAX_JE_TAG = {"zaehler": 1.0, "anheizen": 20.0}
# Ab Werk liegen 23/103 (Brennstoffverbrauch gesamt, t) an der BioWIN und 20/112
# (Anheizvorgänge) am LogWIN; die PuroWIN zählt keinen Brennstoff.
ZAEHLER = {9: "/23/103/0", 10: "/20/112/0"}
PUROWIN_PELLETS = 2


def art_von(fct_type: int | None, brennstoff_code: float | None) -> str:
    """Pellets, Hackgut oder Scheitholz nach Baureihe; die PuroWIN meldet ihn in `38/127`."""
    if fct_type == 10:
        return "scheitholz"
    if fct_type == 25:
        return "pellets" if brennstoff_code == PUROWIN_PELLETS else "hackgut"
    return "pellets"


def weise_von(fct_type: int | None, hat_zaehler: bool) -> str:
    """Woraus der Verbrauch kommt: Zähler der Steuerung, Anheizvorgänge oder erzeugte Wärme."""
    if fct_type == 10:
        return "anheizen"
    return "zaehler" if fct_type == 9 and hat_zaehler else "waerme"


def fuellmenge(nennleistung: float | None) -> float:
    """Füllraum in kg Buche laut Anleitung: LogWIN Premium bis 30 kW 50 kg, darüber 64 kg."""
    return 64.0 if (nennleistung or 0) >= 35 else 50.0


def korrektur(lager: dict[str, Any]) -> float:
    """Mittel der gelernten Korrekturen; ohne Lieferung mit Rest 1."""
    werte = lager.get("korrekturen") or []
    return sum(werte) / len(werte) if werte else 1.0


def _deltas(zaehler: dict[str, float], grenze: float) -> dict[str, float]:
    ergebnis: dict[str, float] = {}
    for (tag_a, a), (tag_b, b) in pairwise(sorted(zaehler.items())):
        folgetag = (date.fromisoformat(tag_b) - date.fromisoformat(tag_a)).days == 1
        if folgetag and a is not None and b is not None and 0 <= b - a <= grenze:
            ergebnis[tag_b] = b - a
    return ergebnis


def tagesverbrauch(
    lager: dict[str, Any],
    tage_k: dict[str, dict[str, Any]],
    zaehler: dict[str, float],
    mit_korrektur: bool = True,
) -> dict[str, float]:
    """Verbrauch je Tag in der Lagereinheit, mit der gelernten Korrektur."""
    weise, art = lager.get("weise"), lager.get("art", "pellets")
    if weise == "zaehler":
        roh = _deltas(zaehler, MAX_JE_TAG["zaehler"])
    elif weise == "anheizen":
        je_fuellung = (lager.get("fuellmenge") or fuellmenge(None)) / KG_JE_RM
        roh = {t: n * je_fuellung for t, n in _deltas(zaehler, MAX_JE_TAG["anheizen"]).items()}
    else:
        nenner = (lager.get("wirkungsgrad") or WIRKUNGSGRAD) * (
            lager.get("heizwert") or HEIZWERT[art]
        )
        roh = {t: v["kwh"] / nenner for t, v in tage_k.items() if v.get("kwh") is not None}
    faktor = korrektur(lager) if mit_korrektur else 1.0
    return {t: round(v * faktor, 4) for t, v in roh.items()}


def bestand(lager: dict[str, Any], verbrauch: dict[str, float]) -> float | None:
    """Vorrat heute: Stand der letzten Lieferung minus Verbrauch der Tage danach, nicht unter null."""
    if lager.get("bestand") is None:
        return None
    seit = lager.get("seit") or ""
    return max(round(lager["bestand"] - sum(v for t, v in verbrauch.items() if t > seit), 3), 0.0)


def geliefert(
    lager: dict[str, Any],
    menge: float,
    rest: float | None,
    heute: date,
    roh: dict[str, float],
    aktuell: float | None = None,
) -> dict[str, Any]:
    """Eine Lieferung; mit `rest` lernt die Rechnung aus dem tatsächlichen Verbrauch."""
    neu = dict(lager)
    korrekturen = list(lager.get("korrekturen") or [])
    seit = lager.get("seit") or ""
    berechnet = sum(v for t, v in roh.items() if t > seit)
    if rest is not None and lager.get("bestand") is not None and berechnet > 0:
        tatsaechlich = lager["bestand"] - rest
        faktor = min(KORREKTUR_MAX, max(KORREKTUR_MIN, tatsaechlich / berechnet))
        korrekturen = [*korrekturen, round(faktor, 3)][-KORREKTUREN:]
    # Ein gerechneter Vorrat unter null heißt leer; der Überhang zählt nicht gegen die neue Menge.
    vorher = rest if rest is not None else max(aktuell or 0.0, 0.0)
    eintrag = {"tag": heute.isoformat(), "menge": menge, "rest": rest}
    neu |= {
        "bestand": round(vorher + menge, 3),
        "seit": heute.isoformat(),
        "korrekturen": korrekturen,
        "lieferungen": [*(lager.get("lieferungen") or []), eintrag],
    }
    return neu


def _jahr(verbrauch: dict[str, float], heute: date) -> dict[str, float]:
    grenze = (heute - timedelta(days=VORSCHAU_TAGE)).isoformat()
    jahr = {t[5:]: v for t, v in verbrauch.items() if grenze <= t < heute.isoformat()}
    return jahr if len(jahr) >= JAHR_MIN_TAGE else {}


def _mittel(verbrauch: dict[str, float], heute: date) -> float | None:
    """Mittel je Kalendertag über die letzten 14 Tage; Tage ohne Wert zählen nicht."""
    grenze = (heute - timedelta(days=MITTEL_TAGE)).isoformat()
    werte = [v for t, v in verbrauch.items() if grenze <= t < heute.isoformat()]
    return sum(werte) / len(werte) if werte else None


def befund(lager: dict[str, Any], verbrauch: dict[str, float], heute: date) -> form.Befund:
    """Tage, bis der Vorrat aufgebraucht ist; das Datum in den Angaben."""
    vorrat = bestand(lager, verbrauch)
    if vorrat is None:
        return form.fehlt("brennstoff", "vorrat")
    mittel, jahr = _mittel(verbrauch, heute), _jahr(verbrauch, heute)
    angaben: dict[str, Any] = {
        "bestand": vorrat,
        "einheit": EINHEIT.get(lager.get("art", "pellets")),
        "je_tag": round(mittel, 4) if mittel is not None else None,
        "korrektur": round(korrektur(lager), 2),
        "vorjahr": bool(jahr),
    }
    gezaehlt = lager.get("weise") == "zaehler" or bool(lager.get("korrekturen"))
    stufe = form.BELASTBAR if gezaehlt else form.VORLAEUFIG
    if mittel is None and not jahr:
        return form.Befund("brennstoff", form.SAMMELT, angaben=angaben)
    if jahr:
        datum = vorschau(max(vorrat, 0.0), heute, jahr)
    elif mittel and mittel > 0:
        tage = math.ceil(max(vorrat, 0.0) / mittel)
        datum = heute + timedelta(days=tage) if tage <= VORSCHAU_TAGE else None
    else:
        return form.Befund(
            "brennstoff", form.UNAUFFAELLIG, None, "d", stufe, angaben | {"ruht": True}
        )
    if datum is None:
        angaben["ueber_jahr"] = True
        return form.Befund("brennstoff", form.UNAUFFAELLIG, None, "d", stufe, angaben)
    tage = (datum - heute).days
    angaben["datum"] = datum.isoformat()
    status = form.HINWEIS if tage < BALD_TAGE else form.UNAUFFAELLIG
    return form.Befund("brennstoff", status, float(tage), "d", stufe, angaben)
