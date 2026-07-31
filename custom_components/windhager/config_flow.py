"""Einrichtung der Integration über die Oberfläche."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .client import WindhagerHttpClient
from .const import (
    ALL_LEVELS,
    CONF_ENABLE_ADVANCED,
    CONF_LEVELS,
    CONF_UPDATE_INTERVAL,
    CONF_WRITABLE_ADVANCED,
    DEFAULT_LEVELS,
    DOMAIN,
    LEVEL_INFO,
    LEVEL_OPERATE,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    UPDATE_INTERVAL,
)
from .exceptions import CannotConnect, InvalidAuth

_LOGGER = logging.getLogger(__name__)


def clean_host(raw: str) -> str:
    """Aus einer Eingabe die reine Adresse gewinnen (URL, Port, Pfad entfernen)."""
    host = raw.strip().rstrip("/")
    if "://" in host:
        parsed = urlparse(host)
        host = parsed.netloc or parsed.path
    host = host.split("/")[0]
    if ":" in host:
        host = host.split(":")[0]
    return host.strip("/")


async def validate_connection(host: str, password: str) -> None:
    """Prüfen, ob die Anlage antwortet und das Passwort stimmt."""
    client = WindhagerHttpClient(host=host, password=password)
    try:
        data, status = await client.probe()
    finally:
        await client.close()

    if status in (401, 403):
        raise InvalidAuth
    if status != 200 or not isinstance(data, list):
        raise CannotConnect


def level_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Auswahl der Bedienebenen und des Abfrageintervalls."""
    return vol.Schema(
        {
            vol.Required(
                CONF_LEVELS, default=list(defaults.get(CONF_LEVELS, DEFAULT_LEVELS))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[SelectOptionDict(value=lvl, label=lvl) for lvl in ALL_LEVELS],
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                    translation_key="levels",
                )
            ),
            vol.Required(
                CONF_ENABLE_ADVANCED,
                default=bool(defaults.get(CONF_ENABLE_ADVANCED, False)),
            ): bool,
            vol.Required(
                CONF_WRITABLE_ADVANCED,
                default=bool(defaults.get(CONF_WRITABLE_ADVANCED, False)),
            ): bool,
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=int(defaults.get(CONF_UPDATE_INTERVAL, UPDATE_INTERVAL)),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_UPDATE_INTERVAL,
                    max=MAX_UPDATE_INTERVAL,
                    step=5,
                    unit_of_measurement="s",
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


def normalize_options(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Eingaben in gültige Optionen überführen."""
    levels = [lvl for lvl in raw.get(CONF_LEVELS, DEFAULT_LEVELS) if lvl in ALL_LEVELS]
    # Ohne Info- und Betreiberebene bliebe die Anlage stumm bzw. unbedienbar.
    for required in (LEVEL_INFO, LEVEL_OPERATE):
        if required not in levels:
            levels.append(required)
    return {
        CONF_LEVELS: [lvl for lvl in ALL_LEVELS if lvl in levels],
        CONF_ENABLE_ADVANCED: bool(raw.get(CONF_ENABLE_ADVANCED, False)),
        CONF_WRITABLE_ADVANCED: bool(raw.get(CONF_WRITABLE_ADVANCED, False)),
        CONF_UPDATE_INTERVAL: int(raw.get(CONF_UPDATE_INTERVAL, UPDATE_INTERVAL)),
    }


class WindhagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Einrichtungsdialog: erst die Anlage, dann der Umfang."""

    VERSION = 1

    def __init__(self) -> None:
        """Zwischenstand des Dialogs."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Adresse und Service-Passwort abfragen."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = clean_host(user_input[CONF_HOST])
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()
            try:
                await validate_connection(host, user_input[CONF_PASSWORD])
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unerwarteter Fehler beim Verbinden mit %s", host)
                errors["base"] = "unknown"
            else:
                self._data = {CONF_HOST: host, CONF_PASSWORD: user_input[CONF_PASSWORD]}
                return await self.async_step_scope()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )

    async def async_step_scope(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Bedienebenen und Abfrageintervall wählen."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"Windhager ({self._data[CONF_HOST]})",
                data=self._data,
                options=normalize_options(user_input),
            )

        return self.async_show_form(step_id="scope", data_schema=level_schema({}))

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Nach abgelehnter Anmeldung ein neues Passwort erfragen."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Neues Passwort prüfen und übernehmen."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_connection(entry.data[CONF_HOST], user_input[CONF_PASSWORD])
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={"host": entry.data[CONF_HOST]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> WindhagerOptionsFlow:
        """Optionen dieser Integration."""
        return WindhagerOptionsFlow()


class WindhagerOptionsFlow(OptionsFlow):
    """Umfang und Abfrageintervall nachträglich ändern."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Gleiche Auswahl wie bei der Einrichtung."""
        if user_input is not None:
            return self.async_create_entry(data=normalize_options(user_input))

        return self.async_show_form(
            step_id="init", data_schema=level_schema(self.config_entry.options)
        )
