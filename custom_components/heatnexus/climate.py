"""Support for Windhager Climate."""

from __future__ import annotations

import asyncio
import logging
import time

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import voluptuous as vol

from .entity import async_setup_entities, geraet_info
from .exceptions import WindhagerValueError
from .helpers import get_oid_value

_LOGGER = logging.getLogger(__name__)

# Raumtemperatur-Sollwertgrenzen laut Betreiberebene (3/51, 3/53: 10..30 °C)
MIN_TEMP = 10.0
MAX_TEMP = 30.0

# Dauer des Komfort-Overrides in Minuten (so wie die Windhager-App: sie
# schreibt 3/4 = Temperatur + 2/10 = Dauer; beobachtet wurden 180 min).
OVERRIDE_DURATION_MIN = 180
# Obergrenze der Dauer (2/10), wie die Anlage sie selbst meldet: 0 bis 400 min.
OVERRIDE_DURATION_MAX = 400

# Betriebswahl (3/50), in die für eine befristete Vorgabe geschaltet wird, wenn
# der Kreis gerade aus ist. „Programm 1" ist das erste Heizprogramm und die
# Voreinstellung der Anlage.
HEIZPROGRAMM = 1

# Merker für den Rücksprung. Er steht in den Attributen, damit er einen
# Neustart von Home Assistant übersteht: Sonst bliebe ein Heizkreis, dessen
# Vorgabe während des Neustarts abläuft, für immer im Heizprogramm stehen.
ATTR_MODUS_DAVOR = "modus_vor_vorgabe"

# Schneller Nachlade-Burst nach einer Climate-Bedienung: das Gerät übernimmt
# sofort, der normale 30-s-Poll ist aber zu träge. Daher kurz hochfrequent nur
# die Climate-Werte nachladen (Anzahl x Intervall-Sekunden).
FAST_REFRESH_COUNT = 6
FAST_REFRESH_INTERVAL = 3

