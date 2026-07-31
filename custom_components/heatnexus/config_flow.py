"""Einrichtung der Integration über die Oberfläche.

Ein Konfigurationseintrag bündelt eine Heizungsanlage, die aus mehreren
Steuerungen bestehen kann (z.B. Heizhaus und Wohnhaus mit je eigener
Adresse). In Home Assistant erscheint das als ein Gerät mit Untergeräten.
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any
from urllib.parse import urlparse

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD
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
import voluptuous as vol

from .client import WindhagerHttpClient
from .const import (
    ALL_LEVELS,
    CONF_COUNT,
    CONF_ENABLE_ADVANCED,
    CONF_LABEL,
    CONF_LEVELS,
    CONF_SYSTEMS,
    CONF_UPDATE_INTERVAL,
    CONF_WRITABLE_ADVANCED,
    DEFAULT_LEVELS,
    DOMAIN,
    LEVEL_INFO,
    LEVEL_OPERATE,
    MAX_SYSTEMS,
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


async def validate_connection(host: str, password: str) -> list:
    """Prüfen, ob die Anlage antwortet, und ihre Struktur zurückgeben."""
    client = WindhagerHttpClient(host=host, password=password)
    try:
        data, status = await client.probe()
    finally:
        await client.close()

    if status in (401, 403):
        raise InvalidAuth
    if status != 200 or not isinstance(data, list):
        raise CannotConnect
    return data


def beschreibe(struktur: list) -> str:
    """Kurzfassung dessen, was die Anlage meldet."""
    namen = []
    for knoten in struktur:
        for funktion in knoten.get("functions", []):
            if not funktion.get("lock") and funktion.get("fctType", -1) >= 0:
                namen.append(str(funktion.get("name", "")).strip())
    return ", ".join(dict.fromkeys(n for n in namen if n)) or "keine Funktionen gemeldet"


def level_schema(defaults: Mapping[str, Any], mit_intervall: bool = True) -> vol.Schema:
    """Auswahl der Bedienebenen (und des Abfrageintervalls)."""
    felder: dict = {
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
            CONF_ENABLE_ADVANCED, default=bool(defaults.get(CONF_ENABLE_ADVANCED, False))
        ): bool,
        vol.Required(
            CONF_WRITABLE_ADVANCED, default=bool(defaults.get(CONF_WRITABLE_ADVANCED, False))
        ): bool,
    }
    if mit_intervall:
        felder[
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=int(defaults.get(CONF_UPDATE_INTERVAL, UPDATE_INTERVAL)),
            )
        ] = NumberSelector(
            NumberSelectorConfig(
                min=MIN_UPDATE_INTERVAL,
                max=MAX_UPDATE_INTERVAL,
                step=5,
                unit_of_measurement="s",
                mode=NumberSelectorMode.BOX,
            )
        )
    return vol.Schema(felder)


def normalize_options(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Eingaben zu den Bedienebenen prüfen und vereinheitlichen."""
    levels = [lvl for lvl in raw.get(CONF_LEVELS, DEFAULT_LEVELS) if lvl in ALL_LEVELS]
    # Ohne Info- und Betreiberebene bliebe die Anlage stumm bzw. unbedienbar.
    for pflicht in (LEVEL_INFO, LEVEL_OPERATE):
        if pflicht not in levels:
            levels.append(pflicht)
    ergebnis: dict[str, Any] = {
        CONF_LEVELS: [lvl for lvl in ALL_LEVELS if lvl in levels],
        CONF_ENABLE_ADVANCED: bool(raw.get(CONF_ENABLE_ADVANCED, False)),
        CONF_WRITABLE_ADVANCED: bool(raw.get(CONF_WRITABLE_ADVANCED, False)),
    }
    if CONF_UPDATE_INTERVAL in raw:
        ergebnis[CONF_UPDATE_INTERVAL] = int(raw[CONF_UPDATE_INTERVAL])
    return ergebnis


class WindhagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Führt durch Name, Anzahl der Anlagen, deren Adressen und den Umfang."""

    VERSION = 2

    def __init__(self) -> None:
        """Zwischenstand des Dialogs."""
        self._name: str = "Heizung"
        self._anzahl: int = 1
        self._systeme: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Name der Heizungsanlage und Anzahl der Steuerungen."""
        if user_input is not None:
            self._name = user_input[CONF_NAME].strip() or "Heizung"
            self._anzahl = int(user_input[CONF_COUNT])
            self._systeme = []
            return await self.async_step_system()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default="Heizung"): str,
                    vol.Required(CONF_COUNT, default=1): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=MAX_SYSTEMS, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
        )

    async def async_step_system(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Bezeichnung, Adresse und Passwort je Steuerung."""
        nummer = len(self._systeme) + 1
        errors: dict[str, str] = {}

        if user_input is not None:
            host = clean_host(user_input[CONF_HOST])
            if any(s[CONF_HOST] == host for s in self._systeme):
                errors["base"] = "already_configured"
            else:
                try:
                    struktur = await validate_connection(host, user_input[CONF_PASSWORD])
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unerwarteter Fehler beim Verbinden mit %s", host)
                    errors["base"] = "unknown"
                else:
                    self._systeme.append(
                        {
                            CONF_LABEL: user_input[CONF_LABEL].strip() or host,
                            CONF_HOST: host,
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            "gefunden": beschreibe(struktur),
                        }
                    )
                    if len(self._systeme) < self._anzahl:
                        return await self.async_step_system()
                    return await self.async_step_scope()

        return self.async_show_form(
            step_id="system",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LABEL, default=f"Anlage {nummer}"): str,
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={"nummer": str(nummer), "anzahl": str(self._anzahl)},
        )

    async def async_step_scope(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Bedienebenen und Abfrageintervall festlegen."""
        if user_input is not None:
            gemeinsam = normalize_options(user_input)
            intervall = gemeinsam.pop(CONF_UPDATE_INTERVAL, UPDATE_INTERVAL)
            options: dict[str, Any] = {CONF_UPDATE_INTERVAL: intervall}
            # Die Auswahl gilt zunächst für alle Anlagen; sie lässt sich
            # später je Anlage getrennt ändern.
            for system in self._systeme:
                options[system[CONF_HOST]] = dict(gemeinsam)

            await self.async_set_unique_id("-".join(sorted(s[CONF_HOST] for s in self._systeme)))
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=self._name,
                data={
                    CONF_NAME: self._name,
                    CONF_SYSTEMS: [
                        {
                            CONF_LABEL: s[CONF_LABEL],
                            CONF_HOST: s[CONF_HOST],
                            CONF_PASSWORD: s[CONF_PASSWORD],
                        }
                        for s in self._systeme
                    ],
                },
                options=options,
            )

        uebersicht = "\n".join(
            f"- **{s[CONF_LABEL]}** ({s[CONF_HOST]}): {s['gefunden']}" for s in self._systeme
        )
        return self.async_show_form(
            step_id="scope",
            data_schema=level_schema({}),
            description_placeholders={"gefunden": uebersicht},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Nach abgelehnter Anmeldung ein neues Passwort erfragen."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Passwort einer Anlage erneuern."""
        entry = self._get_reauth_entry()
        systeme = entry.data.get(CONF_SYSTEMS, [])
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                await validate_connection(host, user_input[CONF_PASSWORD])
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                neu = [
                    {**s, CONF_PASSWORD: user_input[CONF_PASSWORD]} if s[CONF_HOST] == host else s
                    for s in systeme
                ]
                return self.async_update_reload_and_abort(entry, data_updates={CONF_SYSTEMS: neu})

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=systeme[0][CONF_HOST] if systeme else ""
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=s[CONF_HOST],
                                    label=f"{s[CONF_LABEL]} ({s[CONF_HOST]})",
                                )
                                for s in systeme
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> WindhagerOptionsFlow:
        """Optionen dieser Integration."""
        return WindhagerOptionsFlow()


class WindhagerOptionsFlow(OptionsFlow):
    """Umfang je Anlage und Abfrageintervall nachträglich ändern."""

    def __init__(self) -> None:
        """Zwischenstand."""
        self._host: str | None = None

    def _systeme(self) -> list[dict[str, Any]]:
        return self.config_entry.data.get(CONF_SYSTEMS, [])

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Auswahl: allgemeine Einstellungen oder eine bestimmte Anlage."""
        systeme = self._systeme()
        if len(systeme) <= 1:
            self._host = systeme[0][CONF_HOST] if systeme else ""
            return await self.async_step_system()

        return self.async_show_menu(
            step_id="init",
            menu_options=["allgemein", *[f"anlage_{i}" for i in range(len(systeme))]],
        )

    async def async_step_allgemein(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abfrageintervall für alle Anlagen."""
        options = dict(self.config_entry.options)
        if user_input is not None:
            options[CONF_UPDATE_INTERVAL] = int(user_input[CONF_UPDATE_INTERVAL])
            return self.async_create_entry(data=options)

        return self.async_show_form(
            step_id="allgemein",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=int(options.get(CONF_UPDATE_INTERVAL, UPDATE_INTERVAL)),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_UPDATE_INTERVAL,
                            max=MAX_UPDATE_INTERVAL,
                            step=5,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
        )

    async def async_step_system(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Bedienebenen einer Anlage."""
        options = dict(self.config_entry.options)
        host = self._host or ""
        if user_input is not None:
            options[host] = normalize_options(user_input)
            return self.async_create_entry(data=options)

        label = next((s[CONF_LABEL] for s in self._systeme() if s[CONF_HOST] == host), host)
        return self.async_show_form(
            step_id="system",
            data_schema=level_schema(options.get(host, {}), mit_intervall=False),
            description_placeholders={"anlage": f"{label} ({host})".strip()},
        )

    async def async_step_anlage_0(self, user_input=None) -> ConfigFlowResult:
        """Erste Anlage."""
        return await self._anlage(0, user_input)

    async def async_step_anlage_1(self, user_input=None) -> ConfigFlowResult:
        """Zweite Anlage."""
        return await self._anlage(1, user_input)

    async def async_step_anlage_2(self, user_input=None) -> ConfigFlowResult:
        """Dritte Anlage."""
        return await self._anlage(2, user_input)

    async def async_step_anlage_3(self, user_input=None) -> ConfigFlowResult:
        """Vierte Anlage."""
        return await self._anlage(3, user_input)

    async def async_step_anlage_4(self, user_input=None) -> ConfigFlowResult:
        """Fünfte Anlage."""
        return await self._anlage(4, user_input)

    async def async_step_anlage_5(self, user_input=None) -> ConfigFlowResult:
        """Sechste Anlage."""
        return await self._anlage(5, user_input)

    async def _anlage(self, index: int, user_input) -> ConfigFlowResult:
        """Menüauswahl auf den gemeinsamen Schritt lenken."""
        systeme = self._systeme()
        if index < len(systeme):
            self._host = systeme[index][CONF_HOST]
        return await self.async_step_system(user_input)
