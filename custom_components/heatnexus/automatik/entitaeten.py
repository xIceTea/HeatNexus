"""Schalter, Modus und Zustand der Automatik als Entitäten am Heizkreis.

Sie hängen am vorhandenen Heizkreis-Gerät und folgen der Laufzeit über ein
Signal; abgefragt wird nichts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN
from ..registrierung import uebergeordnet
from ..texte import woerterbuch
from . import kennzahlen, regel
from .konfig import MODI
from .laufzeit import SIGNAL_AKTUALISIERT, Laufzeit
from .profile import AUSGEWOGEN, AUSRICHTUNGEN
from .regel import Zustand
from .verwaltung import (
    SIGNAL_NEU,
    Verwaltung,
    geraet_kennung,
    system_kennung,
    unique_id,
    verwaltung_holen,
)


def geraet_info(laufzeit: Laufzeit) -> DeviceInfo:
    """Ein eigenes Gerät je Automatik, unter dem System-Gerät „HeatNexus Automatik“."""
    anlage = getattr(laufzeit.coordinator, "label", "") or ""
    uebersetzt = woerterbuch(laufzeit.hass)
    name = uebersetzt("Automatik {name}").replace("{name}", laufzeit.name)
    return DeviceInfo(
        identifiers={(DOMAIN, geraet_kennung(laufzeit.device_id))},
        name=f"{anlage} · {name}" if anlage else name,
        manufacturer="HeatNexus",
        model=uebersetzt("Automatik"),
        **uebergeordnet(laufzeit.hass, system_kennung(laufzeit.entry_id), laufzeit.entry_id),
    )


class AutomatikEntitaet(Entity):
    """Gemeinsame Grundlage: Kennung, Gerät, Signal."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    ART = ""

    def __init__(self, verwaltung: Verwaltung, device_id: str) -> None:
        self._verwaltung = verwaltung
        self._device_id = device_id
        self._attr_unique_id = unique_id(device_id, self.ART)
        self._attr_device_info = geraet_info(verwaltung.laufzeiten[device_id])

    @property
    def _laufzeit(self) -> Laufzeit | None:
        return self._verwaltung.laufzeiten.get(self._device_id)

    @property
    def available(self) -> bool:
        return self._laufzeit is not None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_AKTUALISIERT.format(self._device_id), self._aktualisiert
            )
        )

    @callback
    def _aktualisiert(self) -> None:
        self.async_write_ha_state()


