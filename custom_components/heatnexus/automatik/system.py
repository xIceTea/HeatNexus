"""Das Gerät „HeatNexus Automatik“ je Eintrag: Überblick über alle Automatiken.

Die Automatik je Heizkreis hängt als eigenes Gerät darunter. Das System-Gerät
entsteht mit der ersten Automatik und verschwindet mit der letzten.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from . import eingaben, kennzahlen, regel
from .laufzeit import SIGNAL_SYSTEM, Laufzeit
from .verwaltung import (
    SIGNAL_NEU,
    Verwaltung,
    system_kennung,
    system_unique_id,
    verwaltung_holen,
)

__all__ = ["system_kennung", "system_unique_id"]


class SystemEntitaet(Entity):
    """Grundlage: Kennung, Gerät, Signal des Eintrags."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    ART = ""

    def __init__(self, verwaltung: Verwaltung, entry_id: str) -> None:
        self._verwaltung = verwaltung
        self._entry_id = entry_id
        self._attr_unique_id = system_unique_id(entry_id, self.ART)
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, system_kennung(entry_id))})

    @property
    def _laufzeiten(self) -> list[Laufzeit]:
        return [
            laufzeit
            for laufzeit in self._verwaltung.laufzeiten.values()
            if laufzeit.entry_id == self._entry_id
        ]

    @property
    def available(self) -> bool:
        return bool(self._laufzeiten)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_SYSTEM.format(self._entry_id), self._aktualisiert
            )
        )

    @callback
    def _aktualisiert(self) -> None:
        self.async_write_ha_state()


class SystemStatus(SystemEntitaet, SensorEntity):
    """Der schwerste Zustand aller Automatiken, je Heizkreis als Attribut."""

    ART = "status"
    _attr_translation_key = "automatik_system_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(kennzahlen.STATUS)

    @property
    def native_value(self) -> str | None:
        return kennzahlen.schwerster([kennzahlen.status(lz) for lz in self._laufzeiten])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"heizkreise": {lz.name: kennzahlen.status(lz) for lz in self._laufzeiten}}


class SystemAutomatiken(SystemEntitaet, SensorEntity):
    """Wie viele Automatiken eingerichtet sind."""

    ART = "automatiken"
    _attr_translation_key = "automatik_system_automatiken"

    @property
    def native_value(self) -> int:
        return len(self._laufzeiten)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"heizkreise": [lz.name for lz in self._laufzeiten]}


class SystemEingriffe(SystemEntitaet, SensorEntity):
    """Eingriffe aller Automatiken heute."""

    ART = "eingriffe"
    _attr_translation_key = "automatik_system_eingriffe"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        return sum(kennzahlen.eingriffe_heute(lz) for lz in self._laufzeiten)


class SystemLetzterEingriff(SystemEntitaet, SensorEntity):
    """Der jüngste Eingriff über alle Heizkreise, mit Grund und Heizkreis."""

    ART = "letzter_eingriff"
    _attr_translation_key = "automatik_system_letzter_eingriff"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _unrecorded_attributes = frozenset({"text"})

    def _juengster(self) -> tuple[datetime, str, str] | None:
        kandidaten = [
            (kennzahlen.zeit(eintrag), eintrag["text"], lz.name)
            for lz in self._laufzeiten
            if (eintrag := kennzahlen.letzter_eingriff(lz))
        ]
        return max(kandidaten, key=lambda k: k[0]) if kandidaten else None

    @property
    def native_value(self) -> datetime | None:
        juengster = self._juengster()
        return juengster[0] if juengster else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        juengster = self._juengster()
        return {"text": juengster[1], "heizkreis": juengster[2]} if juengster else {}


class SystemNaechsteEntscheidung(SystemEntitaet, SensorEntity):
    """Die früheste nächste Entscheidung aller Automatiken."""

    ART = "naechste_entscheidung"
    _attr_translation_key = "automatik_system_naechste_entscheidung"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        zeiten = [z for lz in self._laufzeiten if (z := kennzahlen.naechste_entscheidung(lz))]
        return min(zeiten) if zeiten else None


class SystemStoerung(SystemEntitaet, BinarySensorEntity):
    """An, sobald eine Automatik gestört ist."""

    ART = "stoerung"
    _attr_translation_key = "automatik_system_stoerung"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        return any(kennzahlen.gestoert(lz) for lz in self._laufzeiten)


