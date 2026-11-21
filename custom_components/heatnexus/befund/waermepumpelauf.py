"""Wärmepumpe im Takt des Befunds: Temperaturen im Heizbetrieb und Zählerstände je Tag."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..geraete import BEFUND
from ..helpers import get_oid_value
from . import waermepumpe
from .auswertung import Waermepumpengeraet
from .pflegelauf import beschreibungen, geraetename
from .pflegeziele import praefix

_WP = {fct: BEFUND[fct]["waermepumpe"] for fct in waermepumpe.FUNKTIONSTYPEN}
LUFT = {fct: w["luft"] for fct, w in _WP.items()}
LEISTUNG = {fct: w["leistung"] for fct, w in _WP.items()}
# fctType 7 führt Tageszähler und den COP des Tages; fctType 27 nur Gesamtzähler.
TAGESZAEHLER, WW_HEUTE = _WP[7]["tageszaehler"], _WP[7]["ww_heute"]
VORLAUF, PHASE = waermepumpe.VORLAUF, waermepumpe.PHASE
EHEIZUNG, BH_27 = _WP[27]["eheizung"], _WP[27]["bh"]
WAERME_27, STROM_27, KUEHLEN_27 = _WP[27]["waerme"], _WP[27]["strom"], _WP[27]["kuehlen"]
# Der Bezug beginnt neu mit dem Tag, an dem der Verdampfer gereinigt wurde.
PFLEGE_ART = "verdampfer"


@dataclass(frozen=True)
class WpZiel:
    """Eine Wärmepumpe mit allem, was der Gütegrad braucht; Adressen ohne Präfix."""

    prefix: str
    device_id: str
    fct_type: int
    waerme: str | None = None
    strom: str | None = None
    kuehlen: str | None = None
    einheit: dict[str, str | None] | None = None


def _beschreibungen(coordinator: Any) -> dict[str, dict]:
    return {b.get("oid") or "": b for b in beschreibungen(coordinator)}


def _erstes(vorhanden: dict[str, dict], prefix: str, adressen: tuple[str, ...]) -> str | None:
    return next((a for a in adressen if f"{prefix}{a}" in vorhanden), None)


def _ziel_27(vorhanden: dict[str, dict], prefix: str, device_id: str) -> WpZiel | None:
    waerme, strom = _erstes(vorhanden, prefix, WAERME_27), _erstes(vorhanden, prefix, STROM_27)
    if not (waerme and strom and f"{prefix}{BH_27}" in vorhanden):
        return None
    kuehlen = _erstes(vorhanden, prefix, KUEHLEN_27)
    einheit = {
        a: vorhanden[f"{prefix}{a}"].get("unit") for a in (waerme, strom, kuehlen) if a is not None
    }
    return WpZiel(prefix, device_id, 27, waerme, strom, kuehlen, einheit)


def ziele_von(coordinator: Any) -> list[WpZiel]:
    """AeroWIN nach Funktionstyp, wenn die Zähler der Arbeitszahl gemeldet werden.

    Luft und Vorlauf stehen bei fctType 7 in keinem Menü oder nur auf der Serviceebene;
    `abruf` meldet sie selbst zum Lesen an, statt eine Entität dafür vorauszusetzen.
    """
    vorhanden = _beschreibungen(coordinator)
    gefunden: dict[str, WpZiel] = {}
    for oid, b in vorhanden.items():
        fct, prefix, device_id = b.get("fct_type"), praefix(oid), b.get("device_id")
        if fct not in waermepumpe.FUNKTIONSTYPEN or not prefix or not device_id:
            continue
        if prefix in gefunden:
            continue
        if fct == 7:
            if all(f"{prefix}{a}" in vorhanden for a in TAGESZAEHLER.values()):
                gefunden[prefix] = WpZiel(prefix, device_id, fct)
        elif ziel := _ziel_27(vorhanden, prefix, device_id):
            gefunden[prefix] = ziel
    return [gefunden[p] for p in sorted(gefunden)]


def abruf(coordinator: Any) -> set[str]:
    """Die Adressen, die je Takt frisch sein müssen, auch ohne aktivierte Entität."""
    oids: set[str] = set()
    for z in ziele_von(coordinator):
        adressen = [LUFT[z.fct_type], LEISTUNG[z.fct_type], VORLAUF[z.fct_type], PHASE[z.fct_type]]
        adressen += [WW_HEUTE] if z.fct_type == 7 else [EHEIZUNG]
        oids |= {f"{z.prefix}{a}" for a in adressen}
    return oids


def _kwh(coordinator: Any, z: WpZiel, adresse: str | None) -> float | None:
    if adresse is None or (wert := get_oid_value(coordinator, adresse, z.prefix)) is None:
        return None
    return round(wert * waermepumpe.faktor((z.einheit or {}).get(adresse)), 3)


def _zaehler(coordinator: Any, z: WpZiel) -> dict[str, float | None]:
    if z.fct_type == 7:
        return {n: get_oid_value(coordinator, a, z.prefix) for n, a in TAGESZAEHLER.items()}
    return {
        "wz": _kwh(coordinator, z, z.waerme),
        "sz": _kwh(coordinator, z, z.strom),
        "bhz": get_oid_value(coordinator, BH_27, z.prefix),
        "kz": _kwh(coordinator, z, z.kuehlen),
    }


def messen(
    coordinator: Any, archiv: Any, ww_vorher: dict[str, float | None], zeit: datetime
) -> dict[str, float | None]:
    """Je Wärmepumpe einen Takt; liefert die Warmwasserwärme für den nächsten Vergleich."""
    neu: dict[str, float | None] = {}
    for z in ziele_von(coordinator):

        def wert(adresse: str, z: WpZiel = z) -> float | None:
            return get_oid_value(coordinator, adresse, z.prefix)

        ww = wert(WW_HEUTE) if z.fct_type == 7 else None
        probe = waermepumpe.Probe(
            wert(VORLAUF[z.fct_type]),
            wert(LUFT[z.fct_type]),
            wert(LEISTUNG[z.fct_type]),
            wert(PHASE[z.fct_type]),
            ww,
            wert(EHEIZUNG) if z.fct_type == 27 else None,
        )
        gezaehlt = waermepumpe.zaehlt(z.fct_type, probe, ww_vorher.get(z.prefix))
        tage = waermepumpe.sammeln(
            archiv.wp_tage(z.prefix), zeit, z.fct_type, probe, gezaehlt, _zaehler(coordinator, z)
        )
        archiv.wp_setzen(z.prefix, tage)
        neu[z.prefix] = ww
    return neu


def geraete(coordinator: Any, archiv: Any) -> list[Waermepumpengeraet]:
    """Je Wärmepumpe, was die Auswertung braucht; der Bezug folgt der letzten Verdampferreinigung."""
    return [
        Waermepumpengeraet(
            kennung=z.device_id,
            name=geraetename(coordinator, z.device_id),
            prefix=z.prefix,
            fct_type=z.fct_type,
            bezug_ab=archiv.pflege_eintrag(z.prefix, PFLEGE_ART).get("zuletzt"),
        )
        for z in ziele_von(coordinator)
    ]


def arten(coordinator: Any) -> list[tuple[str, str, tuple[str, ...]]]:
    """Je Wärmepumpe Kennung, Gerät und Art des Befund-Sensors, wie `geraete_der_anlage` sie führt."""
    return [(z.device_id, z.device_id, ("arbeitszahl",)) for z in ziele_von(coordinator)]


def kennungen(coordinator: Any) -> dict[str, str]:
    """Kennung → Domäne von Datum und Taste „Verdampfer gereinigt“; ohne sie gälten sie als verwaist."""
    gefunden: dict[str, str] = {}
    for z in ziele_von(coordinator):
        gefunden[f"{z.device_id}-verdampfer-zuletzt"] = "date"
        gefunden[f"{z.device_id}-verdampfer-erledigt"] = "button"
    return gefunden