# Sicherheits-Fallback: spätestens nach dieser Zeit wird der optimistische
# Sollwert verworfen, auch wenn das Gerät ihn nie exakt bestätigt.
OPTIMISTIC_MAX_AGE_S = 120


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Windhager climates from a config entry."""
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_current_temp_compensation",
        {
            vol.Required("compensation"): vol.All(vol.Coerce(float), vol.Range(min=-3.0, max=3.0)),
        },
        "set_current_temp_compensation",
    )
    # Eco und Comfort sind dieselbe befristete Vorgabe wie ein gesetzter
    # Sollwert, nur mit eigener Dauer. Als Dienst statt als zwei
    # Zahlen-Entitäten, damit die Umschaltung aus einem Aus-Modus für alle
    # Wege gilt – Oberfläche, Automation und Sprachassistent.
    platform.async_register_entity_service(
        "set_vorgabe",
        {
            vol.Required("temperature"): vol.All(
                vol.Coerce(float), vol.Range(min=MIN_TEMP, max=MAX_TEMP)
            ),
            vol.Optional("duration", default=OVERRIDE_DURATION_MIN): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=OVERRIDE_DURATION_MAX)
            ),
        },
        "async_set_vorgabe",
    )

    async_setup_entities(hass, entry, async_add_entities, {"climate": WindhagerThermostatClimate})


class WindhagerBaseThermostat(CoordinatorEntity, RestoreEntity, ClimateEntity):
    """Base class for Windhager thermostats."""

    # Das Thermostat ist die Hauptfunktion seines Geräts und trägt deshalb
    # keinen eigenen Namen: Es heißt wie der Heizkreis, an dem es hängt.
    _attr_has_entity_name = True
    _attr_name = None

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = 0.5
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator, device_info: dict):
        """Initialize the thermostat."""
        super().__init__(coordinator)
        self.client = self.coordinator.client
        self._id = device_info.get("id", "")
        self._name = device_info.get("name", "")
        # IMPORTANT: prefix now contains node AND function id ("/1/15/0").
        # The old code used only the node id and hardcoded fctId 0 in every
        # path, which silently broke for any function with fctId != 0.
        self._prefix = device_info.get("prefix", "")
        # Presets auf die vom Gerät gemeldeten Betriebswahl-Werte einschränken
        # (z.B. hat ein Heizkreis ohne WW keinen Modus 6 "WW-Betrieb")
        allowed = device_info.get("preset_allowed")
        if allowed:
            self._preset_modes = [str(v) for v in allowed if 0 <= v <= 7]
        else:
            self._preset_modes = ["0", "1", "2", "3", "4", "5", "6", "7"]
        self._attr_translation_key = "heatnexus_climate"
        # Optimistisch gesetzter Sollwert: wird sofort angezeigt und beim
        # nächsten Coordinator-Update (das den geschriebenen Wert vom Gerät
        # zurückliest) wieder verworfen. Verhindert das "Zurückspringen" des
        # Schiebereglers während der ~Sekunden bis zum nächsten Poll.
        self._optimistic_target: float | None = None
        self._optimistic_ts: float = 0.0
        # Optimistische Betriebswahl (Modus/Voreinstellung) – sofort anzeigen,
        # bis der Poll den neuen Wert bestätigt.
        self._optimistic_mode: int | None = None
        self._optimistic_mode_ts: float = 0.0
        # Betriebswahl, in die nach Ablauf einer befristeten Vorgabe
        # zurückgesprungen wird. None heißt: kein Rücksprung vorgemerkt.
        self._modus_davor: int | None = None
        self._device_info = geraet_info(coordinator, device_info)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Frische Gerätedaten eingetroffen.

        Den optimistisch gesetzten Wert (deine Eingabe) anzeigen, BIS ein Poll
        ihn bestätigt – d.h. erst verwerfen, wenn der zurückgelesene Sollwert
        (1/1) ~dem gesetzten Wert entspricht. So springt die Anzeige nicht
        kurz auf den alten Wert, während das Gerät noch nachzieht. Zeit-Fallback
        verhindert ein dauerhaftes Hängenbleiben.
        """
        now = time.monotonic()
        if self._optimistic_target is not None:
            actual = self.get_oid_value("/1/1/0")
            confirmed = actual is not None and abs(actual - self._optimistic_target) < 0.3
            expired = (now - self._optimistic_ts) > OPTIMISTIC_MAX_AGE_S
            if confirmed or expired:
                self._optimistic_target = None
        if self._optimistic_mode is not None:
            # WICHTIG: direkt 3/50 lesen (nicht raw_selected_mode, das gäbe den
            # optimistischen Wert zurück und würde nie bestätigen).
            raw = self.get_oid_value("/3/50/0")
            actual_mode = int(raw) if raw is not None else None
            confirmed = actual_mode == self._optimistic_mode
            expired = (now - self._optimistic_mode_ts) > OPTIMISTIC_MAX_AGE_S
            if confirmed or expired:
                self._optimistic_mode = None
        self._ruecksprung_pruefen()
        super()._handle_coordinator_update()

    @callback
    def _ruecksprung_pruefen(self) -> None:
        """Nach Ablauf einer befristeten Vorgabe in den alten Modus zurück.

        Vorgemerkt wird nur, wenn für die Vorgabe überhaupt umgeschaltet werden
        musste – also aus Standby oder WW-Betrieb heraus.

        Zurückgesprungen wird ausschließlich aus genau dem Heizprogramm, in das
        umgeschaltet wurde. Hat jemand die Betriebswahl inzwischen selbst
        verstellt, ist das eine Entscheidung; sie zu überschreiben wäre
        übergriffig. Der Merker fällt dann einfach weg.
        """
        if self._modus_davor is None:
            return
        if self.raw_custom_temp_remaining_time() > 0:
            return

        roh = self.get_oid_value("/3/50/0")
        jetzt = int(roh) if roh is not None else None
        ziel, self._modus_davor = self._modus_davor, None
        if jetzt != HEIZPROGRAMM:
            _LOGGER.debug("Rücksprung entfällt: Betriebswahl steht auf %s", jetzt)
            return

        self._set_optimistic_mode(ziel)
        self.hass.async_create_task(self._modus_schreiben(ziel))

    async def _modus_schreiben(self, modus: int) -> None:
        """Die Betriebswahl setzen; ein Fehler darf die Anzeige nicht zerreißen."""
        try:
            await self.client.update(f"{self._prefix}/3/50/0", str(modus))
        except Exception as err:  # pragma: no cover - Gerätefehler
            _LOGGER.warning("Rücksprung auf Betriebswahl %s fehlgeschlagen: %s", modus, err)

    async def async_added_to_hass(self) -> None:
        """Einen vorgemerkten Rücksprung über den Neustart hinweg übernehmen.

        Ohne das bliebe ein Heizkreis, dessen Vorgabe während eines Neustarts
        abläuft, für immer im Heizprogramm stehen.
        """
        await super().async_added_to_hass()
        if (letzter := await self.async_get_last_state()) is None:
            return
        gemerkt = letzter.attributes.get(ATTR_MODUS_DAVOR)
        if gemerkt is None:
            return
        try:
            self._modus_davor = int(gemerkt)
        except (TypeError, ValueError):
            _LOGGER.debug("Vorgemerkter Modus %r unlesbar", gemerkt)

    @property
    def unique_id(self) -> str:
        return self._id

    @property
    def device_info(self) -> DeviceInfo:
        return self._device_info

    @property
    def preset_modes(self) -> list[str]:
        return self._preset_modes

    def get_oid_value(self, path: str) -> float | None:
        """Get OID value relative to this function's prefix."""
        return get_oid_value(self.coordinator, path, self._prefix)

    def _optimistisch_gueltig(self, seit: float) -> bool:
        """Ob eine optimistische Anzeige noch gelten darf.

        **Zeit statt Takt.** Bis 1.5.0 wurde der Ablauf nur in
        `_handle_coordinator_update` geprüft – also nur, wenn der Coordinator
        die Zuhörer benachrichtigt. Seit der Coordinator unveränderte Daten
        stillschweigend verwirft (`always_update=False`), gibt es diesen Takt
        nicht mehr zwangsläufig: Nimmt die Anlage einen Schreibvorgang nicht
        an, ändert sich nichts, es feuert nichts, und die optimistische
        Anzeige bliebe für immer stehen. Genau der Fall, den die Zeitgrenze
        abfangen soll.
        """
        return (time.monotonic() - seit) <= OPTIMISTIC_MAX_AGE_S

    def raw_selected_mode(self) -> int | None:
        """Get selected mode (Betriebswahl 3/50), optimistisch bevorzugt."""
        if self._optimistic_mode is not None and self._optimistisch_gueltig(
            self._optimistic_mode_ts
        ):
            return self._optimistic_mode
        value = self.get_oid_value("/3/50/0")
        return int(value) if value is not None else None

    def raw_custom_temp_remaining_time(self) -> int:
        """Get remaining time of a manual temperature override (2/10)."""
        value = self.get_oid_value("/2/10/0")
        return int(value) if value is not None else 0

    # Betriebswahl-Werte, in denen der HEIZKREIS nicht heizt und das
    # Thermostat als "Aus" gelten soll:
    #   0 = Standby (Frostschutz, Sollwert ~5 °C)
    #   6 = WW-Betrieb (nur Warmwasser, Heizkörper aus)
    # So zeigt z.B. das Wohnhaus im WW-Betrieb korrekt "Aus" statt "Leerlauf",
    # während der Modus (preset) weiterhin "WW-Betrieb" anzeigt.
    OFF_MODES = {0, 6}

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation mode."""
        mode = self.raw_selected_mode()
        if mode is None or mode in self.OFF_MODES:
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> str:
        """Return the current running hvac operation."""
        mode = self.raw_selected_mode()
        if mode is None or mode in self.OFF_MODES:
            return HVACAction.OFF
        pump = self.get_oid_value("/1/20/0")
        if pump is not None:
            return HVACAction.HEATING if pump != 0 else HVACAction.IDLE
        return HVACAction.HEATING

    @property
    def extra_state_attributes(self) -> dict:
        """Zusatzinfos: Override-Restzeit (Timer) als Feedback nach dem Setzen."""
        remaining = self.raw_custom_temp_remaining_time()  # 2/10 in Minuten
        attrs = {
            "override_aktiv": remaining > 0,
            "override_restzeit_min": remaining,
        }
        mode = self.raw_selected_mode()
        if mode is not None:
            attrs["betriebswahl"] = mode
        if self._modus_davor is not None:
            attrs[ATTR_MODUS_DAVOR] = self._modus_davor
        return attrs

    # ------------------------------------------------------------------
    # Schneller Nachlade-Burst (fängt den Poll-Delay nach einer Bedienung ab)
    # ------------------------------------------------------------------
    def _start_fast_refresh(self) -> None:
        """Kurzen, gezielten Nachlade-Burst der Climate-Werte anstoßen."""
        self.hass.async_create_task(self._fast_refresh_burst())

    async def _fast_refresh_burst(self) -> None:
        oids = self.client.climate_oids(self._prefix)
        for _ in range(FAST_REFRESH_COUNT):
            await asyncio.sleep(FAST_REFRESH_INTERVAL)
            try:
                updated = await self.client.fetch_oids(oids)
            except Exception:
                break
            data = self.coordinator.data
            if data is not None and updated:
                data.setdefault("oids", {}).update(updated)
                # nur die Listener benachrichtigen (kein voller Geräte-Poll)
                self.coordinator.async_update_listeners()

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        # Frisch gewählte Voreinstellung sofort zeigen (ohne "7"-Override-Logik).
        if (
            (
                self._optimistic_mode is None
                or not self._optimistisch_gueltig(self._optimistic_mode_ts)
            )
            and self.raw_custom_temp_remaining_time() > 0
            and "7" in self._preset_modes
        ):
            return "7"
        mode = self.raw_selected_mode()
        if mode is None:
            return None
        key = str(mode)
        return key if key in self._preset_modes else None

    def _set_optimistic_mode(self, mode: int) -> None:
        """Betriebswahl sofort optimistisch anzeigen (Modus + Voreinstellung)."""
        self._optimistic_mode = mode
        self._optimistic_mode_ts = time.monotonic()
        # frische Eingabe gewinnt: alten optimistischen Sollwert nicht behalten
        self._optimistic_target = None
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode (Betriebswahl)."""
        if preset_mode not in self._preset_modes:
            raise WindhagerValueError(f"Unsupported preset {preset_mode}")
        # Sofort anzeigen (z.B. WW-Betrieb -> Heizprogramm 1 bleibt stehen, und
        # bei Heizmodi springt hvac_mode sofort auf HEIZEN).
        self._set_optimistic_mode(int(preset_mode))
        await self.client.update(f"{self._prefix}/3/50/0", preset_mode)

        # Cancel a running manual temperature override
        if self.raw_custom_temp_remaining_time() > 0:
            await self.client.update(f"{self._prefix}/2/10/0", "0")
        self._start_fast_refresh()

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode (OFF = Standby, HEAT = Programm 1)."""
        new_mode = 0 if hvac_mode == HVACMode.OFF else 1
        self._set_optimistic_mode(new_mode)
        await self.client.update(f"{self._prefix}/3/50/0", str(new_mode))
        self._start_fast_refresh()

    async def async_set_temperature(self, **kwargs) -> None:
        """Set the room comfort setpoint as a timed override (like the app)."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            raise WindhagerValueError("No temperature provided")
        await self.async_set_vorgabe(float(temp), OVERRIDE_DURATION_MIN)

    async def async_set_vorgabe(self, temperature: float, duration: float) -> None:
        """Eine befristete Vorgabe schreiben – Temperatur und Dauer.

        Per Geräte-Probe bestätigt: Einen Sollwert setzen heißt beim Windhager
        einen befristeten Komfort-Override schreiben:
          3/4  = gewünschte Temperatur
          2/10 = Dauer in Minuten (Resthandzeit/Timer)
        Der aktive Sollwert erscheint dann in 1/1 (von dort lesen wir zurück).
        3/51 ("Heizbetrieb") ist NICHT der aktive Sollwert (blieb in der Probe
        konstant) – das war der Fehler in v0.6.2.

        **Eco und Comfort gehen denselben Weg.** Bis 1.3.1 schrieben die beiden
        Tasten der Oberfläche `3/4` und `2/10` als Zahlenwerte direkt an der
        Klimaentität vorbei. Damit fehlte ihnen genau das, was hier darunter
        steht: die Umschaltung aus einem Aus-Modus. Im WW-Betrieb setzte die
        Anlage daraufhin nur den Timer, nicht die Temperatur – es lief eine
        Vorgabe, aber keine Wärmeanforderung, und die Rückmeldung wartete auf
        eine Bestätigung, die nie kam.

        Hinweis: Ohne angeschlossenen Raumfühler regelt die Anlage über die
        Heizkurve; der Override verschiebt den Raum-Sollwert befristet, eine
        echte Raumtemperaturregelung ist ohne Fühler aber nicht möglich.
        """
        # Im Aus/WW-Betrieb ist der Heizkreis aus: Das Gerät setzt dann nur den
        # Timer und übernimmt die Temperatur nicht. Bis 1.3.1 wurde der Versuch
        # deshalb abgelehnt – nur hilft das niemandem, der aus dem WW-Betrieb
        # heraus kurz heizen will. Stattdessen wird für die Dauer der Vorgabe
        # in ein Heizprogramm geschaltet und danach zurückgesprungen.
        mode = self.raw_selected_mode()
        if mode is None:
            raise WindhagerValueError(
                "Betriebswahl unbekannt – bitte warten, bis die Anlage gelesen ist."
            )
        if mode in self.OFF_MODES:
            self._modus_davor = mode
            self._set_optimistic_mode(HEIZPROGRAMM)
            await self.client.update(f"{self._prefix}/3/50/0", str(HEIZPROGRAMM))
            _LOGGER.debug(
                "Vorgabe aus Modus %s: schalte auf Programm %s, Rücksprung vorgemerkt",
                mode,
                HEIZPROGRAMM,
            )

        temp = max(MIN_TEMP, min(MAX_TEMP, float(temperature)))
        dauer = max(0, min(OVERRIDE_DURATION_MAX, round(float(duration))))

        # Sofort anzeigen, dann Override + Dauer schreiben und Refresh anstoßen.
        self._optimistic_target = temp
        self._optimistic_ts = time.monotonic()
        self.async_write_ha_state()
        await self.client.update(f"{self._prefix}/3/4/0", f"{temp:.1f}")
        await self.client.update(f"{self._prefix}/2/10/0", str(dauer))
        self._start_fast_refresh()