class SystemPrognose(SystemEntitaet, BinarySensorEntity):
    """An, solange jede Automatik eine frische Wetterprognose hat."""

    ART = "prognose"
    _attr_translation_key = "automatik_system_prognose"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        return bool(self._laufzeiten) and all(lz.prognose_frisch for lz in self._laufzeiten)


class SystemLaufHeute(SystemEntitaet, SensorEntity):
    """Stunden heute; mehrere Kreise: der längste."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 1

    def _lauf(self, laufzeit: Laufzeit) -> eingaben.Lauf:
        raise NotImplementedError

    @property
    def native_value(self) -> float | None:
        werte = [kennzahlen.lauf_heute(self._lauf(lz)) for lz in self._laufzeiten]
        return max(werte) if werte else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "heizkreise": {
                lz.name: kennzahlen.lauf_heute(self._lauf(lz)) for lz in self._laufzeiten
            }
        }


class SystemSonnentagHeute(SystemLaufHeute):
    ART = "sonnentag_heute"
    _attr_translation_key = "automatik_system_sonnentag_heute"

    def _lauf(self, laufzeit: Laufzeit) -> eingaben.Lauf:
        return laufzeit.modus_lauf["absenkung"]


class SystemNurWwHeute(SystemLaufHeute):
    ART = "nur_ww_heute"
    _attr_translation_key = "automatik_system_nur_ww_heute"

    def _lauf(self, laufzeit: Laufzeit) -> eingaben.Lauf:
        return laufzeit.modus_lauf["nur_ww"]


class SystemVorrangHeute(SystemLaufHeute):
    ART = "vorrang_heute"
    _attr_translation_key = "automatik_system_vorrang_heute"

    def _lauf(self, laufzeit: Laufzeit) -> eingaben.Lauf:
        return laufzeit.vorrang


class SystemSonnentagAktiv(SystemEntitaet, BinarySensorEntity):
    """An, solange ein Kreis am Sonnentag absenkt."""

    ART = "sonnentag_aktiv"
    _attr_translation_key = "automatik_system_sonnentag_aktiv"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self) -> bool:
        jetzt = dt_util.now()
        return any(
            kennzahlen.schaltet(lz) and regel.absenkung_laeuft(lz.gedaechtnis, jetzt)
            for lz in self._laufzeiten
        )


class SystemNurWwAktiv(SystemEntitaet, BinarySensorEntity):
    """An, solange ein Kreis auf nur Warmwasser steht."""

    ART = "nur_ww_aktiv"
    _attr_translation_key = "automatik_system_nur_ww_aktiv"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self) -> bool:
        return any(
            kennzahlen.schaltet(lz) and lz.gedaechtnis.saison == regel.NUR_WW
            for lz in self._laufzeiten
        )


class SystemAbsenkungBis(SystemEntitaet, SensorEntity):
    """Das späteste Ende einer laufenden Absenkung."""

    ART = "absenkung_bis"
    _attr_translation_key = "automatik_system_absenkung_bis"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        jetzt = dt_util.now()
        enden = [
            lz.gedaechtnis.absenkung_ziel or lz.gedaechtnis.absenkung_bis
            for lz in self._laufzeiten
            if regel.absenkung_laeuft(lz.gedaechtnis, jetzt)
        ]
        return max((e for e in enden if e), default=None)


class SystemModusSeit(SystemEntitaet, SensorEntity):
    """Der früheste Beginn eines laufenden Modus."""

    ART = "modus_seit"
    _attr_translation_key = "automatik_system_modus_seit"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        return min((z for lz in self._laufzeiten if (z := kennzahlen.modus_seit(lz))), default=None)


class SystemTemperatur(SystemEntitaet, SensorEntity):
    """Eine Temperatur je Kreis; der Zustand ist ihr Mittel."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def _wert(self, laufzeit: Laufzeit) -> float | None:
        raise NotImplementedError

    @property
    def native_value(self) -> float | None:
        werte = [w for lz in self._laufzeiten if (w := self._wert(lz)) is not None]
        return round(sum(werte) / len(werte), 2) if werte else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"heizkreise": {lz.name: self._wert(lz) for lz in self._laufzeiten}}


class SystemRaeume(SystemTemperatur):
    ART = "raeume"
    _attr_translation_key = "automatik_system_raeume"

    def _wert(self, laufzeit: Laufzeit) -> float | None:
        return laufzeit.lage.raum if laufzeit.lage else None


