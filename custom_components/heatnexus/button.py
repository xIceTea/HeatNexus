"""Button platform for the Windhager integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .automatik.entitaeten import TASTEN_ARTEN
from .automatik.entitaeten import anmelden as automatik_anmelden
from .client.gemeinsam import gnmn_aus_oid
from .const import FCT_ENTITY_MAP, NACHFASS_FOLGEN
from .entity import WindhagerEntity, async_setup_entities

# Der Coordinator holt jeden Wert gebündelt, und die Anfragen an die Anlage
# begrenzt der Client über seine eigene Warteschlange. Eine zweite Bremse in
# Home Assistant würde nur den Abruf verzögern, den es gar nicht gibt.
PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Windhager buttons from a config entry."""
    for art in TASTEN_ARTEN:
        automatik_anmelden(hass, entry, async_add_entities, art)
    async_setup_entities(
        hass,
        entry,
        async_add_entities,
        {"button": WindhagerButton, "refresh": WindhagerAbfrageTaste},
    )


class WindhagerButton(WindhagerEntity, ButtonEntity):
    """Button that writes a fixed value to a datapoint when pressed.

    Used e.g. for "Serviceausbrand starten" (writes 6 to 9/75) and
    "Sonden zurücksetzen". For destructive actions add a confirmation in
    the dashboard:

        type: button
        entity: button.purowin_serviceausbrand_starten
        confirmation:
          text: Serviceausbrand wirklich starten? Der Vorgang dauert ca. 1 Stunde
                und kann nicht abgebrochen werden.
    """

    _require_value_for_available = False
    # Ihr Wert wird nie angezeigt; zyklisch gelesen kostet er nur eine Anfrage.
    _register_poll_oid = False

    def __init__(self, coordinator, device_info: dict) -> None:
        super().__init__(coordinator, device_info)
        self._press_value = device_info.get("press_value", "1")

    async def async_press(self) -> None:
        _LOGGER.debug(
            "Taste %s schreibt %s auf %s",
            self.name,
            self._press_value,
            self._oid,
        )
        await self._async_write(self._press_value)

    def _nachfassen(self, erwartet: str | None = None) -> None:
        """Statt der eigenen Adresse, die nirgends erscheint, das lesen, was die Taste verändert."""
        folgen = self._folgewerte() if self.hass else []
        if not folgen:
            super()._nachfassen(erwartet)
            return
        bekannt = (self.coordinator.data or {}).get("oids", {})
        vorher = {oid: bekannt.get(oid) for oid in folgen}
        self.coordinator.nachfassen(folgen, anzahl=NACHFASS_FOLGEN, vorher=vorher)

    def _folgewerte(self) -> list[str]:
        """Was die Taste an der Anlage verändert; es steht sonst erst im nächsten Takt da."""
        eigene = f"/{gnmn_aus_oid(self._oid)}/0"
        praefix = self._oid.removesuffix(eigene)
        for definition in FCT_ENTITY_MAP.get(self._descriptor.get("fct_type"), ()):
            # Mehrere Tasten schreiben denselben Wert auf `9/75`; erst das Kennungsende trennt sie.
            endung = definition.get("key_suffix")
            if (
                definition["oid"] == eigene
                and definition.get("press_value") == self._press_value
                and (not endung or str(self._descriptor.get("id", "")).endswith(f"-{endung}"))
            ):
                # Was nicht im Abrufplan steht, zeigt niemand an; es zu lesen kostete nur Anfragen.
                bekannt = self.coordinator.client.abrufplan
                folgen = (f"{praefix}/{a}/0" for a in definition.get("nachlesen", ()))
                return [oid for oid in folgen if oid in bekannt]
        return []


class WindhagerAbfrageTaste(WindhagerEntity, ButtonEntity):
    """Liest die Werte eines Anlagenteils sofort, statt auf den Takt zu warten."""

    _require_value_for_available = False

    async def async_press(self) -> None:
        oids = self.coordinator.client.geraet_oids(self._descriptor.get("device_id"))
        if oids:
            await self.coordinator.werte_nachlesen(oids)
