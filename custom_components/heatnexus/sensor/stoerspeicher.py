"""Störspeicher des Bediengeräts als Sensor am Gerät „Steuerung“.

Der Zustand ist die Zahl der Einträge, das Attribut `eintraege` die Liste wie
am Bediengerät. Quittieren, Zurücksetzen und Löschen laufen über diesen Sensor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .. import texte
from ..const import CONF_STOERUNG_ZURUECKSETZEN, DOMAIN
from ..entity import steuerung_kennung
from ..error_texts import parse_messages, unbekannt
from ..exceptions import WindhagerError, WindhagerValueError, mit_text

_ZEIT = "%Y-%m-%d %H:%M:%S"
# Was im Logbuch steht; die Wörter laufen durch das Wörterbuch.
_AKTIONEN = {
    "quittieren": "Meldung zurückgesetzt",
    "zuruecksetzen": "Störung am Kessel zurückgesetzt",
    "loeschen": "Meldung gelöscht",
}


def _ortszeit(roh: Any) -> str | None:
    """Zeit der Steuerung (Ortszeit ohne Zone) als Zeitpunkt mit Zone."""
    try:
        zeit = datetime.strptime(str(roh).strip(), _ZEIT)
    except (TypeError, ValueError):
        return None
    return zeit.replace(tzinfo=dt_util.get_default_time_zone()).isoformat()


def _texte_des_knotens(client: Any, knoten: int) -> tuple[dict | None, str]:
    """Störungstexte und Sprache des Geräts, von dem ein Eintrag stammt."""
    for beschreibung in getattr(client, "devices", None) or []:
        if str(beschreibung.get("node_id")) == str(knoten) and beschreibung.get("stoerungstexte"):
            return beschreibung["stoerungstexte"], beschreibung.get("sprache") or client.sprache
    return None, getattr(client, "sprache", None) or "de"


def eintraege_aufbereiten(client: Any, roh: list[dict], erlaubt: bool) -> list[dict]:
    """Klartext, Art und Abhilfe zu jedem Eintrag; Zurücksetzen nur mit Erlaubnis."""
    aus = []
    for eintrag in roh:
        zusatz, sprache = _texte_des_knotens(client, eintrag["knoten"])
        meldung = next(iter(parse_messages(eintrag["meldung"], zusatz, sprache)), None) or {}
        aus.append(
            {
                **eintrag,
                "text": meldung.get("text") or unbekannt(eintrag.get("code") or 0, sprache),
                "art": meldung.get("kind"),
                "info": meldung.get("info"),
                "behebung": meldung.get("behebung"),
                "zuerst": _ortszeit(eintrag.get("zuerst")),
                "zuletzt": _ortszeit(eintrag.get("zuletzt")),
                "zuruecksetzbar": bool(eintrag.get("zuruecksetzbar")) and erlaubt,
            }
        )
    return aus


def kennung(coordinator: Any) -> str:
    """Kennung des Sensors „Störspeicher“ einer Steuerung."""
    return f"{steuerung_kennung(coordinator)}-stoerspeicher"


def kennungen(coordinators: dict) -> set[str]:
    """Die Sensoren der Steuerungen, die einen Störspeicher melden oder noch nicht geantwortet haben."""
    return {
        kennung(coordinator)
        for coordinator in coordinators.values()
        if (coordinator.data or {}).get("stoerspeicher") is not None
        or getattr(getattr(coordinator, "client", None), "stoerspeicher_vorhanden", False) is None
    }


def zuruecksetzen_erlaubt(coordinator: Any) -> bool:
    """Ob die Option „Störungen am Kessel zurücksetzen erlauben“ eingeschaltet ist."""
    eintrag = getattr(coordinator, "config_entry", None)
    return bool((getattr(eintrag, "options", None) or {}).get(CONF_STOERUNG_ZURUECKSETZEN, False))


class StoerspeicherSensor(CoordinatorEntity, SensorEntity):
    """Die Einträge im Störspeicher des Bediengeräts."""

    _attr_has_entity_name = True
    _attr_translation_key = "stoerspeicher"
    _attr_icon = "mdi:clipboard-alert-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    # Die Liste kommt bei jedem Abruf neu von der Steuerung; im Verlauf wäre sie Ballast.
    _unrecorded_attributes = frozenset({"eintraege"})

    def __init__(self, coordinator: Any) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = kennung(coordinator)
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, steuerung_kennung(coordinator))})

    @property
    def _roh(self) -> list[dict] | None:
        return (self.coordinator.data or {}).get("stoerspeicher")

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._roh is not None

    @property
    def native_value(self) -> int | None:
        roh = self._roh
        return None if roh is None else len(roh)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        roh = self._roh
        if roh is None:
            return None
        erlaubt = zuruecksetzen_erlaubt(self.coordinator)
        return {
            "eintraege": eintraege_aufbereiten(self.coordinator.client, roh, erlaubt),
            "aktiv": sum(1 for e in roh if e.get("aktiv")),
            "zuruecksetzen_erlaubt": erlaubt,
        }

    def _eintrag(self, kennung: int) -> dict:
        roh = self._roh
        if roh is None:
            raise mit_text(WindhagerError, "kein_stoerspeicher")
        for eintrag in roh:
            if eintrag["id"] == int(kennung):
                return eintrag
        raise mit_text(WindhagerValueError, "eintrag_fehlt", eintrag=kennung)

    async def async_quittieren(self, eintrag: int) -> None:
        gefunden = self._eintrag(eintrag)
        await self.coordinator.client.stoerung_quittieren(gefunden["id"])
        await self._abschliessen("quittieren", gefunden)

    async def async_zuruecksetzen(self, eintrag: int) -> None:
        if not zuruecksetzen_erlaubt(self.coordinator):
            raise mit_text(WindhagerValueError, "zuruecksetzen_aus")
        gefunden = self._eintrag(eintrag)
        if not gefunden.get("zuruecksetzbar"):
            raise mit_text(WindhagerValueError, "nicht_zuruecksetzbar", eintrag=eintrag)
        await self.coordinator.client.stoerung_zuruecksetzen(gefunden["id"])
        await self._abschliessen("zuruecksetzen", gefunden)

    async def async_loeschen(self, eintrag: int) -> None:
        gefunden = self._eintrag(eintrag)
        if not gefunden.get("loeschbar"):
            raise mit_text(WindhagerValueError, "nicht_loeschbar", eintrag=eintrag)
        await self.coordinator.client.stoerung_loeschen(gefunden["id"])
        await self._abschliessen("loeschen", gefunden)

    async def _abschliessen(self, aktion: str, eintrag: dict) -> None:
        """Im Logbuch festhalten, wer was getan hat, und die Liste neu lesen."""
        logbuch(self.hass, self, aktion, eintrag)
        await self.coordinator.async_request_refresh()


@callback
def logbuch(hass: HomeAssistant, entitaet: Any, aktion: str, eintrag: dict) -> None:
    """Ein Logbucheintrag zur Aktion; der Benutzer kommt aus dem Kontext des Aufrufs."""
    if hass is None or "logbook" not in hass.config.components:
        return
    from homeassistant.components.logbook import async_log_entry

    satz = texte.woerterbuch_des_koordinators(entitaet.coordinator)(_AKTIONEN[aktion])
    async_log_entry(
        hass,
        entitaet.name or "HeatNexus",
        f"{satz}: {eintrag.get('meldung') or eintrag.get('code')}",
        DOMAIN,
        entitaet.entity_id,
        # Home Assistant setzt den Kontext des Dienstaufrufs vor dem Aufruf der Entität.
        getattr(entitaet, "_context", None),
    )


def anmelden(hass: HomeAssistant, entry: Any, async_add_entities: Any) -> None:
    """Je Steuerung einen Sensor, sobald sie einen Störspeicher meldet."""
    bekannt: set[str] = set()

    @callback
    def _pruefen() -> None:
        neu = []
        for coordinator in entry.runtime_data["coordinators"].values():
            if (coordinator.data or {}).get("stoerspeicher") is None:
                continue
            if (eigene := kennung(coordinator)) not in bekannt:
                bekannt.add(eigene)
                neu.append(StoerspeicherSensor(coordinator))
        if neu:
            async_add_entities(neu)

    _pruefen()
    for coordinator in entry.runtime_data["coordinators"].values():
        entry.async_on_unload(coordinator.async_add_listener(_pruefen))