class AutomatikSchalter(AutomatikEntitaet, SwitchEntity):
    """Automatik an oder aus."""

    ART = "schalter"
    _attr_translation_key = "automatik"

    @property
    def is_on(self) -> bool | None:
        return self._laufzeit.aktiv if self._laufzeit else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._verwaltung.einstellen(self._device_id, {"aktiv": True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._verwaltung.einstellen(self._device_id, {"aktiv": False})


class AutomatikModus(AutomatikEntitaet, SelectEntity):
    """Beobachten, Manuell mit Empfehlung oder Automatisch."""

    ART = "modus"
    _attr_translation_key = "automatik_modus"
    _attr_options = list(MODI)

    @property
    def current_option(self) -> str | None:
        return self._laufzeit.konfig.get("modus") if self._laufzeit else None

    async def async_select_option(self, option: str) -> None:
        await self._verwaltung.einstellen(self._device_id, {"modus": option})


class AutomatikAusrichtung(AutomatikEntitaet, SelectEntity):
    """Eco, Ausgewogen oder Komfort – wie früh und kräftig die Automatik eingreift."""

    ART = "ausrichtung"
    _attr_translation_key = "automatik_ausrichtung"
    _attr_options = list(AUSRICHTUNGEN)

    @property
    def current_option(self) -> str | None:
        if not self._laufzeit:
            return None
        return self._laufzeit.konfig.get("ausrichtung") or AUSGEWOGEN

    async def async_select_option(self, option: str) -> None:
        await self._verwaltung.einstellen(self._device_id, {"ausrichtung": option})


class AutomatikZustand(AutomatikEntitaet, SensorEntity):
    """Was die Automatik gerade tut, mit Begründung."""

    ART = "zustand"
    _attr_translation_key = "automatik_zustand"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [zustand.value for zustand in Zustand]
    # Der Satz ändert sich mit jeder Messung; im Verlauf wäre er nur Ballast.
    _unrecorded_attributes = frozenset({"begruendung", "kurz"})

    @property
    def native_value(self) -> str | None:
        return self._laufzeit.zustand.value if self._laufzeit else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        laufzeit = self._laufzeit
        if laufzeit is None:
            return {}
        kurz = regel.kurz(laufzeit.zustand, laufzeit.gedaechtnis, laufzeit.pausiert_bis)
        t = woerterbuch(self.hass)
        return {
            "begruendung": t.satz(laufzeit.begruendung),
            "kurz": t.satz(kurz) if kurz else None,
            "pausiert_bis": laufzeit.pausiert_bis.isoformat() if laufzeit.pausiert_bis else None,
            "eingriffe_heute": laufzeit.steller.stand.eingriffe,
        }


class AutomatikEmpfehlung(AutomatikEntitaet, SensorEntity):
    """Was die Automatik im Modus „Manuell mit Empfehlung“ vorschlägt."""

    ART = "empfehlung"
    _attr_translation_key = "automatik_empfehlung"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["keine", *(zustand.value for zustand in Zustand)]
    _unrecorded_attributes = frozenset({"begruendung"})

    @property
    def native_value(self) -> str | None:
        laufzeit = self._laufzeit
        if laufzeit is None:
            return None
        return laufzeit.empfehlung["zustand"] if laufzeit.empfehlung else "keine"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        empfehlung = self._laufzeit.empfehlung if self._laufzeit else None
        if not empfehlung:
            return {}
        return {
            "begruendung": woerterbuch(self.hass).satz(empfehlung["begruendung"]),
            "seit": empfehlung["seit"],
        }


class AutomatikEmpfehlungTaste(AutomatikEntitaet, ButtonEntity):
    """Die offene Empfehlung übernehmen."""

    ART = "empfehlung_uebernehmen"
    _attr_translation_key = "automatik_empfehlung_uebernehmen"

    @property
    def available(self) -> bool:
        return self._laufzeit is not None and self._laufzeit.empfehlung is not None

    async def async_press(self) -> None:
        await self._verwaltung.empfehlung_uebernehmen(self._device_id)


class AutomatikVerwerfenTaste(AutomatikEmpfehlungTaste):
    """Die offene Empfehlung verwerfen."""

    ART = "empfehlung_verwerfen"
    _attr_translation_key = "automatik_empfehlung_verwerfen"

    async def async_press(self) -> None:
        await self._verwaltung.empfehlung_verwerfen(self._device_id)


class AutomatikWert(AutomatikEntitaet, SensorEntity):
    """Ein Messwert der Automatik; ohne Lauf bleibt er leer."""

    def _wert(self, laufzeit: Laufzeit) -> Any:
        raise NotImplementedError

    @property
    def native_value(self) -> Any:
        laufzeit = self._laufzeit
        return self._wert(laufzeit) if laufzeit is not None else None


class AutomatikGedaempft(AutomatikWert):
    """Die gedämpfte Außentemperatur, mit der die Automatik rechnet."""

    ART = "gedaempft"
    _attr_translation_key = "automatik_gedaempft"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "°C"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def _wert(self, laufzeit: Laufzeit) -> float | None:
        wert = laufzeit.lage.at_gedaempft if laufzeit.lage else None
        return None if wert is None else round(wert, 1)


class AutomatikHeizgrenze(AutomatikWert):
    """Die Heizgrenze der Automatik: die der Steuerung, verschoben um die Ausrichtung."""

    ART = "heizgrenze"
    _attr_translation_key = "automatik_heizgrenze"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "°C"

    def _wert(self, laufzeit: Laufzeit) -> float | None:
        return regel.grenze(laufzeit.lage, laufzeit.werte) if laufzeit.lage else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        laufzeit = self._laufzeit
        if laufzeit is None or laufzeit.lage is None:
            return {}
        return {
            "steuerung": laufzeit.lage.grenze_steuerung,
            "versatz": laufzeit.werte.grenze_versatz,
        }


class AutomatikAbweichung(AutomatikWert):
    """Wie weit die Räume über oder unter ihrem Ziel liegen."""

    ART = "abweichung"
    _attr_translation_key = "automatik_abweichung"
    _attr_native_unit_of_measurement = "K"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def _wert(self, laufzeit: Laufzeit) -> float | None:
        lage, g = laufzeit.lage, laufzeit.gedaechtnis
        soll = g.absenkung_basis or g.saison_soll or (lage.soll if lage else None)
        if lage is None or lage.raum is None or soll is None:
            return None
        return round(regel.abweichung(lage, soll), 2)


class AutomatikSonnenquote(AutomatikWert):
    """Die Sonnenquote des Tages, nach der der Sonnentag entschieden wird."""

    ART = "sonnenquote"
    _attr_translation_key = "automatik_sonnenquote"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def _wert(self, laufzeit: Laufzeit) -> int | None:
        quote = laufzeit.lage.sonnenquote if laufzeit.lage else None
        return None if quote is None else round(quote)


class AutomatikEingriffe(AutomatikWert):
    """Eingriffe an die Steuerung heute; das Budget steht als Attribut."""

    ART = "eingriffe"
    _attr_translation_key = "automatik_eingriffe"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def _wert(self, laufzeit: Laufzeit) -> int:
        return kennzahlen.eingriffe_heute(laufzeit)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"budget": self._laufzeit.werte.budget} if self._laufzeit else {}


class AutomatikLetzterEingriff(AutomatikWert):
    """Wann die Automatik zuletzt an die Steuerung geschrieben hat, und warum."""

    ART = "letzter_eingriff"
    _attr_translation_key = "automatik_letzter_eingriff"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _unrecorded_attributes = frozenset({"text"})

    def _wert(self, laufzeit: Laufzeit) -> datetime | None:
        return kennzahlen.zeit(kennzahlen.letzter_eingriff(laufzeit))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        eintrag = kennzahlen.letzter_eingriff(self._laufzeit) if self._laufzeit else None
        return {"text": woerterbuch(self.hass).satz(eintrag["text"])} if eintrag else {}


class AutomatikNaechsteEntscheidung(AutomatikWert):
    """Die nächste Entscheidungszeit des Profils, heute oder morgen."""

    ART = "naechste_entscheidung"
    _attr_translation_key = "automatik_naechste_entscheidung"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def _wert(self, laufzeit: Laufzeit) -> datetime | None:
        return kennzahlen.naechste_entscheidung(laufzeit)


class AutomatikStoerung(AutomatikEntitaet, BinarySensorEntity):
    """An, wenn die Automatik nicht wie vorgesehen schreiben kann oder Sicherheit greift."""

    ART = "stoerung"
    _attr_translation_key = "automatik_stoerung"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool | None:
        return kennzahlen.gestoert(self._laufzeit) if self._laufzeit else None


KLASSEN: dict[str, type[AutomatikEntitaet]] = {
    "schalter": AutomatikSchalter,
    "modus": AutomatikModus,
    "ausrichtung": AutomatikAusrichtung,
    "zustand": AutomatikZustand,
    "empfehlung": AutomatikEmpfehlung,
    "empfehlung_uebernehmen": AutomatikEmpfehlungTaste,
    "empfehlung_verwerfen": AutomatikVerwerfenTaste,
    "gedaempft": AutomatikGedaempft,
    "heizgrenze": AutomatikHeizgrenze,
    "abweichung": AutomatikAbweichung,
    "sonnenquote": AutomatikSonnenquote,
    "eingriffe": AutomatikEingriffe,
    "letzter_eingriff": AutomatikLetzterEingriff,
    "naechste_entscheidung": AutomatikNaechsteEntscheidung,
    "stoerung": AutomatikStoerung,
}
# Welche Arten eine Plattform anlegt; die Domäne je Art steht in `verwaltung.DOMAENE_JE_ART`.
SENSOR_ARTEN = (
    "zustand",
    "empfehlung",
    "gedaempft",
    "heizgrenze",
    "abweichung",
    "sonnenquote",
    "eingriffe",
    "letzter_eingriff",
    "naechste_entscheidung",
)
TASTEN_ARTEN = ("empfehlung_uebernehmen", "empfehlung_verwerfen")


@callback
def anmelden(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback, art: str
) -> None:
    """Entitäten einer Art anlegen – jetzt und für später eingerichtete Automatiken."""
    verwaltung = verwaltung_holen(hass)
    bekannt: set[str] = set()

    @callback
    def _anlegen() -> None:
        eigene = {
            device_id
            for device_id, laufzeit in verwaltung.laufzeiten.items()
            if laufzeit.entry_id == entry.entry_id
        }
        bekannt.intersection_update(eigene)
        neu = [KLASSEN[art](verwaltung, device_id) for device_id in eigene - bekannt]
        bekannt.update(eigene)
        if neu:
            async_add_entities(neu, config_subentry_id=verwaltung.subeintrag(entry))

    _anlegen()
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEU.format(entry.entry_id), _anlegen)
    )
