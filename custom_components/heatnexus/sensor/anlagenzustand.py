"""Anlagenzustand je Steuerung: was der Kopf der Übersicht zeigt, als Entität.

Meldungsstufe und Sonderzustände des Kessels folgen denselben Regeln wie Panel
und Dashboard; die Kesselregeln stehen in `dashboard/kesselzustand.py`.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN
from ..dashboard.anlagen import rang
from ..dashboard.kesselzustand import (
    BETRIEBSART,
    BETRIEBSWAHL,
    OFFLINE,
    PHASE,
    PHASEN_GESPERRT,
    REGELN,
    SERVICEAUSBRAND,
)
from ..entity import steuerung_kennung
from ..error_texts import meldungscodes
from ..helpers import enum_texte, parse_value

_STUFEN = ("alarm", "fehler", "info")
_STUFENSYMBOL = {
    "in_ordnung": "mdi:check-circle-outline",
    "info": "mdi:information-outline",
    "fehler": "mdi:alert-outline",
    "alarm": "mdi:alert-circle-outline",
}
ZUSTAENDE: tuple[str, ...] = (
    "in_ordnung",
    *_STUFEN,
    "nicht_erreichbar",
    *dict.fromkeys(zustand for *_, zustand in REGELN),
    "brenner_gesperrt",
)


def kennung(coordinator: Any) -> str:
    """Kennung des Sensors „Anlagenzustand“ einer Steuerung."""
    return f"{steuerung_kennung(coordinator)}-anlagenzustand"


def meldungsstufe(daten: dict[str, Any]) -> str:
    """Die schwerste anliegende Meldungsart: `alarm`, `fehler`, `info` oder `ok`.

    Im Störspeicher zählt der Kennbuchstabe; eine Gerätemeldung ohne Eintrag dort zählt als Fehler.
    """
    speicher = [e for e in daten.get("stoerspeicher") or [] if e.get("aktiv")]
    arten = {{"A": "alarm", "I": "info"}.get(e.get("symbol"), "fehler") for e in speicher}
    im_speicher = {str(e.get("code")) for e in speicher}
    for roh in (daten.get("status") or {}).values():
        codes = meldungscodes(roh)
        if not codes or all(str(code) in im_speicher for _, code in codes):
            continue
        arten.add("alarm" if any(art == "A" for art, _ in codes) else "fehler")
    return next((stufe for stufe in _STUFEN if stufe in arten), "ok")


def _kessel(beschreibungen: list[dict]) -> str | None:
    """Präfix des ersten Kessels mit Betriebsart, dem Weg der Wärme nach."""
    endung = f"/{BETRIEBSART}/0"
    kandidaten = [
        d for d in beschreibungen if str(d.get("oid") or "").endswith(endung) and d.get("type")
    ]
    if not kandidaten:
        return None
    erster = min(kandidaten, key=lambda d: (rang(d.get("fct_type")), d["oid"]))
    return erster["oid"][: -len(endung)]


def _zahl(oids: dict[str, Any], oid: str) -> int | None:
    return parse_value(oids.get(oid), int, oid)


def kesselzustand(daten: dict[str, Any], praefix: str | None) -> tuple[str, str] | None:
    """Sonderzustand des Kessels als (Zustand, Symbol); `None`, wenn nichts Besonderes anliegt."""
    if praefix is None:
        return None
    oids = daten.get("oids") or {}
    art = _zahl(oids, f"{praefix}/{BETRIEBSART}/0")
    service = _zahl(oids, f"{praefix}/{BETRIEBSWAHL}/0") == SERVICEAUSBRAND
    for werte, mit_service, _, symbol, zustand in REGELN:
        if art in werte and mit_service in (None, service):
            return zustand, symbol
    werte, symbol = PHASEN_GESPERRT
    if _zahl(oids, f"{praefix}/{PHASE}/0") in werte:
        return "brenner_gesperrt", symbol
    return None


def _anlagentext(
    beschreibungen: list[dict], praefix: str | None, oids: dict[str, Any], adresse: str
) -> str | None:
    """Der Text der Anlage zu einem Auswahlwert, in ihrer Sprache."""
    oid = f"{praefix}/{adresse}/0"
    if praefix is None or (wert := _zahl(oids, oid)) is None:
        return None
    beschreibung = next((d for d in beschreibungen if d.get("oid") == oid), {"enum": adresse})
    return enum_texte(beschreibung).get(wert)


def ermitteln(
    daten: dict[str, Any] | None, beschreibungen: list[dict], erreichbar: bool
) -> tuple[str | None, str, dict[str, Any]]:
    """Zustand, Symbol und Attribute: nicht erreichbar vor Alarm und Fehler, vor dem Kessel."""
    if not erreichbar:
        return "nicht_erreichbar", OFFLINE[1], {}
    if daten is None:
        return None, _STUFENSYMBOL["in_ordnung"], {}
    stufe = meldungsstufe(daten)
    praefix, oids = _kessel(beschreibungen), daten.get("oids") or {}
    kessel = kesselzustand(daten, praefix)
    attribute = {
        "meldungsstufe": stufe,
        "kesselzustand": kessel[0] if kessel else None,
        "betriebsart": _anlagentext(beschreibungen, praefix, oids, BETRIEBSART),
        "betriebsphase": _anlagentext(beschreibungen, praefix, oids, PHASE),
    }
    if stufe in ("alarm", "fehler"):
        return stufe, _STUFENSYMBOL[stufe], attribute
    if kessel:
        return kessel[0], kessel[1], attribute
    zustand = "info" if stufe == "info" else "in_ordnung"
    return zustand, _STUFENSYMBOL[zustand], attribute


class AnlagenzustandSensor(CoordinatorEntity, SensorEntity):
    """Ob die Anlage in Ordnung ist, eine Meldung anliegt, der Kessel etwas Besonderes tut."""

    _attr_has_entity_name = True
    _attr_translation_key = "anlagenzustand"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(ZUSTAENDE)

    def __init__(self, coordinator: Any) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = kennung(coordinator)
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, steuerung_kennung(coordinator))})
        self._auswerten()

    @property
    def available(self) -> bool:
        # Bleibt verfügbar: Gerade wenn die Steuerung schweigt, meldet der Sensor das.
        return True

    def _auswerten(self) -> None:
        """Zustand, Symbol und Attribute einmal je Abruf bestimmen."""
        beschreibungen = getattr(self.coordinator.client, "devices", None) or []
        (
            self._attr_native_value,
            self._attr_icon,
            self._attr_extra_state_attributes,
        ) = ermitteln(self.coordinator.data, beschreibungen, self.coordinator.last_update_success)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._auswerten()
        super()._handle_coordinator_update()


def anmelden(hass: HomeAssistant, entry: Any, async_add_entities: Any) -> None:
    """Je Steuerung ein Sensor, gleich beim Einrichten."""
    async_add_entities(
        AnlagenzustandSensor(coordinator)
        for coordinator in entry.runtime_data["coordinators"].values()
    )