class SystemPrognoseMax(SystemTemperatur):
    ART = "prognose_max"
    _attr_translation_key = "automatik_system_prognose_max"

    def _wert(self, laufzeit: Laufzeit) -> float | None:
        werte = [
            w
            for s in laufzeit.stundenprognose(dt_util.now().date()).values()
            if (w := s.get("korrigiert") if s.get("korrigiert") is not None else s.get("roh"))
            is not None
        ]
        return max(werte) if werte else None


class SystemPrognoseMittel(SystemTemperatur):
    """Das kleinere Tagesmittel von heute und morgen: danach schaltet der Prognoseweg."""

    ART = "prognose_mittel"
    _attr_translation_key = "automatik_system_prognose_mittel"

    def _wert(self, laufzeit: Laufzeit) -> float | None:
        heute = dt_util.now().date()
        werte = [
            m
            for tag in (heute, heute + timedelta(days=1))
            if (m := laufzeit.tagesmittel(tag)) is not None
        ]
        return min(werte) if len(werte) == 2 else None


class SystemPrognosekorrektur(SystemTemperatur):
    ART = "prognosekorrektur"
    _attr_translation_key = "automatik_system_prognosekorrektur"
    _attr_device_class = None
    _attr_native_unit_of_measurement = "K"

    def _wert(self, laufzeit: Laufzeit) -> float | None:
        return laufzeit.temperatur.tagesversatz(laufzeit.werte.lernfenster, dt_util.now().date())


class SystemUeberHeizgrenze(SystemEntitaet, BinarySensorEntity):
    """Heizgrenze der Steuerung nachgebildet: aktuelle AT mit 1 K Hysterese."""

    ART = "ueber_heizgrenze"
    _attr_translation_key = "automatik_system_ueber_heizgrenze"

    def __init__(self, verwaltung: Verwaltung, entry_id: str) -> None:
        super().__init__(verwaltung, entry_id)
        self._halt: dict[str, bool | None] = {}

    def _stand(self) -> dict[str, bool | None]:
        for lz in self._laufzeiten:
            lage = lz.lage
            grenze = (lage.grenze_steuerung if lage else None) or regel.HEIZGRENZE_RUECKFALL
            self._halt[lz.name] = eingaben.heizgrenze_halten(
                lage.at if lage else None, grenze, self._halt.get(lz.name)
            )
        return {lz.name: self._halt.get(lz.name) for lz in self._laufzeiten}

    @property
    def is_on(self) -> bool | None:
        stand = [w for w in self._stand().values() if w is not None]
        return any(stand) if stand else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"heizkreise": self._stand()}


KLASSEN: dict[str, type[SystemEntitaet]] = {
    "status": SystemStatus,
    "automatiken": SystemAutomatiken,
    "eingriffe": SystemEingriffe,
    "letzter_eingriff": SystemLetzterEingriff,
    "naechste_entscheidung": SystemNaechsteEntscheidung,
    "stoerung": SystemStoerung,
    "prognose": SystemPrognose,
    "sonnentag_heute": SystemSonnentagHeute,
    "nur_ww_heute": SystemNurWwHeute,
    "vorrang_heute": SystemVorrangHeute,
    "sonnentag_aktiv": SystemSonnentagAktiv,
    "nur_ww_aktiv": SystemNurWwAktiv,
    "absenkung_bis": SystemAbsenkungBis,
    "modus_seit": SystemModusSeit,
    "raeume": SystemRaeume,
    "prognose_max": SystemPrognoseMax,
    "prognose_mittel": SystemPrognoseMittel,
    "prognosekorrektur": SystemPrognosekorrektur,
    "ueber_heizgrenze": SystemUeberHeizgrenze,
}
BINAER_ARTEN = ("stoerung", "prognose", "sonnentag_aktiv", "nur_ww_aktiv", "ueber_heizgrenze")
SENSOR_ARTEN = tuple(art for art in KLASSEN if art not in BINAER_ARTEN)


@callback
def anmelden(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback, art: str
) -> None:
    """Eine System-Entität anlegen, sobald der Eintrag eine Automatik hat."""
    verwaltung = verwaltung_holen(hass)
    angelegt = False

    @callback
    def _anlegen() -> None:
        nonlocal angelegt
        vorhanden = any(lz.entry_id == entry.entry_id for lz in verwaltung.laufzeiten.values())
        if vorhanden and not angelegt:
            async_add_entities(
                [KLASSEN[art](verwaltung, entry.entry_id)],
                config_subentry_id=verwaltung.subeintrag(entry),
            )
        angelegt = vorhanden

    _anlegen()
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEU.format(entry.entry_id), _anlegen)
    )
