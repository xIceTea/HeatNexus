"""Aus Archiv und Kontext einer Anlage die Abschnitte des Reiters „Befund“ bauen."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from . import form, gradtage, haus, heizkreis, kessel
from .archiv import Archiv


@dataclass(frozen=True)
class Kreis:
    """Ein Heizkreis mit dem, was die Befunde von außen brauchen."""

    kennung: str
    name: str
    raeume: list[str]
    modell: dict[str, Any] | None = None
    raum: float | None = None
    aussen_nacht: float | None = None
    ta_heiz: float | None = None
    ta_absenk: float | None = None


@dataclass(frozen=True)
class Kessel:
    """Ein Kessel mit Nennleistung und den Zählern seit Inbetriebnahme."""

    kennung: str
    name: str
    nennleistung: float | None = None
    zaehler: tuple[float, float] | None = None


@dataclass(frozen=True)
class Kontext:
    """Was zur Anlage gehört; ohne Kessel und mit fremder Wärme folgt ein Verweis."""

    land: str | None
    heizkreise: list[Kreis] = field(default_factory=list)
    kessel: list[Kessel] = field(default_factory=list)
    waermequelle_extern: bool = False


def _als_dict(befund: form.Befund, **vergleich: Any) -> dict[str, Any]:
    gesetzt = {k: v for k, v in vergleich.items() if v is not None}
    return asdict(befund) | {"vergleich": gesetzt}


def _runden(wert: float | None) -> float | None:
    return round(wert, 1) if wert is not None else None


def _haus(archiv: Archiv, kreis: Kreis, grenze: float) -> dict[str, Any]:
    tage = archiv.tage_heizkreis(kreis.kennung)
    if not kreis.raeume:
        speicher = form.fehlt("waermespeicher", "raeume")
    elif kreis.modell is None:
        # Das Hausmodell gehört zur Automatik; ohne eingerichteten Heizkreis gibt es keins.
        speicher = form.fehlt("waermespeicher", "automatik")
    else:
        speicher = haus.waermespeicher(kreis.modell, kreis.raum, kreis.aussen_nacht)
    je_gt = haus.heizstunden_je_gradtag(tage[-kessel.FENSTER :], grenze)
    befunde = [
        _als_dict(speicher),
        _als_dict(
            haus.heizgrenze(tage),
            eingestellt=kreis.ta_heiz,
            rechengrenze=grenze,
            heizstunden_je_gt=_runden(je_gt),
        ),
    ]
    return {"art": "haus", "kennung": kreis.kennung, "titel": kreis.name, "befunde": befunde}


def _heizkreis(archiv: Archiv, kreis: Kreis, heizgrenze: float | None) -> dict[str, Any]:
    if kreis.raeume:
        stunden = archiv.stunden(kreis.kennung)
        raeume = heizkreis.raeume(stunden, heizgrenze)
        naechte = heizkreis.naechte(stunden)
    else:
        raeume = form.fehlt("raeume", "raeume")
        naechte = form.fehlt("naechte", "raeume")
    befunde = [
        _als_dict(raeume),
        _als_dict(naechte, ta_absenk=kreis.ta_absenk),
        _als_dict(heizkreis.vorlauf(archiv.tage_heizkreis(kreis.kennung))),
    ]
    return {"art": "heizkreis", "kennung": kreis.kennung, "titel": kreis.name, "befunde": befunde}


def _anlagentage(archiv: Archiv, kontext: Kontext) -> tuple[dict[str, float], dict[str, bool]]:
    """Tagesmittel außen und ob an dem Tag ein Heizkreis der Anlage geheizt hat."""
    at_je_tag: dict[str, float] = {}
    heiz_je_tag: dict[str, bool] = {}
    for kreis in kontext.heizkreise:
        for t in archiv.tage_heizkreis(kreis.kennung):
            if t.get("at") is not None:
                at_je_tag.setdefault(t["datum"], t["at"])
            heiz_je_tag[t["datum"]] = heiz_je_tag.get(t["datum"], False) or haus.heiztag(t)
    return at_je_tag, heiz_je_tag


def _kessel(
    archiv: Archiv, k: Kessel, kontext: Kontext, grenze: float, heizgrenze: float | None
) -> dict[str, Any]:
    at_je_tag, heiz_je_tag = _anlagentage(archiv, kontext)
    tage = [
        t | {"heiztag": heiz_je_tag.get(t["datum"], False)}
        for t in archiv.tage_kessel(k.kennung, at_je_tag)
    ]
    befunde = [
        _als_dict(kessel.laufzeit(tage, k.zaehler)),
        _als_dict(kessel.energie(tage, grenze, heizgrenze), nennleistung=k.nennleistung),
    ]
    return {"art": "kessel", "kennung": k.kennung, "titel": k.name, "befunde": befunde}


def _lage(abschnitte: list[dict[str, Any]], archiv: Archiv) -> dict[str, Any]:
    befunde = [b for a in abschnitte for b in a["befunde"]]
    tage = [d for eintraege in archiv.tage_hk.values() for d in eintraege]
    lage: dict[str, Any] = {"befunde": len(befunde), "seit": min(tage) if tage else None}
    for name, status in (
        ("unauffaellig", form.UNAUFFAELLIG),
        ("hinweise", form.HINWEIS),
        ("sammelt", form.SAMMELT),
        ("braucht_daten", form.BRAUCHT_DATEN),
    ):
        lage[name] = sum(b["status"] == status for b in befunde)
    return lage


def anlage(archiv: Archiv, kontext: Kontext) -> dict[str, Any]:
    """Haus und Heizkreis je Heizkreis, danach Kessel oder der Verweis auf den Wärmeerzeuger."""
    grenze = gradtage.rechengrenze(kontext.land)
    abschnitte: list[dict[str, Any]] = []
    heizgrenze = None
    for kreis in kontext.heizkreise:
        teil = _haus(archiv, kreis, grenze)
        eigene = teil["befunde"][1]["wert"]
        heizgrenze = heizgrenze if heizgrenze is not None else eigene
        abschnitte += [teil, _heizkreis(archiv, kreis, eigene)]
    abschnitte += [_kessel(archiv, k, kontext, grenze, heizgrenze) for k in kontext.kessel]
    if not kontext.kessel and kontext.waermequelle_extern:
        abschnitte.append({"art": "waermeerzeuger", "kennung": "", "titel": "", "befunde": []})
    return {"lage": _lage(abschnitte, archiv), "abschnitte": abschnitte}