class WindhagerThermostatClimate(WindhagerBaseThermostat):
    """Windhager heating-circuit climate (Heizkreis)."""

    @property
    def current_temperature(self) -> float | None:
        # Gemessene Raumtemperatur (0/1). Ohne Raumfühler liefert das Gerät
        # "-.-" -> None, die Karte zeigt dann korrekt keine Ist-Temperatur.
        return self.get_oid_value("/0/1/0")

    @property
    def target_temperature(self) -> float | None:
        # Aktiver Raum-Sollwert (1/1): zeigt im Heizprogramm die geplante
        # Temperatur, im Heiz-/Absenkbetrieb den jeweiligen Sollwert und in
        # Aus/WW-Betrieb korrekt den Frostwert. Direkt nach dem Setzen kurz der
        # optimistische Wert, bis das Gerät 1/1 nachzieht.
        if self._optimistic_target is not None and self._optimistisch_gueltig(self._optimistic_ts):
            return self._optimistic_target
        return self.get_oid_value("/1/1/0")

    async def set_current_temp_compensation(self, compensation: float) -> None:
        """Set the heating-curve comfort correction (Behaglichkeit, 3/58)."""
        await self.client.update(f"{self._prefix}/3/58/0", f"{compensation:.1f}")
        await self.coordinator.async_request_refresh()
